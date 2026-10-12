"""
Lot 3 — démarrage sans lifespan (Passenger) : `python -m api.cli init|cycle`.

Vérifie :
  - init idempotent et non destructif (deux passages = mêmes comptages) ;
  - arrêt AVANT toute écriture si la base existante est incompatible
    (colonne absente, ENUM incomplet) ;
  - cycle = validation d'office J+3 puis fermeture J+4, idempotent (aucune
    action ni notification ni email en double) ;
  - verrou en base : cycles simultanés exclusifs, verrou expiré repris ;
  - emails lancés en tâche de fond : perdus sans attente à la sortie du
    processus, tous envoyés avec l'attente de la commande.
"""
from __future__ import annotations

import asyncio
import tempfile
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import func, select, text

from api import bootstrap, cli, storage
from api.configs import Database
from api.core import app_lock, scheduler
from api.core import mailer
from api.models.base import Base
from api.models.ModelAccount import Account
from api.models.ModelAppLock import AppLock
from api.models.ModelNotification import Notification
from api.models.ModelPriorityDefinition import PriorityDefinition
from api.models.ModelRequest import Request
from api.models.ModelRequestCategory import RequestCategory
from api.models.ModelRequestStatus import RequestStatus
from tests.support import TestSession, _engine


# ── Outils ────────────────────────────────────────────────────────────────────

async def _counts() -> dict[str, int]:
    async with _engine.connect() as conn:
        tables = await conn.run_sync(lambda c: __import__("sqlalchemy").inspect(c).get_table_names())
        return {
            t: (await conn.execute(text(f'SELECT COUNT(*) FROM "{t}"'))).scalar_one()
            for t in sorted(tables)
        }


def _uploads_tmp(monkeypatch) -> Path:
    tmp = Path(tempfile.mkdtemp(prefix="edg-init-uploads-"))
    monkeypatch.setattr(storage, "UPLOAD_DIR", tmp)
    return tmp


def _fake_reflection(monkeypatch, mutate) -> None:
    real = bootstrap._reflect_columns

    def patched(sync_conn, table_names):
        actual = real(sync_conn, table_names)
        mutate(actual)
        return actual

    monkeypatch.setattr(bootstrap, "_reflect_columns", patched)


class _Mail:
    """Remplace l'envoi SMTP : chaque email prend `delay` secondes (0,3 s par
    défaut, comme un vrai SMTP)."""

    def __init__(self, delay: float = 0.3) -> None:
        self.delay = delay
        self.started = 0
        self.sent: list[str] = []

    async def send(self, *, to_email, **kwargs):
        self.started += 1
        await asyncio.sleep(self.delay)
        self.sent.append(to_email)
        return True


async def _seed_tickets(ages_days: list[float]) -> list[int]:
    """Tickets `resolved` depuis `ages_days` jours, avec demandeur et traitant."""
    now = datetime.utcnow()
    async with TestSession() as s:
        statuses = {}
        for i, code in enumerate(["new", "resolved", "closed"]):
            existing = (await s.execute(select(RequestStatus).where(RequestStatus.code == code))).scalar_one_or_none()
            statuses[code] = existing or RequestStatus(code=code, label=code, sort_order=i)
            s.add(statuses[code])
        prio = (await s.execute(select(PriorityDefinition).limit(1))).scalar_one_or_none() or \
            PriorityDefinition(slug="medium", label="Moyenne", sort_order=1, color="blue")
        cat = (await s.execute(select(RequestCategory).limit(1))).scalar_one_or_none() or \
            RequestCategory(code="incident", label="Incident", sort_order=1)
        s.add_all([prio, cat])
        n = (await s.execute(select(func.count(Account.id)))).scalar_one()
        requester = Account(name="req", email=f"req{n}@edg.gn", role="user", account_status="active", status=True)
        tech = Account(name="tech", email=f"tech{n}@edg.gn", role="technicien", account_status="active", status=True)
        s.add_all([requester, tech])
        await s.flush()
        base = (await s.execute(select(func.count(Request.id)))).scalar_one()
        ids = []
        for k, age in enumerate(ages_days, start=1):
            r = Request(
                ref=f"EDG-26-{base + k:05d}", title=f"T{k}", description="d", is_external=False,
                request_status_id=statuses["resolved"].id, priority_definition_id=prio.id,
                request_category_id=cat.id, requester_id=requester.id, assignee_id=tech.id,
                resolved_at=now - timedelta(days=age),
            )
            s.add(r)
            await s.flush()
            ids.append(r.id)
        await s.commit()
        return ids


