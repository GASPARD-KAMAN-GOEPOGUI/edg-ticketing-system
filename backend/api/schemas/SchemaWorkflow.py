from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel

from api.core.enums import WorkflowStatusEnum
from .base import BaseResponse


class WorkflowBase(BaseModel):
    request_id: int
    workflow_status: WorkflowStatusEnum = WorkflowStatusEnum.ACTIVE


class WorkflowCreate(WorkflowBase):
    infos: Optional[Any] = None


class WorkflowUpdate(BaseModel):
    workflow_status: Optional[WorkflowStatusEnum] = None
    status: Optional[bool] = None
    infos: Optional[Any] = None


class WorkflowResponse(BaseResponse):
    request_id: int
    workflow_status: str

    class Config:
        orm_mode = True
        use_enum_values = True
