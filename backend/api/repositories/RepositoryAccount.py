from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from api.models.ModelAccount import Account
from api.repositories.base_repository import BaseRepository


class AccountRepository(BaseRepository[Account]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Account, session)

    async def find_by_email(self, email: str) -> Account | None:
        return await self.get_one({"email": email})

    async def find_by_keycloak_id(self, keycloak_id: str) -> Account | None:
        return await self.get_one({"keycloak_id": keycloak_id})

    async def find_by_matricule(self, matricule: str) -> Account | None:
        return await self.get_one({"matricule": matricule})

    async def find_by_phone(self, phone: str) -> Account | None:
        return await self.get_one({"phone": phone})

    async def list_by_role(
        self, role: str, *, page: int = 1, limit: int = 20
    ) -> tuple[list[Account], int]:
        return await self.list(
            filters={"role": role},
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
        filters: dict = {"role": ["agent", "chief"]}
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
        return await self.list(
            filters={"unity_id": direction_id},
            only_active=True,
            order_by="name",
            page=page,
            limit=limit,
        )

    async def search(
        self, term: str, *, page: int = 1, limit: int = 20
    ) -> tuple[list[Account], int]:
        return await self.list(
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
        """Retourne les comptes avec role='chief' dans une unité donnée."""
        items, _ = await self.list(
            filters={"unity_id": unit_id, "role": "chief"},
            only_active=True,
            order_by="name",
            limit=50,
        )
        return items

    async def find_directors_by_direction(self, direction_id: int) -> list[Account]:
        """Retourne les directeurs (role='director') d'une direction."""
        items, _ = await self.list(
            filters={"unity_id": direction_id, "role": "director"},
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
            filters={"role": "agent"},
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
