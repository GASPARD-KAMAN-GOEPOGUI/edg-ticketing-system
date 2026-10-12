"""
Event bus interne EDG Support — pub/sub asyncio en mémoire.

Architecture :
  - Chaque client SSE connecté s'abonne avec subscribe(user_id, role)
  - Les services publient des AppEvent via publish(event)
  - Fan-out : chaque événement est envoyé aux files des abonnés autorisés

Ciblage (AppEvent.target) :
  {"roles": "all"}                          → tous les utilisateurs connectés
  {"roles": ["chief-service", "admin"]}     → rôles spécifiques
  {"user_ids": [123, 456]}                  → utilisateurs spécifiques
  {"roles": ["agent"], "user_ids": [99]}    → union des deux

Le fan-out local utilise des files asyncio. Redis Pub/Sub relaie les événements
entre workers quand REDIS_URL est configuré ; une coupure Redis conserve le
fan-out local et le listener réessaie automatiquement.
"""
from __future__ import annotations

import asyncio
import json
import logging
import uuid
from dataclasses import dataclass, field
from typing import Any

logger = logging.getLogger(__name__)
_EVENT_CHANNEL = "edg:realtime-events"
_PENDING_EVENTS_KEY = "edg:realtime-events-after-commit"

try:
    import redis.asyncio as aioredis
except ImportError:  # pragma: no cover - Redis reste optionnel en développement
    aioredis = None


async def _close_redis_resource(resource) -> None:
    close = getattr(resource, "aclose", None) or getattr(resource, "close", None)
    if close:
        result = close()
        if hasattr(result, "__await__"):
            await result


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
        self._worker_id = uuid.uuid4().hex
        self._redis = None
        self._redis_task: asyncio.Task | None = None
        self._redis_pubsub = None
        self._stopping = False

    async def start(self, redis_url: str = "") -> None:
        """Active le relais partagé pour que les workers SSE se voient entre eux."""
        if not redis_url:
            logger.info("EventBus : mode mémoire local (REDIS_URL non configuré).")
            return
        if aioredis is None:
            raise RuntimeError("redis[hiredis] est requis pour le bus SSE multi-worker.")

        client = aioredis.from_url(redis_url, decode_responses=True)
        self._redis = client
        self._stopping = False
        try:
            await client.ping()
            logger.info("EventBus : Redis accessible, relais Pub/Sub en démarrage.")
        except Exception:
            logger.exception("EventBus : Redis indisponible au démarrage, nouvelle tentative en arrière-plan.")
        self._redis_task = asyncio.create_task(self._listen_redis())

    async def stop(self) -> None:
        self._stopping = True
        if self._redis_task:
            self._redis_task.cancel()
            try:
                await self._redis_task
            except asyncio.CancelledError:
                pass
            self._redis_task = None
        if self._redis_pubsub:
            await _close_redis_resource(self._redis_pubsub)
            self._redis_pubsub = None
        if self._redis:
            await _close_redis_resource(self._redis)
            self._redis = None

    async def _listen_redis(self) -> None:
        while not self._stopping:
            pubsub = None
            try:
                if self._redis is None:
                    return
                pubsub = self._redis.pubsub()
                self._redis_pubsub = pubsub
                await pubsub.subscribe(_EVENT_CHANNEL)
                async for message in pubsub.listen():
                    if message.get("type") != "message":
                        continue
                    await self._handle_redis_payload(message.get("data", ""))
                if not self._stopping:
                    raise ConnectionError("Redis Pub/Sub listener closed unexpectedly.")
            except asyncio.CancelledError:
                raise
            except Exception:
                if not self._stopping:
                    logger.exception("EventBus : relais Redis indisponible, nouvelle tentative.")
            finally:
                if pubsub is not None:
                    await _close_redis_resource(pubsub)
                if self._redis_pubsub is pubsub:
                    self._redis_pubsub = None

            if self._stopping or self._redis is None:
                return
            await asyncio.sleep(1)

    async def _handle_redis_payload(self, raw_payload: str) -> None:
        packet = json.loads(raw_payload)
        if packet.get("origin") == self._worker_id:
            return
        await self._dispatch_packet(packet["event"])

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
        packet = {"type": event.type, "payload": event.payload, "target": event.target}
        await self._dispatch_packet(packet)

        if self._redis is not None:
            try:
                await self._redis.publish(
                    _EVENT_CHANNEL,
                    json.dumps({"origin": self._worker_id, "event": packet}, ensure_ascii=False),
                )
            except Exception:
                logger.exception("EventBus : publication Redis échouée (%s).", event.type)

    async def _dispatch_packet(self, packet: dict[str, Any]) -> None:
        target = packet.get("target") or {"roles": "all"}

        async with self._lock:
            subs = list(self._subscribers)

        fanned = 0
        client_packet = {"type": packet["type"], "payload": packet["payload"]}
        for uid, role, q in subs:
            if self._should_receive(uid, role, target):
                try:
                    q.put_nowait(client_packet)
                    fanned += 1
                except asyncio.QueueFull:
                    logger.warning("SSE queue full — user_id=%s event dropped: %s", uid, packet["type"])

        if fanned:
            logger.debug("SSE publish — type=%s fanned_to=%d", packet["type"], fanned)

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


def queue_after_commit(session, event: AppEvent) -> None:
    """Diffère l'événement SSE jusqu'au commit de la transaction métier."""
    session.info.setdefault(_PENDING_EVENTS_KEY, []).append(event)


async def publish_pending(session, bus: EventBus | None = None) -> None:
    """Publie les événements différés après un commit réussi."""
    for event in session.info.pop(_PENDING_EVENTS_KEY, []):
        try:
            await (bus or event_bus).publish(event)
        except Exception as exc:  # pragma: no cover
            logger.warning("event_bus.emit failed silently: %s", exc)


def discard_pending(session) -> None:
    """Jette les événements SSE associés à une transaction annulée."""
    session.info.pop(_PENDING_EVENTS_KEY, None)
