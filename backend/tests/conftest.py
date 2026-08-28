"""
Fixtures communes pour tous les tests API EDG Support.

Stratégie :
  - Base SQLite in-memory → tests isolés, pas de MySQL requis
  - MockAccount par rôle → simule get_current_user sans JWT réel
  - auth_client(role) → client HTTP prêt à l'emploi pour chaque rôle
  - setup_db (session scope) → create_all + seed références une seule fois
"""
from __future__ import annotations

import pytest
import pytest_asyncio
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from typing import Any

from httpx import AsyncClient, ASGITransport
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.pool import StaticPool

# ── Patch de compatibilité SQLite : types MySQL non supportés → TEXT/INTEGER ──
# SQLite ne connaît pas LONGTEXT, TINYINT(1), etc. — on enseigne au compilateur
# de SQLite comment les rendre sans modifier les modèles eux-mêmes.
from sqlalchemy.dialects.sqlite.base import SQLiteTypeCompiler

def _visit_LONGTEXT(self, type_, **kw):   return "TEXT"
def _visit_MEDIUMTEXT(self, type_, **kw): return "TEXT"
def _visit_TINYINT(self, type_, **kw):    return "INTEGER"

SQLiteTypeCompiler.visit_LONGTEXT   = _visit_LONGTEXT
SQLiteTypeCompiler.visit_MEDIUMTEXT = _visit_MEDIUMTEXT
SQLiteTypeCompiler.visit_TINYINT    = _visit_TINYINT

# ── Import du barrel de modèles (enregistre toutes les tables dans Base.metadata) ──
import api.models  # noqa
from api.models.base import Base

# ── Import de l'app APRÈS les modèles ─────────────────────────────────────────
from api.main import app
from api.dependencies import get_db, get_current_user

# ═══════════════════════════════════════════════════════════════════════════════
# BASE DE TEST (SQLite in-memory)
# ═══════════════════════════════════════════════════════════════════════════════

_TEST_DB_URL = "sqlite+aiosqlite:///:memory:"

_test_engine = create_async_engine(
    _TEST_DB_URL,
    connect_args={"check_same_thread": False},
    poolclass=StaticPool,
    echo=False,
)
_TestSession = async_sessionmaker(_test_engine, expire_on_commit=False, class_=AsyncSession)

# ── Patch de compatibilité SQLite : JSON_UNQUOTE (MySQL) sans équivalent ─────
# Le backend utilise du SQL brut MySQL (JSON_UNQUOTE(JSON_EXTRACT(...))) dans
# quelques requêtes (ex. RepositoryRequest.list_transmitted_by_actor). SQLite
# résout déjà JSON_EXTRACT via son extension JSON1 intégrée (et renvoie une
# valeur scalaire déjà "unquoted"), il ne connaît juste pas le nom
# JSON_UNQUOTE — on l'enregistre comme fonction identité, sans modifier le SQL
# métier ni les modèles.
from sqlalchemy import event


@event.listens_for(_test_engine.sync_engine, "connect")
def _register_sqlite_json_unquote(dbapi_connection, _):
    dbapi_connection.create_function("JSON_UNQUOTE", 1, lambda value: value)


async def _override_get_db() -> AsyncGenerator[AsyncSession, None]:
    """Reproduit fidèlement `api.dependencies.get_db()` (commit après un yield
    réussi, rollback sur exception). Nécessaire depuis l'harmonisation
    transactionnelle (2026-08) de ServiceRequest.create()/_apply_routing() :
    ces flux flush (commit=False) plusieurs écritures et comptent sur ce
    commit de fin de requête pour les persister — sans lui, elles étaient
    silencieusement perdues à la fermeture de la session de test (rollback
    implicite de SQLAlchemy sur une transaction non commitée), ce qui ne
    reproduisait pas le comportement réel de production."""
    async with _TestSession() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


# Override global : toute la suite de tests utilise SQLite
app.dependency_overrides[get_db] = _override_get_db

# RateLimitMiddleware (main.py) partage un store en mémoire pour tout le
# process pytest (pas de Redis en test) — sans ceci, les nombreux tests qui
# appellent POST /auth/login dans le même fichier finissent par dépasser la
# limite de prod (10/60s) et échouent avec 429, sans rapport avec ce qu'ils
# testent réellement. Purement un ajustement de suite de tests, la valeur de
# _RATE_LIMITS en production (main.py) n'est pas modifiée.
from api import main as _main_module
for _path in _main_module._RATE_LIMITS:
    _main_module._RATE_LIMITS[_path] = (100_000, 60)


