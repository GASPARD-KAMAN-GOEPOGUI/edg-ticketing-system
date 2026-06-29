"""Drop obsolete tables: homepage_config, homepage_slide, active_session, sms_log, announcement_target_unity.

Revision ID: 012
Revises: 011
Create Date: 2026-06-22

Ces tables ont été supprimées car :
- homepage_config / homepage_slide : frontend statique, pas de config DB
- active_session : JWT stateless — aucune session DB nécessaire
- sms_log : pas de gateway SMS intégré dans la v1
- announcement_target_unity : ciblage d'annonces par unité non retenu dans le CDC v1
"""

from alembic import op
import sqlalchemy as sa

revision = "012"
down_revision = "011"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Supprimer dans l'ordre FK d'abord
    for table in (
        "announcement_target_unity",
        "homepage_slide",
        "homepage_config",
        "active_session",
        "sms_log",
    ):
        try:
            op.drop_table(table)
        except Exception:
            pass


def downgrade() -> None:
    # Recréer les tables en downgrade (structure minimale, sans données)
    op.create_table(
        "sms_log",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("status", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("infos", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime, nullable=True),
        sa.Column("phone", sa.String(30), nullable=False),
        sa.Column("message", sa.Text, nullable=False),
        sa.Column("sent_at", sa.DateTime, nullable=True),
        sa.Column("gateway_ref", sa.String(100), nullable=True),
        sa.Column("request_id", sa.Integer, nullable=True),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )

    op.create_table(
        "active_session",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("status", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("infos", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime, nullable=True),
        sa.Column("account_id", sa.Integer, nullable=False),
        sa.Column("session_id", sa.String(100), nullable=False),
        sa.Column("expires_at", sa.DateTime, nullable=True),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )

    op.create_table(
        "homepage_config",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("status", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("infos", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime, nullable=True),
        sa.Column("section_id", sa.String(50), nullable=False),
        sa.Column("visible", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        sa.Column("editable", sa.Boolean, nullable=False, server_default=sa.false()),
        sa.Column("mission_text", sa.Text, nullable=True),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )

    op.create_table(
        "homepage_slide",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("status", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("infos", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime, nullable=True),
        sa.Column("title", sa.String(200), nullable=True),
        sa.Column("subtitle", sa.String(500), nullable=True),
        sa.Column("image_url", sa.String(500), nullable=True),
        sa.Column("cta_label", sa.String(100), nullable=True),
        sa.Column("cta_url", sa.String(500), nullable=True),
        sa.Column("sort_order", sa.Integer, nullable=False, server_default="0"),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )

    op.create_table(
        "announcement_target_unity",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("status", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("infos", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime, nullable=True),
        sa.Column("announcement_id", sa.Integer, nullable=False),
        sa.Column("unity_id", sa.Integer, nullable=False),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
