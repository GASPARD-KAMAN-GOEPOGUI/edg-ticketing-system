"""
STATE_BACKEND=mysql — état partagé en base pour la production cPanel
(plusieurs processus Passenger, pas de Redis).

Le « deuxième processus » est simulé par ce qui le caractérise : aucune
mémoire commune (registre de sessions vidé, cache des scopes vidé) et, pour
les compteurs, un second moteur SQLAlchemy (autre pool de connexions) sur la
même base. Le test sur deux vrais processus MySQL est fait à part (compte rendu).
"""
from __future__ import annotations

import logging
import time
from datetime import datetime, timedelta
from types import SimpleNamespace

import pytest
from sqlalchemy import event, func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.pool import NullPool

from api import cli, dependencies
from api.core import rate_limit_store, session_registry, state_cleanup
from api.models.ModelAccount import Account
from api.models.ModelAppLock import AppLock
from api.models.ModelRateLimitCounter import RateLimitCounter
from api.models.ModelRevokedToken import RevokedToken
from api.models.ModelSessionBinding import SessionBinding
from tests.support import _DB_PATH, TestSession, _engine, bearer, login, make_account, use_mysql_state


def _other_process() -> None:
    """Ce qu'un autre processus Passenger n'a pas : la mémoire de celui-ci."""
    session_registry.reset_for_tests()
    session_registry._store._redis_checked = True
    dependencies.invalidate_central_auth_cache()


async def _bump_session_version(account_id: int) -> None:
    """Révocation locale (changement de rôle) telle que l'écrit ServiceAccount."""
    async with TestSession() as s:
        acc = await s.get(Account, account_id)
        acc.infos = session_registry.revoked_infos(acc, session_registry.REASON_ROLE_CHANGED)
        await s.commit()


# ── Garde de production ───────────────────────────────────────────────────────

@pytest.mark.parametrize("app_env,redis,backend,ok", [
    ("production", "", "auto", False),
    ("production", "", "mysql", True),
    ("production", "redis://h:6379/0", "auto", True),
    ("production", "", "redis", False),
    ("development", "", "auto", True),
    ("development", "", "memoire", False),
])
def test_production_guard(app_env, redis, backend, ok):
    env = SimpleNamespace(APP_ENV=app_env, REDIS_URL=redis, STATE_BACKEND=backend)
    if ok:
        dependencies.check_state_backend_config(env)
    else:
        with pytest.raises(RuntimeError):
            dependencies.check_state_backend_config(env)


# ── Révocation de session partagée ────────────────────────────────────────────

async def test_revocation_seen_by_another_process(client, central, monkeypatch):
    use_mysql_state(monkeypatch)
    acc = await make_account(central, email="me@edg.gn", role="user", central_id=10)
    tok = (await login(client, "me@edg.gn"))["body"]["data"]["access_token"]
    assert (await client.get("/api/v1/auth/me", headers=bearer(tok))).status_code == 200

    async with TestSession() as s:  # liaison en base, empreinte seule
        rows = (await s.execute(select(SessionBinding))).scalars().all()
    assert rows and all(len(r.token_hash) == 64 and r.token_hash != tok for r in rows)

    await _bump_session_version(acc)
    t0 = time.perf_counter()
    _other_process()
    resp = await client.get("/api/v1/auth/me", headers=bearer(tok))
    delay_ms = (time.perf_counter() - t0) * 1000
    assert resp.status_code == 401 and resp.json()["error_code"] == "SESSION_REVOKED"
    print(f"\nREVOCATION refusée dès la requête suivante, autre processus : {delay_ms:.1f} ms")


async def test_memory_backend_accepts_revoked_token_in_another_process(client, central, monkeypatch):
    """Défaut corrigé par STATE_BACKEND=mysql, démontré en mode mémoire."""
    monkeypatch.setattr(dependencies._env, "STATE_BACKEND", "auto")
    monkeypatch.setattr(dependencies._env, "REDIS_URL", "")
    acc = await make_account(central, email="me@edg.gn", role="user", central_id=10)
    tok = (await login(client, "me@edg.gn"))["body"]["data"]["access_token"]
    await _bump_session_version(acc)
    _other_process()
    assert (await client.get("/api/v1/auth/me", headers=bearer(tok))).status_code == 200


async def test_first_sight_binding_keeps_other_process_binding(monkeypatch):
    use_mysql_state(monkeypatch)
    acc = SimpleNamespace(id=7, infos={"session_version": 3})
    async with TestSession() as s:  # liée par le « processus A » à la version 2
        s.add(SessionBinding(token_hash=session_registry._token_key("t"), account_id=7, version=2,
                             expires_at=datetime.utcnow() + timedelta(hours=1)))
        await s.commit()
    async with TestSession() as s:  # le « processus B » la voit et refuse
        with pytest.raises(session_registry.SessionRevokedException):
            await session_registry.ensure_token_current("t", acc, db=s)
        await s.commit()
    async with TestSession() as s:
        assert (await s.get(SessionBinding, session_registry._token_key("t"))).version == 2


# ── Limitation des tentatives partagée ────────────────────────────────────────

async def test_rate_limit_counter_shared_between_two_engines():
    other = create_async_engine(f"sqlite+aiosqlite:///{_DB_PATH}", poolclass=NullPool)
    OtherSession = async_sessionmaker(other, expire_on_commit=False, class_=AsyncSession)
    try:
        counts = [
            await rate_limit_store.hit(TestSession if i % 2 == 0 else OtherSession, "rl:1.2.3.4:/login", 60)
            for i in range(6)
        ]
    finally:
        await other.dispose()
    assert counts == [1, 2, 3, 4, 5, 6]


