"""
Enums Python pour les valeurs figées (anciennement tables de référence DB).
Utiliser ces enums dans les schémas Pydantic pour validation automatique.
"""
from __future__ import annotations

from enum import Enum


class WorkflowStatusEnum(str, Enum):
    DRAFT    = "draft"
    ACTIVE   = "active"
    ARCHIVED = "archived"


class RequestSourceEnum(str, Enum):
    WEB       = "web"
    MOBILE    = "mobile"
    GUICHET   = "guichet"
    TELEPHONE = "telephone"
    EMAIL     = "email"
    AGENT     = "agent"


class TaskTypeEnum(str, Enum):
    VERIFICATION   = "verification"
    INTERVENTION   = "intervention"
    DOCUMENTATION  = "documentation"
    COMMUNICATION  = "communication"
    ADMINISTRATIVE = "administrative"


class TaskStatusEnum(str, Enum):
    PENDING     = "pending"
    IN_PROGRESS = "in_progress"
    BLOCKED     = "blocked"
    DONE        = "done"
    COMPLETED   = "completed"
    APPROVED    = "approved"
    REJECTED    = "rejected"
    CANCELLED   = "cancelled"
