"""
Routeur admin config — /api/v1/admin/*

Endpoints :
  /admin/sla          — CRUD + toggle des politiques SLA
  /admin/priorities   — CRUD + reorder des niveaux de priorité (is_builtin protégé)
  /admin/routing      — CRUD + toggle + reorder + apply test des règles de routage
  /admin/ref/:table   — CRUD des 14 tables de référence dynamiques (is_builtin protégé)

TODO auth: vérifier rôle admin sur tous les endpoints
"""
from __future__ import annotations

from typing import Any, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, require_roles
from api.services.ServiceSlaPolicy import SlaPolicyService
from api.services.ServiceRoutingRule import RoutingRuleService
from api.services.ServiceReferences import (
    RequestStatusService,
    RequestCategoryService,
    AccountStatusService,
    KnowledgeCategoryService,
    AnnouncementCategoryService,
    AnnouncementPriorityService,
    AnnouncementStatusService,
    PriorityDefinitionService,
)
from api.repositories import UnityRepository
from api.schemas.SchemaSlaPolicy import SlaPolicyCreate, SlaPolicyUpdate, SlaPolicyResponse
from api.schemas.SchemaPriorityDefinition import (
    PriorityDefinitionCreate,
    PriorityDefinitionUpdate,
    PriorityDefinitionResponse,
)

router = APIRouter(
    prefix="/admin",
    tags=["admin-config"],
    dependencies=[Depends(require_roles("admin"))],
)

# ── Helpers ───────────────────────────────────────────────────────────────────

def _sla_svc(db: AsyncSession = Depends(get_db)) -> SlaPolicyService:
    return SlaPolicyService(db)

def _prio_svc(db: AsyncSession = Depends(get_db)) -> PriorityDefinitionService:
    return PriorityDefinitionService(db)

def _routing_svc(db: AsyncSession = Depends(get_db)) -> RoutingRuleService:
    return RoutingRuleService(db)


# Table name → service factory mapping (14 tables de référence)
_REF_SERVICE_MAP = {
    "request_statuses":        lambda db: RequestStatusService(db),
    "request_categories":      lambda db: RequestCategoryService(db),
    "account_statuses":        lambda db: AccountStatusService(db),
    "knowledge_categories":    lambda db: KnowledgeCategoryService(db),
    "announcement_categories": lambda db: AnnouncementCategoryService(db),
    "announcement_priorities": lambda db: AnnouncementPriorityService(db),
    "announcement_statuses":   lambda db: AnnouncementStatusService(db),
}


def _get_ref_service(table: str, db: AsyncSession):
    factory = _REF_SERVICE_MAP.get(table)
    if factory is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Table de référence '{table}' inconnue",
        )
    return factory(db)


def _fmt_rule(rule) -> dict:
    _infos = rule.infos or {}
    codename = rule.target_unity_codename or _infos.get("target_unity_codename")
    label = rule.target_unity_label or _infos.get("target_unity_label") or codename
    dir_id = rule.target_unity_direction_id or _infos.get("target_unity_direction_id")
    return {
        "id": rule.id,
        "name": rule.name,
        "condition_field": rule.condition_field,
        "condition_value": rule.condition_value,
        "target_unity_id": rule.target_unity_id,
        "target_unity_codename": codename,
        "target_unity_label": label,
        "target_unity_direction_id": dir_id,
        "auto_assign": rule.auto_assign,
        "sort_order": rule.sort_order,
        "status": rule.status,
        "infos": _infos,
        "created_at": rule.created_at,
        "updated_at": rule.updated_at,
        "deleted_at": rule.deleted_at,
    }


async def _resolve_unity_id(unity_codename: str | None, db: AsyncSession) -> int | None:
    if not unity_codename:
        return None
    repo = UnityRepository(db)
    unity = await repo.find_by_codename(unity_codename)
    return unity.id if unity else None


async def _unity_direction_id(unity_id: int, db: AsyncSession) -> str | None:
    """Return the direction's unity_id for a given unit, via Organigram parent."""
    from sqlalchemy import select
    from api.models.ModelOrganigram import Organigram
    parent_org_id = (await db.execute(
        select(Organigram.parent_id)
        .where(Organigram.unity_id == unity_id)
        .where(Organigram.parent_id.isnot(None))
        .limit(1)
    )).scalar_one_or_none()
    if parent_org_id is None:
        return None
    dir_unity_id = (await db.execute(
        select(Organigram.unity_id)
        .where(Organigram.id == parent_org_id)
        .limit(1)
    )).scalar_one_or_none()
    return str(dir_unity_id) if dir_unity_id else None


