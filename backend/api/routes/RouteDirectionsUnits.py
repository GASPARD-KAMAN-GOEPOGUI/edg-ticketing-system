"""
Routes de compatibilite frontend - /directions, /departments et /units.

Le modele de donnees reste unique:
  - Unity porte l'identite de l'entite organisationnelle.
  - Organigram.parent_id porte la hierarchie.

Types metier:
  Direction   = entite creee/servie par /directions.
  Departement = enfant d'une direction, cree/servi par /departments.
  Unit/Service = enfant d'un departement, cree/servi par /units.

Pour compatibilite avec les donnees existantes, les anciens services directement
rattaches a une direction restent lisibles comme units legacy, sans migration.
"""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from api.dependencies import get_db, get_current_user, require_roles
from api.models.ModelOrganigram import Organigram
from api.models.ModelUnity import Unity

OrgKind = Literal["direction", "department", "unit"]
ORG_TYPE_KEY = "org_type"


# -- Helpers ------------------------------------------------------------------

def _parse_id_or_404(raw: str | int | None, message: str) -> int:
    try:
        return int(raw)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        raise HTTPException(status_code=404, detail=message)


def _normalise_kind(value: object) -> OrgKind | None:
    raw = str(value or "").strip().lower()
    if raw in {"direction", "department", "unit"}:
        return raw  # type: ignore[return-value]
    if raw == "service":
        return "unit"
    return None


def _infos_with_kind(unity: Unity | None, kind: OrgKind) -> dict:
    infos = dict(unity.infos or {}) if unity is not None else {}
    infos[ORG_TYPE_KEY] = kind
    return infos


def _label_starts(label: str | None, prefixes: tuple[str, ...]) -> bool:
    lowered = (label or "").strip().lower()
    return any(lowered.startswith(prefix) for prefix in prefixes)


def _is_visible_unity(unity: Unity | None) -> bool:
    return unity is not None and unity.deleted_at is None


def _is_visible_org(org: Organigram | None) -> bool:
    return org is not None and org.deleted_at is None and _is_visible_unity(org.unity)


def _kind_from_org(org: Organigram) -> OrgKind:
    unity = org.unity
    stored = _normalise_kind((unity.infos or {}).get(ORG_TYPE_KEY) if unity else None)
    if stored:
        return stored

    label = unity.label if unity else ""
    if _label_starts(label, ("direction",)):
        return "direction"
    if _label_starts(label, ("departement", "département")):
        return "department"
    if _label_starts(label, ("service", "unite", "unité", "secretariat", "secrétariat", "cabinet")):
        return "unit"
    if org.parent_id is None:
        return "direction"
    return "unit"


async def _get_org_by_unity(
    db: AsyncSession,
    unity_id: int,
    *,
    expected: OrgKind | None = None,
) -> Organigram | None:
    stmt = (
        select(Organigram)
        .options(
            selectinload(Organigram.unity),
            selectinload(Organigram.parent).selectinload(Organigram.unity),
        )
        .where(Organigram.unity_id == unity_id)
        .where(Organigram.deleted_at.is_(None))
    )
    rows = (await db.execute(stmt)).scalars().all()
    for org in rows:
        if not _is_visible_org(org):
            continue
        if expected is None or _kind_from_org(org) == expected:
            return org
    return None


async def _require_org(
    db: AsyncSession,
    unity_id: int,
    *,
    expected: OrgKind,
    message: str,
    require_active: bool = False,
) -> Organigram:
    org = await _get_org_by_unity(db, unity_id, expected=expected)
    if not _is_visible_org(org):
        raise HTTPException(status_code=404, detail=message)
    if require_active and (not org.status or not org.unity.status):
        raise HTTPException(status_code=409, detail=f"{message} ou inactive")
    return org


async def _find_ancestor(
    db: AsyncSession,
    org: Organigram,
    expected: OrgKind,
) -> Organigram | None:
    parent_id = org.parent_id
    seen: set[int] = set()
    while parent_id and parent_id not in seen:
        seen.add(parent_id)
        stmt = (
            select(Organigram)
            .options(selectinload(Organigram.unity))
            .where(Organigram.id == parent_id)
            .where(Organigram.deleted_at.is_(None))
        )
        parent = (await db.execute(stmt)).scalar_one_or_none()
        if not _is_visible_org(parent):
            return None
        if _kind_from_org(parent) == expected:
            return parent
        parent_id = parent.parent_id
    return None


