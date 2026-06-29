from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean, CheckConstraint, Enum as SAEnum, ForeignKey, Index,
    Integer, SmallInteger, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, BaseColumns, MYSQL_ARGS

if TYPE_CHECKING:
    from .ModelRequest import Request


class Appreciation(Base, BaseColumns):
    """Note CSAT — interne ou externe, via lien public ou SMS. Relation 1:1 avec request."""

    __tablename__ = "appreciation"

    request_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("request.id", ondelete="CASCADE"),
        unique=True, nullable=False
    )
    rating: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    resolved_confirmed: Mapped[bool] = mapped_column(Boolean, nullable=False)
    is_modified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    author_type: Mapped[str] = mapped_column(
        SAEnum("internal", "external", name="appreciation_author_enum"),
        nullable=False,
    )

    request: Mapped[Request] = relationship(
        "Request", back_populates="appreciation", lazy="raise"
    )

    __table_args__ = (
        UniqueConstraint("request_id", name="uk_appr_req"),
        CheckConstraint("rating BETWEEN 1 AND 5", name="chk_rating"),
        Index("idx_appr_rating", "rating"),
        Index("idx_appr_status", "status", "deleted_at"),
        MYSQL_ARGS,
    )
