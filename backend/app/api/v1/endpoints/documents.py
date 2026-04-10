"""
JurisIA — Endpoints Documents
Routes pour l'upload, l'analyse, la génération et la gestion des documents.
Ces endpoints sont le cœur de la valeur produit de JurisIA.
"""
from __future__ import annotations

import mimetypes
from typing import Annotated, Optional
from datetime import datetime, timezone

import structlog
from fastapi import (
    APIRouter,
    BackgroundTasks,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import StreamingResponse, Response, Response
from pydantic import BaseModel, Field
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import (
    CurrentVerifiedUser,
    CurrentOrg,
    CurrentSubscription,
    DB,
)
from app.core.security import generate_ulid
from app.db.database import get_db
from app.models import (
    Document,
    DocumentClause,
    DocumentStatus,
    DocumentType,
    Organization,
    Subscription,
    SubscriptionPlan,
    UsageQuota,
    User,
)
from app.services.documents.analysis_service import DocumentAnalysisService
from app.services.documents.generation_service import DocumentGenerationService
from app.services.documents.storage_service import StorageService
from app.services.documents.quota_service import QuotaService

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/documents", tags=["Documents"])

# ─── Constantes ───────────────────────────────────────────────────────────────
MAX_FILE_SIZE_MB = 20
MAX_FILE_SIZE_BYTES = MAX_FILE_SIZE_MB * 1024 * 1024
ALLOWED_MIME_TYPES = {
    "application/pdf",
    "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    "application/msword",
    "text/plain",
}


# ─── Schémas de réponse ───────────────────────────────────────────────────────

class ClauseResponse(BaseModel):
    id: str
    clause_text: str
    risk_level: str
    explanation: str
    suggestion: Optional[str]
    legal_reference: Optional[str]
    legal_reference_url: Optional[str]
    position_start: Optional[int]

    model_config = {"from_attributes": True}


class DocumentResponse(BaseModel):
    id: str
    title: str
    doc_type: str
    category: Optional[str]
    sub_category: Optional[str]
    status: str
    score: Optional[int]
    created_at: datetime
    updated_at: datetime
    analysis_result: Optional[dict]
    metadata_: Optional[dict] = Field(None, alias="metadata")

    model_config = {"from_attributes": True, "populate_by_name": True}


class DocumentDetailResponse(DocumentResponse):
    clauses: list[ClauseResponse] = []


class DocumentListResponse(BaseModel):
    items: list[DocumentResponse]
    total: int
    page: int
    page_size: int


class GenerateDocumentRequest(BaseModel):
    """Corps de requête pour la génération d'un document."""
    template_key: str = Field(
        ...,
        description="Identifiant du template",
        examples=["prestation_services", "cgv", "nda", "lettre_relance_1"],
    )
    title: str = Field(..., min_length=2, max_length=255)
    form_data: dict = Field(
        ...,
        description="Données du formulaire guidé (champs variables selon le template)",
    )


class DocumentStatusResponse(BaseModel):
    id: str
    status: str
    score: Optional[int]
    error_message: Optional[str]


# ─── POST /documents/analyze ──────────────────────────────────────────────────

@router.post(
    "/analyze",
    response_model=DocumentStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Analyser un document (upload + analyse IA)",
    description=(
        "Upload un document PDF/DOCX et lance son analyse IA de manière asynchrone. "
        "Retourne immédiatement un ID de document. "
        "Utilisez GET /documents/{id} pour récupérer les résultats quand status=completed."
    ),
)
async def analyze_document(
    background_tasks: BackgroundTasks,
    current_user: CurrentVerifiedUser,
    org: CurrentOrg,
    subscription: CurrentSubscription,
    db: DB,
    file: UploadFile = File(..., description="Document à analyser (PDF, DOCX, TXT — max 20 Mo)"),
) -> DocumentStatusResponse:
    # 1. Vérifier les quotas
    quota_svc = QuotaService(db)
    can_analyze, reason = await quota_svc.check_quota(org.id, subscription.plan, "documents_analyzed")
    if not can_analyze:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={
                "code": "QUOTA_EXCEEDED",
                "message": reason,
                "action": "Passez à un plan supérieur sur /billing/upgrade",
            },
        )

    # 2. Valider le fichier
    content = await file.read()
    _validate_file(file.filename or "document", content)

    # 3. Uploader vers S3
    storage_svc = StorageService()
    doc_id = generate_ulid()
    file_path = await storage_svc.upload_document(
        content=content,
        document_id=doc_id,
        original_filename=file.filename or "document",
        organization_id=org.id,
    )

    # 4. Créer l'entrée Document en BDD
    document = Document(
        id=doc_id,
        organization_id=org.id,
        created_by=current_user.id,
        title=file.filename or "Document sans titre",
        doc_type=DocumentType.ANALYSIS,
        status=DocumentStatus.PENDING,
        file_path=file_path,
    )
    db.add(document)
    await db.flush()

    # 5. Incrémenter le quota utilisé
    await quota_svc.increment_usage(org.id, "documents_analyzed")

    # 6. Lancer l'analyse en arrière-plan
    background_tasks.add_task(
        _run_analysis_background,
        doc_id=doc_id,
        content=content,
        filename=file.filename or "document",
        sector=org.sector_label or "services",
        employee_count=org.employee_count_range or "11-50",
    )

    logger.info("document_analysis_queued", document_id=doc_id, org_id=org.id)

    return DocumentStatusResponse(
        id=doc_id,
        status=DocumentStatus.PENDING.value,
        score=None,
        error_message=None,
    )


