from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, BaseColumns, MYSQL_ARGS

if TYPE_CHECKING:
    from .ModelOrganigram import Organigram
    from .ModelAccount import Account


class Unity(Base, BaseColumns):
    """
    Unité organisationnelle (Direction, Département, Service, Cabinet…).
    L'identité de l'entité. La position dans la hiérarchie est portée par Organigram.
    codename           : code court unique (ex : DSI, DSI-DEV, DSI-SUPPORT).
    aleas              : alias / abréviation affichée sur les badges.
    parent_direction_id: direction parente (ex : DSI rattachée à DG). Purement organisationnel.
    """

    __tablename__ = "unity"

    label: Mapped[str] = mapped_column(String(200), nullable=False)
    codename: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    aleas: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    parent_direction_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("unity.id", ondelete="SET NULL"), nullable=True
    )

    # ── Relations ─────────────────────────────────────────────────────────────
    organigrams: Mapped[list[Organigram]] = relationship(
        "Organigram",
        back_populates="unity",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    accounts: Mapped[list[Account]] = relationship(
        "Account",
        back_populates="unity",
        foreign_keys="Account.unity_id",
        lazy="raise",
    )

    __table_args__ = (
        Index("idx_unity_codename", "codename"),
        Index("idx_unity_status", "status", "deleted_at"),
        Index("idx_unity_parent_dir", "parent_direction_id"),
        MYSQL_ARGS,
    )
