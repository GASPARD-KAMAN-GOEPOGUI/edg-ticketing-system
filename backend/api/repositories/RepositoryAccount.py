from __future__ import annotations

from sqlalchemy import and_, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.phone import is_phone_identifier, normalize_phone
from api.core.rbac import normalize_role
from api.models.ModelAccount import Account
from api.models.ModelUnity import Unity
from api.repositories.base_repository import BaseRepository


class AccountRepository(BaseRepository[Account]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Account, session)

    @staticmethod
    def _role_filter(role: str) -> str | list[str]:
        normalized = normalize_role(role)
        return ["director", "dg"] if normalized == "director" else normalized

    async def find_by_email(self, email: str) -> Account | None:
        return await self.get_one({"email": email})

    async def find_by_central_user_id(self, central_user_id: int) -> Account | None:
        return await self.get_one({"central_user_id": central_user_id})

    async def find_by_matricule(self, matricule: str) -> Account | None:
        return await self.get_one({"matricule": matricule})

    async def find_by_phone(self, phone: str) -> Account | None:
        return await self.get_one({"phone": phone})

    async def list_by_role(
        self, role: str, *, page: int = 1, limit: int = 20
    ) -> tuple[list[Account], int]:
        return await self.list(
            filters={"role": self._role_filter(role)},
            only_active=True,
            order_by="name",
            page=page,
            limit=limit,
        )

    async def list_agents(
        self,
        *,
        unity_id: int | None = None,
        availability: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[Account], int]:
        filters: dict = {"role": ["agent-support", "chief-service", "chief-departement"]}
        if unity_id:
            filters["unity_id"] = unity_id
        if availability:
            filters["availability"] = availability
        return await self.list(
            filters=filters, only_active=True, order_by="name",
            page=page, limit=limit,
        )

    async def list_by_direction(
        self, direction_id: int, *, page: int = 1, limit: int = 50
    ) -> tuple[list[Account], int]:
        unity_ids = await self._direction_unity_ids(direction_id)
        return await self.list(
            filters={"unity_id": unity_ids},
            only_active=True,
            order_by="name",
            page=page,
            limit=limit,
        )

    async def list_by_unit(
        self, unit_id: int, *, page: int = 1, limit: int = 50
    ) -> tuple[list[Account], int]:
        return await self.list(
            filters={"unity_id": unit_id},
            only_active=True,
            order_by="name",
            page=page,
            limit=limit,
        )

    async def list_by_role_and_direction(
        self, role: str, direction_id: int, *, page: int = 1, limit: int = 50
    ) -> tuple[list[Account], int]:
        unity_ids = await self._direction_unity_ids(direction_id)
        return await self.list(
            filters={"role": self._role_filter(role), "unity_id": unity_ids},
            only_active=True,
            order_by="name",
            page=page,
            limit=limit,
        )

    async def list_by_role_and_unit(
        self, role: str, unit_id: int, *, page: int = 1, limit: int = 50
    ) -> tuple[list[Account], int]:
        return await self.list(
            filters={"role": self._role_filter(role), "unity_id": unit_id},
            only_active=True,
            order_by="name",
            page=page,
            limit=limit,
        )

    async def _direction_unity_ids(self, direction_id: int) -> list[int]:
        root_id = int(direction_id)
        ids: list[int] = [root_id]

        from api.models.ModelOrganigram import Organigram as _Org

        org_row = await self.session.execute(
            select(_Org.id)
            .where(_Org.unity_id == root_id, _Org.deleted_at.is_(None))
            .limit(1)
        )
        org_id = org_row.scalar_one_or_none()
        if org_id:
            # Descend tout l'arbre Organigram (département -> service -> ...),
            # pas seulement les enfants directs, sinon les unités à 2+ niveaux
            # sous la direction (ex : Service sous Département) sont ignorées.
            frontier = [org_id]
            seen_org_ids = {org_id}
            while frontier:
                child_rows = await self.session.execute(
                    select(_Org.id, _Org.unity_id)
                    .where(_Org.parent_id.in_(frontier), _Org.deleted_at.is_(None))
                )
                next_frontier: list[int] = []
                for child_org_id, unity_id in child_rows.all():
                    if child_org_id in seen_org_ids:
                        continue
                    seen_org_ids.add(child_org_id)
                    next_frontier.append(child_org_id)
                    if unity_id is not None:
                        ids.append(int(unity_id))
                frontier = next_frontier

        unity_rows = await self.session.execute(
            select(Unity.id)
            .where(Unity.parent_direction_id == root_id, Unity.deleted_at.is_(None))
        )
        ids.extend(int(uid) for (uid,) in unity_rows.all() if uid is not None)
        return sorted(set(ids))

    def _apply_search(self, stmt, search: tuple[list[str], str]):
        """
        Sélecteur @mention (annuaire) — surcharge le comportement générique
        (`base_repository._apply_search`, un seul ILIKE par colonne) pour supporter :
          - un terme téléphone tolérant au formatage (espaces/tirets/indicatif),
            via `core/phone.py` déjà utilisé par l'inscription/le login ;
          - une recherche multi-mots ("Prénom Nom" / "Nom Prénom") : chaque mot doit
            matcher au moins une colonne (ET logique entre mots, OU entre colonnes),
            puisque prénom/nom vivent dans deux colonnes séparées et qu'aucune des
            deux ne contient la chaîne complète.
        Ne modifie pas `base_repository.py` (partagé par les autres repositories,
        ex. RequestRepository) — surcharge locale à Account uniquement, même
        principe que `RequestRepository._apply_filters`.
        """
        cols, term = search
        clean = (term or "").strip()
        if not clean:
            return stmt

        def _clauses(value: str):
            return [
                getattr(Account, c).ilike(f"%{value}%")
                for c in cols if getattr(Account, c, None) is not None
            ]

        if is_phone_identifier(clean):
            normalized = normalize_phone(clean) or clean
            values = {clean, normalized}
            clauses = [c for v in values for c in _clauses(v)]
            return stmt.where(or_(*clauses)) if clauses else stmt

        tokens = clean.split()
        if len(tokens) <= 1:
            clauses = _clauses(clean)
            return stmt.where(or_(*clauses)) if clauses else stmt

        token_clauses = [or_(*_clauses(token)) for token in tokens if _clauses(token)]
        return stmt.where(and_(*token_clauses)) if token_clauses else stmt

    async def search(
        self, term: str, *,
        direction_id: int | None = None,
        unit_id: int | None = None,
        page: int = 1, limit: int = 20,
    ) -> tuple[list[Account], int]:
        """`unit_id`/`direction_id` permettent de combiner la recherche libre avec
        les filtres organigramme déjà posés (Direction/Département/Service) au lieu
        de les ignorer — `unit_id` prioritaire s'il est fourni, sinon résolution de
        tous les services de `direction_id` via `_direction_unity_ids`."""
        filters: dict = {}
        if unit_id is not None:
            filters["unity_id"] = int(unit_id)
        elif direction_id is not None:
            filters["unity_id"] = await self._direction_unity_ids(int(direction_id))
        return await self.list(
            filters=filters or None,
            search=(["name", "firstname", "email", "matricule", "phone"], term),
            only_active=True,
            page=page,
            limit=limit,
        )

    async def set_availability(self, id: int, availability: str) -> Account | None:
        return await self.update(id, {"availability": availability})

    async def verify_email(self, id: int) -> Account | None:
        from datetime import datetime, timezone
        return await self.update(id, {
            "email_verified": True,
            "activated_at": datetime.now(timezone.utc).replace(tzinfo=None),
        })

    # ── Hiérarchie : chefs par unité/direction (pattern edgrh chiefs_by_units) ─

    async def find_chiefs_by_unit(self, unit_id: int) -> list[Account]:
        """Retourne les comptes avec role='chief-service' dans une unité donnée."""
        items, _ = await self.list(
            filters={"unity_id": unit_id, "role": self._role_filter("chief")},
            only_active=True,
            order_by="name",
            limit=50,
        )
        return items

    async def find_directors_by_direction(self, direction_id: int) -> list[Account]:
        """Retourne les directeurs (role='director') d'une direction."""
        items, _ = await self.list(
            filters={"unity_id": direction_id, "role": ["director", "dg"]},
            only_active=True,
            order_by="name",
            limit=20,
        )
        return items

    async def find_chief_for_unity(self, unity_id: int) -> Account | None:
        """Retourne le premier chef actif (role='chief') d'une unité, ou None."""
        chiefs = await self.find_chiefs_by_unit(unity_id)
        return chiefs[0] if chiefs else None

    async def find_support_agent(self) -> Account | None:
        """Retourne le premier agent actif disponible (fallback support général)."""
        items, _ = await self.list(
            filters={"role": "agent-support"},
            only_active=True,
            order_by="name",
            limit=1,
        )
        return items[0] if items else None

    async def find_approvers_for_request(
        self, *, unit_id: int | None = None, direction_id: int | None = None
    ) -> list[Account]:
        """
        Retourne les approbateurs potentiels d'une demande dans l'ordre :
        1. Chefs d'unité (role=chief, unity_id=unit_id)
        2. Directeurs (role=director, unity_id=direction_id)
        """
        approvers: list[Account] = []
        if unit_id:
            approvers += await self.find_chiefs_by_unit(unit_id)
        if direction_id:
            approvers += await self.find_directors_by_direction(direction_id)
        return approvers