async def _state(ids: list[int]) -> list[tuple]:
    async with TestSession() as s:
        rows = (await s.execute(
            select(Request.id, RequestStatus.code, Request.infos)
            .join(RequestStatus, Request.request_status_id == RequestStatus.id)
            .where(Request.id.in_(ids)).order_by(Request.id)
        )).all()
        return [(code, (infos or {}).get("pv_validated_at")) for _, code, infos in rows]


async def _notif_count() -> int:
    async with TestSession() as s:
        return (await s.execute(select(func.count(Notification.id)))).scalar_one()


# ── init ──────────────────────────────────────────────────────────────────────

async def test_init_twice_is_idempotent_and_non_destructive(monkeypatch):
    uploads = _uploads_tmp(monkeypatch)
    assert await cli.run_init(engine=_engine, session_factory=TestSession) == 0
    first = await _counts()
    assert first["request_status"] > 0 and first["account"] == 1  # seeds + admin
    assert (uploads / "avatars").is_dir() and (uploads / "requests").is_dir()

    assert await cli.run_init(engine=_engine, session_factory=TestSession) == 0
    assert await _counts() == first


async def test_init_stops_before_any_write_on_missing_column(monkeypatch):
    _uploads_tmp(monkeypatch)
    async with _engine.begin() as conn:
        await conn.execute(text("DROP TABLE app_lock"))  # create_all la recréerait
    before = await _counts()
    _fake_reflection(monkeypatch, lambda a: a["request"].pop("distributor_id"))

    assert await cli.run_init(engine=_engine, session_factory=TestSession) == 2
    after = await _counts()
    assert after == before and "app_lock" not in after  # ni seed, ni create_all


async def test_init_stops_on_incomplete_role_enum(monkeypatch):
    _uploads_tmp(monkeypatch)
    async with _engine.begin() as conn:
        await conn.execute(text("DROP TABLE app_lock"))
    before = await _counts()
    expected_roles = bootstrap.expected_schema()["account"]["role"]

    def mutate(actual):  # ENUM réel sans « technicien », comme le dump 018
        actual["account"]["role"] = expected_roles - {"technicien"}

    _fake_reflection(monkeypatch, mutate)
    issues = await bootstrap.check_schema(_engine)
    assert issues == ["account.role : valeurs ENUM absentes de la base : technicien"]
    assert await cli.run_init(engine=_engine, session_factory=TestSession) == 2
    assert await _counts() == before


# ── check (lecture seule) ─────────────────────────────────────────────────────

async def test_check_is_read_only_and_reports_conformity(monkeypatch):
    _uploads_tmp(monkeypatch)
    assert await cli.run_init(engine=_engine, session_factory=TestSession) == 0
    async with _engine.begin() as conn:
        await conn.execute(text("DROP TABLE app_lock"))  # init la recréerait
    before = await _counts()

    assert await cli.run_check(engine=_engine) == 0  # table absente : pas un écart
    after = await _counts()
    assert after == before and "app_lock" not in after  # rien écrit, rien créé


async def test_check_exit_2_on_mismatch_without_writing(monkeypatch):
    before = await _counts()
    _fake_reflection(monkeypatch, lambda a: a["request"].pop("distributor_id"))
    assert await cli.run_check(engine=_engine) == 2
    assert await _counts() == before