async def test_rate_limit_middleware_with_mysql_state(client, central, monkeypatch):
    use_mysql_state(monkeypatch)
    codes = []
    for _ in range(12):  # même IP de connexion, aucun proxy de confiance
        monkeypatch.setattr(dependencies._env, "TRUSTED_PROXIES", [])
        r = await client.post("/api/v1/auth/login", json={"identifier": "x@edg.gn", "password": "x"})
        codes.append(r.status_code)
    assert 429 not in codes[:10] and codes[10:] == [429, 429]
    async with TestSession() as s:
        row = (await s.execute(select(RateLimitCounter))).scalar_one()
    assert row.key_hash == rate_limit_store.key_hash("rl:127.0.0.1:/api/v1/auth/login") and row.count == 12


async def test_expired_window_restarts_at_one():
    assert await rate_limit_store.hit(TestSession, "k", 60) == 1
    assert await rate_limit_store.hit(TestSession, "k", 60) == 2
    async with TestSession() as s:
        (await s.get(RateLimitCounter, rate_limit_store.key_hash("k"))).expires_at = datetime.utcnow() - timedelta(seconds=1)
        await s.commit()
    assert await rate_limit_store.hit(TestSession, "k", 60) == 1


async def test_rate_limit_db_error_fails_open_with_warning(client, central, monkeypatch, caplog):
    use_mysql_state(monkeypatch)

    async def broken(*args, **kwargs):
        raise RuntimeError("base injoignable")

    monkeypatch.setattr(rate_limit_store, "hit", broken)
    with caplog.at_level(logging.WARNING):
        r = await client.post("/api/v1/auth/login", json={"identifier": "x@edg.gn", "password": "x"})
    assert r.status_code != 429  # même comportement que le chemin Redis
    assert any("RateLimitMiddleware MySQL erreur" in m and rec.levelno == logging.WARNING
               for rec in caplog.records for m in [rec.getMessage()])


# ── Coût par requête authentifiée ─────────────────────────────────────────────

async def _measure(client, tok: str, n: int = 40) -> tuple[int, float]:
    statements: list[str] = []

    def count(conn, cursor, stmt, *a):
        statements.append(stmt)

    event.listen(_engine.sync_engine, "before_cursor_execute", count)
    try:
        statements.clear()
        await client.get("/api/v1/auth/me", headers=bearer(tok))
        per_request = len(statements)
        t0 = time.perf_counter()
        for _ in range(n):
            await client.get("/api/v1/auth/me", headers=bearer(tok))
        avg_ms = (time.perf_counter() - t0) * 1000 / n
    finally:
        event.remove(_engine.sync_engine, "before_cursor_execute", count)
    return per_request, avg_ms


async def test_query_count_and_overhead_per_authenticated_request(client, central, monkeypatch):
    await make_account(central, email="me@edg.gn", role="user", central_id=10)
    tok = (await login(client, "me@edg.gn"))["body"]["data"]["access_token"]
    await client.get("/api/v1/auth/me", headers=bearer(tok))
    mem_q, mem_ms = await _measure(client, tok)

    use_mysql_state(monkeypatch)
    tok2 = (await login(client, "me@edg.gn"))["body"]["data"]["access_token"]
    await client.get("/api/v1/auth/me", headers=bearer(tok2))
    sql_q, sql_ms = await _measure(client, tok2)

    print(f"\nREQUETES SQL par GET /auth/me : memoire={mem_q} mysql={sql_q} (+{sql_q - mem_q})")
    print(f"LATENCE moyenne (SQLite, 40 req.) : memoire={mem_ms:.2f} ms mysql={sql_ms:.2f} ms (+{sql_ms - mem_ms:.2f} ms)")
    # Révocation + liaison regroupées : le mode mysql ne coûte pas plus de
    # requêtes que le mode mémoire (qui interroge déjà revoked_token).
    assert sql_q == mem_q


# ── Nettoyage dans le cycle ───────────────────────────────────────────────────

async def test_purge_removes_only_expired_rows():
    past, future = datetime.utcnow() - timedelta(minutes=1), datetime.utcnow() + timedelta(hours=1)
    async with TestSession() as s:
        for tag, exp in (("old", past), ("new", future)):
            s.add(SessionBinding(token_hash=tag.ljust(64, "0"), account_id=1, version=0, expires_at=exp))
            s.add(RateLimitCounter(key_hash=tag.ljust(64, "2"), count=1, expires_at=exp))
            s.add(RevokedToken(token_hash=tag.ljust(64, "1"), revoked_at=past, expires_at=exp))
            s.add(AppLock(name=tag, holder="h", acquired_at=past, expires_at=exp))
        await s.commit()

    deleted = await state_cleanup.purge_expired(TestSession)
    assert deleted == {"session_binding": 1, "rate_limit_counter": 1, "revoked_token": 1, "app_lock": 1}
    async with TestSession() as s:
        for model in (SessionBinding, RateLimitCounter, RevokedToken, AppLock):
            assert (await s.execute(select(func.count()).select_from(model))).scalar_one() == 1


async def test_cycle_runs_purge(monkeypatch):
    from api.configs import Database
    from api.core import scheduler

    async def noop():
        return None

    monkeypatch.setattr(Database, "AsyncSessionLocal", TestSession)
    monkeypatch.setattr(scheduler, "_job_auto_validation", noop)
    monkeypatch.setattr(scheduler, "_job_auto_close", noop)
    async with TestSession() as s:
        s.add(RateLimitCounter(key_hash="vieux".ljust(64, "3"), count=3, expires_at=datetime.utcnow() - timedelta(minutes=5)))
        await s.commit()
    assert await cli.run_cycle(session_factory=TestSession) == 0
    async with TestSession() as s:
        assert await s.get(RateLimitCounter, "vieux".ljust(64, "3")) is None
