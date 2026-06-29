from __future__ import annotations

from sqlalchemy import Index

from .base import Base, BaseRefColumns, MYSQL_ARGS


class AnnouncementStatus(Base, BaseRefColumns):
    """Cycle de vie d'une annonce — administrable sans redéploiement."""

    __tablename__ = "announcement_status"

    __table_args__ = (
        Index("idx_anst_status", "status", "deleted_at"),
        MYSQL_ARGS,
    )