# ═══════════════════════════════════════════════════════════════════════════════
# SETUP / TEARDOWN DE SESSION
# ═══════════════════════════════════════════════════════════════════════════════

@pytest_asyncio.fixture(scope="session", autouse=True)
async def setup_db():
    """Crée les tables et seed les références une seule fois pour la session de tests."""
    from api.seed_references import seed_references

    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    async with _TestSession() as session:
        await seed_references(session)
        await session.commit()

    yield

    async with _test_engine.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


# ═══════════════════════════════════════════════════════════════════════════════
# COMPTES MOCK (pas de DB nécessaire pour l'injection de rôle)
# ═══════════════════════════════════════════════════════════════════════════════

class MockAccount:
    """Substitut minimal du modèle Account pour l'injection de dépendance get_current_user."""

    def __init__(
        self,
        role: str,
        id: int = 1,
        unity_id: int | None = None,
    ) -> None:
        self.id = id
        self.role = role
        self.unity_id = unity_id
        self.name = f"Test {role.capitalize()}"
        self.firstname = "Test"
        self.email = f"{role}@test.edg.gn"
        self.phone = None
        self.matricule = f"M{id:05d}"
        self.job = f"Poste {role}"
        self.status = True
        self.deleted_at = None
        self.uuid = f"00000000-0000-0000-0000-{id:012d}"
        self.availability = "available"
        self.account_status = "active"
        self.notif_email = False
        self.notif_sms = False
        self.mfa_enabled = False
        self.avatar = None
        self.central_user_id = None
        self.central_user_uuid = None
        self.infos = None


# Un compte par rôle (IDs distincts pour éviter les collisions)
MOCK_ACCOUNTS: dict[str, MockAccount] = {
    "public":   MockAccount("public",   id=0),
    "user":     MockAccount("user",     id=1),
    "agent":    MockAccount("agent",    id=2, unity_id=1),
    "chief":    MockAccount("chief",    id=3, unity_id=1),
    "director": MockAccount("director", id=4, unity_id=1),
    "dg":       MockAccount("dg",       id=5),
    "admin":    MockAccount("admin",    id=6),
}

# Un deuxième compte "user" pour les tests d'ownership croisé
MOCK_OTHER_USER = MockAccount("user", id=99)


def _role_override(role: str):
    """Retourne une dépendance FastAPI synchrone qui injecte le MockAccount du rôle donné."""
    mock = MOCK_ACCOUNTS[role]
    def _dep() -> MockAccount:
        return mock
    return _dep


# ═══════════════════════════════════════════════════════════════════════════════
# FACTORY DE CLIENTS HTTP AUTHENTIFIÉS
# ═══════════════════════════════════════════════════════════════════════════════

@pytest.fixture
def auth_client():
    """
    Retourne une factory renvoyant un AsyncContextManager<AsyncClient>.

    Usage dans un test :
        async def test_xxx(auth_client):
            async with auth_client("admin") as client:
                r = await client.get("/api/v1/...")
    """
    @asynccontextmanager
    async def _factory(role: str):
        app.dependency_overrides[get_current_user] = _role_override(role)
        async with AsyncClient(
            transport=ASGITransport(app=app), base_url="http://test"
        ) as client:
            yield client
        app.dependency_overrides.pop(get_current_user, None)

    return _factory


@pytest.fixture
async def anon_client() -> AsyncGenerator[AsyncClient, None]:
    """Client sans authentification (pas d'override get_current_user)."""
    # S'assurer que get_current_user n'est pas overridé
    app.dependency_overrides.pop(get_current_user, None)
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client


# ═══════════════════════════════════════════════════════════════════════════════
# MOCK DE LA PLATEFORME CENTRALE manager-user (pas d'appel réseau en test)
# ═══════════════════════════════════════════════════════════════════════════════

# Compteur PARTAGÉ au niveau module (pas par instance de registre) — la DB de
# test est persistée pour toute la session pytest (setup_db, scope="session"),
# alors qu'une nouvelle _CentralAuthRegistry est créée à chaque test qui demande
# mock_central_auth. Un compteur par-instance recommencerait à 90000 à chaque
# test et entrerait en collision (contrainte UNIQUE sur central_user_id/uuid)
# avec les comptes déjà créés par des tests précédents dans la même session.
import itertools as _itertools
_central_id_counter = _itertools.count(90000)


