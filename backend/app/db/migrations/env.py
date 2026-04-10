"""
JurisIA — Environnement Alembic
Lit la DATABASE_URL depuis les variables d'environnement et configure les migrations.
"""
from __future__ import annotations

import asyncio
import os
from logging.config import fileConfig

from alembic import context
from sqlalchemy import pool
from sqlalchemy.engine import Connection
from sqlalchemy.ext.asyncio import async_engine_from_config

# ── Charger les modèles dans Base.metadata ────────────────────────────────────
# Import obligatoire pour que Alembic détecte les tables
import app.models  # noqa: F401 — side effect import
from app.db.database import Base

# Configuration Alembic
config = context.config

# Configurer le logging depuis alembic.ini
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Métadonnées cible pour l'autogenerate
target_metadata = Base.metadata

# ── Lire DATABASE_URL depuis les variables d'environnement ────────────────────
database_url = os.environ.get("DATABASE_URL")
if not database_url:
    raise ValueError(
        "DATABASE_URL n'est pas définie. "
        "Assurez-vous que votre fichier .env est chargé."
    )

# Alembic sync : convertir asyncpg → psycopg2 si nécessaire
# (Alembic génère les migrations en mode synchrone)
sync_url = database_url.replace("postgresql+asyncpg://", "postgresql+psycopg2://")
config.set_main_option("sqlalchemy.url", sync_url)


def run_migrations_offline() -> None:
    """
    Mode offline : génère le SQL sans se connecter à la BDD.
    Utile pour : alembic upgrade head --sql > migration.sql
    """
    url = config.get_main_option("sqlalchemy.url")
    context.configure(
        url=url,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
        compare_server_default=True,
    )

    with context.begin_transaction():
        context.run_migrations()


def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
        compare_server_default=True,
        # Inclure les schémas dans la comparaison
        include_schemas=True,
    )

    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    """Mode online async : se connecte réellement à PostgreSQL."""
    connectable = async_engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )

    async with connectable.connect() as connection:
        await connection.run_sync(do_run_migrations)

    await connectable.dispose()


def run_migrations_online() -> None:
    """Mode online : point d'entrée principal pour les migrations."""
    asyncio.run(run_async_migrations())


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
