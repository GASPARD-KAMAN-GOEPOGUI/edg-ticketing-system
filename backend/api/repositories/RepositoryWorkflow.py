from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from api.models.ModelWorkflow import Workflow
from api.repositories.base_repository import BaseRepository


class WorkflowRepository(BaseRepository[Workflow]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Workflow, session)

    async def find_by_request(self, request_id: str) -> list[Workflow]:
        items, _ = await self.list(
            filters={"request_id": request_id},
            order_by="-created_at",
            limit=50,
        )
        return items

    async def find_active_workflow(
        self, request_id: str
    ) -> Workflow | None:
        """Retourne le workflow actif d'une requête."""
        return await self.get_one(
            {"request_id": request_id, "workflow_status": "active"}
        )

    async def complete(self, id: str) -> Workflow | None:
        return await self.update(id, {"workflow_status": "completed"})

    async def suspend(self, id: str) -> Workflow | None:
        return await self.update(id, {"workflow_status": "suspended"})

    async def search(
        self,
        *,
        request_id: int | None = None,
        workflow_status: str | None = None,
        uuid: str | None = None,
        page: int = 1,
        limit: int = 50,
    ) -> tuple[list[Workflow], int]:
        """Recherche multi-critères (pattern edgrh WorkflowRepo.get_search)."""
        filters: dict = {}
        if request_id is not None:
            filters["request_id"] = request_id
        if workflow_status is not None:
            filters["workflow_status"] = workflow_status
        if uuid is not None:
            filters["uuid"] = uuid
        return await self.list(
            filters=filters if filters else None,
            order_by="-created_at",
            page=page,
            limit=limit,
        )
