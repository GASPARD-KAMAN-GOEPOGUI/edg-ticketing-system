"""
Révocation des sessions d'un compte — changement de rôle, désactivation, suppression.

Pourquoi ce module : le bearer token est émis par la plateforme centrale. Il
n'est pas garanti décodable (pas de JWT exploitable, donc pas d'`iat`) et EDG
Connect ne peut y ajouter aucun claim. Le central ne sait rien d'un changement
de rôle LOCAL : il continuerait d'accepter l'ancien token jusqu'à expiration.

Mécanisme (version de session) :
  1. Chaque compte porte une version dans `account.infos.session_version`
     (dans `infos` et non dans une colonne : la table `account` est partagée
     avec la plateforme centrale, même choix que `intervenant_status`).
  2. Chaque token relayé par EDG Connect (login, refresh, consentement) est lié
     à la version courante du compte : empreinte SHA-256 -> (account_id, version).
     Un token jamais vu (émis hors de nos routes) est lié à la première
     utilisation.
  3. Une modification critique incrémente la version : tout token lié à
     l'ancienne version — access ET refresh — est refusé (401 SESSION_REVOKED),
     y compris après une réactivation. Seule une nouvelle connexion produit un
     token valide.

Stockage des liaisons (STATE_BACKEND, voir api/core/state_backend.py) :
  - mysql : table `session_binding`, partagée entre processus, via la
    session de la requête ; aucun repli en mémoire ;
  - redis : Redis (REDIS_URL), partagé entre workers ;
  - memory : mémoire du processus (développement monoprocessus). Un
    redémarrage oublie les liaisons : les tokens existants sont re-liés à la
    version courante à leur prochaine utilisation — INACCEPTABLE avec
    plusieurs processus (un token révoqué serait accepté par un processus qui
    ne l'a jamais vu), d'où la garde de production.
La vérification `account_status`/rôle en base reste appliquée à chaque requête.
"""
from __future__ import annotations

import hashlib
import json
import logging
import time
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from sqlalchemy import literal, select, union_all
from sqlalchemy.exc import IntegrityError

from api.configs.Environment import get_environment
from api.core import state_backend, token_revocation
from api.core.error_codes import ErrorCode
from api.core.event_bus import AppEvent, queue_after_commit
from api.core.exceptions import UnauthorizedException
from api.models.ModelRevokedToken import RevokedToken
from api.models.ModelSessionBinding import SessionBinding

logger = logging.getLogger(__name__)
_env = get_environment()

try:
    import redis.asyncio as aioredis
except ImportError:  # pragma: no cover - Redis reste optionnel en développement
    aioredis = None

SESSION_VERSION_KEY = "session_version"
REVOKED_REASON_KEY = "session_revoked_reason"
REVOKED_AT_KEY = "session_revoked_at"

# Motifs exposés au client — le frontend en dérive le message affiché.
REASON_ROLE_CHANGED = "role_changed"
REASON_DISABLED = "disabled"
REASON_DELETED = "deleted"

# Plus long que la durée de vie d'un refresh token central (1 h observée) : une
# liaison ne doit jamais expirer avant le token qu'elle protège.
_BINDING_TTL_SECONDS = 24 * 3600
_MEMORY_MAX_ENTRIES = 20_000
_REDIS_PREFIX = "edg:session-binding:"

_MESSAGES = {
    REASON_ROLE_CHANGED: "Votre rôle a été modifié par un administrateur. Veuillez vous reconnecter.",
    REASON_DISABLED: "Votre compte a été désactivé. Contactez un administrateur pour obtenir de nouveau l'accès.",
    REASON_DELETED: "Votre compte a été supprimé. Contactez un administrateur.",
}
_DEFAULT_MESSAGE = "Votre session n'est plus valide. Veuillez vous reconnecter."


class SessionRevokedException(UnauthorizedException):
    """401 typé : `error_code` + `value` (motif) permettent au frontend
    d'afficher un message précis au lieu d'un 401 brut."""

    def __init__(self, reason: str | None) -> None:
        error_code = (
            ErrorCode.ACCOUNT_DISABLED
            if reason in (REASON_DISABLED, REASON_DELETED)
            else ErrorCode.SESSION_REVOKED
        )
        super().__init__(_MESSAGES.get(reason or "", _DEFAULT_MESSAGE), error_code=error_code)
        self.value = reason or "revoked"


# ── État du compte ────────────────────────────────────────────────────────────

def _infos(account) -> dict:
    infos = getattr(account, "infos", None)
    return infos if isinstance(infos, dict) else {}


def session_version(account) -> int:
    try:
        return int(_infos(account).get(SESSION_VERSION_KEY) or 0)
    except (TypeError, ValueError):
        return 0


def revoked_reason(account) -> str | None:
    return _infos(account).get(REVOKED_REASON_KEY)


