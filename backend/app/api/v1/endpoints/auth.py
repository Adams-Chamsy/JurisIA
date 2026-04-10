"""
JurisIA — Endpoints d'Authentification
Routes : /auth/register, /auth/login, /auth/refresh, /auth/logout,
         /auth/verify-email, /auth/reset-password, /auth/2fa/*
"""
from __future__ import annotations

from typing import Annotated

import structlog
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request, status
from slowapi import Limiter
from slowapi.util import get_remote_address
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.dependencies.auth import CurrentVerifiedUser, DB, get_current_user
from app.core.config import settings
from app.db.database import get_db
from app.schemas.auth import (
    AuthResponse,
    ChangePasswordRequest,
    Enable2FARequest,
    LoginRequest,
    MessageResponse,
    PasswordResetConfirmRequest,
    PasswordResetRequest,
    RefreshTokenRequest,
    RegisterRequest,
    Setup2FAResponse,
    TokenResponse,
    UserResponse,
)
from app.services.auth.auth_service import AuthError, AuthService

logger = structlog.get_logger(__name__)
router = APIRouter(prefix="/auth", tags=["Authentication"])

# Rate limiter (instance créée dans main.py, réutilisée ici)
limiter = Limiter(key_func=get_remote_address)


# ─── POST /auth/register ──────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=MessageResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Inscription d'un nouvel utilisateur",
    description="Crée un compte utilisateur, une organisation et un abonnement Free. Envoie un email de vérification.",
)
async def register(
    request: Request,
    body: RegisterRequest,
    db: DB,
) -> MessageResponse:
    # Rate limit : 5 inscriptions par IP par heure
    # (appliqué via middleware global)
    try:
        svc = AuthService(db)
        result = await svc.register(body)
        return MessageResponse(message=result["message"])
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail={"code": e.code, "message": e.message})


# ─── POST /auth/login ─────────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=AuthResponse,
    summary="Connexion utilisateur",
    description="Authentifie l'utilisateur. Retourne les tokens JWT. Gère le 2FA si activé.",
)
async def login(
    request: Request,
    body: LoginRequest,
    db: DB,
) -> AuthResponse:
    try:
        svc = AuthService(db)
        ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")

        response = await svc.login(
            email=body.email,
            password=body.password,
            totp_code=body.totp_code,
            ip_address=ip,
            user_agent=user_agent,
        )
        return response
    except AuthError as e:
        # Délai artificiel pour ralentir les attaques brute force
        import asyncio
        await asyncio.sleep(0.5)
        raise HTTPException(status_code=e.status_code, detail={"code": e.code, "message": e.message})


# ─── POST /auth/refresh ───────────────────────────────────────────────────────

@router.post(
    "/refresh",
    response_model=TokenResponse,
    summary="Renouvellement du token d'accès",
    description="Génère un nouvel access token à partir d'un refresh token valide. Rotation automatique.",
)
async def refresh_token(
    request: Request,
    body: RefreshTokenRequest,
    db: DB,
) -> TokenResponse:
    try:
        svc = AuthService(db)
        ip = request.client.host if request.client else None
        user_agent = request.headers.get("user-agent")
        return await svc.refresh_access_token(
            refresh_token_raw=body.refresh_token,
            ip_address=ip,
            user_agent=user_agent,
        )
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail={"code": e.code, "message": e.message})


# ─── POST /auth/logout ────────────────────────────────────────────────────────

@router.post(
    "/logout",
    response_model=MessageResponse,
    summary="Déconnexion",
    description="Révoque le refresh token. L'access token expire naturellement.",
)
async def logout(
    body: RefreshTokenRequest,
    db: DB,
    current_user: CurrentVerifiedUser,
) -> MessageResponse:
    svc = AuthService(db)
    await svc.logout(body.refresh_token)
    return MessageResponse(message="Déconnexion réussie")


# ─── GET /auth/verify-email ───────────────────────────────────────────────────

@router.get(
    "/verify-email",
    response_model=MessageResponse,
    summary="Vérification de l'adresse email",
)
async def verify_email(
    token: str,
    db: DB,
) -> MessageResponse:
    try:
        svc = AuthService(db)
        await svc.verify_email(token)
        return MessageResponse(message="Email vérifié avec succès. Vous pouvez maintenant vous connecter.")
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail={"code": e.code, "message": e.message})


# ─── POST /auth/forgot-password ───────────────────────────────────────────────

