"""
Révocation des jetons à la déconnexion — EDG Support.

La plateforme centrale ne documente aucune route de révocation (/v1) : elle
continue d'accepter un jeton jusqu'à son expiration. La déconnexion inscrit
donc l'empreinte SHA-256 de l'access ET du refresh token dans `revoked_token`
(en base : vu par tous les processus Passenger), et :
  - toute requête authentifiée refuse un access token révoqué
    (dependencies.resolve_central_account) ;
  - /auth/refresh refuse un refresh token révoqué, AVANT d'appeler le central.

Conservation : REVOCATION_TTL_SECONDS = 24 h, au moins la durée de vie
maximale d'un jeton concerné. Valeurs documentées par la plateforme centrale :
access `expires_in` 180 s, refresh `refresh_expires_in` 3600 s ; la plus longue
durée évoquée est ACCESS_TOKEN_EXPIRE_MINUTES=480 (8 h, jetons locaux de
repli). 24 h couvre ces trois valeurs avec marge et reprend la durée des
liaisons de session (session_registry._BINDING_TTL_SECONDS). Au-delà, le
jeton est expiré côté central : l'empreinte peut être purgée (api.cli cycle).
"""
from __future__ import annotations

import hashlib
from datetime import datetime, timedelta, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.ModelRevokedToken import RevokedToken

REVOCATION_TTL_SECONDS = 24 * 3600


def token_hash(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def revoke_tokens(db: AsyncSession, *tokens: str | None) -> int:
    """Inscrit les jetons fournis (vides ignorés, doublons tolérés). Écrit dans
    la transaction de l'appelant ; retourne le nombre de jetons traités."""
    now = _now()
    hashes = {token_hash(t) for t in tokens if t}
    for h in hashes:
        await db.merge(RevokedToken(
            token_hash=h, revoked_at=now,
            expires_at=now + timedelta(seconds=REVOCATION_TTL_SECONDS),
        ))
    if hashes:
        await db.flush()
    return len(hashes)


async def is_revoked(db: AsyncSession, token: str) -> bool:
    result = await db.execute(
        select(RevokedToken.token_hash)
        .where(RevokedToken.token_hash == token_hash(token), RevokedToken.expires_at > _now())
    )
    return result.first() is not None
