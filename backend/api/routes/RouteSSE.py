"""
Route SSE — Server-Sent Events pour les mises à jour temps réel EDG Support.

Authentification :
  Le token bearer central est passé via query param (?token=...) car l'API
  EventSource du navigateur ne supporte pas les en-têtes HTTP personnalisés.
  Validé via la même résolution centrale que get_current_user
  (api.dependencies.resolve_central_account).

Événements émis :
  connected        — confirmation à la connexion
  ping             — keepalive toutes les 25 s
  <event.type>     — tout AppEvent publié dans le bus (ex: request.created)
  user.session_revoked — session révoquée (rôle modifié, compte désactivé ou
                     supprimé) : envoyé puis le flux est FERMÉ. Le rôle d'un
                     abonné étant figé à la connexion, garder le flux ouvert
                     laisserait un ex-admin recevoir les événements « admin ».
"""
from __future__ import annotations

import asyncio
import json
import time
from typing import AsyncIterator, Optional

from fastapi import APIRouter, Query
from starlette.requests import Request

try:
    from sse_starlette.sse import EventSourceResponse
except ImportError as exc:  # pragma: no cover
    raise ImportError(
        "sse-starlette est requis. Installez-le avec : pip install sse-starlette"
    ) from exc

from api.configs.Database import AsyncSessionLocal
from api.configs.Environment import get_environment
from api.core import session_registry
from api.core.event_bus import event_bus, publish_pending
from api.core.exceptions import UnauthorizedException
from api.dependencies import resolve_central_account
from api.repositories import AccountRepository

_env = get_environment()
_PING_INTERVAL = 25  # secondes entre keepalives

router = APIRouter(prefix="/events", tags=["realtime"])


@router.get(
    "",
    summary="Flux SSE — mises à jour temps réel",
    description=(
        "Connexion Server-Sent Events. Le bearer token central doit être passé en "
        "query param `?token=` car EventSource ne supporte pas les en-têtes."
    ),
)
async def stream_events(
    request: Request,
    token: Optional[str] = Query(None, description="Bearer token central"),
) -> EventSourceResponse:
    # ── Authentification ──────────────────────────────────────────────────────
    if _env.DISABLE_AUTH:
        user_id: int = 0
        role: str = "admin"
        version = 0
    else:
        if not token:
            raise UnauthorizedException("Token requis pour établir la connexion SSE.")
        async with AsyncSessionLocal() as session:
            account = await resolve_central_account(token, session)
            await session.commit()
            await publish_pending(session)
        user_id = int(account.id)
        role = str(account.role)
        version = session_registry.session_version(account)

    def _revoked(reason: str | None) -> dict:
        return {
            "event": "user.session_revoked",
            "data": json.dumps(
                {"user_id": user_id, "reason": reason or "revoked", "timestamp": int(time.time())},
                ensure_ascii=False,
            ),
        }

    async def _revocation_reason() -> str | None:
        """Revérifie en base, à chaque keepalive, que la session du flux est
        toujours valide. Filet si l'événement ciblé est perdu ; couvre aussi un
        rôle modifié directement en base (table partagée avec le central)."""
        if _env.DISABLE_AUTH:
            return None
        try:
            async with AsyncSessionLocal() as session:
                current = await AccountRepository(session).get_by_id(user_id, include_deleted=True)
        except Exception:
            return None  # base momentanément indisponible : ne pas déconnecter à tort
        if current is None or current.deleted_at is not None:
            return session_registry.REASON_DELETED
        if not session_registry.is_account_active(current):
            return session_registry.REASON_DISABLED
        if session_registry.session_version(current) != version or str(current.role) != role:
            return session_registry.revoked_reason(current) or session_registry.REASON_ROLE_CHANGED
        return None


    # ── Générateur d'événements ───────────────────────────────────────────────
    async def _generator() -> AsyncIterator[dict]:
        q = await event_bus.subscribe(user_id, role)
        try:
            yield {
                "event": "connected",
                "data": json.dumps({"status": "connected", "role": role}, ensure_ascii=False),
            }

            while True:
                if await request.is_disconnected():
                    break

                try:
                    msg = await asyncio.wait_for(q.get(), timeout=float(_PING_INTERVAL))

                    # Session révoquée : l'événement est transmis puis le flux
                    # est fermé — l'abonnement (et son rôle figé) disparaît.
                    if msg["type"] == "user.session_revoked" and msg["payload"].get("user_id") == user_id:
                        yield _revoked(msg["payload"].get("reason"))
                        break

                    yield {
                        "event": msg["type"],
                        "data": json.dumps(msg["payload"], ensure_ascii=False, default=str),
                    }
                except asyncio.TimeoutError:
                    reason = await _revocation_reason()
                    if reason:
                        yield _revoked(reason)
                        break
                    yield {"event": "ping", "data": str(int(time.time()))}

        except asyncio.CancelledError:
            pass
        finally:
            await event_bus.unsubscribe(user_id, q)

    return EventSourceResponse(_generator())
