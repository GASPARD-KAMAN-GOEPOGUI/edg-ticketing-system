from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Enum as SAEnum, ForeignKey, Index, Integer, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, BaseColumns, MYSQL_ARGS

if TYPE_CHECKING:
    from .ModelAnnouncement import Announcement


class AnnouncementTargetRole(Base, BaseColumns):
    __tablename__ = "announcement_target_role"

    announcement_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("announcement.id", ondelete="CASCADE"), nullable=False
    )
    role: Mapped[str] = mapped_column(
        SAEnum("public", "user", "agent", "chief", "director", "dg", "admin",
               name="ann_target_role_enum"),
        nullable=False,
    )

    announcement: Mapped[Announcement] = relationship(
        "Announcement", back_populates="target_roles", lazy="raise"
    )

    __table_args__ = (
        UniqueConstraint("announcement_id", "role", name="uk_atrole_ann_role"),
        Index("idx_atrole_status", "status", "deleted_at"),
        MYSQL_ARGS,
    )
