"""Migre les enums role de activity_log et announcement_target_role vers le
vocabulaire de role actuel (agent-support/chief-service/chief-departement),
jamais mis a jour lors du split agent->agent-support / chief->chief-service+
chief-departement / dg->director. Account.role (role_enum) etait deja correct ;
seuls log_role_enum et ann_target_role_enum trainaient encore l'ancien
vocabulaire, ce qui provoquait un crash (LookupError) des qu'un role normalise
("agent-support", etc.) etait ecrit dans ces colonnes.

Revision ID: 019
Revises: 018
Create Date: 2026-08-28
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "019"
down_revision: Union[str, None] = "018"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_ROLES = ("public", "user", "agent", "chief", "director", "dg", "admin")
_NEW_ROLES = (
    "public", "user", "agent-support", "chief-service", "chief-departement",
    "director", "admin",
)
_UNION_ROLES = (
    "public", "user", "agent", "agent-support", "chief", "chief-service",
    "chief-departement", "director", "dg", "admin",
)
_BACKFILL = {"agent": "agent-support", "chief": "chief-service", "dg": "director"}


def _migrate_column(table: str, column: str, enum_name: str, *, nullable: bool) -> None:
    # 1. Union temporaire (ancien + nouveau vocabulaire) pour pouvoir relire les
    #    lignes existantes pendant la bascule.
    op.alter_column(
        table, column,
        existing_type=sa.Enum(*_UNION_ROLES, name=f"{enum_name}_tmp"),
        type_=sa.Enum(*_UNION_ROLES, name=f"{enum_name}_tmp"),
        nullable=nullable,
    )
    # 2. Backfill des valeurs legacy.
    for old, new in _BACKFILL.items():
        op.execute(f"UPDATE {table} SET {column} = '{new}' WHERE {column} = '{old}'")
    # 3. Restreint au vocabulaire final.
    op.alter_column(
        table, column,
        existing_type=sa.Enum(*_UNION_ROLES, name=f"{enum_name}_tmp"),
        type_=sa.Enum(*_NEW_ROLES, name=enum_name),
        nullable=nullable,
    )


def _revert_column(table: str, column: str, enum_name: str, *, nullable: bool) -> None:
    op.alter_column(
        table, column,
        existing_type=sa.Enum(*_NEW_ROLES, name=enum_name),
        type_=sa.Enum(*_UNION_ROLES, name=f"{enum_name}_tmp"),
        nullable=nullable,
    )
    for old, new in _BACKFILL.items():
        op.execute(f"UPDATE {table} SET {column} = '{old}' WHERE {column} = '{new}'")
    op.alter_column(
        table, column,
        existing_type=sa.Enum(*_UNION_ROLES, name=f"{enum_name}_tmp"),
        type_=sa.Enum(*_OLD_ROLES, name=enum_name),
        nullable=nullable,
    )


def upgrade() -> None:
    _migrate_column("activity_log", "actor_role", "log_role_enum", nullable=False)
    _migrate_column("announcement_target_role", "role", "ann_target_role_enum", nullable=False)


def downgrade() -> None:
    _revert_column("announcement_target_role", "role", "ann_target_role_enum", nullable=False)
    _revert_column("activity_log", "actor_role", "log_role_enum", nullable=False)
