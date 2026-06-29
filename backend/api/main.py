"""Point d'entrée de l'application FastAPI — EDG Connect API."""

from __future__ import annotations

import asyncio
import logging
from collections import defaultdict
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from datetime import datetime, timedelta

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

import api.models  # noqa: F401 — enregistre toutes les tables dans Base.metadata
from api.configs.Database import engine, AsyncSessionLocal
from api.configs.Environment import get_environment
from api.models.base import Base
from api.core import register_exception_handlers
from api.core.middleware import RequestLoggingMiddleware, ResponseWrapperMiddleware
from api.core.scheduler import start_scheduler, stop_scheduler
from api.seed_references import seed_references
from api.seed_admin import seed_admin

# Redis optionnel pour le rate limiting distribué
try:
    import redis.asyncio as aioredis
    _REDIS_AVAILABLE = True
except ImportError:
    _REDIS_AVAILABLE = False

from api.routes import (
    health_router,
    auth_router,
    sse_router,
    references_router,
    unity_router,
    organigram_router,
    directions_router,
    units_router,
    public_dirs_router,
    account_router,
    request_router,
    public_request_router,
    attachment_router,
    sla_policy_router,
    sla_policy_read_router,
    routing_rule_router,
    director_routing_router,
    workflow_router,
    request_workflow_router,
    workflow_detail_router,
    task_router,
    notification_router,
    activity_log_router,
    knowledge_article_router,
    announcement_router,
    appreciation_router,
    request_appreciation_router,
    csat_stats_router,
    communication_setting_router,
    admin_config_router,
    users_router,
    users_me_router,
    users_avatars_router,
    knowledge_router,
    knowledge_public_router,
    stats_router,
    agent_stats_router,
    reports_router,
    escalation_router,
)

env = get_environment()


# ─── Rate Limiting Middleware (H-02 + C-N°5) ─────────────────────────────────
#
# Redis (INCR + EXPIRE) si REDIS_URL est configuré → partage entre workers.
# Sinon : fenêtre glissante en mémoire (monoprocessus uniquement, dev).
#
# Routes protégées et limites :
#   /api/v1/auth/login           → 10 req / 60 s
#   /api/v1/auth/register        → 5  req / 60 s
#   /api/v1/auth/forgot-password → 3  req / 60 s
#   /api/v1/auth/reset-password  → 3  req / 60 s

_RATE_LIMITS: dict[str, tuple[int, int]] = {
    "/api/v1/auth/login":            (10, 60),
    "/api/v1/auth/register":         (5,  60),
    "/api/v1/auth/forgot-password":  (3,  60),
    "/api/v1/auth/reset-password":   (3,  60),
}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Rate limiter distribué (Redis) avec repli en mémoire.

    Redis : INCR key → si count==1 EXPIRE key window → si count>max → 429.
    Mémoire : fenêtre glissante avec asyncio.Lock (dev / monoprocessus).
    """

    def __init__(self, app) -> None:
        super().__init__(app)
        self._redis: "aioredis.Redis | None" = None
        self._redis_ok: bool = False
        # Fallback en mémoire
        self._store: dict[str, list[datetime]] = defaultdict(list)
        self._lock = asyncio.Lock()

    async def _get_redis(self):
        if self._redis_ok:
            return self._redis
        if not _REDIS_AVAILABLE or not env.REDIS_URL:
            return None
        try:
            r = aioredis.from_url(env.REDIS_URL, decode_responses=True)
            await r.ping()
            self._redis = r
            self._redis_ok = True
            logger.info("RateLimitMiddleware : Redis connecté (%s)", env.REDIS_URL)
            return r
        except Exception as exc:
            logger.warning("RateLimitMiddleware : Redis indisponible (%s) — repli en mémoire.", exc)
            return None

    async def _check_redis(self, key: str, max_req: int, window_sec: int) -> bool:
        """Retourne True si la limite est atteinte."""
        r = await self._get_redis()
        if r is None:
            return False
        try:
            count = await r.incr(key)
            if count == 1:
                await r.expire(key, window_sec)
            return count > max_req
        except Exception as exc:
            logger.warning("RateLimitMiddleware Redis erreur : %s", exc)
            return False  # fail-open plutôt que bloquer en cas de panne Redis

    async def _check_memory(self, key: str, max_req: int, window_sec: int) -> bool:
        now = datetime.utcnow()
        cutoff = now - timedelta(seconds=window_sec)
        async with self._lock:
            self._store[key] = [t for t in self._store[key] if t > cutoff]
            if len(self._store[key]) >= max_req:
                return True
            self._store[key].append(now)
            return False

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path not in _RATE_LIMITS:
            return await call_next(request)

        max_req, window_sec = _RATE_LIMITS[path]
        ip = (
            request.headers.get("X-Forwarded-For", "").split(",")[0].strip()
            or (request.client.host if request.client else "unknown")
        )
        key = f"rl:{ip}:{path}"

        redis_used = await self._get_redis() is not None
        limited = (
            await self._check_redis(key, max_req, window_sec)
            if redis_used
            else await self._check_memory(key, max_req, window_sec)
        )

        if limited:
            return JSONResponse(
                status_code=429,
                content={
                    "detail": (
                        f"Trop de tentatives ({max_req} max / {window_sec} s). "
                        "Réessayez dans quelques minutes."
                    )
                },
            )
        return await call_next(request)


# ─── Logging ──────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.DEBUG if env.DEBUG_MODE else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
)
logger = logging.getLogger(__name__)


# ─── Lifespan ─────────────────────────────────────────────────────────────────
@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    """Gestion du cycle de vie de l'application (startup / shutdown)."""
    logger.info("Démarrage de %s [env=%s]", env.APP_NAME, env.APP_ENV)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    async with AsyncSessionLocal() as session:
        await seed_references(session)
        await seed_admin(session)
        await session.commit()
    start_scheduler(interval_minutes=10)
    yield
    stop_scheduler()
    logger.info("Arrêt de %s", env.APP_NAME)


