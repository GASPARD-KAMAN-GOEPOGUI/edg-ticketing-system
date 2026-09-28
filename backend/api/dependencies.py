"""
Dépendances FastAPI — session SQLAlchemy + authentification centrale manager-user.

Hiérarchie des dépendances auth :
  get_current_user           → utilisateur authentifié obligatoire (401 si absent)
  get_current_user_optional  → utilisateur authentifié ou None (routes semi-publiques)
  require_roles(*roles)      → get_current_user + vérification du rôle (403 si refusé)
  require_permissions(*perm) → get_current_user + vérification des permissions (403)

Chaque requête protégée valide le bearer token auprès de la plateforme centrale
(scopes + groupes), résout le compte local par central_user_id (aucun
rattachement automatique ici — voir api.core.central_auth), puis synchronise le
rôle local depuis le groupe central mappé, uniquement si le rôle actuel
appartient à {admin, chief-service, user} (chief/director restent locaux).

Le SEUL endroit où un compte local peut être créé sans passer par
POST /accounts (admin) ou POST /auth/register est POST /auth/login, via
resolve_or_provision_login_account() ci-dessous : auto-provisioning silencieux
si l'utilisateur appartient déjà à un groupe support central, ou renvoi d'une
ConsentRequiredResponse sinon (voir RouteAuth.py). get_current_user() reste
strict pour toutes les autres routes protégées et pour SSE.

Mode développement :
  Si DISABLE_AUTH=True dans .env, l'authentification est désactivée (aucun
  appel à la plateforme centrale). Un utilisateur fictif de rôle 'admin' est
  injecté pour tous les appels. INTERDIT en production — une RuntimeError est
  levée au démarrage si tenté.
"""
from __future__ import annotations

import asyncio
import hashlib
import logging
import time
from typing import AsyncGenerator, Callable, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from api.configs.Database import AsyncSessionLocal
from api.configs.Environment import get_environment
from api.core import central_auth
from api.core.rbac import Permission, ROLE_GROUP_ALIASES, ROLE_PERMISSIONS, normalize_role

logger = logging.getLogger(__name__)
_env = get_environment()

# Roles dont le rôle local peut être mis à jour par la synchro depuis la plateforme
# centrale (à la connexion). Doit couvrir exactement les rôles ayant un groupe central
# dédié dans GROUP_ROLE_PRIORITY — sinon un changement de groupe côté central ne
# descendrait jamais jusqu'au rôle local.
# `chief-departement` et `director` en sont volontairement exclus : ils n'ont aucun
# groupe central, donc restent purement locaux et ne sont jamais écrasés.
_ROLE_SYNC_SPACE = {"admin", "chief-service", "chef-division-support", "technicien", "user"}

# ── C-07 : Garde DISABLE_AUTH en production ───────────────────────────────────
if _env.DISABLE_AUTH and _env.APP_ENV == "production":
    raise RuntimeError(
        "DISABLE_AUTH=True est interdit en production (APP_ENV=production). "
        "Désactivez cette variable dans votre fichier .env de production."
    )

# ── Garde variables centrales absentes en production ──────────────────────────
if _env.APP_ENV == "production" and not _env.DISABLE_AUTH and (
    not _env.CENTRAL_AUTH_BASE_URL or not _env.CLIENT_APP_CODE or not _env.CLIENT_APP_SECRET
):
    raise RuntimeError(
        "CENTRAL_AUTH_BASE_URL/CLIENT_APP_CODE/CLIENT_APP_SECRET sont requis en production "
        "(APP_ENV=production) — configurez l'intégration manager-user dans votre .env de production."
    )

# ── Garde REDIS_URL absent en production ───────────────────────────────────────
# Sans Redis, le rate-limiter (RateLimitMiddleware) retombe en mode mémoire —
# non partagé entre les workers gunicorn.
if _env.APP_ENV == "production" and not _env.REDIS_URL:
    raise RuntimeError(
        "REDIS_URL est requis en production (APP_ENV=production). "
        "Sans Redis, le rate-limiter n'est pas partagé entre les workers — "
        "configurez REDIS_URL dans votre .env de production."
    )

