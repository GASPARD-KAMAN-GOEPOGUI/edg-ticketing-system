"""
Routes de compatibilité frontend — /directions/* et /units/*

Ces routes traduisent les appels frontend (basés sur le schéma original direction/unit)
vers le modèle de données backend (Unity + Organigram).

Règle de correspondance :
  Direction = nœud racine de l'organigramme (parent_id IS NULL)
  Unit      = nœud enfant de l'organigramme (parent_id NOT NULL)

Les IDs retournés sont des entiers (str(unity.id)) pour compatibilité
avec les champs unity_id / direction_id / unit_id du modèle Request.
"""
from __future__ import annotations

from fastapi import APIRouter, Body, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.orm import selectinload
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_current_user, require_roles
from api.models.ModelOrganigram import Organigram
from api.models.ModelUnity import Unity

# ── Formatters ────────────────────────────────────────────────────────────────

def _as_direction(u: Unity) -> dict:
    return {
        "id": str(u.id),
        "name": u.label,
        "code": u.codename,
        "description": u.description,
        "status": u.status,
        "parent_direction_id": str(u.parent_direction_id) if u.parent_direction_id else None,
    }


def _as_unit(u: Unity, direction_id: str | None = None) -> dict:
    return {
        "id": str(u.id),
        "name": u.label,
        "code": u.codename,
        "direction_id": direction_id,
        "description": u.description,
        "status": u.status,
    }


# ── Compteur public des directions actives (sans authentification) ────────────

public_dirs_router = APIRouter(prefix="/public", tags=["public"])


@public_dirs_router.get("/directions/count")
async def count_active_directions(db: AsyncSession = Depends(get_db)):
    """Retourne le nombre de directions actives — endpoint public, pas de JWT requis."""
    stmt = (
        select(Organigram)
        .options(selectinload(Organigram.unity))
        .where(Organigram.parent_id.is_(None))
        .where(Organigram.deleted_at.is_(None))
    )
    rows = (await db.execute(stmt)).scalars().all()
    count = sum(1 for r in rows if r.unity and r.unity.status)
    return {"count": count}


# ── /directions/* ─────────────────────────────────────────────────────────────

directions_router = APIRouter(
    prefix="/directions",
    tags=["directions"],
    dependencies=[Depends(get_current_user)],
)


