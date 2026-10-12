"""
Fixtures des tests backend.

Stratégie :
  - Base SQLite temporaire (aucun MySQL requis, voir tests/support.py) — `get_db` remplacé par une
    copie fidèle (commit, publication des événements différés, rollback).
  - Plateforme centrale SIMULÉE (`FakeCentral`) : login, refresh, scopes,
    mutations de compte. `get_current_user` n'est PAS remplacé — la chaîne
    d'authentification réelle (dependencies.py) est éprouvée.
"""
from __future__ import annotations

import os
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from tests.support import Base, FakeCentral, TestSession, _engine, use_mysql_state
from api.main import app
from api import dependencies
from api.core import central_auth, session_registry
from api.core.event_bus import discard_pending, event_bus, publish_pending
from api.services.ServiceAccount import AccountService


async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
    async with TestSession() as session:
        try:
            yield session
            await session.commit()
            await publish_pending(session)
        except Exception:
            await session.rollback()
            discard_pending(session)
            raise


@pytest.fixture
def central(monkeypatch) -> FakeCentral:
    fake = FakeCentral()

    async def _noop(*args, **kwargs):
        return None

    async def _machine_token():
        return "machine"

    monkeypatch.setattr(central_auth, "central_login", fake.central_login)
    monkeypatch.setattr(central_auth, "central_refresh", fake.central_refresh)
    monkeypatch.setattr(central_auth, "get_scopes", fake.get_scopes)
    monkeypatch.setattr(central_auth, "get_groups", fake.get_groups)
    monkeypatch.setattr(central_auth, "get_machine_token", _machine_token)
    monkeypatch.setattr(central_auth, "add_group_membership", fake.add_group)
    monkeypatch.setattr(central_auth, "remove_group_membership", fake.remove_group)
    monkeypatch.setattr(central_auth, "update_central_account", _noop)
    monkeypatch.setattr(central_auth, "activate_central_account", fake.activate)
    monkeypatch.setattr(central_auth, "deactivate_central_account", fake.deactivate)
    monkeypatch.setattr(central_auth, "log_central_event", _noop)
    # Hors sujet ici : l'affectation organisationnelle exigée par certains rôles.
    monkeypatch.setattr(AccountService, "_validate_role_org_assignment", _noop)
    return fake


@pytest_asyncio.fixture(autouse=True)
async def _isolated(monkeypatch):
    monkeypatch.setattr(dependencies._env, "DISABLE_AUTH", False)
    monkeypatch.setattr(dependencies._env, "CENTRAL_AUTH_CACHE_TTL", 0)
    # Le client de test (ASGITransport) se connecte depuis 127.0.0.1 : déclaré
    # proxy de confiance pour que `login()` varie l'IP via X-Forwarded-For.
    monkeypatch.setattr(dependencies._env, "TRUSTED_PROXIES", ["127.0.0.1"])
    # EDG_TEST_STATE_BACKEND=mysql : toute la suite tourne avec l'état partagé
    # en base (session_binding, rate_limit_counter) — celui de la production cPanel.
    if os.environ.get("EDG_TEST_STATE_BACKEND") == "mysql":
        use_mysql_state(monkeypatch)
    session_registry.reset_for_tests()
    # Liaisons en mémoire, même si le .env local déclare REDIS_URL.
    session_registry._store._redis_checked = True
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)
        await conn.run_sync(Base.metadata.create_all)
    app.dependency_overrides[dependencies.get_db] = _override_get_db
    yield
    app.dependency_overrides.pop(dependencies.get_db, None)
    session_registry.reset_for_tests()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def subscribe():
    """Abonnés SSE simulés directement sur le bus (fan-out réel)."""
    subs: list = []

    async def _subscribe(user_id: int, role: str):
        q = await event_bus.subscribe(user_id, role)
        subs.append((user_id, q))
        return q

    yield _subscribe
    for user_id, q in subs:
        await event_bus.unsubscribe(user_id, q)