async def _direction_for_org(db: AsyncSession, org: Organigram) -> Organigram | None:
    if _kind_from_org(org) == "direction":
        return org
    return await _find_ancestor(db, org, "direction")


async def _department_for_org(db: AsyncSession, org: Organigram) -> Organigram | None:
    if _kind_from_org(org) == "department":
        return org
    return await _find_ancestor(db, org, "department")


async def _descendant_org_ids(db: AsyncSession, org_id: int) -> list[int]:
    descendants: list[int] = []
    pending = [org_id]
    seen: set[int] = set()
    while pending:
        parent_id = pending.pop(0)
        if parent_id in seen:
            continue
        seen.add(parent_id)
        child_rows = await db.execute(
            select(Organigram.id)
            .where(Organigram.parent_id == parent_id)
            .where(Organigram.deleted_at.is_(None))
        )
        child_ids = [int(row[0]) for row in child_rows.all()]
        descendants.extend(child_ids)
        pending.extend(child_ids)
    return descendants


async def _is_descendant(db: AsyncSession, parent_candidate_id: int, org_id: int) -> bool:
    return parent_candidate_id in set(await _descendant_org_ids(db, org_id))


async def _active_direct_children_count(db: AsyncSession, org_id: int) -> int:
    count = await db.execute(
        select(func.count())
        .select_from(Organigram)
        .join(Unity, Organigram.unity_id == Unity.id)
        .where(Organigram.parent_id == org_id)
        .where(Organigram.deleted_at.is_(None))
        .where(Unity.deleted_at.is_(None))
        .where(Organigram.status.is_(True))
        .where(Unity.status.is_(True))
    )
    return int(count.scalar() or 0)


async def _set_status(
    db: AsyncSession,
    unity_id: int,
    *,
    expected: OrgKind,
    active: bool,
    force: bool = False,
) -> None:
    org = await _require_org(
        db,
        unity_id,
        expected=expected,
        message="Entite organisationnelle introuvable",
    )

    if active:
        if org.parent_id is not None:
            parent = (
                await db.execute(
                    select(Organigram)
                    .options(selectinload(Organigram.unity))
                    .where(Organigram.id == org.parent_id)
                    .where(Organigram.deleted_at.is_(None))
                )
            ).scalar_one_or_none()
            if not _is_visible_org(parent) or not parent.status or not parent.unity.status:
                raise HTTPException(
                    status_code=409,
                    detail="Impossible d'activer cet element tant que son parent est inactif.",
                )
        org.status = True
        org.unity.status = True
        await db.commit()
        return

    active_children = await _active_direct_children_count(db, org.id)
    if active_children > 0 and not force:
        raise HTTPException(
            status_code=409,
            detail=(
                "Cet element possede encore des enfants actifs. "
                "Confirmez la desactivation pour desactiver aussi ses descendants."
            ),
        )

    org.status = False
    org.unity.status = False

    if force:
        descendant_ids = await _descendant_org_ids(db, org.id)
        if descendant_ids:
            descendants = (
                await db.execute(
                    select(Organigram)
                    .options(selectinload(Organigram.unity))
                    .where(Organigram.id.in_(descendant_ids))
                    .where(Organigram.deleted_at.is_(None))
                )
            ).scalars().all()
            for child in descendants:
                child.status = False
                if _is_visible_unity(child.unity):
                    child.unity.status = False

    await db.commit()


async def _create_unity(
    db: AsyncSession,
    *,
    body: dict,
    kind: OrgKind,
    parent_unity_id: int | None,
) -> Unity:
    from api.services.ServiceUnity import UnityService

    unity = await UnityService(db).create({
        "label": body.get("name", ""),
        "codename": body.get("code", ""),
        "description": body.get("description"),
        "parent_direction_id": parent_unity_id,
        "infos": {ORG_TYPE_KEY: kind},
    })
    return unity


async def _update_unity(
    db: AsyncSession,
    unity: Unity,
    *,
    body: dict,
    kind: OrgKind,
    parent_unity_id: int | None,
) -> Unity:
    from api.services.ServiceUnity import UnityService

    patch = {
        k: v for k, v in {
            "label": body.get("name"),
            "codename": body.get("code"),
            "description": body.get("description"),
            "status": body.get("status"),
        }.items() if v is not None
    }
    patch["infos"] = _infos_with_kind(unity, kind)
    patch["parent_direction_id"] = parent_unity_id
    return await UnityService(db).update(str(unity.id), patch)