class _CentralAuthRegistry:
    """Registre en mémoire d'identités centrales simulées pour les tests."""

    def __init__(self) -> None:
        self.users: dict[str, dict] = {}   # email(lower) -> {password, user_id, uuid, groups}
        self.tokens: dict[str, str] = {}   # bearer -> email(lower)
        self.added_memberships: list[tuple[str, str]] = []  # (user_uuid, group_codename)

    def register(
        self, *, email: str, password: str, user_id: int,
        groups: list[str] | None = None, inactive_groups: list[str] | None = None,
        uuid: str | None = None,
        name: str | None = None, firstname: str | None = None, phone: str | None = None,
    ) -> None:
        self.users[email.lower()] = {
            "password": password,
            "user_id": user_id,
            "uuid": uuid or f"uuid-{user_id}",
            "groups": groups or [],
            "inactive_groups": inactive_groups or [],
            "name": name,
            "firstname": firstname,
            "phone": phone,
        }

    def _generate_id(self) -> int:
        return next(_central_id_counter)


@pytest_asyncio.fixture
async def mock_central_auth(monkeypatch):
    """
    Monkeypatch api.core.central_auth pour simuler la plateforme centrale
    (source-token/login/refresh/scopes/groupes) sans appel réseau réel.

    Usage :
        async def test_xxx(mock_central_auth):
            mock_central_auth.register(email="a@edg.gn", password="Pwd123!", user_id=1001, groups=["admin-support"])
            ...  # POST /api/v1/auth/login avec identifier="a@edg.gn", password="Pwd123!"
    """
    import api.core.central_auth as central_auth_module

    registry = _CentralAuthRegistry()

    async def fake_central_login(email: str, password: str):
        user = registry.users.get(email.lower())
        if user is None or user["password"] != password:
            raise central_auth_module.CentralInvalidCredentials("Identifiant ou mot de passe incorrect.")
        token = f"central-bearer-{user['user_id']}"
        registry.tokens[token] = email.lower()
        return {
            "bearer_token": token,
            "refresh_token": f"central-refresh-{user['user_id']}",
            "token_type": "bearer",
            "expires_in": 180,
        }

    async def fake_central_refresh(refresh_token: str):
        if not refresh_token.startswith("central-refresh-"):
            raise central_auth_module.CentralInvalidCredentials("Refresh token invalide.")
        user_id = refresh_token[len("central-refresh-"):]
        token = f"central-bearer-{user_id}"
        if token not in registry.tokens:
            raise central_auth_module.CentralInvalidCredentials("Refresh token invalide.")
        return {"bearer_token": token, "token_type": "bearer", "expires_in": 180}

    async def fake_get_scopes(bearer_token: str):
        email = registry.tokens.get(bearer_token)
        if email is None:
            raise central_auth_module.CentralInvalidCredentials("Session invalide.")
        user = registry.users[email]
        return {
            "actor_type": "user", "user_id": user["user_id"], "user_uuid": user["uuid"],
            "email": email, "scopes": [],
        }

    async def fake_get_groups(bearer_token: str):
        email = registry.tokens.get(bearer_token)
        if email is None:
            raise central_auth_module.CentralInvalidCredentials("Session invalide.")
        user = registry.users[email]
        return [
            {"codename": g, "is_activated": True} for g in user["groups"]
        ] + [
            {"codename": g, "is_activated": False} for g in user.get("inactive_groups", [])
        ]

    async def fake_get_profile(bearer_token: str):
        email = registry.tokens.get(bearer_token)
        if email is None:
            raise central_auth_module.CentralInvalidCredentials("Session invalide.")
        user = registry.users[email]
        return {
            "uuid": user["uuid"],
            "email": email,
            "name": user.get("firstname"),        # convention centrale : name = prénom
            "last_name": user.get("name"),         # last_name = nom de famille
            "phone": user.get("phone"),
        }

    async def fake_log_central_event(*args, **kwargs):
        return None

    # ── Mutation de comptes (gestion de comptes, phase 2) ────────────────────

    async def fake_get_machine_token():
        return "central-machine-token"

    async def fake_create_central_account(*, group_codename, email, phone, firstname, last_name, password):
        user_id = registry._generate_id()
        uuid = f"uuid-{user_id}"
        registry.users[email.lower()] = {
            "password": password, "user_id": user_id, "uuid": uuid, "groups": [group_codename],
        }
        return {
            "status": "created_and_added", "message": None, "user_id": user_id,
            "user_uuid": uuid, "user_is_activated": True, "group_codename": group_codename,
        }

    async def fake_update_central_account(user_uuid, *, email, phone, firstname, last_name, machine_token):
        return {"user_uuid": user_uuid, "email": email, "phone": phone, "name": firstname, "last_name": last_name}

    async def fake_add_group_membership(user_uuid, group_codename, machine_token):
        registry.added_memberships.append((user_uuid, group_codename))
        return None

    async def fake_remove_group_membership(user_uuid, group_codename, machine_token):
        return None

    async def fake_activate_central_account(user_uuid, machine_token):
        return None

    async def fake_deactivate_central_account(user_uuid, machine_token):
        return None

    async def fake_reset_central_password(user_uuid, machine_token):
        return central_auth_module._DEFAULT_RESET_PASSWORD

    async def fake_delete_central_account(user_id, user_bearer):
        return None

    monkeypatch.setattr(central_auth_module, "central_login", fake_central_login)
    monkeypatch.setattr(central_auth_module, "central_refresh", fake_central_refresh)
    monkeypatch.setattr(central_auth_module, "get_scopes", fake_get_scopes)
    monkeypatch.setattr(central_auth_module, "get_groups", fake_get_groups)
    monkeypatch.setattr(central_auth_module, "get_profile", fake_get_profile)
    monkeypatch.setattr(central_auth_module, "log_central_event", fake_log_central_event)
    monkeypatch.setattr(central_auth_module, "get_machine_token", fake_get_machine_token)
    monkeypatch.setattr(central_auth_module, "create_central_account", fake_create_central_account)
    monkeypatch.setattr(central_auth_module, "update_central_account", fake_update_central_account)
    monkeypatch.setattr(central_auth_module, "add_group_membership", fake_add_group_membership)
    monkeypatch.setattr(central_auth_module, "remove_group_membership", fake_remove_group_membership)
    monkeypatch.setattr(central_auth_module, "activate_central_account", fake_activate_central_account)
    monkeypatch.setattr(central_auth_module, "deactivate_central_account", fake_deactivate_central_account)
    monkeypatch.setattr(central_auth_module, "reset_central_password", fake_reset_central_password)
    monkeypatch.setattr(central_auth_module, "delete_central_account", fake_delete_central_account)

    return registry