async def test_check_exit_1_when_database_unreachable():
    from sqlalchemy.ext.asyncio import create_async_engine

    dead = create_async_engine("mysql+aiomysql://u:p@127.0.0.1:1/absente", connect_args={"connect_timeout": 2})
    try:
        assert await cli.run_check(engine=dead) == 1
    finally:
        await dead.dispose()


def test_compare_table_options_engine_charset_collation():
    expected = {"t": ("InnoDB", "utf8mb4", "utf8mb4_unicode_ci")}
    ok = bootstrap.compare_table_options(expected, {"t": ("InnoDB", "utf8mb4_unicode_ci")})
    assert ok == []
    assert bootstrap.compare_table_options(expected, {"t": ("MyISAM", "utf8mb4_unicode_ci")}) == [
        "t : moteur MyISAM au lieu de InnoDB"]
    assert bootstrap.compare_table_options(expected, {"t": ("InnoDB", "latin1_swedish_ci")}) == [
        "t : charset de latin1_swedish_ci au lieu de utf8mb4"]
    assert bootstrap.compare_table_options(expected, {"t": ("InnoDB", "utf8mb4_0900_ai_ci")}) == [
        "t : collation utf8mb4_0900_ai_ci au lieu de utf8mb4_unicode_ci"]
    assert bootstrap.compare_table_options(expected, {}) == []  # table absente : create_all


def test_all_models_declare_innodb_utf8mb4():
    for table, opts in bootstrap.expected_table_options().items():
        assert opts == ("InnoDB", "utf8mb4", "utf8mb4_unicode_ci"), table


def test_technical_tables_index_size_within_767_bytes():
    """Compatibilité MySQL 5.7 / MariaDB en ROW_FORMAT COMPACT : 767 octets max
    par clé d'index, en utf8mb4 (4 octets par caractère)."""
    from sqlalchemy import CHAR, DateTime, Integer, String

    def size(col) -> int:
        if isinstance(col.type, (String, CHAR)):
            return col.type.length * 4
        if isinstance(col.type, DateTime):
            return 8
        if isinstance(col.type, Integer):
            return 4
        raise AssertionError(f"type non prévu : {col.type!r}")

    tables = {t.name: t for t in Base.metadata.sorted_tables}
    for name in ("app_lock", "revoked_token", "session_binding", "rate_limit_counter"):
        if name not in tables:
            continue
        t = tables[name]
        keys = [("PRIMARY", list(t.primary_key.columns))] + [(ix.name, list(ix.columns)) for ix in t.indexes]
        for key_name, cols in keys:
            assert sum(size(c) for c in cols) <= 767, f"{name}.{key_name}"


async def test_check_and_init_stop_on_myisam_table(monkeypatch):
    _uploads_tmp(monkeypatch)
    before = await _counts()
    monkeypatch.setattr(
        bootstrap, "_reflect_table_options",
        lambda sync_conn: {"app_lock": ("MyISAM", "utf8mb4_unicode_ci")},
    )
    assert await bootstrap.check_schema(_engine) == ["app_lock : moteur MyISAM au lieu de InnoDB"]
    assert await cli.run_check(engine=_engine) == 2
    assert await cli.run_init(engine=_engine, session_factory=TestSession) == 2
    assert await _counts() == before


def test_compare_schema_tolerates_missing_table_and_extra_enum_values():
    expected = {"t": {"a": frozenset({"x", "y"})}, "absente": {"c": None}}
    assert bootstrap.compare_schema(expected, {"t": {"a": frozenset({"x", "y", "z"})}}) == []


# ── cycle ─────────────────────────────────────────────────────────────────────