async def _all_visible_orgs(db: AsyncSession) -> list[Organigram]:
    stmt = (
        select(Organigram)
        .options(
            selectinload(Organigram.unity),
            selectinload(Organigram.parent).selectinload(Organigram.unity),
        )
        .where(Organigram.deleted_at.is_(None))
        .order_by(Organigram.id)
    )
    rows = (await db.execute(stmt)).scalars().all()
    return [row for row in rows if _is_visible_org(row)]


def _matches_status_filter(org: Organigram, status_filter: str) -> bool:
    if status_filter == "active":
        return bool(org.status and org.unity.status)
    if status_filter == "inactive":
        return not bool(org.status and org.unity.status)
    return True


async def _as_direction(db: AsyncSession, org: Organigram) -> dict:
    direction_parent_id: str | None = None
    if org.parent_id is not None:
        parent = await _find_ancestor(db, org, "direction")
        direction_parent_id = str(parent.unity_id) if parent is not None else None
    if direction_parent_id is None and org.unity.parent_direction_id:
        direction_parent_id = str(org.unity.parent_direction_id)
    return {
        "id": str(org.unity.id),
        "name": org.unity.label,
        "code": org.unity.codename,
        "description": org.unity.description,
        "status": bool(org.status and org.unity.status),
        "parent_direction_id": direction_parent_id,
        "active_children_count": await _active_direct_children_count(db, org.id),
        "type": "direction",
    }


async def _as_department(db: AsyncSession, org: Organigram) -> dict:
    direction = await _direction_for_org(db, org)
    return {
        "id": str(org.unity.id),
        "name": org.unity.label,
        "code": org.unity.codename,
        "description": org.unity.description,
        "status": bool(org.status and org.unity.status),
        "direction_id": str(direction.unity_id) if direction else None,
        "direction_name": direction.unity.label if direction else None,
        "active_children_count": await _active_direct_children_count(db, org.id),
        "type": "department",
    }


async def _as_unit(db: AsyncSession, org: Organigram) -> dict:
    direction = await _direction_for_org(db, org)
    department = await _department_for_org(db, org)
    return {
        "id": str(org.unity.id),
        "name": org.unity.label,
        "code": org.unity.codename,
        "description": org.unity.description,
        "status": bool(org.status and org.unity.status),
        "direction_id": str(direction.unity_id) if direction else None,
        "direction_name": direction.unity.label if direction else None,
        "department_id": str(department.unity_id) if department else None,
        "department_name": department.unity.label if department else None,
        "active_children_count": await _active_direct_children_count(db, org.id),
        "type": "unit",
    }


async def _orgs_by_kind(
    db: AsyncSession,
    kind: OrgKind,
    *,
    status_filter: str = "all",
) -> list[Organigram]:
    rows = await _all_visible_orgs(db)
    return [
        org for org in rows
        if _kind_from_org(org) == kind and _matches_status_filter(org, status_filter)
    ]


# -- Compteur public des directions actives -----------------------------------

public_dirs_router = APIRouter(prefix="/public", tags=["public"])


@public_dirs_router.get("/directions/count")
async def count_active_directions(db: AsyncSession = Depends(get_db)):
    rows = await _orgs_by_kind(db, "direction", status_filter="active")
    return {"count": len(rows)}


# -- /directions ---------------------------------------------------------------

directions_router = APIRouter(
    prefix="/directions",
    tags=["directions"],
    dependencies=[Depends(get_current_user)],
)


@directions_router.get("/")
async def list_directions(
    limit: int = Query(200, ge=1, le=500),
    status_filter: str = Query("all", alias="status"),
    db: AsyncSession = Depends(get_db),
):
    rows = (await _orgs_by_kind(db, "direction", status_filter=status_filter))[:limit]
    items = [await _as_direction(db, row) for row in rows]
    return {"items": items, "total": len(items), "page": 1, "limit": limit}


@directions_router.get("/{direction_id}")
async def get_direction(direction_id: str, db: AsyncSession = Depends(get_db)):
    uid = _parse_id_or_404(direction_id, "Direction introuvable")
    org = await _require_org(db, uid, expected="direction", message="Direction introuvable")
    return await _as_direction(db, org)


