"""
Routes d'authentification — plateforme centrale manager-user.

Endpoints :
  POST /auth/register          Inscription publique (rôle "user" forcé) via le central
  POST /auth/forgot-password   Étape 1 — envoi d'un code de vérification par email (OTP local)
  POST /auth/reset-password    Étape 3 — vérification du code + reset central du mot de passe
  POST /auth/login             Connexion (email/matricule + mot de passe) via le central
                                Retourne TokenResponse si un compte local existe déjà
                                ou a pu être auto-provisionné (groupe support central
                                déjà présent), sinon ConsentRequiredResponse (200) —
                                voir dependencies.py::resolve_or_provision_login_account.
  POST /auth/consent/accept    Rattachement après consentement explicite — utilisateur
                                central authentifié mais sans compte local NI groupe
                                support (suite d'un login ayant renvoyé needs_consent).
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
from typing import NoReturn, Optional, Union

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.core import central_auth, mailer
from api.core.exceptions import ValidationException
from api.dependencies import (
    get_db,
    get_current_user,
    get_current_user_optional,
    oauth2_scheme,
    resolve_or_provision_login_account,
    _ensure_account_active,
    _sync_role_from_groups,
    _fetch_scopes_and_groups,
    invalidate_central_auth_cache,
)
from api.repositories import AccountRepository
from api.schemas.SchemaAuth import (
    RegisterRequest,
    LoginRequest,
    ForgotPasswordRequest,
    ResetPasswordRequest,
    ChangePasswordRequest,
    RefreshRequest,
    LogoutRequest,
    ConsentAcceptRequest,
    TokenResponse,
    ConsentRequiredResponse,
    AccessTokenResponse,
)
from api.schemas.SchemaAccount import AccountResponse
from api.services import AccountService

logger = logging.getLogger(__name__)

_RESET_CODE_TTL_MINUTES = 15
_RESET_CODE_MAX_ATTEMPTS = 5

# Message unique lorsque la plateforme centrale ne répond pas. L'origine du
# problème est nommée explicitement : l'authentification lui est entièrement
# déléguée, et sans cette mention l'utilisateur comme l'exploitant croient à une
# panne d'EDG Connect et cherchent au mauvais endroit. Formulé sans jargon :
# aucun code, aucune URL, aucun détail technique.
_CENTRAL_DOWN_MESSAGE = (
    "La plateforme centrale d'authentification ne répond pas. "
    "Réessayez dans quelques instants."
)
# Version courante des CGU/politique de confidentialité présentées à l'écran de
# consentement (frontend routes/legal.terms.tsx, legal.privacy.tsx). À
# incrémenter si le texte légal change de façon substantielle — permet de
# ré-solliciter le consentement des comptes déjà rattachés si besoin un jour.
_CONSENT_VERSION = "1.0"

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


# ── TEMPORAIRE (2026-08) — diagnostic public "CLIENT_APP_CODE/SECRET rejetés" ──
# Investigation d'un rejet du couple client_code/client_secret par le central
# alors que les valeurs sont censées être correctes — volontairement PUBLIC
# (aucune authentification), pour pouvoir tester avant même qu'un login central
# fonctionne. Ne renvoie jamais le secret utilisé, seulement le client_code et
# la réponse brute (code + corps) de la plateforme centrale.
# ⚠️ RAPPEL : à supprimer (cette route + central_auth.debug_source_token_exchange)
# une fois le diagnostic terminé — ne doit jamais rester en production.
class _DebugSourceTokenBody(BaseModel):
    client_code: Optional[str] = None
    client_secret: Optional[str] = None


@router.post(
    "/debug/source-token",
    summary="[TEMPORAIRE — À SUPPRIMER] Diagnostic brut de l'échange source_token avec le central",
)
async def debug_source_token(body: _DebugSourceTokenBody = _DebugSourceTokenBody()):
    return await central_auth.debug_source_token_exchange(body.client_code, body.client_secret)


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
    response_model=Union[TokenResponse, ConsentRequiredResponse],
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
    except central_auth.CentralValidationError as exc:
        # La plateforme centrale refuse la requête sur le fond (politique de mot
        # de passe, format…). Son message est relayé tel quel : c'est elle qui
        # connaît sa règle, la paraphraser la trahirait.
        logger.warning("central_auth: requête refusée par le central (%s)", exc)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(exc),
        )
    except central_auth.CentralInvalidClientCredentials as exc:
        # Erreur de CONFIGURATION du serveur (CLIENT_APP_CODE/SECRET), pas une
        # panne : l'annoncer comme une indisponibilité enverrait l'utilisateur —
        # et l'exploitant — chercher au mauvais endroit.
        logger.error("central_auth: identifiants applicatifs rejetés (%s)", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "La configuration d'accès à la plateforme centrale est refusée. "
                "Contactez l'administrateur système."
            ),
        )
    except central_auth.CentralUnavailableError as exc:
        logger.error("central_auth: échec login (%s)", exc)
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_CENTRAL_DOWN_MESSAGE,
        )

    bearer_token = tokens["bearer_token"]
    account, scopes = await resolve_or_provision_login_account(bearer_token, db)

    if account is None:
        # Authentifié par le central, mais aucun groupe support de cette
        # application (voir dependencies.py::resolve_or_provision_login_account)
        # → rattachement soumis à consentement explicite, pas de compte créé ici.
        try:
            profile = await central_auth.get_profile(bearer_token)
        except central_auth.CentralAuthError:
            profile = {}
        identity = central_auth.parse_profile_identity(profile)

        await _log_auth_event(
            db, actor=scopes.get("email", email), actor_id=None, actor_role="unknown",
            action="login_needs_consent", target="auth", ip_address=ip,
        )
        return ConsentRequiredResponse(
            access_token=bearer_token,
            refresh_token=tokens.get("refresh_token", ""),
            expires_in=tokens.get("expires_in", 0),
            email=scopes.get("email", email),
            suggested_name=identity["name"],
            suggested_firstname=identity["firstname"],
            suggested_phone=identity["phone"],
            consent_version=_CONSENT_VERSION,
        )

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


# ── Consentement (rattachement sans groupe support central) ──────────────────

@router.post(
    "/consent/accept",
    response_model=TokenResponse,
    summary="Rattachement après consentement — utilisateur central sans groupe support",
)
async def accept_consent(
    request: Request,
    body: ConsentAcceptRequest,
    db: AsyncSession = Depends(get_db),
    bearer_token: str | None = Depends(oauth2_scheme),
):
    if not bearer_token:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentification requise.")

    # Re-vérification complète côté central au moment de l'acceptation — jamais
    # confiance dans ce que le frontend a affiché sur l'écran de consentement
    # (email/groupes ont pu changer depuis l'appel /auth/login initial).
    scopes, groups = await _fetch_scopes_and_groups(bearer_token)
    central_user_id = scopes.get("user_id")
    if not central_user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Session invalide ou expirée.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    account_repo = AccountRepository(db)
    account = await account_repo.find_by_central_user_id(central_user_id)

    if account is not None:
        # Idempotence — double soumission / retry réseau du même accept, ou
        # l'utilisateur a déjà été rattaché entretemps (ex. auto-provisionné par
        # une autre requête concurrente). On ne recrée rien, on synchronise juste.
        account = await _sync_role_from_groups(account, groups, account_repo)
    else:
        mapped_role = central_auth.role_from_groups(groups)
        email = (scopes.get("email") or "").strip().lower()

        try:
            profile = await central_auth.get_profile(bearer_token)
        except central_auth.CentralAuthError:
            profile = {}
        central_uuid = central_auth.parse_profile_identity(profile)["uuid"]

        if not mapped_role:
            # Cas normal du flux consentement : aucun groupe support pour l'instant
            # → rattachement au groupe collaborateur-support, rôle local "user".
            mapped_role = "user"
            if central_uuid:
                machine_token = await central_auth.get_machine_token()
                await central_auth.add_group_membership(central_uuid, "collaborateur-support", machine_token)
        # Si mapped_role est déjà renseigné (l'utilisateur a été ajouté à un
        # groupe support entre le login et cette acceptation), on ne touche pas
        # à ses groupes centraux — juste au miroir local, avec le rôle réel.

        account = await AccountService(db).provision_from_central(
            central_user_id=central_user_id,
            central_user_uuid=central_uuid,
            email=email,
            name=body.name,
            firstname=body.firstname,
            phone=body.phone,
            role=mapped_role,
            consent_accepted_at=datetime.utcnow(),
            consent_version=body.consent_version,
        )
        await central_auth.log_central_event(
            bearer_token, object_id=str(account.id), action="consent_accept", status="success",
            message=f"Rattachement après consentement : {account.email}",
        )

    _ensure_account_active(account)
    await _log_auth_event(
        db, actor=account.email, actor_id=account.id, actor_role=account.role,
        action="consent_accept", target=f"account:{account.id}", ip_address=_client_ip(request),
    )

    return {
        "access_token": bearer_token,
        "refresh_token": body.refresh_token,
        "token_type": "bearer",
        "expires_in": body.expires_in,
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
            detail="Session expirée côté plateforme centrale. Veuillez vous reconnecter.",
            headers={"WWW-Authenticate": "Bearer"},
        )
    except central_auth.CentralUnavailableError:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=_CENTRAL_DOWN_MESSAGE,
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
    # Purge du cache des scopes/groupes : sans ça le token resterait accepté
    # jusqu'à l'expiration de son entrée alors que l'utilisateur se déconnecte.
    if bearer_token:
        invalidate_central_auth_cache(bearer_token)

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

@router.post(
    "/change-password",
    summary="Changer son mot de passe depuis son espace (utilisateur connecté)",
)
async def change_password_route(
    request: Request,
    body: ChangePasswordRequest,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """Changement de mot de passe en self-service, depuis la page Profil.

    Se distingue de /forgot-password + /reset-password : l'utilisateur etant deja
    authentifie, aucun email ni code OTP n'est envoye. Le mot de passe n'existe
    que sur la plateforme centrale — l'ecriture y est donc immediatement valable
    partout, il n'y a rien a synchroniser localement.
    """
    if not current_user.central_user_uuid:
        raise ValidationException(
            "Ce compte n'est pas rattaché à la plateforme centrale — "
            "contactez un administrateur.",
            error_code="ACCOUNT_NOT_CENTRAL_LINKED",
        )

    machine_token = await central_auth.get_machine_token()
    await central_auth.reset_central_password(
        current_user.central_user_uuid, machine_token, new_password=body.new_password,
    )

    await _log_auth_event(
        db, actor=current_user.email, actor_id=current_user.id,
        actor_role=current_user.role, action="change_password",
        target=f"account:{current_user.id}", ip_address=_client_ip(request),
    )
    return {"changed": True}


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
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=_CENTRAL_DOWN_MESSAGE)
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
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=_CENTRAL_DOWN_MESSAGE)
    except central_auth.CentralAuthError:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Session invalide ou expirée.")
