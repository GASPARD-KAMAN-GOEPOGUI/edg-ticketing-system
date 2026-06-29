"""014 — Ajout de merged_into_id sur la table request (fusion de tickets).

Revision ID: 014
Revises: 013
Create Date: 2026-06-22
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "014"
down_revision = "013"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("request") as batch:
        batch.add_column(
            sa.Column("merged_into_id", sa.Integer(), nullable=True)
        )
        try:
            batch.create_foreign_key(
                "fk_request_merged_into",
                "request",
                ["merged_into_id"],
                ["id"],
            )
        except Exception:
            pass
        batch.create_index("idx_req_merged_into", ["merged_into_id"])


def downgrade() -> None:
    with op.batch_alter_table("request") as batch:
        try:
            batch.drop_constraint("fk_request_merged_into", type_="foreignkey")
        except Exception:
            pass
        try:
            batch.drop_index("idx_req_merged_into")
        except Exception:
            pass
        batch.drop_column("merged_into_id")
