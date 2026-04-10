"""JurisIA — Endpoints Compliance (RGPD / AI Act)"""
from __future__ import annotations
from typing import Optional
from datetime import datetime, timezone

import structlog
from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import desc, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import CurrentVerifiedUser, CurrentOrg, CurrentSubscription, DB
from app.core.security import generate_ulid
from app.models import ComplianceAudit, AuditType, SubscriptionPlan

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/compliance", tags=["Conformité"])


class StartAuditRequest(BaseModel):
    audit_type: str  # "rgpd" | "ai_act"
    answers: dict


class AuditResponse(BaseModel):
    id: str
    audit_type: str
    score: Optional[int]
    action_plan: Optional[list]
    completed_at: Optional[str]
    created_at: str

    model_config = {"from_attributes": True}


@router.post("/audit", response_model=AuditResponse, summary="Lancer un audit RGPD ou AI Act")
async def start_audit(
    body: StartAuditRequest,
    current_user: CurrentVerifiedUser,
    org: CurrentOrg,
    subscription: CurrentSubscription,
    db: DB,
) -> AuditResponse:
    # AI Act requis plan Pro+
    if body.audit_type == "ai_act" and subscription.plan not in [SubscriptionPlan.PRO, SubscriptionPlan.BUSINESS]:
        raise HTTPException(
            status_code=403,
            detail={"code": "PLAN_REQUIRED", "message": "L'audit AI Act nécessite un plan Pro ou Business"},
        )

    # Calculer le score
    score, action_plan = _compute_audit_result(body.audit_type, body.answers)

    audit = ComplianceAudit(
        id=generate_ulid(),
        organization_id=org.id,
        audit_type=AuditType(body.audit_type),
        score=score,
        answers=body.answers,
        action_plan=action_plan,
        completed_at=datetime.now(timezone.utc),
    )
    db.add(audit)
    await db.flush()

    logger.info("audit_completed", org_id=org.id, type=body.audit_type, score=score)

    return AuditResponse(
        id=audit.id,
        audit_type=audit.audit_type.value,
        score=audit.score,
        action_plan=audit.action_plan,
        completed_at=audit.completed_at.isoformat() if audit.completed_at else None,
        created_at=audit.created_at.isoformat(),
    )


@router.get("/audits", response_model=list[AuditResponse], summary="Historique des audits")
async def list_audits(current_user: CurrentVerifiedUser, org: CurrentOrg, db: DB):
    result = await db.execute(
        select(ComplianceAudit)
        .where(ComplianceAudit.organization_id == org.id)
        .order_by(desc(ComplianceAudit.created_at))
        .limit(20)
    )
    audits = result.scalars().all()
    return [
        AuditResponse(
            id=a.id,
            audit_type=a.audit_type.value,
            score=a.score,
            action_plan=a.action_plan,
            completed_at=a.completed_at.isoformat() if a.completed_at else None,
            created_at=a.created_at.isoformat(),
        )
        for a in audits
    ]


def _compute_audit_result(audit_type: str, answers: dict) -> tuple[int, list]:
    """Calcule le score d'audit et génère le plan d'action. Logique métier simplifiée."""
    if audit_type == "rgpd":
        return _compute_rgpd_score(answers)
    elif audit_type == "ai_act":
        return _compute_ai_act_score(answers)
    return 50, []


def _compute_rgpd_score(answers: dict) -> tuple[int, list]:
    checks = {
        "has_privacy_policy": ("Politique de confidentialité publiée", "high"),
        "has_cookie_consent": ("Bandeau cookies conforme", "high"),
        "has_data_register": ("Registre des traitements (Art. 30 RGPD)", "high"),
        "has_dpo_contact": ("Contact DPD/DPO identifié", "medium"),
        "data_minimization": ("Minimisation des données collectées", "medium"),
        "has_user_rights_process": ("Procédure pour les droits des personnes", "high"),
        "uses_eu_hosting": ("Hébergement des données en UE", "high"),
        "has_vendor_contracts": ("Contrats avec sous-traitants IA/tech", "medium"),
    }

    score = 0
    total_weight = 0
    action_plan = []

    for key, (label, priority) in checks.items():
        weight = 15 if priority == "high" else 10
        total_weight += weight
        if answers.get(key) is True:
            score += weight
        else:
            action_plan.append({
                "action": label,
                "priority": priority,
                "description": f"Mettre en place : {label}",
                "deadline": "Urgent (30 jours)" if priority == "high" else "Planifier (90 jours)",
            })

    final_score = round((score / total_weight) * 100) if total_weight > 0 else 0
    return final_score, action_plan


def _compute_ai_act_score(answers: dict) -> tuple[int, list]:
    checks = {
        "has_ai_inventory": ("Inventaire des outils IA utilisés", "high"),
        "knows_risk_classification": ("Classification des risques AI Act connue", "high"),
        "has_human_oversight": ("Supervision humaine des décisions IA", "high"),
        "has_ai_documentation": ("Documentation technique des systèmes IA", "medium"),
        "uses_bias_testing": ("Tests de biais et discrimination réalisés", "medium"),
        "has_transparency_notices": ("Notices de transparence pour les utilisateurs", "medium"),
    }

    score = 0
    total_weight = 0
    action_plan = []

    for key, (label, priority) in checks.items():
        weight = 20 if priority == "high" else 13
        total_weight += weight
        if answers.get(key) is True:
            score += weight
        else:
            action_plan.append({
                "action": label,
                "priority": priority,
                "description": f"Requis par l'AI Act (application août 2026) : {label}",
                "deadline": "Avant août 2026" if priority == "high" else "2026",
            })

    final_score = round((score / total_weight) * 100) if total_weight > 0 else 0
    return final_score, action_plan