# ── Schémas d'entrée routing ──────────────────────────────────────────────────

class RoutingRuleAdminCreate(BaseModel):
    name: str
    condition_field: str
    condition_value: str
    target_unity_codename: Optional[str] = None
    auto_assign: bool = False
    sort_order: int = 99
    status: bool = True


class RoutingRuleAdminUpdate(BaseModel):
    name: Optional[str] = None
    condition_field: Optional[str] = None
    condition_value: Optional[str] = None
    target_unity_codename: Optional[str] = None
    auto_assign: Optional[bool] = None
    sort_order: Optional[int] = None
    status: Optional[bool] = None


class ReorderRequest(BaseModel):
    ordered_ids: List[int]


class RefCreate(BaseModel):
    code: str
    label: str
    sort_order: int = 0
    infos: Optional[Any] = None


class RefUpdate(BaseModel):
    label: Optional[str] = None
    sort_order: Optional[int] = None
    status: Optional[bool] = None
    infos: Optional[Any] = None


# ═══════════════════════════════════════════════════════════════════════════════
# SLA Policies — /admin/sla
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/sla", response_model=List[SlaPolicyResponse])
async def list_sla(svc: SlaPolicyService = Depends(_sla_svc)):
    result = await svc.list_all()
    return result.items


@router.post("/sla", response_model=SlaPolicyResponse, status_code=status.HTTP_201_CREATED)
async def create_sla(body: SlaPolicyCreate, svc: SlaPolicyService = Depends(_sla_svc)):
    # TODO auth: rôle admin
    return await svc.create(body.dict())


@router.put("/sla/{id}", response_model=SlaPolicyResponse)
async def update_sla(id: int, body: SlaPolicyUpdate, svc: SlaPolicyService = Depends(_sla_svc)):
    # TODO auth: rôle admin
    return await svc.update(id, body.dict(exclude_none=True))


@router.put("/sla/{id}/toggle", response_model=SlaPolicyResponse)
async def toggle_sla(id: int, svc: SlaPolicyService = Depends(_sla_svc)):
    # TODO auth: rôle admin
    return await svc.toggle(id)


