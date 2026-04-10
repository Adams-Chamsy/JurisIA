"""
JurisIA — Service de Gestion des Quotas
Vérifie et incrémente les quotas d'utilisation par organisation selon le plan d'abonnement.
Extrait de storage_service.py pour respecter le principe de responsabilité unique (SRP).
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Optional

import structlog
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import generate_ulid
from app.models import Subscription, SubscriptionPlan, UsageQuota

logger = structlog.get_logger(__name__)

# ── Mapping Plan → Quotas ─────────────────────────────────────────────────────

PLAN_QUOTAS: dict[SubscriptionPlan, dict] = {
    SubscriptionPlan.FREE: {
        "documents_analyzed":    settings.QUOTA_FREE_DOCUMENTS,
        "documents_generated":   settings.QUOTA_FREE_DOCUMENTS,
        "questions_asked":       10,
        "signatures_used":       0,
        "is_lifetime":           True,   # Limite sur la vie du compte, pas mensuelle
    },
    SubscriptionPlan.STARTER: {
        "documents_analyzed":    settings.QUOTA_STARTER_DOCUMENTS_PER_MONTH,
        "documents_generated":   settings.QUOTA_STARTER_DOCUMENTS_PER_MONTH,
        "questions_asked":       settings.QUOTA_STARTER_QUESTIONS_PER_MONTH,
        "signatures_used":       0,
        "is_lifetime":           False,
    },
    SubscriptionPlan.PRO: {
        "documents_analyzed":    settings.QUOTA_PRO_DOCUMENTS_PER_MONTH,
        "documents_generated":   settings.QUOTA_PRO_DOCUMENTS_PER_MONTH,
        "questions_asked":       settings.QUOTA_PRO_QUESTIONS_PER_MONTH,
        "signatures_used":       5,
        "is_lifetime":           False,
    },
    SubscriptionPlan.BUSINESS: {
        "documents_analyzed":    99999,
        "documents_generated":   99999,
        "questions_asked":       99999,
        "signatures_used":       20,
        "is_lifetime":           False,
    },
}

# Mapping nom de quota → champ BDD
QUOTA_FIELD_MAP: dict[str, str] = {
    "documents_analyzed":  "documents_analyzed",
    "documents_generated": "documents_generated",
    "questions_asked":     "questions_asked",
    "signatures_used":     "signatures_used",
}


class QuotaService:
    """
    Service de vérification et de comptage des quotas.
    Doit être instancié avec une session DB.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    async def check_quota(
        self,
        org_id: str,
        plan: SubscriptionPlan,
        quota_type: str,
    ) -> tuple[bool, str]:
        """
        Vérifie si l'organisation peut effectuer une action supplémentaire.

        Returns:
            (True, "") si autorisé
            (False, "message d'erreur") si quota dépassé
        """
        plan_limits = PLAN_QUOTAS.get(plan, PLAN_QUOTAS[SubscriptionPlan.FREE])
        limit = plan_limits.get(quota_type, 0)

        # Illimité
        if limit >= 9999:
            return True, ""

        is_lifetime = plan_limits.get("is_lifetime", False)
        usage = await self._get_usage(org_id, is_lifetime=is_lifetime)
        field = QUOTA_FIELD_MAP.get(quota_type, quota_type)
        current_count = getattr(usage, field, 0) or 0

        if current_count >= limit:
            plan_name = plan.value.capitalize()
            period = "au total" if is_lifetime else "ce mois-ci"
            return False, (
                f"Quota atteint : {current_count}/{limit} "
                f"{quota_type.replace('_', ' ')} {period} "
                f"(plan {plan_name}). "
                f"Passez à un plan supérieur pour continuer."
            )

        return True, ""

    async def get_current_usage(
        self, org_id: str, plan: SubscriptionPlan
    ) -> dict[str, int]:
        """Retourne l'usage actuel de l'organisation sous forme de dict."""
        plan_limits = PLAN_QUOTAS.get(plan, PLAN_QUOTAS[SubscriptionPlan.FREE])
        is_lifetime = plan_limits.get("is_lifetime", False)
        usage = await self._get_usage(org_id, is_lifetime=is_lifetime)
        return {
            "documents_analyzed":  getattr(usage, "documents_analyzed",  0) or 0,
            "documents_generated": getattr(usage, "documents_generated", 0) or 0,
            "questions_asked":     getattr(usage, "questions_asked",     0) or 0,
            "signatures_used":     getattr(usage, "signatures_used",     0) or 0,
        }

    async def increment_usage(self, org_id: str, quota_type: str) -> None:
        """
        Incrémente le compteur d'usage pour l'organisation.
        Crée l'entrée du mois si elle n'existe pas encore.
        """
        now = datetime.now(timezone.utc)

        result = await self.db.execute(
            select(UsageQuota).where(
                UsageQuota.organization_id == org_id,
                UsageQuota.period_year     == now.year,
                UsageQuota.period_month    == now.month,
            )
        )
        quota = result.scalar_one_or_none()

        if not quota:
            quota = UsageQuota(
                id=generate_ulid(),
                organization_id=org_id,
                period_year=now.year,
                period_month=now.month,
            )
            self.db.add(quota)

        field = QUOTA_FIELD_MAP.get(quota_type, quota_type)
        current_val = getattr(quota, field, 0) or 0
        setattr(quota, field, current_val + 1)
        await self.db.flush()

        logger.debug(
            "quota_incremented",
            org_id=org_id,
            quota_type=quota_type,
            new_value=current_val + 1,
        )

    async def _get_usage(self, org_id: str, is_lifetime: bool) -> UsageQuota:
        """
        Récupère l'usage actuel.
        - Plan Free (is_lifetime=True)  : cumul total toutes périodes
        - Plans payants (is_lifetime=False) : mois courant uniquement
        """
        now = datetime.now(timezone.utc)

        if is_lifetime:
            # Agréger toutes les périodes
            result = await self.db.execute(
                select(
                    func.coalesce(func.sum(UsageQuota.documents_analyzed),  0).label("documents_analyzed"),
                    func.coalesce(func.sum(UsageQuota.documents_generated), 0).label("documents_generated"),
                    func.coalesce(func.sum(UsageQuota.questions_asked),     0).label("questions_asked"),
                    func.coalesce(func.sum(UsageQuota.signatures_used),     0).label("signatures_used"),
                ).where(UsageQuota.organization_id == org_id)
            )
            row = result.one()

            # Créer un objet temporaire non-persisté avec les totaux
            mock_quota = UsageQuota()
            mock_quota.documents_analyzed  = row.documents_analyzed
            mock_quota.documents_generated = row.documents_generated
            mock_quota.questions_asked     = row.questions_asked
            mock_quota.signatures_used     = row.signatures_used
            return mock_quota

        else:
            # Mois courant
            result = await self.db.execute(
                select(UsageQuota).where(
                    UsageQuota.organization_id == org_id,
                    UsageQuota.period_year     == now.year,
                    UsageQuota.period_month    == now.month,
                )
            )
            quota = result.scalar_one_or_none()
            if not quota:
                # Aucune utilisation ce mois → retourner un quota vide
                empty = UsageQuota()
                empty.documents_analyzed  = 0
                empty.documents_generated = 0
                empty.questions_asked     = 0
                empty.signatures_used     = 0
                return empty
            return quota