@directions_router.post("/", status_code=status.HTTP_201_CREATED)
async def create_direction(
    body: dict = Body(...),
    _=Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    parent_org: Organigram | None = None
    parent_direction_id: int | None = None
    if body.get("parent_direction_id"):
        parent_direction_id = _parse_id_or_404(body.get("parent_direction_id"), "Direction parente introuvable")
        parent_org = await _require_org(
            db,
            parent_direction_id,
            expected="direction",
            message="Direction parente introuvable",
            require_active=True,
        )

    unity = await _create_unity(db, body=body, kind="direction", parent_unity_id=parent_direction_id)
    org = Organigram(unity_id=unity.id, parent_id=parent_org.id if parent_org else None, infos={ORG_TYPE_KEY: "direction"})
    db.add(org)
    await db.commit()
    await db.refresh(org)
    return await _as_direction(db, await _require_org(db, unity.id, expected="direction", message="Direction introuvable"))


@directions_router.put("/{direction_id}")
async def update_direction(
    direction_id: str,
    body: dict = Body(...),
    _=Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    uid = _parse_id_or_404(direction_id, "Direction introuvable")
    org = await _require_org(db, uid, expected="direction", message="Direction introuvable")

    parent_unity_id: int | None = org.unity.parent_direction_id
    if "parent_direction_id" in body:
        raw_parent = body.get("parent_direction_id")
        if raw_parent:
            parent_unity_id = _parse_id_or_404(raw_parent, "Direction parente introuvable")
            if parent_unity_id == uid:
                raise HTTPException(status_code=409, detail="Une direction ne peut pas etre son propre parent.")
            parent_org = await _require_org(
                db,
                parent_unity_id,
                expected="direction",
                message="Direction parente introuvable",
                require_active=True,
            )
            if await _is_descendant(db, parent_org.id, org.id):
                raise HTTPException(status_code=409, detail="Relation circulaire interdite.")
            org.parent_id = parent_org.id
        else:
            parent_unity_id = None
            org.parent_id = None

    unity = await _update_unity(
        db,
        org.unity,
        body=body,
        kind="direction",
        parent_unity_id=parent_unity_id,
    )
    org.unity = unity
    await db.commit()
    return await _as_direction(db, org)


@directions_router.post("/{direction_id}/deactivate", status_code=status.HTTP_200_OK)
async def deactivate_direction(
    direction_id: str,
    force: bool = Query(False),
    _=Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    uid = _parse_id_or_404(direction_id, "Direction introuvable")
    await _set_status(db, uid, expected="direction", active=False, force=force)
    return {"ok": True}


@directions_router.post("/{direction_id}/activate", status_code=status.HTTP_200_OK)
async def activate_direction(
    direction_id: str,
    _=Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    uid = _parse_id_or_404(direction_id, "Direction introuvable")
    await _set_status(db, uid, expected="direction", active=True)
    return {"ok": True}


@directions_router.delete("/{direction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_direction(
    direction_id: str,
    force: bool = Query(False),
    _=Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    uid = _parse_id_or_404(direction_id, "Direction introuvable")
    await _set_status(db, uid, expected="direction", active=False, force=force)


# -- /departments --------------------------------------------------------------

departments_router = APIRouter(
    prefix="/departments",
    tags=["departments"],
    dependencies=[Depends(get_current_user)],
)


@departments_router.get("/")
async def list_departments(
    direction_id: str | None = Query(None),
    limit: int = Query(200, ge=1, le=500),
    status_filter: str = Query("all", alias="status"),
    db: AsyncSession = Depends(get_db),
):
    rows = await _orgs_by_kind(db, "department", status_filter=status_filter)
    if direction_id:
        did = _parse_id_or_404(direction_id, "Direction introuvable")
        filtered: list[Organigram] = []
        for row in rows:
            direction = await _direction_for_org(db, row)
            if direction and direction.unity_id == did:
                filtered.append(row)
        rows = filtered
    rows = rows[:limit]
    items = [await _as_department(db, row) for row in rows]
    return {"items": items, "total": len(items), "page": 1, "limit": limit}


@departments_router.get("/by-direction/{direction_id}")
async def list_departments_by_direction(
    direction_id: str,
    limit: int = Query(200, ge=1, le=500),
    status_filter: str = Query("all", alias="status"),
    db: AsyncSession = Depends(get_db),
):
    return await list_departments(
        direction_id=direction_id,
        limit=limit,
        status_filter=status_filter,
        db=db,
    )


@departments_router.get("/{department_id}")
async def get_department(department_id: str, db: AsyncSession = Depends(get_db)):
    uid = _parse_id_or_404(department_id, "Departement introuvable")
    org = await _require_org(db, uid, expected="department", message="Departement introuvable")
    return await _as_department(db, org)


@departments_router.post("/", status_code=status.HTTP_201_CREATED)
async def create_department(
    body: dict = Body(...),
    _=Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    direction_id = _parse_id_or_404(body.get("direction_id"), "Direction obligatoire")
    direction_org = await _require_org(
        db,
        direction_id,
        expected="direction",
        message="Direction introuvable",
        require_active=True,
    )
    unity = await _create_unity(db, body=body, kind="department", parent_unity_id=direction_id)
    org = Organigram(unity_id=unity.id, parent_id=direction_org.id, infos={ORG_TYPE_KEY: "department"})
    db.add(org)
    await db.commit()
    return await _as_department(db, await _require_org(db, unity.id, expected="department", message="Departement introuvable"))


@departments_router.put("/{department_id}")
async def update_department(
    department_id: str,
    body: dict = Body(...),
    _=Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    uid = _parse_id_or_404(department_id, "Departement introuvable")
    org = await _require_org(db, uid, expected="department", message="Departement introuvable")

    direction = await _direction_for_org(db, org)
    direction_unity_id = direction.unity_id if direction else None
    if body.get("direction_id"):
        direction_unity_id = _parse_id_or_404(body.get("direction_id"), "Direction introuvable")
        direction_org = await _require_org(
            db,
            direction_unity_id,
            expected="direction",
            message="Direction introuvable",
            require_active=True,
        )
        if await _is_descendant(db, direction_org.id, org.id):
            raise HTTPException(status_code=409, detail="Relation circulaire interdite.")
        org.parent_id = direction_org.id

    unity = await _update_unity(
        db,
        org.unity,
        body=body,
        kind="department",
        parent_unity_id=direction_unity_id,
    )
    org.unity = unity
    await db.commit()
    return await _as_department(db, org)


@departments_router.post("/{department_id}/deactivate", status_code=status.HTTP_200_OK)
async def deactivate_department(
    department_id: str,
    force: bool = Query(False),
    _=Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    uid = _parse_id_or_404(department_id, "Departement introuvable")
    await _set_status(db, uid, expected="department", active=False, force=force)
    return {"ok": True}


@departments_router.post("/{department_id}/activate", status_code=status.HTTP_200_OK)
async def activate_department(
    department_id: str,
    _=Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    uid = _parse_id_or_404(department_id, "Departement introuvable")
    await _set_status(db, uid, expected="department", active=True)
    return {"ok": True}


@departments_router.delete("/{department_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_department(
    department_id: str,
    force: bool = Query(False),
    _=Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    uid = _parse_id_or_404(department_id, "Departement introuvable")
    await _set_status(db, uid, expected="department", active=False, force=force)


# -- /units -------------------------------------------------------------------

units_router = APIRouter(
    prefix="/units",
    tags=["units"],
    dependencies=[Depends(get_current_user)],
)


@units_router.get("/by-direction/{direction_id}")
async def list_units_by_direction(
    direction_id: str,
    limit: int = Query(200, ge=1, le=500),
    status_filter: str = Query("all", alias="status"),
    db: AsyncSession = Depends(get_db),
):
    did = _parse_id_or_404(direction_id, "Direction introuvable")
    rows = await _orgs_by_kind(db, "unit", status_filter=status_filter)
    filtered: list[Organigram] = []
    for row in rows:
        direction = await _direction_for_org(db, row)
        if direction and direction.unity_id == did:
            filtered.append(row)
    rows = filtered[:limit]
    items = [await _as_unit(db, row) for row in rows]
    return {"items": items, "total": len(items), "page": 1, "limit": limit}


@units_router.get("/by-department/{department_id}")
async def list_units_by_department(
    department_id: str,
    limit: int = Query(200, ge=1, le=500),
    status_filter: str = Query("all", alias="status"),
    db: AsyncSession = Depends(get_db),
):
    did = _parse_id_or_404(department_id, "Departement introuvable")
    rows = await _orgs_by_kind(db, "unit", status_filter=status_filter)
    filtered: list[Organigram] = []
    for row in rows:
        department = await _department_for_org(db, row)
        if department and department.unity_id == did:
            filtered.append(row)
    rows = filtered[:limit]
    items = [await _as_unit(db, row) for row in rows]
    return {"items": items, "total": len(items), "page": 1, "limit": limit}


@units_router.get("/")
async def list_units(
    direction_id: str | None = Query(None),
    department_id: str | None = Query(None),
    limit: int = Query(200, ge=1, le=500),
    status_filter: str = Query("all", alias="status"),
    db: AsyncSession = Depends(get_db),
):
    if department_id:
        return await list_units_by_department(
            department_id=department_id,
            limit=limit,
            status_filter=status_filter,
            db=db,
        )
    if direction_id:
        return await list_units_by_direction(
            direction_id=direction_id,
            limit=limit,
            status_filter=status_filter,
            db=db,
        )

    rows = (await _orgs_by_kind(db, "unit", status_filter=status_filter))[:limit]
    items = [await _as_unit(db, row) for row in rows]
    return {"items": items, "total": len(items), "page": 1, "limit": limit}


@units_router.get("/{unit_id}")
async def get_unit(unit_id: str, db: AsyncSession = Depends(get_db)):
    uid = _parse_id_or_404(unit_id, "Unite introuvable")
    org = await _require_org(db, uid, expected="unit", message="Unite introuvable")
    return await _as_unit(db, org)


@units_router.post("/", status_code=status.HTTP_201_CREATED)
async def create_unit(
    body: dict = Body(...),
    _=Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    department_id = _parse_id_or_404(body.get("department_id"), "Departement obligatoire")
    department_org = await _require_org(
        db,
        department_id,
        expected="department",
        message="Departement introuvable",
        require_active=True,
    )
    direction_org = await _direction_for_org(db, department_org)
    unity = await _create_unity(
        db,
        body=body,
        kind="unit",
        parent_unity_id=direction_org.unity_id if direction_org else None,
    )
    org = Organigram(unity_id=unity.id, parent_id=department_org.id, infos={ORG_TYPE_KEY: "unit"})
    db.add(org)
    await db.commit()
    return await _as_unit(db, await _require_org(db, unity.id, expected="unit", message="Unite introuvable"))


@units_router.put("/{unit_id}")
async def update_unit(
    unit_id: str,
    body: dict = Body(...),
    _=Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    uid = _parse_id_or_404(unit_id, "Unite introuvable")
    org = await _require_org(db, uid, expected="unit", message="Unite introuvable")

    department_org = await _department_for_org(db, org)
    if body.get("department_id"):
        department_id = _parse_id_or_404(body.get("department_id"), "Departement introuvable")
        department_org = await _require_org(
            db,
            department_id,
            expected="department",
            message="Departement introuvable",
            require_active=True,
        )
        if department_org.unity_id == uid or await _is_descendant(db, department_org.id, org.id):
            raise HTTPException(status_code=409, detail="Relation circulaire interdite.")
        org.parent_id = department_org.id
    elif "direction_id" in body and not body.get("department_id") and department_org is None:
        raise HTTPException(
            status_code=422,
            detail="Une unite ou un service doit etre rattache a un departement.",
        )

    direction_org = await _direction_for_org(db, department_org) if department_org else await _direction_for_org(db, org)
    unity = await _update_unity(
        db,
        org.unity,
        body=body,
        kind="unit",
        parent_unity_id=direction_org.unity_id if direction_org else None,
    )
    org.unity = unity
    await db.commit()
    return await _as_unit(db, org)


@units_router.post("/{unit_id}/deactivate", status_code=status.HTTP_200_OK)
async def deactivate_unit(
    unit_id: str,
    force: bool = Query(False),
    _=Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    uid = _parse_id_or_404(unit_id, "Unite introuvable")
    await _set_status(db, uid, expected="unit", active=False, force=force)
    return {"ok": True}


@units_router.post("/{unit_id}/activate", status_code=status.HTTP_200_OK)
async def activate_unit(
    unit_id: str,
    _=Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    uid = _parse_id_or_404(unit_id, "Unite introuvable")
    await _set_status(db, uid, expected="unit", active=True)
    return {"ok": True}


@units_router.delete("/{unit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_unit(
    unit_id: str,
    force: bool = Query(False),
    _=Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    uid = _parse_id_or_404(unit_id, "Unite introuvable")
    await _set_status(db, uid, expected="unit", active=False, force=force)
