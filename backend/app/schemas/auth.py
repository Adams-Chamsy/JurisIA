"""
JurisIA — Schémas Pydantic : Authentification
Validation des entrées/sorties pour tous les endpoints d'authentification.
"""
from __future__ import annotations

from typing import Optional
from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator


# ── Schémas de Requête ────────────────────────────────────────────────────────

class RegisterRequest(BaseModel):
    """Corps de requête pour l'inscription."""

    full_name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Nom complet de l'utilisateur",
        examples=["Marie Dupont"],
    )
    email: EmailStr = Field(
        ...,
        description="Adresse email (identifiant unique)",
        examples=["marie@entreprise.fr"],
    )
    password: str = Field(
        ...,
        min_length=8,
        max_length=128,
        description="Mot de passe (min 8 caractères, majuscule, minuscule, chiffre)",
    )
    organization_name: str = Field(
        ...,
        min_length=2,
        max_length=255,
        description="Nom de l'entreprise",
        examples=["Dupont & Associés SAS"],
    )
    siren: Optional[str] = Field(
        None,
        pattern=r"^\d{9}$",
        description="Numéro SIREN à 9 chiffres (optionnel)",
        examples=["123456789"],
    )
    accept_terms: bool = Field(
        ...,
        description="Acceptation des CGU/CGV (obligatoire)",
    )

    @field_validator("full_name", "organization_name")
    @classmethod
    def no_html(cls, v: str) -> str:
        """Prévention basique XSS : refus des balises HTML."""
        if "<" in v or ">" in v:
            raise ValueError("Les balises HTML ne sont pas autorisées")
        return v.strip()

    @field_validator("accept_terms")
    @classmethod
    def must_accept_terms(cls, v: bool) -> bool:
        if not v:
            raise ValueError("Vous devez accepter les conditions d'utilisation")
        return v


class LoginRequest(BaseModel):
    """Corps de requête pour la connexion."""

    email: EmailStr
    password: str = Field(..., min_length=1, max_length=128)
    totp_code: Optional[str] = Field(
        None,
        pattern=r"^\d{6}$",
        description="Code TOTP 6 chiffres (si 2FA activé)",
    )


class RefreshTokenRequest(BaseModel):
    """Corps de requête pour le renouvellement du token."""

    refresh_token: str = Field(..., min_length=10)


class PasswordResetRequest(BaseModel):
    """Demande de réinitialisation de mot de passe."""

    email: EmailStr


class PasswordResetConfirmRequest(BaseModel):
    """Confirmation de réinitialisation avec nouveau mot de passe."""

    token: str = Field(..., min_length=32)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_password(cls, v: str) -> str:
        from app.core.security import validate_password_strength
        is_valid, error = validate_password_strength(v)
        if not is_valid:
            raise ValueError(error)
        return v


class ChangePasswordRequest(BaseModel):
    """Changement de mot de passe pour un utilisateur connecté."""

    current_password: str = Field(..., min_length=1, max_length=128)
    new_password: str = Field(..., min_length=8, max_length=128)

    @field_validator("new_password")
    @classmethod
    def validate_new_password(cls, v: str) -> str:
        from app.core.security import validate_password_strength
        is_valid, error = validate_password_strength(v)
        if not is_valid:
            raise ValueError(error)
        return v


class Enable2FARequest(BaseModel):
    """Activation du 2FA avec vérification du code TOTP."""

    totp_code: str = Field(..., pattern=r"^\d{6}$")


# ── Schémas de Réponse ────────────────────────────────────────────────────────

class TokenResponse(BaseModel):
    """Réponse contenant les tokens JWT."""

    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int  # Secondes avant expiration de l'access token


class UserResponse(BaseModel):
    """Représentation publique d'un utilisateur (sans données sensibles)."""

    id: str
    email: str
    full_name: str
    avatar_url: Optional[str] = None
    email_verified: bool
    two_fa_enabled: bool

    model_config = {"from_attributes": True}


class OrganizationResponse(BaseModel):
    """Représentation publique d'une organisation."""

    id: str
    name: str
    siren: Optional[str] = None
    sector_label: Optional[str] = None
    employee_count_range: Optional[str] = None

    model_config = {"from_attributes": True}


class AuthResponse(BaseModel):
    """Réponse complète après connexion réussie."""

    user: UserResponse
    organization: Optional[OrganizationResponse] = None
    tokens: TokenResponse
    requires_2fa: bool = False  # True si 2FA requis mais pas encore soumis


class Setup2FAResponse(BaseModel):
    """Réponse pour la configuration du 2FA."""

    totp_uri: str      # URI pour QR Code (otpauth://...)
    backup_codes: list[str]  # 8 codes de récupération


class MessageResponse(BaseModel):
    """Réponse générique avec un message."""

    message: str
    success: bool = True
