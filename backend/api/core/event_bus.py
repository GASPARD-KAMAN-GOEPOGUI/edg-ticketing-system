"""
Event bus interne EDG Support — pub/sub asyncio en mémoire.

Architecture :
  - Chaque client SSE connecté s'abonne avec subscribe(user_id, role)
  - Les services publient des AppEvent via publish(event)
  - Fan-out : chaque événement est envoyé aux files des abonnés autorisés

Ciblage (AppEvent.target) :
  {"roles": "all"}                          → tous les utilisateurs connectés
  {"roles": ["agent", "chief", "admin"]}    → rôles spécifiques
  {"user_ids": [123, 456]}                  → utilisateurs spécifiques
  {"roles": ["agent"], "user_ids": [99]}    → union des deux

Note : implémentation in-memory. Plusieurs workers Uvicorn/Gunicorn
n'ont pas d'état partagé — pour la production multi-process, utiliser
Redis Pub/Sub comme broker externe.
"""
from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)


@dataclass
class AppEvent:
    """Événement applicatif publié dans le bus."""

    type: str
    payload: dict[str, Any]
    # Ciblage de la diffusion — voir format ci-dessus
    target: dict[str, Any] = field(default_factory=lambda: {"roles": "all"})


class EventBus:
    """Bus d'événements asyncio — fanout vers les abonnés autorisés."""

    def __init__(self) -> None:
        self._subscribers: list[tuple[int, str, asyncio.Queue]] = []
        self._lock = asyncio.Lock()

    async def subscribe(self, user_id: int, role: str) -> asyncio.Queue:
        q: asyncio.Queue = asyncio.Queue(maxsize=200)
        async with self._lock:
            self._subscribers.append((user_id, role, q))
        logger.debug("SSE subscribe — user_id=%s role=%s total=%d", user_id, role, len(self._subscribers))
        return q

    async def unsubscribe(self, user_id: int, q: asyncio.Queue) -> None:
        async with self._lock:
            self._subscribers = [s for s in self._subscribers if not (s[0] == user_id and s[2] is q)]
        logger.debug("SSE unsubscribe — user_id=%s total=%d", user_id, len(self._subscribers))

    async def publish(self, event: AppEvent) -> None:
        target = event.target
        packet = {"type": event.type, "payload": event.payload}

        async with self._lock:
            subs = list(self._subscribers)

        fanned = 0
        for uid, role, q in subs:
            if self._should_receive(uid, role, target):
                try:
                    q.put_nowait(packet)
                    fanned += 1
                except asyncio.QueueFull:
                    logger.warning("SSE queue full — user_id=%s event dropped: %s", uid, event.type)

        if fanned:
            logger.debug("SSE publish — type=%s fanned_to=%d", event.type, fanned)

    @staticmethod
    def _should_receive(user_id: int, role: str, target: dict[str, Any]) -> bool:
        roles = target.get("roles")
        if roles == "all":
            return True
        allowed = False
        if isinstance(roles, list) and role in roles:
            allowed = True
        user_ids = target.get("user_ids")
        if isinstance(user_ids, list) and user_id in user_ids:
            allowed = True
        return allowed

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


# ── Singleton global ──────────────────────────────────────────────────────────

event_bus = EventBus()


async def emit(event: AppEvent) -> None:
    """Helper fire-and-forget — ne propage jamais d'exception."""
    try:
        await event_bus.publish(event)
    except Exception as exc:  # pragma: no cover
        logger.warning("event_bus.emit failed silently: %s", exc)
