"""
Routes pour les 14 tables de référence — CRUD standard + restore.
Préfixe : /references/{resource}
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_current_user, require_roles
from api.core.enums import (
    WorkflowStatusEnum, RequestSourceEnum, TaskTypeEnum, TaskStatusEnum,
)
from api.services import (
    RequestStatusService,
    RequestCategoryService,
    PriorityDefinitionService,
)

router = APIRouter(
    prefix="/references",
    tags=["references"],
    dependencies=[Depends(get_current_user)],
)

_admin = Depends(require_roles("admin"))


# ── Chargement global (startup frontend) ──────────────────────────────────────

@router.get("/all")
async def get_all_references(db: AsyncSession = Depends(get_db)):
    """
    Retourne toutes les tables de référence en un seul appel.
    Utilisé par le frontend au démarrage pour pré-charger les dropdowns.
    """
    return {
        "request_statuses":        await RequestStatusService(db).list_all(),
        "request_sources":         [e.value for e in RequestSourceEnum],
        "request_categories":      await RequestCategoryService(db).list_all(),
        "workflow_statuses":       [e.value for e in WorkflowStatusEnum],
        "task_types":              [e.value for e in TaskTypeEnum],
        "task_statuses":           [e.value for e in TaskStatusEnum],
        "priority_definitions":    await PriorityDefinitionService(db).list_all(),
    }


# ── Request statuses ──────────────────────────────────────────────────────────

@router.get("/request-statuses")
async def list_request_statuses(db: AsyncSession = Depends(get_db)):
    return await RequestStatusService(db).list_all()


@router.get("/request-statuses/{id}")
async def get_request_status(id: int, db: AsyncSession = Depends(get_db)):
    return await RequestStatusService(db).get_by_id(id)


@router.post("/request-statuses", status_code=status.HTTP_201_CREATED, dependencies=[_admin])
async def create_request_status(data: dict, db: AsyncSession = Depends(get_db)):
    return await RequestStatusService(db).create(data)


@router.put("/request-statuses/{id}", dependencies=[_admin])
async def update_request_status(id: int, data: dict, db: AsyncSession = Depends(get_db)):
    return await RequestStatusService(db).update(id, data)


@router.delete("/request-statuses/{id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[_admin])
async def delete_request_status(id: int, db: AsyncSession = Depends(get_db)):
    await RequestStatusService(db).delete(id)


@router.put("/request-statuses/{id}/restore", dependencies=[_admin])
async def restore_request_status(id: int, db: AsyncSession = Depends(get_db)):
    return await RequestStatusService(db).restore(id)


# ── Request sources (enum statique) ──────────────────────────────────────────

@router.get("/request-sources")
async def list_request_sources():
    return [{"code": e.value} for e in RequestSourceEnum]


# ── Request categories ────────────────────────────────────────────────────────

@router.get("/request-categories")
async def list_request_categories(db: AsyncSession = Depends(get_db)):
    return await RequestCategoryService(db).list_all()


@router.get("/request-categories/{id}")
async def get_request_category(id: int, db: AsyncSession = Depends(get_db)):
    return await RequestCategoryService(db).get_by_id(id)


@router.post("/request-categories", status_code=status.HTTP_201_CREATED, dependencies=[_admin])
async def create_request_category(data: dict, db: AsyncSession = Depends(get_db)):
    return await RequestCategoryService(db).create(data)


@router.put("/request-categories/{id}", dependencies=[_admin])
async def update_request_category(id: int, data: dict, db: AsyncSession = Depends(get_db)):
    return await RequestCategoryService(db).update(id, data)


@router.delete("/request-categories/{id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[_admin])
async def delete_request_category(id: int, db: AsyncSession = Depends(get_db)):
    await RequestCategoryService(db).delete(id)


@router.put("/request-categories/{id}/restore", dependencies=[_admin])
async def restore_request_category(id: int, db: AsyncSession = Depends(get_db)):
    return await RequestCategoryService(db).restore(id)


# ── Workflow statuses (enum statique) ────────────────────────────────────────

@router.get("/workflow-statuses")
async def list_workflow_statuses():
    return [{"code": e.value} for e in WorkflowStatusEnum]


# ── Task types (enum statique) ────────────────────────────────────────────────

@router.get("/task-types")
async def list_task_types():
    return [{"code": e.value} for e in TaskTypeEnum]


# ── Task statuses (enum statique) ─────────────────────────────────────────────

@router.get("/task-statuses")
async def list_task_statuses():
    return [{"code": e.value} for e in TaskStatusEnum]


# ── Priority definitions ──────────────────────────────────────────────────────

@router.get("/priority-definitions")
async def list_priority_definitions(db: AsyncSession = Depends(get_db)):
    return await PriorityDefinitionService(db).list_all()


@router.get("/priority-definitions/{id}")
async def get_priority_definition(id: int, db: AsyncSession = Depends(get_db)):
    return await PriorityDefinitionService(db).get_by_id(id)


@router.post("/priority-definitions", status_code=status.HTTP_201_CREATED, dependencies=[_admin])
async def create_priority_definition(data: dict, db: AsyncSession = Depends(get_db)):
    return await PriorityDefinitionService(db).create(data)


@router.put("/priority-definitions/{id}", dependencies=[_admin])
async def update_priority_definition(id: int, data: dict, db: AsyncSession = Depends(get_db)):
    return await PriorityDefinitionService(db).update(id, data)


@router.delete("/priority-definitions/{id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[_admin])
async def delete_priority_definition(id: int, db: AsyncSession = Depends(get_db)):
    await PriorityDefinitionService(db).delete(id)


@router.put("/priority-definitions/{id}/restore", dependencies=[_admin])
async def restore_priority_definition(id: int, db: AsyncSession = Depends(get_db)):
    return await PriorityDefinitionService(db).restore(id)


@router.post("/priority-definitions/reorder", dependencies=[_admin])
async def reorder_priority_definitions(ordered_ids: list[int], db: AsyncSession = Depends(get_db)):
    return await PriorityDefinitionService(db).reorder(ordered_ids)
