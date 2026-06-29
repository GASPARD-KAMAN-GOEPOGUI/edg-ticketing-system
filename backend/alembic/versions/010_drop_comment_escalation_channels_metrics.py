"""drop comment, escalation, escalation_level, escalation_status,
announcement_metric, announcement_channel

Revision ID: 010
Revises: 009
Create Date: 2026-06-21

Ces 6 tables sont supprimées.
- comment         → events workflow_detail event_type='comment'
- escalation      → events workflow_detail event_type='escalation_open/reviewed/resolved/rejected'
- escalation_level / escalation_status → référentiels de escalation, plus utilisés
- announcement_metric / announcement_channel → fonctionnalité retirée
"""

from alembic import op
import sqlalchemy as sa

revision = "010"
down_revision = "009"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Suppression dans l'ordre : enfants avant parents (FK child → parent).
    # Les contraintes FK sont portées par les tables enfants (comment, escalation,
    # announcement_metric, announcement_channel). On les supprime en premier.

    op.drop_table("comment")
    op.drop_table("escalation")
    op.drop_table("escalation_level")
    op.drop_table("escalation_status")
    op.drop_table("announcement_metric")
    op.drop_table("announcement_channel")


def downgrade() -> None:
    # ── announcement_channel ──────────────────────────────────────────────────
    op.create_table(
        "announcement_channel",
        sa.Column("id",              sa.Integer(),     nullable=False, autoincrement=True),
        sa.Column("uuid",            sa.String(36),    nullable=False),
        sa.Column("status",          sa.Boolean(),     nullable=False, server_default="1"),
        sa.Column("infos",           sa.JSON(),        nullable=True),
        sa.Column("created_at",      sa.DateTime(),    nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at",      sa.DateTime(),    nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at",      sa.DateTime(),    nullable=True),
        sa.Column("announcement_id", sa.Integer(),     nullable=False),
        sa.Column("channel",         sa.Enum("internal_notif", "email", "sms", "dashboard", "homepage",
                                             name="announcement_channel_enum"), nullable=False),
        sa.ForeignKeyConstraint(["announcement_id"], ["announcement.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── announcement_metric ───────────────────────────────────────────────────
    op.create_table(
        "announcement_metric",
        sa.Column("id",                  sa.Integer(),  nullable=False, autoincrement=True),
        sa.Column("uuid",                sa.String(36), nullable=False),
        sa.Column("status",              sa.Boolean(),  nullable=False, server_default="1"),
        sa.Column("infos",               sa.JSON(),     nullable=True),
        sa.Column("created_at",          sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at",          sa.DateTime(), nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at",          sa.DateTime(), nullable=True),
        sa.Column("announcement_id",     sa.Integer(),  nullable=False),
        sa.Column("emails_sent",         sa.Integer(),  nullable=False, server_default="0"),
        sa.Column("sms_sent",            sa.Integer(),  nullable=False, server_default="0"),
        sa.Column("notifications_sent",  sa.Integer(),  nullable=False, server_default="0"),
        sa.Column("view_count",          sa.Integer(),  nullable=False, server_default="0"),
        sa.Column("consultation_rate",   sa.Float(),    nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["announcement_id"], ["announcement.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("announcement_id", name="uq_ann_metric_ann_id"),
    )

    # ── escalation_level ──────────────────────────────────────────────────────
    op.create_table(
        "escalation_level",
        sa.Column("id",         sa.Integer(),    nullable=False, autoincrement=True),
        sa.Column("uuid",       sa.String(36),   nullable=False),
        sa.Column("status",     sa.Boolean(),    nullable=False, server_default="1"),
        sa.Column("infos",      sa.JSON(),       nullable=True),
        sa.Column("created_at", sa.DateTime(),   nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(),   nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(),   nullable=True),
        sa.Column("code",       sa.String(50),   nullable=False),
        sa.Column("label",      sa.String(200),  nullable=False),
        sa.Column("sort_order", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("is_builtin", sa.Boolean(),    nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )

    # ── escalation_status ─────────────────────────────────────────────────────
    op.create_table(
        "escalation_status",
        sa.Column("id",         sa.Integer(),    nullable=False, autoincrement=True),
        sa.Column("uuid",       sa.String(36),   nullable=False),
        sa.Column("status",     sa.Boolean(),    nullable=False, server_default="1"),
        sa.Column("infos",      sa.JSON(),       nullable=True),
        sa.Column("created_at", sa.DateTime(),   nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime(),   nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at", sa.DateTime(),   nullable=True),
        sa.Column("code",       sa.String(50),   nullable=False),
        sa.Column("label",      sa.String(200),  nullable=False),
        sa.Column("sort_order", sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("is_builtin", sa.Boolean(),    nullable=False, server_default="0"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code"),
    )

    # ── comment ───────────────────────────────────────────────────────────────
    op.create_table(
        "comment",
        sa.Column("id",          sa.Integer(),   nullable=False, autoincrement=True),
        sa.Column("uuid",        sa.String(36),  nullable=False),
        sa.Column("status",      sa.Boolean(),   nullable=False, server_default="1"),
        sa.Column("infos",       sa.JSON(),      nullable=True),
        sa.Column("created_at",  sa.DateTime(),  nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at",  sa.DateTime(),  nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at",  sa.DateTime(),  nullable=True),
        sa.Column("request_id",  sa.Integer(),   nullable=False),
        sa.Column("author_id",   sa.Integer(),   nullable=False),
        sa.Column("author_name", sa.String(200), nullable=False),
        sa.Column("body",        sa.Text(),      nullable=False),
        sa.Column("is_public",   sa.Boolean(),   nullable=False, server_default="0"),
        sa.Column("is_edited",   sa.Boolean(),   nullable=False, server_default="0"),
        sa.ForeignKeyConstraint(["request_id"], ["request.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["author_id"],  ["account.id"]),
        sa.PrimaryKeyConstraint("id"),
    )

    # ── escalation ────────────────────────────────────────────────────────────
    op.create_table(
        "escalation",
        sa.Column("id",                sa.Integer(),    nullable=False, autoincrement=True),
        sa.Column("uuid",              sa.String(36),   nullable=False),
        sa.Column("status",            sa.Boolean(),    nullable=False, server_default="1"),
        sa.Column("infos",             sa.JSON(),       nullable=True),
        sa.Column("created_at",        sa.DateTime(),   nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at",        sa.DateTime(),   nullable=False, server_default=sa.func.now()),
        sa.Column("deleted_at",        sa.DateTime(),   nullable=True),
        sa.Column("request_id",        sa.Integer(),    nullable=False),
        sa.Column("from_user_id",      sa.Integer(),    nullable=True),
        sa.Column("to_user_id",        sa.Integer(),    nullable=True),
        sa.Column("from_agent_name",   sa.String(200),  nullable=False),
        sa.Column("to_agent_name",     sa.String(200),  nullable=False),
        sa.Column("level",             sa.String(50),   nullable=False),
        sa.Column("reason",            sa.Text(),       nullable=False),
        sa.Column("sla_over_hours",    sa.SmallInteger(), nullable=False, server_default="0"),
        sa.Column("priority",          sa.String(50),   nullable=False),
        sa.Column("escalation_status", sa.String(50),   nullable=False, server_default="open"),
        sa.Column("dg_comment",        sa.Text(),       nullable=True),
        sa.ForeignKeyConstraint(["request_id"],   ["request.id"]),
        sa.ForeignKeyConstraint(["from_user_id"], ["account.id"]),
        sa.ForeignKeyConstraint(["to_user_id"],   ["account.id"]),
        sa.PrimaryKeyConstraint("id"),
    )
