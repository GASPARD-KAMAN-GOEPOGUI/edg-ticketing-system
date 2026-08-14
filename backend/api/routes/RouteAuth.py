"""
Routes d'authentification — plateforme centrale manager-user.

Endpoints :
  POST /auth/register          Inscription publique (rôle "user" forcé) via le central
  POST /auth/forgot-password   Étape 1 — envoi d'un code de vérification par email (OTP local)
  POST /auth/reset-password    Étape 3 — vérification du code + reset central du mot de passe
  POST /auth/login             Connexion (email/matricule + mot de passe) via le central
  POST /auth/refresh           Rafraîchissement de l'access token via le central
  POST /auth/logout            Déconnexion (aucune révocation locale, tokens émis par le central)
  GET  /auth/me                Profil de l'utilisateur connecté (compte local)
  GET  /auth/me/scopes         Relais des scopes centraux (métadonnées, debug uniquement)
  GET  /auth/me/groups         Relais des groupes centraux (métadonnées, debug uniquement)

Le mot de passe est géré par la plateforme centrale manager-user — voir
backend/README-integration-plateforme-centrale/README-integration-plateforme-centrale.md.
La plateforme centrale n'exposant aucun endpoint self-service de reset (seul un
reset admin existe, §12), forgot-password/reset-password reconstituent un OTP par
email localement — le code (hashé), son expiration et le compteur de tentatives
sont stockés dans account.infos (pas de table dédiée), qui déverrouille ensuite
ce même appel central.
"""
from __future__ import annotations

import hashlib
import logging
import secrets
from datetime import datetime, timedelta
from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.ext.asyncio import AsyncSession

from api.core import central_auth, mailer
from api.core.exceptions import ValidationException
from api.dependencies import (
    get_db,
    get_current_user,
    get_current_user_optional,
    oauth2_scheme,
    resolve_central_account,
)
from api.repositories import AccountRepository
from api.schemas.SchemaAuth import (
    RegisterRequest,
    LoginRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    RefreshRequest,
    LogoutRequest,
    TokenResponse,
    AccessTokenResponse,
)
from api.schemas.SchemaAccount import AccountResponse
from api.services import AccountService

logger = logging.getLogger(__name__)

_RESET_CODE_TTL_MINUTES = 15
_RESET_CODE_MAX_ATTEMPTS = 5

router = APIRouter(prefix="/auth", tags=["auth"])


def _svc(db: AsyncSession = Depends(get_db)) -> AccountService:
    return AccountService(db)


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


async def _log_auth_event(
    db: AsyncSession,
    *,
    actor: str,
    actor_id: int | None,
    actor_role: str,
    action: str,
    target: str,
    ip_address: str | None = None,
    log_status: str = "success",
) -> None:
    try:
        from api.repositories.RepositoryActivityLog import ActivityLogRepository
        await ActivityLogRepository(db).append({
            "actor": actor,
            "actor_id": actor_id,
            "actor_role": actor_role,
            "action": action,
            "category": "auth",
            "target": target,
            "ip_address": ip_address,
            "log_status": log_status,
        })
    except Exception as exc:
        logger.warning("Impossible d'écrire le log auth : %s", exc)


# ── Inscription ───────────────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=AccountResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Inscription publique (rôle utilisateur, via la plateforme centrale)",
)
async def register(
    request: Request,
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    svc: AccountService = Depends(_svc),
):
    data = body.dict()
    data["role"] = "user"  # C-01 — auto-élévation impossible, jamais depuis le payload client
    account = await svc.create(data, validate_org_assignment=False)
    await _log_auth_event(
        db, actor=account.email, actor_id=account.id, actor_role=account.role,
        action="register", target=f"account:{account.id}", ip_address=_client_ip(request),
    )
    return account


# ── Mot de passe oublié ──────────────────────────────────────────────────────
# La plateforme centrale n'expose aucun endpoint self-service pour ça (README §12 :
# seul un reset déclenché par un admin, au token machine, existe). Ce flux
# reconstitue donc un OTP par email côté EDG Connect, qui ne fait que déverrouiller
# ce même appel central (central_auth.reset_central_password) avec le mot de passe
# choisi par l'utilisateur, une fois le code vérifié.