# OAuth2 scheme — tokenUrl utilisé par OpenAPI/Swagger uniquement
oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/api/v1/auth/login",
    auto_error=False,  # on gère les erreurs manuellement
)


# ── Session SQLAlchemy ────────────────────────────────────────────────────────

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
            logger.debug("db: COMMIT OK")
        except Exception:
            await session.rollback()
            logger.debug("db: ROLLBACK (exception dans le handler)")
            raise


# ── Authentification centrale (manager-user) ──────────────────────────────────

def _ensure_account_active(account) -> None:
    if (
        not account.status
        or account.deleted_at is not None
        or (account.account_status or "").strip().lower() != "active"
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Compte désactivé ou supprimé. Contactez l'administration.",
            headers={"WWW-Authenticate": "Bearer"},
        )


async def _sync_role_from_groups(account, groups: list[dict], repo):
    """Applique le mapping groupes centraux -> rôle local, dans les limites de
    _ROLE_SYNC_SPACE (voir docstring de module)."""
    mapped_role = central_auth.role_from_groups(groups)
    current_role = normalize_role(account.role)
    if mapped_role and current_role in _ROLE_SYNC_SPACE and mapped_role != current_role:
        updated = await repo.update(account.id, {"role": mapped_role})
        if updated is not None:
            return updated
    return account


# ── Cache des scopes/groupes centraux ────────────────────────────────────────
#
# Sans cache, CHAQUE requête protégée déclenchait deux appels HTTP vers la
# plateforme centrale (get_scopes + get_groups), soit ~3 s de latence réseau par
# requête. Un écran qui en émet cinq — la création d'utilisateur et ses listes en
# cascade direction → département → service — payait dix allers-retours et
# pouvait dépasser le timeout de 15 s du client, laissant des listes vides sans
# message d'erreur.
#
# Trois mécanismes, chacun pour une raison distincte :
#   1. TTL court (CENTRAL_AUTH_CACHE_TTL) — mutualise les requêtes d'un même
#      écran. Volontairement bas : une révocation ou un changement de groupe
#      central met au pire TTL secondes à être vu.
#   2. Verrou par token — sans lui, cinq requêtes parallèles sur un cache froid
#      partiraient toutes au réseau ; c'est précisément le cas du chargement
#      d'écran qu'on cherche à corriger. La première appelle, les autres
#      attendent puis lisent le cache.
#   3. Appels en parallèle — get_scopes et get_groups sont indépendants ;
#      asyncio.gather divise par deux la latence des cache miss restants.
#
# Cache mémoire par processus : en production (4 workers gunicorn) chaque worker
# a le sien, ce qui reste correct — le pire cas est un appel par worker et par
# TTL. Un cache partagé passerait par Redis, comme la blacklist de tokens.
_scopes_cache: dict[str, tuple[float, dict, list[dict]]] = {}
_scopes_locks: dict[str, asyncio.Lock] = {}
_CACHE_MAX_ENTRIES = 512


def _token_key(token: str) -> str:
    """Le token n'est jamais conservé en clair, même en mémoire."""
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _cache_sweep(now: float) -> None:
    expired = [k for k, (exp, _, _) in _scopes_cache.items() if exp <= now]
    for key in expired:
        _scopes_cache.pop(key, None)
        lock = _scopes_locks.get(key)
        if lock is not None and not lock.locked():
            _scopes_locks.pop(key, None)
    # Garde-fou mémoire : si le cache déborde malgré le sweep (beaucoup de tokens
    # actifs), on repart de zéro plutôt que de croître sans limite.
    if len(_scopes_cache) > _CACHE_MAX_ENTRIES:
        _scopes_cache.clear()
        for key, lock in list(_scopes_locks.items()):
            if not lock.locked():
                _scopes_locks.pop(key, None)


def invalidate_central_auth_cache(token: str | None = None) -> None:
    """Purge le cache — un token précis (déconnexion), ou tout le cache.

    Appelé au logout : sans ça, le token resterait accepté jusqu'à l'expiration
    de son entrée, alors que l'utilisateur vient de se déconnecter.
    """
    if token is None:
        _scopes_cache.clear()
        return
    key = _token_key(token)
    _scopes_cache.pop(key, None)
    lock = _scopes_locks.get(key)
    if lock is not None and not lock.locked():
        _scopes_locks.pop(key, None)


