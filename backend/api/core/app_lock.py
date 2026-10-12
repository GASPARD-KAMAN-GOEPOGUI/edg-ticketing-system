"""
Verrou nommé en base (table `app_lock`) — EDG Support.

Partagé entre processus (cron, workers Passenger) puisqu'il vit en base, et
portable MySQL / SQLite (tests) : aucune fonction propre à un moteur.

  acquire : INSERT de la ligne (clé primaire = nom) → verrou pris.
            Si la ligne existe : UPDATE … WHERE expires_at < maintenant,
            pour reprendre un verrou expiré (processus tué). Les deux
            requêtes sont atomiques : deux prétendants simultanés ne peuvent
            pas l'obtenir tous les deux.
  release : DELETE de la ligne, seulement par son détenteur.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, update
from sqlalchemy.exc import IntegrityError

from api.models.ModelAppLock import AppLock


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def acquire(session_factory, name: str, holder: str, ttl_seconds: int) -> bool:
    """Prend le verrou `name` pour `ttl_seconds`. Retourne False s'il est déjà tenu."""
    now = _now()
    expires_at = now + timedelta(seconds=ttl_seconds)
    async with session_factory() as session:
        session.add(AppLock(name=name, holder=holder, acquired_at=now, expires_at=expires_at))
        try:
            await session.commit()
            return True
        except IntegrityError:
            await session.rollback()
    async with session_factory() as session:
        result = await session.execute(
            update(AppLock)
            .where(AppLock.name == name, AppLock.expires_at < now)
            .values(holder=holder, acquired_at=now, expires_at=expires_at)
        )
        await session.commit()
        return result.rowcount == 1


async def release(session_factory, name: str, holder: str) -> None:
    """Libère le verrou `name` s'il est toujours tenu par `holder`."""
    async with session_factory() as session:
        await session.execute(
            delete(AppLock).where(AppLock.name == name, AppLock.holder == holder)
        )
        await session.commit()