def is_account_active(account) -> bool:
    return bool(
        account.status
        and account.deleted_at is None
        and (account.account_status or "").strip().lower() == "active"
    )


def ensure_account_active(account) -> None:
    if not is_account_active(account):
        raise SessionRevokedException(
            REASON_DELETED if account.deleted_at is not None else REASON_DISABLED
        )


_SESSION_KEYS = (SESSION_VERSION_KEY, REVOKED_REASON_KEY, REVOKED_AT_KEY)


def preserve_session_keys(account, infos: dict) -> dict:
    """Un `infos` fourni par un client ne doit jamais réécrire l'état de session
    (ramener une ancienne version revaliderait d'anciens tokens)."""
    merged = {k: v for k, v in infos.items() if k not in _SESSION_KEYS}
    for key in _SESSION_KEYS:
        if key in _infos(account):
            merged[key] = _infos(account)[key]
    return merged


def revoked_infos(account, reason: str, base: dict | None = None) -> dict:
    """Nouvelle valeur de `infos` avec la version incrémentée — à écrire dans la
    MÊME mise à jour que le changement qui la motive (rôle, statut…). `base` :
    `infos` déjà préparé par l'appelant (fusion d'autres clés), sinon l'actuel."""
    infos = dict(base) if isinstance(base, dict) else dict(_infos(account))
    infos[SESSION_VERSION_KEY] = session_version(account) + 1
    infos[REVOKED_REASON_KEY] = reason
    infos[REVOKED_AT_KEY] = datetime.now(timezone.utc).isoformat()
    return infos


def queue_session_revoked(db, account_id: int, reason: str) -> None:
    """Événement ciblé sur le SEUL compte concerné, publié après commit.
    Aucune donnée sensible : identifiant, motif, horodatage."""
    queue_after_commit(db, AppEvent(
        type="user.session_revoked",
        payload={
            "user_id": account_id,
            "reason": reason,
            "timestamp": datetime.now(timezone.utc).isoformat(),
        },
        target={"user_ids": [account_id]},
    ))


def queue_user_changed(db, account_id: int, event_type: str = "user.updated") -> None:
    """Synchronise les Backoffices ouverts (tous les admins) et les autres
    onglets du compte concerné. Le client refetch : la base reste la source
    de vérité, l'événement ne transporte que l'identifiant."""
    queue_after_commit(db, AppEvent(
        type=event_type,
        payload={"id": account_id, "timestamp": datetime.now(timezone.utc).isoformat()},
        target={"roles": ["admin"], "user_ids": [account_id]},
    ))


# ── Liaisons token -> version ─────────────────────────────────────────────────

