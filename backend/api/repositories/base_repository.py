"""
BaseRepository — CRUD générique async, SQLAlchemy 2.0 + MySQL (aiomysql).

Toutes les tables héritent de BaseColumns :
  id (INT AUTO_INCREMENT), uuid (CHAR 36), status (bool), infos (JSON),
  created_at, updated_at, deleted_at (soft-delete).

Usage concret :
    class DirectionRepository(BaseRepository[Direction]):
        def __init__(self, session: AsyncSession) -> None:
            super().__init__(Direction, session)
"""
from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Generic, TypeVar

from sqlalchemy import Select, func, inspect, or_, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

ModelType = TypeVar("ModelType")

_IMMUTABLE: frozenset[str] = frozenset({"id", "created_at"})


# ── Exceptions ────────────────────────────────────────────────────────────────

class NotFoundException(Exception):
    """Enregistrement introuvable ou soft-deleted."""


class RepositoryIntegrityError(Exception):
    """Conservé pour la rétrocompatibilité — prefer EDGException subclasses."""


# ── Parser d'erreurs MySQL ────────────────────────────────────────────────────

# Table → (nom lisible, error_code)
_FK_TABLE_MAP: dict[str, tuple[str, str]] = {
    "direction":             ("direction",               "DIRECTION_NOT_FOUND"),
    "unit":                  ("service/unité",           "UNIT_NOT_FOUND"),
    "account":               ("compte utilisateur",      "ACCOUNT_NOT_FOUND"),
    "request":               ("demande",                 "REQUEST_NOT_FOUND"),
    "request_category":      ("catégorie",               "CATEGORY_NOT_FOUND"),
    "sla_policy":            ("politique SLA",           "SLA_POLICY_NOT_FOUND"),
    "workflow":              ("workflow",                "WORKFLOW_NOT_FOUND"),
    "task":                  ("tâche",                   "TASK_NOT_FOUND"),
    "routing_rule":          ("règle de routage",        "ROUTING_RULE_NOT_FOUND"),
    "appreciation":          ("appréciation",            "APPRECIATION_NOT_FOUND"),
    "notification":          ("notification",            "NOTIFICATION_NOT_FOUND"),
    "escalation":            ("escalade",                "ESCALATION_NOT_FOUND"),
    "attachment":            ("pièce jointe",            "ATTACHMENT_NOT_FOUND"),
    "workflow_detail":        ("étape / événement",       "WORKFLOW_DETAIL_NOT_FOUND"),
    "homepage_config":       ("configuration",           "CONFIG_NOT_FOUND"),
    "activity_log":          ("journal",                 "LOG_NOT_FOUND"),
}

# Nom de colonne/clé → (nom de champ public, message, error_code)
_DUP_KEY_MAP: dict[str, tuple[str, str, str]] = {
    "email":       ("email",      "Cette adresse email est déjà utilisée.",      "EMAIL_ALREADY_EXISTS"),
    "matricule":   ("matricule",  "Ce matricule est déjà utilisé.",              "MATRICULE_ALREADY_EXISTS"),
    "code":        ("code",       "Ce code est déjà utilisé.",                   "CODE_ALREADY_EXISTS"),
    "ref":         ("ref",        "Cette référence est déjà utilisée.",          "REF_ALREADY_EXISTS"),
    "slug":        ("slug",       "Ce slug est déjà utilisé.",                   "SLUG_ALREADY_EXISTS"),
    "phone":       ("phone",      "Ce numéro de téléphone est déjà utilisé.",    "DUPLICATE_ENTRY"),
}

# MySQL 1452 : a foreign key constraint fails … FOREIGN KEY (`col`) REFERENCES `table` …
_RE_FK = re.compile(
    r"FOREIGN KEY \(`([^`]+)`\) REFERENCES `([^`]+)`",
    re.IGNORECASE,
)
# MySQL 1062 : Duplicate entry 'val' for key 'table.column_name'
_RE_DUP = re.compile(
    r"Duplicate entry '([^']+)' for key '(?:[^.]+\.)?([^']+)'",
    re.IGNORECASE,
)


