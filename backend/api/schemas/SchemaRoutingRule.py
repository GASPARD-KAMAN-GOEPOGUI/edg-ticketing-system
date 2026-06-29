from __future__ import annotations

from typing import Any, Optional

from pydantic import BaseModel

from .base import BaseResponse


class RoutingRuleBase(BaseModel):
    target_unity_id: Optional[int] = None
    name: str
    condition_field: str
    condition_value: str
    auto_assign: bool = False
    sort_order: int


class RoutingRuleCreate(RoutingRuleBase):
    infos: Optional[Any] = None


class RoutingRuleUpdate(BaseModel):
    target_unity_id: Optional[int] = None
    name: Optional[str] = None
    condition_field: Optional[str] = None
    condition_value: Optional[str] = None
    auto_assign: Optional[bool] = None
    sort_order: Optional[int] = None
    status: Optional[bool] = None
    infos: Optional[Any] = None


class RoutingRuleResponse(BaseResponse):
    target_unity_id: Optional[int] = None
    target_unity_codename: Optional[str] = None
    target_unity_label: Optional[str] = None
    target_unity_direction_id: Optional[str] = None
    name: str
    condition_field: str
    condition_value: str
    auto_assign: bool
    sort_order: int

    class Config:
        orm_mode = True
