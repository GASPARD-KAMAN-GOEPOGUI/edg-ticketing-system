from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.ModelWorkflow import Workflow
from api.models.ModelWorkflowDetail import WorkflowDetail
from api.repositories.base_repository import BaseRepository


class WorkflowDetailRepository(BaseRepository[WorkflowDetail]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(WorkflowDetail, session)

    _AUDIT_INFO_KEYS = (
        "actor_id",
        "actor_role",
        "target_user_id",
        "target_role",
        "old_status",
        "new_status",
        "reason",
    )

    async def list_by_workflow(
        self, workflow_id: str, *, page: int = 1, limit: int = 100
    ) -> tuple[list[WorkflowDetail], int]:
        return await self.list(
            filters={"workflow_id": workflow_id},
            order_by="created_at",
            page=page,
            limit=limit,
        )

    async def list_root_nodes(self, workflow_id: str) -> list[WorkflowDetail]:
        """Retourne les nœuds racines (parent_id IS NULL)."""
        stmt = (
            select(WorkflowDetail)
            .where(WorkflowDetail.workflow_id == workflow_id)
            .where(WorkflowDetail.parent_id.is_(None))
            .where(WorkflowDetail.deleted_at.is_(None))
            .order_by(WorkflowDetail.created_at)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def list_children(self, parent_id: str) -> list[WorkflowDetail]:
        """Retourne les nœuds enfants d'un nœud parent."""
        items, _ = await self.list(
            filters={"parent_id": parent_id},
            order_by="created_at",
            limit=100,
        )
        return items

    async def get_current_step(self, workflow_id: str) -> WorkflowDetail | None:
        """Retourne l'étape active en attente de décision (activated=True, accepted IS NULL)."""
        stmt = (
            select(WorkflowDetail)
            .where(WorkflowDetail.workflow_id == int(workflow_id))
            .where(WorkflowDetail.activated == True)   # noqa: E712
            .where(WorkflowDetail.accepted.is_(None))
            .where(WorkflowDetail.deleted_at.is_(None))
            .order_by(WorkflowDetail.id)
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def find_next_to_activate(self, workflow_id: int, after_id: int) -> WorkflowDetail | None:
        """Retourne la prochaine étape non encore activée (activated=False), après after_id."""
        stmt = (
            select(WorkflowDetail)
            .where(WorkflowDetail.workflow_id == workflow_id)
            .where(WorkflowDetail.activated == False)  # noqa: E712
            .where(WorkflowDetail.deleted_at.is_(None))
            .where(WorkflowDetail.id > after_id)
            .order_by(WorkflowDetail.id)
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def accept(
        self,
        id: str,
        *,
        agent_id: str | None = None,
        accepted: bool = True,
        comment: str | None = None,
    ) -> WorkflowDetail | None:
        data: dict = {"accepted": accepted, "activated": True}
        if agent_id:
            data["agent_id"] = agent_id
        if comment is not None:
            data["comment"] = comment
        return await self.update(id, data)

    async def activate_node(self, id: str) -> WorkflowDetail | None:
        return await self.update(id, {"activated": True})

    async def create_bulk(self, steps: list[dict]) -> list[WorkflowDetail]:
        """Insère plusieurs étapes en une seule transaction."""
        created = []
        for step in steps:
            obj = await self.create(step)
            created.append(obj)
        return created

    async def list_by_agent(
        self, agent_id: str, *, page: int = 1, limit: int = 20
    ) -> tuple[list[WorkflowDetail], int]:
        return await self.list(
            filters={"agent_id": agent_id},
            order_by="-created_at",
            page=page,
            limit=limit,
        )

    async def list_by_request(
        self, request_id: str, *, page: int = 1, limit: int = 200
    ) -> list[WorkflowDetail]:
        """Retourne tous les événements de timeline d'une demande via le workflow."""
        stmt = (
            select(WorkflowDetail)
            .join(Workflow, WorkflowDetail.workflow_id == Workflow.id)
            .where(Workflow.request_id == int(request_id))
            .where(WorkflowDetail.deleted_at.is_(None))
            .order_by(WorkflowDetail.created_at)
            .offset((page - 1) * limit)
            .limit(limit)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())

    async def search(
        self,
        *,
        workflow_id: int | None = None,
        agent_id: int | None = None,
        unit_id: int | None = None,
        activated: bool | None = None,
        accepted: bool | None = None,
        page: int = 1,
        limit: int = 100,
    ) -> tuple[list[WorkflowDetail], int]:
        """Recherche multi-critères (pattern edgrh DetailWorkflowRepo.get_search)."""
        filters: dict = {}
        if workflow_id is not None:
            filters["workflow_id"] = workflow_id
        if agent_id is not None:
            filters["agent_id"] = agent_id
        if unit_id is not None:
            filters["unit_id"] = unit_id
        if activated is not None:
            filters["activated"] = activated
        if accepted is not None:
            filters["accepted"] = accepted
        return await self.list(
            filters=filters if filters else None,
            order_by="created_at",
            page=page,
            limit=limit,
        )

    async def _get_last_event_id(self, workflow_id: int) -> int | None:
        """Retourne l'ID du dernier événement créé pour ce workflow (pour chaînage parent_id)."""
        stmt = (
            select(WorkflowDetail.id)
            .where(WorkflowDetail.workflow_id == workflow_id)
            .where(WorkflowDetail.deleted_at.is_(None))
            .order_by(WorkflowDetail.id.desc())
            .limit(1)
        )
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def create_event(self, data: dict) -> WorkflowDetail:
        """
        Insère un événement de timeline dans le journal du workflow.

        Champs supportés :
          workflow_id  — obligatoire
          event_type   — type d'événement (created, routed_to_service, assigned…)
          label        — description lisible de l'événement
          actor_id     — ID de l'acteur source (requérant, agent, chef…)
          actor_name   — nom lisible de l'acteur source
          dest_id      — ID de l'acteur destination (chef, support…). Si fourni,
                         agent_id = dest_id et actor_id est conservé dans infos.
          unity_id     — unité organisationnelle du contexte de l'événement
          comment      — commentaire libre
          infos        — métadonnées JSON additionnelles
          activated    — booléen (défaut False)

        parent_id est résolu automatiquement : pointe vers le dernier événement
        du même workflow (chaîne linéaire). NULL uniquement pour le premier événement.
        """
        infos: dict = dict(data.get("infos") or {})
        dest_id = data.get("dest_id")
        actor_id = data.get("actor_id")
        comment = data.get("comment")

        if actor_id:
            infos.setdefault("actor_id", str(actor_id))
        if infos.get("source_role") and not infos.get("actor_role"):
            infos["actor_role"] = infos.get("source_role")

        if dest_id:
            # Routing event : dest_id = destinataire, actor_id conservé dans infos
            agent_id_val = dest_id
            infos.setdefault("target_user_id", str(dest_id))
        else:
            # Événement standard : acteur = agent_id
            agent_id_val = actor_id

        if infos.get("dest_role") and not infos.get("target_role"):
            infos["target_role"] = infos.get("dest_role")
        if comment and not infos.get("reason") and data.get("event_type") != "comment_added":
            infos["reason"] = comment
        for key in self._AUDIT_INFO_KEYS:
            infos.setdefault(key, None)

        # Chaînage automatique : parent_id = dernier événement du workflow
        workflow_id = data.get("workflow_id")
        if "parent_id" in data:
            parent_id = data["parent_id"]
        elif workflow_id:
            parent_id = await self._get_last_event_id(int(workflow_id))
        else:
            parent_id = None

        return await self.create({
            "workflow_id": workflow_id,
            "event_type": data.get("event_type"),
            "label": data.get("label"),
            "agent_id": agent_id_val,
            "unity_id": data.get("unity_id"),
            "actor_name": data.get("actor_name"),
            "comment": comment,
            "infos": infos,
            "parent_id": parent_id,
            "activated": data.get("activated", False),
        })

    async def list_comments_by_request(
        self, request_id: str, *, public_only: bool = False
    ) -> list[WorkflowDetail]:
        """Retourne les commentaires (event_type='comment_added') d'une demande via son workflow."""
        stmt = (
            select(WorkflowDetail)
            .join(Workflow, WorkflowDetail.workflow_id == Workflow.id)
            .where(Workflow.request_id == int(request_id))
            .where(WorkflowDetail.event_type == "comment_added")
            .where(WorkflowDetail.deleted_at.is_(None))
            .order_by(WorkflowDetail.created_at)
        )
        result = await self.session.execute(stmt)
        items = list(result.scalars().all())
        if public_only:
            # infos = {"is_public": True/False}
            items = [
                e for e in items
                if isinstance(e.infos, dict) and e.infos.get("is_public", False)
            ]
        return items

    async def get_comment_by_id_for_request(
        self, comment_id: str, request_id: str
    ) -> WorkflowDetail | None:
        """Retourne un commentaire (event_type='comment_added') seulement s'il appartient
        au workflow de cette demande — utilisé pour valider reply_to_id (C-05.1)."""
        stmt = (
            select(WorkflowDetail)
            .join(Workflow, WorkflowDetail.workflow_id == Workflow.id)
            .where(WorkflowDetail.id == int(comment_id))
            .where(Workflow.request_id == int(request_id))
            .where(WorkflowDetail.event_type == "comment_added")
            .where(WorkflowDetail.deleted_at.is_(None))
        )
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_escalations_by_request(
        self, request_id: str
    ) -> list[WorkflowDetail]:
        """Retourne les escalades manuelles (event_type='escalation_manual') d'une demande."""
        stmt = (
            select(WorkflowDetail)
            .join(Workflow, WorkflowDetail.workflow_id == Workflow.id)
            .where(Workflow.request_id == int(request_id))
            .where(WorkflowDetail.event_type == "escalation_manual")
            .where(WorkflowDetail.deleted_at.is_(None))
            .order_by(WorkflowDetail.created_at)
        )
        result = await self.session.execute(stmt)
        return list(result.scalars().all())
