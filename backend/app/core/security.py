"""
JurisIA — Utilitaires de Sécurité
Fonctions de hashage, JWT, chiffrement et génération d'identifiants.
Toutes les fonctions critiques de sécurité sont centralisées ici.
"""
from __future__ import annotations

import hashlib
import hmac
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any

import structlog
from cryptography.fernet import Fernet
from jose import JWTError, jwt
from passlib.context import CryptContext

from app.core.config import settings

logger = structlog.get_logger(__name__)

# ── Hashage des mots de passe (Argon2id) ──────────────────────────────────────

# Argon2id : résistant aux attaques GPU/ASIC
# Paramètres OWASP recommandés 2024 : 64 MB mémoire, 3 itérations
pwd_context = CryptContext(
    schemes=["argon2"],
    deprecated="auto",
    argon2__memory_cost=65536,    # 64 MB
    argon2__time_cost=3,          # 3 itérations
    argon2__parallelism=4,        # 4 threads
)


def hash_password(password: str) -> str:
    """Hash un mot de passe avec Argon2id. Retourne le hash à stocker en BDD."""
    return pwd_context.hash(password)


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Vérifie un mot de passe contre son hash. Constant-time comparison."""
    try:
        return pwd_context.verify(plain_password, hashed_password)
    except Exception:
        # Ne jamais exposer les détails d'une erreur de vérification
        return False


def validate_password_strength(password: str) -> tuple[bool, str]:
    """
    Valide la force d'un mot de passe.
    Retourne (is_valid, error_message).
    """
    if len(password) < 8:
        return False, "Le mot de passe doit contenir au moins 8 caractères"
    if not any(c.isupper() for c in password):
        return False, "Le mot de passe doit contenir au moins une majuscule"
    if not any(c.islower() for c in password):
        return False, "Le mot de passe doit contenir au moins une minuscule"
    if not any(c.isdigit() for c in password):
        return False, "Le mot de passe doit contenir au moins un chiffre"
    return True, ""


# ── JWT (JSON Web Tokens) ──────────────────────────────────────────────────────

def create_access_token(
    subject: str,
    extra_claims: dict[str, Any] | None = None,
    expires_delta: timedelta | None = None,
) -> str:
    """
    Crée un JWT d'accès signé.

    Args:
        subject: L'identifiant de l'utilisateur (user_id)
        extra_claims: Claims additionnels (org_id, role, etc.)
        expires_delta: Durée de validité personnalisée

    Returns:
        JWT signé encodé en base64url
    """
    if expires_delta is None:
        expires_delta = timedelta(minutes=settings.JWT_ACCESS_TOKEN_EXPIRE_MINUTES)

    now = datetime.now(timezone.utc)
    expire = now + expires_delta

    payload: dict[str, Any] = {
        "sub": subject,
        "iat": now,
        "exp": expire,
        "type": "access",
        "jti": generate_secure_token(16),  # JWT ID unique pour révocation future
    }

    if extra_claims:
        payload.update(extra_claims)

    return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)


def create_refresh_token() -> tuple[str, str]:
    """
    Crée un refresh token opaque (non-JWT).
    Retourne (token_raw, token_hash) — stocker uniquement le hash en BDD.
    """
    token_raw = secrets.token_urlsafe(64)
    token_hash = hashlib.sha256(token_raw.encode()).hexdigest()
    return token_raw, token_hash


def verify_access_token(token: str) -> dict[str, Any] | None:
    """
    Vérifie et décode un JWT d'accès.
    Retourne les claims ou None si invalide.
    """
    try:
        payload = jwt.decode(
            token,
            settings.JWT_SECRET_KEY,
            algorithms=[settings.JWT_ALGORITHM],
        )
        if payload.get("type") != "access":
            logger.warning("invalid_token_type", type=payload.get("type"))
            return None
        return payload
    except JWTError as e:
        logger.debug("jwt_verification_failed", error=str(e))
        return None


def hash_refresh_token(token_raw: str) -> str:
    """Hash un refresh token brut pour stockage en BDD."""
    return hashlib.sha256(token_raw.encode()).hexdigest()


# ── Chiffrement symétrique (Fernet / AES-128-CBC) ────────────────────────────

def _get_fernet() -> Fernet:
    """Initialise le chiffreur Fernet avec la clé de configuration."""
    try:
        return Fernet(settings.ENCRYPTION_KEY.encode())
    except Exception as e:
        raise ValueError(f"ENCRYPTION_KEY invalide : {e}") from e


def encrypt_data(plaintext: str) -> str:
    """Chiffre une chaîne de caractères. Retourne le ciphertext base64."""
    fernet = _get_fernet()
    return fernet.encrypt(plaintext.encode()).decode()


def decrypt_data(ciphertext: str) -> str:
    """Déchiffre une chaîne chiffrée. Lève une exception si invalide."""
    fernet = _get_fernet()
    return fernet.decrypt(ciphertext.encode()).decode()


# ── Génération de tokens sécurisés ────────────────────────────────────────────

def generate_secure_token(length: int = 32) -> str:
    """Génère un token cryptographiquement sécurisé (hex)."""
    return secrets.token_hex(length)


def generate_ulid() -> str:
    """
    Génère un identifiant unique de 26 caractères, lexicographiquement triable.
    Utilise UUID4 encodé en base32 pour éviter la dépendance à ulid-py (incompatible Python 3.12+).
    Compatible avec la colonne String(26) en base de données.
    """
    import uuid, base64
    raw = uuid.uuid4().bytes                          # 16 bytes
    encoded = base64.b32encode(raw).decode().rstrip("=")  # 26 chars
    return encoded


# ── Validation CSRF ───────────────────────────────────────────────────────────

def generate_csrf_token(session_id: str) -> str:
    """Génère un token CSRF lié à la session."""
    secret = settings.APP_SECRET_KEY.encode()
    msg = session_id.encode()
    return hmac.new(secret, msg, hashlib.sha256).hexdigest()


def verify_csrf_token(token: str, session_id: str) -> bool:
    """Vérifie un token CSRF via comparaison constant-time."""
    expected = generate_csrf_token(session_id)
    return hmac.compare_digest(token, expected)


# ── Sanitisation des entrées ──────────────────────────────────────────────────

def sanitize_string(value: str, max_length: int = 1000) -> str:
    """
    Sanitise une chaîne de caractères :
    - Supprime les caractères de contrôle dangereux
    - Tronque à la longueur maximale
    - Normalise les espaces
    """
    # Suppression des caractères de contrôle (sauf newline et tab)
    sanitized = "".join(
        ch for ch in value
        if ord(ch) >= 32 or ch in ("\n", "\t", "\r")
    )
    # Normalisation des espaces multiples
    sanitized = " ".join(sanitized.split())
    return sanitized[:max_length]
