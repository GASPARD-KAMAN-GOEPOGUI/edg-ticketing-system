from __future__ import annotations

from sqlalchemy import Boolean, Enum as SAEnum, Index, SmallInteger, String, Text

from .base import Base, BaseColumns, MYSQL_ARGS
from sqlalchemy.orm import Mapped, mapped_column


class PriorityDefinition(Base, BaseColumns):
    """
    Priorités des demandes uniquement. Utilise 'slug' comme identifiant fonctionnel
    (au lieu de 'code') pour souligner sa nature sémantique.
    Pilote les SLA, les escalades automatiques et les badges frontend.
    """

    __tablename__ = "priority_definition"

    slug: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False, default="")
    color: Mapped[str] = mapped_column(
        SAEnum("slate", "blue", "teal", "amber", "orange", "red", "purple",
               name="priority_color_enum"),
        nullable=False,
        default="slate",
    )
    sort_order: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    __table_args__ = (
        Index("idx_prio_order", "sort_order"),
        Index("idx_prio_status", "status", "deleted_at"),
        MYSQL_ARGS,
    )
