from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, BaseColumns, MYSQL_ARGS

if TYPE_CHECKING:
    from .ModelAccount import Account


class CommunicationSetting(Base, BaseColumns):
    """Singleton — une seule ligne représente la configuration globale des canaux de communication."""

    __tablename__ = "communication_setting"

    # ── Clé étrangère (traçabilité) ───────────────────────────────────────────
    updated_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("account.id"), nullable=True
    )

    # ── Attributs métier ──────────────────────────────────────────────────────
    internal_notif_on: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    email_on: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    sms_on: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    banner_on: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    whatsapp_on: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    push_mobile_on: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sender_email: Mapped[str] = mapped_column(
        String(255), nullable=False, default="noreply@edg.gn"
    )
    sender_sms: Mapped[str] = mapped_column(
        String(11), nullable=False, default="EDG"
    )
    reply_to: Mapped[str] = mapped_column(
        String(255), nullable=False, default="support@edg.gn"
    )

    # ── Relations ─────────────────────────────────────────────────────────────
    updated_by_account: Mapped[Optional[Account]] = relationship(
        "Account", foreign_keys="CommunicationSetting.updated_by", lazy="selectin"
    )

    __table_args__ = (
        Index("idx_comms_status", "status", "deleted_at"),
        MYSQL_ARGS,
    )
