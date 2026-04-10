"""
JurisIA — Assistant Conversationnel Juridique
Endpoints et service pour le chat IA avec contexte conversationnel et RAG.
"""
from __future__ import annotations

from typing import Optional, AsyncGenerator
import json

import structlog
from fastapi import APIRouter, HTTPException, Query, status
from fastapi.responses import Response
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import CurrentVerifiedUser, CurrentOrg, CurrentSubscription, DB
from app.core.config import settings
from app.core.security import generate_ulid
from app.models import Conversation, ConversationMessage, MessageRole, UsageQuota
from app.services.documents.quota_service import QuotaService

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/chat", tags=["Assistant Juridique"])

# ─── Prompt Système ───────────────────────────────────────────────────────────

CHAT_SYSTEM_PROMPT = """Tu es JurisIA, un assistant juridique expert en droit français des affaires et droit du travail.
Tu aides les dirigeants de PME françaises à comprendre leurs obligations légales et à prendre des décisions éclairées.

RÈGLES FONDAMENTALES :
1. Tu réponds TOUJOURS en français, avec un langage accessible (niveau terminale, pas de jargon sans explication)
2. Tu cites SYSTÉMATIQUEMENT les références légales applicables (Code du travail, Code civil, Code de commerce)
3. Tu distingues clairement ce que tu affirmes avec certitude de ce qui est incertain
4. Tu rappelles TOUJOURS en fin de réponse complexe : "Cette réponse est informative. Pour une décision engageant votre responsabilité, consultez un avocat."
5. Si la question dépasse ton périmètre (droit pénal, fiscalité complexe, contentieux actif), tu le signales et recommandes un spécialiste
6. Tu proposes quand c'est pertinent de générer un document associé

PÉRIMÈTRE :
✅ Contrats commerciaux, CGV, NDA
✅ Droit du travail : embauche, licenciement, rupture conventionnelle, sanctions
✅ RGPD et conformité numérique
✅ AI Act et obligations IA
✅ Recouvrement de créances (jusqu'à la mise en demeure)
✅ Obligations légales des entreprises (mentions obligatoires, formalités)

❌ Droit pénal
❌ Fiscalité (renvoyer vers un expert-comptable)
❌ Contentieux actif en cours
❌ Droit de la famille

FORMAT DE RÉPONSE :
- Commence par la réponse directe à la question
- Structure avec des points numérotés pour les réponses multi-étapes
- Cite les articles de loi entre parenthèses : (Article L1237-19 du Code du travail)
- Termine par "📖 Références : " avec les articles cités
- Si un document peut être généré : "[💼 Je peux générer ce document pour vous]"
"""

# ─── Schémas ─────────────────────────────────────────────────────────────────

class SendMessageRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=5000)
    conversation_id: Optional[str] = Field(None, description="ID de la conversation (None = nouvelle)")


class MessageResponse(BaseModel):
    id: str
    role: str
    content: str
    sources: Optional[list] = None
    created_at: str

    model_config = {"from_attributes": True}


class ConversationResponse(BaseModel):
    id: str
    title: Optional[str]
    created_at: str
    updated_at: str
    message_count: int = 0

    model_config = {"from_attributes": True}


class ConversationDetailResponse(ConversationResponse):
    messages: list[MessageResponse] = []


# ─── POST /chat/messages ──────────────────────────────────────────────────────

