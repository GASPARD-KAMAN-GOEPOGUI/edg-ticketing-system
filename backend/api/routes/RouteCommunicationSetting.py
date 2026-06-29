from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, require_roles
from api.schemas.SchemaCommunicationSetting import (
    CommunicationSettingUpdate, CommunicationSettingResponse,
)
from api.services import CommunicationSettingService

router = APIRouter(
    prefix="/communication-settings",
    tags=["communication-settings"],
    dependencies=[Depends(require_roles("admin"))],
)


def _svc(db: AsyncSession = Depends(get_db)) -> CommunicationSettingService:
    return CommunicationSettingService(db)


@router.get("/", response_model=CommunicationSettingResponse)
async def get_current(svc: CommunicationSettingService = Depends(_svc)):
    return await svc.get_or_create_default()


@router.patch("/", response_model=CommunicationSettingResponse)
async def update_settings(
    body: CommunicationSettingUpdate,
    updated_by: Optional[str] = Query(None),
    svc: CommunicationSettingService = Depends(_svc),
):
    return await svc.update_current(body.dict(exclude_unset=True), updated_by=updated_by)
