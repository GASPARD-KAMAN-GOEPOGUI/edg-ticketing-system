"""Ajoute le role "chef-division-support" (CDS — memes permissions/espace que
technicien/agent-support pour l'instant, en attendant les restrictions du
Module 2) aux enums role_enum (account), log_role_enum (activity_log) et
ann_target_role_enum (announcement_target_role). Ajout pur, aucun backfill
necessaire (aucune ligne existante ne porte cette valeur).

Revision ID: 021
Revises: 020
Create Date: 2026-09-18
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "021"
down_revision: Union[str, None] = "020"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

_OLD_ROLES = (
    "public", "user", "agent-support", "technicien", "chief-service",
    "chief-departement", "director", "admin",
)
_NEW_ROLES = (
    "public", "user", "agent-support", "technicien", "chef-division-support",
    "chief-service", "chief-departement", "director", "admin",
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
    op.execute(
        "UPDATE account SET role = 'technicien' WHERE role = 'chef-division-support'"
    )
    op.execute(
        "UPDATE activity_log SET actor_role = 'technicien' WHERE actor_role = 'chef-division-support'"
    )
    op.execute(
        "UPDATE announcement_target_role SET role = 'technicien' WHERE role = 'chef-division-support'"
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
