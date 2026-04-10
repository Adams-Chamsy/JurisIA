"""
JurisIA — Service d'Authentification
Toute la logique métier d'auth : inscription, connexion, tokens, 2FA, reset password.
Ce service est la seule couche qui manipule les données d'auth.
"""
from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional

import pyotp
import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    decrypt_data,
    encrypt_data,
    generate_secure_token,
    generate_ulid,
    hash_password,
    hash_refresh_token,
    verify_password,
)
from app.models import OrganizationMember, RefreshToken, Subscription, User, Organization
from app.models import SubscriptionPlan, SubscriptionStatus, UserRole
from app.schemas.auth import (
    AuthResponse,
    OrganizationResponse,
    RegisterRequest,
    Setup2FAResponse,
    TokenResponse,
    UserResponse,
)

logger = structlog.get_logger(__name__)

# ─── Codes d'erreur standardisés ──────────────────────────────────────────────

class AuthError(Exception):
    """Exception de base pour les erreurs d'authentification."""

    def __init__(self, code: str, message: str, status_code: int = 400):
        self.code = code
        self.message = message
        self.status_code = status_code
        super().__init__(message)


AUTH_ERRORS = {
    "EMAIL_ALREADY_EXISTS": AuthError("EMAIL_ALREADY_EXISTS", "Cette adresse email est déjà utilisée", 409),
    "INVALID_CREDENTIALS": AuthError("INVALID_CREDENTIALS", "Email ou mot de passe incorrect", 401),
    "EMAIL_NOT_VERIFIED": AuthError("EMAIL_NOT_VERIFIED", "Veuillez vérifier votre email avant de vous connecter", 403),
    "ACCOUNT_DELETED": AuthError("ACCOUNT_DELETED", "Ce compte a été supprimé", 404),
    "INVALID_2FA_CODE": AuthError("INVALID_2FA_CODE", "Code 2FA invalide ou expiré", 401),
    "2FA_REQUIRED": AuthError("2FA_REQUIRED", "Code 2FA requis", 403),
    "INVALID_TOKEN": AuthError("INVALID_TOKEN", "Token invalide ou expiré", 401),
    "TOKEN_REVOKED": AuthError("TOKEN_REVOKED", "Ce token a été révoqué", 401),
    "USER_NOT_FOUND": AuthError("USER_NOT_FOUND", "Utilisateur introuvable", 404),
    "WEAK_PASSWORD": AuthError("WEAK_PASSWORD", "Le mot de passe ne respecte pas les critères de sécurité", 400),
}


# ─── AuthService ──────────────────────────────────────────────────────────────

