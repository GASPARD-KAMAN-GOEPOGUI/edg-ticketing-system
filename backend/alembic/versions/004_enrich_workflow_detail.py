"""enrich workflow_detail: add event_type, label, actor_name, request_id; make workflow_id nullable

Revision ID: 004
Revises: 003
Create Date: 2026-06-20
"""
from alembic import op
import sqlalchemy as sa

revision = "004"
down_revision = "003"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Make workflow_id nullable (timeline events don't belong to a workflow)
    op.alter_column("workflow_detail", "workflow_id", existing_type=sa.Integer(), nullable=True)

    # Add request_id FK (direct link for timeline event rows)
    op.add_column("workflow_detail", sa.Column("request_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        "fk_wfd_request_id", "workflow_detail", "request", ["request_id"], ["id"]
    )

    # Add timeline-specific fields
    op.add_column("workflow_detail", sa.Column("event_type", sa.String(50), nullable=True))
    op.add_column("workflow_detail", sa.Column("label", sa.String(500), nullable=True))
    op.add_column("workflow_detail", sa.Column("actor_name", sa.String(200), nullable=True))

    # Index for efficient timeline queries by request
    op.create_index("idx_wfd_req", "workflow_detail", ["request_id"])


def downgrade() -> None:
    op.drop_index("idx_wfd_req", table_name="workflow_detail")
    op.drop_constraint("fk_wfd_request_id", "workflow_detail", type_="foreignkey")
    op.drop_column("workflow_detail", "actor_name")
    op.drop_column("workflow_detail", "label")
    op.drop_column("workflow_detail", "event_type")
    op.drop_column("workflow_detail", "request_id")
    op.alter_column("workflow_detail", "workflow_id", existing_type=sa.Integer(), nullable=False)