async def _run_analysis_background(
    doc_id: str,
    content: bytes,
    filename: str,
    sector: str,
    employee_count: str,
) -> None:
    """Tâche d'arrière-plan FastAPI pour l'analyse (MVP sans Celery complet)."""
    from app.db.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            svc = DocumentAnalysisService(db)
            await svc.analyze_document(
                document_id=doc_id,
                file_content=content,
                filename=filename,
                organization_sector=sector,
                employee_count=employee_count,
            )
            await db.commit()
        except Exception as e:
            logger.error("background_analysis_failed", doc_id=doc_id, error=str(e))
            await db.rollback()


# ─── POST /documents/generate ─────────────────────────────────────────────────

@router.post(
    "/generate",
    response_model=DocumentStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Générer un document juridique",
    description="Génère un document juridique à partir d'un template et de données de formulaire.",
)
async def generate_document(
    body: GenerateDocumentRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentVerifiedUser,
    org: CurrentOrg,
    subscription: CurrentSubscription,
    db: DB,
) -> DocumentStatusResponse:
    # 1. Vérifier les quotas
    quota_svc = QuotaService(db)
    can_generate, reason = await quota_svc.check_quota(org.id, subscription.plan, "documents_generated")
    if not can_generate:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"code": "QUOTA_EXCEEDED", "message": reason, "action": "Upgrader votre plan"},
        )

    # 2. Valider que le template existe
    gen_svc = DocumentGenerationService(db)
    if not gen_svc.template_exists(body.template_key):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "TEMPLATE_NOT_FOUND", "message": f"Template '{body.template_key}' introuvable"},
        )

    # 3. Créer le document en BDD
    doc_id = generate_ulid()
    category, sub_category = gen_svc.get_template_category(body.template_key)

    document = Document(
        id=doc_id,
        organization_id=org.id,
        created_by=current_user.id,
        title=body.title,
        doc_type=DocumentType.GENERATED,
        category=category,
        sub_category=sub_category,
        status=DocumentStatus.PENDING,
        generated_content={"template_key": body.template_key, "form_data": body.form_data},
    )
    db.add(document)
    await db.flush()

    # 4. Incrémenter quota
    await quota_svc.increment_usage(org.id, "documents_generated")

    # 5. Générer en arrière-plan
    background_tasks.add_task(
        _run_generation_background,
        doc_id=doc_id,
        template_key=body.template_key,
        form_data=body.form_data,
        org_name=org.name,
    )

    logger.info("document_generation_queued", document_id=doc_id, template=body.template_key)

    return DocumentStatusResponse(id=doc_id, status="pending", score=None, error_message=None)


async def _run_generation_background(
    doc_id: str, template_key: str, form_data: dict, org_name: str
) -> None:
    from app.db.database import AsyncSessionLocal
    async with AsyncSessionLocal() as db:
        try:
            svc = DocumentGenerationService(db)
            await svc.generate_document(
                document_id=doc_id,
                template_key=template_key,
                form_data=form_data,
                org_name=org_name,
            )
            await db.commit()
        except Exception as e:
            logger.error("background_generation_failed", doc_id=doc_id, error=str(e))
            await db.rollback()


