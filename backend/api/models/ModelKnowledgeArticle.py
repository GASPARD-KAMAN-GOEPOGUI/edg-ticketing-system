from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, DateTime, ForeignKey, Index, Integer, JSON, SmallInteger, String, Text
from sqlalchemy.dialects.mysql import LONGTEXT
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, BaseColumns, MYSQL_ARGS

if TYPE_CHECKING:
    from .ModelAccount import Account


class KnowledgeArticle(Base, BaseColumns):
    """category est une référence logique vers knowledge_category.code."""

    __tablename__ = "knowledge_article"

    # ── Clé étrangère ─────────────────────────────────────────────────────────
    author_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("account.id"), nullable=True
    )

    # ── Attributs métier ──────────────────────────────────────────────────────
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    excerpt: Mapped[str] = mapped_column(Text, nullable=False)
    body: Mapped[str] = mapped_column(LONGTEXT, nullable=False)
    category: Mapped[str] = mapped_column(String(50), nullable=False)
    read_time: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=3)
    author: Mapped[str] = mapped_column(String(200), nullable=False)
    is_published: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_archived: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    tags: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)

    # ── Dates ─────────────────────────────────────────────────────────────────
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)

    # ── Relations ─────────────────────────────────────────────────────────────
    author_account: Mapped[Optional[Account]] = relationship(
        "Account", foreign_keys="KnowledgeArticle.author_id", lazy="raise"
    )

    __table_args__ = (
        Index("idx_kb_cat", "category"),
        Index("idx_kb_pub", "is_published"),
        Index("idx_kb_status", "status", "deleted_at"),
        MYSQL_ARGS,
    )
