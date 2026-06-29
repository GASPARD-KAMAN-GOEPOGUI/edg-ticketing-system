from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy import true as sql_true
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.error_codes import ErrorCode
from api.core.event_bus import AppEvent, emit as emit_event
from api.models.ModelAccount import Account
from api.models.ModelPriorityDefinition import PriorityDefinition
from api.models.ModelRequest import Request as RequestModel
from api.models.ModelRequestCategory import RequestCategory
from api.models.ModelRequestStatus import RequestStatus
from api.models.ModelWorkflow import Workflow
from api.repositories import RequestRepository, WorkflowDetailRepository
from api.schemas.SchemaRequest import RequestResponse
from api.services.base_service import BaseService
from api.services.NotificationEmitter import emit as emit_notif
from api.services.ServiceCrypto import decrypt_field

# Transitions de statut autorisées (CDC §4.1)
# Clé = statut cible, valeur = ensemble des statuts sources valides
_ALLOWED_TRANSITIONS: dict[str, set[str]] = {
    "qualifying":   {"new", "reopened"},
    "qualified":    {"qualifying"},
    "assigned":     {"qualified", "qualifying", "new", "reopened"},
    "in_progress":  {"assigned", "qualifying", "qualified"},
    "pending":      {"in_progress", "assigned"},
    "waiting_user": {"in_progress", "assigned"},
    "escalated":    {"in_progress", "assigned", "pending", "waiting_user", "qualifying"},
    "resolved":     {"in_progress", "assigned", "escalated", "pending", "waiting_user"},
    "closed":       {"resolved"},
    "reopened":     {"resolved", "rejected"},
    "rejected":     {"new", "qualifying", "qualified", "assigned", "in_progress", "pending"},
    "cancelled":    {"new", "qualifying", "qualified", "assigned", "in_progress", "pending", "waiting_user"},
}

# Transitions libres pour admin/dg (bypass matrice)
_BYPASS_ROLES = frozenset({"admin", "dg"})

# Mapping statut → event_type spécifique (CDC §7 + §8)
_STATUS_EVENT_MAP: dict[str, str] = {
    "qualifying":   "qualifying",
    "qualified":    "qualified",
    "in_progress":  "in_progress",
    "waiting_user": "waiting_user",
    "rejected":     "rejected",
    "pending":      "pending",
    "escalated":    "escalated",
}
_STATUS_LABEL_MAP: dict[str, str] = {
    "qualifying":   "Ticket en cours de qualification",
    "qualified":    "Ticket qualifié",
    "in_progress":  "Prise en charge — traitement en cours",
    "waiting_user": "En attente de retour utilisateur",
    "rejected":     "Ticket rejeté",
    "pending":      "Ticket en attente",
    "escalated":    "Ticket escaladé",
}


