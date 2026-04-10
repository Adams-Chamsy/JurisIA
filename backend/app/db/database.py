"""
JurisIA — Configuration Base de Données
Moteur SQLAlchemy async avec pool de connexions optimisé.
Pattern : session par requête HTTP via FastAPI dependency injection.
"""
from collections.abc import AsyncGenerator
from typing import Any

import structlog
from sqlalchemy import event, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from app.core.config import settings

logger = structlog.get_logger(__name__)


class Base(DeclarativeBase):
    """
    Classe de base pour tous les modèles SQLAlchemy.
    Fournit des utilitaires communs : représentation, conversion dict.
    """

    def to_dict(self) -> dict[str, Any]:
        """Convertit le modèle en dictionnaire (pour logging, debug)."""
        return {
            col.name: getattr(self, col.name)
            for col in self.__table__.columns
        }

    def __repr__(self) -> str:
        classname = self.__class__.__name__
        pk_cols = [col.name for col in self.__table__.columns if col.primary_key]
        pk_vals = {col: getattr(self, col) for col in pk_cols}
        return f"<{classname} {pk_vals}>"


def create_engine() -> AsyncEngine:
    """
    Crée et configure le moteur SQLAlchemy async.
    Pool configuré pour les workloads de production.
    """
    engine = create_async_engine(
        settings.DATABASE_URL,
        echo=settings.is_development,          # SQL query logging en dev
        pool_size=settings.DATABASE_POOL_SIZE,
        max_overflow=settings.DATABASE_MAX_OVERFLOW,
        pool_pre_ping=True,                    # Vérifie les connexions avant usage
        pool_recycle=3600,                     # Renouvelle les connexions toutes les heures
    )

    # Listener pour le logging des connexions lentes
    @event.listens_for(engine.sync_engine, "before_cursor_execute")
    def before_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        context._query_start_time = __import__("time").monotonic()

    @event.listens_for(engine.sync_engine, "after_cursor_execute")
    def after_cursor_execute(conn, cursor, statement, parameters, context, executemany):
        elapsed = __import__("time").monotonic() - context._query_start_time
        if elapsed > 1.0:  # Log les requêtes de plus de 1 seconde
            logger.warning(
                "slow_query_detected",
                duration_seconds=round(elapsed, 3),
                statement=statement[:200],  # Tronquer pour les logs
            )

    return engine


# Instance globale du moteur
engine = create_engine()

# Factory de sessions async
AsyncSessionLocal = async_sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,  # Évite les lazy loads après commit
    autocommit=False,
    autoflush=False,
)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    Dependency FastAPI : fournit une session DB par requête.
    La session est automatiquement fermée après la requête.

    Usage dans les endpoints :
        async def my_endpoint(db: AsyncSession = Depends(get_db)):
    """
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def check_db_connection() -> bool:
    """Vérifie que la base de données est accessible. Utilisé pour le health check."""
    try:
        async with AsyncSessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return True
    except Exception as e:
        logger.error("db_connection_failed", error=str(e))
        return False


async def init_db() -> None:
    """
    Initialise la base de données : crée les tables si elles n'existent pas.
    En production, utiliser Alembic pour les migrations.
    """
    # Import au niveau module pour charger tous les modèles dans Base.metadata
    import app.models  # noqa: F401 — enregistre les modèles dans Base.metadata
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
        logger.info("db_initialized", tables=list(Base.metadata.tables.keys()))