def _parse_integrity_error(exc: IntegrityError):
    """
    Convertit une IntegrityError SQLAlchemy/MySQL en exception EDG métier.
    Retourne ForeignKeyException (422) ou ConflictException (409).
    Si non reconnu, lève RepositoryIntegrityError classique.
    """
    # Import local pour éviter les imports circulaires
    from api.core.exceptions import ForeignKeyException, ConflictException

    orig = str(exc.orig) if exc.orig else str(exc)

    # ── Clé étrangère (1452) ──────────────────────────────────────────────────
    m = _RE_FK.search(orig)
    if m:
        col_name, ref_table = m.group(1), m.group(2).lower()
        entity_name, error_code = _FK_TABLE_MAP.get(
            ref_table, (f"entité référencée ({ref_table})", "FOREIGN_KEY_VIOLATION")
        )
        raise ForeignKeyException(
            f"La {entity_name} spécifiée n'existe pas.",
            error_code=error_code,
            field=col_name,
            hint=(
                f"Vérifiez que {col_name!r} correspond à un identifiant "
                f"de {entity_name} existant."
            ),
        ) from exc

    # ── Doublon (1062) ────────────────────────────────────────────────────────
    m = _RE_DUP.search(orig)
    if m:
        dup_value, key_name = m.group(1), m.group(2).lower()
        # Chercher par nom de colonne dans key_name (ex: "ix_accounts_email" → "email")
        matched = next(
            ((field, msg, code) for kw, (field, msg, code) in _DUP_KEY_MAP.items()
             if kw in key_name),
            None,
        )
        if matched:
            field, message, error_code = matched
            raise ConflictException(
                message,
                error_code=error_code,
                field=field,
                value=dup_value,
                hint=f"Utilisez une valeur différente pour le champ '{field}'.",
            ) from exc
        raise ConflictException(
            "Cette valeur est déjà utilisée.",
            error_code="DUPLICATE_ENTRY",
            value=dup_value,
            hint="Vérifiez les champs uniques de votre requête.",
        ) from exc

    # Erreur d'intégrité non reconnue — log interne, message générique
    raise RepositoryIntegrityError(orig) from exc


# ── Repository générique ──────────────────────────────────────────────────────