class RequestService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.repo = RequestRepository(session)
        self.detail_repo = WorkflowDetailRepository(session)

    # ── Helper : traduit codes string → IDs FK ────────────────────────────────

    async def _translate_codes(self, data: dict) -> dict:
        out = dict(data)
        if "request_status" in out:
            code = out.pop("request_status")
            if code is not None:
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

    # ── Sérialisation ─────────────────────────────────────────────────────────

    @staticmethod
    def _decrypt_schema(schema: RequestResponse) -> RequestResponse:
        if schema.description and schema.description.startswith("enc:"):
            return schema.copy(update={"description": decrypt_field(schema.description)})
        return schema

    @staticmethod
    def _serialize(items: list) -> list:
        """Convertit les ORM Request en RequestResponse et déchiffre les champs sensibles."""
        result = []
        for item in items:
            schema = RequestResponse.from_orm(item)
            if schema.description and schema.description.startswith("enc:"):
                schema = schema.copy(update={"description": decrypt_field(schema.description)})
            result.append(schema)
        return result

    # ── Listes ────────────────────────────────────────────────────────────────

    async def list_all(self, *, page: int = 1, limit: int = 20):
        items, total = await self.repo.list(order_by="-created_at", page=page, limit=limit)
        return self.paginate(self._serialize(items), total, page, limit)

    async def list_filtered(
        self,
        *,
        request_status: Optional[str] = None,
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
            from sqlalchemy import select as _sel
            from api.models.ModelOrganigram import Organigram as _Org
            _r1 = await self.session.execute(
                _sel(_Org.id)
                .where(_Org.unity_id == int(direction_id), _Org.deleted_at.is_(None))
                .limit(1)
            )
            _org_id = _r1.scalar_one_or_none()
            _ids: list[int] = [int(direction_id)]
            if _org_id:
                _r2 = await self.session.execute(
                    _sel(_Org.unity_id)
                    .where(_Org.parent_id == _org_id, _Org.deleted_at.is_(None))
                )
                _ids.extend(uid for (uid,) in _r2.all())
            effective_unity_id = _ids  # list → repo utilise IN(...)
        else:
            effective_unity_id = None

        if search:
            items, total = await self.repo.search(
                search,
                filters={
                    k: v for k, v in {
                        "request_status": request_status,
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
            )
        return self.paginate(self._serialize(items), total, page, limit)

    async def list_by_status(self, status: str, *, page: int = 1, limit: int = 20):
        items, total = await self.repo.list_by_status(status, page=page, limit=limit)
        return self.paginate(self._serialize(items), total, page, limit)

    async def list_by_assignee(self, assignee_id: str, *, page: int = 1, limit: int = 20):
        items, total = await self.repo.list_by_assignee(assignee_id, page=page, limit=limit)
        return self.paginate(self._serialize(items), total, page, limit)

    async def list_by_direction(self, direction_id: str, *, page: int = 1, limit: int = 20):
        items, total = await self.repo.list_by_direction(direction_id, page=page, limit=limit)
        return self.paginate(self._serialize(items), total, page, limit)

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
        priority: Optional[str] = None,
        request_status: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ):
        items, total = await self.repo.list_queue(
            direction_id=direction_id,
            assignee_id=assignee_id,
            priority=priority,
            request_status=request_status,
            search=search,
            page=page,
            limit=limit,
        )
        return self.paginate(self._serialize(items), total, page, limit)

    async def qualify_triage(self, id: str, data: dict, *, actor_id: Optional[str] = None):
        """Qualifie une demande de triage : fixe l'unité/catégorie/priorité, in_triage=False, status=qualifying."""
        patch = {k: v for k, v in data.items() if k in {"category", "priority"}}
        # Map direction_id / unit_id → unity_id (compatibilité frontend)
        if "unit_id" in data:
            patch["unity_id"] = data["unit_id"]
        elif "direction_id" in data:
            patch["unity_id"] = data["direction_id"]
        patch["in_triage"] = False
        patch["request_status"] = "qualifying"
        return await self.update(id, patch, actor_id=actor_id)

    # ── Lectures unitaires ────────────────────────────────────────────────────

    async def get_by_id(self, id: str):
        obj = await self.repo.get_by_id(id)
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

    async def _auto_assign(
        self,
        request_id: int,
        unity_id: int,
        *,
        actor_id: Optional[str] = None,
    ) -> None:
        """Affecte la demande à l'agent le moins chargé de l'unité.

        Si aucun agent disponible, la demande reste non affectée sans erreur.
        """
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
            .where(Account.role.in_(["agent", "chief"]))
            .where(Account.account_status == "active")
            .where(Account.deleted_at.is_(None))
            .order_by(func.coalesce(load_sq.c.cnt, 0).asc())
            .limit(1)
        )

        result = await self.session.execute(stmt)
        agent_id = result.scalar_one_or_none()

        if agent_id is not None:
            await self.assign(str(request_id), str(agent_id), actor_id=actor_id)

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
                await self.detail_repo.create_event({
                    "workflow_id": wf_id,
                    "event_type": "routed_to_service",
                    "label": f"Orientation automatique — {matched.name}",
                    "actor_name": actor_name,
                    "actor_id": actor_id,
                    "dest_id": chief.id if chief else None,
                    "unity_id": target_unity_id,
                    "activated": True,
                    "infos": {
                        "event_status": "pending_validation",
                        "rule_id": str(matched.id),
                        "rule_name": matched.name,
                        "source_role": actor_role,
                        "dest_role": "chief",
                    },
                })

                status_translated = await self._translate_codes({"request_status": "assigned"})
                await self.repo.update(str(obj.id), {
                    "assignee_id": chief.id if chief else None,
                    "unity_id": target_unity_id,
                    "in_triage": False,
                    **status_translated,
                })

                if chief:
                    await emit_notif(
                        self.session,
                        recipient_id=str(chief.id),
                        title="Nouvelle demande à traiter",
                        body=f"La demande {obj.ref} a été routée vers votre service.",
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
            "infos": {
                "event_status": "to_qualify",
                "source_role": actor_role,
                "dest_role": "support",
            },
        })

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
                action_url="/app/triage",
            )

        self._logger.info(f"Demande {obj.ref} → triage (aucune règle matchée)")
        return False

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

        year = datetime.now(timezone.utc).year
        ref = await self.repo.next_ref(year)
        data["ref"] = ref
        category_code = data.get("category")
        raw_description = data.get("description", "")
        translated = await self._translate_codes(data)
        workflow_steps: list[dict] = translated.pop("workflows", None) or []

        obj = await self.repo.create(translated)
        wf_id = await self._get_or_create_workflow(obj.id)

        # Étape 1 — événement CREATED
        await self.detail_repo.create_event({
            "workflow_id": wf_id,
            "event_type": "created",
            "label": "Demande créée par l'utilisateur",
            "actor_id": data.get("requester_id"),
            "actor_name": data.get("requester_name"),
            "activated": True,
            "infos": {"event_status": "new", "source_role": "user"},
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
            target={"roles": ["agent", "chief", "director", "dg", "admin"]},
        ))

        # Étape 2 — routage automatique (remplace _auto_assign)
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

    async def update(self, id: str, data: dict, *, actor_id: Optional[str] = None, actor_role: Optional[str] = None):
        status_code = data.get("request_status")

        # Validation de la matrice de transitions (sauf admin/dg)
        if status_code and actor_role not in _BYPASS_ROLES:
            current = await self.repo.get_by_id(id)
            if current is not None:
                current_status = (current.request_status or "new").lower()
                allowed_sources = _ALLOWED_TRANSITIONS.get(status_code, set())
                if allowed_sources and current_status not in allowed_sources:
                    raise self.bad_request(
                        f"Transition invalide : {current_status!r} → {status_code!r}.",
                        error_code=ErrorCode.INVALID_STATUS_TRANSITION,
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
                "activated": True,
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
                "in_progress":  ("Demande prise en charge", "Votre demande {ref} est maintenant en cours de traitement.", "info"),
                "pending":      ("Information complémentaire requise", "Un agent attend votre retour sur la demande {ref}.", "warning"),
                "waiting_user": ("Information complémentaire requise", "Un agent attend votre retour sur la demande {ref}.", "warning"),
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
            "infos": {"event_status": "new", "source_role": actor_role},
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

    async def assign(self, id: str, assignee_id: str, *, actor_id: Optional[str] = None):
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
            "label": "Demande assignée",
            "actor_id": actor_id,
            "activated": True,
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

    async def close(self, id: str, *, actor_id: Optional[str] = None):
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
            "activated": True,
        })
        await emit_event(AppEvent(type="request.closed", payload={"id": id}, target={"roles": "all"}))
        return obj

    async def resolve(self, id: str, *, actor_id: Optional[str] = None):
        translated = await self._translate_codes({"request_status": "resolved"})
        obj = await self.repo.update(id, {
            **translated,
            "resolved_at": datetime.now(timezone.utc).replace(tzinfo=None),
        })
        if obj is None:
            raise self.not_found("Cette demande n'existe pas.", error_code=ErrorCode.REQUEST_NOT_FOUND)
        wf_id_res = await self._get_or_create_workflow(int(id))
        await self.detail_repo.create_event({
            "workflow_id": wf_id_res,
            "event_type": "resolved",
            "label": "Demande résolue",
            "actor_id": actor_id,
            "activated": True,
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

        translated_status = (obj.request_status or "").lower()
        if translated_status not in ("resolved", "rejected"):
            raise self.bad_request(
                "La réouverture n'est possible que sur un ticket à l'état RESOLVED ou REJECTED.",
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
            "infos": {
                "event_status": "pending_validation",
                "source_role": "user",
                "dest_role": "chief",
            },
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

    async def reopen(self, id: str, *, actor_id: Optional[str] = None, actor_name: Optional[str] = None):
        """
        Phase 2 — Le chef approuve la réouverture (ou l'agent/admin force la réouverture).

        Efface le flag reopen_requested si présent, change le statut en REOPENED.
        """
        obj = await self.get_by_id(id)

        # Efface le flag de demande de réouverture si présent
        if isinstance(obj.infos, dict) and obj.infos.get("reopen_requested"):
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
            "infos": {
                "event_status": "in_progress",
                "source_role": "chief",
                "dest_role": "user",
            },
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

    async def cancel(self, id: str, *, actor_id: Optional[str] = None, reason: Optional[str] = None):
        translated = await self._translate_codes({"request_status": "cancelled"})
        patch: dict[str, Any] = dict(translated)
        if reason:
            existing = await self.repo.get_by_id(int(id))
            existing_infos = (existing.infos or {}) if existing else {}
            patch["infos"] = {**existing_infos, "cancel_reason": reason}
        obj = await self.repo.update(id, patch)
        if obj is None:
            raise self.not_found("Cette demande n'existe pas.", error_code=ErrorCode.REQUEST_NOT_FOUND)
        wf_id_cancel = await self._get_or_create_workflow(int(id))
        await self.detail_repo.create_event({
            "workflow_id": wf_id_cancel,
            "event_type": "cancelled",
            "label": f"Demande annulée{' — ' + reason if reason else ''}",
            "actor_id": actor_id,
            "activated": True,
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
        reason: Optional[str] = None,
    ):
        """
        Réaffectation vers un autre service (action chef).

        Trouve le chef du service cible, crée un événement reassigned_service,
        met à jour la demande (unity_id, assignee_id, status=assigned).
        """
        from api.repositories.RepositoryAccount import AccountRepository

        obj = await self.get_by_id(id)
        wf_id = await self._get_or_create_workflow(int(id))
        acc_repo = AccountRepository(self.session)
        chief = await acc_repo.find_chief_for_unity(target_unity_id)

        await self.detail_repo.create_event({
            "workflow_id": wf_id,
            "event_type": "reassigned_service",
            "label": f"Réaffecté vers un autre service{' — ' + reason if reason else ''}",
            "actor_id": actor_id,
            "actor_name": actor_name,
            "dest_id": chief.id if chief else None,
            "unity_id": target_unity_id,
            "comment": reason,
            "activated": True,
            "infos": {
                "event_status": "pending_validation",
                "source_role": "chief",
                "dest_role": "chief",
                "previous_unity_id": obj.unity_id,
            },
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

    async def reject(
        self,
        id: str,
        *,
        actor_id: Optional[str] = None,
        actor_name: Optional[str] = None,
        reason: Optional[str] = None,
    ):
        """
        Rejet de la demande par le chef de service (validation refusée).

        Crée l'événement rejected, passe le statut à 'rejected',
        notifie le requérant.
        """
        obj = await self.get_by_id(id)
        wf_id = await self._get_or_create_workflow(int(id))

        status_translated = await self._translate_codes({"request_status": "rejected"})
        await self.repo.update(id, {
            **status_translated,
            "assignee_id": obj.requester_id,
        })

        await self.detail_repo.create_event({
            "workflow_id": wf_id,
            "event_type": "rejected",
            "label": f"Demande rejetée{' — ' + reason if reason else ''}",
            "actor_id": actor_id,
            "actor_name": actor_name,
            "comment": reason,
            "activated": True,
            "infos": {
                "event_status": "rejected",
                "source_role": "chief",
                "dest_role": "user",
            },
        })

        if obj.requester_id:
            await emit_notif(
                self.session,
                recipient_id=str(obj.requester_id),
                title="Demande rejetée",
                body=f"Votre demande {obj.ref} a été rejetée{' : ' + reason if reason else '.'}",
                type="warning",
                request_id=id,
                action_label="Voir la demande",
                action_url=f"/app/requests/{id}",
            )

        await emit_event(AppEvent(type="request.rejected", payload={"id": id}, target={"roles": "all"}))

        fresh = await self.repo.get_by_id(int(id))
        return fresh if fresh else obj

    async def list_by_unit(self, unit_id: str, *, page: int = 1, limit: int = 20):
        return await self.list_filtered(unit_id=unit_id, page=page, limit=limit)

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

    # ── Fusion de tickets ─────────────────────────────────────────────────────

    async def merge(self, source_id: str, target_id: str, *, actor_id: Optional[str] = None):
        """
        Fusionne la demande source dans la demande cible.
        - source : merged_into_id = target.id, statut → cancelled
        - target : inchangé (reçoit une note dans la timeline)
        """
        source = await self.get_by_id(source_id)
        target = await self.get_by_id(target_id)

        if str(source.id) == str(target.id):
            raise self.bad_request("Une demande ne peut pas être fusionnée avec elle-même.")

        if source.merged_into_id is not None:
            raise self.bad_request(f"La demande {source.ref} est déjà fusionnée.")

        cancelled = await self._translate_codes({"request_status": "cancelled"})
        await self.repo.update(source_id, {
            **cancelled,
            "merged_into_id": target.id,
        })

        wf_id_src = await self._get_or_create_workflow(int(source_id))
        await self.detail_repo.create_event({
            "workflow_id": wf_id_src,
            "event_type": "merged",
            "label": f"Demande fusionnée dans {target.ref}",
            "actor_id": actor_id,
            "activated": True,
        })
        wf_id_tgt = await self._get_or_create_workflow(int(target_id))
        await self.detail_repo.create_event({
            "workflow_id": wf_id_tgt,
            "event_type": "merge_received",
            "label": f"Demande {source.ref} fusionnée ici",
            "actor_id": actor_id,
            "activated": True,
        })
        await emit_event(AppEvent(
            type="request.merged",
            payload={"source_id": source_id, "target_id": target_id},
            target={"roles": "all"},
        ))
        return await self.get_by_id(target_id)

    # ── Duplication de ticket ─────────────────────────────────────────────────

    async def duplicate(self, id: str, *, actor_id: Optional[str] = None):
        """
        Duplique une demande existante : crée une nouvelle demande avec les
        mêmes champs métier mais une nouvelle référence, statut=new et
        sans assignee ni merged_into_id.
        """
        source = await self.get_by_id(id)

        year = datetime.now(timezone.utc).year
        new_ref = await self.repo.next_ref(year)

        new_data = {
            "ref": new_ref,
            "title": f"[Copie] {source.title}",
            "description": source.description,
            "request_status_id": source.request_status_id,
            "priority_definition_id": source.priority_definition_id,
            "request_category_id": source.request_category_id,
            "request_source": source.request_source,
            "unity_id": source.unity_id,
            "is_external": source.is_external,
            "requester_type": source.requester_type,
            "submission_mode": source.submission_mode,
            "requester_name": source.requester_name,
            "requester_phone": source.requester_phone,
            "requester_email": source.requester_email,
            "requester_address": source.requester_address,
            "meter_number": source.meter_number,
            "client_ref": source.client_ref,
            "sla_hours": source.sla_hours,
            "in_triage": source.in_triage,
            "requester_id": source.requester_id,
        }

        # Re-fixe statut → new
        new_status = await self._translate_codes({"request_status": "new"})
        new_data.update(new_status)

        new_req = await self.repo.create(new_data)
        wf_id_dup = await self._get_or_create_workflow(new_req.id)
        await self.detail_repo.create_event({
            "workflow_id": wf_id_dup,
            "event_type": "created",
            "label": f"Demande créée par duplication de {source.ref}",
            "actor_id": actor_id,
            "activated": True,
        })
        await emit_event(AppEvent(
            type="request.created",
            payload={"id": new_req.id, "ref": new_ref, "duplicated_from": source.ref},
            target={"roles": ["agent", "chief", "director", "dg", "admin"]},
        ))
        return new_req
