"""Replace direction + unit tables with unity + organigram.

Revision ID: 011
Revises: 010
Create Date: 2026-06-22

Changements :
- Crée les tables : unity, organigram
- Supprime les colonnes direction_id + unit_id des tables FK-bearing
- Ajoute unity_id aux tables FK-bearing
- Supprime les tables : direction, unit, announcement_target_direction
"""

from alembic import op
import sqlalchemy as sa

revision = "011"
down_revision = "010"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # ── 1. Créer la table unity ───────────────────────────────────────────────
    op.create_table(
        "unity",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("status", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("infos", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime, nullable=True),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("codename", sa.String(50), nullable=False, unique=True),
        sa.Column("aleas", sa.String(50), nullable=True),
        sa.Column("description", sa.Text, nullable=True),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("idx_unity_codename", "unity", ["codename"])
    op.create_index("idx_unity_status", "unity", ["status", "deleted_at"])

    # ── 2. Créer la table organigram ──────────────────────────────────────────
    op.create_table(
        "organigram",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("status", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("infos", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now(), onupdate=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime, nullable=True),
        sa.Column("unity_id", sa.Integer, sa.ForeignKey("unity.id"), nullable=False),
        sa.Column("parent_id", sa.Integer, sa.ForeignKey("organigram.id", ondelete="SET NULL"), nullable=True),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
        mysql_collate="utf8mb4_unicode_ci",
    )
    op.create_index("idx_org_unity", "organigram", ["unity_id"])
    op.create_index("idx_org_parent", "organigram", ["parent_id"])
    op.create_index("idx_org_status", "organigram", ["status", "deleted_at"])

    # ── 3. Mettre à jour account — direction_id/unit_id → unity_id ──────────
    with op.batch_alter_table("account") as batch_op:
        # Supprime les anciennes colonnes FK si elles existent
        try:
            batch_op.drop_constraint("fk_account_direction", type_="foreignkey")
        except Exception:
            pass
        try:
            batch_op.drop_constraint("fk_account_unit", type_="foreignkey")
        except Exception:
            pass
        try:
            batch_op.drop_column("direction_id")
        except Exception:
            pass
        try:
            batch_op.drop_column("unit_id")
        except Exception:
            pass
        batch_op.add_column(
            sa.Column("unity_id", sa.Integer, sa.ForeignKey("unity.id"), nullable=True)
        )

    op.create_index("idx_account_unity", "account", ["unity_id"])

    # ── 5. Mettre à jour request — direction_id/unit_id → unity_id ────────────
    with op.batch_alter_table("request") as batch_op:
        for col in ("direction_id", "unit_id", "on_behalf_direction_id", "on_behalf_unit_id"):
            try:
                batch_op.drop_column(col)
            except Exception:
                pass
        batch_op.add_column(
            sa.Column("unity_id", sa.Integer, sa.ForeignKey("unity.id"), nullable=True)
        )
        batch_op.add_column(
            sa.Column("on_behalf_unity_id", sa.Integer, sa.ForeignKey("unity.id"), nullable=True)
        )

    # ── 6. Mettre à jour routing_rule ─────────────────────────────────────────
    with op.batch_alter_table("routing_rule") as batch_op:
        for col in ("target_direction_id", "target_unit_id"):
            try:
                batch_op.drop_column(col)
            except Exception:
                pass
        batch_op.add_column(
            sa.Column("target_unity_id", sa.Integer, sa.ForeignKey("unity.id"), nullable=True)
        )

    # ── 7. Mettre à jour workflow_detail — unit_id → unity_id ─────────────────
    with op.batch_alter_table("workflow_detail") as batch_op:
        try:
            batch_op.drop_column("unit_id")
        except Exception:
            pass
        batch_op.add_column(
            sa.Column("unity_id", sa.Integer, sa.ForeignKey("unity.id"), nullable=True)
        )

    # ── 8. Supprimer les anciennes tables ─────────────────────────────────────
    # announcement_target_direction d'abord (FK sur direction.id)
    try:
        op.drop_table("announcement_target_direction")
    except Exception:
        pass

    try:
        op.drop_table("unit")
    except Exception:
        pass

    try:
        op.drop_table("direction")
    except Exception:
        pass


def downgrade() -> None:
    # Recréer direction + unit (structure minimale)
    op.create_table(
        "direction",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("status", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("infos", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime, nullable=True),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )
    op.create_table(
        "unit",
        sa.Column("id", sa.Integer, primary_key=True, autoincrement=True),
        sa.Column("status", sa.Boolean, nullable=False, server_default=sa.true()),
        sa.Column("infos", sa.JSON, nullable=True),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime, nullable=True),
        sa.Column("code", sa.String(20), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("direction_id", sa.Integer, sa.ForeignKey("direction.id"), nullable=True),
        mysql_engine="InnoDB",
        mysql_charset="utf8mb4",
    )

    # Restaurer les colonnes (sans données)
    with op.batch_alter_table("account") as batch_op:
        batch_op.drop_column("unity_id")
        batch_op.add_column(sa.Column("direction_id", sa.Integer, sa.ForeignKey("direction.id"), nullable=True))
        batch_op.add_column(sa.Column("unit_id", sa.Integer, sa.ForeignKey("unit.id"), nullable=True))

    with op.batch_alter_table("request") as batch_op:
        batch_op.drop_column("unity_id")
        batch_op.drop_column("on_behalf_unity_id")
        batch_op.add_column(sa.Column("direction_id", sa.Integer, nullable=True))
        batch_op.add_column(sa.Column("unit_id", sa.Integer, nullable=True))
        batch_op.add_column(sa.Column("on_behalf_direction_id", sa.Integer, nullable=True))
        batch_op.add_column(sa.Column("on_behalf_unit_id", sa.Integer, nullable=True))

    with op.batch_alter_table("routing_rule") as batch_op:
        batch_op.drop_column("target_unity_id")
        batch_op.add_column(sa.Column("target_direction_id", sa.Integer, nullable=True))
        batch_op.add_column(sa.Column("target_unit_id", sa.Integer, nullable=True))

    with op.batch_alter_table("workflow_detail") as batch_op:
        batch_op.drop_column("unity_id")
        batch_op.add_column(sa.Column("unit_id", sa.Integer, nullable=True))

    # Supprimer les nouvelles tables
    op.drop_table("organigram")
    op.drop_table("unity")
