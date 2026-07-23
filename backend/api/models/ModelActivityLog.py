from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Enum as SAEnum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, BaseColumns, MYSQL_ARGS

if TYPE_CHECKING:
    from .ModelAccount import Account


class ActivityLog(Base, BaseColumns):
    """
    Append-only — jamais de UPDATE ni DELETE.
    ip_address et user_agent sont masqués pour tout rôle sauf admin.
    actor est un snapshot du nom conservé pour l'audit.
    """

    __tablename__ = "activity_log"

    # ── Clé étrangère ─────────────────────────────────────────────────────────
    actor_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("account.id"), nullable=True
    )

    # ── Attributs métier ──────────────────────────────────────────────────────
    actor: Mapped[str] = mapped_column(String(200), nullable=False)
    actor_role: Mapped[str] = mapped_column(
        SAEnum("public", "user", "agent", "chief", "director", "dg", "admin",
               name="log_role_enum"),
        nullable=False,
    )
    action: Mapped[str] = mapped_column(String(500), nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    target: Mapped[str] = mapped_column(String(500), nullable=False)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    log_status: Mapped[str] = mapped_column(
        SAEnum("success", "warning", "error", name="log_status_enum"),
        nullable=False,
    )

    # ── Relations ─────────────────────────────────────────────────────────────
    actor_account: Mapped[Optional[Account]] = relationship(
        "Account", foreign_keys="ActivityLog.actor_id", lazy="raise"
    )

    __table_args__ = (
        Index("idx_log_cat", "category"),
        Index("idx_log_actor", "actor_id"),
        Index("idx_log_created", "created_at"),
        Index("idx_log_logstatus", "log_status"),
        Index("idx_log_status", "status", "deleted_at"),
        MYSQL_ARGS,
    )
