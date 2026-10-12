"""
Compteurs de limitation des tentatives en base (STATE_BACKEND=mysql) — EDG Support.

Même logique que le stockage Redis de RateLimitMiddleware : fenêtre fixe
ouverte au premier coup (INCR puis EXPIRE), refus quand le compteur dépasse
le maximum. Partagé entre processus ; portable MySQL / SQLite (tests).
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from sqlalchemy import case, select, update
from sqlalchemy.exc import IntegrityError

from api.models.ModelRateLimitCounter import RateLimitCounter


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def key_hash(key: str) -> str:
    """Empreinte stockée en base (clé primaire CHAR(64)) de la clé lisible « rl:IP:chemin »."""
    return hashlib.sha256(key.encode("utf-8")).hexdigest()


async def hit(session_factory, key: str, window_sec: int) -> int:
    """Compte une tentative pour `key` et retourne le total de la fenêtre courante."""
    now = _now()
    expires_at = now + timedelta(seconds=window_sec)
    h = key_hash(key)
    async with session_factory() as session:
        session.add(RateLimitCounter(key_hash=h, count=1, expires_at=expires_at))
        try:
            await session.commit()
            return 1
        except IntegrityError:
            await session.rollback()
        # Incrément atomique ; fenêtre expirée -> nouvelle fenêtre (compteur à 1).
        # Le verrou de ligne de l'UPDATE sérialise les processus concurrents :
        # la lecture qui suit, dans la même transaction, voit notre incrément.
        expired = RateLimitCounter.expires_at <= now
        await session.execute(
            update(RateLimitCounter)
            .where(RateLimitCounter.key_hash == h)
            .values(
                count=case((expired, 1), else_=RateLimitCounter.count + 1),
                expires_at=case((expired, expires_at), else_=RateLimitCounter.expires_at),
            )
        )
        count = (await session.execute(
            select(RateLimitCounter.count).where(RateLimitCounter.key_hash == h)
        )).scalar_one()
        await session.commit()
        return int(count)
