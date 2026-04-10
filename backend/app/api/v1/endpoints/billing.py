"""
JurisIA — Endpoints Billing (Stripe)
Gestion des abonnements, checkout, webhooks Stripe.
"""
from __future__ import annotations

import structlog
import stripe
from fastapi import APIRouter, Header, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import CurrentVerifiedUser, CurrentOrg, CurrentSubscription, DB
from app.core.config import settings
from app.core.security import generate_ulid
from app.models import Subscription, SubscriptionPlan, SubscriptionStatus
from datetime import datetime, timezone

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/billing", tags=["Billing"])
stripe.api_key = settings.STRIPE_SECRET_KEY

PLAN_PRICE_MAP = {
    "starter": settings.STRIPE_PRICE_ID_STARTER,
    "pro": settings.STRIPE_PRICE_ID_PRO,
    "business": settings.STRIPE_PRICE_ID_BUSINESS,
}


class CreateCheckoutRequest(BaseModel):
    plan: str  # starter | pro | business
    success_url: str = f"{settings.FRONTEND_URL}/billing/success"
    cancel_url: str = f"{settings.FRONTEND_URL}/billing"


class CheckoutResponse(BaseModel):
    checkout_url: str


@router.post("/checkout", response_model=CheckoutResponse, summary="Créer une session de paiement Stripe")
async def create_checkout(
    body: CreateCheckoutRequest,
    current_user: CurrentVerifiedUser,
    org: CurrentOrg,
    subscription: CurrentSubscription,
    db: DB,
) -> CheckoutResponse:
    if body.plan not in PLAN_PRICE_MAP:
        raise HTTPException(
            status_code=400,
            detail={"code": "INVALID_PLAN", "message": f"Plan invalide. Options : {list(PLAN_PRICE_MAP.keys())}"},
        )

    price_id = PLAN_PRICE_MAP[body.plan]
    if not price_id:
        raise HTTPException(
            status_code=503,
            detail={"code": "PLAN_NOT_CONFIGURED", "message": "Ce plan n'est pas encore disponible"},
        )

    try:
        session = stripe.checkout.Session.create(
            customer=subscription.stripe_customer_id,
            payment_method_types=["card"],
            line_items=[{"price": price_id, "quantity": 1}],
            mode="subscription",
            success_url=body.success_url + "?session_id={CHECKOUT_SESSION_ID}",
            cancel_url=body.cancel_url,
            metadata={"org_id": org.id, "user_id": current_user.id, "plan": body.plan},
            locale="fr",
            allow_promotion_codes=True,
        )
        logger.info("checkout_session_created", org_id=org.id, plan=body.plan)
        return CheckoutResponse(checkout_url=session.url)
    except stripe.StripeError as e:
        logger.error("stripe_checkout_failed", error=str(e))
        raise HTTPException(status_code=500, detail={"code": "STRIPE_ERROR", "message": "Erreur de paiement"})


@router.get("/portal", summary="Portail client Stripe (gérer l'abonnement)")
async def get_billing_portal(
    current_user: CurrentVerifiedUser,
    org: CurrentOrg,
    subscription: CurrentSubscription,
):
    try:
        session = stripe.billing_portal.Session.create(
            customer=subscription.stripe_customer_id,
            return_url=f"{settings.FRONTEND_URL}/settings/billing",
        )
        return {"portal_url": session.url}
    except stripe.StripeError as e:
        raise HTTPException(status_code=500, detail={"code": "STRIPE_ERROR", "message": str(e)})


