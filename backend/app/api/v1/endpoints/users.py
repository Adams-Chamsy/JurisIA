"""JurisIA — Endpoints Utilisateurs & Organisations"""
from __future__ import annotations
from typing import Optional

from fastapi import APIRouter, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel, EmailStr
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import CurrentVerifiedUser, CurrentOrg, DB
from app.models import Organization

router = APIRouter(prefix="/users", tags=["Users & Organizations"])


class UpdateProfileRequest(BaseModel):
    full_name: Optional[str] = None
    avatar_url: Optional[str] = None


class UpdateOrgRequest(BaseModel):
    name: Optional[str] = None
    siren: Optional[str] = None
    sector_label: Optional[str] = None
    employee_count_range: Optional[str] = None
    convention_collective: Optional[str] = None


@router.patch("/me", summary="Mettre à jour le profil utilisateur")
async def update_profile(
    body: UpdateProfileRequest,
    current_user: CurrentVerifiedUser,
    db: DB,
):
    if body.full_name is not None:
        current_user.full_name = body.full_name.strip()
    if body.avatar_url is not None:
        current_user.avatar_url = body.avatar_url
    await db.flush()
    return {"id": current_user.id, "full_name": current_user.full_name, "email": current_user.email}


@router.patch("/organization", summary="Mettre à jour les informations de l'organisation")
async def update_organization(
    body: UpdateOrgRequest,
    current_user: CurrentVerifiedUser,
    org: CurrentOrg,
    db: DB,
):
    for field, value in body.model_dump(exclude_none=True).items():
        setattr(org, field, value)
    await db.flush()
    return {"id": org.id, "name": org.name, "siren": org.siren}


@router.delete("/me", status_code=204, response_class=Response, summary="Supprimer le compte (RGPD)")
async def delete_account(current_user: CurrentVerifiedUser, db: DB):
    """Soft delete conforme RGPD. Données physiquement supprimées après 30 jours."""
    from datetime import datetime, timezone
    current_user.deleted_at = datetime.now(timezone.utc)
    current_user.email = f"deleted_{current_user.id}@deleted.jurisai.fr"  # Anonymisation email
    current_user.full_name = "Compte supprimé"
    current_user.password_hash = None
    await db.flush()


@router.get("/organization/siren/{siren}", summary="Recherche entreprise par SIREN (via Pappers)")
async def lookup_siren(siren: str, current_user: CurrentVerifiedUser):
    """Auto-complétion du profil entreprise depuis le SIREN."""
    import httpx
    from app.core.config import settings

    if not settings.PAPPERS_API_KEY:
        raise HTTPException(status_code=503, detail={"code": "SERVICE_UNAVAILABLE", "message": "Service SIREN non configuré"})

    async with httpx.AsyncClient() as client:
        try:
            response = await client.get(
                f"https://api.pappers.fr/v2/entreprise",
                params={"siren": siren, "api_token": settings.PAPPERS_API_KEY},
                timeout=5.0,
            )
            if response.status_code == 200:
                data = response.json()
                return {
                    "siren": siren,
                    "name": data.get("denomination", ""),
                    "sector_code": data.get("code_naf", ""),
                    "sector_label": data.get("libelle_code_naf", ""),
                    "employee_count_range": data.get("tranche_effectif", ""),
                }
        except Exception:
            pass

    raise HTTPException(status_code=404, detail={"code": "SIREN_NOT_FOUND", "message": "SIREN introuvable"})
