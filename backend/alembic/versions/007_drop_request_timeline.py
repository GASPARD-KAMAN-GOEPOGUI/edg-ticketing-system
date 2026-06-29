"""drop request_timeline table

Revision ID: 007
Revises: 006
Create Date: 2026-06-20

Les 75 lignes de request_timeline ont été migrées vers workflow_detail
lors de la migration 006. Ce fichier supprime définitivement la table.

downgrade() la recrée vide — les données historiques ne sont pas
restaurées (elles restent dans workflow_detail avec le marqueur
infos.migrated_from = 'request_timeline').
"""

from alembic import op
import sqlalchemy as sa

revision = "007"
down_revision = "006"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_table("request_timeline")


def downgrade() -> None:
    op.create_table(
        "request_timeline",
        sa.Column("id", sa.Integer(), nullable=False, autoincrement=True),
        sa.Column("uuid", sa.String(36), nullable=False),
        sa.Column("request_id", sa.Integer(), nullable=False),
        sa.Column("event_type", sa.String(50), nullable=True),
        sa.Column("label", sa.String(500), nullable=True),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("actor_name", sa.String(200), nullable=True),
        sa.Column("status", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column("infos", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("updated_at", sa.DateTime(), nullable=False, server_default=sa.text("NOW()")),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
        sa.ForeignKeyConstraint(["request_id"], ["request.id"], ondelete="CASCADE"),
    )
