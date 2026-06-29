from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, Enum as SAEnum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, BaseColumns, MYSQL_ARGS

if TYPE_CHECKING:
    from .ModelAccount import Account
    from .ModelRequest import Request


class Notification(Base, BaseColumns):
    __tablename__ = "notification"

    # ── Clés étrangères ───────────────────────────────────────────────────────
    recipient_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("account.id", ondelete="CASCADE"), nullable=False
    )
    request_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("request.id"), nullable=True
    )

    # ── Attributs métier ──────────────────────────────────────────────────────
    type: Mapped[str] = mapped_column(
        SAEnum("info", "success", "warning", name="notification_type_enum"),
        nullable=False,
        default="info",
    )
    channel: Mapped[str] = mapped_column(
        SAEnum("in_app", "sms", "email", name="notification_channel_enum"),
        nullable=False,
        default="in_app",
    )
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    body: Mapped[str] = mapped_column(Text, nullable=False)
    action_label: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    action_url: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    is_read: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    visibility: Mapped[str] = mapped_column(
        SAEnum("public", "admin_only", name="notification_visibility_enum"),
        nullable=False,
        default="public",
    )

    # ── Dates ─────────────────────────────────────────────────────────────────
    read_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # ── Relations ─────────────────────────────────────────────────────────────
    recipient: Mapped[Account] = relationship(
        "Account", foreign_keys="Notification.recipient_id", lazy="raise"
    )
    request: Mapped[Optional[Request]] = relationship(
        "Request", foreign_keys="Notification.request_id", lazy="raise"
    )

    __table_args__ = (
        Index("idx_notif_recip", "recipient_id"),
        Index("idx_notif_unread", "recipient_id", "is_read"),
        Index("idx_notif_status", "status", "deleted_at"),
        MYSQL_ARGS,
    )
