"""
Blacklist de tokens JWT révoqués.

Stratégie :
  - Si REDIS_URL est configuré → RedisTokenBlacklist (persistant, partagé entre instances)
  - Sinon → InMemoryTokenBlacklist (fallback, perdu au redémarrage — NON RECOMMANDÉ en prod)

Usage :
    from api.core.token_blacklist import token_blacklist

    await token_blacklist.revoke(jti, expires_at)
    if await token_blacklist.is_revoked(jti):
        raise UnauthorizedException(...)
"""
from __future__ import annotations

import logging
import threading
from datetime import datetime, timezone
from typing import Protocol

logger = logging.getLogger(__name__)


# ── Protocole commun ──────────────────────────────────────────────────────────

class TokenBlacklist(Protocol):
    async def revoke(self, jti: str, expires_at: datetime | None = None) -> None: ...
    async def is_revoked(self, jti: str) -> bool: ...


# ── Implémentation Redis ──────────────────────────────────────────────────────

class RedisTokenBlacklist:
    """
    Blacklist persistante sur Redis.
    Clé : blacklist:{jti} — TTL = durée de vie du token.
    """

    def __init__(self, redis_url: str) -> None:
        import redis.asyncio as aioredis  # importé ici pour garder le fallback fonctionnel
        self._client = aioredis.from_url(redis_url, decode_responses=True)
        logger.info("TokenBlacklist → Redis (%s)", redis_url)

    async def revoke(self, jti: str, expires_at: datetime | None = None) -> None:
        if not jti:
            return
        ttl = 3600  # 1h par défaut si pas d'expiration connue
        if expires_at:
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            remaining = (expires_at - now).total_seconds()
            ttl = max(1, int(remaining))
        await self._client.setex(f"blacklist:{jti}", ttl, "1")

    async def is_revoked(self, jti: str) -> bool:
        if not jti:
            return False
        result = await self._client.exists(f"blacklist:{jti}")
        return bool(result)


# ── Implémentation mémoire (fallback) ─────────────────────────────────────────

class InMemoryTokenBlacklist:
    """
    Blacklist en mémoire — fallback si Redis non configuré.
    ATTENTION : perdue au redémarrage ; non partagée entre processus/workers.
    """

    def __init__(self) -> None:
        self._store: dict[str, datetime] = {}
        self._lock = threading.Lock()
        logger.warning(
            "TokenBlacklist → mémoire (REDIS_URL non configuré). "
            "NON RECOMMANDÉ en production : tokens révoqués redeviennent valides après redémarrage."
        )

    async def revoke(self, jti: str, expires_at: datetime | None = None) -> None:
        with self._lock:
            self._store[jti] = expires_at or datetime.max.replace(tzinfo=None)

    async def is_revoked(self, jti: str) -> bool:
        with self._lock:
            exp = self._store.get(jti)
            if exp is None:
                return False
            now = datetime.now(timezone.utc).replace(tzinfo=None)
            if exp < now:
                del self._store[jti]
                return False
            return True


# ── Usine — choisit l'implémentation au démarrage ─────────────────────────────

def _build_blacklist() -> InMemoryTokenBlacklist | RedisTokenBlacklist:
    from api.configs.Environment import get_environment
    env = get_environment()
    if env.REDIS_URL:
        try:
            return RedisTokenBlacklist(env.REDIS_URL)
        except Exception as exc:
            logger.error("Impossible de créer RedisTokenBlacklist : %s — fallback mémoire", exc)
    return InMemoryTokenBlacklist()


# Singleton global
token_blacklist: InMemoryTokenBlacklist | RedisTokenBlacklist = _build_blacklist()