@router.post(
    "/messages",
    summary="Envoyer un message à l'assistant juridique",
    description="Envoie un message et reçoit une réponse juridique IA avec sources. Streaming disponible.",
)
async def send_message(
    body: SendMessageRequest,
    current_user: CurrentVerifiedUser,
    org: CurrentOrg,
    subscription: CurrentSubscription,
    db: DB,
) -> MessageResponse:
    # 1. Vérifier les quotas
    quota_svc = QuotaService(db)
    can_ask, reason = await quota_svc.check_quota(org.id, subscription.plan, "questions_asked")
    if not can_ask:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "QUOTA_EXCEEDED", "message": reason, "action": "Upgrader votre plan"},
        )

    # 2. Récupérer ou créer la conversation
    conversation = await _get_or_create_conversation(
        db=db,
        conversation_id=body.conversation_id,
        org_id=org.id,
        user_id=current_user.id,
        first_message=body.message,
    )

    # 3. Sauvegarder le message utilisateur
    user_msg = ConversationMessage(
        id=generate_ulid(),
        conversation_id=conversation.id,
        role=MessageRole.USER,
        content=body.message,
    )
    db.add(user_msg)
    await db.flush()

    # 4. Récupérer l'historique pour le contexte
    history = await _get_conversation_history(db, conversation.id, limit=10)

    # 5. Générer la réponse IA
    svc = ChatService()
    ai_response, sources, tokens_used = await svc.generate_response(
        user_message=body.message,
        conversation_history=history,
        org_sector=org.sector_label or "services",
    )

    # 6. Sauvegarder la réponse IA
    assistant_msg = ConversationMessage(
        id=generate_ulid(),
        conversation_id=conversation.id,
        role=MessageRole.ASSISTANT,
        content=ai_response,
        sources=sources,
        tokens_used=tokens_used,
    )
    db.add(assistant_msg)

    # 7. Incrémenter quota
    await quota_svc.increment_usage(org.id, "questions_asked")

    # 8. Mettre à jour le titre de la conversation si nouveau
    if not conversation.title:
        conversation.title = _generate_conversation_title(body.message)

    await db.flush()

    logger.info(
        "chat_message_processed",
        conversation_id=conversation.id,
        tokens=tokens_used,
        org_id=org.id,
    )

    return MessageResponse(
        id=assistant_msg.id,
        role="assistant",
        content=ai_response,
        sources=sources,
        created_at=assistant_msg.created_at.isoformat(),
    )


# ─── GET /chat/conversations ──────────────────────────────────────────────────

@router.get(
    "/conversations",
    response_model=list[ConversationResponse],
    summary="Liste des conversations",
)
async def list_conversations(
    current_user: CurrentVerifiedUser,
    org: CurrentOrg,
    db: DB,
    limit: int = Query(20, ge=1, le=100),
) -> list[ConversationResponse]:
    result = await db.execute(
        select(Conversation)
        .where(
            Conversation.organization_id == org.id,
            Conversation.user_id == current_user.id,
        )
        .order_by(desc(Conversation.updated_at))
        .limit(limit)
    )
    conversations = result.scalars().all()

    responses = []
    for conv in conversations:
        count_result = await db.execute(
            select(ConversationMessage).where(ConversationMessage.conversation_id == conv.id)
        )
        count = len(count_result.scalars().all())
        resp = ConversationResponse.model_validate(conv)
        resp.message_count = count
        responses.append(resp)

    return responses


# ─── GET /chat/conversations/{id} ────────────────────────────────────────────

@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationDetailResponse,
    summary="Détails d'une conversation avec tous ses messages",
)
async def get_conversation(
    conversation_id: str,
    current_user: CurrentVerifiedUser,
    org: CurrentOrg,
    db: DB,
) -> ConversationDetailResponse:
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.organization_id == org.id,
        )
    )
    conv = result.scalar_one_or_none()
    if not conv:
        raise HTTPException(status_code=404, detail={"code": "CONV_NOT_FOUND", "message": "Conversation introuvable"})

    messages_result = await db.execute(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation_id)
        .order_by(ConversationMessage.created_at)
    )
    messages = messages_result.scalars().all()

    resp = ConversationDetailResponse.model_validate(conv)
    resp.messages = [
        MessageResponse(
            id=m.id,
            role=m.role.value,
            content=m.content,
            sources=m.sources,
            created_at=m.created_at.isoformat(),
        )
        for m in messages
    ]
    resp.message_count = len(messages)
    return resp


# ─── DELETE /chat/conversations/{id} ─────────────────────────────────────────

@router.delete(
    "/conversations/{conversation_id}",
    status_code=200,
    summary="Supprimer une conversation",
)
async def delete_conversation(
    conversation_id: str,
    current_user: CurrentVerifiedUser,
    org: CurrentOrg,
    db: DB,
) -> None:
    result = await db.execute(
        select(Conversation).where(
            Conversation.id == conversation_id,
            Conversation.organization_id == org.id,
        )
    )
    conv = result.scalar_one_or_none()
    if conv:
        await db.delete(conv)


# ─── ChatService ─────────────────────────────────────────────────────────────

