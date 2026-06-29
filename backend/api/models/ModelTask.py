from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, BaseColumns, MYSQL_ARGS

if TYPE_CHECKING:
    from .ModelRequest import Request
    from .ModelAccount import Account
    from .ModelUnity import Unity


class Task(Base, BaseColumns):
    """
    La relation task ↔ workflow est portée par workflow_detail.task_id
    (pas de référence circulaire — task n'a pas de workflow_id FK).
    """

    __tablename__ = "task"

    # ── Clés étrangères ───────────────────────────────────────────────────────
    request_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("request.id"), nullable=False
    )
    from_agent_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("account.id"), nullable=True
    )
    to_agent_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("account.id"), nullable=True
    )
    from_unit_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("unity.id"), nullable=True
    )
    to_unit_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("unity.id"), nullable=True
    )

    # ── Attributs métier ──────────────────────────────────────────────────────
    task_type: Mapped[str] = mapped_column(String(50), nullable=False)
    reason: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    task_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="pending"
    )

    # ── Relations ─────────────────────────────────────────────────────────────
    request: Mapped[Request] = relationship(
        "Request",
        back_populates="tasks",
        foreign_keys="Task.request_id",
        lazy="raise",
    )
    from_agent: Mapped[Optional[Account]] = relationship(
        "Account", foreign_keys="Task.from_agent_id", lazy="raise"
    )
    to_agent: Mapped[Optional[Account]] = relationship(
        "Account", foreign_keys="Task.to_agent_id", lazy="raise"
    )
    from_unit: Mapped[Optional[Unity]] = relationship(
        "Unity", foreign_keys="Task.from_unit_id", lazy="raise"
    )
    to_unit: Mapped[Optional[Unity]] = relationship(
        "Unity", foreign_keys="Task.to_unit_id", lazy="raise"
    )

    __table_args__ = (
        Index("idx_task_req", "request_id"),
        Index("idx_task_tstatus", "task_status"),
        Index("idx_task_status", "status", "deleted_at"),
        MYSQL_ARGS,
    )
