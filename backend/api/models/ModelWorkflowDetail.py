from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, BaseColumns, MYSQL_ARGS

if TYPE_CHECKING:
    from .ModelWorkflow import Workflow
    from .ModelUnity import Unity
    from .ModelAccount import Account
    from .ModelTask import Task


class WorkflowDetail(Base, BaseColumns):
    """
    Journal d'audit append-only du workflow.
    Chaque entrée appartient à un Workflow (workflow_id obligatoire).
    La remontée vers la Request se fait via : workflow_detail → workflow → request.

    États de accepted : None = en attente, True = accepté, False = rejeté.
    Le statut global du workflow est porté par Workflow.workflow_status, pas ici.
    """

    __tablename__ = "workflow_detail"

    # ── FK métier ─────────────────────────────────────────────────────────────
    workflow_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("workflow.id"), nullable=True
    )
    unity_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("unity.id"), nullable=True
    )
    agent_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("account.id"), nullable=True
    )
    task_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("task.id"), nullable=True
    )
    parent_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("workflow_detail.id"), nullable=True
    )

    # ── Champs timeline ───────────────────────────────────────────────────────
    event_type: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    label: Mapped[Optional[str]] = mapped_column(String(500), nullable=True)
    actor_name: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)

    # ── État validation (accepted nullable = 3 états) ─────────────────────────
    accepted: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    activated: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # ── Commentaire ───────────────────────────────────────────────────────────
    comment: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Relations ─────────────────────────────────────────────────────────────
    workflow: Mapped[Optional[Workflow]] = relationship(
        "Workflow", back_populates="details", lazy="raise"
    )
    unity: Mapped[Optional[Unity]] = relationship(
        "Unity", foreign_keys="WorkflowDetail.unity_id", lazy="raise"
    )
    agent: Mapped[Optional[Account]] = relationship(
        "Account", foreign_keys="WorkflowDetail.agent_id", lazy="raise"
    )
    task: Mapped[Optional[Task]] = relationship(
        "Task", foreign_keys="WorkflowDetail.task_id", lazy="raise"
    )
    parent: Mapped[Optional[WorkflowDetail]] = relationship(
        "WorkflowDetail",
        back_populates="children",
        remote_side="WorkflowDetail.id",
        foreign_keys="WorkflowDetail.parent_id",
        lazy="raise",
    )
    children: Mapped[list[WorkflowDetail]] = relationship(
        "WorkflowDetail",
        back_populates="parent",
        foreign_keys="WorkflowDetail.parent_id",
        lazy="raise",
    )

    __table_args__ = (
        Index("idx_wfd_wf", "workflow_id"),
        Index("idx_wfd_status", "status", "deleted_at"),
        MYSQL_ARGS,
    )
