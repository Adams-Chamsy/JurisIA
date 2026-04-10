"""
JurisIA — Dependencies FastAPI
Fonctions d'injection de dépendances réutilisées dans tous les endpoints.
Pattern : "Depends()" pour auth, rôles, quotas.
"""
from __future__ import annotations

from typing import Annotated, Optional

import structlog
from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import verify_access_token
from app.db.database import get_db
from app.models import (
    Organization,
    OrganizationMember,
    Subscription,
    User,
    SubscriptionPlan,
    SubscriptionStatus,
    UserRole,
)

logger = structlog.get_logger(__name__)

# ─── Schéma Bearer token ──────────────────────────────────────────────────────

bearer_scheme = HTTPBearer(auto_error=False)


# ─── Dependency : Current User ────────────────────────────────────────────────

async def get_current_user(
    credentials: Annotated[Optional[HTTPAuthorizationCredentials], Depends(bearer_scheme)],
    db: AsyncSession = Depends(get_db),
) -> User:
    """
    Vérifie le JWT Bearer token et retourne l'utilisateur authentifié.
    Lève une 401 si le token est absent, invalide, ou si l'utilisateur est supprimé.
    """
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail={
            "code": "UNAUTHORIZED",
            "message": "Token d'authentification requis ou invalide",
            "action": "Veuillez vous reconnecter",
        },
        headers={"WWW-Authenticate": "Bearer"},
    )

    if not credentials:
        raise credentials_exception

    payload = verify_access_token(credentials.credentials)
    if not payload:
        raise credentials_exception

    user_id: str = payload.get("sub")
    if not user_id:
        raise credentials_exception

    user = await db.get(User, user_id)
    if not user or user.deleted_at is not None:
        raise credentials_exception

    return user


async def get_current_verified_user(
    current_user: User = Depends(get_current_user),
) -> User:
    """
    Vérifie que l'utilisateur a confirmé son email.
    En développement, bypass pour faciliter les tests.
    """
    if not current_user.email_verified and settings.is_production:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail={
                "code": "EMAIL_NOT_VERIFIED",
                "message": "Veuillez vérifier votre adresse email",
                "action": "Consultez votre boîte mail et cliquez sur le lien de vérification",
            },
        )
    return current_user


# ─── Dependency : Current Organization ───────────────────────────────────────

async def get_current_organization(
    current_user: User = Depends(get_current_verified_user),
    db: AsyncSession = Depends(get_db),
) -> Organization:
    """
    Retourne l'organisation active de l'utilisateur courant.
    Pour le MVP, chaque utilisateur n'a qu'une organisation.
    """
    result = await db.execute(
        select(Organization)
        .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
        .where(OrganizationMember.user_id == current_user.id)
        .limit(1)
    )
    org = result.scalar_one_or_none()

    if not org:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail={
                "code": "ORG_NOT_FOUND",
                "message": "Organisation introuvable",
                "action": "Contactez le support : support@jurisai.fr",
            },
        )
    return org


# ─── Dependency : Current Subscription ───────────────────────────────────────

async def get_current_subscription(
    org: Organization = Depends(get_current_organization),
    db: AsyncSession = Depends(get_db),
) -> Subscription:
    """Retourne l'abonnement actif de l'organisation."""
    result = await db.execute(
        select(Subscription)
        .where(
            Subscription.organization_id == org.id,
            Subscription.status.in_([
                SubscriptionStatus.ACTIVE,
                SubscriptionStatus.TRIALING,
            ]),
        )
        .limit(1)
    )
    subscription = result.scalar_one_or_none()

    if not subscription:
        # Créer un abonnement Free si inexistant (ne devrait pas arriver)
        logger.warning("subscription_not_found", org_id=org.id)
        raise HTTPException(
            status_code=status.HTTP_402_PAYMENT_REQUIRED,
            detail={
                "code": "NO_ACTIVE_SUBSCRIPTION",
                "message": "Aucun abonnement actif",
                "action": "Veuillez choisir un plan sur /billing",
            },
        )
    return subscription


# ─── Guards de Plan ───────────────────────────────────────────────────────────

def require_plan(*plans: SubscriptionPlan):
    """
    Factory de dependency pour vérifier le plan d'abonnement.

    Usage:
        @router.get("/feature", dependencies=[Depends(require_plan(SubscriptionPlan.PRO))])
    """
    async def check_plan(subscription: Subscription = Depends(get_current_subscription)):
        if subscription.plan not in plans and subscription.plan != SubscriptionPlan.BUSINESS:
            plan_names = " ou ".join(p.value.capitalize() for p in plans)
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "PLAN_REQUIRED",
                    "message": f"Cette fonctionnalité nécessite un abonnement {plan_names}",
                    "action": "Passez à un plan supérieur sur /billing/upgrade",
                    "required_plans": [p.value for p in plans],
                    "current_plan": subscription.plan.value,
                },
            )
        return subscription

    return check_plan


# ─── Guard de Rôle ────────────────────────────────────────────────────────────

def require_role(*roles: UserRole):
    """
    Factory de dependency pour vérifier le rôle dans l'organisation.

    Usage:
        @router.delete("/resource", dependencies=[Depends(require_role(UserRole.OWNER, UserRole.ADMIN))])
    """
    async def check_role(
        current_user: User = Depends(get_current_verified_user),
        org: Organization = Depends(get_current_organization),
        db: AsyncSession = Depends(get_db),
    ):
        result = await db.execute(
            select(OrganizationMember).where(
                OrganizationMember.user_id == current_user.id,
                OrganizationMember.organization_id == org.id,
            )
        )
        member = result.scalar_one_or_none()

        if not member or member.role not in roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail={
                    "code": "INSUFFICIENT_ROLE",
                    "message": "Vous n'avez pas les permissions nécessaires",
                    "action": "Contactez l'administrateur de votre organisation",
                    "required_roles": [r.value for r in roles],
                    "current_role": member.role.value if member else "none",
                },
            )
        return member

    return check_role


# ─── Type Aliases (pour la syntaxe Annotated) ─────────────────────────────────

CurrentUser = Annotated[User, Depends(get_current_user)]
CurrentVerifiedUser = Annotated[User, Depends(get_current_verified_user)]
CurrentOrg = Annotated[Organization, Depends(get_current_organization)]
CurrentSubscription = Annotated[Subscription, Depends(get_current_subscription)]
DB = Annotated[AsyncSession, Depends(get_db)]