# ═══════════════════════════════════════════════════════════════════════════════
# FIXTURES DE DONNÉES (helpers réutilisables)
# ═══════════════════════════════════════════════════════════════════════════════

@pytest_asyncio.fixture
async def test_unity(setup_db) -> dict[str, Any]:
    """Crée une unity de test et retourne son dict de réponse."""
    async with _TestSession() as session:
        from api.models.ModelUnity import Unity
        u = Unity()
        u.codename = "TST"
        u.label = "Unity Test"
        u.aleas = "TST"
        u.status = True
        session.add(u)
        await session.commit()
        await session.refresh(u)
        return {"id": u.id, "codename": u.codename, "label": u.label}


@asynccontextmanager
async def _async_admin_client():
    app.dependency_overrides[get_current_user] = _role_override("admin")
    async with AsyncClient(
        transport=ASGITransport(app=app), base_url="http://test"
    ) as client:
        yield client
    app.dependency_overrides.pop(get_current_user, None)


@pytest_asyncio.fixture(scope="session")
async def unity_id(setup_db) -> int:
    """Crée une unity de test (une seule fois par session) et retourne son id."""
    from sqlalchemy import select
    from api.models.ModelUnity import Unity

    async with _TestSession() as session:
        result = await session.execute(
            select(Unity).where(Unity.codename == "TSDIR")
        )
        existing = result.scalar_one_or_none()
        if existing is not None:
            return existing.id

        u = Unity()
        u.codename = "TSDIR"
        u.label = "Direction de Test"
        u.aleas = "TSDIR"
        u.status = True
        session.add(u)
        await session.flush()
        uid = u.id
        await session.commit()
    return uid


@pytest_asyncio.fixture(scope="session")
async def request_id(setup_db, unity_id) -> str:
    """Crée une demande de test (une seule fois par session) et retourne son id (string)."""
    async with _async_admin_client() as client:
        payload = {
            "title": "Demande de test baseline",
            "description": "Description de la demande de test.",
            "category": "panne",
            "priority": "medium",
            "is_external": False,
            "unity_id": unity_id,
            "requester_name": "Citoyen Test",
            "requester_email": "citoyen@test.edg.gn",
        }
        resp = await client.post("/api/v1/requests/", json=payload)
        if resp.status_code == 201:
            data = resp.json()
            body = data.get("data", data)
            return str(body["id"])
    return None
