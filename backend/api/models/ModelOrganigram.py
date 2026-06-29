from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, BaseColumns, MYSQL_ARGS

if TYPE_CHECKING:
    from .ModelUnity import Unity


class Organigram(Base, BaseColumns):
    """
    Nœud de l'organigramme : positionne une Unity dans la hiérarchie.
    unity_id  → quelle entité organisationnelle est à ce nœud.
    parent_id → nœud parent (NULL = racine de son arbre).
    Un nœud racine sans parent représente une Direction (niveau 1).
    """

    __tablename__ = "organigram"

    unity_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("unity.id"), nullable=False
    )
    parent_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("organigram.id", ondelete="SET NULL"), nullable=True
    )

    # ── Relations ─────────────────────────────────────────────────────────────
    unity: Mapped[Unity] = relationship(
        "Unity", back_populates="organigrams", lazy="selectin"
    )
    parent: Mapped[Optional[Organigram]] = relationship(
        "Organigram",
        back_populates="children",
        remote_side="Organigram.id",
        foreign_keys="Organigram.parent_id",
        lazy="raise",
    )
    children: Mapped[list[Organigram]] = relationship(
        "Organigram",
        back_populates="parent",
        foreign_keys="Organigram.parent_id",
        lazy="raise",
    )

    __table_args__ = (
        Index("idx_org_unity", "unity_id"),
        Index("idx_org_parent", "parent_id"),
        Index("idx_org_status", "status", "deleted_at"),
        MYSQL_ARGS,
    )
