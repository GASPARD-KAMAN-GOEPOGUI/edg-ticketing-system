"""
Services pour les 14 tables de référence EDG Support.
Chaque service est une fine couche au-dessus de son repository.
"""
from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.repositories import (
    RequestStatusRepository,
    RequestCategoryRepository,
    PriorityDefinitionRepository,
)
from api.services.base_service import BaseService


class _ReferenceGuardMixin:
    """Règles communes aux référentiels éditables depuis l'Administration.

    Deux protections, qui ne se confondent pas :

    1. **Le code d'un élément intégré est immuable.** Les codes de statut sont
       utilisés comme littéraux à une centaine d'endroits du backend (matrice de
       transitions, statuts collaboratifs/terminaux, circuit du PV…), et les
       politiques SLA retrouvent catégories et priorités par le TEXTE de leur
       code. Un renommage casserait le workflow sans lever la moindre erreur au
       moment où il est fait. Le libellé, lui, reste librement modifiable : ce
       n'est que de l'affichage.

    2. **On n'archive pas une valeur encore utilisée.** Remplace l'ancienne règle
       « intégré = indestructible », qui protégeait la mauvaise chose : un
       référentiel intégré que plus aucun ticket ne porte est inoffensif, alors
       qu'une valeur créée à la main mais portée par des centaines de tickets ne
       doit pas disparaître. La désactivation reste l'issue pour retirer une
       valeur des formulaires sans toucher à l'historique.
    """

    #: Colonne de `request` qui référence ce référentiel.
    _USAGE_COLUMN: str = ""
    #: Champ de code immuable sur un élément intégré (`code` ou `slug`).
    _CODE_FIELD: str = "code"
    _LABEL: str = "Cette valeur"

    async def _assert_code_immutable(self, obj, data: dict) -> None:
        field = self._CODE_FIELD
        if field not in data or not getattr(obj, "is_builtin", False):
            return
        if str(data[field] or "") == str(getattr(obj, field, "") or ""):
            return  # valeur inchangée : rien à refuser
        raise self.bad_request(
            f"Le code d'une valeur intégrée ne peut pas être modifié : le "
            f"fonctionnement de l'application s'y réfère. Le libellé, lui, reste "
            f"modifiable.",
        )

    async def _create_or_revive(self, data: dict):
        """Création tolérante aux valeurs archivées.

        L'index unique sur `code`/`slug` ignore `deleted_at` : une valeur
        archivée occupe donc toujours son code, alors qu'elle n'apparaît plus
        nulle part dans l'Administration. Refuser ou laisser partir l'INSERT
        (erreur 1062 opaque) enfermerait l'admin — il ne peut ni voir la ligne
        ni réutiliser son code. On la restaure et on lui applique les données
        soumises : « je recrée cette valeur » fait revenir la valeur.
        """
        field = self._CODE_FIELD
        code = data.get(field, "")
        existing = await self.repo.get_one({field: code}, include_deleted=True)
        if existing is None:
            return await self.repo.create(data)
        if existing.deleted_at is None:
            raise self.conflict(f"Ce {field} existe déjà")
        await self.repo.restore(existing.id)
        # Le code est déjà celui demandé — on ne réécrit que le reste.
        payload = {k: v for k, v in data.items() if k != field}
        return await self.repo.update(existing.id, payload) if payload else \
            await self.repo.get_by_id(existing.id)

    async def _assert_not_in_use(self, obj) -> None:
        from api.models.ModelRequest import Request as RequestModel

        column = getattr(RequestModel, self._USAGE_COLUMN)
        used = (await self.session.execute(
            select(func.count()).select_from(RequestModel)
            .where(column == obj.id)
            .where(RequestModel.deleted_at.is_(None))
        )).scalar_one()
        if used:
            raise self.bad_request(
                f"{self._LABEL} est utilisée par {used} ticket(s) : elle ne peut "
                f"pas être archivée. Désactivez-la pour la retirer des "
                f"formulaires sans toucher à l'historique.",
            )


class RequestStatusService(_ReferenceGuardMixin, BaseService):
    _USAGE_COLUMN = "request_status_id"
    _CODE_FIELD = "code"
    _LABEL = "Ce statut"

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
        return await self._create_or_revive(data)

    async def update(self, id: int, data: dict):
        current = await self.get_by_id(id)
        await self._assert_code_immutable(current, data)
        obj = await self.repo.update(id, data)
        if obj is None:
            raise self.not_found("Statut de requête introuvable")
        return obj

    async def delete(self, id: int) -> bool:
        obj = await self.get_by_id(id)
        await self._assert_not_in_use(obj)
        return await self.repo.delete(id)

    async def restore(self, id: int):
        ok = await self.repo.restore(id)
        if not ok:
            raise self.not_found("Statut de requête introuvable")
        return await self.repo.get_by_id(id)


class RequestCategoryService(_ReferenceGuardMixin, BaseService):
    _USAGE_COLUMN = "request_category_id"
    _CODE_FIELD = "code"
    _LABEL = "Cette categorie"

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
        return await self._create_or_revive(data)

    async def update(self, id: int, data: dict):
        current = await self.get_by_id(id)
        await self._assert_code_immutable(current, data)
        obj = await self.repo.update(id, data)
        if obj is None:
            raise self.not_found("Catégorie de requête introuvable")
        return obj

    async def delete(self, id: int) -> bool:
        obj = await self.get_by_id(id)
        await self._assert_not_in_use(obj)
        return await self.repo.delete(id)

    async def restore(self, id: int):
        ok = await self.repo.restore(id)
        if not ok:
            raise self.not_found("Catégorie de requête introuvable")
        return await self.repo.get_by_id(id)

class PriorityDefinitionService(_ReferenceGuardMixin, BaseService):
    _USAGE_COLUMN = "priority_definition_id"
    _CODE_FIELD = "slug"
    _LABEL = "Cette priorite"

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
        return await self._create_or_revive(data)

    async def update(self, id: int, data: dict):
        current = await self.get_by_id(id)
        await self._assert_code_immutable(current, data)
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
        await self._assert_not_in_use(obj)
        return await self.repo.delete(id)

    async def restore(self, id: int):
        ok = await self.repo.restore(id)
        if not ok:
            raise self.not_found("Définition de priorité introuvable")
        return await self.repo.get_by_id(id)
