from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import (
    Boolean, Double, Enum as SAEnum, ForeignKey,
    Index, Integer, SmallInteger, String, Text, UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, BaseColumns, MYSQL_ARGS

if TYPE_CHECKING:
    from .ModelUnity import Unity
    from .ModelAccount import Account
    from .ModelAttachment import Attachment
    from .ModelWorkflow import Workflow
    from .ModelTask import Task
    from .ModelAppreciation import Appreciation
    from .ModelRequestStatus import RequestStatus
    from .ModelPriorityDefinition import PriorityDefinition
    from .ModelRequestCategory import RequestCategory


class Request(Base, BaseColumns):
    __tablename__ = "request"

    # ── Clés étrangères référentiels ──────────────────────────────────────────
    request_status_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("request_status.id"), nullable=False
    )
    priority_definition_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("priority_definition.id"), nullable=False
    )
    request_category_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("request_category.id"), nullable=False
    )
    request_source: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # ── Clés étrangères métier ────────────────────────────────────────────────
    unity_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("unity.id"), nullable=True
    )
    on_behalf_unity_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("unity.id"), nullable=True
    )
    assignee_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("account.id"), nullable=True
    )
    requester_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("account.id"), nullable=True
    )

    # ── Attributs métier ──────────────────────────────────────────────────────
    ref: Mapped[str] = mapped_column(String(30), unique=True, nullable=False)
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    in_triage: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    is_external: Mapped[bool] = mapped_column(Boolean, nullable=False)
    requester_type: Mapped[Optional[str]] = mapped_column(
        SAEnum("internal", "external", name="requester_type_enum"), nullable=True
    )
    submission_mode: Mapped[str] = mapped_column(
        SAEnum("personal", "on_behalf_of_unit", name="submission_mode_enum"),
        nullable=False,
        default="personal",
    )
    requester_name: Mapped[str] = mapped_column(String(200), nullable=False, default="")
    requester_phone: Mapped[Optional[str]] = mapped_column(String(30), nullable=True)
    requester_email: Mapped[Optional[str]] = mapped_column(String(320), nullable=True)
    requester_address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    meter_number: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    client_ref: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    lat: Mapped[Optional[float]] = mapped_column(Double, nullable=True)
    lng: Mapped[Optional[float]] = mapped_column(Double, nullable=True)
    location_label: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sla_hours: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    sla_elapsed: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    sla_breached: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)

    # ── Fusion de tickets ─────────────────────────────────────────────────────
    merged_into_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("request.id"), nullable=True
    )

    # ── Dates ─────────────────────────────────────────────────────────────────
    sla_response_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    resolved_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    closed_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # ── Relations FK référentiels ─────────────────────────────────────────────
    request_status_ref: Mapped[RequestStatus] = relationship(
        "RequestStatus", foreign_keys=[request_status_id], lazy="selectin"
    )
    priority_definition_ref: Mapped[PriorityDefinition] = relationship(
        "PriorityDefinition", foreign_keys=[priority_definition_id], lazy="selectin"
    )
    request_category_ref: Mapped[RequestCategory] = relationship(
        "RequestCategory", foreign_keys=[request_category_id], lazy="selectin"
    )
    # ── Relations métier ──────────────────────────────────────────────────────
    unity: Mapped[Optional[Unity]] = relationship(
        "Unity", foreign_keys="Request.unity_id", lazy="selectin"
    )
    on_behalf_unity: Mapped[Optional[Unity]] = relationship(
        "Unity", foreign_keys="Request.on_behalf_unity_id", lazy="selectin"
    )
    assignee: Mapped[Optional[Account]] = relationship(
        "Account", foreign_keys="Request.assignee_id", lazy="selectin",
    )
    requester: Mapped[Optional[Account]] = relationship(
        "Account", foreign_keys="Request.requester_id", lazy="selectin",
    )

    attachments: Mapped[list[Attachment]] = relationship(
        "Attachment",
        back_populates="request",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    workflows: Mapped[list[Workflow]] = relationship(
        "Workflow", back_populates="request", lazy="selectin"
    )
    tasks: Mapped[list[Task]] = relationship(
        "Task",
        back_populates="request",
        foreign_keys="Task.request_id",
        lazy="selectin",
    )
    appreciation: Mapped[Optional[Appreciation]] = relationship(
        "Appreciation",
        back_populates="request",
        cascade="all, delete-orphan",
        uselist=False,
        lazy="selectin",
    )

    # ── Propriétés de compatibilité ascendante ────────────────────────────────
    @property
    def request_status(self) -> str:
        return self.request_status_ref.code if self.request_status_ref else ""

    @property
    def priority(self) -> str:
        return self.priority_definition_ref.slug if self.priority_definition_ref else ""

    @property
    def category(self) -> str:
        return self.request_category_ref.code if self.request_category_ref else ""

    @property
    def source(self) -> Optional[str]:
        return self.request_source

    @property
    def direction_id(self) -> Optional[int]:
        """Direction parente déduite depuis l'unité de la demande.
        - Si unity est un service (a un parent_direction_id) → retourne le parent
        - Si unity EST une direction (pas de parent) → retourne son propre id
        """
        if not self.unity:
            return None
        if self.unity.parent_direction_id:
            return self.unity.parent_direction_id
        return self.unity.id

    @property
    def assignee_name(self) -> Optional[str]:
        """Nom complet (prenom + nom) — aligne sur ServiceRequest._account_display_name,
        deja utilise pour les evenements timeline (target_user_name de l'assignation)."""
        if not self.assignee:
            return None
        parts = [p for p in (self.assignee.firstname, self.assignee.name) if p]
        return " ".join(parts) if parts else None

    @property
    def requester_unit_id(self) -> Optional[int]:
        """Unite d'appartenance du demandeur (Account.unity_id), pour affichage
        Direction/Departement/Service du demandeur cote frontend (resolu via la
        liste des unites deja chargee, meme pattern que Request.direction_id)."""
        return self.requester.unity_id if self.requester else None

    @property
    def timelines(self):
        """Aplatit workflows[].details[] en une liste ordonnée pour RequestResponse."""
        result = []
        for wf in sorted(self.workflows or [], key=lambda w: w.id):
            result.extend(wf.details or [])
        return result

    __table_args__ = (
        UniqueConstraint("ref", name="uk_req_ref"),
        Index("idx_req_merged_into", "merged_into_id"),
        Index("idx_req_status_id",       "request_status_id"),
        Index("idx_req_priority_def_id", "priority_definition_id"),
        Index("idx_req_category_id",     "request_category_id"),
        Index("idx_req_source",          "request_source"),
        Index("idx_req_unity",           "unity_id"),
        Index("idx_req_assignee",        "assignee_id"),
        Index("idx_req_created",         "created_at"),
        Index("idx_req_triage",          "in_triage"),
        Index("idx_req_status",          "status", "deleted_at"),
        MYSQL_ARGS,
    )
