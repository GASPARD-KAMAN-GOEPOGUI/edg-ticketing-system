"""Ajoute le role "technicien" (memes permissions/espace qu'agent-support) aux
enums role_enum (account), log_role_enum (activity_log) et
ann_target_role_enum (announcement_target_role). Ajout pur, aucun backfill
necessaire (aucune ligne existante ne porte cette valeur).

Revision ID: 020
Revises: 019
Create Date: 2026-09-18
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "020"
down_revision: Union[str, None] = "019"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_ROLES = (
    "public", "user", "agent-support", "chief-service", "chief-departement",
    "director", "admin",
)
_NEW_ROLES = (
    "public", "user", "agent-support", "technicien", "chief-service",
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
    op.execute("UPDATE account SET role = 'agent-support' WHERE role = 'technicien'")
    op.execute(
        "UPDATE activity_log SET actor_role = 'agent-support' WHERE actor_role = 'technicien'"
    )
    op.execute(
        "UPDATE announcement_target_role SET role = 'agent-support' WHERE role = 'technicien'"
    )
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
