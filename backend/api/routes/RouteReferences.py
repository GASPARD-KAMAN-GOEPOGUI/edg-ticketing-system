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
    AccountStatusService,
    KnowledgeCategoryService,
    AnnouncementCategoryService,
    AnnouncementPriorityService,
    AnnouncementStatusService,
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
        "account_statuses":        await AccountStatusService(db).list_all(),
        "knowledge_categories":    await KnowledgeCategoryService(db).list_all(),
        "announcement_categories": await AnnouncementCategoryService(db).list_all(),
        "announcement_priorities": await AnnouncementPriorityService(db).list_all(),
        "announcement_statuses":   await AnnouncementStatusService(db).list_all(),
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


# ── Account statuses ──────────────────────────────────────────────────────────

@router.get("/account-statuses")
async def list_account_statuses(db: AsyncSession = Depends(get_db)):
    return await AccountStatusService(db).list_all()


@router.get("/account-statuses/{id}")
async def get_account_status(id: int, db: AsyncSession = Depends(get_db)):
    return await AccountStatusService(db).get_by_id(id)


@router.post("/account-statuses", status_code=status.HTTP_201_CREATED, dependencies=[_admin])
async def create_account_status(data: dict, db: AsyncSession = Depends(get_db)):
    return await AccountStatusService(db).create(data)


@router.put("/account-statuses/{id}", dependencies=[_admin])
async def update_account_status(id: int, data: dict, db: AsyncSession = Depends(get_db)):
    return await AccountStatusService(db).update(id, data)


@router.delete("/account-statuses/{id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[_admin])
async def delete_account_status(id: int, db: AsyncSession = Depends(get_db)):
    await AccountStatusService(db).delete(id)


@router.put("/account-statuses/{id}/restore", dependencies=[_admin])
async def restore_account_status(id: int, db: AsyncSession = Depends(get_db)):
    return await AccountStatusService(db).restore(id)


# ── Knowledge categories ──────────────────────────────────────────────────────

@router.get("/knowledge-categories")
async def list_knowledge_categories(db: AsyncSession = Depends(get_db)):
    return await KnowledgeCategoryService(db).list_all()


@router.get("/knowledge-categories/{id}")
async def get_knowledge_category(id: int, db: AsyncSession = Depends(get_db)):
    return await KnowledgeCategoryService(db).get_by_id(id)


@router.post("/knowledge-categories", status_code=status.HTTP_201_CREATED, dependencies=[_admin])
async def create_knowledge_category(data: dict, db: AsyncSession = Depends(get_db)):
    return await KnowledgeCategoryService(db).create(data)


@router.put("/knowledge-categories/{id}", dependencies=[_admin])
async def update_knowledge_category(id: int, data: dict, db: AsyncSession = Depends(get_db)):
    return await KnowledgeCategoryService(db).update(id, data)


@router.delete("/knowledge-categories/{id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[_admin])
async def delete_knowledge_category(id: int, db: AsyncSession = Depends(get_db)):
    await KnowledgeCategoryService(db).delete(id)


@router.put("/knowledge-categories/{id}/restore", dependencies=[_admin])
async def restore_knowledge_category(id: int, db: AsyncSession = Depends(get_db)):
    return await KnowledgeCategoryService(db).restore(id)


# ── Announcement categories ───────────────────────────────────────────────────

@router.get("/announcement-categories")
async def list_announcement_categories(db: AsyncSession = Depends(get_db)):
    return await AnnouncementCategoryService(db).list_all()


@router.get("/announcement-categories/{id}")
async def get_announcement_category(id: int, db: AsyncSession = Depends(get_db)):
    return await AnnouncementCategoryService(db).get_by_id(id)


@router.post("/announcement-categories", status_code=status.HTTP_201_CREATED, dependencies=[_admin])
async def create_announcement_category(data: dict, db: AsyncSession = Depends(get_db)):
    return await AnnouncementCategoryService(db).create(data)


@router.put("/announcement-categories/{id}", dependencies=[_admin])
async def update_announcement_category(id: int, data: dict, db: AsyncSession = Depends(get_db)):
    return await AnnouncementCategoryService(db).update(id, data)


@router.delete("/announcement-categories/{id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[_admin])
async def delete_announcement_category(id: int, db: AsyncSession = Depends(get_db)):
    await AnnouncementCategoryService(db).delete(id)


@router.put("/announcement-categories/{id}/restore", dependencies=[_admin])
async def restore_announcement_category(id: int, db: AsyncSession = Depends(get_db)):
    return await AnnouncementCategoryService(db).restore(id)


# ── Announcement priorities ───────────────────────────────────────────────────

@router.get("/announcement-priorities")
async def list_announcement_priorities(db: AsyncSession = Depends(get_db)):
    return await AnnouncementPriorityService(db).list_all()


@router.get("/announcement-priorities/{id}")
async def get_announcement_priority(id: int, db: AsyncSession = Depends(get_db)):
    return await AnnouncementPriorityService(db).get_by_id(id)


@router.post("/announcement-priorities", status_code=status.HTTP_201_CREATED, dependencies=[_admin])
async def create_announcement_priority(data: dict, db: AsyncSession = Depends(get_db)):
    return await AnnouncementPriorityService(db).create(data)


@router.put("/announcement-priorities/{id}", dependencies=[_admin])
async def update_announcement_priority(id: int, data: dict, db: AsyncSession = Depends(get_db)):
    return await AnnouncementPriorityService(db).update(id, data)


@router.delete("/announcement-priorities/{id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[_admin])
async def delete_announcement_priority(id: int, db: AsyncSession = Depends(get_db)):
    await AnnouncementPriorityService(db).delete(id)


@router.put("/announcement-priorities/{id}/restore", dependencies=[_admin])
async def restore_announcement_priority(id: int, db: AsyncSession = Depends(get_db)):
    return await AnnouncementPriorityService(db).restore(id)


# ── Announcement statuses ─────────────────────────────────────────────────────

@router.get("/announcement-statuses")
async def list_announcement_statuses(db: AsyncSession = Depends(get_db)):
    return await AnnouncementStatusService(db).list_all()


@router.get("/announcement-statuses/{id}")
async def get_announcement_status(id: int, db: AsyncSession = Depends(get_db)):
    return await AnnouncementStatusService(db).get_by_id(id)


@router.post("/announcement-statuses", status_code=status.HTTP_201_CREATED, dependencies=[_admin])
async def create_announcement_status(data: dict, db: AsyncSession = Depends(get_db)):
    return await AnnouncementStatusService(db).create(data)


@router.put("/announcement-statuses/{id}", dependencies=[_admin])
async def update_announcement_status(id: int, data: dict, db: AsyncSession = Depends(get_db)):
    return await AnnouncementStatusService(db).update(id, data)


@router.delete("/announcement-statuses/{id}", status_code=status.HTTP_204_NO_CONTENT, dependencies=[_admin])
async def delete_announcement_status(id: int, db: AsyncSession = Depends(get_db)):
    await AnnouncementStatusService(db).delete(id)


@router.put("/announcement-statuses/{id}/restore", dependencies=[_admin])
async def restore_announcement_status(id: int, db: AsyncSession = Depends(get_db)):
    return await AnnouncementStatusService(db).restore(id)


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
