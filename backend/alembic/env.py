"""
Alembic env.py — configuration async pour SQLAlchemy 2.0 + aiomysql.

Flux d'exécution :
  alembic upgrade head   → run_migrations_online() via asyncio.run()
  alembic upgrade head --sql → run_migrations_offline() (génère le SQL sans l'exécuter)
"""
from __future__ import annotations

import asyncio
import os
import sys
from logging.config import fileConfig

from sqlalchemy import pool
from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.engine import Connection

from alembic import context

# ── Chemin Python — permet d'importer api.* depuis backend/ ──────────────────
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

# ── Importe les modèles pour que Base.metadata les contienne ─────────────────
import api.models  # noqa: F401 — enregistre tous les modèles dans Base.metadata
from api.models.base import Base
from api.configs.Environment import get_environment

# ── Config Alembic ────────────────────────────────────────────────────────────
alembic_config = context.config

if alembic_config.config_file_name is not None:
    fileConfig(alembic_config.config_file_name)

target_metadata = Base.metadata

# ── URL de la base construite depuis les variables d'environnement ────────────
def _get_url() -> str:
    env = get_environment()
    # aiomysql pour le moteur async ; pymysql pour le mode offline (génération SQL)
    return (
        f"mysql+aiomysql://{env.DATABASE_USERNAME}:{env.DATABASE_PASSWORD}"
        f"@{env.DATABASE_HOSTNAME}:{env.DATABASE_PORT}/{env.DATABASE_NAME}"
    )

def _get_sync_url() -> str:
    """URL synchrone (pymysql) utilisée uniquement en mode offline."""
    env = get_environment()
    return (
        f"mysql+pymysql://{env.DATABASE_USERNAME}:{env.DATABASE_PASSWORD}"
        f"@{env.DATABASE_HOSTNAME}:{env.DATABASE_PORT}/{env.DATABASE_NAME}"
    )


# ── Mode offline : génère le SQL sans connexion ───────────────────────────────
def run_migrations_offline() -> None:
    context.configure(
        url=_get_sync_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


# ── Mode online (async) ───────────────────────────────────────────────────────
def do_run_migrations(connection: Connection) -> None:
    context.configure(
        connection=connection,
        target_metadata=target_metadata,
        compare_type=True,
    )
    with context.begin_transaction():
        context.run_migrations()


async def run_async_migrations() -> None:
    engine = create_async_engine(
        _get_url(),
        poolclass=pool.NullPool,
    )
    async with engine.connect() as connection:
        await connection.run_sync(do_run_migrations)
    await engine.dispose()


def run_migrations_online() -> None:
    asyncio.run(run_async_migrations())


# ── Point d'entrée ────────────────────────────────────────────────────────────
if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