@router.get("/subscription", summary="Statut de l'abonnement actuel")
async def get_subscription_status(
    current_user: CurrentVerifiedUser,
    org: CurrentOrg,
    subscription: CurrentSubscription,
    db: DB,
):
    # Récupérer l'usage du mois
    from app.services.documents.quota_service import QuotaService, PLAN_QUOTAS
    quota_svc = QuotaService(db)
    usage = await quota_svc._get_usage(org.id, PLAN_QUOTAS[subscription.plan].get("is_lifetime", False))
    limits = PLAN_QUOTAS.get(subscription.plan, {})

    return {
        "plan": subscription.plan.value,
        "status": subscription.status.value,
        "current_period_end": subscription.current_period_end.isoformat() if subscription.current_period_end else None,
        "cancel_at_period_end": subscription.cancel_at_period_end,
        "usage": {
            "documents_analyzed": usage.documents_analyzed,
            "documents_generated": usage.documents_generated,
            "questions_asked": usage.questions_asked,
        },
        "limits": {
            "documents_analyzed": limits.get("documents_analyzed", 0),
            "documents_generated": limits.get("documents_generated", 0),
            "questions_asked": limits.get("questions_asked", 0),
        },
    }


@router.post("/webhooks/stripe", include_in_schema=False)
async def stripe_webhook(
    request: Request,
    db: DB,
    stripe_signature: str = Header(None, alias="stripe-signature"),
):
    """Webhook Stripe pour synchroniser les changements d'abonnement."""
    payload = await request.body()

    try:
        event = stripe.Webhook.construct_event(
            payload, stripe_signature, settings.STRIPE_WEBHOOK_SECRET
        )
    except (stripe.SignatureVerificationError, ValueError) as e:
        logger.warning("stripe_webhook_invalid_signature", error=str(e))
        raise HTTPException(status_code=400, detail="Signature invalide")

    event_type = event["type"]
    data = event["data"]["object"]

    if event_type == "checkout.session.completed":
        await _handle_checkout_completed(db, data)
    elif event_type == "customer.subscription.updated":
        await _handle_subscription_updated(db, data)
    elif event_type == "customer.subscription.deleted":
        await _handle_subscription_deleted(db, data)
    elif event_type == "invoice.payment_failed":
        await _handle_payment_failed(db, data)

    logger.info("stripe_webhook_processed", event_type=event_type)
    return {"received": True}


async def _handle_checkout_completed(db: AsyncSession, data: dict) -> None:
    customer_id = data.get("customer")
    subscription_id = data.get("subscription")
    plan = data.get("metadata", {}).get("plan", "starter")

    result = await db.execute(
        select(Subscription).where(Subscription.stripe_customer_id == customer_id)
    )
    sub = result.scalar_one_or_none()
    if sub:
        sub.stripe_subscription_id = subscription_id
        sub.plan = SubscriptionPlan(plan)
        sub.status = SubscriptionStatus.ACTIVE
        await db.commit()
        logger.info("subscription_activated", customer_id=customer_id, plan=plan)


async def _handle_subscription_updated(db: AsyncSession, data: dict) -> None:
    sub_id = data.get("id")
    result = await db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == sub_id)
    )
    sub = result.scalar_one_or_none()
    if sub:
        sub.status = SubscriptionStatus(data.get("status", "active"))
        sub.cancel_at_period_end = data.get("cancel_at_period_end", False)
        period_end = data.get("current_period_end")
        if period_end:
            sub.current_period_end = datetime.fromtimestamp(period_end, tz=timezone.utc)
        await db.commit()


async def _handle_subscription_deleted(db: AsyncSession, data: dict) -> None:
    sub_id = data.get("id")
    result = await db.execute(
        select(Subscription).where(Subscription.stripe_subscription_id == sub_id)
    )
    sub = result.scalar_one_or_none()
    if sub:
        sub.status = SubscriptionStatus.CANCELED
        sub.plan = SubscriptionPlan.FREE
        await db.commit()
        logger.info("subscription_canceled", subscription_id=sub_id)


async def _handle_payment_failed(db: AsyncSession, data: dict) -> None:
    customer_id = data.get("customer")
    result = await db.execute(
        select(Subscription).where(Subscription.stripe_customer_id == customer_id)
    )
    sub = result.scalar_one_or_none()
    if sub:
        sub.status = SubscriptionStatus.PAST_DUE
        await db.commit()
        logger.warning("payment_failed", customer_id=customer_id)
