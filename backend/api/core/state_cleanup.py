"""
Purge des entrées expirées de l'état partagé — EDG Support.

Appelée par `python -m api.cli cycle` (cron horaire, sous verrou). Ne touche
qu'aux lignes dont `expires_at` est dépassé : une liaison, un compteur ou une
révocation encore valides ne sont jamais supprimés. Le verrou du cycle en
cours, valide, n'est donc pas concerné.
"""
from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import delete

from api.models.ModelAppLock import AppLock
from api.models.ModelRateLimitCounter import RateLimitCounter
from api.models.ModelRevokedToken import RevokedToken
from api.models.ModelSessionBinding import SessionBinding

_TABLES = (SessionBinding, RateLimitCounter, RevokedToken, AppLock)


async def purge_expired(session_factory) -> dict[str, int]:
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    deleted: dict[str, int] = {}
    async with session_factory() as session:
        for model in _TABLES:
            result = await session.execute(delete(model).where(model.expires_at < now))
            deleted[model.__tablename__] = result.rowcount or 0
        await session.commit()
    return deleted
