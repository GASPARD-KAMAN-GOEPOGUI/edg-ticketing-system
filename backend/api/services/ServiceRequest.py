from __future__ import annotations

import re
import unicodedata
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy import true as sql_true
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload

from api.core.exceptions import ConflictException
from api.core.error_codes import ErrorCode
from api.core.event_bus import AppEvent, emit as emit_event
from api.core.ticket_actions import (
    BYPASS_TRANSITION_ROLES as _BYPASS_ROLES,
    TERMINAL_STATUSES,
    assert_assignment_allowed,
    assert_action_allowed,
    assert_role_specific_action_constraints,
    assert_service_reassignment_allowed,
    assert_ticket_scope,
    assert_transition_allowed,
    normalize_status,
)
from api.models.ModelAccount import Account
from api.models.ModelPriorityDefinition import PriorityDefinition
from api.models.ModelRequest import Request as RequestModel
from api.models.ModelRequestCategory import RequestCategory
from api.models.ModelRequestStatus import RequestStatus
from api.models.ModelUnity import Unity
from api.models.ModelWorkflow import Workflow
from api.repositories import RequestRepository, WorkflowDetailRepository
from api.schemas.SchemaRequest import RequestResponse, RequestListItemResponse
from api.services.base_service import BaseService
from api.services.NotificationEmitter import emit as emit_notif
from api.services.ServiceCrypto import decrypt_field

# Mapping statut → event_type spécifique (CDC §7 + §8)
_STATUS_EVENT_MAP: dict[str, str] = {
    "qualifying":   "qualifying",
    "qualified":    "qualified",
    "assigned":     "assigned",
    "in_progress":  "in_progress",
    "rejected":     "rejected",
    "pending":      "pending",
    "escalated":    "escalated",
}
_STATUS_LABEL_MAP: dict[str, str] = {
    "qualifying":   "Ticket en cours de qualification",
    "qualified":    "Ticket qualifié",
    "assigned":     "Ticket assigné à un agent",
    "in_progress":  "Prise en charge — traitement en cours",
    "rejected":     "Ticket rejeté",
    "pending":      "Ticket en attente",
    "escalated":    "Ticket escaladé",
}


