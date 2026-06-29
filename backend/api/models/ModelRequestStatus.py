from __future__ import annotations

from sqlalchemy import Index

from .base import Base, BaseRefColumns, MYSQL_ARGS


class RequestStatus(Base, BaseRefColumns):
    __tablename__ = "request_status"

    __table_args__ = (
        Index("idx_rs_order", "sort_order"),
        Index("idx_rs_status", "status", "deleted_at"),
        MYSQL_ARGS,
    )
