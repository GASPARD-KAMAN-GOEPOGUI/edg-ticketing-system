"""
Dépendances FastAPI — session SQLAlchemy + authentification centrale manager-user.

Hiérarchie des dépendances auth :
  get_current_user           → utilisateur authentifié obligatoire (401 si absent)
  get_current_user_optional  → utilisateur authentifié ou None (routes semi-publiques)
  require_roles(*roles)      → get_current_user + vérification du rôle (403 si refusé)
  require_permissions(*perm) → get_current_user + vérification des permissions (403)

Chaque requête protégée valide le bearer token auprès de la plateforme centrale
(scopes + groupes), résout le compte local par central_user_id (aucun
rattachement automatique — voir api.core.central_auth), puis synchronise le
rôle local depuis le groupe central mappé, uniquement si le rôle actuel
appartient à {admin, agent-support, user} (chief/director restent locaux).

Mode développement :
  Si DISABLE_AUTH=True dans .env, l'authentification est désactivée (aucun
  appel à la plateforme centrale). Un utilisateur fictif de rôle 'admin' est
  injecté pour tous les appels. INTERDIT en production — une RuntimeError est
  levée au démarrage si tenté.
"""
from __future__ import annotations

import logging
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

_ROLE_SYNC_SPACE = {"admin", "agent-support", "user"}

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

async def resolve_central_account(token: str, db: AsyncSession):
    """
    Valide un bearer token auprès de la plateforme centrale (scopes + groupes),
    résout le compte local par central_user_id (aucun rattachement automatique)
    et synchronise le rôle si celui-ci appartient à {admin, agent-support, user}.
    Lève HTTPException (401/503) en cas d'échec. Utilisé par get_current_user
    et par la validation du token de connexion SSE (RouteSSE.py).
    """
    try:
        scopes = await central_auth.get_scopes(token)
        groups = await central_auth.get_groups(token)
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

    mapped_role = central_auth.role_from_groups(groups)
    current_role = normalize_role(account.role)
    if mapped_role and current_role in _ROLE_SYNC_SPACE and mapped_role != current_role:
        updated = await repo.update(account.id, {"role": mapped_role})
        if updated is not None:
            account = updated

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

    return account


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
        @router.get("/", dependencies=[Depends(require_roles("admin", "chief-service"))])
    """
    async def _guard(current_user=Depends(get_current_user)):
        current_role = normalize_role(current_user.role)
        allowed_roles = set()
        for role in roles:
            if role == "dg":
                continue
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
