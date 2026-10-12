"""
Initialisation de l'application — EDG Support.

Point unique appelé par :
  - le lifespan FastAPI (dev, uvicorn/gunicorn) : `initialize(strict_schema=False)`
  - la commande `python -m api.cli init` (production Passenger, où le lifespan
    ne s'exécute jamais) : `initialize(strict_schema=True)`

Strictement NON DESTRUCTIF :
  1. contrôle du schéma en LECTURE SEULE, AVANT toute écriture : colonnes
     attendues par les modèles absentes de la base, ou valeurs ENUM attendues
     absentes de la colonne réelle → SchemaMismatchError (mode strict) ;
  2. create_all : crée uniquement les tables absentes (jamais de ALTER/DROP) ;
  3. seed_references / seed_admin : insèrent uniquement ce qui manque ;
  4. création des dossiers d'uploads.
"""
from __future__ import annotations

import logging

from sqlalchemy import inspect

import api.models  # noqa: F401 — enregistre toutes les tables dans Base.metadata
from api.models.base import Base

logger = logging.getLogger(__name__)


class SchemaMismatchError(RuntimeError):
    """La base existante ne correspond pas aux modèles (colonnes ou ENUM)."""

    def __init__(self, issues: list[str]) -> None:
        self.issues = issues
        super().__init__(
            "Schéma de base incompatible avec le code :\n  - " + "\n  - ".join(issues)
        )


def expected_schema() -> dict[str, dict[str, frozenset[str] | None]]:
    """{table: {colonne: valeurs ENUM attendues ou None}} d'après les modèles."""
    schema: dict[str, dict[str, frozenset[str] | None]] = {}
    for table in Base.metadata.sorted_tables:
        schema[table.name] = {
            col.name: frozenset(col.type.enums) if getattr(col.type, "enums", None) else None
            for col in table.columns
        }
    return schema


def _reflect_columns(sync_conn, table_names: list[str]) -> dict[str, dict[str, frozenset[str] | None]]:
    """{table existante: {colonne: valeurs ENUM réelles ou None}} lu en base.

    Sur MySQL, le type réfléchi d'une colonne ENUM porte `.enums` ; sur un
    moteur sans ENUM natif (SQLite des tests) la valeur est None et la
    comparaison des valeurs est ignorée pour cette colonne."""
    insp = inspect(sync_conn)
    existing = set(insp.get_table_names())
    actual: dict[str, dict[str, frozenset[str] | None]] = {}
    for name in table_names:
        if name not in existing:
            continue
        actual[name] = {
            col["name"]: frozenset(col["type"].enums) if getattr(col["type"], "enums", None) else None
            for col in insp.get_columns(name)
        }
    return actual


def compare_schema(expected: dict, actual: dict) -> list[str]:
    """Écarts bloquants entre les modèles et la base. Une table absente n'en est
    pas un (create_all la créera) ; une colonne ou une valeur ENUM absente, si."""
    issues: list[str] = []
    for table, columns in expected.items():
        if table not in actual:
            continue
        real = actual[table]
        for column, enums in columns.items():
            if column not in real:
                issues.append(f"{table}.{column} : colonne absente de la base")
                continue
            if enums and real[column] is not None:
                missing = sorted(enums - real[column])
                if missing:
                    issues.append(
                        f"{table}.{column} : valeurs ENUM absentes de la base : {', '.join(missing)}"
                    )
    return issues


async def check_schema(engine) -> list[str]:
    """Contrôle en lecture seule ; retourne la liste des écarts (vide = conforme)."""
    expected = expected_schema()
    async with engine.connect() as conn:
        actual = await conn.run_sync(_reflect_columns, list(expected))
    return compare_schema(expected, actual)


def ensure_upload_dirs() -> None:
    from api import storage

    for sub in ("avatars", "requests"):
        (storage.UPLOAD_DIR / sub).mkdir(parents=True, exist_ok=True)


async def initialize(*, strict_schema: bool, engine=None, session_factory=None) -> None:
    """Initialise la base et les dossiers. Voir la docstring du module."""
    from api.configs import Database
    from api.seed_admin import seed_admin
    from api.seed_references import seed_references

    engine = engine or Database.engine
    session_factory = session_factory or Database.AsyncSessionLocal

    issues = await check_schema(engine)
    if issues:
        if strict_schema:
            raise SchemaMismatchError(issues)
        logger.warning(
            "Schéma de base incompatible avec le code (%d écart(s)) :\n  - %s",
            len(issues), "\n  - ".join(issues),
        )

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with session_factory() as session:
        await seed_references(session)
        await seed_admin(session)
        await session.commit()
    ensure_upload_dirs()
