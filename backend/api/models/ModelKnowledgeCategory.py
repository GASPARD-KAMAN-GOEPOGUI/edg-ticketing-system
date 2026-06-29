from __future__ import annotations

from sqlalchemy import Index

from .base import Base, BaseRefColumns, MYSQL_ARGS


class KnowledgeCategory(Base, BaseRefColumns):
    """Classification des articles de base de connaissances."""

    __tablename__ = "knowledge_category"

    __table_args__ = (
        Index("idx_kc_order", "sort_order"),
        Index("idx_kc_status", "status", "deleted_at"),
        MYSQL_ARGS,
    )
