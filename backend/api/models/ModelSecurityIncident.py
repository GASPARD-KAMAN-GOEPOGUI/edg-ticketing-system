from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, BaseColumns, MYSQL_ARGS

if TYPE_CHECKING:
    from .ModelAccount import Account


class SecurityIncident(Base, BaseColumns):
    """
    Journal des tentatives d'accès non autorisées sur l'interface admin.
    Créé automatiquement quand la caméra capture une photo après 2+ échecs de connexion.
    """

    __tablename__ = "security_incident"

    # ── Clé étrangère (traçabilité) ───────────────────────────────────────────
    resolved_by: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("account.id"), nullable=True
    )

    # ── Attributs métier ──────────────────────────────────────────────────────
    email_attempted: Mapped[Optional[str]] = mapped_column(String(320), nullable=True)
    ip_address: Mapped[Optional[str]] = mapped_column(String(45), nullable=True)
    user_agent: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    browser: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    os_info: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    device_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    location_approx: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    photo_path: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    occurred_at: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    resolved: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    notes: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Dates ─────────────────────────────────────────────────────────────────
    resolved_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # ── Relations ─────────────────────────────────────────────────────────────
    resolver: Mapped[Optional[Account]] = relationship(
        "Account", foreign_keys="SecurityIncident.resolved_by", lazy="raise"
    )

    __table_args__ = (
        Index("idx_sec_inc_resolved", "resolved"),
        Index("idx_sec_inc_email", "email_attempted"),
        Index("idx_sec_inc_created", "created_at"),
        Index("idx_sec_inc_status", "status", "deleted_at"),
        MYSQL_ARGS,
    )