def _token_key(token: str) -> str:
    """Le token n'est jamais conservé en clair."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class _BindingStore:
    def __init__(self) -> None:
        self._memory: dict[str, tuple[float, int, int]] = {}
        self._redis = None
        self._redis_checked = False

    async def _get_redis(self):
        if self._redis_checked:
            return self._redis
        self._redis_checked = True
        if not _env.REDIS_URL or aioredis is None:
            return None
        try:
            client = aioredis.from_url(_env.REDIS_URL, decode_responses=True)
            await client.ping()
            self._redis = client
        except Exception as exc:
            logger.warning("session_registry : Redis indisponible (%s) — repli en mémoire.", exc)
            self._redis = None
        return self._redis

    # ── MySQL (STATE_BACKEND=mysql) ──────────────────────────────────────────

    @staticmethod
    def _require_db(db):
        if db is None:
            raise RuntimeError("session_registry : STATE_BACKEND=mysql exige la session de base de la requête.")
        return db

    async def _mysql_get(self, key: str, db) -> Optional[tuple[int, int]]:
        row = (await self._require_db(db).execute(
            select(SessionBinding.account_id, SessionBinding.version)
            .where(SessionBinding.token_hash == key, SessionBinding.expires_at > _utcnow())
        )).first()
        return (int(row[0]), int(row[1])) if row else None

    async def _mysql_set(self, key: str, account_id: int, version: int, *, only_if_absent: bool, db) -> None:
        db = self._require_db(db)
        expires_at = _utcnow() + timedelta(seconds=_BINDING_TTL_SECONDS)
        if not only_if_absent:
            await db.merge(SessionBinding(token_hash=key, account_id=account_id, version=version, expires_at=expires_at))
            await db.flush()
            return
        # Insertion atomique « si absent » : la clé primaire arbitre entre deux
        # processus concurrents ; le savepoint évite d'invalider la transaction
        # de la requête en cas de doublon. Une liaison expirée est remplacée.
        existing = await db.get(SessionBinding, key)
        if existing is not None:
            if existing.expires_at > _utcnow():
                return
            existing.account_id, existing.version, existing.expires_at = account_id, version, expires_at
            await db.flush()
            return
        try:
            async with db.begin_nested():
                db.add(SessionBinding(token_hash=key, account_id=account_id, version=version, expires_at=expires_at))
        except IntegrityError:
            pass  # lié entre-temps par un autre processus : sa liaison fait foi

    async def get(self, key: str, db=None) -> Optional[tuple[int, int]]:
        if state_backend.use_mysql():
            return await self._mysql_get(key, db)
        redis = await self._get_redis()
        if redis is not None:
            try:
                raw = await redis.get(_REDIS_PREFIX + key)
                if raw is None:
                    return None
                data = json.loads(raw)
                return int(data["a"]), int(data["v"])
            except Exception as exc:
                logger.warning("session_registry : lecture Redis échouée (%s) — repli mémoire.", exc)
        entry = self._memory.get(key)
        if entry is None or entry[0] <= time.monotonic():
            self._memory.pop(key, None)
            return None
        return entry[1], entry[2]

    async def set(self, key: str, account_id: int, version: int, *, only_if_absent: bool = False, db=None) -> None:
        if state_backend.use_mysql():
            await self._mysql_set(key, account_id, version, only_if_absent=only_if_absent, db=db)
            return
        redis = await self._get_redis()
        if redis is not None:
            try:
                await redis.set(
                    _REDIS_PREFIX + key,
                    json.dumps({"a": account_id, "v": version}),
                    ex=_BINDING_TTL_SECONDS,
                    nx=only_if_absent,
                )
                return
            except Exception as exc:
                logger.warning("session_registry : écriture Redis échouée (%s) — repli mémoire.", exc)
        now = time.monotonic()
        if only_if_absent:
            current = self._memory.get(key)
            if current is not None and current[0] > now:
                return
        if len(self._memory) >= _MEMORY_MAX_ENTRIES:
            self._memory = {k: v for k, v in self._memory.items() if v[0] > now}
            if len(self._memory) >= _MEMORY_MAX_ENTRIES:
                self._memory.clear()
        self._memory[key] = (now + _BINDING_TTL_SECONDS, account_id, version)

    def reset(self) -> None:
        """Tests uniquement."""
        self._memory.clear()
        self._redis = None
        self._redis_checked = False


_store = _BindingStore()


async def bind_token(token: str | None, account, *, db=None) -> None:
    """Lie un token relayé par EDG Connect à la version courante du compte."""
    if not token or account is None:
        return
    await _store.set(_token_key(token), int(account.id), session_version(account), db=db)


async def get_binding(token: str, *, db=None) -> Optional[tuple[int, int]]:
    return await _store.get(_token_key(token), db=db)


async def load_token_state(db, token: str) -> tuple[bool, Optional[tuple[int, int]]]:
    """(révoqué par une déconnexion ?, liaison) pour un token.

    STATE_BACKEND=mysql : UNE seule requête (UNION ALL revoked_token +
    session_binding) — c'est le surcoût par requête authentifiée. Autres
    modes : contrôle de révocation en base, liaison en Redis/mémoire."""
    if not state_backend.use_mysql():
        return await token_revocation.is_revoked(db, token), await get_binding(token, db=db)
    key, now = _token_key(token), _utcnow()
    revoked_q = select(literal("r").label("kind"), literal(0).label("a"), literal(0).label("v")).where(
        RevokedToken.token_hash == key, RevokedToken.expires_at > now,
    )
    binding_q = select(
        literal("b").label("kind"), SessionBinding.account_id.label("a"), SessionBinding.version.label("v"),
    ).where(SessionBinding.token_hash == key, SessionBinding.expires_at > now)
    rows = (await db.execute(union_all(revoked_q, binding_q))).all()
    revoked = any(r.kind == "r" for r in rows)
    binding = next(((int(r.a), int(r.v)) for r in rows if r.kind == "b"), None)
    return revoked, binding


_UNKNOWN: Any = object()


async def ensure_token_current(token: str, account, *, db=None, binding=_UNKNOWN) -> Optional[tuple[int, int]]:
    """Refuse un token lié à une version antérieure du compte (ou à un autre
    compte). Un token inconnu est lié à la version courante. `binding` : valeur
    déjà lue (load_token_state) pour éviter une requête. Retourne la liaison."""
    if binding is _UNKNOWN:
        binding = await get_binding(token, db=db)
    if binding is None:
        await _store.set(
            _token_key(token), int(account.id), session_version(account), only_if_absent=True, db=db,
        )
        binding = await get_binding(token, db=db)
        if binding is None:
            return None
    bound_account_id, bound_version = binding
    if bound_account_id != int(account.id) or bound_version != session_version(account):
        raise SessionRevokedException(revoked_reason(account))
    return binding


def reset_for_tests() -> None:
    _store.reset()


def snapshot_for_tests() -> dict[str, Any]:
    return dict(_store._memory)