async def _fetch_scopes_and_groups(token: str) -> tuple[dict, list[dict]]:
    ttl = _env.CENTRAL_AUTH_CACHE_TTL
    if ttl <= 0:
        return await _fetch_scopes_and_groups_uncached(token)

    key = _token_key(token)
    now = time.monotonic()

    cached = _scopes_cache.get(key)
    if cached is not None and cached[0] > now:
        return cached[1], cached[2]

    lock = _scopes_locks.setdefault(key, asyncio.Lock())
    async with lock:
        # Une requête concurrente a pu remplir le cache pendant l'attente.
        now = time.monotonic()
        cached = _scopes_cache.get(key)
        if cached is not None and cached[0] > now:
            return cached[1], cached[2]

        scopes, groups = await _fetch_scopes_and_groups_uncached(token)
        # Seuls les succès sont mis en cache : une erreur d'auth ou une panne du
        # central ne doit pas être figée pour les requêtes suivantes.
        _scopes_cache[key] = (time.monotonic() + ttl, scopes, groups)
        _cache_sweep(now)
        return scopes, groups


async def _fetch_scopes_and_groups_uncached(token: str) -> tuple[dict, list[dict]]:
    try:
        scopes, groups = await asyncio.gather(
            central_auth.get_scopes(token),
            central_auth.get_groups(token),
        )
    except central_auth.CentralUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service d'authentification central indisponible.",
        )
    except central_auth.CentralAuthError:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session invalide ou expirée.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    return scopes, groups


async def resolve_central_account(token: str, db: AsyncSession):
    """
    Valide un bearer token auprès de la plateforme centrale (scopes + groupes),
    résout le compte local par central_user_id (aucun rattachement automatique
    ici) et synchronise le rôle si celui-ci appartient à {admin, chief-service,
    user}. Lève HTTPException (401/503) en cas d'échec. Utilisé par
    get_current_user et par la validation du token de connexion SSE
    (RouteSSE.py) — comportement strict inchangé, voir
    resolve_or_provision_login_account() pour le cas login.
    """
    scopes, groups = await _fetch_scopes_and_groups(token)

    central_user_id = scopes.get("user_id")
    from api.repositories import AccountRepository
    repo = AccountRepository(db)
    account = await repo.find_by_central_user_id(central_user_id) if central_user_id else None
    if account is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Ce compte n'est pas rattaché à un compte local. Contactez un administrateur.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    account = await _sync_role_from_groups(account, groups, repo)
    _ensure_account_active(account)
    return account


async def resolve_or_provision_login_account(bearer_token: str, db: AsyncSession):
    """
    Variante de resolve_central_account() réservée à POST /auth/login. Ne lève
    JAMAIS "compte non rattaché" — distingue :
      - l'utilisateur appartient déjà à un groupe support central
        (admin-support/qualify-support/collaborateur-support) mais son miroir
        local est absent (compte créé/rattaché par une autre équipe, ou perdu
        localement) -> auto-provisioning silencieux, rôle = mapping du groupe ;
      - l'utilisateur central est connu mais n'appartient à aucun groupe de
        cette application -> retourne (None, scopes) ; le caller (RouteAuth.py)
        doit alors répondre par une ConsentRequiredResponse plutôt que de créer
        un compte, en attendant un consentement explicite (POST
        /auth/consent/accept).

    Retourne (account | None, scopes). Lève HTTPException (401/503) pour les
    échecs centraux et pour un compte désactivé/supprimé, exactement comme
    resolve_central_account.
    """
    scopes, groups = await _fetch_scopes_and_groups(bearer_token)

    from api.repositories import AccountRepository
    repo = AccountRepository(db)
    central_user_id = scopes.get("user_id")
    account = await repo.find_by_central_user_id(central_user_id) if central_user_id else None

    if account is None:
        if not central_user_id:
            # Le central n'a pas renvoyé de user_id exploitable dans les scopes —
            # provisionner sans ancrage central_user_id créerait un compte local
            # impossible à retrouver au prochain login (nouvelle identité fantôme
            # à chaque connexion). Traité comme une session invalide plutôt que
            # comme "aucun groupe support" (ce n'est pas la même situation).
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Session invalide ou expirée.",
                headers={"WWW-Authenticate": "Bearer"},
            )

        mapped_role = central_auth.role_from_groups(groups)
        if not mapped_role:
            return None, scopes

        try:
            profile = await central_auth.get_profile(bearer_token)
        except central_auth.CentralAuthError:
            profile = {}
        identity = central_auth.parse_profile_identity(profile)
        email = (scopes.get("email") or "").strip().lower()

        from api.services import AccountService
        account = await AccountService(db).provision_from_central(
            central_user_id=central_user_id,
            central_user_uuid=identity["uuid"],
            email=email,
            name=identity["name"] or (email.split("@")[0] if email else "Utilisateur"),
            firstname=identity["firstname"],
            phone=identity["phone"],
            role=mapped_role,
        )
    else:
        account = await _sync_role_from_groups(account, groups, repo)

    _ensure_account_active(account)
    return account, scopes


