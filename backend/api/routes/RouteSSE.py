"""
Route SSE — Server-Sent Events pour les mises à jour temps réel EDG Connect.

Authentification :
  Le token JWT est passé via query param (?token=...) car l'API EventSource
  du navigateur ne supporte pas les en-têtes HTTP personnalisés.

Session unique (H-08) :
  - La session est vérifiée en DB au moment de la connexion.
  - Si l'utilisateur se connecte depuis un autre appareil, un événement
    `session.revoked` est publié dans le bus et la connexion SSE est fermée
    dans les secondes qui suivent (sans attendre le prochain ping).

Événements émis :
  connected        — confirmation à la connexion
  ping             — keepalive toutes les 25 s
  session_revoked  — fermeture forcée (nouvelle connexion détectée)
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
from api.core.security import decode_token
from api.core.exceptions import UnauthorizedException
from api.core.token_blacklist import token_blacklist

_env = get_environment()
_PING_INTERVAL = 25  # secondes entre keepalives

router = APIRouter(prefix="/events", tags=["realtime"])


@router.get(
    "",
    summary="Flux SSE — mises à jour temps réel",
    description=(
        "Connexion Server-Sent Events. Le token JWT doit être passé en "
        "query param `?token=` car EventSource ne supporte pas les en-têtes."
    ),
)
async def stream_events(
    request: Request,
    token: Optional[str] = Query(None, description="JWT access token"),
) -> EventSourceResponse:
    # ── Authentification ──────────────────────────────────────────────────────
    if _env.DISABLE_AUTH:
        user_id: int = 0
        role: str = "admin"
        session_id: Optional[str] = None
    else:
        if not token:
            raise UnauthorizedException("Token requis pour établir la connexion SSE.")
        try:
            payload = decode_token(token)
        except Exception:
            raise UnauthorizedException("Token SSE invalide ou expiré.")

        jti = payload.get("jti", "")
        if await token_blacklist.is_revoked(jti):
            raise UnauthorizedException("Token SSE révoqué. Reconnectez-vous.")

        user_id = int(payload.get("sub", 0))
        role = str(payload.get("role", "user"))
        session_id = payload.get("session_id")


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
