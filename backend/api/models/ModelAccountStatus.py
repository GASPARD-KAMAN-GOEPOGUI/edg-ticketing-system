from __future__ import annotations

from sqlalchemy import Index

from .base import Base, BaseRefColumns, MYSQL_ARGS


class AccountStatus(Base, BaseRefColumns):
    __tablename__ = "account_status"

    __table_args__ = (
        Index("idx_ast_status", "status", "deleted_at"),
        MYSQL_ARGS,
    )
