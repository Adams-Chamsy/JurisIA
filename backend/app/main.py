"""
JurisIA — Application FastAPI Principale
Point d'entrée du serveur. Configure tous les middlewares, routers et événements du cycle de vie.
"""
from __future__ import annotations

import sys
import time
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request, status
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.middleware import SlowAPIMiddleware
from slowapi.util import get_remote_address

from app.core.config import settings
from app.core.logging import configure_logging
from app.db.database import check_db_connection, init_db

# ── Logging structuré (configurer en premier) ─────────────────────────────────
configure_logging()
logger = structlog.get_logger(__name__)

# ── Rate Limiter global ───────────────────────────────────────────────────────
_in_pytest = "pytest" in sys.modules or "PYTEST_CURRENT_TEST" in __import__("os").environ  # noqa: SIM118
limiter = Limiter(
    key_func=get_remote_address,
    default_limits=[f"{settings.RATE_LIMIT_PER_MINUTE}/minute"],
    storage_uri="memory://" if _in_pytest else settings.REDIS_URL,
)


# ── Lifespan (startup / shutdown) ─────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI):
    """Gestion du cycle de vie de l'application."""
    # ── STARTUP ──
    logger.info("app_starting", env=settings.APP_ENV, version="1.0.0")

    # Vérifier la connexion DB
    if not await check_db_connection():
        logger.error("startup_db_connection_failed")
        raise RuntimeError("Impossible de se connecter à la base de données au démarrage")

    # Créer les tables en dev (en prod, utiliser Alembic)
    if settings.is_development:
        await init_db()
        logger.info("dev_db_initialized")

    # Configurer Sentry si DSN fourni
    if settings.SENTRY_DSN:
        import sentry_sdk
        from sentry_sdk.integrations.fastapi import FastApiIntegration
        from sentry_sdk.integrations.sqlalchemy import SqlalchemyIntegration
        sentry_sdk.init(
            dsn=settings.SENTRY_DSN,
            environment=settings.SENTRY_ENVIRONMENT,
            integrations=[FastApiIntegration(), SqlalchemyIntegration()],
            traces_sample_rate=0.1,
        )
        logger.info("sentry_initialized")

    logger.info("app_started_successfully")
    yield

    # ── SHUTDOWN ──
    logger.info("app_shutting_down")
    from app.db.database import engine
    await engine.dispose()
    logger.info("app_shutdown_complete")


# ── Création de l'application ─────────────────────────────────────────────────
app = FastAPI(
    title="JurisIA API",
    description=(
        "Assistant Juridique IA Souverain pour PME Françaises.\n\n"
        "🔒 Données hébergées en France | ✅ RGPD natif | ⚖️ Droit français spécialisé"
    ),
    version="1.0.0",
    docs_url="/docs" if not settings.is_production else None,    # Désactivé en prod
    redoc_url="/redoc" if not settings.is_production else None,
    openapi_url="/openapi.json" if not settings.is_production else None,
    lifespan=lifespan,
)

# ── Rate Limiting ─────────────────────────────────────────────────────────────
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(SlowAPIMiddleware)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origins_list,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-Request-ID", "X-CSRF-Token"],
    expose_headers=["X-Request-ID", "X-RateLimit-Limit", "X-RateLimit-Remaining"],
)

# ── Compression Gzip ──────────────────────────────────────────────────────────
app.add_middleware(GZipMiddleware, minimum_size=1000)


