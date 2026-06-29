from __future__ import annotations

from sqlalchemy import Index, SmallInteger, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from .base import Base, BaseColumns, MYSQL_ARGS


class SlaPolicy(Base, BaseColumns):
    """Contrainte UNIQUE(category, priority). Référence logique vers request_category et priority_definition."""

    __tablename__ = "sla_policy"

    category: Mapped[str] = mapped_column(String(50), nullable=False)
    priority: Mapped[str] = mapped_column(String(50), nullable=False)
    response_h: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    resolution_h: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    escalate_after_h: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    __table_args__ = (
        UniqueConstraint("category", "priority", name="uk_sla_cat_prio"),
        Index("idx_sla_status", "status", "deleted_at"),
        MYSQL_ARGS,
    )
