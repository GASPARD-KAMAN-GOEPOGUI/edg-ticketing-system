from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from api.core.event_bus import AppEvent, emit as emit_event
from api.repositories import TaskRepository, WorkflowDetailRepository, WorkflowRepository
from api.services.base_service import BaseService


class TaskService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.repo = TaskRepository(session)
        self.detail_repo = WorkflowDetailRepository(session)
        self.wf_repo = WorkflowRepository(session)

    async def _timeline(
        self, request_id: str, event_type: str, label: str, actor_id: str | None = None
    ) -> None:
        wf = await self.wf_repo.find_active_workflow(str(request_id))
        if wf is None:
            return
        await self.detail_repo.create_event({
            "workflow_id": str(wf.id),
            "event_type": event_type,
            "label": label,
            "actor_id": actor_id,
        })

    async def list_all(self, *, page: int = 1, limit: int = 20):
        items, total = await self.repo.list(order_by="-created_at", page=page, limit=limit)
        return self.paginate(items, total, page, limit)

    async def list_by_request(self, request_id: str, *, page: int = 1, limit: int = 50):
        items, total = await self.repo.list_by_request(request_id, page=page, limit=limit)
        return self.paginate(items, total, page, limit)

    async def list_by_workflow(self, workflow_id: str, *, page: int = 1, limit: int = 50):
        items, total = await self.repo.list_by_workflow(workflow_id, page=page, limit=limit)
        return self.paginate(items, total, page, limit)

    async def list_assigned_to(self, agent_id: str, *, page: int = 1, limit: int = 20):
        items, total = await self.repo.list_assigned_to_agent(agent_id, page=page, limit=limit)
        return self.paginate(items, total, page, limit)

    async def list_pending(self, *, page: int = 1, limit: int = 20):
        items, total = await self.repo.list_pending(page=page, limit=limit)
        return self.paginate(items, total, page, limit)

    async def list_by_type(self, task_type: str, *, page: int = 1, limit: int = 20):
        items, total = await self.repo.list_by_type(task_type, page=page, limit=limit)
        return self.paginate(items, total, page, limit)

    async def get_by_id(self, id: str):
        obj = await self.repo.get_by_id(id)
        if obj is None:
            raise self.not_found("Tâche introuvable")
        return obj

    async def create(self, data: dict, *, actor_id: str | None = None):
        obj = await self.repo.create(data)
        label = f"Tâche {obj.task_type} créée"
        await self._timeline(obj.request_id, f"task_{obj.task_type}", label, actor_id)
        await emit_event(AppEvent(
            type="task.created",
            payload={"id": obj.id, "request_id": obj.request_id, "task_type": obj.task_type},
            target={"roles": ["agent", "chief", "admin"]},
        ))
        return obj

    async def update(self, id: str, data: dict):
        obj = await self.repo.update(id, data)
        if obj is None:
            raise self.not_found("Tâche introuvable")
        return obj

    async def complete(
        self, id: str, *, resolution_note: str | None = None, actor_id: str | None = None
    ):
        task = await self.get_by_id(id)
        obj = await self.repo.complete(id, resolution_note=resolution_note)
        if obj is None:
            raise self.not_found("Tâche introuvable")
        await self._timeline(task.request_id, "task_completed", "Tâche complétée", actor_id)
        await emit_event(AppEvent(
            type="task.completed",
            payload={"id": id, "request_id": task.request_id},
            target={"roles": ["agent", "chief", "admin"]},
        ))
        return obj

    async def reject(
        self, id: str, *, rejection_reason: str | None = None, actor_id: str | None = None
    ):
        task = await self.get_by_id(id)
        obj = await self.repo.reject(id, rejection_reason=rejection_reason)
        if obj is None:
            raise self.not_found("Tâche introuvable")
        await self._timeline(task.request_id, "task_rejected", "Tâche rejetée", actor_id)
        return obj

    async def approve(self, id: str, *, actor_id: str | None = None):
        task = await self.get_by_id(id)
        obj = await self.repo.approve(id)
        if obj is None:
            raise self.not_found("Tâche introuvable")
        await self._timeline(task.request_id, "task_approved", "Tâche approuvée", actor_id)
        return obj

    async def cancel(self, id: str, *, actor_id: str | None = None):
        task = await self.get_by_id(id)
        obj = await self.repo.cancel(id)
        if obj is None:
            raise self.not_found("Tâche introuvable")
        await self._timeline(task.request_id, "task_cancelled", "Tâche annulée", actor_id)
        return obj

    async def delete(self, id: str) -> bool:
        await self.get_by_id(id)
        return await self.repo.delete(id)
