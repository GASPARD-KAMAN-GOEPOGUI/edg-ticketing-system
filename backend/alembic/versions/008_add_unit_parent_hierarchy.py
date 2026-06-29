"""add parent_id to unit for hierarchy tree (pattern edgrh)

Revision ID: 008
Revises: 007
Create Date: 2026-06-20

Ajoute une auto-référence `parent_id` sur la table `unit` pour supporter
une hiérarchie récursive d'unités (sous-unités, sous-sous-unités, etc.).
Reproduit le pattern OrganigramModel d'edgrh, adapté à la structure backend.

Les requêtes `WITH RECURSIVE` (ancestors, descendants, tree) sont dans
RepositoryUnit.
"""

from alembic import op
import sqlalchemy as sa

revision = "008"
down_revision = "007"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "unit",
        sa.Column("parent_id", sa.Integer(), nullable=True),
    )
    op.create_foreign_key(
        "fk_unit_parent",
        "unit", "unit",
        ["parent_id"], ["id"],
        ondelete="SET NULL",
    )
    op.create_index("idx_unit_parent", "unit", ["parent_id"])


def downgrade() -> None:
    op.drop_index("idx_unit_parent", table_name="unit")
    op.drop_constraint("fk_unit_parent", "unit", type_="foreignkey")
    op.drop_column("unit", "parent_id")
