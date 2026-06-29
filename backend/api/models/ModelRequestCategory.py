from __future__ import annotations

from sqlalchemy import Index

from .base import Base, BaseRefColumns, MYSQL_ARGS


class RequestCategory(Base, BaseRefColumns):
    """Classification des demandes. Pilote le routage automatique, les SLA et les rapports."""

    __tablename__ = "request_category"

    __table_args__ = (
        Index("idx_rc_order", "sort_order"),
        Index("idx_rc_status", "status", "deleted_at"),
        MYSQL_ARGS,
    )
