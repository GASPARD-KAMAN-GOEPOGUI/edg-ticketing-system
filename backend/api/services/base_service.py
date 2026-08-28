"""
BaseService — classe de base pour tous les services EDG Support.
Injecte la session SQLAlchemy et expose les helpers communs.
"""
from __future__ import annotations

import math
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from api.core.exceptions import (
    NotFoundException,
    ConflictException,
    BusinessException,
    ForbiddenException,
    ValidationException,
)
from api.core.logger import get_logger
from api.schemas.base import PaginatedResponse


class BaseService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self._logger = get_logger(f"service.{self.__class__.__name__}")

    # ── Helpers d'exception ───────────────────────────────────────────────────

    @staticmethod
    def not_found(
        detail: str = "La ressource demandée est introuvable.",
        *,
        error_code: str = "NOT_FOUND",
        field: str | None = None,
        value=None,
        hint: str | None = None,
    ) -> NotFoundException:
        return NotFoundException(detail, error_code=error_code, field=field, value=value, hint=hint)

    @staticmethod
    def conflict(
        detail: str = "Cette ressource existe déjà.",
        *,
        error_code: str = "ALREADY_EXISTS",
        field: str | None = None,
        value=None,
        hint: str | None = None,
    ) -> ConflictException:
        return ConflictException(detail, error_code=error_code, field=field, value=value, hint=hint)

    @staticmethod
    def bad_request(
        detail: str = "L'opération demandée n'est pas autorisée.",
        *,
        error_code: str = "BUSINESS_RULE_VIOLATION",
        field: str | None = None,
        hint: str | None = None,
    ) -> BusinessException:
        return BusinessException(detail, error_code=error_code, field=field, hint=hint)

    @staticmethod
    def forbidden(
        detail: str = "Vous n'êtes pas autorisé à effectuer cette opération.",
        *,
        hint: str | None = None,
    ) -> ForbiddenException:
        return ForbiddenException(detail, hint=hint)

    @staticmethod
    def validation_error(
        detail: str = "Les données fournies sont invalides.",
        *,
        details: list | None = None,
    ) -> ValidationException:
        return ValidationException(detail, details=details)

    # ── Helper pagination ─────────────────────────────────────────────────────

    @staticmethod
    def paginate(
        items: list[Any],
        total: int,
        page: int,
        page_size: int,
    ) -> PaginatedResponse:
        pages = math.ceil(total / page_size) if page_size > 0 else 1
        return PaginatedResponse(
            items=items,
            total=total,
            page=page,
            page_size=page_size,
            pages=pages,
        )
