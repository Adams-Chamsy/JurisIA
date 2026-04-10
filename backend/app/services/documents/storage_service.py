"""
JurisIA — Services Auxiliaires Documents
StorageService : upload/download fichiers S3-compatible (OVH/MinIO)
QuotaService  : vérification et comptage des quotas par plan
PDFReportService : génération de rapports PDF d'analyse
"""
from __future__ import annotations

import io
from datetime import datetime, timezone
from typing import Optional

import structlog
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models import Document, DocumentClause, Subscription, SubscriptionPlan, UsageQuota

logger = structlog.get_logger(__name__)


# ─── StorageService ───────────────────────────────────────────────────────────

class StorageService:
    """
    Gestion du stockage de fichiers sur S3-compatible (OVH Object Storage en prod, MinIO en dev).
    En dev sans S3 configuré, simule le stockage (retourne un chemin fictif).
    """

    def _get_client(self):
        import boto3
        kwargs = {
            "aws_access_key_id": settings.S3_ACCESS_KEY_ID,
            "aws_secret_access_key": settings.S3_SECRET_ACCESS_KEY,
            "region_name": settings.S3_REGION,
        }
        if settings.S3_ENDPOINT_URL:
            kwargs["endpoint_url"] = settings.S3_ENDPOINT_URL
        return boto3.client("s3", **kwargs)

    def _is_s3_available(self) -> bool:
        """En dev sans S3_ENDPOINT_URL configuré et sans credentials, bypass le storage."""
        return bool(
            settings.S3_ACCESS_KEY_ID != "minioadmin" or settings.S3_ENDPOINT_URL
        )

    async def upload_document(
        self,
        content: bytes,
        document_id: str,
        original_filename: str,
        organization_id: str,
    ) -> str:
        """Upload un document et retourne son chemin S3."""
        ext = original_filename.rsplit(".", 1)[-1].lower() if "." in original_filename else "bin"
        key = f"orgs/{organization_id}/documents/{document_id}/original.{ext}"

        if not self._is_s3_available():
            logger.debug("s3_bypassed_dev_mode", key=key)
            return key  # En dev sans S3, retourner juste le chemin

        try:
            client = self._get_client()
            client.put_object(
                Bucket=settings.S3_BUCKET_NAME,
                Key=key,
                Body=content,
                ContentType=self._get_content_type(ext),
                ServerSideEncryption="AES256",
                Metadata={"organization-id": organization_id, "document-id": document_id},
            )
            logger.info("file_uploaded", key=key, size_bytes=len(content))
            return key
        except Exception as e:
            logger.error("s3_upload_failed", key=key, error=str(e))
            return key  # Dégradé : continuer sans S3

    async def upload_generated_document(
        self,
        content: bytes,
        document_id: str,
        organization_id: str,
        extension: str = "docx",
    ) -> str:
        """Upload un document généré."""
        key = f"orgs/{organization_id}/generated/{document_id}/document.{extension}"

        if not self._is_s3_available():
            return key

        try:
            client = self._get_client()
            client.put_object(
                Bucket=settings.S3_BUCKET_NAME,
                Key=key,
                Body=content,
                ContentType=self._get_content_type(extension),
                ServerSideEncryption="AES256",
            )
            return key
        except Exception as e:
            logger.error("s3_upload_generated_failed", key=key, error=str(e))
            return key

    async def download_document(self, file_path: str):
        """Télécharge un document depuis S3 et retourne un stream."""
        if not self._is_s3_available():
            return iter([b"Document non disponible en mode developpement sans S3"])

        client = self._get_client()
        response = client.get_object(Bucket=settings.S3_BUCKET_NAME, Key=file_path)
        return response["Body"]

    async def delete_document(self, file_path: str) -> None:
        """Supprime un fichier de S3."""
        if not self._is_s3_available():
            return
        client = self._get_client()
        client.delete_object(Bucket=settings.S3_BUCKET_NAME, Key=file_path)

    @staticmethod
    def _get_content_type(ext: str) -> str:
        types = {
            "pdf": "application/pdf",
            "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            "doc": "application/msword",
            "txt": "text/plain",
        }
        return types.get(ext.lower(), "application/octet-stream")


# ─── QuotaService ─────────────────────────────────────────────────────────────

# Mapping plan → quotas mensuels
PLAN_QUOTAS = {
    SubscriptionPlan.FREE: {
        "documents_analyzed": settings.QUOTA_FREE_DOCUMENTS,
        "documents_generated": settings.QUOTA_FREE_DOCUMENTS,
        "questions_asked": 10,
        "is_lifetime": True,  # Free = limite vie, pas mensuelle
    },
    SubscriptionPlan.STARTER: {
        "documents_analyzed": settings.QUOTA_STARTER_DOCUMENTS_PER_MONTH,
        "documents_generated": settings.QUOTA_STARTER_DOCUMENTS_PER_MONTH,
        "questions_asked": settings.QUOTA_STARTER_QUESTIONS_PER_MONTH,
        "is_lifetime": False,
    },
    SubscriptionPlan.PRO: {
        "documents_analyzed": settings.QUOTA_PRO_DOCUMENTS_PER_MONTH,
        "documents_generated": settings.QUOTA_PRO_DOCUMENTS_PER_MONTH,
        "questions_asked": settings.QUOTA_PRO_QUESTIONS_PER_MONTH,
        "is_lifetime": False,
    },
    SubscriptionPlan.BUSINESS: {
        "documents_analyzed": 99999,
        "documents_generated": 99999,
        "questions_asked": 99999,
        "is_lifetime": False,
    },
}