@directions_router.get("/")
async def list_directions(
    limit: int = Query(200, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Organigram)
        .options(selectinload(Organigram.unity))
        .where(Organigram.parent_id.is_(None))
        .where(Organigram.deleted_at.is_(None))
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    items = [_as_direction(r.unity) for r in rows if r.unity]
    return {"items": items, "total": len(items), "page": 1, "limit": limit}


@directions_router.get("/{direction_id}")
async def get_direction(direction_id: str, db: AsyncSession = Depends(get_db)):
    try:
        uid = int(direction_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Direction introuvable")
    stmt = (
        select(Organigram)
        .options(selectinload(Organigram.unity))
        .where(Organigram.unity_id == uid)
        .where(Organigram.parent_id.is_(None))
        .where(Organigram.deleted_at.is_(None))
    )
    org = (await db.execute(stmt)).scalar_one_or_none()
    if org is None or org.unity is None:
        raise HTTPException(status_code=404, detail="Direction introuvable")
    return _as_direction(org.unity)


@directions_router.post("/", status_code=status.HTTP_201_CREATED)
async def create_direction(
    body: dict = Body(...),
    _=Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    from api.services.ServiceUnity import UnityService
    parent_dir_id: int | None = None
    if body.get("parent_direction_id"):
        try:
            parent_dir_id = int(body["parent_direction_id"])
        except (ValueError, TypeError):
            pass
    unity = await UnityService(db).create({
        "label": body.get("name", ""),
        "codename": body.get("code", ""),
        "description": body.get("description"),
        "parent_direction_id": parent_dir_id,
    })
    return _as_direction(unity)


@directions_router.patch("/{direction_id}")
async def update_direction(
    direction_id: str,
    body: dict = Body(...),
    _=Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    from api.services.ServiceUnity import UnityService
    patch = {
        k: v for k, v in {
            "label": body.get("name"),
            "codename": body.get("code"),
            "description": body.get("description"),
            "status": body.get("status"),
        }.items() if v is not None
    }
    # parent_direction_id : présent dans le body → on met à jour (None = supprimer le lien)
    if "parent_direction_id" in body:
        raw = body["parent_direction_id"]
        try:
            patch["parent_direction_id"] = int(raw) if raw else None
        except (ValueError, TypeError):
            patch["parent_direction_id"] = None
    unity = await UnityService(db).update(direction_id, patch)
    return _as_direction(unity)


@directions_router.delete("/{direction_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_direction(
    direction_id: str,
    _=Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    from api.services.ServiceUnity import UnityService
    from api.repositories.RepositoryUnity import UnityRepository
    # Idempotent : retourne 204 même si déjà supprimé
    await UnityRepository(db).delete(int(direction_id))


# ── /units/* ──────────────────────────────────────────────────────────────────

units_router = APIRouter(
    prefix="/units",
    tags=["units"],
    dependencies=[Depends(get_current_user)],
)


@units_router.get("/by-direction/{direction_id}")
async def list_units_by_direction(
    direction_id: str,
    limit: int = Query(200, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    try:
        uid = int(direction_id)
    except ValueError:
        return {"items": [], "total": 0, "page": 1, "limit": limit}

    root_stmt = (
        select(Organigram)
        .where(Organigram.unity_id == uid)
        .where(Organigram.parent_id.is_(None))
        .where(Organigram.deleted_at.is_(None))
    )
    root = (await db.execute(root_stmt)).scalar_one_or_none()
    if root is None:
        return {"items": [], "total": 0, "page": 1, "limit": limit}

    children_stmt = (
        select(Organigram)
        .options(selectinload(Organigram.unity))
        .where(Organigram.parent_id == root.id)
        .where(Organigram.deleted_at.is_(None))
        .limit(limit)
    )
    children = (await db.execute(children_stmt)).scalars().all()
    items = [_as_unit(c.unity, direction_id) for c in children if c.unity]
    return {"items": items, "total": len(items), "page": 1, "limit": limit}


@units_router.get("/")
async def list_units(
    limit: int = Query(200, ge=1, le=500),
    db: AsyncSession = Depends(get_db),
):
    stmt = (
        select(Organigram)
        .options(
            selectinload(Organigram.unity),
            selectinload(Organigram.parent),
        )
        .where(Organigram.parent_id.isnot(None))
        .where(Organigram.deleted_at.is_(None))
        .limit(limit)
    )
    rows = (await db.execute(stmt)).scalars().all()
    items = [
        _as_unit(r.unity, str(r.parent.unity_id) if r.parent else None)
        for r in rows if r.unity
    ]
    return {"items": items, "total": len(items), "page": 1, "limit": limit}


@units_router.get("/{unit_id}")
async def get_unit(unit_id: str, db: AsyncSession = Depends(get_db)):
    try:
        uid = int(unit_id)
    except ValueError:
        raise HTTPException(status_code=404, detail="Unité introuvable")
    stmt = (
        select(Organigram)
        .options(
            selectinload(Organigram.unity),
            selectinload(Organigram.parent),
        )
        .where(Organigram.unity_id == uid)
        .where(Organigram.parent_id.isnot(None))
        .where(Organigram.deleted_at.is_(None))
    )
    org = (await db.execute(stmt)).scalar_one_or_none()
    if org is None or org.unity is None:
        raise HTTPException(status_code=404, detail="Unité introuvable")
    direction_id = str(org.parent.unity_id) if org.parent else None
    return _as_unit(org.unity, direction_id)


@units_router.post("/", status_code=status.HTTP_201_CREATED)
async def create_unit(
    body: dict = Body(...),
    _=Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    from api.services.ServiceUnity import UnityService
    direction_id = body.get("direction_id")

    parent_dir_int: int | None = None
    parent_org_id: int | None = None
    if direction_id:
        try:
            parent_dir_int = int(direction_id)
            parent_stmt = (
                select(Organigram)
                .where(Organigram.unity_id == parent_dir_int)
                .where(Organigram.parent_id.is_(None))
                .where(Organigram.deleted_at.is_(None))
            )
            parent_org = (await db.execute(parent_stmt)).scalar_one_or_none()
            if parent_org:
                parent_org_id = parent_org.id
        except (ValueError, TypeError):
            pass

    unity = await UnityService(db).create({
        "label": body.get("name", ""),
        "codename": body.get("code", ""),
        "description": body.get("description"),
        "parent_direction_id": parent_dir_int,
    })

    org = Organigram(unity_id=unity.id, parent_id=parent_org_id)
    db.add(org)
    await db.commit()

    return _as_unit(unity, direction_id)


@units_router.patch("/{unit_id}")
async def update_unit(
    unit_id: str,
    body: dict = Body(...),
    _=Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    from api.services.ServiceUnity import UnityService
    direction_id = body.get("direction_id")
    patch: dict = {
        k: v for k, v in {
            "label": body.get("name"),
            "codename": body.get("code"),
            "description": body.get("description"),
            "status": body.get("status"),
        }.items() if v is not None
    }
    if direction_id is not None:
        try:
            patch["parent_direction_id"] = int(direction_id)
        except (ValueError, TypeError):
            patch["parent_direction_id"] = None

    unity = await UnityService(db).update(unit_id, patch)

    returned_direction_id: str | None = None

    # Update organigram parent if direction_id supplied
    try:
        uid = int(unit_id)
        org_stmt = (
            select(Organigram)
            .options(selectinload(Organigram.parent))
            .where(Organigram.unity_id == uid)
            .where(Organigram.deleted_at.is_(None))
        )
        org = (await db.execute(org_stmt)).scalar_one_or_none()
        if org:
            if direction_id is not None:
                try:
                    dir_uid = int(direction_id)
                    parent_stmt = (
                        select(Organigram)
                        .where(Organigram.unity_id == dir_uid)
                        .where(Organigram.parent_id.is_(None))
                        .where(Organigram.deleted_at.is_(None))
                    )
                    parent_org = (await db.execute(parent_stmt)).scalar_one_or_none()
                    if parent_org:
                        org.parent_id = parent_org.id
                        returned_direction_id = direction_id
                except (ValueError, TypeError):
                    pass
            elif org.parent:
                returned_direction_id = str(org.parent.unity_id)
            await db.commit()
    except Exception:
        pass

    return _as_unit(unity, returned_direction_id)


@units_router.delete("/{unit_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_unit(
    unit_id: str,
    _=Depends(require_roles("admin")),
    db: AsyncSession = Depends(get_db),
):
    from api.repositories.RepositoryUnity import UnityRepository
    # Idempotent : retourne 204 même si déjà supprimé (include_deleted pour éviter un 404)
    repo = UnityRepository(db)
    obj = await repo.get_by_id(int(unit_id), include_deleted=True)
    if obj is not None and obj.deleted_at is None:
        await repo.delete(int(unit_id))
