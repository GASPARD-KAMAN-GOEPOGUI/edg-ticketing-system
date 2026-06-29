"""
Services pour les 14 tables de référence EDG Connect.
Chaque service est une fine couche au-dessus de son repository.
"""
from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from api.repositories import (
    RequestStatusRepository,
    RequestCategoryRepository,
    AccountStatusRepository,
    KnowledgeCategoryRepository,
    AnnouncementCategoryRepository,
    AnnouncementPriorityRepository,
    AnnouncementStatusRepository,
    PriorityDefinitionRepository,
)
from api.services.base_service import BaseService


class RequestStatusService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.repo = RequestStatusRepository(session)

    async def list_all(self, *, only_active: bool = True):
        return await self.repo.list_ordered(only_active=only_active)

    async def get_by_id(self, id: int):
        obj = await self.repo.get_by_id(id)
        if obj is None:
            raise self.not_found("Statut de requête introuvable")
        return obj

    async def get_by_code(self, code: str):
        obj = await self.repo.find_by_code(code)
        if obj is None:
            raise self.not_found(f"Code '{code}' introuvable")
        return obj

    async def create(self, data: dict):
        existing = await self.repo.find_by_code(data.get("code", ""))
        if existing:
            raise self.conflict("Ce code existe déjà")
        return await self.repo.create(data)

    async def update(self, id: int, data: dict):
        obj = await self.repo.update(id, data)
        if obj is None:
            raise self.not_found("Statut de requête introuvable")
        return obj

    async def delete(self, id: int) -> bool:
        obj = await self.get_by_id(id)
        if obj.is_builtin:
            raise self.bad_request("Les statuts intégrés ne peuvent pas être supprimés")
        return await self.repo.delete(id)

    async def restore(self, id: int):
        ok = await self.repo.restore(id)
        if not ok:
            raise self.not_found("Statut de requête introuvable")
        return await self.repo.get_by_id(id)


class RequestCategoryService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.repo = RequestCategoryRepository(session)

    async def list_all(self, *, only_active: bool = True):
        return await self.repo.list_ordered(only_active=only_active)

    async def get_by_id(self, id: int):
        obj = await self.repo.get_by_id(id)
        if obj is None:
            raise self.not_found("Catégorie de requête introuvable")
        return obj

    async def create(self, data: dict):
        existing = await self.repo.find_by_code(data.get("code", ""))
        if existing:
            raise self.conflict("Ce code existe déjà")
        return await self.repo.create(data)

    async def update(self, id: int, data: dict):
        obj = await self.repo.update(id, data)
        if obj is None:
            raise self.not_found("Catégorie de requête introuvable")
        return obj

    async def delete(self, id: int) -> bool:
        obj = await self.get_by_id(id)
        if obj.is_builtin:
            raise self.bad_request("Les catégories intégrées ne peuvent pas être supprimées")
        return await self.repo.delete(id)

    async def restore(self, id: int):
        ok = await self.repo.restore(id)
        if not ok:
            raise self.not_found("Catégorie de requête introuvable")
        return await self.repo.get_by_id(id)


class AccountStatusService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.repo = AccountStatusRepository(session)

    async def list_all(self, *, only_active: bool = True):
        return await self.repo.list_ordered(only_active=only_active)

    async def get_by_id(self, id: int):
        obj = await self.repo.get_by_id(id)
        if obj is None:
            raise self.not_found("Statut de compte introuvable")
        return obj

    async def create(self, data: dict):
        existing = await self.repo.find_by_code(data.get("code", ""))
        if existing:
            raise self.conflict("Ce code existe déjà")
        return await self.repo.create(data)

    async def update(self, id: int, data: dict):
        obj = await self.repo.update(id, data)
        if obj is None:
            raise self.not_found("Statut de compte introuvable")
        return obj

    async def delete(self, id: int) -> bool:
        obj = await self.get_by_id(id)
        if obj.is_builtin:
            raise self.bad_request("Les statuts intégrés ne peuvent pas être supprimés")
        return await self.repo.delete(id)

    async def restore(self, id: int):
        ok = await self.repo.restore(id)
        if not ok:
            raise self.not_found("Statut de compte introuvable")
        return await self.repo.get_by_id(id)


class KnowledgeCategoryService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.repo = KnowledgeCategoryRepository(session)

    async def list_all(self, *, only_active: bool = True):
        return await self.repo.list_ordered(only_active=only_active)

    async def get_by_id(self, id: int):
        obj = await self.repo.get_by_id(id)
        if obj is None:
            raise self.not_found("Catégorie de connaissance introuvable")
        return obj

    async def create(self, data: dict):
        existing = await self.repo.find_by_code(data.get("code", ""))
        if existing:
            raise self.conflict("Ce code existe déjà")
        return await self.repo.create(data)

    async def update(self, id: int, data: dict):
        obj = await self.repo.update(id, data)
        if obj is None:
            raise self.not_found("Catégorie de connaissance introuvable")
        return obj

    async def delete(self, id: int) -> bool:
        obj = await self.get_by_id(id)
        if obj.is_builtin:
            raise self.bad_request("Les catégories intégrées ne peuvent pas être supprimées")
        return await self.repo.delete(id)

    async def restore(self, id: int):
        ok = await self.repo.restore(id)
        if not ok:
            raise self.not_found("Catégorie de connaissance introuvable")
        return await self.repo.get_by_id(id)


