from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, Index, Integer, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, BaseColumns, MYSQL_ARGS

if TYPE_CHECKING:
    from .ModelUnity import Unity


class RoutingRule(Base, BaseColumns):
    """
    condition_value doit respecter une contrainte polymorphe selon condition_field :
    'category' → request_category.code · 'priority' → priority_definition.slug
    'source' → request_source.code · 'keyword' → texte libre.
    Validé applicativement, non enforçable par FK MySQL.
    """

    __tablename__ = "routing_rule"

    # ── Clé étrangère ─────────────────────────────────────────────────────────
    target_unity_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("unity.id"), nullable=True
    )

    # ── Attributs métier ──────────────────────────────────────────────────────
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    condition_field: Mapped[str] = mapped_column(
        SAEnum("category", "priority", "source", "keyword",
               name="routing_condition_enum"),
        nullable=False,
    )
    condition_value: Mapped[str] = mapped_column(Text, nullable=False)
    auto_assign: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    sort_order: Mapped[int] = mapped_column(SmallInteger, nullable=False)

    # ── Relations ─────────────────────────────────────────────────────────────
    target_unity: Mapped[Optional[Unity]] = relationship(
        "Unity", foreign_keys="RoutingRule.target_unity_id", lazy="selectin"
    )

    @property
    def target_unity_codename(self) -> Optional[str]:
        return self.target_unity.codename if self.target_unity else None

    @property
    def target_unity_label(self) -> Optional[str]:
        return self.target_unity.label if self.target_unity else None

    @property
    def target_unity_direction_id(self) -> Optional[str]:
        if self.target_unity and self.target_unity.parent_direction_id:
            return str(self.target_unity.parent_direction_id)
        return None

    __table_args__ = (
        Index("idx_rr_order", "sort_order"),
        Index("idx_rr_status", "status", "deleted_at"),
        MYSQL_ARGS,
    )
