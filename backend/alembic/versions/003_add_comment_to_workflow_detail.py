"""add comment to workflow_detail

Revision ID: 003
Revises: 002
Create Date: 2026-06-20
"""
from alembic import op
import sqlalchemy as sa

revision = "003"
down_revision = "002"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("workflow_detail", sa.Column("comment", sa.Text(), nullable=True))


def downgrade() -> None:
    op.drop_column("workflow_detail", "comment")
