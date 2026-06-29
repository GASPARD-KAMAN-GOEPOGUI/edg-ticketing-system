"""drop request_id from workflow_detail

Revision ID: 009
Revises: 008
Create Date: 2026-06-21

La colonne request_id est retirée de workflow_detail.
La remontée vers la Request se fait désormais via workflow_detail → workflow → request.
"""

from alembic import op
import sqlalchemy as sa

revision = "009"
down_revision = "008"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.drop_index("idx_wfd_req", table_name="workflow_detail")
    op.drop_constraint("fk_wfd_request_id", "workflow_detail", type_="foreignkey")
    op.drop_column("workflow_detail", "request_id")


def downgrade() -> None:
    op.add_column(
        "workflow_detail",
        sa.Column("request_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_wfd_request_id",
        "workflow_detail",
        "request",
        ["request_id"],
        ["id"],
    )
    op.create_index("idx_wfd_req", "workflow_detail", ["request_id"])
