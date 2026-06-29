"""015 — Ajout de parent_direction_id sur unity (hiérarchie entre directions).

Revision ID: 015
Revises: 014
Create Date: 2026-06-27
"""
from __future__ import annotations

from alembic import op
import sqlalchemy as sa

revision = "015"
down_revision = "014"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("unity") as batch:
        batch.add_column(
            sa.Column("parent_direction_id", sa.Integer(), nullable=True)
        )
        try:
            batch.create_foreign_key(
                "fk_unity_parent_direction",
                "unity",
                ["parent_direction_id"],
                ["id"],
                ondelete="SET NULL",
            )
        except Exception:
            pass
        batch.create_index("idx_unity_parent_dir", ["parent_direction_id"])


def downgrade() -> None:
    with op.batch_alter_table("unity") as batch:
        try:
            batch.drop_constraint("fk_unity_parent_direction", type_="foreignkey")
        except Exception:
            pass
        try:
            batch.drop_index("idx_unity_parent_dir")
        except Exception:
            pass
        batch.drop_column("parent_direction_id")
