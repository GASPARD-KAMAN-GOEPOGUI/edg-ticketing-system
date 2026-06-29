from __future__ import annotations

from sqlalchemy import Index

from .base import Base, BaseRefColumns, MYSQL_ARGS


class AnnouncementPriority(Base, BaseRefColumns):
    """Priorités des annonces (distinct de priority_definition qui concerne les demandes)."""

    __tablename__ = "announcement_priority"

    __table_args__ = (
        Index("idx_ap_order", "sort_order"),
        Index("idx_ap_status", "status", "deleted_at"),
        MYSQL_ARGS,
    )