async def test_cycle_j3_j4_and_idempotent(monkeypatch):
    mail = _Mail()
    monkeypatch.setattr(Database, "AsyncSessionLocal", TestSession)
    monkeypatch.setattr(mailer, "send_notification_email", mail.send)
    j2, j3, j4 = await _seed_tickets([2, 3.05, 4.05])

    assert await cli.run_cycle(session_factory=TestSession) == 0
    s1 = await _state([j2, j3, j4])
    assert s1[0] == ("resolved", None)                      # J+2 : intact
    assert s1[1][0] == "resolved" and s1[1][1] is not None  # J+3 : validé d'office
    assert s1[2][0] == "closed" and s1[2][1] is not None    # J+4 : validé puis fermé
    notifs, emails = await _notif_count(), list(mail.sent)
    assert notifs > 0 and emails and mail.started == len(emails)

    assert await cli.run_cycle(session_factory=TestSession) == 0
    assert await _state([j2, j3, j4]) == s1                 # horodatages inchangés
    assert await _notif_count() == notifs                   # aucune notification en double
    assert mail.sent == emails                              # aucun email en double


async def test_concurrent_cycles_are_exclusive(monkeypatch):
    calls = []

    async def slow_job():
        calls.append(1)
        await asyncio.sleep(0.3)

    async def noop():
        return None

    monkeypatch.setattr(scheduler, "_job_auto_validation", slow_job)
    monkeypatch.setattr(scheduler, "_job_auto_close", noop)
    results = await asyncio.gather(
        cli.run_cycle(session_factory=TestSession), cli.run_cycle(session_factory=TestSession)
    )
    assert results == [0, 0] and len(calls) == 1
    async with TestSession() as s:  # verrou libéré en fin de cycle
        assert (await s.execute(select(func.count()).select_from(AppLock))).scalar_one() == 0


async def test_held_lock_skips_cycle_and_expired_lock_is_taken_over(monkeypatch):
    monkeypatch.setattr(Database, "AsyncSessionLocal", TestSession)
    monkeypatch.setattr(mailer, "send_notification_email", _Mail().send)
    (j4,) = await _seed_tickets([4.05])

    assert await app_lock.acquire(TestSession, cli.CYCLE_LOCK_NAME, "autre-process", 600)
    assert await cli.run_cycle(session_factory=TestSession) == 0
    assert (await _state([j4]))[0][0] == "resolved"          # rien fait : verrou tenu

    async with TestSession() as s:                          # le détenteur a été tué
        lock = await s.get(AppLock, cli.CYCLE_LOCK_NAME)
        lock.expires_at = datetime.utcnow() - timedelta(minutes=1)
        await s.commit()
    assert await cli.run_cycle(session_factory=TestSession) == 0
    assert (await _state([j4]))[0][0] == "closed"


# ── emails lancés en tâche de fond ────────────────────────────────────────────

async def test_background_emails_lost_without_drain_and_sent_with_drain(monkeypatch):
    """Reproduit un vrai processus CLI : asyncio.run dans un thread, puis sortie."""
    monkeypatch.setattr(Database, "AsyncSessionLocal", TestSession)

    def run_process(drain: bool) -> None:
        asyncio.run(cli.run_cycle(session_factory=TestSession, drain_emails=drain))

    # Sans attente : un envoi encore en cours à la sortie du processus est
    # perdu. 30 s garantit qu'il l'est, quelle que soit la charge de la machine
    # (avec 0,3 s, la purge et la libération du verrou, faites après les
    # tâches, pouvaient durer plus longtemps sous charge : test instable).
    lost = _Mail(delay=30)
    monkeypatch.setattr(mailer, "send_notification_email", lost.send)
    await _seed_tickets([4.05])
    await asyncio.to_thread(run_process, False)
    assert lost.started > 0 and lost.sent == []              # annulés à la sortie

    kept = _Mail()
    monkeypatch.setattr(mailer, "send_notification_email", kept.send)
    await _seed_tickets([4.05])
    await asyncio.to_thread(run_process, True)
    assert kept.started > 0 and len(kept.sent) == kept.started