async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """
    Valide le bearer token auprès de la plateforme centrale manager-user et
    retourne le compte local rattaché. Lève 401/503 si l'une des vérifications
    échoue.
    """
    # ── Bypass développement ──────────────────────────────────────────────────
    if _env.DISABLE_AUTH:
        # Chercher le premier compte admin actif en DB pour éviter id=0 (404 sur /me)
        from api.repositories import AccountRepository
        repo = AccountRepository(db)
        items, _ = await repo.list(filters={"role": "admin"}, limit=1)
        if items:
            return items[0]
        # Repli sur compte fictif si aucun admin n'existe encore (DB vide)
        from api.models.ModelAccount import Account as AccountModel
        dev_user = AccountModel()
        dev_user.id    = 0
        dev_user.uuid  = "00000000-0000-0000-0000-000000000000"
        dev_user.name  = "Dev Admin"
        dev_user.email = "admin@edg.gn"
        dev_user.role  = "admin"
        dev_user.status = True
        dev_user.deleted_at = None
        return dev_user

    # ── Token manquant ────────────────────────────────────────────────────────
    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Authentification requise pour accéder à cette ressource.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return await resolve_central_account(token, db)


async def get_current_user_optional(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """
    Comme get_current_user mais retourne None au lieu d'une 401.
    Utile pour les routes semi-publiques.
    """
    if not token:
        return None
    try:
        return await get_current_user(token=token, db=db)
    except HTTPException:
        return None


# ── Factories de guards ───────────────────────────────────────────────────────

def require_roles(*roles: str) -> Callable:
    """
    Retourne une dépendance FastAPI qui exige que l'utilisateur
    ait l'un des rôles listés.

    Usage :
        @router.get("/", dependencies=[Depends(require_roles("admin"))])
    """
    async def _guard(current_user=Depends(get_current_user)):
        current_role = normalize_role(current_user.role)
        allowed_roles = set()
        for role in roles:
            raw = role.strip().lower()
            allowed_roles.update(ROLE_GROUP_ALIASES.get(raw, ROLE_GROUP_ALIASES.get(normalize_role(role), {normalize_role(role)})))
        if current_role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Accès réservé aux rôles : {', '.join(roles)}. "
                    f"Votre rôle actuel est '{current_user.role}'."
                ),
            )
        return current_user
    return _guard


def require_permissions(*permissions: Permission) -> Callable:
    """
    Retourne une dépendance FastAPI qui exige que l'utilisateur
    dispose de toutes les permissions listées.
    """
    async def _guard(current_user=Depends(get_current_user)):
        user_perms = ROLE_PERMISSIONS.get(normalize_role(current_user.role), set())
        missing = [p.value for p in permissions if p not in user_perms]
        if missing:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    f"Permission(s) manquante(s) : {', '.join(missing)}."
                ),
            )
        return current_user
    return _guard


# ── Alias pratiques ───────────────────────────────────────────────────────────

def admin_only() -> Callable:
    """Raccourci pour require_roles("admin")."""
    return require_roles("admin")


def authenticated() -> Callable:
    """Raccourci pour get_current_user (non-optionnel)."""
    return get_current_user