class BaseRepository(Generic[ModelType]):

    def __init__(self, model: type[ModelType], session: AsyncSession) -> None:
        self.model = model
        self.session = session

    # ── Helpers ───────────────────────────────────────────────────────────────

    def _valid_columns(self) -> frozenset[str]:
        return frozenset(inspect(self.model).columns.keys())

    def apply_soft_delete_filter(self, stmt: Select) -> Select:
        """Filtre deleted_at IS NULL. Réutilisable dans les sous-classes."""
        return stmt.where(self.model.deleted_at.is_(None))

    def _apply_filters(self, stmt: Select, filters: dict) -> Select:
        for key, val in filters.items():
            col = getattr(self.model, key, None)
            if col is None:
                continue
            stmt = stmt.where(col.in_(val) if isinstance(val, (list, tuple, set)) else col == val)
        return stmt

    def _apply_search(self, stmt: Select, search: tuple[list[str], str]) -> Select:
        cols, term = search
        clauses = [
            getattr(self.model, c).ilike(f"%{term}%")
            for c in cols if getattr(self.model, c, None) is not None
        ]
        return stmt.where(or_(*clauses)) if clauses else stmt

    def _apply_order(self, stmt: Select, order_by: str) -> Select:
        desc = order_by.startswith("-")
        col_name = order_by.lstrip("-")
        if col_name not in self._valid_columns():
            col_name, desc = "created_at", True
        col = getattr(self.model, col_name)
        return stmt.order_by(col.desc() if desc else col.asc())

    # ── Lectures ──────────────────────────────────────────────────────────────

    async def get_by_id(
        self,
        id: int,
        *,
        include_deleted: bool = False,
        load_options: list | None = None,
    ) -> ModelType | None:
        stmt = select(self.model).where(self.model.id == id)
        if not include_deleted:
            stmt = self.apply_soft_delete_filter(stmt)
        if load_options:
            stmt = stmt.options(*load_options)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_by_uuid(
        self,
        uuid: str,
        *,
        include_deleted: bool = False,
        load_options: list | None = None,
    ) -> ModelType | None:
        stmt = select(self.model).where(self.model.uuid == uuid)
        if not include_deleted:
            stmt = self.apply_soft_delete_filter(stmt)
        if load_options:
            stmt = stmt.options(*load_options)
        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_one(
        self,
        filters: dict,
        *,
        include_deleted: bool = False,
        load_options: list | None = None,
    ) -> ModelType | None:
        stmt = select(self.model)
        if not include_deleted:
            stmt = self.apply_soft_delete_filter(stmt)
        stmt = self._apply_filters(stmt, filters)
        if load_options:
            stmt = stmt.options(*load_options)
        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list(
        self,
        *,
        filters: dict | None = None,
        search: tuple[list[str], str] | None = None,
        order_by: str | None = None,
        page: int = 1,
        limit: int = 20,
        include_deleted: bool = False,
        only_active: bool | None = None,
        load_options: list | None = None,
    ) -> tuple[list[ModelType], int]:
        """Retourne (items, total). COUNT calculé avant LIMIT/OFFSET."""
        data = select(self.model)
        cnt = select(func.count()).select_from(self.model)

        if not include_deleted:
            data = self.apply_soft_delete_filter(data)
            cnt = cnt.where(self.model.deleted_at.is_(None))
        if only_active is not None:
            data = data.where(self.model.status == only_active)
            cnt = cnt.where(self.model.status == only_active)
        if filters:
            data = self._apply_filters(data, filters)
            cnt = self._apply_filters(cnt, filters)
        if search:
            data = self._apply_search(data, search)
            cnt = self._apply_search(cnt, search)

        total = (await self.session.execute(cnt)).scalar_one() or 0

        data = self._apply_order(data, order_by) if order_by else data.order_by(self.model.created_at.desc())
        data = data.limit(limit).offset(max(0, (page - 1) * limit))
        if load_options:
            data = data.options(*load_options)

        rows = await self.session.execute(data)
        return list(rows.scalars().all()), total

    async def exists(self, filters: dict) -> bool:
        stmt = select(func.count()).select_from(self.model)
        stmt = self.apply_soft_delete_filter(stmt)
        stmt = self._apply_filters(stmt, filters)
        return ((await self.session.execute(stmt)).scalar_one() or 0) > 0

    async def count(
        self,
        filters: dict | None = None,
        *,
        include_deleted: bool = False,
    ) -> int:
        stmt = select(func.count()).select_from(self.model)
        if not include_deleted:
            stmt = self.apply_soft_delete_filter(stmt)
        if filters:
            stmt = self._apply_filters(stmt, filters)
        return (await self.session.execute(stmt)).scalar_one() or 0

    # ── Écritures ─────────────────────────────────────────────────────────────

    async def create(self, data: dict, *, commit: bool = True) -> ModelType:
        """
        `commit=False` — flush au lieu de commit (id auto-incrémenté disponible
        immédiatement, cf. cursor.lastrowid ; `created_at`/`updated_at` restent
        server_default et ne sont donc peuplés qu'après un commit/refresh ou une
        lecture fraîche). Réservé aux flux qui orchestrent explicitement un commit
        unique en fin de transaction (ex. ServiceRequest.create()) — laisse la
        session dans un état "flush" en cas d'IntegrityError plutôt que de
        rollback, pour ne pas annuler des écritures antérieures déjà flush dans
        la même transaction (le rollback reste de la responsabilité de l'appelant
        ou de la savepoint englobante — cf. begin_nested()).
        """
        valid = self._valid_columns()
        row = {k: v for k, v in data.items() if k in valid}
        obj = self.model(**row)
        self.session.add(obj)
        try:
            if commit:
                await self.session.commit()
                await self.session.refresh(obj)
            else:
                await self.session.flush()
        except IntegrityError as exc:
            if commit:
                await self.session.rollback()
            _parse_integrity_error(exc)
        return obj

    async def bulk_create(self, data_list: list[dict], *, commit: bool = True) -> list[ModelType]:
        """`commit=False` — flush au lieu de commit ; voir docstring de `create()`."""
        valid = self._valid_columns()
        objs: list[ModelType] = []
        for data in data_list:
            row = {k: v for k, v in data.items() if k in valid}
            objs.append(self.model(**row))
        self.session.add_all(objs)
        try:
            if commit:
                await self.session.commit()
                for obj in objs:
                    await self.session.refresh(obj)
            else:
                await self.session.flush()
        except IntegrityError as exc:
            if commit:
                await self.session.rollback()
            _parse_integrity_error(exc)
        return objs

    async def update(self, id: int, data: dict, *, commit: bool = True) -> ModelType | None:
        """Ignore les clés inconnues et les champs protégés (id, created_at).
        `commit=False` — voir docstring de `create()`."""
        obj = await self.get_by_id(id)
        if obj is None:
            return None
        allowed = self._valid_columns() - _IMMUTABLE
        for k, v in data.items():
            if k in allowed:
                setattr(obj, k, v)
        try:
            if commit:
                await self.session.commit()
                await self.session.refresh(obj)
            else:
                await self.session.flush()
                # Important : les attributs dérivés d'une relation (ex. FK
                # `request_status_id` → propriété `request_status`) restent en
                # cache avec leur ancienne valeur après un simple flush — un
                # `session.expire(obj)` sans requête associée casse ensuite tout
                # accès synchrone à cet attribut sous SQLAlchemy async
                # (MissingGreenlet : le lazy-load implicite n'a nulle part où
                # s'exécuter). `refresh()` reste nécessaire ici — un SELECT dans
                # la MÊME transaction (donc voit ses propres écritures non
                # commitées), largement moins coûteux qu'un commit (pas de
                # fsync/round-trip de validation), et bien moins fréquent que
                # les anciens commits systématiques qu'il remplace.
                await self.session.refresh(obj)
        except IntegrityError as exc:
            if commit:
                await self.session.rollback()
            _parse_integrity_error(exc)
        return obj

    async def delete(self, id: int) -> bool:
        """SOFT delete — positionne deleted_at. JAMAIS de DELETE physique."""
        obj = await self.get_by_id(id)
        if obj is None:
            return False
        obj.deleted_at = datetime.now(timezone.utc).replace(tzinfo=None)
        await self.session.commit()
        return True

    async def restore(self, id: int) -> bool:
        obj = await self.get_by_id(id, include_deleted=True)
        if obj is None:
            return False
        obj.deleted_at = None
        await self.session.commit()
        return True

    async def hard_delete(self, id: int) -> bool:
        """DELETE physique irréversible — usage explicite et rare uniquement."""
        obj = await self.get_by_id(id, include_deleted=True)
        if obj is None:
            return False
        await self.session.delete(obj)
        await self.session.commit()
        return True

    async def activate(self, id: int) -> bool:
        obj = await self.get_by_id(id)
        if obj is None:
            return False
        obj.status = True
        await self.session.commit()
        return True

    async def deactivate(self, id: int) -> bool:
        obj = await self.get_by_id(id)
        if obj is None:
            return False
        obj.status = False
        await self.session.commit()
        return True

    async def get_or_create(
        self,
        filters: dict,
        defaults: dict | None = None,
        *,
        include_deleted: bool = False,
    ) -> tuple[ModelType, bool]:
        """Récupère ou crée. include_deleted=True prend aussi en compte les lignes
        soft-deletées : indispensable quand `filters` porte sur une colonne UNIQUE,
        car l'index unique ignore `deleted_at` et l'INSERT échouerait en 1062."""
        obj = await self.get_one(filters, include_deleted=include_deleted)
        if obj is not None:
            return obj, False
        return await self.create({**(defaults or {}), **filters}), True

    async def update_infos(self, id: int, patch: dict) -> ModelType | None:
        """Merge JSON de 1er niveau dans la colonne infos."""
        obj = await self.get_by_id(id)
        if obj is None:
            return None
        current = dict(obj.infos) if obj.infos else {}
        current.update(patch)
        obj.infos = current
        await self.session.commit()
        await self.session.refresh(obj)
        return obj


# ── Sous-classe pour les 12 tables de référence ───────────────────────────────

class ReferenceBaseRepository(BaseRepository[ModelType]):
    """
    Tables de référence dynamiques : code, label, sort_order, is_builtin.
    Héritée par les 12 repos de référence.
    """

    async def find_by_code(self, code: str) -> ModelType | None:
        return await self.get_one({"code": code})

    async def list_ordered(
        self, *, only_active: bool | None = True
    ) -> list[ModelType]:
        items, _ = await self.list(
            order_by="sort_order",
            limit=500,
            only_active=only_active,
        )
        return items

    async def list_builtin(self) -> list[ModelType]:
        items, _ = await self.list(
            filters={"is_builtin": True},
            order_by="sort_order",
            limit=500,
        )
        return items
