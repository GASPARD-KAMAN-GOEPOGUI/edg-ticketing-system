from __future__ import annotations

from datetime import datetime
from typing import Any, List, Optional

from pydantic import BaseModel

from .base import BaseResponse


class KnowledgeArticleBase(BaseModel):
    author_id: Optional[int] = None
    title: str
    excerpt: str
    body: str
    category: str
    read_time: int = 3
    author: str
    is_published: bool = False
    tags: Optional[List[str]] = None


class KnowledgeArticleCreate(KnowledgeArticleBase):
    infos: Optional[Any] = None


class KnowledgeArticleUpdate(BaseModel):
    title: Optional[str] = None
    excerpt: Optional[str] = None
    body: Optional[str] = None
    category: Optional[str] = None
    read_time: Optional[int] = None
    is_published: Optional[bool] = None
    is_archived: Optional[bool] = None
    tags: Optional[List[str]] = None
    status: Optional[bool] = None
    infos: Optional[Any] = None
    published_at: Optional[datetime] = None


class KnowledgeArticleResponse(BaseResponse):
    author_id: Optional[int] = None
    title: str
    excerpt: str
    body: str
    category: str
    read_time: int
    author: str
    is_published: bool
    is_archived: bool
    tags: Optional[Any] = None
    published_at: Optional[datetime] = None

    class Config:
        orm_mode = True
