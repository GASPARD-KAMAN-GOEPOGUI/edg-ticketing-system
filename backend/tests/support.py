"""Outillage partagé des tests — module unique (et non conftest.py, que pytest
charge sous un autre nom de module : deux copies auraient deux bases)."""
from __future__ import annotations

import itertools
import os
import tempfile

from httpx import AsyncClient
from sqlalchemy import event
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

# Types MySQL inconnus de SQLite — rendus sans modifier les modèles.
SQLiteTypeCompiler.visit_LONGTEXT = lambda self, type_, **kw: "TEXT"
SQLiteTypeCompiler.visit_MEDIUMTEXT = lambda self, type_, **kw: "TEXT"
SQLiteTypeCompiler.visit_TINYINT = lambda self, type_, **kw: "INTEGER"

import api.models  # noqa: F401,E402 — enregistre toutes les tables
from api.core import central_auth  # noqa: E402
from api.models.ModelAccount import Account  # noqa: E402
from api.models.base import Base  # noqa: E402,F401

# Fichier temporaire plutôt que `:memory:` : une base en mémoire vit dans UNE
# connexion, or pytest-asyncio peut changer de boucle entre fixture et test.
_DB_PATH = os.path.join(tempfile.mkdtemp(prefix="edg-tests-"), "test.db")
_engine = create_async_engine(
    f"sqlite+aiosqlite:///{_DB_PATH}",
    connect_args={"check_same_thread": False},
    poolclass=NullPool,
)
TestSession = async_sessionmaker(_engine, expire_on_commit=False, class_=AsyncSession)


@event.listens_for(_engine.sync_engine, "connect")
def _sqlite_functions(dbapi_connection, _):
    dbapi_connection.create_function("JSON_UNQUOTE", 1, lambda value: value)



class FakeCentral:
    """Plateforme centrale simulée : émet des tokens opaques qu'elle continue
    d'accepter après un changement de rôle local (exactement comme la vraie),
    et suit l'appartenance aux groupes que le Backoffice lui pousse."""

    def __init__(self) -> None:
        self._seq = itertools.count(1)
        self.access: dict[str, int] = {}    # access token -> central_user_id
        self.refresh: dict[str, int] = {}   # refresh token -> central_user_id
        self.users: dict[str, int] = {}     # email -> central_user_id
        self.disabled: set[int] = set()
        self.groups: dict[int, set[str]] = {}  # central_user_id -> groupes

    def issue(self, central_user_id: int) -> dict:
        n = next(self._seq)
        access, refresh = f"access-{central_user_id}-{n}", f"refresh-{central_user_id}-{n}"
        self.access[access] = central_user_id
        self.refresh[refresh] = central_user_id
        return {"bearer_token": access, "access_token": access, "refresh_token": refresh,
                "token_type": "bearer", "expires_in": 300}

    async def central_login(self, email: str, password: str) -> dict:
        cid = self.users.get(email)
        if cid is None or cid in self.disabled or password != "secret":
            raise central_auth.CentralInvalidCredentials("Identifiant ou mot de passe incorrect.")
        return self.issue(cid)

    async def central_refresh(self, refresh_token: str) -> dict:
        cid = self.refresh.get(refresh_token)
        if cid is None or cid in self.disabled:
            raise central_auth.CentralInvalidCredentials("Session expirée.")
        return self.issue(cid)

    async def get_scopes(self, token: str) -> dict:
        cid = self.access.get(token)
        if cid is None:
            raise central_auth.CentralInvalidCredentials("Session invalide ou expirée.")
        return {"user_id": cid, "email": next(e for e, c in self.users.items() if c == cid)}

    async def get_groups(self, token: str) -> list:
        cid = self.access.get(token)
        if cid is None:
            raise central_auth.CentralInvalidCredentials("Session invalide ou expirée.")
        return [{"codename": g, "is_activated": True} for g in sorted(self.groups.get(cid, set()))]

    async def add_group(self, user_uuid: str, group_codename: str, machine_token: str) -> None:
        self.groups.setdefault(int(user_uuid.split("-")[-1]), set()).add(group_codename)

    async def remove_group(self, user_uuid: str, group_codename: str, machine_token: str) -> None:
        self.groups.setdefault(int(user_uuid.split("-")[-1]), set()).discard(group_codename)

    async def deactivate(self, user_uuid: str, machine_token: str) -> None:
        self.disabled.add(int(user_uuid.split("-")[-1]))

    async def activate(self, user_uuid: str, machine_token: str) -> None:
        self.disabled.discard(int(user_uuid.split("-")[-1]))


_ip_seq = itertools.count(1)


async def make_account(central: FakeCentral, *, email: str, role: str, central_id: int) -> int:
    async with TestSession() as session:
        account = Account(
            name=email.split("@")[0], email=email, role=role,
            central_user_id=central_id, central_user_uuid=f"uuid-{central_id}",
            account_status="active", status=True,
        )
        session.add(account)
        await session.commit()
        central.users[email] = central_id
        central.groups[central_id] = {central_auth.group_for_role(role)}
        return account.id


async def login(client: AsyncClient, email: str) -> dict:
    """POST /auth/login ; chaque appel vient d'une IP distincte (rate limiter)."""
    resp = await client.post(
        "/api/v1/auth/login",
        json={"identifier": email, "password": "secret"},
        headers={"X-Forwarded-For": f"10.0.0.{next(_ip_seq)}"},
    )
    return {"status": resp.status_code, "body": resp.json()}


def bearer(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


def drain(q) -> list[dict]:
    items = []
    while not q.empty():
        items.append(q.get_nowait())
    return items


def use_mysql_state(monkeypatch) -> None:
    """STATE_BACKEND=mysql sur la base de test : liaisons de session et
    compteurs de tentatives en tables, sans aucune mémoire de processus."""
    from api.configs import Database, Environment

    monkeypatch.setattr(Environment.get_environment(), "STATE_BACKEND", "mysql")
    monkeypatch.setattr(Database, "AsyncSessionLocal", TestSession)
