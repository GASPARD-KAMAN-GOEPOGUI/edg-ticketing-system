from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.rbac import normalize_role
from api.repositories import WorkflowRepository, WorkflowDetailRepository
from api.services.base_service import BaseService


class WorkflowService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.repo = WorkflowRepository(session)
        self.detail_repo = WorkflowDetailRepository(session)

    @staticmethod
    def _clean_infos(infos: dict[str, Any] | None) -> dict[str, Any]:
        return {key: value for key, value in (infos or {}).items() if value is not None}

    @staticmethod
    def _to_int(value) -> int | None:
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _same_id(left, right) -> bool:
        return left is not None and right is not None and str(left) == str(right)

    async def _direction_unity_ids(self, direction_id: int | str | None) -> set[int]:
        root_id = self._to_int(direction_id)
        if root_id is None:
            return set()

        from api.models.ModelOrganigram import Organigram
        from api.models.ModelUnity import Unity

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

    async def _workflow_request_unity_id(self, workflow_id) -> int | None:
        wf_id = self._to_int(workflow_id)
        if wf_id is None:
            return None

        from api.models.ModelRequest import Request as RequestModel
        from api.models.ModelWorkflow import Workflow

        row = await self.session.execute(
            select(RequestModel.unity_id)
            .join(Workflow, Workflow.request_id == RequestModel.id)
            .where(Workflow.id == wf_id, Workflow.deleted_at.is_(None))
            .limit(1)
        )
        return self._to_int(row.scalar_one_or_none())

    async def _assert_detail_decision_allowed(self, detail, actor) -> None:
        if actor is None:
            return

        role = normalize_role(getattr(actor, "role", ""))
        if role == "admin":
            return

        actor_id = getattr(actor, "id", None)
        if self._same_id(getattr(detail, "agent_id", None), actor_id):
            return

        actor_unity_id = getattr(actor, "unity_id", None)
        detail_unity_id = self._to_int(getattr(detail, "unity_id", None))
        request_unity_id = await self._workflow_request_unity_id(getattr(detail, "workflow_id", None))

        if role == "chief":
            if self._same_id(detail_unity_id, actor_unity_id) or self._same_id(request_unity_id, actor_unity_id):
                return

        if role == "director":
            allowed_ids = await self._direction_unity_ids(actor_unity_id)
            if detail_unity_id in allowed_ids or request_unity_id in allowed_ids:
                return

        raise self.forbidden("Vous ne pouvez décider que les étapes workflow dans votre périmètre.")

    async def _timeline(
        self,
        workflow_id: str,
        event_type: str,
        label: str,
        actor_id: str | None = None,
        *,
        actor_name: str | None = None,
        actor_role: str | None = None,
        comment: str | None = None,
        infos: dict[str, Any] | None = None,
    ) -> None:
        event_infos = self._clean_infos(infos)
        if actor_id:
            event_infos.setdefault("actor_id", str(actor_id))
        if actor_role:
            event_infos.setdefault("source_role", actor_role)
            event_infos.setdefault("actor_role", actor_role)
        await self.detail_repo.create_event({
            "workflow_id": workflow_id,
            "event_type": event_type,
            "label": label,
            "actor_id": actor_id,
            "actor_name": actor_name,
            "comment": comment,
            "activated": True,
            "infos": event_infos,
        })

    async def list_all(self, *, page: int = 1, limit: int = 20):
        items, total = await self.repo.list(order_by="-created_at", page=page, limit=limit)
        return self.paginate(items, total, page, limit)

    async def get_by_id(self, id: str):
        obj = await self.repo.get_by_id(id)
        if obj is None:
            raise self.not_found("Workflow introuvable")
        return obj

    async def get_by_request(self, request_id: str):
        return await self.repo.find_by_request(request_id)

    async def get_active_for_request(self, request_id: str):
        obj = await self.repo.find_active_workflow(request_id)
        if obj is None:
            raise self.not_found("Aucun workflow actif pour cette requête")
        return obj

    async def create(self, data: dict, *, actor_id: str | None = None):
        obj = await self.repo.create(data)
        await self._timeline(str(obj.id), "workflow_started", "Workflow démarré", actor_id)
        return obj

    async def create_for_request(
        self, request_id: str, data: dict, *, actor_id: str | None = None
    ):
        data["request_id"] = request_id
        return await self.create(data, actor_id=actor_id)

    async def update(self, id: str, data: dict):
        obj = await self.repo.update(id, data)
        if obj is None:
            raise self.not_found("Workflow introuvable")
        return obj

    async def complete(self, id: str, *, actor_id: str | None = None):
        wf = await self.get_by_id(id)
        obj = await self.repo.complete(id)
        if obj is None:
            raise self.not_found("Workflow introuvable")
        await self._timeline(str(wf.id), "workflow_completed", "Workflow complété", actor_id)
        return obj

    async def suspend(self, id: str, *, actor_id: str | None = None):
        wf = await self.get_by_id(id)
        obj = await self.repo.suspend(id)
        if obj is None:
            raise self.not_found("Workflow introuvable")
        await self._timeline(str(wf.id), "workflow_suspended", "Workflow suspendu", actor_id)
        return obj

    async def delete(self, id: str) -> bool:
        await self.get_by_id(id)
        return await self.repo.delete(id)

    # ── Workflow Details ──────────────────────────────────────────────────────

    async def list_details(self, workflow_id: str):
        items, _ = await self.detail_repo.list_by_workflow(workflow_id)
        return items

    async def list_root_nodes(self, workflow_id: str):
        return await self.detail_repo.list_root_nodes(workflow_id)

    async def list_children(self, parent_id: str):
        return await self.detail_repo.list_children(parent_id)

    async def get_detail_by_id(self, id: str):
        obj = await self.detail_repo.get_by_id(id)
        if obj is None:
            raise self.not_found("Détail de workflow introuvable")
        return obj

    async def create_detail(self, data: dict):
        return await self.detail_repo.create(data)

    async def update_detail(self, id: str, data: dict):
        obj = await self.detail_repo.update(id, data)
        if obj is None:
            raise self.not_found("Détail de workflow introuvable")
        return obj

    async def create_circuit(
        self,
        workflow_id: str,
        steps: list[dict],
    ) -> list:
        """
        Crée toutes les étapes d'un circuit en une fois.
        La première étape est automatiquement activée (activated=True).
        Les suivantes restent en attente (activated=False).
        """
        if not steps:
            raise self.bad_request("Un circuit doit contenir au moins une étape.")

        created = []
        for i, step in enumerate(steps):
            step["workflow_id"] = int(workflow_id)
            step["activated"] = i == 0
            step["accepted"] = None  # None = en attente (comme edgrh)
            obj = await self.detail_repo.create(step)
            created.append(obj)
        return created

    async def accept_detail(
        self,
        id: str,
        *,
        agent_id: str | None = None,
        actor_name: str | None = None,
        actor_role: str | None = None,
        actor=None,
        accepted: bool = True,
        comment: str | None = None,
    ):
        """
        Accepte ou refuse une étape du workflow.

        - Acceptée → active l'étape suivante. Si dernière → workflow 'completed'.
        - Refusée  → workflow 'suspended', timeline journalisée.
        """
        clean_comment = comment.strip() if isinstance(comment, str) else None
        if not accepted and not clean_comment:
            raise self.bad_request(
                "Un motif est obligatoire pour refuser une étape workflow.",
                field="comment",
            )

        current = await self.get_detail_by_id(id)
        await self._assert_detail_decision_allowed(current, actor)

        obj = await self.detail_repo.accept(
            id, agent_id=agent_id, accepted=accepted, comment=clean_comment
        )
        if obj is None:
            raise self.not_found("Détail de workflow introuvable")

        wf = await self.repo.get_by_id(str(obj.workflow_id))
        old_workflow_status = getattr(wf, "workflow_status", None) if wf else None
        base_infos = {
            "workflow_detail_id": str(obj.id),
            "step_id": str(obj.id),
            "accepted": accepted,
            "old_workflow_status": old_workflow_status,
        }

        if accepted:
            next_step = await self.detail_repo.find_next_to_activate(
                workflow_id=obj.workflow_id, after_id=obj.id
            )
            if next_step:
                await self.detail_repo.activate_node(str(next_step.id))
                if wf:
                    await self._timeline(
                        str(wf.id),
                        "workflow_step_accepted",
                        "Étape validée — passage à l'étape suivante",
                        agent_id,
                        actor_name=actor_name,
                        actor_role=actor_role,
                        comment=clean_comment,
                        infos={
                            **base_infos,
                            "new_workflow_status": old_workflow_status,
                            "next_step_id": str(next_step.id),
                        },
                    )
            else:
                if wf:
                    await self.repo.complete(str(wf.id))
                    await self._timeline(
                        str(wf.id),
                        "workflow_step_accepted",
                        "Étape validée — dernière étape",
                        agent_id,
                        actor_name=actor_name,
                        actor_role=actor_role,
                        comment=clean_comment,
                        infos={
                            **base_infos,
                            "new_workflow_status": "completed",
                        },
                    )
                    await self._timeline(
                        str(wf.id),
                        "workflow_completed",
                        "Toutes les étapes validées — workflow complété",
                        agent_id,
                        actor_name=actor_name,
                        actor_role=actor_role,
                        infos={
                            "workflow_detail_id": str(obj.id),
                            "old_workflow_status": old_workflow_status,
                            "new_workflow_status": "completed",
                        },
                    )
        else:
            if wf:
                await self.repo.suspend(str(wf.id))
                await self._timeline(
                    str(wf.id),
                    "workflow_step_rejected",
                    "Étape refusée — workflow suspendu",
                    agent_id,
                    actor_name=actor_name,
                    actor_role=actor_role,
                    comment=clean_comment,
                    infos={
                        **base_infos,
                        "new_workflow_status": "suspended",
                    },
                )

        return obj

    async def search_workflows(
        self,
        *,
        request_id: int | None = None,
        workflow_status: str | None = None,
        uuid: str | None = None,
        page: int = 1,
        limit: int = 50,
    ):
        """Recherche multi-critères workflows (pattern edgrh WorkflowRouter /search/)."""
        items, total = await self.repo.search(
            request_id=request_id,
            workflow_status=workflow_status,
            uuid=uuid,
            page=page,
            limit=limit,
        )
        return self.paginate(items, total, page, limit)

    async def search_details(
        self,
        *,
        workflow_id: int | None = None,
        agent_id: int | None = None,
        unit_id: int | None = None,
        activated: bool | None = None,
        accepted: bool | None = None,
        page: int = 1,
        limit: int = 100,
    ):
        """Recherche multi-critères étapes (pattern edgrh DetailWorkflowRouter /search/)."""
        items, total = await self.detail_repo.search(
            workflow_id=workflow_id,
            agent_id=agent_id,
            unit_id=unit_id,
            activated=activated,
            accepted=accepted,
            page=page,
            limit=limit,
        )
        return self.paginate(items, total, page, limit)

    async def restore_workflow(self, id: str):
        """Restaure un workflow soft-deleted (pattern edgrh WorkflowRouter /restore/{id})."""
        ok = await self.repo.restore(int(id))
        if not ok:
            raise self.not_found("Workflow introuvable ou non supprimé")
        return await self.repo.get_by_id(int(id), include_deleted=False)

    async def restore_detail(self, id: str):
        """Restaure une étape soft-deleted."""
        ok = await self.detail_repo.restore(int(id))
        if not ok:
            raise self.not_found("Étape introuvable ou non supprimée")
        return await self.detail_repo.get_by_id(int(id), include_deleted=False)

    async def get_current_step(self, workflow_id: str):
        """Retourne l'étape active en attente de décision (activated=True, accepted=False)."""
        return await self.detail_repo.get_current_step(workflow_id)

    async def activate_detail_node(self, id: str):
        obj = await self.detail_repo.activate_node(id)
        if obj is None:
            raise self.not_found("Détail de workflow introuvable")
        return obj

    # ── Auto-circuit (pattern edgrh DemandService.create_workflow_demand) ─────

    async def create_for_request_with_auto_circuit(
        self,
        request_id: str,
        *,
        unit_id: int | None = None,
        direction_id: int | None = None,
        workflow_status: str = "active",
        actor_id: str | None = None,
    ) -> dict:
        """
        Crée un workflow + circuit de validation automatique basé sur la
        hiérarchie de l'unité/direction de la demande.

        Ordre des étapes (reproduit edgrh annual_meeting / chiefs_by_units) :
          1. Chefs d'unité (role='chief', unit_id fourni)
          2. Directeurs de direction (role='director', direction_id fourni)

        La première étape est activée automatiquement.
        Retourne {"workflow": ..., "steps": [...]}.
        """
        from api.repositories import AccountRepository

        account_repo = AccountRepository(self.session)

        # 1. Créer le workflow
        wf = await self.repo.create({
            "request_id": int(request_id),
            "workflow_status": workflow_status,
        })

        # 2. Trouver les approbateurs selon la hiérarchie
        approvers = await account_repo.find_approvers_for_request(
            unit_id=unit_id, direction_id=direction_id
        )

        # 3. Construire les étapes
        steps_data = []
        for i, approver in enumerate(approvers):
            steps_data.append({
                "workflow_id": wf.id,
                "agent_id": approver.id,
                "unity_id": unit_id if approver.unit_id == unit_id else None,
                "activated": i == 0,
                "accepted": None,
                "label": f"Validation — {approver.name}",
                "actor_name": approver.name,
            })

        created_steps = await self.detail_repo.create_bulk(steps_data) if steps_data else []

        # 4. Événement timeline
        await self._timeline(
            str(wf.id),
            "workflow_started",
            f"Circuit automatique démarré ({len(created_steps)} étape(s))",
            actor_id,
        )

        return {"workflow": wf, "steps": created_steps}
