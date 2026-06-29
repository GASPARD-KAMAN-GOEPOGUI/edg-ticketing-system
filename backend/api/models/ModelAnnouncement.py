from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import DateTime, Enum as SAEnum, ForeignKey, Index, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, BaseColumns, MYSQL_ARGS

if TYPE_CHECKING:
    from .ModelAccount import Account
    from .ModelAnnouncementTargetRole import AnnouncementTargetRole
    from .ModelAnnouncementCategory import AnnouncementCategory
    from .ModelAnnouncementPriority import AnnouncementPriority
    from .ModelAnnouncementStatus import AnnouncementStatus


class Announcement(Base, BaseColumns):
    __tablename__ = "announcement"

    # ── Clés étrangères ───────────────────────────────────────────────────────
    announcement_category_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("announcement_category.id"), nullable=False
    )
    announcement_priority_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("announcement_priority.id"), nullable=False
    )
    announcement_status_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("announcement_status.id"), nullable=False
    )
    author_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("account.id"), nullable=False
    )

    # ── Attributs métier ──────────────────────────────────────────────────────
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    audience: Mapped[str] = mapped_column(
        SAEnum("internal", "external", "all", "unit", name="announcement_audience_enum"),
        nullable=False,
        default="internal",
    )
    attachment_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    visibility: Mapped[str] = mapped_column(
        SAEnum("public", "admin_only", name="announcement_visibility_enum"),
        nullable=False,
        default="public",
    )

    # ── Dates ─────────────────────────────────────────────────────────────────
    published_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    expires_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # ── Relations FK référentiels ─────────────────────────────────────────────
    announcement_category_ref: Mapped[AnnouncementCategory] = relationship(
        "AnnouncementCategory",
        foreign_keys=[announcement_category_id],
        lazy="selectin",
    )
    announcement_priority_ref: Mapped[AnnouncementPriority] = relationship(
        "AnnouncementPriority",
        foreign_keys=[announcement_priority_id],
        lazy="selectin",
    )
    announcement_status_ref: Mapped[AnnouncementStatus] = relationship(
        "AnnouncementStatus",
        foreign_keys=[announcement_status_id],
        lazy="selectin",
    )

    # ── Relations métier ──────────────────────────────────────────────────────
    author: Mapped[Account] = relationship(
        "Account", foreign_keys="Announcement.author_id", lazy="raise"
    )
    target_roles: Mapped[list[AnnouncementTargetRole]] = relationship(
        "AnnouncementTargetRole",
        back_populates="announcement",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    # ── Propriétés de compatibilité ascendante ────────────────────────────────
    @property
    def announcement_category(self) -> str:
        return self.announcement_category_ref.code if self.announcement_category_ref else ""

    @property
    def announcement_priority(self) -> str:
        return self.announcement_priority_ref.code if self.announcement_priority_ref else ""

    @property
    def announcement_status(self) -> str:
        return self.announcement_status_ref.code if self.announcement_status_ref else ""

    __table_args__ = (
        Index("idx_ann_cat_id",    "announcement_category_id"),
        Index("idx_ann_prio_id",   "announcement_priority_id"),
        Index("idx_ann_status_id", "announcement_status_id"),
        Index("idx_ann_status",    "status", "deleted_at"),
        MYSQL_ARGS,
    )
