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
from api.core.event_bus import event_bus
from api.core.exceptions import UnauthorizedException
from api.dependencies import resolve_central_account

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
    else:
        if not token:
            raise UnauthorizedException("Token requis pour établir la connexion SSE.")
        async with AsyncSessionLocal() as session:
            account = await resolve_central_account(token, session)
        user_id = int(account.id)
        role = str(account.role)


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

                    # H-08 — Fermeture immédiate si session révoquée (nouveau login)
                    if msg["type"] == "session.revoked" and msg["payload"].get("user_id") == user_id:
                        yield {
                            "event": "session_revoked",
                            "data": json.dumps(
                                {"reason": "new_login_detected"},
                                ensure_ascii=False,
                            ),
                        }
                        break  # ferme la connexion SSE

                    yield {
                        "event": msg["type"],
                        "data": json.dumps(msg["payload"], ensure_ascii=False, default=str),
                    }
                except asyncio.TimeoutError:
                    yield {"event": "ping", "data": str(int(time.time()))}

        except asyncio.CancelledError:
            pass
        finally:
            await event_bus.unsubscribe(user_id, q)

    return EventSourceResponse(_generator())