QUOTA_FIELD_MAP = {
    "documents_analyzed": "documents_analyzed",
    "documents_generated": "documents_generated",
    "questions_asked": "questions_asked",
}


class QuotaService:

    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_quota(
        self, org_id: str, plan: SubscriptionPlan, quota_type: str
    ) -> tuple[bool, str]:
        """
        Vérifie si l'organisation peut effectuer une action.
        Retourne (peut_agir, message_erreur).
        """
        plan_limits = PLAN_QUOTAS.get(plan, PLAN_QUOTAS[SubscriptionPlan.FREE])
        limit = plan_limits.get(quota_type, 0)

        if limit >= 9999:  # Illimité
            return True, ""

        usage = await self._get_usage(org_id, plan_limits.get("is_lifetime", False))
        current_count = getattr(usage, QUOTA_FIELD_MAP.get(quota_type, quota_type), 0)

        if current_count >= limit:
            plan_name = plan.value.capitalize()
            return False, (
                f"Limite atteinte : {current_count}/{limit} {quota_type.replace('_', ' ')} "
                f"pour le plan {plan_name}. "
                f"Passez à un plan supérieur pour continuer."
            )

        return True, ""

    async def increment_usage(self, org_id: str, quota_type: str) -> None:
        """Incrémente le compteur d'usage pour l'organisation."""
        now = datetime.now(timezone.utc)
        period_year = now.year
        period_month = now.month

        result = await self.db.execute(
            select(UsageQuota).where(
                UsageQuota.organization_id == org_id,
                UsageQuota.period_year == period_year,
                UsageQuota.period_month == period_month,
            )
        )
        quota = result.scalar_one_or_none()

        if not quota:
            from app.core.security import generate_ulid
            quota = UsageQuota(
                id=generate_ulid(),
                organization_id=org_id,
                period_year=period_year,
                period_month=period_month,
            )
            self.db.add(quota)

        field = QUOTA_FIELD_MAP.get(quota_type, quota_type)
        current_val = getattr(quota, field, 0)
        setattr(quota, field, current_val + 1)
        await self.db.flush()

    async def _get_usage(self, org_id: str, is_lifetime: bool) -> UsageQuota:
        """Récupère l'usage actuel (mensuel ou total selon le plan)."""
        now = datetime.now(timezone.utc)

        if is_lifetime:
            # Pour le plan Free : total toutes périodes confondues
            result = await self.db.execute(
                select(
                    func.sum(UsageQuota.documents_analyzed).label("documents_analyzed"),
                    func.sum(UsageQuota.documents_generated).label("documents_generated"),
                    func.sum(UsageQuota.questions_asked).label("questions_asked"),
                ).where(UsageQuota.organization_id == org_id)
            )
            row = result.one()
            # Créer un objet temporaire avec les totaux
            mock = UsageQuota()
            mock.documents_analyzed = row.documents_analyzed or 0
            mock.documents_generated = row.documents_generated or 0
            mock.questions_asked = row.questions_asked or 0
            return mock
        else:
            # Pour les plans payants : usage du mois en cours
            result = await self.db.execute(
                select(UsageQuota).where(
                    UsageQuota.organization_id == org_id,
                    UsageQuota.period_year == now.year,
                    UsageQuota.period_month == now.month,
                )
            )
            quota = result.scalar_one_or_none()
            if not quota:
                from app.core.security import generate_ulid
                return UsageQuota(
                    id=generate_ulid(),
                    organization_id=org_id,
                    period_year=now.year,
                    period_month=now.month,
                )
            return quota


# ─── PDFReportService ─────────────────────────────────────────────────────────

