from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, require_roles
from api.services import AppreciationService

router = APIRouter(
    prefix="/stats",
    tags=["csat"],
    dependencies=[Depends(require_roles("chief", "director", "dg", "admin"))],
)


def _svc(db: AsyncSession = Depends(get_db)) -> AppreciationService:
    return AppreciationService(db)


@router.get("/csat")
async def csat_global(svc: AppreciationService = Depends(_svc)):
    return await svc.csat_global()


@router.get("/csat/by-agent")
async def csat_by_agent(svc: AppreciationService = Depends(_svc)):
    return await svc.csat_by_agent()


@router.get("/csat/by-direction")
async def csat_by_direction(svc: AppreciationService = Depends(_svc)):
    return await svc.csat_by_direction()


@router.get("/csat/by-category")
async def csat_by_category(svc: AppreciationService = Depends(_svc)):
    return await svc.csat_by_category()


@router.get("/csat/monthly")
async def csat_monthly(months: int = 12, svc: AppreciationService = Depends(_svc)):
    return await svc.csat_monthly(months=months)