class ChatService:
    """Service de génération de réponses juridiques IA."""

    async def generate_response(
        self,
        user_message: str,
        conversation_history: list[dict],
        org_sector: str = "services",
    ) -> tuple[str, list[dict], int]:
        """
        Génère une réponse juridique.
        Retourne (réponse, sources_citées, tokens_utilisés).
        """
        from mistralai import Mistral
        import asyncio

        client = Mistral(api_key=settings.MISTRAL_API_KEY)

        # Construire les messages pour l'API
        messages = [{"role": "system", "content": CHAT_SYSTEM_PROMPT}]

        # Ajouter l'historique (fenêtre glissante de 10 messages)
        for msg in conversation_history[-10:]:
            messages.append({"role": msg["role"], "content": msg["content"]})

        # Ajouter le message courant avec le contexte secteur
        contextualized_message = (
            f"[Contexte: entreprise du secteur {org_sector}]\n\n{user_message}"
        )
        messages.append({"role": "user", "content": contextualized_message})

        for attempt in range(3):
            try:
                response = client.chat.complete(
                    model=settings.MISTRAL_MODEL,
                    messages=messages,
                    max_tokens=1500,
                    temperature=0.15,  # Légèrement plus élevé que l'analyse pour naturalité
                )

                content = response.choices[0].message.content
                tokens = response.usage.total_tokens if response.usage else 0

                # Extraire les références légales citées
                sources = self._extract_sources(content)

                return content, sources, tokens

            except Exception as e:
                if attempt == 2:
                    logger.error("chat_generation_failed", error=str(e))
                    return (
                        "Je rencontre une difficulté technique momentanée. "
                        "Veuillez réessayer dans quelques instants ou contacter le support.",
                        [],
                        0,
                    )
                await asyncio.sleep(2 ** attempt)

    def _extract_sources(self, text: str) -> list[dict]:
        """Extrait les références légales du texte de la réponse."""
        import re
        sources = []
        # Pattern : "Article LXXXX-XX du Code ..."
        pattern = r"Article\s+(L?\d+[-\d]*)\s+du\s+([^,\.\n]+)"
        matches = re.finditer(pattern, text, re.IGNORECASE)
        seen = set()
        for match in matches:
            article = match.group(1)
            code = match.group(2).strip()
            key = f"{article}-{code}"
            if key not in seen:
                seen.add(key)
                sources.append({
                    "article": f"Article {article}",
                    "code": code,
                    "text": match.group(0),
                    "url": self._build_legifrance_url(article, code),
                })
        return sources[:5]  # Max 5 sources

    @staticmethod
    def _build_legifrance_url(article: str, code: str) -> str:
        """Construit une URL Légifrance approximative."""
        code_lower = code.lower()
        if "travail" in code_lower:
            return f"https://www.legifrance.gouv.fr/codes/section_lc/LEGITEXT000006072050/"
        elif "civil" in code_lower:
            return f"https://www.legifrance.gouv.fr/codes/section_lc/LEGITEXT000006070721/"
        elif "commerce" in code_lower:
            return f"https://www.legifrance.gouv.fr/codes/section_lc/LEGITEXT000005634379/"
        return "https://www.legifrance.gouv.fr/"


# ─── Helpers ──────────────────────────────────────────────────────────────────

async def _get_or_create_conversation(
    db: AsyncSession,
    conversation_id: Optional[str],
    org_id: str,
    user_id: str,
    first_message: str,
) -> Conversation:
    if conversation_id:
        result = await db.execute(
            select(Conversation).where(
                Conversation.id == conversation_id,
                Conversation.organization_id == org_id,
            )
        )
        conv = result.scalar_one_or_none()
        if conv:
            return conv

    # Créer une nouvelle conversation
    conv = Conversation(
        id=generate_ulid(),
        organization_id=org_id,
        user_id=user_id,
        title=_generate_conversation_title(first_message),
    )
    db.add(conv)
    await db.flush()
    return conv


async def _get_conversation_history(
    db: AsyncSession, conversation_id: str, limit: int = 10
) -> list[dict]:
    result = await db.execute(
        select(ConversationMessage)
        .where(ConversationMessage.conversation_id == conversation_id)
        .order_by(desc(ConversationMessage.created_at))
        .limit(limit)
    )
    messages = list(reversed(result.scalars().all()))
    return [{"role": m.role.value, "content": m.content} for m in messages]


def _generate_conversation_title(first_message: str) -> str:
    """Génère un titre court à partir du premier message."""
    words = first_message.strip().split()
    title = " ".join(words[:8])
    if len(words) > 8:
        title += "..."
    return title[:100]