class PDFReportService:
    """Génère des rapports PDF professionnels pour les analyses de documents."""

    async def generate_analysis_report(
        self, document: Document, clauses: list[DocumentClause]
    ) -> bytes:
        """Génère un rapport PDF d'analyse complet."""
        from reportlab.lib.pagesizes import A4
        from reportlab.lib import colors
        from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
        from reportlab.lib.units import mm
        from reportlab.platypus import (
            SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle, HRFlowable
        )

        buffer = io.BytesIO()
        doc = SimpleDocTemplate(
            buffer,
            pagesize=A4,
            rightMargin=20 * mm,
            leftMargin=20 * mm,
            topMargin=25 * mm,
            bottomMargin=20 * mm,
        )

        styles = getSampleStyleSheet()
        story = []

        # ── Header ──
        story.append(Paragraph(
            '<font color="#0F2447" size="18"><b>JurisIA — Rapport d\'Analyse</b></font>',
            styles["Title"],
        ))
        story.append(Paragraph(
            f'<font size="11" color="#64748B">{document.title}</font>',
            styles["Normal"],
        ))
        story.append(Paragraph(
            f'<font size="9" color="#64748B">Analysé le '
            f'{document.updated_at.strftime("%d/%m/%Y à %H:%M")} (UTC)</font>',
            styles["Normal"],
        ))
        story.append(Spacer(1, 10 * mm))
        story.append(HRFlowable(width="100%", thickness=1, color=colors.HexColor("#E2E8F0")))
        story.append(Spacer(1, 5 * mm))

        # ── Score global ──
        score = document.score or 0
        score_color = "#16A34A" if score >= 70 else "#D97706" if score >= 40 else "#DC2626"
        story.append(Paragraph(
            f'<font size="14"><b>Score de Solidité Juridique : </b>'
            f'<font color="{score_color}"><b>{score}/100</b></font></font>',
            styles["Normal"],
        ))
        story.append(Spacer(1, 5 * mm))

        # Résumé
        analysis = document.analysis_result or {}
        if analysis.get("summary"):
            story.append(Paragraph("<b>Résumé Exécutif</b>", styles["Heading2"]))
            story.append(Paragraph(analysis["summary"], styles["Normal"]))
            story.append(Spacer(1, 5 * mm))

        # Compteurs
        risk_counts = analysis.get("risk_counts", {})
        if risk_counts:
            story.append(Paragraph("<b>Synthèse des Clauses</b>", styles["Heading2"]))
            table_data = [
                ["Niveau", "Nombre", "Signification"],
                ["🔴 Danger", str(risk_counts.get("danger", 0)), "Action corrective urgente"],
                ["🟡 Avertissement", str(risk_counts.get("warning", 0)), "À négocier ou clarifier"],
                ["✅ Conforme", str(risk_counts.get("safe", 0)), "Clause équilibrée"],
                ["⚠️ Manquante", str(risk_counts.get("missing", 0)), "Clause recommandée absente"],
            ]
            table = Table(table_data, colWidths=[45 * mm, 25 * mm, 90 * mm])
            table.setStyle(TableStyle([
                ("BACKGROUND", (0, 0), (-1, 0), colors.HexColor("#0F2447")),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, colors.HexColor("#E2E8F0")),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, colors.HexColor("#F8FAFC")]),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]))
            story.append(table)
            story.append(Spacer(1, 8 * mm))

        # Détail des clauses
        story.append(Paragraph("<b>Analyse Clause par Clause</b>", styles["Heading2"]))

        risk_order = {"danger": 0, "missing": 1, "warning": 2, "safe": 3}
        sorted_clauses = sorted(clauses, key=lambda c: risk_order.get(c.risk_level.value, 99))

        for i, clause in enumerate(sorted_clauses, 1):
            risk_colors = {
                "danger": "#DC2626",
                "warning": "#D97706",
                "safe": "#16A34A",
                "missing": "#D97706",
            }
            risk_labels = {
                "danger": "🔴 RISQUE ÉLEVÉ",
                "warning": "🟡 AVERTISSEMENT",
                "safe": "✅ CONFORME",
                "missing": "⚠️ MANQUANT",
            }
            color = risk_colors.get(clause.risk_level.value, "#64748B")
            label = risk_labels.get(clause.risk_level.value, clause.risk_level.value.upper())

            story.append(Paragraph(
                f'<font color="{color}"><b>{label}</b></font> — Clause {i}',
                styles["Heading3"],
            ))
            story.append(Paragraph(
                f'<i>"{clause.clause_text[:200]}..."</i>' if len(clause.clause_text) > 200
                else f'<i>"{clause.clause_text}"</i>',
                styles["Normal"],
            ))
            story.append(Paragraph(f"<b>Explication :</b> {clause.explanation}", styles["Normal"]))
            if clause.suggestion:
                story.append(Paragraph(
                    f'<font color="#1E5FD8"><b>Recommandation :</b> {clause.suggestion}</font>',
                    styles["Normal"],
                ))
            if clause.legal_reference:
                story.append(Paragraph(
                    f'<font size="8" color="#64748B">📖 Référence : {clause.legal_reference}</font>',
                    styles["Normal"],
                ))
            story.append(Spacer(1, 4 * mm))

        # Footer disclaimer
        story.append(HRFlowable(width="100%", thickness=0.5, color=colors.HexColor("#E2E8F0")))
        story.append(Paragraph(
            '<font size="7" color="#DC2626">⚠️ Ce rapport est fourni à titre informatif. '
            'Il ne constitue pas un conseil juridique professionnel. '
            'Pour toute décision importante, consultez un avocat qualifié. '
            f'Généré par JurisIA le {datetime.now(timezone.utc).strftime("%d/%m/%Y")}</font>',
            styles["Normal"],
        ))

        doc.build(story)
        return buffer.getvalue()