class RequestService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.repo = RequestRepository(session)
        self.detail_repo = WorkflowDetailRepository(session)

    async def _guard_ticket_action(
        self,
        id: str,
        action: str,
        *,
        target_status: Optional[str] = None,
        actor=None,
        actor_role: Optional[str] = None,
    ):
        obj = await self.get_by_id(id)
        effective_role = str(getattr(actor, "role", actor_role or "") or "")
        if effective_role:
            assert_action_allowed(effective_role, action)
        if actor is not None:
            allowed_dir_unity_ids = None
            if effective_role.strip().lower() in {"agent", "chief", "director"}:
                allowed_dir_unity_ids = await self._direction_unity_ids(getattr(actor, "unity_id", None))
            assert_ticket_scope(actor, obj, action=action, allowed_dir_unity_ids=allowed_dir_unity_ids)
            assert_role_specific_action_constraints(actor, obj, action)
        if target_status is not None:
            assert_transition_allowed(
                obj.request_status,
                target_status,
                actor_role=effective_role or None,
            )
        return obj

    # ── Helper : traduit codes string → IDs FK ────────────────────────────────

    async def _translate_codes(self, data: dict) -> dict:
        out = dict(data)
        if "request_status" in out:
            code = out.pop("request_status")
            if code is not None:
                code = normalize_status(code)
                r = await self.session.execute(
                    select(RequestStatus.id)
                    .where(RequestStatus.code == code)
                    .where(RequestStatus.deleted_at.is_(None))
                )
                status_id = r.scalar_one_or_none()
                if status_id is None:
                    # Fallback vers "new" si le code demandé n'existe pas
                    r2 = await self.session.execute(
                        select(RequestStatus.id)
                        .where(RequestStatus.code == "new")
                        .where(RequestStatus.deleted_at.is_(None))
                    )
                    status_id = r2.scalar_one_or_none()
                if status_id is not None:
                    out["request_status_id"] = status_id
        if "category" in out:
            code = out.pop("category")
            if code is not None:
                # Cherche par code exact (insensible à la casse), puis fallback "autre"
                r = await self.session.execute(
                    select(RequestCategory.id)
                    .where(RequestCategory.code == code.lower())
                    .where(RequestCategory.deleted_at.is_(None))
                )
                cat_id = r.scalar_one_or_none()
                if cat_id is None:
                    r2 = await self.session.execute(
                        select(RequestCategory.id)
                        .where(RequestCategory.code == "autre")
                        .where(RequestCategory.deleted_at.is_(None))
                    )
                    cat_id = r2.scalar_one_or_none()
                if cat_id is not None:
                    out["request_category_id"] = cat_id
        if "priority" in out:
            slug = out.pop("priority")
            if slug is not None:
                r = await self.session.execute(
                    select(PriorityDefinition.id)
                    .where(PriorityDefinition.slug == slug)
                    .where(PriorityDefinition.deleted_at.is_(None))
                )
                prio_id = r.scalar_one_or_none()
                if prio_id is None:
                    # Fallback vers "medium" si le slug demandé n'existe pas
                    r2 = await self.session.execute(
                        select(PriorityDefinition.id)
                        .where(PriorityDefinition.slug == "medium")
                        .where(PriorityDefinition.deleted_at.is_(None))
                    )
                    prio_id = r2.scalar_one_or_none()
                if prio_id is not None:
                    out["priority_definition_id"] = prio_id
        if "source" in out:
            out["request_source"] = out.pop("source")
        if "direction_id" in out:
            # direction_id n'est pas une vraie colonne (propriété calculée) — une direction
            # est elle-même une Unity racine, donc on la retient comme unity_id UNIQUEMENT
            # si aucun service plus précis n'a déjà été fourni. Le ticket reste orienté via
            # le routage automatique (routing_rule) ou la file de triage (in_triage), cette
            # traduction ne fait que conserver la suggestion de direction au lieu de la perdre.
            dir_id = out.pop("direction_id")
            if dir_id is not None and not out.get("unity_id"):
                out["unity_id"] = dir_id
        return out

    # ── Helper : workflow ─────────────────────────────────────────────────────

    async def _get_or_create_workflow(self, request_id: int) -> int:
        """Retourne l'ID du Workflow actif de la demande ; en crée un si absent."""
        row = await self.session.execute(
            select(Workflow.id)
            .where(Workflow.request_id == request_id)
            .where(Workflow.deleted_at.is_(None))
            .order_by(Workflow.id.desc())
            .limit(1)
        )
        wf_id = row.scalar_one_or_none()
        if wf_id is not None:
            return wf_id
        wf = Workflow(request_id=request_id, workflow_status="active")
        self.session.add(wf)
        await self.session.flush()
        return wf.id

    @staticmethod
    def _account_display_name(account_or_name=None, firstname: Optional[str] = None) -> Optional[str]:
        """Nom lisible stable pour la timeline, sans exposer de logique UI."""
        if account_or_name is None and not firstname:
            return None
        if isinstance(account_or_name, str):
            name = account_or_name
        else:
            name = getattr(account_or_name, "name", None)
            firstname = getattr(account_or_name, "firstname", firstname)
        parts = [p for p in (firstname, name) if p]
        return " ".join(parts) if parts else None

    @staticmethod
    def _clean_infos(infos: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in infos.items() if v is not None}

    @staticmethod
    def _reference_part(value: str | None, fallback: str) -> str:
        raw = value or fallback
        ascii_value = unicodedata.normalize("NFKD", raw).encode("ascii", "ignore").decode("ascii")
        compact = re.sub(r"[^A-Za-z0-9]", "", ascii_value).upper()
        return (compact or fallback.upper()).ljust(3, "X")[:3]

    @staticmethod
    def _unity_ref_source(unity: Unity | None, *, prefer_tail: bool = False) -> str | None:
        if unity is None:
            return None
        if unity.aleas:
            return unity.aleas
        if unity.codename:
            if prefer_tail:
                parts = [p for p in re.split(r"[-_\s]+", unity.codename) if p]
                return parts[-1] if parts else unity.codename
            return unity.codename
        return unity.label

    async def _ref_unity_by_id(self, unity_id: Any) -> Unity | None:
        if unity_id is None:
            return None
        try:
            normalized_id = int(unity_id)
        except (TypeError, ValueError):
            return None
        row = await self.session.execute(
            select(Unity)
            .where(Unity.id == normalized_id)
            .where(Unity.deleted_at.is_(None))
            .limit(1)
        )
        return row.scalar_one_or_none()

    async def _requester_ref_unities(self, data: dict) -> tuple[Unity | None, Unity | None]:
        requester_unity: Unity | None = None
        requester_id = data.get("requester_id")
        if requester_id is not None:
            try:
                requester_id_int = int(requester_id)
            except (TypeError, ValueError):
                requester_id_int = 0
            if requester_id_int:
                row = await self.session.execute(
                    select(Account.unity_id)
                    .where(Account.id == requester_id_int)
                    .where(Account.deleted_at.is_(None))
                    .limit(1)
                )
                requester_unity = await self._ref_unity_by_id(row.scalar_one_or_none())

        unit = (
            requester_unity
            or await self._ref_unity_by_id(data.get("on_behalf_unity_id"))
            or await self._ref_unity_by_id(data.get("unity_id"))
            or await self._ref_unity_by_id(data.get("direction_id"))
        )
        direction = await self._ref_unity_by_id(unit.parent_direction_id) if unit and unit.parent_direction_id else unit
        return direction, unit

    async def _build_reference_base(self, data: dict, submitted_at: datetime) -> str:
        direction, unit = await self._requester_ref_unities(data)
        direction_code = self._reference_part(self._unity_ref_source(direction), "GEN")
        unit_code = self._reference_part(self._unity_ref_source(unit, prefer_tail=True), "UNK")
        stamp = (
            f"{submitted_at:%H%M%S}"
            f"{submitted_at.year % 1000:03d}"
            f"{submitted_at:%m%d}"
        )
        return f"{direction_code}-{unit_code}-{stamp}"

    async def _direction_unity_ids(self, direction_id: int | str | None) -> set[int]:
        """Retourne la direction et ses services via organigramme + parent_direction_id."""
        if direction_id is None:
            return set()
        try:
            root_id = int(direction_id)
        except (TypeError, ValueError):
            return set()

        from api.models.ModelOrganigram import Organigram

        ids: set[int] = {root_id}
        org_row = await self.session.execute(
            select(Organigram.id)
            .where(Organigram.unity_id == root_id, Organigram.deleted_at.is_(None))
            .limit(1)
        )
        org_id = org_row.scalar_one_or_none()
        if org_id:
            child_rows = await self.session.execute(
                select(Organigram.unity_id)
                .where(Organigram.parent_id == org_id, Organigram.deleted_at.is_(None))
            )
            ids.update(int(uid) for (uid,) in child_rows.all() if uid is not None)

        unity_rows = await self.session.execute(
            select(Unity.id)
            .where(Unity.parent_direction_id == root_id, Unity.deleted_at.is_(None))
        )
        ids.update(int(uid) for (uid,) in unity_rows.all() if uid is not None)
        return ids

    # ── Sérialisation ─────────────────────────────────────────────────────────

    @staticmethod
    def _decrypt_schema(schema: RequestResponse) -> RequestResponse:
        updates: dict[str, Any] = {"request_status": normalize_status(schema.request_status)}
        if schema.description and schema.description.startswith("enc:"):
            updates["description"] = decrypt_field(schema.description)
        return schema.copy(update=updates)

    @staticmethod
    def _serialize(items: list) -> list:
        """Convertit les ORM Request en RequestListItemResponse (schéma allégé liste) et déchiffre les champs sensibles."""
        result = []
        for item in items:
            schema = RequestListItemResponse.from_orm(item)
            updates = {"request_status": normalize_status(schema.request_status)}
            if schema.description and schema.description.startswith("enc:"):
                updates["description"] = decrypt_field(schema.description)
            result.append(schema.copy(update=updates))
        return result

    # ── Listes ────────────────────────────────────────────────────────────────

    # RequestListItemResponse ne sérialise ni attachments/tasks (endpoints dédiés)
    # ni timelines/appreciation (réservés à la page détail) — inutile de les
    # charger sur les listes/dashboards (jusqu'à 500 tickets d'un coup).
    _LIST_LOAD_OPTIONS = [
        noload(RequestModel.attachments),
        noload(RequestModel.tasks),
        noload(RequestModel.workflows),
        noload(RequestModel.appreciation),
    ]

    async def list_all(self, *, page: int = 1, limit: int = 20):
        items, total = await self.repo.list(
            order_by="-created_at", page=page, limit=limit,
            load_options=self._LIST_LOAD_OPTIONS,
        )
        return self.paginate(self._serialize(items), total, page, limit)

    async def list_filtered(
        self,
        *,
        request_status: Optional[str] = None,
        exclude_status: Optional[str] = None,
        is_external: Optional[bool] = None,
        direction_id: Optional[str] = None,
        unit_id: Optional[str] = None,
        assignee_id: Optional[str] = None,
        requester_id: Optional[str] = None,
        search: Optional[str] = None,
        sla_breached: Optional[bool] = None,
        in_triage: Optional[bool] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ):
        # Résolution unity_id : unit_id = match exact ; direction_id = direction + tous ses services
        if unit_id is not None:
            effective_unity_id = unit_id
        elif direction_id is not None:
            effective_unity_id = list(await self._direction_unity_ids(direction_id))
        else:
            effective_unity_id = None

        if search:
            items, total = await self.repo.search(
                search,
                filters={
                    k: v for k, v in {
                        "request_status": request_status,
                        "exclude_request_status": exclude_status,
                        "is_external": is_external,
                        "unity_id": effective_unity_id,
                        "assignee_id": assignee_id,
                        "requester_id": requester_id,
                    }.items() if v is not None
                },
                page=page,
                limit=limit,
            )
        else:
            filters: dict[str, Any] = {}
            if request_status is not None:
                filters["request_status"] = request_status
            if exclude_status is not None:
                filters["exclude_request_status"] = exclude_status
            if is_external is not None:
                filters["is_external"] = is_external
            if effective_unity_id is not None:
                filters["unity_id"] = effective_unity_id
            if assignee_id is not None:
                filters["assignee_id"] = assignee_id
            if requester_id is not None:
                filters["requester_id"] = requester_id
            if sla_breached is not None:
                filters["sla_breached"] = sla_breached
            if in_triage is not None:
                filters["in_triage"] = in_triage
            if date_from:
                from datetime import datetime as _dt
                try:
                    filters["date_from"] = _dt.fromisoformat(date_from)
                except ValueError:
                    pass
            if date_to:
                from datetime import datetime as _dt, timedelta as _td
                try:
                    # Inclure tout le jour "date_to" jusqu'à 23:59:59
                    filters["date_to"] = _dt.fromisoformat(date_to).replace(
                        hour=23, minute=59, second=59, microsecond=999999
                    )
                except ValueError:
                    pass

            items, total = await self.repo.list(
                filters=filters or None,
                order_by="-created_at",
                page=page,
                limit=limit,
                load_options=self._LIST_LOAD_OPTIONS,
            )
        return self.paginate(self._serialize(items), total, page, limit)

    async def list_by_status(self, status: str, *, page: int = 1, limit: int = 20):
        items, total = await self.repo.list_by_status(status, page=page, limit=limit)
        return self.paginate(self._serialize(items), total, page, limit)

    async def list_by_assignee(self, assignee_id: str, *, page: int = 1, limit: int = 20):
        items, total = await self.repo.list_by_assignee(assignee_id, page=page, limit=limit)
        return self.paginate(self._serialize(items), total, page, limit)

    async def list_by_direction(self, direction_id: str, *, page: int = 1, limit: int = 20):
        return await self.list_filtered(direction_id=direction_id, page=page, limit=limit)

    async def list_by_requester(self, requester_id: str, *, page: int = 1, limit: int = 20):
        items, total = await self.repo.list_by_requester(requester_id, page=page, limit=limit)
        return self.paginate(self._serialize(items), total, page, limit)

    async def list_pending_triage(self, *, page: int = 1, limit: int = 20):
        items, total = await self.repo.list_pending_triage(page=page, limit=limit)
        return self.paginate(self._serialize(items), total, page, limit)

    async def list_sla_breached(self, *, page: int = 1, limit: int = 20):
        items, total = await self.repo.list_sla_breached(page=page, limit=limit)
        return self.paginate(self._serialize(items), total, page, limit)

    async def list_queue(
        self,
        *,
        direction_id: Optional[str] = None,
        assignee_id: Optional[str] = None,
        unassigned_only: bool = False,
        priority: Optional[str] = None,
        request_status: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ):
        items, total = await self.repo.list_queue(
            direction_id=direction_id,
            assignee_id=assignee_id,
            unassigned_only=unassigned_only,
            priority=priority,
            request_status=request_status,
            search=search,
            page=page,
            limit=limit,
        )
        return self.paginate(self._serialize(items), total, page, limit)

    async def qualify_triage(
        self,
        id: str,
        data: dict,
        *,
        actor_id: Optional[str] = None,
        actor_name: Optional[str] = None,
        actor_role: Optional[str] = None,
        actor=None,
    ):
        """Qualifie une demande de triage : fixe l'unité/catégorie/priorité, in_triage=False.
        Si assignee_id fourni → status=assigned directement (routage vers une personne précise).
        Sinon → status=qualifying (la direction prend en charge).
        """
        patch = {k: v for k, v in data.items() if k in {"category", "priority"}}
        # Map direction_id / unit_id → unity_id (compatibilité frontend)
        if "unit_id" in data:
            patch["unity_id"] = data["unit_id"]
        elif "direction_id" in data:
            patch["unity_id"] = data["direction_id"]
        patch["in_triage"] = False

        assignee_id = data.get("assignee_id")
        if assignee_id:
            patch["assignee_id"] = int(assignee_id)
            patch["request_status"] = "assigned"
        else:
            patch["request_status"] = "qualifying"

        await self._guard_ticket_action(
            id,
            "qualify",
            target_status=patch["request_status"],
            actor=actor,
            actor_role=actor_role,
        )
        return await self.update(
            id,
            patch,
            actor_id=actor_id,
            actor_name=actor_name,
            actor_role=actor_role,
        )

    # ── Lectures unitaires ────────────────────────────────────────────────────

    async def get_by_id(self, id: str, *, include_deleted: bool = False):
        obj = await self.repo.get_by_id(id, include_deleted=include_deleted)
        if obj is None:
            raise self.not_found(
                "Cette demande n'existe pas.",
                error_code=ErrorCode.REQUEST_NOT_FOUND,
                field="id",
                value=id,
            )
        return obj

    async def get_by_ref(self, ref: str):
        obj = await self.repo.find_by_ref(ref)
        if obj is None:
            raise self.not_found(
                f"Aucune demande avec la référence '{ref}'.",
                error_code=ErrorCode.REQUEST_NOT_FOUND,
                field="ref",
                value=ref,
            )
        return obj

    async def track(self, ref: str, email: Optional[str] = None, phone: Optional[str] = None):
        obj = await self.repo.find_by_ref(ref)
        if obj is None:
            raise self.not_found(
                "Aucune demande trouvée pour ces coordonnées.",
                error_code=ErrorCode.REQUEST_NOT_FOUND,
                field="ref",
                value=ref,
            )

        if not email and not phone:
            raise self.not_found(
                "Aucune demande trouvée pour ces coordonnées.",
                error_code=ErrorCode.REQUEST_NOT_FOUND,
                field="ref",
                value=ref,
            )

        # Coordonnées du demandeur : compte interne prioritaire, sinon champs libres
        if obj.requester:
            actual_email = (obj.requester.email or "").strip().lower()
            actual_phone = (obj.requester.phone or "").strip()
        else:
            actual_email = (obj.requester_email or "").strip().lower()
            actual_phone = (obj.requester_phone or "").strip()

        _strip_phone = lambda s: re.sub(r"[\s\-\(\)\.]", "", s)

        credential_ok = False
        if email and actual_email and email.strip().lower() == actual_email:
            credential_ok = True
        if phone and actual_phone and _strip_phone(phone) == _strip_phone(actual_phone):
            credential_ok = True

        if not credential_ok:
            raise self.not_found(
                "Aucune demande trouvée pour ces coordonnées.",
                error_code=ErrorCode.REQUEST_NOT_FOUND,
                field="ref",
                value=ref,
            )

        return obj

    # ── Auto-affectation ──────────────────────────────────────────────────────

    async def _select_auto_assignee(self, unity_id: int) -> Optional[int]:
        """Retourne l'agent disponible le moins chargé dans l'unité cible."""
        # Statuts terminaux — exclus du comptage de charge active
        terminal_result = await self.session.execute(
            select(RequestStatus.id)
            .where(RequestStatus.code.in_(["resolved", "closed", "cancelled", "rejected"]))
            .where(RequestStatus.deleted_at.is_(None))
        )
        terminal_ids = [r[0] for r in terminal_result.fetchall()]

        # Charge active de chaque agent (demandes non terminées assignées)
        load_filter = (
            RequestModel.request_status_id.not_in(terminal_ids)
            if terminal_ids
            else sql_true()
        )
        load_sq = (
            select(RequestModel.assignee_id, func.count().label("cnt"))
            .where(RequestModel.deleted_at.is_(None))
            .where(RequestModel.assignee_id.is_not(None))
            .where(load_filter)
            .group_by(RequestModel.assignee_id)
            .subquery()
        )

        # Agent disponible le moins chargé dans l'unité
        stmt = (
            select(Account.id)
            .outerjoin(load_sq, Account.id == load_sq.c.assignee_id)
            .where(Account.unity_id == unity_id)
            .where(Account.role == "agent")
            .where(Account.account_status == "active")
            .where(or_(Account.availability.is_(None), Account.availability == "available"))
            .where(Account.deleted_at.is_(None))
            .order_by(func.coalesce(load_sq.c.cnt, 0).asc())
            .limit(1)
        )

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _auto_assign(
        self,
        request_id: int,
        unity_id: int,
        *,
        actor_id: Optional[str] = None,
    ) -> None:
        """Affecte la demande à l'agent disponible le moins chargé de l'unité."""
        agent_id = await self._select_auto_assignee(unity_id)
        if agent_id is None:
            return

        current = await self.repo.get_by_id(str(request_id))
        if current is not None:
            assert_transition_allowed(current.request_status, "assigned")

        translated = await self._translate_codes({"request_status": "assigned"})
        await self.repo.update(str(request_id), {
            "assignee_id": agent_id,
            "unity_id": unity_id,
            "in_triage": False,
            **translated,
        })

    # ── Routage automatique ───────────────────────────────────────────────────

    async def _apply_routing(
        self,
        obj,
        wf_id: int,
        *,
        actor_id: Optional[str] = None,
        actor_name: Optional[str] = None,
        raw_description: str = "",
        actor_role: str = "user",
    ) -> bool:
        """
        Évalue les règles de routage et oriente la demande.

        Retourne True si une règle a matché (ROUTED_TO_SERVICE),
        False si aucune règle (ROUTED_TO_SUPPORT / triage).

        Mapping sans nouvelles tables :
          current_holder_id   → request.assignee_id
          current_holder_role → dérivé de assignee.role
          current_service_id  → request.unity_id
          event_status        → workflow_detail.infos["event_status"]
        """
        from api.repositories.RepositoryRoutingRule import RoutingRuleRepository
        from api.repositories.RepositoryAccount import AccountRepository

        rr_repo = RoutingRuleRepository(self.session)
        acc_repo = AccountRepository(self.session)

        matched = await rr_repo.find_matching_rule(
            category=obj.category,
            priority=obj.priority,
            source=obj.request_source,
            title=obj.title,
            description=raw_description,
        )

        if matched and matched.target_unity_id:
            target_unity_id = matched.target_unity_id
            chief = await acc_repo.find_chief_for_unity(target_unity_id)

            # Conflit d'intérêt : le demandeur est lui-même le chef de l'unité cible.
            # On bascule en triage pour éviter l'auto-traitement (biais, traçabilité).
            if chief and str(chief.id) == str(actor_id):
                self._logger.warning(
                    f"Demande {obj.ref} → conflit d'intérêt : requester #{actor_id} "
                    f"est chef de l'unité {target_unity_id} — basculement en triage"
                )
                if actor_id:
                    await emit_notif(
                        self.session,
                        recipient_id=str(actor_id),
                        title="Demande transmise au support général",
                        body=(
                            f"Votre demande {obj.ref} a été transmise au support général "
                            f"car vous êtes responsable du service cible (neutralité garantie)."
                        ),
                        type="info",
                        request_id=str(obj.id),
                        action_label="Suivre ma demande",
                        action_url=f"/app/requests/{obj.id}",
                    )
                # Fall-through au bloc triage ci-dessous
            else:
                auto_assignee_id = (
                    await self._select_auto_assignee(target_unity_id)
                    if matched.auto_assign
                    else None
                )
                assignee_id = auto_assignee_id or (chief.id if chief else None)
                assignee_role = "agent" if auto_assignee_id else "chief"
                event_label = f"Orientation automatique — {matched.name}"
                if auto_assignee_id:
                    event_label = f"{event_label} — auto-assignation agent"

                await self.detail_repo.create_event({
                    "workflow_id": wf_id,
                    "event_type": "routed_to_service",
                    "label": event_label,
                    "actor_name": actor_name,
                    "actor_id": actor_id,
                    "dest_id": assignee_id,
                    "unity_id": target_unity_id,
                    "activated": True,
                    "infos": self._clean_infos({
                        "event_status": "pending_validation",
                        "rule_id": str(matched.id),
                        "rule_name": matched.name,
                        "auto_assign": matched.auto_assign,
                        "auto_assigned": auto_assignee_id is not None,
                        "source_role": actor_role,
                        "actor_role": actor_role,
                        "dest_role": assignee_role,
                        "target_role": assignee_role,
                        "target_user_id": str(assignee_id) if assignee_id else None,
                        "target_user_name": self._account_display_name(chief) if not auto_assignee_id else None,
                        "old_status": getattr(obj, "request_status", None),
                        "new_status": "assigned",
                        "target_unity_id": target_unity_id,
                    }),
                })

                assert_transition_allowed(obj.request_status, "assigned", actor_role=actor_role)
                status_translated = await self._translate_codes({"request_status": "assigned"})
                await self.repo.update(str(obj.id), {
                    "assignee_id": assignee_id,
                    "unity_id": target_unity_id,
                    "in_triage": False,
                    **status_translated,
                })

                if assignee_id:
                    await emit_notif(
                        self.session,
                        recipient_id=str(assignee_id),
                        title="Nouvelle demande assignée" if auto_assignee_id else "Nouvelle demande à traiter",
                        body=(
                            f"La demande {obj.ref} vous a été assignée automatiquement."
                            if auto_assignee_id
                            else f"La demande {obj.ref} a été routée vers votre service."
                        ),
                        type="info",
                        request_id=str(obj.id),
                        action_label="Voir la demande",
                        action_url=f"/app/requests/{obj.id}",
                    )

                await emit_event(AppEvent(
                    type="request.routed",
                    payload={"id": obj.id, "unity_id": target_unity_id, "rule": matched.name},
                    target={"roles": "all"},
                ))
                self._logger.info(f"Demande {obj.ref} routée → unité={target_unity_id} chef={getattr(chief, 'id', None)}")
                return True

        # Aucune règle OU conflit d'intérêt → triage / support général
        support = await acc_repo.find_support_agent()

        await self.detail_repo.create_event({
            "workflow_id": wf_id,
            "event_type": "routed_to_support",
            "label": "Aucune règle de routage — envoi au support général",
            "actor_name": actor_name,
            "actor_id": actor_id,
            "dest_id": support.id if support else None,
            "activated": True,
            "infos": self._clean_infos({
                "event_status": "to_qualify",
                "source_role": actor_role,
                "actor_role": actor_role,
                "dest_role": "support",
                "target_role": "support",
                "target_user_id": str(support.id) if support else None,
                "target_user_name": self._account_display_name(support) if support else None,
                "old_status": getattr(obj, "request_status", None),
                "new_status": "qualifying",
            }),
        })

        assert_transition_allowed(obj.request_status, "qualifying", actor_role=actor_role)
        status_qualifying = await self._translate_codes({"request_status": "qualifying"})
        await self.repo.update(str(obj.id), {
            "assignee_id": support.id if support else None,
            "in_triage": True,
            **status_qualifying,
        })

        if support:
            await emit_notif(
                self.session,
                recipient_id=str(support.id),
                title="Demande à qualifier",
                body=f"La demande {obj.ref} arrive au support général (aucune règle de routage).",
                type="warning",
                request_id=str(obj.id),
                action_label="Qualifier",
                action_url="/app/queue?tab=qualify",
            )

        self._logger.info(f"Demande {obj.ref} → triage (aucune règle matchée)")
        return False

    @staticmethod
    def _should_auto_route(data: dict) -> bool:
        infos = data.get("infos")
        if isinstance(infos, dict) and infos.get("auto_route") is True:
            return True
        return data.get("auto_route") is True

    # ── Créations ─────────────────────────────────────────────────────────────

    async def create(self, data: dict):
        self._logger.info(f"Création demande — catégorie={data.get('category')!r}")

        duplicate = await self.repo.find_duplicate(
            title=data.get("title", ""),
            category=data.get("category", ""),
            requester_id=data.get("requester_id"),
            requester_email=data.get("requester_email"),
            meter_number=data.get("meter_number"),
        )
        if duplicate is not None:
            raise self.conflict(
                f"Une demande identique est déjà en cours de traitement (réf. {duplicate.ref}).",
                error_code=ErrorCode.DUPLICATE_REQUEST,
                field="title",
                hint=(
                    f"Votre demande \"{duplicate.title}\" est déjà enregistrée sous "
                    f"la référence {duplicate.ref} avec le statut "
                    f"\"{duplicate.request_status}\". Consultez son avancement ou "
                    f"contactez votre agent de support."
                ),
            )

        submitted_at = datetime.now(timezone.utc)
        ref_base = await self._build_reference_base(data, submitted_at)
        category_code = data.get("category")
        raw_description = data.get("description", "")

        # SLA — résout sla_hours depuis la politique catégorie+priorité (sla_policy),
        # sauf si déjà fourni explicitement par l'appelant.
        if not data.get("sla_hours"):
            from api.repositories.RepositorySlaPolicy import SlaPolicyRepository
            sla_policy = await SlaPolicyRepository(self.session).find_policy(
                (category_code or "").lower(), data.get("priority", "medium")
            )
            if sla_policy is not None:
                data["sla_hours"] = sla_policy.resolution_h

        obj = None
        workflow_steps: list[dict] = []
        ref = ""
        for attempt in range(25):
            ref = await self.repo.next_ref(ref_base)
            data["ref"] = ref
            translated = await self._translate_codes(data)
            workflow_steps = translated.pop("workflows", None) or []
            try:
                obj = await self.repo.create(translated)
                break
            except ConflictException as exc:
                if exc.error_code != "REF_ALREADY_EXISTS":
                    raise
                self._logger.warning(
                    "Collision référence %s détectée, nouvelle tentative (%s/25)",
                    ref,
                    attempt + 1,
                )
        if obj is None:
            raise self.conflict(
                "Impossible de générer une référence unique pour cette demande.",
                error_code=ErrorCode.REF_ALREADY_EXISTS,
                field="ref",
                value=ref_base,
                hint="Réessayez dans quelques secondes.",
            )
        wf_id = await self._get_or_create_workflow(obj.id)

        # Étape 1 — événement CREATED
        await self.detail_repo.create_event({
            "workflow_id": wf_id,
            "event_type": "created",
            "label": "Demande créée par l'utilisateur",
            "actor_id": data.get("requester_id"),
            "actor_name": data.get("requester_name"),
            "activated": True,
            "infos": {
                "event_status": "new",
                "source_role": data.get("requester_role", "user"),
                "actor_role": data.get("requester_role", "user"),
                "new_status": "new",
            },
        })

        # Circuit de validation optionnel (pattern edgrh)
        for i, step in enumerate(workflow_steps):
            step_data = dict(step) if isinstance(step, dict) else step
            step_data["workflow_id"] = wf_id
            step_data.setdefault("activated", i == 0)
            step_data.setdefault("accepted", None)
            await self.detail_repo.create(step_data)

        self._logger.info(f"Demande créée — ref={ref}")
        await emit_event(AppEvent(
            type="request.created",
            payload={"id": obj.id, "ref": ref, "category": category_code},
            target={"roles": ["agent", "chief", "director", "admin"]},
        ))

        # Étape 2 — routage automatique uniquement si explicitement demandé.
        if self._should_auto_route(data):
            try:
                await self._apply_routing(
                    obj, wf_id,
                    actor_id=data.get("requester_id"),
                    actor_name=data.get("requester_name"),
                    raw_description=raw_description,
                    actor_role=data.get("requester_role", "user"),
                )
            except Exception as exc:
                self._logger.warning(f"Routage échoué pour demande {ref}: {exc}")

        # Re-fetch pour retourner l'état complet après routage
        fresh = await self.repo.get_by_id(obj.id)
        if fresh is not None:
            obj = fresh

        return obj

    async def submit_external(self, data: dict):
        """Soumission publique externe — force is_external=True et requester_type=external."""
        data["is_external"] = True
        data["requester_type"] = "external"
        data.setdefault("request_status", "new")
        data.setdefault("in_triage", True)
        return await self.create(data)

    # ── Mises à jour ──────────────────────────────────────────────────────────

    async def update(
        self,
        id: str,
        data: dict,
        *,
        actor_id: Optional[str] = None,
        actor_name: Optional[str] = None,
        actor_role: Optional[str] = None,
    ):
        raw_status = data.get("request_status")
        status_code = normalize_status(raw_status) if raw_status else None
        if raw_status and status_code != raw_status:
            data = {**data, "request_status": status_code}
        current = await self.repo.get_by_id(id)

        # Validation stricte de la matrice : les routes dediees portent les exceptions metier.
        if status_code and current is not None:
            assert_transition_allowed(
                current.request_status,
                status_code,
                actor_role=actor_role,
            )

        translated = await self._translate_codes(data)
        obj = await self.repo.update(id, translated)
        if obj is None:
            raise self.not_found(
                "Cette demande n'existe pas.",
                error_code=ErrorCode.REQUEST_NOT_FOUND,
                field="id",
                value=id,
            )
        if status_code:
            event_type = _STATUS_EVENT_MAP.get(status_code, "status_changed")
            event_label = _STATUS_LABEL_MAP.get(status_code, f"Statut → {status_code}")
            wf_id = await self._get_or_create_workflow(int(id))
            await self.detail_repo.create_event({
                "workflow_id": wf_id,
                "event_type": event_type,
                "label": event_label,
                "actor_id": actor_id,
                "actor_name": actor_name,
                "activated": True,
                "infos": self._clean_infos({
                    "event_status": status_code,
                    "source_role": actor_role,
                    "actor_role": actor_role,
                    "old_status": getattr(current, "request_status", None),
                    "new_status": status_code,
                    "changed_fields": sorted(data.keys()),
                }),
            })
            await emit_event(AppEvent(
                type="request.status_changed",
                payload={"id": id, "status": status_code},
                target={"roles": "all"},
            ))
            # Notification individuelle au demandeur (CDC §6.3)
            _notif_map = {
                "qualifying":   ("Demande en cours de qualification", "Votre demande {ref} est en cours de qualification.", "info"),
                "qualified":    ("Demande qualifiée", "Votre demande {ref} a été qualifiée et sera traitée prochainement.", "info"),
                "assigned":     ("Demande assignée", "Votre demande {ref} a été assignée à un agent qui va la traiter.", "info"),
                "in_progress":  ("Demande prise en charge", "Votre demande {ref} est maintenant en cours de traitement.", "info"),
                "pending":      ("Information complémentaire requise", "Un agent attend votre retour sur la demande {ref}.", "warning"),
                "escalated":    ("Demande escaladée", "Votre demande {ref} a été escaladée à un niveau supérieur.", "warning"),
            }
            if status_code in _notif_map and obj is not None and obj.requester_id:
                title_tpl, body_tpl, notif_type = _notif_map[status_code]
                ref_val = getattr(obj, "ref", id)
                await emit_notif(
                    self.session,
                    recipient_id=str(obj.requester_id),
                    title=title_tpl,
                    body=body_tpl.format(ref=ref_val),
                    type=notif_type,
                    request_id=id,
                    action_label="Voir la demande",
                    action_url=f"/app/requests/{id}",
                )
        else:
            if data:
                wf_id = await self._get_or_create_workflow(int(id))
                await self.detail_repo.create_event({
                    "workflow_id": wf_id,
                    "event_type": "request_updated",
                    "label": "Demande mise à jour",
                    "actor_id": actor_id,
                    "actor_name": actor_name,
                    "activated": True,
                    "infos": self._clean_infos({
                        "event_status": getattr(obj, "request_status", None),
                        "source_role": actor_role,
                        "actor_role": actor_role,
                        "changed_fields": sorted(data.keys()),
                    }),
                })
            await emit_event(AppEvent(
                type="request.updated",
                payload={"id": id},
                target={"roles": "all"},
            ))
        return obj

    async def requester_edit(self, id: str, data: dict, *, actor_id: str, actor_role: str = "user"):
        """Modification complète d'un ticket par son demandeur.
        Autorisé uniquement si request_status == 'new' (aucun acteur n'a encore agi).
        Relance le routage automatique après mise à jour.
        """
        from fastapi import HTTPException as _HTTP

        req = await self.repo.get_by_id(id)
        if req is None:
            raise self.not_found("Demande introuvable", error_code=ErrorCode.REQUEST_NOT_FOUND)

        if str(req.requester_id) != str(actor_id):
            raise _HTTP(status_code=403, detail="Seul le demandeur peut modifier ce ticket.")

        if req.request_status != "new":
            raise _HTTP(
                status_code=422,
                detail="Ce ticket ne peut plus être modifié — un acteur est déjà intervenu.",
            )

        patch: dict = {}
        if data.get("title"):
            patch["title"] = data["title"].strip()
        raw_desc = data.get("description", "")
        if raw_desc:
            patch["description"] = raw_desc.strip()
        if data.get("category"):
            patch["category"] = data["category"]
        if data.get("priority"):
            patch["priority"] = data["priority"]
        if data.get("unity_id") is not None:
            patch["unity_id"] = data["unity_id"]
        elif data.get("unit_id") is not None:
            patch["unity_id"] = data["unit_id"]
        elif data.get("direction_id") is not None:
            patch["unity_id"] = data["direction_id"]

        patch["assignee_id"] = None

        translated_patch = await self._translate_codes(patch)
        await self.repo.update(id, translated_patch)

        wf_id = await self._get_or_create_workflow(req.id)
        await self.detail_repo.create_event({
            "workflow_id": wf_id,
            "event_type": "requester_edit",
            "label": "Ticket modifié par le demandeur",
            "actor_id": actor_id,
            "actor_name": req.requester_name,
            "activated": True,
            "infos": {
                "event_status": "new",
                "source_role": actor_role,
                "actor_role": actor_role,
                "old_status": req.request_status,
                "new_status": "new",
                "changed_fields": sorted(patch.keys()),
            },
        })

        fresh = await self.repo.get_by_id(id)
        try:
            await self._apply_routing(
                fresh, wf_id,
                actor_id=actor_id,
                actor_name=req.requester_name,
                raw_description=raw_desc,
                actor_role=actor_role,
            )
        except Exception as exc:
            self._logger.warning(f"Re-routage échoué pour demande {req.ref}: {exc}")

        return await self.repo.get_by_id(id)

    async def assign(
        self, id: str, assignee_id: str, *,
        actor_id: Optional[str] = None,
        actor_name: Optional[str] = None,
        actor_role: Optional[str] = None,
        actor=None,
    ):
        current = await self._guard_ticket_action(
            id,
            "assign",
            target_status="assigned",
            actor=actor,
            actor_role=actor_role,
        )
        row = await self.session.execute(
            select(
                Account.unity_id,
                Unity.parent_direction_id,
                Account.name,
                Account.firstname,
                Account.role,
            )
            .select_from(Account)
            .outerjoin(Unity, Unity.id == Account.unity_id)
            .where(Account.id == int(assignee_id))
        )
        assignee_row = row.first()
        if assignee_row is None:
            raise self.not_found("Cet agent n'existe pas.", error_code=ErrorCode.ACCOUNT_NOT_FOUND)

        (
            assignee_unity_id,
            assignee_parent_dir_id,
            assignee_name_raw,
            assignee_firstname,
            assignee_role,
        ) = assignee_row
        assignee_name = self._account_display_name(assignee_name_raw, assignee_firstname)

        if actor is not None:
            assert_assignment_allowed(
                actor,
                current,
                assignee_id,
                target_unity_id=assignee_unity_id,
                target_role=assignee_role,
            )

        if actor_role not in _BYPASS_ROLES:
            assignee_direction_id = assignee_parent_dir_id or assignee_unity_id

            if current.direction_id is not None and assignee_direction_id != current.direction_id:
                raise self.bad_request(
                    "Cet agent n'appartient pas à la direction de ce ticket.",
                    error_code=ErrorCode.INVALID_STATUS_TRANSITION,
                )

        translated = await self._translate_codes({"request_status": "assigned"})
        obj = await self.repo.update(id, {
            "assignee_id": assignee_id,
            "in_triage": False,
            **translated,
        })
        if obj is None:
            raise self.not_found("Cette demande n'existe pas.", error_code=ErrorCode.REQUEST_NOT_FOUND)
        wf_id_assign = await self._get_or_create_workflow(int(id))
        await self.detail_repo.create_event({
            "workflow_id": wf_id_assign,
            "event_type": "assigned",
            "label": f"Demande assignée à {assignee_name or assignee_id}",
            "actor_id": actor_id,
            "actor_name": actor_name,
            "dest_id": assignee_id,
            "activated": True,
            "infos": self._clean_infos({
                "event_status": "assigned",
                "source_role": actor_role,
                "actor_role": actor_role,
                "dest_role": assignee_role,
                "target_role": assignee_role,
                "target_user_id": str(assignee_id),
                "target_user_name": assignee_name,
                "old_status": current.request_status,
                "new_status": "assigned",
                "old_assignee_id": current.assignee_id,
                "new_assignee_id": assignee_id,
                "target_unity_id": assignee_unity_id,
            }),
        })
        await emit_notif(
            self.session,
            recipient_id=assignee_id,
            title="Demande assignée",
            body=f"La demande {obj.ref} vous a été assignée.",
            type="info",
            request_id=id,
            action_label="Voir la demande",
            action_url=f"/app/requests/{id}",
        )
        await emit_event(AppEvent(
            type="request.assigned",
            payload={"id": id, "assignee_id": assignee_id},
            target={"roles": "all"},
        ))
        return obj

    async def close(
        self,
        id: str,
        *,
        actor_id: Optional[str] = None,
        actor_name: Optional[str] = None,
        actor_role: Optional[str] = None,
        actor=None,
    ):
        current = await self._guard_ticket_action(
            id,
            "close",
            target_status="closed",
            actor=actor,
            actor_role=actor_role,
        )
        translated = await self._translate_codes({"request_status": "closed"})
        obj = await self.repo.update(id, {
            **translated,
            "closed_at": datetime.now(timezone.utc).replace(tzinfo=None),
        })
        if obj is None:
            raise self.not_found("Cette demande n'existe pas.", error_code=ErrorCode.REQUEST_NOT_FOUND)
        wf_id_close = await self._get_or_create_workflow(int(id))
        await self.detail_repo.create_event({
            "workflow_id": wf_id_close,
            "event_type": "closed",
            "label": "Demande clôturée",
            "actor_id": actor_id,
            "actor_name": actor_name,
            "activated": True,
            "infos": self._clean_infos({
                "event_status": "closed",
                "source_role": actor_role,
                "actor_role": actor_role,
                "old_status": current.request_status,
                "new_status": "closed",
            }),
        })
        await emit_event(AppEvent(type="request.closed", payload={"id": id}, target={"roles": "all"}))
        return obj

    async def resolve(
        self,
        id: str,
        *,
        actor_id: Optional[str] = None,
        actor_name: Optional[str] = None,
        actor_role: Optional[str] = None,
        actor=None,
    ):
        current = await self._guard_ticket_action(
            id,
            "resolve",
            target_status="resolved",
            actor=actor,
            actor_role=actor_role,
        )
        translated = await self._translate_codes({"request_status": "resolved"})
        obj = await self.repo.update(id, {
            **translated,
            "resolved_at": datetime.now(timezone.utc).replace(tzinfo=None),
            "in_triage": False,
        })
        if obj is None:
            raise self.not_found("Cette demande n'existe pas.", error_code=ErrorCode.REQUEST_NOT_FOUND)
        wf_id_res = await self._get_or_create_workflow(int(id))
        await self.detail_repo.create_event({
            "workflow_id": wf_id_res,
            "event_type": "resolved",
            "label": "Demande résolue",
            "actor_id": actor_id,
            "actor_name": actor_name,
            "activated": True,
            "infos": self._clean_infos({
                "event_status": "resolved",
                "source_role": actor_role,
                "actor_role": actor_role,
                "old_status": current.request_status,
                "new_status": "resolved",
            }),
        })
        await emit_notif(
            self.session,
            recipient_id=getattr(obj, "requester_id", None),
            title="Demande résolue",
            body=f"Votre demande {obj.ref} a été résolue avec succès.",
            type="success",
            request_id=id,
            action_label="Confirmer la résolution",
            action_url=f"/app/requests/{id}",
        )
        await emit_event(AppEvent(type="request.resolved", payload={"id": id}, target={"roles": "all"}))
        return obj

    async def request_reopen(
        self,
        id: str,
        *,
        actor_id: Optional[str] = None,
        actor_name: Optional[str] = None,
        actor_role: Optional[str] = None,
        actor=None,
        reason: str,
    ):
        """
        Phase 1 — L'utilisateur refuse la résolution et demande la réouverture.

        Préconditions :
          - Le ticket doit être à l'état RESOLVED.
          - Le motif est obligatoire.

        Actions :
          - Crée un événement REOPEN_REQUESTED (dest = chef de service).
          - Pose request.infos["reopen_requested"] = True (flag visible par le chef).
          - Notifie le chef de service actuel.
          - Status inchangé : reste RESOLVED en attente de décision chef.
        """
        obj = await self.get_by_id(id)
        effective_actor_role = actor_role or getattr(actor, "role", None) or "user"
        if actor is not None:
            await self._guard_ticket_action(
                id,
                "request_reopen",
                actor=actor,
                actor_role=effective_actor_role,
            )

        translated_status = (obj.request_status or "").lower()
        if translated_status not in ("resolved", "rejected", "closed"):
            raise self.bad_request(
                "La réouverture n'est possible que sur un ticket à l'état RESOLVED, REJECTED ou CLOSED.",
                error_code=ErrorCode.INVALID_STATUS_TRANSITION,
            )

        # Fenêtre de 7 jours pour rouvrir un ticket fermé automatiquement
        if translated_status == "closed" and obj.closed_at:
            from datetime import timedelta
            deadline = obj.closed_at + timedelta(days=7)
            if datetime.now(timezone.utc).replace(tzinfo=None) > deadline:
                raise self.bad_request(
                    "La fenêtre de réouverture (7 jours après fermeture) est expirée. Créez une nouvelle demande.",
                    error_code=ErrorCode.INVALID_STATUS_TRANSITION,
                )

        if not reason or not reason.strip():
            raise self.bad_request(
                "Un motif est obligatoire pour demander la réouverture.",
                field="reason",
            )

        if isinstance(obj.infos, dict) and obj.infos.get("reopen_requested"):
            raise self.conflict(
                "Une demande de réouverture est déjà en attente d'approbation.",
                error_code=ErrorCode.DUPLICATE_REQUEST,
            )

        wf_id = await self._get_or_create_workflow(int(id))

        # Trouve le chef du service actuel pour la destination
        from api.repositories.RepositoryAccount import AccountRepository
        acc_repo = AccountRepository(self.session)
        chief = await acc_repo.find_chief_for_unity(obj.unity_id) if obj.unity_id else None

        await self.detail_repo.create_event({
            "workflow_id": wf_id,
            "event_type": "reopen_requested",
            "label": f"Réouverture demandée — {reason.strip()}",
            "actor_id": actor_id,
            "actor_name": actor_name,
            "dest_id": chief.id if chief else None,
            "comment": reason.strip(),
            "activated": True,
            "infos": self._clean_infos({
                "event_status": "pending_validation",
                "source_role": effective_actor_role,
                "actor_role": effective_actor_role,
                "dest_role": "chief",
                "target_role": "chief",
                "target_user_id": str(chief.id) if chief else None,
                "target_user_name": self._account_display_name(chief) if chief else None,
                "old_status": translated_status,
                "new_status": translated_status,
                "reason": reason.strip(),
            }),
        })

        # Marque le flag sur la demande (pas de changement de statut)
        current_infos = dict(obj.infos) if isinstance(obj.infos, dict) else {}
        current_infos["reopen_requested"] = True
        await self.repo.update(id, {"infos": current_infos})

        if chief:
            await emit_notif(
                self.session,
                recipient_id=str(chief.id),
                title="Réouverture demandée",
                body=f"L'utilisateur conteste la résolution de {obj.ref} : « {reason.strip()[:80]} »",
                type="warning",
                request_id=id,
                action_label="Voir la demande",
                action_url=f"/app/requests/{id}",
            )

        await emit_event(AppEvent(
            type="request.reopen_requested",
            payload={"id": id},
            target={"roles": "all"},
        ))

        fresh = await self.repo.get_by_id(int(id))
        return fresh if fresh else obj

    async def reopen(
        self,
        id: str,
        *,
        actor_id: Optional[str] = None,
        actor_name: Optional[str] = None,
        actor_role: Optional[str] = None,
        actor=None,
    ):
        """
        Phase 2 — Le chef approuve la réouverture.

        Efface le flag reopen_requested si présent, change le statut en REOPENED.
        """
        await self._guard_ticket_action(
            id,
            "reopen",
            target_status="reopened",
            actor=actor,
            actor_role=actor_role,
        )
        obj = await self.get_by_id(id)

        has_pending_reopen = isinstance(obj.infos, dict) and obj.infos.get("reopen_requested")
        effective_role = str(getattr(actor, "role", actor_role or "") or "").strip().lower()
        if not has_pending_reopen and effective_role not in _BYPASS_ROLES:
            raise self.bad_request(
                "Aucune demande de réouverture n'est en attente.",
                error_code=ErrorCode.INVALID_STATUS_TRANSITION,
            )

        # Efface le flag de demande de réouverture si présent
        if has_pending_reopen:
            current_infos = dict(obj.infos)
            current_infos.pop("reopen_requested", None)
            await self.repo.update(id, {"infos": current_infos})

        translated = await self._translate_codes({"request_status": "reopened"})
        updated = await self.repo.update(id, translated)
        if updated is None:
            raise self.not_found("Cette demande n'existe pas.", error_code=ErrorCode.REQUEST_NOT_FOUND)

        wf_id = await self._get_or_create_workflow(int(id))
        await self.detail_repo.create_event({
            "workflow_id": wf_id,
            "event_type": "reopened",
            "label": "Réouverture approuvée — ticket remis en traitement",
            "actor_id": actor_id,
            "actor_name": actor_name,
            "activated": True,
            "infos": self._clean_infos({
                "event_status": "in_progress",
                "source_role": actor_role,
                "actor_role": actor_role,
                "dest_role": "user",
                "target_role": "user",
                "target_user_id": str(obj.requester_id) if obj.requester_id else None,
                "target_user_name": obj.requester_name,
                "old_status": obj.request_status,
                "new_status": "reopened",
            }),
        })

        # Notifie le requérant
        if obj.requester_id:
            await emit_notif(
                self.session,
                recipient_id=str(obj.requester_id),
                title="Votre demande de réouverture a été acceptée",
                body=f"Le ticket {obj.ref} a été remis en traitement.",
                type="info",
                request_id=id,
                action_label="Voir la demande",
                action_url=f"/app/requests/{id}",
            )

        await emit_event(AppEvent(type="request.reopened", payload={"id": id}, target={"roles": "all"}))
        fresh = await self.repo.get_by_id(int(id))
        return fresh if fresh else updated

    async def reject_reopen(
        self,
        id: str,
        *,
        actor_id: Optional[str] = None,
        actor_name: Optional[str] = None,
        actor_role: Optional[str] = None,
        actor=None,
        reason: Optional[str] = None,
    ):
        """
        Refus d'une demande de réouverture.

        Le statut du ticket ne change pas, mais le flag reopen_requested est retiré
        et la décision est conservée dans la timeline.
        """
        clean_reason = reason.strip() if isinstance(reason, str) else ""
        if not clean_reason:
            raise self.bad_request(
                "Un motif est obligatoire pour refuser une réouverture.",
                field="reason",
            )

        obj = await self._guard_ticket_action(
            id,
            "reject_reopen",
            actor=actor,
            actor_role=actor_role,
        )
        if not (isinstance(obj.infos, dict) and obj.infos.get("reopen_requested")):
            raise self.bad_request(
                "Aucune demande de réouverture n'est en attente.",
                error_code=ErrorCode.INVALID_STATUS_TRANSITION,
            )

        current_infos = dict(obj.infos)
        current_infos.pop("reopen_requested", None)
        current_infos["reopen_rejected_reason"] = clean_reason
        current_infos["reopen_rejected_at"] = datetime.now(timezone.utc).isoformat()
        await self.repo.update(id, {"infos": current_infos})

        wf_id = await self._get_or_create_workflow(int(id))
        await self.detail_repo.create_event({
            "workflow_id": wf_id,
            "event_type": "reopen_rejected",
            "label": f"Réouverture refusée — {clean_reason}",
            "actor_id": actor_id,
            "actor_name": actor_name,
            "comment": clean_reason,
            "activated": True,
            "infos": self._clean_infos({
                "event_status": obj.request_status,
                "source_role": actor_role,
                "actor_role": actor_role,
                "dest_role": "user",
                "target_role": "user",
                "target_user_id": str(obj.requester_id) if obj.requester_id else None,
                "target_user_name": obj.requester_name,
                "old_status": obj.request_status,
                "new_status": obj.request_status,
                "reason": clean_reason,
            }),
        })

        if obj.requester_id:
            await emit_notif(
                self.session,
                recipient_id=str(obj.requester_id),
                title="Votre demande de réouverture a été refusée",
                body=f"Le ticket {obj.ref} reste à l'état {obj.request_status} : {clean_reason[:100]}",
                type="warning",
                request_id=id,
                action_label="Voir la demande",
                action_url=f"/app/requests/{id}",
            )

        await emit_event(AppEvent(type="request.reopen_rejected", payload={"id": id}, target={"roles": "all"}))
        fresh = await self.repo.get_by_id(int(id))
        return fresh if fresh else obj

    async def cancel(
        self,
        id: str,
        *,
        actor_id: Optional[str] = None,
        actor_name: Optional[str] = None,
        actor_role: Optional[str] = None,
        actor=None,
        reason: Optional[str] = None,
    ):
        clean_reason = reason.strip() if isinstance(reason, str) else ""
        if not clean_reason:
            raise self.bad_request(
                "Un motif est obligatoire pour annuler une demande.",
                field="reason",
            )

        current = await self._guard_ticket_action(
            id,
            "cancel",
            target_status="cancelled",
            actor=actor,
            actor_role=actor_role,
        )
        translated = await self._translate_codes({"request_status": "cancelled"})
        patch: dict[str, Any] = dict(translated)
        existing = await self.repo.get_by_id(int(id))
        existing_infos = (existing.infos or {}) if existing else {}
        patch["infos"] = {**existing_infos, "cancel_reason": clean_reason}
        obj = await self.repo.update(id, patch)
        if obj is None:
            raise self.not_found("Cette demande n'existe pas.", error_code=ErrorCode.REQUEST_NOT_FOUND)
        wf_id_cancel = await self._get_or_create_workflow(int(id))
        await self.detail_repo.create_event({
            "workflow_id": wf_id_cancel,
            "event_type": "cancelled",
            "label": f"Demande annulée — {clean_reason}",
            "actor_id": actor_id,
            "actor_name": actor_name,
            "comment": clean_reason,
            "activated": True,
            "infos": self._clean_infos({
                "event_status": "cancelled",
                "source_role": actor_role,
                "actor_role": actor_role,
                "old_status": current.request_status,
                "new_status": "cancelled",
                "reason": clean_reason,
            }),
        })
        await emit_event(AppEvent(type="request.cancelled", payload={"id": id}, target={"roles": "all"}))
        return obj

    async def reassign_service(
        self,
        id: str,
        target_unity_id: int,
        *,
        actor_id: Optional[str] = None,
        actor_name: Optional[str] = None,
        actor_role: Optional[str] = None,
        actor=None,
        reason: Optional[str] = None,
    ):
        """
        Réaffectation vers un autre service (action chef).

        Trouve le chef du service cible, crée un événement reassigned_service,
        met à jour la demande (unity_id, assignee_id, status=assigned).
        """
        from api.repositories.RepositoryAccount import AccountRepository

        obj = await self._guard_ticket_action(
            id,
            "reassign",
            target_status="assigned",
            actor=actor,
            actor_role=actor_role,
        )
        target_row = await self.session.execute(
            select(Unity.id, Unity.parent_direction_id, Unity.label)
            .where(Unity.id == int(target_unity_id), Unity.deleted_at.is_(None))
        )
        target_unity = target_row.first()
        if target_unity is None:
            raise self.not_found("Service cible introuvable.", error_code=ErrorCode.UNIT_NOT_FOUND)

        target_unity_db_id, target_parent_direction_id, target_label = target_unity
        target_direction_id = target_parent_direction_id or target_unity_db_id
        actor_direction_id = None
        effective_actor_role = str(getattr(actor, "role", actor_role or "") or "").strip().lower()
        actor_unity_id = getattr(actor, "unity_id", None)
        if actor is not None and effective_actor_role == "chief" and actor_unity_id is not None:
            actor_unity_row = await self.session.execute(
                select(Unity.id, Unity.parent_direction_id)
                .where(Unity.id == int(actor_unity_id), Unity.deleted_at.is_(None))
            )
            actor_unity = actor_unity_row.first()
            if actor_unity is not None:
                actor_unity_db_id, actor_parent_direction_id = actor_unity
                actor_direction_id = actor_parent_direction_id or actor_unity_db_id

        if actor is not None:
            assert_service_reassignment_allowed(
                actor,
                obj,
                target_unity_id,
                target_direction_id=target_direction_id,
                actor_direction_id=actor_direction_id,
            )

        if obj.unity_id is not None and int(obj.unity_id) == int(target_unity_id):
            raise self.bad_request(
                "Ce ticket est déjà affecté à ce service.",
                error_code=ErrorCode.INVALID_STATUS_TRANSITION,
            )
        wf_id = await self._get_or_create_workflow(int(id))
        acc_repo = AccountRepository(self.session)
        chief = await acc_repo.find_chief_for_unity(target_unity_id)

        await self.detail_repo.create_event({
            "workflow_id": wf_id,
            "event_type": "reassigned_service",
            "label": f"Réaffecté vers {target_label or 'un autre service'}{' — ' + reason if reason else ''}",
            "actor_id": actor_id,
            "actor_name": actor_name,
            "dest_id": chief.id if chief else None,
            "unity_id": target_unity_id,
            "comment": reason,
            "activated": True,
            "infos": self._clean_infos({
                "event_status": "pending_validation",
                "source_role": actor_role,
                "actor_role": actor_role,
                "dest_role": getattr(chief, "role", None) or "chief",
                "target_role": getattr(chief, "role", None) or "chief",
                "target_user_id": str(chief.id) if chief else None,
                "target_user_name": self._account_display_name(chief) if chief else None,
                "previous_unity_id": obj.unity_id,
                "target_unity_id": target_unity_id,
                "target_direction_id": target_direction_id,
                "old_status": obj.request_status,
                "new_status": "assigned",
                "old_assignee_id": obj.assignee_id,
                "new_assignee_id": chief.id if chief else None,
                "reason": reason,
            }),
        })

        status_translated = await self._translate_codes({"request_status": "assigned"})
        await self.repo.update(id, {
            "unity_id": target_unity_id,
            "assignee_id": chief.id if chief else None,
            "in_triage": False,
            **status_translated,
        })

        if chief:
            await emit_notif(
                self.session,
                recipient_id=str(chief.id),
                title="Demande réaffectée vers votre service",
                body=f"La demande {obj.ref} vous a été transférée.",
                type="info",
                request_id=id,
                action_label="Voir la demande",
                action_url=f"/app/requests/{id}",
            )

        await emit_event(AppEvent(
            type="request.reassigned",
            payload={"id": id, "unity_id": target_unity_id},
            target={"roles": "all"},
        ))

        fresh = await self.repo.get_by_id(int(id))
        return fresh if fresh else obj

    async def transfer_direction(
        self,
        id: str,
        target_direction_id: int,
        *,
        actor_id: Optional[str] = None,
        actor_name: Optional[str] = None,
        actor_role: Optional[str] = None,
        actor=None,
        reason: Optional[str] = None,
    ):
        """
        Transfert inter-direction.

        Le directeur source sort le ticket de son périmètre quand aucun service
        de sa direction ne peut le traiter. Le ticket entre alors dans la
        direction cible comme une demande à qualifier, sans assignation directe.
        """
        from api.repositories.RepositoryAccount import AccountRepository

        clean_reason = reason.strip() if isinstance(reason, str) else ""
        if not clean_reason:
            raise self.bad_request(
                "Un motif est obligatoire pour transférer une demande vers une autre direction.",
                field="reason",
            )

        obj = await self._guard_ticket_action(
            id,
            "transfer_direction",
            actor=actor,
            actor_role=actor_role,
        )

        if normalize_status(obj.request_status) in TERMINAL_STATUSES:
            raise self.bad_request(
                "Un ticket finalisé ne peut pas être transféré vers une autre direction.",
                error_code=ErrorCode.INVALID_STATUS_TRANSITION,
            )
        assert_transition_allowed(obj.request_status, "qualifying", actor_role=actor_role)

        try:
            target_direction_int = int(target_direction_id)
        except (TypeError, ValueError):
            raise self.bad_request("Direction cible invalide.", field="target_direction_id")

        target_row = await self.session.execute(
            select(Unity.id, Unity.parent_direction_id, Unity.label)
            .where(Unity.id == target_direction_int, Unity.deleted_at.is_(None))
        )
        target_direction = target_row.first()
        if target_direction is None:
            raise self.not_found("Direction cible introuvable.", error_code=ErrorCode.UNIT_NOT_FOUND)

        target_direction_db_id, target_parent_direction_id, target_label = target_direction
        if target_parent_direction_id is not None:
            raise self.bad_request(
                "La cible doit être une direction, pas un service.",
                field="target_direction_id",
            )

        source_direction_id = obj.direction_id or obj.unity_id
        if source_direction_id is not None and int(source_direction_id) == int(target_direction_db_id):
            raise self.bad_request(
                "Ce ticket est déjà dans cette direction.",
                error_code=ErrorCode.INVALID_STATUS_TRANSITION,
            )

        wf_id = await self._get_or_create_workflow(int(id))
        acc_repo = AccountRepository(self.session)
        target_directors = await acc_repo.find_directors_by_direction(int(target_direction_db_id))
        first_director = target_directors[0] if target_directors else None

        await self.detail_repo.create_event({
            "workflow_id": wf_id,
            "event_type": "transferred_direction",
            "label": f"Transféré vers {target_label or 'une autre direction'} — {clean_reason}",
            "actor_id": actor_id,
            "actor_name": actor_name,
            "dest_id": first_director.id if first_director else None,
            "unity_id": target_direction_db_id,
            "comment": clean_reason,
            "activated": True,
            "infos": self._clean_infos({
                "event_status": "qualifying",
                "source_role": actor_role,
                "actor_role": actor_role,
                "dest_role": "director",
                "target_role": "director",
                "target_user_id": str(first_director.id) if first_director else None,
                "target_user_name": self._account_display_name(first_director) if first_director else None,
                "previous_direction_id": source_direction_id,
                "target_direction_id": target_direction_db_id,
                "target_direction_name": target_label,
                "previous_unity_id": obj.unity_id,
                "target_unity_id": target_direction_db_id,
                "old_status": obj.request_status,
                "new_status": "qualifying",
                "old_assignee_id": obj.assignee_id,
                "new_assignee_id": None,
                "reason": clean_reason,
            }),
        })

        status_translated = await self._translate_codes({"request_status": "qualifying"})
        existing_infos = dict(obj.infos) if isinstance(obj.infos, dict) else {}
        existing_infos.update({
            "last_transfer_reason": clean_reason,
            "last_transfer_from_direction_id": source_direction_id,
            "last_transfer_to_direction_id": target_direction_db_id,
        })
        await self.repo.update(id, {
            "unity_id": target_direction_db_id,
            "assignee_id": None,
            "in_triage": False,
            "infos": existing_infos,
            **status_translated,
        })

        if first_director:
            await emit_notif(
                self.session,
                recipient_id=str(first_director.id),
                title="Demande transférée vers votre direction",
                body=f"La demande {obj.ref} a été transférée vers {target_label} : {clean_reason[:120]}",
                type="info",
                request_id=id,
                action_label="Voir la demande",
                action_url=f"/app/requests/{id}",
            )

        await emit_event(AppEvent(
            type="request.transferred_direction",
            payload={
                "id": id,
                "from_direction_id": source_direction_id,
                "to_direction_id": target_direction_db_id,
            },
            target={"user_ids": [int(first_director.id)] if first_director else []},
        ))

        fresh = await self.repo.get_by_id(int(id))
        return fresh if fresh else obj

    async def change_priority(
        self,
        id: str,
        priority: str,
        *,
        actor_id: Optional[str] = None,
        actor_name: Optional[str] = None,
        actor_role: Optional[str] = None,
        actor=None,
    ):
        clean_priority = priority.strip().lower() if isinstance(priority, str) else ""
        if not clean_priority:
            raise self.bad_request("La priorité est obligatoire.", field="priority")

        obj = await self._guard_ticket_action(
            id,
            "change_priority",
            actor=actor,
            actor_role=actor_role,
        )
        if normalize_status(obj.request_status) in TERMINAL_STATUSES:
            raise self.bad_request(
                "La priorité d'un ticket finalisé ne peut pas être modifiée.",
                error_code=ErrorCode.INVALID_STATUS_TRANSITION,
            )

        priority_row = await self.session.execute(
            select(PriorityDefinition.id)
            .where(PriorityDefinition.slug == clean_priority)
            .where(PriorityDefinition.deleted_at.is_(None))
        )
        priority_id = priority_row.scalar_one_or_none()
        if priority_id is None:
            raise self.bad_request(
                "Priorité inconnue.",
                field="priority",
            )

        old_priority = obj.priority
        if old_priority == clean_priority:
            return obj

        updated = await self.repo.update(id, {"priority_definition_id": priority_id})
        if updated is None:
            raise self.not_found("Cette demande n'existe pas.", error_code=ErrorCode.REQUEST_NOT_FOUND)

        wf_id = await self._get_or_create_workflow(int(id))
        await self.detail_repo.create_event({
            "workflow_id": wf_id,
            "event_type": "priority_changed",
            "label": f"Priorité modifiée — {old_priority} → {clean_priority}",
            "actor_id": actor_id,
            "actor_name": actor_name,
            "activated": True,
            "infos": self._clean_infos({
                "event_status": obj.request_status,
                "actor_id": actor_id,
                "source_role": actor_role,
                "actor_role": actor_role,
                "target_user_id": "",
                "target_role": "",
                "old_status": obj.request_status,
                "new_status": obj.request_status,
                "reason": "Changement de priorité",
                "old_priority": old_priority,
                "new_priority": clean_priority,
            }),
        })
        await emit_event(AppEvent(
            type="request.priority_changed",
            payload={"id": id, "priority": clean_priority},
            target={"roles": "all"},
        ))

        fresh = await self.repo.get_by_id(int(id))
        return fresh if fresh else updated

    async def reject(
        self,
        id: str,
        *,
        actor_id: Optional[str] = None,
        actor_name: Optional[str] = None,
        actor_role: Optional[str] = None,
        actor=None,
        reason: Optional[str] = None,
    ):
        """
        Rejet de la demande par le chef de service (validation refusée).

        Crée l'événement rejected, passe le statut à 'rejected',
        notifie le requérant.
        """
        clean_reason = reason.strip() if isinstance(reason, str) else ""
        if not clean_reason:
            raise self.bad_request(
                "Un motif est obligatoire pour rejeter une demande.",
                field="reason",
            )

        obj = await self._guard_ticket_action(
            id,
            "reject",
            target_status="rejected",
            actor=actor,
            actor_role=actor_role,
        )
        wf_id = await self._get_or_create_workflow(int(id))

        status_translated = await self._translate_codes({"request_status": "rejected"})
        await self.repo.update(id, {
            **status_translated,
            "assignee_id": obj.requester_id,
        })

        await self.detail_repo.create_event({
            "workflow_id": wf_id,
            "event_type": "rejected",
            "label": f"Demande rejetée — {clean_reason}",
            "actor_id": actor_id,
            "actor_name": actor_name,
            "comment": clean_reason,
            "activated": True,
            "infos": self._clean_infos({
                "event_status": "rejected",
                "source_role": actor_role,
                "actor_role": actor_role,
                "dest_role": "user",
                "target_role": "user",
                "target_user_id": str(obj.requester_id) if obj.requester_id else None,
                "target_user_name": obj.requester_name,
                "old_status": obj.request_status,
                "new_status": "rejected",
                "reason": clean_reason,
            }),
        })

        if obj.requester_id:
            await emit_notif(
                self.session,
                recipient_id=str(obj.requester_id),
                title="Demande rejetée",
                body=f"Votre demande {obj.ref} a été rejetée : {clean_reason}",
                type="warning",
                request_id=id,
                action_label="Voir la demande",
                action_url=f"/app/requests/{id}",
            )

        await emit_event(AppEvent(type="request.rejected", payload={"id": id}, target={"roles": "all"}))

        fresh = await self.repo.get_by_id(int(id))
        return fresh if fresh else obj

    async def list_by_unity(self, unity_id: str, *, page: int = 1, limit: int = 20):
        return await self.list_filtered(unit_id=unity_id, page=page, limit=limit)

    async def delete(self, id: str) -> bool:
        await self.get_by_id(id)
        return await self.repo.delete(id)

    async def delete_by_uuid(self, id: str, uuid: str) -> bool:
        """Suppression avec vérification uuid — pattern edgrh delete_uuid()."""
        req = await self.get_by_id(id)
        if str(req.uuid) != uuid:
            raise self.bad_request("UUID invalide pour cette demande.")
        return await self.repo.delete(id)

    async def restore(self, id: str):
        """Restauration soft-delete — pattern edgrh /restore/{id}."""
        ok = await self.repo.restore(int(id))
        if not ok:
            raise self.not_found("Demande introuvable ou non supprimée")
        return await self.repo.get_by_id(int(id))

    async def get_first_filtered(
        self,
        *,
        request_status: Optional[str] = None,
        unity_id: Optional[str] = None,
        assignee_id: Optional[str] = None,
        requester_id: Optional[str] = None,
        is_external: Optional[bool] = None,
        in_triage: Optional[bool] = None,
        sla_breached: Optional[bool] = None,
        category: Optional[str] = None,
        priority: Optional[str] = None,
    ):
        """Retourne le PREMIER résultat filtré — pattern edgrh get_items()."""
        result = await self.list_filtered(
            request_status=request_status,
            unit_id=unity_id,
            assignee_id=assignee_id,
            requester_id=requester_id,
            is_external=is_external,
            in_triage=in_triage,
            sla_breached=sla_breached,
            page=1,
            limit=1,
        )
        items = result.get("items") or result.get("data") or []
        if not items:
            raise self.not_found("Aucune demande correspondant aux critères.")
        return items[0]

    async def count_by_status(self) -> dict[str, int]:
        return await self.repo.count_by_status()

    async def search(self, q: str, *, page: int = 1, limit: int = 20):
        items, total = await self.repo.search(q, page=page, limit=limit)
        return self.paginate(self._serialize(items), total, page, limit)