class AnnouncementCategoryService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.repo = AnnouncementCategoryRepository(session)

    async def list_all(self, *, only_active: bool = True):
        return await self.repo.list_ordered(only_active=only_active)

    async def get_by_id(self, id: int):
        obj = await self.repo.get_by_id(id)
        if obj is None:
            raise self.not_found("Catégorie d'annonce introuvable")
        return obj

    async def create(self, data: dict):
        existing = await self.repo.find_by_code(data.get("code", ""))
        if existing:
            raise self.conflict("Ce code existe déjà")
        return await self.repo.create(data)

    async def update(self, id: int, data: dict):
        obj = await self.repo.update(id, data)
        if obj is None:
            raise self.not_found("Catégorie d'annonce introuvable")
        return obj

    async def delete(self, id: int) -> bool:
        obj = await self.get_by_id(id)
        if obj.is_builtin:
            raise self.bad_request("Les catégories intégrées ne peuvent pas être supprimées")
        return await self.repo.delete(id)

    async def restore(self, id: int):
        ok = await self.repo.restore(id)
        if not ok:
            raise self.not_found("Catégorie d'annonce introuvable")
        return await self.repo.get_by_id(id)


class AnnouncementPriorityService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.repo = AnnouncementPriorityRepository(session)

    async def list_all(self, *, only_active: bool = True):
        return await self.repo.list_ordered(only_active=only_active)

    async def get_by_id(self, id: int):
        obj = await self.repo.get_by_id(id)
        if obj is None:
            raise self.not_found("Priorité d'annonce introuvable")
        return obj

    async def create(self, data: dict):
        existing = await self.repo.find_by_code(data.get("code", ""))
        if existing:
            raise self.conflict("Ce code existe déjà")
        return await self.repo.create(data)

    async def update(self, id: int, data: dict):
        obj = await self.repo.update(id, data)
        if obj is None:
            raise self.not_found("Priorité d'annonce introuvable")
        return obj

    async def delete(self, id: int) -> bool:
        obj = await self.get_by_id(id)
        if obj.is_builtin:
            raise self.bad_request("Les priorités intégrées ne peuvent pas être supprimées")
        return await self.repo.delete(id)

    async def restore(self, id: int):
        ok = await self.repo.restore(id)
        if not ok:
            raise self.not_found("Priorité d'annonce introuvable")
        return await self.repo.get_by_id(id)


class AnnouncementStatusService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.repo = AnnouncementStatusRepository(session)

    async def list_all(self, *, only_active: bool = True):
        return await self.repo.list_ordered(only_active=only_active)

    async def get_by_id(self, id: int):
        obj = await self.repo.get_by_id(id)
        if obj is None:
            raise self.not_found("Statut d'annonce introuvable")
        return obj

    async def create(self, data: dict):
        existing = await self.repo.find_by_code(data.get("code", ""))
        if existing:
            raise self.conflict("Ce code existe déjà")
        return await self.repo.create(data)

    async def update(self, id: int, data: dict):
        obj = await self.repo.update(id, data)
        if obj is None:
            raise self.not_found("Statut d'annonce introuvable")
        return obj

    async def delete(self, id: int) -> bool:
        obj = await self.get_by_id(id)
        if obj.is_builtin:
            raise self.bad_request("Les statuts intégrés ne peuvent pas être supprimés")
        return await self.repo.delete(id)

    async def restore(self, id: int):
        ok = await self.repo.restore(id)
        if not ok:
            raise self.not_found("Statut d'annonce introuvable")
        return await self.repo.get_by_id(id)


class PriorityDefinitionService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.repo = PriorityDefinitionRepository(session)

    async def list_all(self, *, only_active: bool = True):
        return await self.repo.list_ordered(only_active=only_active)

    async def get_by_id(self, id: int):
        obj = await self.repo.get_by_id(id)
        if obj is None:
            raise self.not_found("Définition de priorité introuvable")
        return obj

    async def get_by_slug(self, slug: str):
        obj = await self.repo.find_by_slug(slug)
        if obj is None:
            raise self.not_found(f"Slug '{slug}' introuvable")
        return obj

    async def create(self, data: dict):
        existing = await self.repo.find_by_slug(data.get("slug", ""))
        if existing:
            raise self.conflict("Ce slug existe déjà")
        return await self.repo.create(data)

    async def update(self, id: int, data: dict):
        obj = await self.repo.update(id, data)
        if obj is None:
            raise self.not_found("Définition de priorité introuvable")
        return obj

    async def reorder(self, ordered_ids: list[int]) -> list:
        for i, prio_id in enumerate(ordered_ids, 1):
            await self.repo.update(prio_id, {"sort_order": i})
        return await self.repo.list_ordered(only_active=None)

    async def delete(self, id: int) -> bool:
        obj = await self.get_by_id(id)
        if obj.is_builtin:
            raise self.bad_request("Les priorités intégrées ne peuvent pas être supprimées")
        return await self.repo.delete(id)

    async def restore(self, id: int):
        ok = await self.repo.restore(id)
        if not ok:
            raise self.not_found("Définition de priorité introuvable")
        return await self.repo.get_by_id(id)