# ── Middleware : Request ID & Timing ──────────────────────────────────────────
@app.middleware("http")
async def request_context_middleware(request: Request, call_next):
    """
    Ajoute un ID unique à chaque requête et mesure le temps de réponse.
    Loggue toutes les requêtes avec leur durée.
    """
    import uuid
    request_id = request.headers.get("X-Request-ID", str(uuid.uuid4())[:8])
    start_time = time.monotonic()

    # Bind le request_id au contexte de log pour toute la durée de la requête
    structlog.contextvars.bind_contextvars(request_id=request_id)

    try:
        response = await call_next(request)
        duration_ms = round((time.monotonic() - start_time) * 1000, 2)

        response.headers["X-Request-ID"] = request_id
        response.headers["X-Response-Time"] = f"{duration_ms}ms"

        # Ne pas logger les health checks pour éviter le bruit
        if request.url.path not in ("/health", "/metrics"):
            log_level = "warning" if response.status_code >= 400 else "info"
            getattr(logger, log_level)(
                "http_request",
                method=request.method,
                path=request.url.path,
                status_code=response.status_code,
                duration_ms=duration_ms,
            )
        return response
    except Exception as exc:
        duration_ms = round((time.monotonic() - start_time) * 1000, 2)
        logger.error(
            "http_request_error",
            method=request.method,
            path=request.url.path,
            duration_ms=duration_ms,
            error=str(exc),
        )
        raise
    finally:
        structlog.contextvars.clear_contextvars()


# ── Middleware : Security Headers ─────────────────────────────────────────────
@app.middleware("http")
async def security_headers_middleware(request: Request, call_next):
    """Ajoute les headers de sécurité HTTP à chaque réponse."""
    response = await call_next(request)
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
    response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
    if settings.is_production:
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains; preload"
    return response


# ── Gestionnaire d'erreurs global ─────────────────────────────────────────────
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """
    Capture toutes les exceptions non gérées.
    Ne jamais exposer les détails techniques en production.
    """
    logger.error(
        "unhandled_exception",
        path=request.url.path,
        method=request.method,
        error=str(exc),
        error_type=type(exc).__name__,
    )
    if settings.is_production:
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content={
                "code": "INTERNAL_ERROR",
                "message": "Une erreur interne s'est produite. Notre équipe a été notifiée.",
                "action": "Si le problème persiste, contactez support@jurisai.fr",
            },
        )
    # En dev, retourner les détails pour le débogage
    return JSONResponse(
        status_code=500,
        content={"code": "INTERNAL_ERROR", "message": str(exc), "type": type(exc).__name__},
    )


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(
        status_code=404,
        content={
            "code": "NOT_FOUND",
            "message": f"Route introuvable : {request.method} {request.url.path}",
        },
    )


# ── Enregistrement des routers ────────────────────────────────────────────────
from app.api.v1.endpoints import auth, documents, chat, billing, compliance, users  # noqa: E402

API_PREFIX = "/api/v1"

app.include_router(auth.router, prefix=API_PREFIX)
app.include_router(documents.router, prefix=API_PREFIX)
app.include_router(chat.router, prefix=API_PREFIX)
app.include_router(billing.router, prefix=API_PREFIX)
app.include_router(compliance.router, prefix=API_PREFIX)
app.include_router(users.router, prefix=API_PREFIX)


# ── Endpoints système ─────────────────────────────────────────────────────────
@app.get("/health", tags=["System"], include_in_schema=False)
async def health_check():
    """Health check endpoint pour les load balancers et le monitoring."""
    db_ok = await check_db_connection()
    redis_ok = await _check_redis()

    all_healthy = db_ok and redis_ok
    status_code = 200 if all_healthy else 503

    return JSONResponse(
        status_code=status_code,
        content={
            "status": "healthy" if all_healthy else "degraded",
            "version": "1.0.0",
            "environment": settings.APP_ENV,
            "services": {
                "database": "up" if db_ok else "down",
                "redis": "up" if redis_ok else "down",
            },
        },
    )


@app.get("/", tags=["System"], include_in_schema=False)
async def root():
    return {
        "name": "JurisIA API",
        "version": "1.0.0",
        "docs": "/docs",
        "status": "operational",
    }


async def _check_redis() -> bool:
    try:
        import redis.asyncio as aioredis
        r = aioredis.from_url(settings.REDIS_URL)
        await r.ping()
        await r.aclose()
        return True
    except Exception:
        return False
