from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any, Optional

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

    @property
    def reopen_count(self) -> int:
        """BR-SLA-REOPEN-001 — nombre de réouvertures approuvées (événements `reopened`)."""
        return sum(1 for e in self.timelines if e.event_type == "reopened")

    @property
    def sla_cycles(self) -> list[dict[str, Any]]:
        """
        BR-SLA-REOPEN-001 — reconstruit l'historique des cycles SLA depuis
        `timelines` (workflow_detail, append-only), sans nouvelle table ni colonne :
        un cycle clos par résolution (`treatment_completed`, instantané gelé dans
        `infos` par `ServiceRequest._sla_cycle_snapshot`), une réouverture
        (`reopened`) démarrant le cycle suivant. Le cycle courant (non encore
        résolu) est ajouté en fin de liste s'il existe, calculé en direct depuis
        les compteurs "live" (`sla_hours`/`sla_breached`) — jamais persisté ici.
        Le premier cycle n'est jamais recalculé : une fois clos, ses valeurs
        proviennent uniquement de l'événement `treatment_completed` d'origine.
        """
        events = sorted(
            (e for e in self.timelines if e.created_at is not None),
            key=lambda e: e.created_at,
        )
        cycles: list[dict[str, Any]] = []
        # Suivi du cycle courant (non encore clos), pour le cas où le ticket est
        # toujours en traitement — uniquement recalculé en direct pour CE cycle,
        # jamais pour un cycle déjà clos (voir bloc `treatment_completed` ci-dessous).
        started_at = self.created_at
        reopen_reason: Optional[str] = None
        for event in events:
            if event.event_type == "treatment_completed":
                # Cycle clos : toutes les valeurs proviennent exclusivement de
                # l'instantané gelé dans `infos` au moment de la résolution — jamais
                # recalculées depuis un nouveau parcours des événements (robuste à
                # tout événement enregistré hors-ordre après coup, ex. horloge système).
                infos = event.infos or {}
                cycles.append({
                    "cycle_number": infos.get("sla_cycle_number") or (len(cycles) + 1),
                    "started_at": infos.get("sla_cycle_started_at", started_at),
                    "ended_at": event.created_at,
                    "sla_hours": infos.get("sla_hours_target"),
                    "elapsed_hours": infos.get("sla_elapsed_hours"),
                    "response_hours": infos.get("sla_response_hours"),
                    "breached": infos.get("sla_breached"),
                    "resolved_by": event.actor_name,
                    "reopen_reason": infos.get("sla_reopen_reason"),
                    "closed": True,
                })
            elif event.event_type == "reopened":
                started_at = event.created_at
                reopen_reason = event.comment or (event.infos or {}).get("reopen_reason")

        # Cycle courant non clos : le nombre de cycles clos doit être exactement
        # reopen_count + 1 (cycle initial + un par réouverture) tant que le
        # ticket est de nouveau résolu après chaque réouverture ; s'il en manque
        # un, le ticket est encore en traitement sur son cycle le plus récent.
        if len(cycles) < self.reopen_count + 1:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            elapsed_hours = (
                round((now - started_at).total_seconds() / 3600, 2) if started_at else None
            )
            cycles.append({
                "cycle_number": len(cycles) + 1,
                "started_at": started_at,
                "ended_at": None,
                "sla_hours": self.sla_hours or None,
                "elapsed_hours": elapsed_hours,
                "response_hours": None,
                "breached": self.sla_breached,
                "resolved_by": None,
                "reopen_reason": reopen_reason,
                "closed": False,
            })
        return cycles

    @property
    def interventions(self) -> list[dict[str, Any]]:
        """
        BR-TRACE-001 — reconstruit la liste des interventions (conteneur logique
        du travail complet d'un intervenant : commentaires, pièces jointes,
        travail effectué, décision) depuis les métadonnées explicitement
        enregistrées sur chaque événement (`infos.intervention_id`/
        `intervention_order`/`intervention_cycle_number`) — jamais recalculées,
        jamais dérivées par comptage. Chaque intervention garde le detail de ses
        propres événements via `event_ids` (déjà présents dans `timelines`).
        """
        events = sorted(
            (e for e in self.timelines if e.created_at is not None),
            key=lambda e: e.created_at,
        )
        order: list[str] = []
        by_id: dict[str, dict[str, Any]] = {}

        def _ensure(intervention_id: str, seed: dict[str, Any]) -> dict[str, Any]:
            bucket = by_id.get(intervention_id)
            if bucket is None:
                bucket = {
                    "intervention_id": intervention_id,
                    "cycle_number": seed.get("cycle_number") or 1,
                    "intervention_order": seed.get("intervention_order"),
                    "actor_id": seed.get("actor_id"),
                    "actor_name": seed.get("actor_name"),
                    "actor_role": seed.get("actor_role"),
                    "actor_matricule": seed.get("actor_matricule"),
                    "actor_direction_label": seed.get("actor_direction_label"),
                    "actor_department_label": seed.get("actor_department_label"),
                    "actor_service_label": seed.get("actor_service_label"),
                    "started_at": seed.get("started_at"),
                    "ended_at": None,
                    "duration_seconds": None,
                    "work_done": None,
                    "instruction": None,
                    "transmission_reason": None,
                    "decision": None,
                    "destination_id": None,
                    "destination_name": None,
                    "summary": None,
                    "solution": None,
                    "recommendations": None,
                    "sla_hours": None,
                    "sla_breached": None,
                    "comment_count": 0,
                    "attachment_count": 0,
                    "event_ids": [],
                }
                by_id[intervention_id] = bucket
                order.append(intervention_id)
            return bucket

        for event in events:
            infos = event.infos or {}
            intervention_id = infos.get("intervention_id")

            # Transmission : pré-amorce l'intervention du destinataire (aucun
            # événement `assigned` séparé n'existe pour la marquer autrement).
            next_iv = infos.get("next_intervention")
            if isinstance(next_iv, dict) and next_iv.get("intervention_id"):
                _ensure(next_iv["intervention_id"], {
                    "cycle_number": next_iv.get("intervention_cycle_number"),
                    "intervention_order": next_iv.get("intervention_order"),
                    "actor_id": infos.get("target_user_id"),
                    "actor_name": infos.get("target_user_name"),
                    "actor_role": infos.get("target_role") or infos.get("dest_role"),
                    "actor_matricule": next_iv.get("actor_matricule"),
                    "actor_direction_label": next_iv.get("actor_direction_label"),
                    "actor_department_label": next_iv.get("actor_department_label"),
                    "actor_service_label": next_iv.get("actor_service_label"),
                    "started_at": next_iv.get("started_at"),
                })

            if not intervention_id:
                continue  # événement hors conteneur (création, qualification, message du demandeur…)

            bucket = _ensure(intervention_id, {
                "cycle_number": infos.get("intervention_cycle_number"),
                "intervention_order": infos.get("intervention_order"),
                # Le titulaire de l'intervention peut différer de l'acteur qui écrit
                # l'événement (ex. un chef qui assigne un agent) — `intervention_actor_*`
                # (figé par `_actor_identity_snapshot` au nom de l'assigné) prime sur les
                # colonnes `agent_id`/`actor_name` de l'événement lui-même.
                "actor_id": infos.get("intervention_actor_id") or event.agent_id,
                "actor_name": infos.get("intervention_actor_name") or event.actor_name,
                "actor_role": infos.get("intervention_actor_role"),
                "actor_matricule": infos.get("actor_matricule"),
                "actor_direction_label": infos.get("actor_direction_label"),
                "actor_department_label": infos.get("actor_department_label"),
                "actor_service_label": infos.get("actor_service_label"),
                "started_at": event.created_at,
            })
            bucket["event_ids"].append(event.id)

            if event.event_type == "comment_added":
                bucket["comment_count"] += 1
            elif event.event_type == "attachment_added":
                bucket["attachment_count"] += 1
            elif event.event_type == "treatment_transmitted":
                bucket["decision"] = "transmission"
                bucket["work_done"] = infos.get("work_done")
                bucket["transmission_reason"] = infos.get("reason")
                bucket["instruction"] = infos.get("instruction")
                bucket["destination_id"] = infos.get("target_user_id")
                bucket["destination_name"] = infos.get("target_user_name")
                bucket["started_at"] = infos.get("started_at") or bucket["started_at"]
                bucket["ended_at"] = infos.get("ended_at")
                bucket["duration_seconds"] = infos.get("duration_seconds")
            elif event.event_type == "treatment_completed":
                bucket["decision"] = "resolution"
                bucket["work_done"] = infos.get("work_done")
                bucket["summary"] = infos.get("summary")
                bucket["solution"] = infos.get("solution")
                bucket["recommendations"] = infos.get("recommendations")
                bucket["started_at"] = infos.get("started_at") or bucket["started_at"]
                bucket["ended_at"] = infos.get("ended_at")
                bucket["duration_seconds"] = infos.get("duration_seconds")
                bucket["sla_hours"] = infos.get("sla_hours_target")
                bucket["sla_breached"] = infos.get("sla_breached")

        return [by_id[i] for i in order]

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
