from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, BaseColumns, MYSQL_ARGS

if TYPE_CHECKING:
    from .ModelRequest import Request
    from .ModelWorkflowDetail import WorkflowDetail


class Workflow(Base, BaseColumns):
    __tablename__ = "workflow"

    request_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("request.id"), nullable=False
    )
    workflow_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="active"
    )

    request: Mapped[Request] = relationship(
        "Request", back_populates="workflows", lazy="raise"
    )
    details: Mapped[list[WorkflowDetail]] = relationship(
        "WorkflowDetail",
        back_populates="workflow",
        cascade="all, delete-orphan",
        lazy="selectin",
    )

    __table_args__ = (
        Index("idx_wf_req", "request_id"),
        Index("idx_wf_status", "status", "deleted_at"),
        MYSQL_ARGS,
    )