# ─── GET /documents ───────────────────────────────────────────────────────────

@router.get(
    "",
    response_model=DocumentListResponse,
    summary="Liste des documents de l'organisation",
)
async def list_documents(
    current_user: CurrentVerifiedUser,
    org: CurrentOrg,
    db: DB,
    page: int = Query(1, ge=1, description="Numéro de page"),
    page_size: int = Query(20, ge=1, le=100, description="Éléments par page"),
    doc_type: Optional[str] = Query(None, description="Filtrer par type : analysis | generated"),
    status_filter: Optional[str] = Query(None, alias="status", description="Filtrer par statut"),
) -> DocumentListResponse:
    offset = (page - 1) * page_size

    query = select(Document).where(Document.organization_id == org.id)

    if doc_type:
        query = query.where(Document.doc_type == doc_type)
    if status_filter:
        query = query.where(Document.status == status_filter)

    # Total
    from sqlalchemy import func, select as sa_select
    count_result = await db.execute(
        sa_select(func.count()).select_from(
            query.subquery()
        )
    )
    total = count_result.scalar_one()

    # Données paginées
    result = await db.execute(
        query.order_by(desc(Document.created_at)).offset(offset).limit(page_size)
    )
    documents = result.scalars().all()

    return DocumentListResponse(
        items=[DocumentResponse.model_validate(d) for d in documents],
        total=total,
        page=page,
        page_size=page_size,
    )


# ─── GET /documents/{id} ──────────────────────────────────────────────────────

@router.get(
    "/{document_id}",
    response_model=DocumentDetailResponse,
    summary="Détails d'un document avec ses clauses",
)
async def get_document(
    document_id: str,
    current_user: CurrentVerifiedUser,
    org: CurrentOrg,
    db: DB,
) -> DocumentDetailResponse:
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.organization_id == org.id,
        )
    )
    document = result.scalar_one_or_none()

    if not document:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={"code": "DOCUMENT_NOT_FOUND", "message": "Document introuvable"},
        )

    # Charger les clauses si c'est une analyse complétée
    clauses = []
    if document.doc_type == DocumentType.ANALYSIS and document.status == DocumentStatus.COMPLETED:
        clauses_result = await db.execute(
            select(DocumentClause)
            .where(DocumentClause.document_id == document_id)
            .order_by(DocumentClause.position_start)
        )
        clauses = clauses_result.scalars().all()

    response = DocumentDetailResponse.model_validate(document)
    response.clauses = [ClauseResponse.model_validate(c) for c in clauses]
    return response


# ─── GET /documents/{id}/status ───────────────────────────────────────────────

@router.get(
    "/{document_id}/status",
    response_model=DocumentStatusResponse,
    summary="Statut d'un document (polling pendant le traitement IA)",
)
async def get_document_status(
    document_id: str,
    current_user: CurrentVerifiedUser,
    org: CurrentOrg,
    db: DB,
) -> DocumentStatusResponse:
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.organization_id == org.id,
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail={"code": "DOCUMENT_NOT_FOUND", "message": "Document introuvable"})

    return DocumentStatusResponse(
        id=document.id,
        status=document.status.value,
        score=document.score,
        error_message=document.error_message,
    )


# ─── GET /documents/{id}/download ─────────────────────────────────────────────

@router.get(
    "/{document_id}/download",
    summary="Télécharger un document (PDF ou DOCX)",
)
async def download_document(
    document_id: str,
    current_user: CurrentVerifiedUser,
    org: CurrentOrg,
    db: DB,
    format: str = Query("pdf", description="Format : pdf | docx"),
):
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.organization_id == org.id,
            Document.status == DocumentStatus.COMPLETED,
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail={"code": "DOCUMENT_NOT_FOUND", "message": "Document non disponible"})

    if format not in ("pdf", "docx"):
        raise HTTPException(status_code=400, detail={"code": "INVALID_FORMAT", "message": "Format invalide. Utilisez pdf ou docx"})

    storage_svc = StorageService()

    if document.doc_type == DocumentType.ANALYSIS:
        # Générer le rapport PDF d'analyse
        from app.services.documents.pdf_service import PDFReportService
        pdf_service = PDFReportService()
        clauses_result = await db.execute(
            select(DocumentClause).where(DocumentClause.document_id == document_id)
        )
        clauses = clauses_result.scalars().all()
        pdf_bytes = await pdf_service.generate_analysis_report(document, clauses)
        return StreamingResponse(
            iter([pdf_bytes]),
            media_type="application/pdf",
            headers={"Content-Disposition": f'attachment; filename="analyse-{document_id[:8]}.pdf"'},
        )
    else:
        # Document généré : récupérer depuis S3 ou régénérer
        if document.file_path:
            file_stream = await storage_svc.download_document(document.file_path)
            mime_type = "application/pdf" if format == "pdf" else "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            ext = format
            return StreamingResponse(
                file_stream,
                media_type=mime_type,
                headers={"Content-Disposition": f'attachment; filename="{document.title[:50]}.{ext}"'},
            )
        raise HTTPException(status_code=404, detail={"code": "FILE_NOT_FOUND", "message": "Fichier non disponible"})


