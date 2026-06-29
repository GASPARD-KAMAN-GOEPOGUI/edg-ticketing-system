"""
Validation applicative des codes de référence.

Usage :
    from api.core.ref_validation import check_ref_code
    from api.repositories import AccountStatusRepository

    await check_ref_code(session, AccountStatusRepository, code, "account_status")

Lève ValidationException (422) si le code n'existe pas ou est désactivé.
"""
from __future__ import annotations

from typing import Type

from sqlalchemy.ext.asyncio import AsyncSession

from api.core.exceptions import ValidationException


async def check_ref_code(
    session: AsyncSession,
    repo_class: Type,
    code: str,
    field: str,
) -> None:
    """Vérifie qu'un code existe et est actif dans la table de référence correspondante."""
    repo = repo_class(session)
    obj = await repo.find_by_code(code)
    if obj is None or obj.deleted_at is not None or not obj.status:
        raise ValidationException(
            f"La valeur '{code}' n'est pas reconnue pour le champ '{field}'. "
            f"Ajoutez-la dans le référentiel admin avant de l'utiliser.",
            error_code="INVALID_REF_CODE",
        )