@router.post(
    "/forgot-password",
    summary="Étape 1 — demander un code de vérification par email",
)
async def forgot_password(
    body: ForgotPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    email = body.email.strip().lower()
    account_repo = AccountRepository(db)
    account = await account_repo.find_by_email(email)

    response: dict = {"sent": True}
    # Ne jamais révéler si l'email existe (anti-énumération) — toujours 200,
    # mais on ne génère/envoie un code que si un compte correspond réellement.
    if account is not None:
        code = f"{secrets.randbelow(1_000_000):06d}"
        code_hash = hashlib.sha256(code.encode()).hexdigest()
        expires_at = datetime.utcnow() + timedelta(minutes=_RESET_CODE_TTL_MINUTES)
        # Pas de table dédiée — le code (hashé), son expiration et le compteur de
        # tentatives vivent dans account.infos (merge JSON, cf. update_infos()).
        await account_repo.update_infos(account.id, {
            "reset_code_hash": code_hash,
            "reset_code_expires_at": expires_at.isoformat(),
            "reset_code_attempts": 0,
        })
        email_sent = False
        full_name = (f"{account.firstname or ''} {account.name or ''}".strip() or account.name or "").upper()
        try:
            email_sent = await mailer.send_reset_code_email(email, code, full_name)
        except Exception as exc:
            logger.error("Envoi de l'email de réinitialisation échoué pour %r : %s", email, exc)

        # Le code n'apparaît dans la réponse que si l'email n'a vraiment pas pu être
        # envoyé (SMTP non configuré ou échec) — jamais quand l'envoi a réussi, pour ne
        # pas l'exposer dans l'UI alors qu'il part réellement dans la boîte mail.
        if not email_sent:
            response["dev_code"] = code

    return response


@router.post(
    "/reset-password",
    summary="Étape 3 — vérifier le code et réinitialiser le mot de passe",
)
async def reset_password_route(
    request: Request,
    body: ResetPasswordRequest,
    db: AsyncSession = Depends(get_db),
):
    email = body.email.strip().lower()
    account_repo = AccountRepository(db)
    account = await account_repo.find_by_email(email)

    def _expired() -> NoReturn:
        raise ValidationException(
            "Code expiré ou introuvable. Demandez un nouveau code.",
            error_code="RESET_CODE_EXPIRED",
        )

    if account is None or not account.central_user_uuid:
        _expired()

    infos = account.infos or {}
    code_hash = infos.get("reset_code_hash")
    expires_at_raw = infos.get("reset_code_expires_at")
    attempts = int(infos.get("reset_code_attempts") or 0)

    if not code_hash or not expires_at_raw:
        _expired()
    try:
        expires_at = datetime.fromisoformat(expires_at_raw)
    except (TypeError, ValueError):
        _expired()
    if datetime.utcnow() > expires_at or attempts >= _RESET_CODE_MAX_ATTEMPTS:
        _expired()

    submitted_hash = hashlib.sha256(body.code.strip().encode()).hexdigest()
    if not secrets.compare_digest(submitted_hash, code_hash):
        await account_repo.update_infos(account.id, {"reset_code_attempts": attempts + 1})
        raise ValidationException(
            "Code invalide ou déjà utilisé. Vérifiez le code saisi.",
            error_code="RESET_CODE_INVALID",
        )

    machine_token = await central_auth.get_machine_token()
    await central_auth.reset_central_password(
        account.central_user_uuid, machine_token, new_password=body.new_password,
    )
    # Invalide le code après usage (empêche le replay).
    await account_repo.update_infos(account.id, {
        "reset_code_hash": None, "reset_code_expires_at": None, "reset_code_attempts": 0,
    })

    await _log_auth_event(
        db, actor=account.email, actor_id=account.id, actor_role=account.role,
        action="reset_password", target=f"account:{account.id}", ip_address=_client_ip(request),
    )
    return {"reset": True}


# ── Connexion ─────────────────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Connexion (email/matricule + mot de passe) via la plateforme centrale",
)
async def login(
    request: Request,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
):
    ip = _client_ip(request)
    email = body.identifier.strip()

    if "@" not in email:
        # Identifiant non-email (matricule) : résolution locale, le central n'accepte que l'email
        from api.repositories import AccountRepository
        local = await AccountRepository(db).find_by_matricule(email)
        if local is None:
            await _log_auth_event(
                db, actor=body.identifier, actor_id=None, actor_role="unknown",
                action="login_failed", target="auth", ip_address=ip, log_status="error",
            )
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="Identifiant ou mot de passe incorrect.",
            )
        email = local.email

    try:
        tokens = await central_auth.central_login(email, body.password)
    except central_auth.CentralInvalidCredentials:
        await _log_auth_event(
            db, actor=email, actor_id=None, actor_role="unknown",
            action="login_failed", target="auth", ip_address=ip, log_status="error",
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Identifiant ou mot de passe incorrect.",
        )
    except (central_auth.CentralUnavailableError, central_auth.CentralInvalidClientCredentials) as exc:
        logger.error("central_auth: échec login (%s)", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service d'authentification central indisponible.",
        )

    bearer_token = tokens["bearer_token"]
    account = await resolve_central_account(bearer_token, db)

    await _log_auth_event(
        db, actor=account.email, actor_id=account.id, actor_role=account.role,
        action="login", target=f"account:{account.id}", ip_address=ip,
    )
    await central_auth.log_central_event(
        bearer_token, object_id=str(account.id), action="login", status="success",
        message=f"Connexion réussie : {account.email}",
    )

    return {
        "access_token": bearer_token,
        "refresh_token": tokens.get("refresh_token", ""),
        "token_type": tokens.get("token_type", "bearer"),
        "expires_in": tokens.get("expires_in", 0),
        "user": account,
    }


