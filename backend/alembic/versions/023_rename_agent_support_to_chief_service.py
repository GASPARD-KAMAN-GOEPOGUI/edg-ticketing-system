"""Renomme le role "agent-support" en "chief-service" (meme role, nouveau nom —
CSSHF selon la procedure papier EDG/PS-GSI/Pro-02). Bascule les lignes
existantes : 5 comptes (account.role), 25 lignes (activity_log.actor_role),
0 ligne (announcement_target_role.role) au moment de cette migration.

Revision ID: 023
Revises: 022
Create Date: 2026-09-21
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "023"
down_revision: Union[str, None] = "022"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_ROLES = (
    "public", "user", "agent-support", "technicien", "chef-division-support",
    "chief-departement", "director", "admin",
)
_UNION_ROLES = (
    "public", "user", "agent-support", "chief-service", "technicien",
    "chef-division-support", "chief-departement", "director", "admin",
)
_NEW_ROLES = (
    "public", "user", "chief-service", "technicien", "chef-division-support",
    "chief-departement", "director", "admin",
)


def _migrate_column(table: str, column: str, enum_name: str, *, nullable: bool) -> None:
    op.alter_column(
        table, column,
        existing_type=sa.Enum(*_UNION_ROLES, name=f"{enum_name}_tmp"),
        type_=sa.Enum(*_UNION_ROLES, name=f"{enum_name}_tmp"),
        nullable=nullable,
    )
    op.execute(f"UPDATE {table} SET {column} = 'chief-service' WHERE {column} = 'agent-support'")
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
    op.execute(f"UPDATE {table} SET {column} = 'agent-support' WHERE {column} = 'chief-service'")
    op.alter_column(
        table, column,
        existing_type=sa.Enum(*_UNION_ROLES, name=f"{enum_name}_tmp"),
        type_=sa.Enum(*_OLD_ROLES, name=enum_name),
        nullable=nullable,
    )


def upgrade() -> None:
    _migrate_column("account", "role", "role_enum", nullable=False)
    _migrate_column("activity_log", "actor_role", "log_role_enum", nullable=False)
    _migrate_column("announcement_target_role", "role", "ann_target_role_enum", nullable=False)


def downgrade() -> None:
    _revert_column("announcement_target_role", "role", "ann_target_role_enum", nullable=False)
    _revert_column("activity_log", "actor_role", "log_role_enum", nullable=False)
    _revert_column("account", "role", "role_enum", nullable=False)
