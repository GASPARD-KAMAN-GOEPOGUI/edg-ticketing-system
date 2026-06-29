from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel

from api.core.enums import TaskTypeEnum, TaskStatusEnum
from .base import BaseResponse


class TaskBase(BaseModel):
    request_id: int
    from_agent_id: Optional[int] = None
    to_agent_id: Optional[int] = None
    from_unit_id: Optional[int] = None
    to_unit_id: Optional[int] = None
    task_type: TaskTypeEnum
    reason: Optional[str] = None
    task_status: TaskStatusEnum = TaskStatusEnum.PENDING


class TaskCreate(TaskBase):
    infos: Optional[Any] = None


class TaskUpdate(BaseModel):
    to_agent_id: Optional[int] = None
    to_unit_id: Optional[int] = None
    task_status: Optional[TaskStatusEnum] = None
    status: Optional[bool] = None
    infos: Optional[Any] = None


class TaskResponse(BaseResponse):
    request_id: int
    from_agent_id: Optional[int] = None
    to_agent_id: Optional[int] = None
    from_unit_id: Optional[int] = None
    to_unit_id: Optional[int] = None
    task_type: str
    reason: Optional[str] = None
    task_status: str

    class Config:
        orm_mode = True
        use_enum_values = True