# ─── Application ──────────────────────────────────────────────────────────────
app = FastAPI(
    title=env.APP_NAME,
    version=env.APP_VERSION,
    debug=env.DEBUG_MODE,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ─── Exception handlers ───────────────────────────────────────────────────────
# Doit être enregistré AVANT les middlewares
register_exception_handlers(app)

# ─── Middlewares ──────────────────────────────────────────────────────────────
# Ordre d'ajout = ordre inverse d'exécution (le dernier ajouté s'exécute en premier)
# Dev  : toutes origines acceptées, credentials désactivés (pas de JWT encore)
# Prod : restreindre aux origines configurées dans CORS_ORIGINS
_is_dev = env.APP_ENV != "production"
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"] if _is_dev else env.CORS_ORIGINS,
    allow_credentials=not _is_dev,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(ResponseWrapperMiddleware)
app.add_middleware(RequestLoggingMiddleware)
app.add_middleware(RateLimitMiddleware)  # H-02 — anti brute-force auth

# ─── Routes ───────────────────────────────────────────────────────────────────
_API = "/api/v1"

app.include_router(health_router)
app.include_router(auth_router,                  prefix=_API)
app.include_router(sse_router,                   prefix=_API)
app.include_router(references_router,            prefix=_API)
app.include_router(unity_router,                 prefix=_API)
app.include_router(organigram_router,            prefix=_API)
app.include_router(public_dirs_router,           prefix=_API)
app.include_router(directions_router,            prefix=_API)
app.include_router(units_router,                 prefix=_API)
app.include_router(account_router,               prefix=_API)
app.include_router(public_request_router,        prefix=_API)
app.include_router(request_router,               prefix=_API)
app.include_router(attachment_router,            prefix=_API)
app.include_router(sla_policy_read_router,       prefix=_API)
app.include_router(sla_policy_router,            prefix=_API)
app.include_router(routing_rule_router,          prefix=_API)
app.include_router(director_routing_router,      prefix=_API)
app.include_router(workflow_router,              prefix=_API)
app.include_router(request_workflow_router,      prefix=_API)
app.include_router(workflow_detail_router,       prefix=_API)
app.include_router(task_router,                  prefix=_API)
app.include_router(notification_router,          prefix=_API)
app.include_router(activity_log_router,          prefix=_API)
app.include_router(knowledge_article_router,     prefix=_API)
app.include_router(announcement_router,          prefix=_API)
app.include_router(appreciation_router,          prefix=_API)
app.include_router(request_appreciation_router,  prefix=_API)
app.include_router(csat_stats_router,            prefix=_API)
app.include_router(communication_setting_router,   prefix=_API)
app.include_router(admin_config_router,          prefix=_API)
app.include_router(users_avatars_router,         prefix=_API)
app.include_router(users_me_router,              prefix=_API)
app.include_router(users_router,                 prefix=_API)
app.include_router(knowledge_public_router,      prefix=_API)
app.include_router(knowledge_router,             prefix=_API)
app.include_router(stats_router,                 prefix=_API)
app.include_router(agent_stats_router,           prefix=_API)
app.include_router(reports_router,               prefix=_API)
app.include_router(escalation_router,            prefix=_API)
