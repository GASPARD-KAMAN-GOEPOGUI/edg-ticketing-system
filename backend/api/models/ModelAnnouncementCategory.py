from __future__ import annotations

from sqlalchemy import Index

from .base import Base, BaseRefColumns, MYSQL_ARGS


class AnnouncementCategory(Base, BaseRefColumns):
    __tablename__ = "announcement_category"

    __table_args__ = (
        Index("idx_ac_status", "status", "deleted_at"),
        MYSQL_ARGS,
    )
