"""
JurisIA — Configuration Centrale de l'Application
Gestion typée de toutes les variables d'environnement via Pydantic Settings.
Pattern : singleton via lru_cache pour éviter les rechargements multiples.
"""
from functools import lru_cache
from typing import List, Literal
from pydantic import AnyHttpUrl, EmailStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """
    Configuration principale de JurisIA.
    Toutes les valeurs sont chargées depuis les variables d'environnement.
    Les valeurs par défaut ne sont définies que pour le développement local.
    """

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",  # Ignore les variables inconnues
    )

    # ── Application ──────────────────────────────────────────────────────────
    APP_NAME: str = "JurisIA"
    APP_ENV: Literal["development", "staging", "production"] = "development"
    APP_SECRET_KEY: str
    APP_DEBUG: bool = False
    APP_BASE_URL: str = "http://localhost:8000"
    FRONTEND_URL: str = "http://localhost:3000"
    ALLOWED_ORIGINS: str = "http://localhost:3000"

    # ── Base de Données ───────────────────────────────────────────────────────
    DATABASE_URL: str
    DATABASE_POOL_SIZE: int = 10
    DATABASE_MAX_OVERFLOW: int = 20

    # ── Redis ─────────────────────────────────────────────────────────────────
    REDIS_URL: str = "redis://localhost:6379/0"
    REDIS_CACHE_TTL: int = 3600

    # ── JWT ───────────────────────────────────────────────────────────────────
    JWT_SECRET_KEY: str
    JWT_ALGORITHM: str = "HS256"
    JWT_ACCESS_TOKEN_EXPIRE_MINUTES: int = 60
    JWT_REFRESH_TOKEN_EXPIRE_DAYS: int = 30

    # ── Chiffrement ───────────────────────────────────────────────────────────
    ENCRYPTION_KEY: str  # Fernet key pour données sensibles

    # ── Mistral AI ────────────────────────────────────────────────────────────
    MISTRAL_API_KEY: str
    MISTRAL_MODEL: str = "mistral-large-latest"
    MISTRAL_MAX_TOKENS: int = 4096
    MISTRAL_TEMPERATURE: float = 0.1

    # ── Qdrant (Vector DB) ────────────────────────────────────────────────────
    QDRANT_URL: str = "http://localhost:6333"
    QDRANT_API_KEY: str | None = None
    QDRANT_COLLECTION_NAME: str = "jurisai_legal_corpus"

    # ── Stockage S3-compatible ────────────────────────────────────────────────
    S3_ENDPOINT_URL: str | None = None  # None = MinIO local / AWS
    S3_ACCESS_KEY_ID: str = "minioadmin"
    S3_SECRET_ACCESS_KEY: str = "minioadmin"
    S3_BUCKET_NAME: str = "jurisai-documents"
    S3_REGION: str = "gra"

    # ── Stripe ────────────────────────────────────────────────────────────────
    STRIPE_SECRET_KEY: str
    STRIPE_WEBHOOK_SECRET: str = ""
    STRIPE_PRICE_ID_STARTER: str = ""
    STRIPE_PRICE_ID_PRO: str = ""
    STRIPE_PRICE_ID_BUSINESS: str = ""

    # ── Mailjet ───────────────────────────────────────────────────────────────
    MAILJET_API_KEY: str = ""
    MAILJET_SECRET_KEY: str = ""
    MAILJET_FROM_EMAIL: str = "hello@jurisai.fr"
    MAILJET_FROM_NAME: str = "JurisIA"

    # ── Yousign ───────────────────────────────────────────────────────────────
    YOUSIGN_API_KEY: str = ""
    YOUSIGN_BASE_URL: str = "https://api-sandbox.yousign.app/v3"

    # ── Pappers ───────────────────────────────────────────────────────────────
    PAPPERS_API_KEY: str = ""

    # ── Sentry ────────────────────────────────────────────────────────────────
    SENTRY_DSN: str = ""
    SENTRY_ENVIRONMENT: str = "development"

    # ── Celery ────────────────────────────────────────────────────────────────
    CELERY_BROKER_URL: str = "redis://localhost:6379/1"
    CELERY_RESULT_BACKEND: str = "redis://localhost:6379/2"
    CELERY_MAX_RETRIES: int = 3
    CELERY_RETRY_DELAY: int = 60

    # ── Rate Limiting ─────────────────────────────────────────────────────────
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_AUTH_PER_MINUTE: int = 10

    # ── Quotas par Plan ───────────────────────────────────────────────────────
    QUOTA_FREE_DOCUMENTS: int = 3
    QUOTA_STARTER_DOCUMENTS_PER_MONTH: int = 20
    QUOTA_STARTER_QUESTIONS_PER_MONTH: int = 50
    QUOTA_PRO_DOCUMENTS_PER_MONTH: int = 9999
    QUOTA_PRO_QUESTIONS_PER_MONTH: int = 9999

    # ── Légifrance ────────────────────────────────────────────────────────────
    LEGIFRANCE_CLIENT_ID: str = ""
    LEGIFRANCE_CLIENT_SECRET: str = ""

    # ── Computed Properties ───────────────────────────────────────────────────
    @property
    def is_production(self) -> bool:
        return self.APP_ENV == "production"

    @property
    def is_development(self) -> bool:
        return self.APP_ENV == "development"

    @property
    def allowed_origins_list(self) -> List[str]:
        """Convertit la chaîne CSV des origines en liste."""
        return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",")]

    # ── Validateurs ──────────────────────────────────────────────────────────
    @field_validator("MISTRAL_TEMPERATURE")
    @classmethod
    def validate_temperature(cls, v: float) -> float:
        if not 0.0 <= v <= 1.0:
            raise ValueError("MISTRAL_TEMPERATURE doit être entre 0.0 et 1.0")
        return v

    @model_validator(mode="after")
    def validate_production_secrets(self) -> "Settings":
        """En production, certaines clés sont obligatoires."""
        if self.APP_ENV == "production":
            required = [
                ("SENTRY_DSN", self.SENTRY_DSN),
                ("STRIPE_WEBHOOK_SECRET", self.STRIPE_WEBHOOK_SECRET),
            ]
            missing = [name for name, val in required if not val]
            if missing:
                raise ValueError(
                    f"Variables obligatoires en production manquantes : {missing}"
                )
        return self


@lru_cache
def get_settings() -> Settings:
    """
    Retourne l'instance unique des paramètres (singleton).
    Utiliser cette fonction dans toute l'application via Depends(get_settings).
    """
    return Settings()


# Instance globale pour les imports directs (hors FastAPI Depends)
settings = get_settings()