# ─── DELETE /documents/{id} ───────────────────────────────────────────────────

@router.delete(
    "/{document_id}",
    status_code=200,
    summary="Supprimer un document",
)
async def delete_document(
    document_id: str,
    current_user: CurrentVerifiedUser,
    org: CurrentOrg,
    db: DB,
):
    result = await db.execute(
        select(Document).where(
            Document.id == document_id,
            Document.organization_id == org.id,
        )
    )
    document = result.scalar_one_or_none()
    if not document:
        raise HTTPException(status_code=404, detail={"code": "DOCUMENT_NOT_FOUND", "message": "Document introuvable"})

    # Supprimer le fichier S3 si présent
    if document.file_path:
        try:
            storage_svc = StorageService()
            await storage_svc.delete_document(document.file_path)
        except Exception as e:
            logger.warning("s3_delete_failed", doc_id=document_id, error=str(e))

    await db.delete(document)
    logger.info("document_deleted", document_id=document_id, org_id=org.id)


# ─── GET /documents/templates ─────────────────────────────────────────────────

@router.get(
    "/templates/list",
    summary="Liste des templates de documents disponibles",
)
async def list_templates(current_user: CurrentVerifiedUser, subscription: CurrentSubscription):
    """Retourne les templates disponibles selon le plan d'abonnement."""
    from app.services.documents.generation_service import DOCUMENT_TEMPLATES
    templates = []
    for key, tpl in DOCUMENT_TEMPLATES.items():
        required_plan = tpl.get("required_plan", SubscriptionPlan.FREE)
        is_available = (
            subscription.plan == SubscriptionPlan.BUSINESS or
            (subscription.plan == SubscriptionPlan.PRO and required_plan in [SubscriptionPlan.FREE, SubscriptionPlan.STARTER, SubscriptionPlan.PRO]) or
            (subscription.plan == SubscriptionPlan.STARTER and required_plan in [SubscriptionPlan.FREE, SubscriptionPlan.STARTER]) or
            (subscription.plan == SubscriptionPlan.FREE and required_plan == SubscriptionPlan.FREE)
        )
        templates.append({
            "key": key,
            "name": tpl["name"],
            "category": tpl["category"],
            "description": tpl["description"],
            "fields": tpl["fields"],
            "available": is_available,
            "required_plan": required_plan.value if not is_available else None,
        })
    return {"templates": templates}


# ─── Validation fichier ───────────────────────────────────────────────────────

def _validate_file(filename: str, content: bytes) -> None:
    """Valide le type et la taille du fichier uploadé."""
    if len(content) > MAX_FILE_SIZE_BYTES:
        raise HTTPException(
            status_code=status.HTTP_413_REQUEST_ENTITY_TOO_LARGE,
            detail={
                "code": "FILE_TOO_LARGE",
                "message": f"Le fichier dépasse la limite de {MAX_FILE_SIZE_MB} Mo",
            },
        )
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "EMPTY_FILE", "message": "Le fichier est vide"},
        )
    # Vérifier l'extension
    allowed_extensions = {".pdf", ".docx", ".doc", ".txt"}
    ext = "." + filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
    if ext not in allowed_extensions:
        raise HTTPException(
            status_code=status.HTTP_415_UNSUPPORTED_MEDIA_TYPE,
            detail={
                "code": "UNSUPPORTED_FILE_TYPE",
                "message": f"Format non supporté : {ext}. Formats acceptés : PDF, DOCX, TXT",
            },
        )