@router.delete("/sla/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_sla(id: int, svc: SlaPolicyService = Depends(_sla_svc)):
    # TODO auth: rôle admin
    await svc.delete(id)


# ═══════════════════════════════════════════════════════════════════════════════
# Priority Definitions — /admin/priorities
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/priorities", response_model=List[PriorityDefinitionResponse])
async def list_priorities(svc: PriorityDefinitionService = Depends(_prio_svc)):
    # TODO auth: rôle admin
    return await svc.list_all(only_active=None)


@router.post("/priorities", response_model=PriorityDefinitionResponse, status_code=status.HTTP_201_CREATED)
async def create_priority(body: PriorityDefinitionCreate, svc: PriorityDefinitionService = Depends(_prio_svc)):
    # TODO auth: rôle admin
    return await svc.create(body.dict())


@router.put("/priorities/reorder", status_code=status.HTTP_200_OK)
async def reorder_priorities(body: ReorderRequest, svc: PriorityDefinitionService = Depends(_prio_svc)):
    # TODO auth: rôle admin
    items = await svc.reorder(body.ordered_ids)
    return {"reordered": len(items)}


@router.put("/priorities/{id}", response_model=PriorityDefinitionResponse)
async def update_priority(id: int, body: PriorityDefinitionUpdate, svc: PriorityDefinitionService = Depends(_prio_svc)):
    # TODO auth: rôle admin
    return await svc.update(id, body.dict(exclude_none=True))


@router.delete("/priorities/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_priority(id: int, svc: PriorityDefinitionService = Depends(_prio_svc)):
    # TODO auth: rôle admin
    await svc.delete(id)


# ═══════════════════════════════════════════════════════════════════════════════
# Routing Rules — /admin/routing
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/routing")
async def list_routing(svc: RoutingRuleService = Depends(_routing_svc)):
    # TODO auth: rôle admin
    result = await svc.list_all()
    return {"items": [_fmt_rule(r) for r in result.items], "total": result.total}


@router.post("/routing", status_code=status.HTTP_201_CREATED)
async def create_routing(body: RoutingRuleAdminCreate, db: AsyncSession = Depends(get_db)):
    unity_id = await _resolve_unity_id(body.target_unity_codename, db)
    infos: dict = {}
    if body.target_unity_codename:
        infos["target_unity_codename"] = body.target_unity_codename
        repo = UnityRepository(db)
        unity = await repo.find_by_codename(body.target_unity_codename)
        if unity:
            infos["target_unity_label"] = unity.label or body.target_unity_codename
            dir_id = unity.parent_direction_id
            if dir_id is None:
                dir_id_str = await _unity_direction_id(unity.id, db)
            else:
                dir_id_str = str(dir_id)
            if dir_id_str:
                infos["target_unity_direction_id"] = dir_id_str
    svc = RoutingRuleService(db)
    rule = await svc.create({
        "name": body.name,
        "condition_field": body.condition_field,
        "condition_value": body.condition_value,
        "target_unity_id": unity_id,
        "auto_assign": body.auto_assign,
        "sort_order": body.sort_order,
        "status": body.status,
        "infos": infos or None,
    })
    return _fmt_rule(rule)


@router.put("/routing/reorder", status_code=status.HTTP_200_OK)
async def reorder_routing(body: ReorderRequest, svc: RoutingRuleService = Depends(_routing_svc)):
    # TODO auth: rôle admin
    items = await svc.reorder(body.ordered_ids)
    return {"reordered": len(items)}


@router.post("/routing/apply")
async def apply_routing_test(body: dict, svc: RoutingRuleService = Depends(_routing_svc)):
    # TODO auth: rôle admin
    return await svc.apply_test(body)


@router.put("/routing/{id}")
async def update_routing(id: int, body: RoutingRuleAdminUpdate, db: AsyncSession = Depends(get_db)):
    patch: dict = {}
    if body.name is not None:
        patch["name"] = body.name
    if body.condition_field is not None:
        patch["condition_field"] = body.condition_field
    if body.condition_value is not None:
        patch["condition_value"] = body.condition_value
    if body.target_unity_codename is not None:
        patch["target_unity_id"] = await _resolve_unity_id(body.target_unity_codename, db)
    if body.auto_assign is not None:
        patch["auto_assign"] = body.auto_assign
    if body.sort_order is not None:
        patch["sort_order"] = body.sort_order
    if body.status is not None:
        patch["status"] = body.status
    if body.target_unity_codename is not None:
        svc = RoutingRuleService(db)
        existing = await svc.get_by_id(id)
        infos = dict(existing.infos or {})
        infos["target_unity_codename"] = body.target_unity_codename
        repo = UnityRepository(db)
        unity = await repo.find_by_codename(body.target_unity_codename)
        if unity:
            infos["target_unity_label"] = unity.label or body.target_unity_codename
            dir_id = unity.parent_direction_id
            if dir_id is None:
                dir_id_str = await _unity_direction_id(unity.id, db)
            else:
                dir_id_str = str(dir_id)
            if dir_id_str:
                infos["target_unity_direction_id"] = dir_id_str
        patch["infos"] = infos
    svc = RoutingRuleService(db)
    rule = await svc.update(id, patch)
    return _fmt_rule(rule)


@router.put("/routing/{id}/toggle")
async def toggle_routing(id: int, svc: RoutingRuleService = Depends(_routing_svc)):
    # TODO auth: rôle admin
    rule = await svc.toggle(id)
    return _fmt_rule(rule)


@router.delete("/routing/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_routing(id: int, svc: RoutingRuleService = Depends(_routing_svc)):
    # TODO auth: rôle admin
    await svc.delete(id)


# ═══════════════════════════════════════════════════════════════════════════════
# Reference Tables — /admin/ref/:table
# ═══════════════════════════════════════════════════════════════════════════════

@router.get("/ref/{table}")
async def list_ref(table: str, db: AsyncSession = Depends(get_db)):
    # TODO auth: rôle admin
    svc = _get_ref_service(table, db)
    items = await svc.list_all(only_active=None)
    return {"items": items, "table": table}


@router.post("/ref/{table}", status_code=status.HTTP_201_CREATED)
async def create_ref(table: str, body: RefCreate, db: AsyncSession = Depends(get_db)):
    # TODO auth: rôle admin
    svc = _get_ref_service(table, db)
    return await svc.create(body.dict(exclude_none=True))


@router.put("/ref/{table}/{id}")
async def update_ref(table: str, id: int, body: RefUpdate, db: AsyncSession = Depends(get_db)):
    # TODO auth: rôle admin
    svc = _get_ref_service(table, db)
    return await svc.update(id, body.dict(exclude_none=True))


@router.delete("/ref/{table}/{id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_ref(table: str, id: int, db: AsyncSession = Depends(get_db)):
    # TODO auth: rôle admin
    svc = _get_ref_service(table, db)
    await svc.delete(id)


@router.put("/ref/{table}/{id}/restore")
async def restore_ref(table: str, id: int, db: AsyncSession = Depends(get_db)):
    # TODO auth: rôle admin
    svc = _get_ref_service(table, db)
    return await svc.restore(id)