class AuthService:
    """
    Service d'authentification de JurisIA.
    Toutes les méthodes sont async et prennent une session DB en paramètre.
    """

    def __init__(self, db: AsyncSession):
        self.db = db

    # ── Inscription ────────────────────────────────────────────────────────

    async def register(self, data: RegisterRequest) -> dict:
        """
        Inscrit un nouvel utilisateur et crée son organisation.
        Retourne un message de confirmation (email de vérification envoyé).
        """
        # 1. Vérifier si l'email existe déjà
        existing = await self._get_user_by_email(data.email)
        if existing:
            raise AUTH_ERRORS["EMAIL_ALREADY_EXISTS"]

        # 2. Créer l'utilisateur
        user_id = generate_ulid()
        verification_token = generate_secure_token(32)

        user = User(
            id=user_id,
            email=data.email.lower().strip(),
            password_hash=hash_password(data.password),
            full_name=data.full_name.strip(),
            email_verification_token=verification_token,
            email_verified=False,
        )
        self.db.add(user)

        # 3. Créer l'organisation
        org_id = generate_ulid()
        organization = Organization(
            id=org_id,
            name=data.organization_name.strip(),
            siren=data.siren,
        )
        self.db.add(organization)

        # 4. Lier l'utilisateur à l'organisation comme Owner
        member = OrganizationMember(
            user_id=user_id,
            organization_id=org_id,
            role=UserRole.OWNER,
            joined_at=datetime.now(timezone.utc),
        )
        self.db.add(member)

        # 5. Créer un abonnement Free
        import stripe as stripe_lib
        stripe_lib.api_key = settings.STRIPE_SECRET_KEY

        stripe_customer = stripe_lib.Customer.create(
            email=data.email,
            name=data.organization_name,
            metadata={"org_id": org_id, "user_id": user_id},
        )

        subscription = Subscription(
            id=generate_ulid(),
            organization_id=org_id,
            stripe_customer_id=stripe_customer.id,
            plan=SubscriptionPlan.FREE,
            status=SubscriptionStatus.ACTIVE,
        )
        self.db.add(subscription)

        await self.db.flush()  # Valider sans committer (le commit est dans le dependency)

        # 6. Envoyer l'email de vérification (async, non bloquant)
        await self._send_verification_email(user, verification_token)

        logger.info(
            "user_registered",
            user_id=user_id,
            org_id=org_id,
            email=data.email,
        )

        return {
            "message": f"Compte créé. Un email de vérification a été envoyé à {data.email}.",
            "user_id": user_id,
        }

    # ── Connexion ──────────────────────────────────────────────────────────

    async def login(
        self,
        email: str,
        password: str,
        totp_code: Optional[str] = None,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> AuthResponse:
        """
        Authentifie un utilisateur.
        Gère le 2FA si activé.
        Retourne les tokens JWT + les infos utilisateur.
        """
        # 1. Récupérer l'utilisateur
        user = await self._get_user_by_email(email.lower().strip())
        if not user:
            # Timing attack mitigation : toujours hasher même si user inexistant
            hash_password("dummy_to_prevent_timing_attack")
            raise AUTH_ERRORS["INVALID_CREDENTIALS"]

        # 2. Vérifier le soft delete
        if user.deleted_at is not None:
            raise AUTH_ERRORS["ACCOUNT_DELETED"]

        # 3. Vérifier le mot de passe
        if not user.password_hash or not verify_password(password, user.password_hash):
            logger.warning("failed_login_attempt", email=email, ip=ip_address)
            raise AUTH_ERRORS["INVALID_CREDENTIALS"]

        # 4. Vérifier l'email (en dev, on peut bypass)
        if not user.email_verified and settings.is_production:
            raise AUTH_ERRORS["EMAIL_NOT_VERIFIED"]

        # 5. Vérifier le 2FA
        if user.two_fa_enabled:
            if not totp_code:
                raise AUTH_ERRORS["2FA_REQUIRED"]
            if not self._verify_totp(user, totp_code):
                logger.warning("failed_2fa_attempt", user_id=user.id, ip=ip_address)
                raise AUTH_ERRORS["INVALID_2FA_CODE"]

        # 6. Récupérer l'organisation principale
        org = await self._get_user_primary_org(user.id)

        # 7. Générer les tokens
        tokens = await self._create_tokens(
            user=user,
            org=org,
            ip_address=ip_address,
            user_agent=user_agent,
        )

        # 8. Mettre à jour last_login
        user.last_login_at = datetime.now(timezone.utc)

        logger.info("user_logged_in", user_id=user.id, ip=ip_address)

        return AuthResponse(
            user=UserResponse.model_validate(user),
            organization=OrganizationResponse.model_validate(org) if org else None,
            tokens=tokens,
        )

    # ── Refresh Token ──────────────────────────────────────────────────────

    async def refresh_access_token(
        self,
        refresh_token_raw: str,
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> TokenResponse:
        """Renouvelle l'access token via un refresh token valide."""
        token_hash = hash_refresh_token(refresh_token_raw)

        # Récupérer le token en BDD
        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        stored_token = result.scalar_one_or_none()

        if not stored_token:
            raise AUTH_ERRORS["INVALID_TOKEN"]

        if stored_token.revoked_at is not None:
            # Token déjà révoqué → suspicion de vol → révoquer tous les tokens de l'utilisateur
            logger.warning(
                "refresh_token_reuse_detected",
                user_id=stored_token.user_id,
                token_hash=token_hash[:8] + "...",
            )
            await self._revoke_all_tokens(stored_token.user_id)
            raise AUTH_ERRORS["TOKEN_REVOKED"]

        if stored_token.expires_at < datetime.now(timezone.utc):
            raise AUTH_ERRORS["INVALID_TOKEN"]

        # Récupérer l'utilisateur
        user = await self.db.get(User, stored_token.user_id)
        if not user or user.deleted_at:
            raise AUTH_ERRORS["INVALID_TOKEN"]

        # Rotation du refresh token (one-time use)
        stored_token.revoked_at = datetime.now(timezone.utc)

        org = await self._get_user_primary_org(user.id)
        tokens = await self._create_tokens(user, org, ip_address, user_agent)

        logger.info("token_refreshed", user_id=user.id)
        return tokens

    # ── Déconnexion ────────────────────────────────────────────────────────

    async def logout(self, refresh_token_raw: str) -> None:
        """Révoque un refresh token (déconnexion)."""
        token_hash = hash_refresh_token(refresh_token_raw)
        result = await self.db.execute(
            select(RefreshToken).where(RefreshToken.token_hash == token_hash)
        )
        stored_token = result.scalar_one_or_none()
        if stored_token:
            stored_token.revoked_at = datetime.now(timezone.utc)

    # ── Vérification Email ─────────────────────────────────────────────────

    async def verify_email(self, token: str) -> None:
        """Vérifie l'email d'un utilisateur via son token."""
        result = await self.db.execute(
            select(User).where(User.email_verification_token == token)
        )
        user = result.scalar_one_or_none()

        if not user:
            raise AUTH_ERRORS["INVALID_TOKEN"]

        user.email_verified = True
        user.email_verification_token = None
        logger.info("email_verified", user_id=user.id)

    # ── Reset Password ─────────────────────────────────────────────────────

    async def request_password_reset(self, email: str) -> None:
        """
        Envoie un email de réinitialisation.
        Ne révèle jamais si l'email existe ou non (sécurité).
        """
        user = await self._get_user_by_email(email.lower())
        if user and not user.deleted_at:
            reset_token = generate_secure_token(32)
            user.password_reset_token = reset_token
            user.password_reset_expires_at = datetime.now(timezone.utc) + timedelta(hours=1)
            await self._send_password_reset_email(user, reset_token)
            logger.info("password_reset_requested", user_id=user.id)
        # Toujours retourner le même message (pas de timing leak)

    async def confirm_password_reset(self, token: str, new_password: str) -> None:
        """Confirme la réinitialisation avec le nouveau mot de passe."""
        result = await self.db.execute(
            select(User).where(
                User.password_reset_token == token,
                User.password_reset_expires_at > datetime.now(timezone.utc),
            )
        )
        user = result.scalar_one_or_none()

        if not user:
            raise AUTH_ERRORS["INVALID_TOKEN"]

        user.password_hash = hash_password(new_password)
        user.password_reset_token = None
        user.password_reset_expires_at = None

        # Révoquer tous les refresh tokens (sécurité après reset)
        await self._revoke_all_tokens(user.id)
        logger.info("password_reset_confirmed", user_id=user.id)

    # ── 2FA (TOTP) ─────────────────────────────────────────────────────────

    async def setup_2fa(self, user_id: str) -> Setup2FAResponse:
        """Configure le 2FA pour un utilisateur. Retourne l'URI TOTP et les codes backup."""
        user = await self.db.get(User, user_id)
        if not user:
            raise AUTH_ERRORS["USER_NOT_FOUND"]

        # Générer un secret TOTP
        totp_secret = pyotp.random_base32()
        totp_uri = pyotp.totp.TOTP(totp_secret).provisioning_uri(
            name=user.email,
            issuer_name="JurisIA",
        )

        # Générer 8 codes de récupération
        backup_codes = [secrets.token_hex(4).upper() for _ in range(8)]

        # Stocker le secret chiffré (activé après vérification du code)
        user.two_fa_secret_encrypted = encrypt_data(totp_secret)

        return Setup2FAResponse(totp_uri=totp_uri, backup_codes=backup_codes)

    async def enable_2fa(self, user_id: str, totp_code: str) -> None:
        """Active le 2FA après vérification du code TOTP."""
        user = await self.db.get(User, user_id)
        if not user:
            raise AUTH_ERRORS["USER_NOT_FOUND"]

        if not self._verify_totp(user, totp_code):
            raise AUTH_ERRORS["INVALID_2FA_CODE"]

        user.two_fa_enabled = True
        logger.info("2fa_enabled", user_id=user_id)

    # ── Méthodes Privées ───────────────────────────────────────────────────

    async def _get_user_by_email(self, email: str) -> Optional[User]:
        result = await self.db.execute(select(User).where(User.email == email))
        return result.scalar_one_or_none()

    async def _get_user_primary_org(self, user_id: str) -> Optional[Organization]:
        """Récupère la première organisation de l'utilisateur (celle créée à l'inscription)."""
        result = await self.db.execute(
            select(Organization)
            .join(OrganizationMember, OrganizationMember.organization_id == Organization.id)
            .where(OrganizationMember.user_id == user_id)
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def _create_tokens(
        self,
        user: User,
        org: Optional[Organization],
        ip_address: Optional[str] = None,
        user_agent: Optional[str] = None,
    ) -> TokenResponse:
        """Crée access + refresh token et stocke le refresh en BDD."""
        access_token = create_access_token(
            subject=user.id,
            extra_claims={
                "email": user.email,
                "org_id": org.id if org else None,
            },
        )
        refresh_token_raw, token_hash = create_refresh_token()

        rt = RefreshToken(
            id=generate_ulid(),
            user_id=user.id,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(days=settings.JWT_REFRESH_TOKEN_EXPIRE_DAYS),
            ip_address=ip_address,
            user_agent=user_agent,
        )
        self.db.add(rt)

        return TokenResponse(
            access_token=access_token,
            refresh_token=refresh_token_raw,
            expires_in=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES * 60,
        )

    async def _revoke_all_tokens(self, user_id: str) -> None:
        """Révoque tous les refresh tokens d'un utilisateur."""
        result = await self.db.execute(
            select(RefreshToken).where(
                RefreshToken.user_id == user_id,
                RefreshToken.revoked_at.is_(None),
            )
        )
        tokens = result.scalars().all()
        now = datetime.now(timezone.utc)
        for token in tokens:
            token.revoked_at = now

    def _verify_totp(self, user: User, code: str) -> bool:
        """Vérifie un code TOTP. Fenêtre de 1 période (30s avant/après)."""
        if not user.two_fa_secret_encrypted:
            return False
        try:
            secret = decrypt_data(user.two_fa_secret_encrypted)
            totp = pyotp.TOTP(secret)
            return totp.verify(code, valid_window=1)
        except Exception:
            return False

    async def _send_verification_email(self, user: User, token: str) -> None:
        """Envoie l'email de vérification (non bloquant)."""
        # Import ici pour éviter import circulaire
        from app.services.notifications.email_service import EmailService
        try:
            email_svc = EmailService()
            verify_url = f"{settings.FRONTEND_URL}/verify-email?token={token}"
            await email_svc.send_verification_email(
                to_email=user.email,
                to_name=user.full_name,
                verify_url=verify_url,
            )
        except Exception as e:
            # Ne jamais bloquer l'inscription si l'email échoue
            logger.error("verification_email_failed", user_id=user.id, error=str(e))

    async def _send_password_reset_email(self, user: User, token: str) -> None:
        """Envoie l'email de réinitialisation de mot de passe."""
        from app.services.notifications.email_service import EmailService
        try:
            email_svc = EmailService()
            reset_url = f"{settings.FRONTEND_URL}/reset-password?token={token}"
            await email_svc.send_password_reset_email(
                to_email=user.email,
                to_name=user.full_name,
                reset_url=reset_url,
            )
        except Exception as e:
            logger.error("reset_email_failed", user_id=user.id, error=str(e))
