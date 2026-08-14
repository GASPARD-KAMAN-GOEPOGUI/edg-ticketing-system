"""Bascule vers l'authentification centrale manager-user.

Contexte : remplacement du JWT local (Argon2) par la plateforme centrale
manager-user (voir backend/README-integration-plateforme-centrale/). La
colonne password_hash n'a plus d'usage (mots de passe gérés par le central) ;
keycloak_id était un vestige inutilisé d'une tentative SSO abandonnée,
remplacé par des colonnes propres central_user_id/central_user_uuid.
La biométrie admin (ArcFace) est également retirée : plus d'équivalent
côté manager-user, la table security_incident est supprimée.

Revision ID: 016
Revises: 015
Create Date: 2026-08-10
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "016"
down_revision: Union[str, None] = "015"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_column("account", "password_hash")
    op.drop_column("account", "keycloak_id")
    op.add_column("account", sa.Column("central_user_id", sa.Integer(), nullable=True))
    op.add_column("account", sa.Column("central_user_uuid", sa.String(64), nullable=True))
    op.create_unique_constraint("uq_account_central_user_id", "account", ["central_user_id"])
    op.create_unique_constraint("uq_account_central_user_uuid", "account", ["central_user_uuid"])
    op.create_index("idx_account_central_user_id", "account", ["central_user_id"])

    try:
        op.drop_table("security_incident")
    except Exception:
        pass


def downgrade() -> None:
    op.create_table(
        "security_incident",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("uuid", sa.String(36), nullable=True),
        sa.Column("status", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("infos", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime, nullable=True),
        sa.Column("resolved_by", sa.Integer, sa.ForeignKey("account.id"), nullable=True),
        sa.Column("email_attempted", sa.String(320), nullable=True),
        sa.Column("ip_address", sa.String(45), nullable=True),
        sa.Column("user_agent", sa.Text, nullable=True),
        sa.Column("browser", sa.String(100), nullable=True),
        sa.Column("os_info", sa.String(100), nullable=True),
        sa.Column("device_type", sa.String(50), nullable=True),
        sa.Column("location_approx", sa.String(200), nullable=True),
        sa.Column("photo_path", sa.String(500), nullable=True),
        sa.Column("occurred_at", sa.String(50), nullable=True),
        sa.Column("attempt_count", sa.Integer, nullable=False, server_default="1"),
        sa.Column("resolved", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("notes", sa.Text, nullable=True),
        sa.Column("resolved_at", sa.DateTime, nullable=True),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )

    op.drop_index("idx_account_central_user_id", table_name="account")
    op.drop_constraint("uq_account_central_user_uuid", "account", type_="unique")
    op.drop_constraint("uq_account_central_user_id", "account", type_="unique")
    op.drop_column("account", "central_user_uuid")
    op.drop_column("account", "central_user_id")
    op.add_column("account", sa.Column("keycloak_id", sa.String(255), nullable=True))
    op.add_column("account", sa.Column("password_hash", sa.String(255), nullable=True))