# ── Rafraîchissement du token ─────────────────────────────────────────────────

@router.post(
    "/refresh",
    response_model=AccessTokenResponse,
    summary="Obtenir un nouveau access token depuis le refresh token (relais central)",
)
async def refresh_token(body: RefreshRequest):
    try:
        tokens = await central_auth.central_refresh(body.refresh_token)
    except central_auth.CentralInvalidCredentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session expirée. Veuillez vous reconnecter.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except central_auth.CentralUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Service d'authentification central indisponible.",
        )

    return {
        "access_token": tokens["bearer_token"],
        "token_type": tokens.get("token_type", "bearer"),
        "expires_in": tokens.get("expires_in", 0),
    }


# ── Déconnexion ───────────────────────────────────────────────────────────────

@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Déconnexion",
)
async def logout(
    request: Request,
    body: LogoutRequest,
    db: AsyncSession = Depends(get_db),
    bearer_token: str | None = Depends(oauth2_scheme),
    current_user=Depends(get_current_user_optional),
):
    if current_user is not None:
        await _log_auth_event(
            db, actor=current_user.email, actor_id=current_user.id, actor_role=current_user.role,
            action="logout", target=f"account:{current_user.id}", ip_address=_client_ip(request),
        )
        if bearer_token:
            await central_auth.log_central_event(
                bearer_token, object_id=str(current_user.id), action="logout", status="success",
                message=f"Déconnexion : {current_user.email}",
            )


# ── Profil courant ────────────────────────────────────────────────────────────

@router.get(
    "/me",
    response_model=AccountResponse,
    summary="Profil de l'utilisateur connecté",
)
async def get_me(current_user=Depends(get_current_user)):
    return current_user


@router.get(
    "/me/scopes",
    summary="Relais des scopes centraux de l'utilisateur connecté (debug/metadata)",
)
async def get_me_scopes(bearer_token: str | None = Depends(oauth2_scheme)):
    if not bearer_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentification requise.")
    try:
        return await central_auth.get_scopes(bearer_token)
    except central_auth.CentralUnavailableError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service central indisponible.")
    except central_auth.CentralAuthError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session invalide ou expirée.")


@router.get(
    "/me/groups",
    summary="Relais des groupes centraux de l'utilisateur connecté (debug/metadata)",
)
async def get_me_groups(bearer_token: str | None = Depends(oauth2_scheme)):
    if not bearer_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentification requise.")
    try:
        return await central_auth.get_groups(bearer_token)
    except central_auth.CentralUnavailableError:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Service central indisponible.")
    except central_auth.CentralAuthError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session invalide ou expirée.")
