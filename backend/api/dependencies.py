"""
Dépendances FastAPI — session SQLAlchemy + authentification JWT.

Hiérarchie des dépendances auth :
  get_current_user           → utilisateur authentifié obligatoire (401 si absent)
  get_current_user_optional  → utilisateur authentifié ou None (routes semi-publiques)
  require_roles(*roles)      → get_current_user + vérification du rôle (403 si refusé)
  require_permissions(*perm) → get_current_user + vérification des permissions (403)

Mode développement :
  Si DISABLE_AUTH=True dans .env, l'authentification est désactivée.
  Un utilisateur fictif de rôle 'admin' est injecté pour tous les appels.
  INTERDIT en production — une RuntimeError est levée au démarrage si tenté.
"""
from __future__ import annotations

import logging
from typing import AsyncGenerator, Callable, Optional

from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession

from api.configs.Database import AsyncSessionLocal
from api.configs.Environment import get_environment
from api.core.exceptions import UnauthorizedException, ForbiddenException
from api.core.security import decode_token
from api.core.token_blacklist import token_blacklist
from api.core.rbac import Permission, ROLE_GROUP_ALIASES, ROLE_PERMISSIONS, normalize_role

logger = logging.getLogger(__name__)
_env = get_environment()

# ── C-07 : Garde DISABLE_AUTH en production ───────────────────────────────────
if _env.DISABLE_AUTH and _env.APP_ENV == "production":
    raise RuntimeError(
        "DISABLE_AUTH=True est interdit en production (APP_ENV=production). "
        "Désactivez cette variable dans votre fichier .env de production."
    )

# ── 3.4 : Garde SECRET_KEY placeholder en production ──────────────────────────
if _env.APP_ENV == "production" and (
    "changeme" in _env.SECRET_KEY.lower() or len(_env.SECRET_KEY) < 32
):
    raise RuntimeError(
        "SECRET_KEY invalide ou de type placeholder en production (APP_ENV=production). "
        "Générez une clé avec : python -c \"import secrets; print(secrets.token_hex(32))\""
    )

# ── 3.3 : Garde REDIS_URL absent en production ────────────────────────────────
# Sans Redis, la blacklist de tokens et le rate-limiter (RateLimitMiddleware)
# retombent en mode mémoire — non partagé entre les workers gunicorn.
if _env.APP_ENV == "production" and not _env.REDIS_URL:
    raise RuntimeError(
        "REDIS_URL est requis en production (APP_ENV=production). "
        "Sans Redis, la blacklist de tokens et le rate-limiter ne sont pas partagés "
        "entre les workers — configurez REDIS_URL dans votre .env de production."
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


# ── Authentification JWT ──────────────────────────────────────────────────────

async def get_current_user(
    token: Optional[str] = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db),
):
    """
    Extrait et valide le JWT porteur.
    Vérifie : token valide → type access → JTI non révoqué → session active → compte actif.
    Retourne l'objet Account SQLAlchemy de l'utilisateur connecté.
    Lève 401 si l'une de ces vérifications échoue.
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

    # ── Décode le JWT ─────────────────────────────────────────────────────────
    try:
        payload = decode_token(token)
    except UnauthorizedException as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.message,
            headers={"WWW-Authenticate": "Bearer"},
        )

    # ── Vérifie le type ───────────────────────────────────────────────────────
    if payload.get("type") != "access":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Type de token invalide. Utilisez un access token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # ── Vérifie la blacklist (JTI) ────────────────────────────────────────────
    jti = payload.get("jti", "")
    if await token_blacklist.is_revoked(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token révoqué. Veuillez vous reconnecter.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # ── Charge l'utilisateur depuis la BDD ────────────────────────────────────
    account_id = int(payload.get("sub", 0))
    from api.repositories import AccountRepository
    repo = AccountRepository(db)
    user = await repo.get_by_id(account_id)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Compte introuvable ou désactivé.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    if not user.status or user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Compte désactivé ou supprimé. Contactez l'administration.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    return user


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
