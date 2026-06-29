"""align workflow_detail with edgrh DetailWorkflowModel: drop workflow_status, make accepted nullable

Revision ID: 005
Revises: 004
Create Date: 2026-06-20
"""
from alembic import op
import sqlalchemy as sa

revision = "005"
down_revision = "004"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Make accepted nullable: None=en attente, True=accepté, False=rejeté (comme edgrh)
    op.alter_column("workflow_detail", "accepted", existing_type=sa.Boolean(), nullable=True)

    # Rows created as workflow steps that haven't been decided yet: reset to NULL
    op.execute(
        "UPDATE workflow_detail SET accepted = NULL "
        "WHERE accepted = 0 AND activated = 0 AND deleted_at IS NULL"
    )

    # Drop workflow_status: le statut global appartient à Workflow, pas WorkflowDetail (comme edgrh)
    op.drop_column("workflow_detail", "workflow_status")


def downgrade() -> None:
    op.add_column("workflow_detail", sa.Column("workflow_status", sa.String(50), nullable=True))
    op.execute("UPDATE workflow_detail SET workflow_status = 'active' WHERE workflow_status IS NULL")
    op.alter_column("workflow_detail", "workflow_status", existing_type=sa.String(50), nullable=False)
    op.alter_column("workflow_detail", "accepted", existing_type=sa.Boolean(), nullable=False)
