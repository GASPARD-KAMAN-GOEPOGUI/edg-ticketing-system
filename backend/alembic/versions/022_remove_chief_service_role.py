"""Retire le role "chief-service" (purement local, jamais assigne a aucun
compte) des enums role_enum (account), log_role_enum (activity_log) et
ann_target_role_enum (announcement_target_role). Aucun backfill necessaire :
aucune ligne existante ne porte cette valeur (verifie avant migration).

Revision ID: 022
Revises: 021
Create Date: 2026-09-18
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "022"
down_revision: Union[str, None] = "021"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_ROLES = (
    "public", "user", "agent-support", "technicien", "chef-division-support",
    "chief-service", "chief-departement", "director", "admin",
)
_NEW_ROLES = (
    "public", "user", "agent-support", "technicien", "chef-division-support",
    "chief-departement", "director", "admin",
)


def upgrade() -> None:
    op.alter_column(
        "account", "role",
        existing_type=sa.Enum(*_OLD_ROLES, name="role_enum"),
        type_=sa.Enum(*_NEW_ROLES, name="role_enum"),
        nullable=False,
    )
    op.alter_column(
        "activity_log", "actor_role",
        existing_type=sa.Enum(*_OLD_ROLES, name="log_role_enum"),
        type_=sa.Enum(*_NEW_ROLES, name="log_role_enum"),
        nullable=False,
    )
    op.alter_column(
        "announcement_target_role", "role",
        existing_type=sa.Enum(*_OLD_ROLES, name="ann_target_role_enum"),
        type_=sa.Enum(*_NEW_ROLES, name="ann_target_role_enum"),
        nullable=False,
    )


def downgrade() -> None:
    op.alter_column(
        "announcement_target_role", "role",
        existing_type=sa.Enum(*_NEW_ROLES, name="ann_target_role_enum"),
        type_=sa.Enum(*_OLD_ROLES, name="ann_target_role_enum"),
        nullable=False,
    )
    op.alter_column(
        "activity_log", "actor_role",
        existing_type=sa.Enum(*_NEW_ROLES, name="log_role_enum"),
        type_=sa.Enum(*_OLD_ROLES, name="log_role_enum"),
        nullable=False,
    )
    op.alter_column(
        "account", "role",
        existing_type=sa.Enum(*_NEW_ROLES, name="role_enum"),
        type_=sa.Enum(*_OLD_ROLES, name="role_enum"),
        nullable=False,
    )
