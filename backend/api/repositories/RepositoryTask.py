from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.ModelTask import Task
from api.repositories.base_repository import BaseRepository


class TaskRepository(BaseRepository[Task]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Task, session)

    async def list_by_request(
        self, request_id: str, *, page: int = 1, limit: int = 50
    ) -> tuple[list[Task], int]:
        return await self.list(
            filters={"request_id": request_id},
            order_by="-created_at",
            page=page,
            limit=limit,
        )

    async def list_by_workflow(
        self, workflow_id: str, *, page: int = 1, limit: int = 50
    ) -> tuple[list[Task], int]:
        from api.models.ModelWorkflow import Workflow
        from api.models.ModelWorkflowDetail import WorkflowDetail

        base_q = (
            select(Task)
            .join(WorkflowDetail, WorkflowDetail.task_id == Task.id)
            .join(Workflow, Workflow.id == WorkflowDetail.workflow_id)
            .where(
                Workflow.uuid == workflow_id,
                WorkflowDetail.deleted_at.is_(None),
                Task.deleted_at.is_(None),
            )
        )
        total = (
            await self.session.execute(select(func.count()).select_from(base_q.subquery()))
        ).scalar_one()
        offset = (page - 1) * limit
        rows = (
            await self.session.execute(
                base_q.order_by(Task.created_at).offset(offset).limit(limit)
            )
        ).scalars().all()
        return list(rows), total

    async def list_assigned_to_agent(
        self,
        agent_id: str,
        *,
        task_status: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[Task], int]:
        filters: dict = {"to_agent_id": agent_id}
        if task_status:
            filters["task_status"] = task_status
        return await self.list(
            filters=filters,
            order_by="-created_at",
            page=page,
            limit=limit,
        )

    async def list_pending(
        self, *, page: int = 1, limit: int = 20
    ) -> tuple[list[Task], int]:
        return await self.list(
            filters={"task_status": "pending"},
            order_by="created_at",
            page=page,
            limit=limit,
        )

    async def list_by_type(
        self, task_type: str, *, page: int = 1, limit: int = 20
    ) -> tuple[list[Task], int]:
        return await self.list(
            filters={"task_type": task_type},
            order_by="-created_at",
            page=page,
            limit=limit,
        )

    async def complete(self, id: str, *, resolution_note: str | None = None) -> Task | None:
        data: dict = {"task_status": "completed"}
        if resolution_note:
            data["infos"] = {"resolution_note": resolution_note}
        return await self.update(id, data)

    async def reject(self, id: str, *, rejection_reason: str | None = None) -> Task | None:
        data: dict = {"task_status": "rejected"}
        if rejection_reason:
            data["infos"] = {"rejection_reason": rejection_reason}
        return await self.update(id, data)

    async def approve(self, id: str) -> Task | None:
        return await self.update(id, {"task_status": "approved"})

    async def cancel(self, id: str) -> Task | None:
        return await self.update(id, {"task_status": "cancelled"})
