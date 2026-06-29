"""Convert workflow_status, request_source, task_type, task_status to Python enums.

Revision ID: 013
Revises: 012
Create Date: 2026-06-22

Changements :
- DROP TABLE workflow_status, request_source, task_type, task_status
- ALTER TABLE request : DROP request_source_id (FK INT), ADD request_source VARCHAR(50)
  (les données sont migrées : code extrait via JOIN avant suppression de la FK)
"""

from alembic import op
import sqlalchemy as sa

revision = "013"
down_revision = "012"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # 1. Migrer request.request_source_id → request.request_source (VARCHAR)
    #    Copier le code depuis request_source avant de supprimer la FK
    op.execute("""
        UPDATE request r
        JOIN request_source rs ON r.request_source_id = rs.id
        SET r.request_source = rs.code
        WHERE r.request_source_id IS NOT NULL
    """)

    with op.batch_alter_table("request") as batch_op:
        try:
            batch_op.drop_constraint("fk_request_source", type_="foreignkey")
        except Exception:
            pass
        try:
            batch_op.drop_column("request_source_id")
        except Exception:
            pass
        batch_op.add_column(
            sa.Column("request_source", sa.String(50), nullable=True)
        )

    # 2. Supprimer les tables devenues inutiles
    for table in ("workflow_status", "request_source", "task_type", "task_status"):
        try:
            op.drop_table(table)
        except Exception:
            pass


def downgrade() -> None:
    # Recréer les tables (structure minimale, sans données)
    for name, extra_cols in [
        ("workflow_status", []),
        ("request_source",  []),
        ("task_type",       []),
        ("task_status",     []),
    ]:
        op.create_table(
            name,
            sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
            sa.Column("status", sa.Boolean, nullable=False, server_default=sa.true()),
            sa.Column("infos", sa.JSON, nullable=True),
            sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
            sa.Column("deleted_at", sa.DateTime, nullable=True),
            sa.Column("code", sa.String(50), nullable=False, unique=True),
            sa.Column("label", sa.String(200), nullable=False),
            sa.Column("sort_order", sa.SmallInteger, nullable=False, server_default="0"),
            sa.Column("is_builtin", sa.Boolean, nullable=False, server_default=sa.false()),
            mysql_engine="InnoDB",
            mysql_charset="utf8mb4",
        )

    # Restaurer request_source_id FK sur request (sans données)
    with op.batch_alter_table("request") as batch_op:
        try:
            batch_op.drop_column("request_source")
        except Exception:
            pass
        batch_op.add_column(
            sa.Column("request_source_id", sa.Integer,
                      sa.ForeignKey("request_source.id"), nullable=True)
        )