@router.post(
    "/forgot-password",
    response_model=MessageResponse,
    summary="Demande de réinitialisation de mot de passe",
)
async def forgot_password(
    body: PasswordResetRequest,
    db: DB,
) -> MessageResponse:
    svc = AuthService(db)
    await svc.request_password_reset(body.email)
    # Toujours le même message (pas d'info sur l'existence de l'email)
    return MessageResponse(
        message="Si cette adresse email existe, vous recevrez un lien de réinitialisation dans quelques minutes."
    )


# ─── POST /auth/reset-password ────────────────────────────────────────────────

@router.post(
    "/reset-password",
    response_model=MessageResponse,
    summary="Confirmation de la réinitialisation du mot de passe",
)
async def reset_password(
    body: PasswordResetConfirmRequest,
    db: DB,
) -> MessageResponse:
    try:
        svc = AuthService(db)
        await svc.confirm_password_reset(body.token, body.new_password)
        return MessageResponse(message="Mot de passe réinitialisé avec succès. Vous pouvez maintenant vous connecter.")
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail={"code": e.code, "message": e.message})


# ─── POST /auth/change-password ───────────────────────────────────────────────

@router.post(
    "/change-password",
    response_model=MessageResponse,
    summary="Changement de mot de passe (utilisateur connecté)",
)
async def change_password(
    body: ChangePasswordRequest,
    db: DB,
    current_user: CurrentVerifiedUser,
) -> MessageResponse:
    from app.core.security import hash_password, verify_password, validate_password_strength

    if not current_user.password_hash or not verify_password(body.current_password, current_user.password_hash):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"code": "INVALID_CREDENTIALS", "message": "Mot de passe actuel incorrect"},
        )

    is_valid, error = validate_password_strength(body.new_password)
    if not is_valid:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail={"code": "WEAK_PASSWORD", "message": error},
        )

    current_user.password_hash = hash_password(body.new_password)
    await db.flush()
    return MessageResponse(message="Mot de passe modifié avec succès")


# ─── GET /auth/me ─────────────────────────────────────────────────────────────

@router.get(
    "/me",
    response_model=UserResponse,
    summary="Profil de l'utilisateur courant",
)
async def get_me(current_user: CurrentVerifiedUser) -> UserResponse:
    return UserResponse.model_validate(current_user)


# ─── 2FA Endpoints ────────────────────────────────────────────────────────────

@router.post(
    "/2fa/setup",
    response_model=Setup2FAResponse,
    summary="Configuration du 2FA (génère le QR code)",
)
async def setup_2fa(
    db: DB,
    current_user: CurrentVerifiedUser,
) -> Setup2FAResponse:
    try:
        svc = AuthService(db)
        return await svc.setup_2fa(current_user.id)
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail={"code": e.code, "message": e.message})


@router.post(
    "/2fa/enable",
    response_model=MessageResponse,
    summary="Activation du 2FA (après scan du QR code)",
)
async def enable_2fa(
    body: Enable2FARequest,
    db: DB,
    current_user: CurrentVerifiedUser,
) -> MessageResponse:
    try:
        svc = AuthService(db)
        await svc.enable_2fa(current_user.id, body.totp_code)
        return MessageResponse(message="Double authentification activée avec succès")
    except AuthError as e:
        raise HTTPException(status_code=e.status_code, detail={"code": e.code, "message": e.message})


@router.post(
    "/2fa/disable",
    response_model=MessageResponse,
    summary="Désactivation du 2FA",
)
async def disable_2fa(
    body: Enable2FARequest,
    db: DB,
    current_user: CurrentVerifiedUser,
) -> MessageResponse:
    from app.core.security import decrypt_data
    import pyotp

    if not current_user.two_fa_secret_encrypted:
        raise HTTPException(status_code=400, detail={"code": "2FA_NOT_ENABLED", "message": "Le 2FA n'est pas activé"})

    secret = decrypt_data(current_user.two_fa_secret_encrypted)
    totp = pyotp.TOTP(secret)
    if not totp.verify(body.totp_code, valid_window=1):
        raise HTTPException(status_code=401, detail={"code": "INVALID_2FA_CODE", "message": "Code 2FA invalide"})

    current_user.two_fa_enabled = False
    current_user.two_fa_secret_encrypted = None
    await db.flush()
    return MessageResponse(message="Double authentification désactivée")
