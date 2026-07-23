"""
Routes d'authentification JWT — EDG Connect.

Endpoints :
  POST /auth/register          Inscription (crée un compte + retourne les tokens)
  POST /auth/login             Connexion (email/matricule + mot de passe)
  POST /auth/refresh           Rafraîchissement de l'access token
  POST /auth/logout            Révocation session + access + refresh tokens
  GET  /auth/me                Profil de l'utilisateur connecté
  POST /auth/change-password   Changement de mot de passe
  POST /auth/set-password/{id} Réinitialisation admin (réservé admin)
"""
from __future__ import annotations

import asyncio
import logging
import random
import string
import uuid
from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from api.dependencies import get_db, get_current_user, require_roles, oauth2_scheme
from api.schemas.SchemaAuth import (
    LoginRequest,
    RegisterRequest,
    RefreshRequest,
    LogoutRequest,
    ChangePasswordRequest,
    SetPasswordRequest,
    TokenResponse,
    AccessTokenResponse,
)
from api.schemas.SchemaAccount import AccountResponse
from api.services import AccountService
from api.core.security import (
    create_access_token,
    create_refresh_token,
    decode_token,
    access_token_expire_seconds,
)
from api.core.token_blacklist import token_blacklist
from api.core.exceptions import UnauthorizedException, EDGException
from api.core.event_bus import event_bus, AppEvent

# ── Stockage des codes de réinitialisation (in-memory, TTL 15 min) ────────────
# { email_lower: (code, expires_at) }
_reset_codes: dict[str, tuple[str, datetime]] = {}
_reset_lock = asyncio.Lock()
_RESET_TTL = timedelta(minutes=15)


async def _create_reset_code(email: str) -> str:
    """Génère un code à 6 chiffres et le stocke avec expiry."""
    code = "".join(random.choices(string.digits, k=6))
    expires_at = datetime.now(timezone.utc).replace(tzinfo=None) + _RESET_TTL
    async with _reset_lock:
        _reset_codes[email.lower()] = (code, expires_at)
    return code


async def _check_reset_code(email: str, code: str) -> str:
    """Retourne 'valid', 'expired' ou 'invalid'."""
    async with _reset_lock:
        entry = _reset_codes.get(email.lower())
    if entry is None:
        return "invalid"
    stored_code, expires_at = entry
    if datetime.now(timezone.utc).replace(tzinfo=None) > expires_at:
        return "expired"
    if stored_code != code:
        return "invalid"
    return "valid"


async def _consume_reset_code(email: str) -> None:
    """Supprime le code après utilisation (usage unique)."""
    async with _reset_lock:
        _reset_codes.pop(email.lower(), None)


class ForgotPasswordRequest(BaseModel):
    email: str


class ResetPasswordRequest(BaseModel):
    email: str
    code: str
    new_password: str

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _svc(db: AsyncSession = Depends(get_db)) -> AccountService:
    return AccountService(db)


# ── Helper — log d'activité (best-effort : échec avalé, ne bloque pas la réponse
#    en cas d'erreur, mais reste awaited — profilage a mesuré <0.05s en pratique) ─

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


def _build_token_response(user, session_id: str, include_refresh: bool = True) -> dict:
    access = create_access_token(user.id, user.email, user.role, session_id)
    refresh = create_refresh_token(user.id, session_id) if include_refresh else ""
    return {
        "access_token": access,
        "refresh_token": refresh,
        "token_type": "bearer",
        "expires_in": access_token_expire_seconds(),
        "user": user,
    }


def _client_ip(request: Request) -> str | None:
    forwarded = request.headers.get("X-Forwarded-For")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else None


# ── Inscription ───────────────────────────────────────────────────────────────

@router.post(
    "/register",
    response_model=TokenResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Créer un compte et obtenir les tokens",
)
async def register(
    request: Request,
    body: RegisterRequest,
    db: AsyncSession = Depends(get_db),
    svc: AccountService = Depends(_svc),
):
    data = body.dict()
    user = await svc.register(data)  # force role="user" dans le service
    session_id = str(uuid.uuid4())
    await _log_auth_event(
        db, actor=user.email, actor_id=user.id, actor_role=user.role,
        action="register", target=f"account:{user.id}",
        ip_address=_client_ip(request),
    )
    return _build_token_response(user, session_id)


# ── Connexion ─────────────────────────────────────────────────────────────────

@router.post(
    "/login",
    response_model=TokenResponse,
    summary="Connexion (email/matricule + mot de passe)",
)
async def login(
    request: Request,
    body: LoginRequest,
    db: AsyncSession = Depends(get_db),
    svc: AccountService = Depends(_svc),
):
    ip = _client_ip(request)
    try:
        user = await svc.authenticate(body.identifier, body.password)
    except UnauthorizedException as exc:
        await _log_auth_event(
            db, actor=body.identifier, actor_id=None, actor_role="unknown",
            action="login_failed", target="auth",
            ip_address=ip, log_status="error",
        )
        raise  # edg_exception_handler retourne error_code structuré (ex: ACCOUNT_DISABLED)

    session_id = str(uuid.uuid4())

    await _log_auth_event(
        db, actor=user.email, actor_id=user.id, actor_role=user.role,
        action="login", target=f"account:{user.id}",
        ip_address=ip,
    )

    return _build_token_response(user, session_id)


# ── Rafraîchissement du token ─────────────────────────────────────────────────

@router.post(
    "/refresh",
    response_model=AccessTokenResponse,
    summary="Obtenir un nouveau access token depuis le refresh token",
)
async def refresh_token(
    body: RefreshRequest,
    db: AsyncSession = Depends(get_db),
):
    try:
        payload = decode_token(body.refresh_token)
    except UnauthorizedException as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=exc.message,
            headers={"WWW-Authenticate": "Bearer"},
        )

    if payload.get("type") != "refresh":
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Token invalide : ce n'est pas un refresh token.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    jti = payload.get("jti", "")
    if await token_blacklist.is_revoked(jti):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Refresh token révoqué. Veuillez vous reconnecter.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    session_id = payload.get("session_id", "")
    account_id = int(payload.get("sub", 0))
    from api.repositories import AccountRepository
    user = await AccountRepository(db).get_by_id(account_id)
    if user is None or not user.status or user.deleted_at is not None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Compte introuvable ou désactivé.",
            headers={"WWW-Authenticate": "Bearer"},
        )

    new_access = create_access_token(user.id, user.email, user.role, session_id)
    return {
        "access_token": new_access,
        "token_type": "bearer",
        "expires_in": access_token_expire_seconds(),
    }


# ── Déconnexion ───────────────────────────────────────────────────────────────

@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Déconnexion — révoque la session + access token + refresh token",
)
async def logout(
    request: Request,
    body: LogoutRequest,
    db: AsyncSession = Depends(get_db),
    bearer_token: str | None = Depends(oauth2_scheme),
):
    """
    H-03 — Révoque les deux tokens :
      - refresh_token (body, obligatoire)
      - access_token (body optionnel OU Authorization header)
    H-08 — Révoque la session en base.
    """
    session_id_to_revoke: str | None = None
    actor_info: tuple[str, int | None, str] = ("anonymous", None, "unknown")

    # 1. Révoquer le refresh token
    try:
        ref_payload = decode_token(body.refresh_token)
        ref_jti = ref_payload.get("jti", "")
        session_id_to_revoke = ref_payload.get("session_id")
        exp_ts = ref_payload.get("exp")
        exp_dt = (
            datetime.fromtimestamp(exp_ts, tz=timezone.utc).replace(tzinfo=None)
            if exp_ts else None
        )
        if ref_jti:
            await token_blacklist.revoke(ref_jti, exp_dt)
    except UnauthorizedException:
        pass  # refresh token déjà invalide — acceptable

    # 2. Révoquer l'access token (depuis le body ou le header Authorization)
    access_raw = body.access_token or bearer_token
    if access_raw:
        try:
            acc_payload = decode_token(access_raw)
            acc_jti = acc_payload.get("jti", "")
            acc_exp_ts = acc_payload.get("exp")
            acc_exp_dt = (
                datetime.fromtimestamp(acc_exp_ts, tz=timezone.utc).replace(tzinfo=None)
                if acc_exp_ts else None
            )
            if acc_jti:
                await token_blacklist.revoke(acc_jti, acc_exp_dt)
            # Si pas de session_id dans le refresh, essayer l'access
            if not session_id_to_revoke:
                session_id_to_revoke = acc_payload.get("session_id")
            sub = acc_payload.get("sub", "")
            actor_info = (
                acc_payload.get("email", sub),
                int(sub) if sub else None,
                acc_payload.get("role", "unknown"),
            )
        except UnauthorizedException:
            pass

    # 3. Log
    await _log_auth_event(
        db,
        actor=actor_info[0],
        actor_id=actor_info[1],
        actor_role=actor_info[2],
        action="logout",
        target="auth",
        ip_address=_client_ip(request),
    )


# ── Profil courant ────────────────────────────────────────────────────────────

@router.get(
    "/me",
    response_model=AccountResponse,
    summary="Profil de l'utilisateur connecté",
)
async def get_me(current_user=Depends(get_current_user)):
    return current_user


# ── Changement de mot de passe ────────────────────────────────────────────────

@router.post(
    "/change-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Changer son propre mot de passe",
)
async def change_password(
    request: Request,
    body: ChangePasswordRequest,
    db: AsyncSession = Depends(get_db),
    current_user=Depends(get_current_user),
    svc: AccountService = Depends(_svc),
):
    try:
        await svc.change_password(
            current_user.id,
            body.current_password,
            body.new_password,
        )
    except UnauthorizedException as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=exc.message,
        )

    await _log_auth_event(
        db,
        actor=current_user.email,
        actor_id=current_user.id,
        actor_role=current_user.role,
        action="change_password",
        target=f"account:{current_user.id}",
        ip_address=_client_ip(request),
    )


# ── Réinitialisation admin ────────────────────────────────────────────────────

@router.post(
    "/set-password/{account_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Admin — définir/réinitialiser le mot de passe d'un compte",
    dependencies=[Depends(require_roles("admin"))],
)
async def admin_set_password(
    account_id: int,
    body: SetPasswordRequest,
    svc: AccountService = Depends(_svc),
):
    await svc.set_password(account_id, body.password)


# ── Mot de passe oublié ───────────────────────────────────────────────────────

@router.post(
    "/forgot-password",
    summary="Demander un code de réinitialisation du mot de passe",
)
async def forgot_password(
    body: ForgotPasswordRequest,
    svc: AccountService = Depends(_svc),
):
    """
    Génère un code à 6 chiffres (TTL 15 min) et le stocke.
    En développement : retourne le code directement dans la réponse.
    En production : envoie un email (TODO: brancher SMTP) et ne retourne pas le code.
    Volontairement silencieux si l'email n'existe pas (anti-énumération).
    """
    from api.configs.Environment import get_environment
    env = get_environment()

    try:
        user = await svc.get_by_email(body.email.strip().lower())
    except Exception:
        # Anti-énumération : ne pas révéler l'existence du compte
        if env.APP_ENV != "production":
            return {"sent": False, "dev_code": None}
        return {"sent": False}

    code = await _create_reset_code(body.email.strip().lower())
    logger.info(
        "Password reset requested for %s — code generated (TTL 15 min)", user.email
    )

    # TODO prod: envoyer l'email via SMTP
    # await send_password_reset_email(user.email, user.name, code)

    if env.APP_ENV != "production":
        # Dev : code renvoyé directement (affiché dans l'UI)
        return {"sent": True, "dev_code": code}
    return {"sent": True}


# ── Vérification biométrique (reconnaissance faciale DeepFace) ───────────────

class BiometricVerifyRequest(BaseModel):
    image: str       # base64 data URL ou base64 pur — image webcam
    identifier: str  # email de l'administrateur


@router.post(
    "/biometric-verify",
    summary="Vérification biométrique par reconnaissance faciale (ArcFace / InsightFace)",
)
async def biometric_verify(
    request: Request,
    body: BiometricVerifyRequest,
    db: AsyncSession = Depends(get_db),
):
    from api.services.ServiceBiometric import (
        verify_faces,
        load_reference_image,
        SpoofDetectedError,
    )
    from api.repositories.RepositoryAccount import AccountRepository

    ip = _client_ip(request)
    account_repo = AccountRepository(db)

    # 1. Récupérer le compte administrateur
    user = await account_repo.find_by_email(body.identifier.strip().lower())
    if not user or user.role != "admin" or user.account_status != "active":
        return {"match": False, "confidence": 0.0}

    # 2. Vérifier la présence d'une photo de référence
    if not user.avatar_url:
        logger.warning(
            "Biometric: aucune photo de référence pour l'admin %s", user.email
        )
        return {"match": False, "confidence": 0.0, "error": "no_reference_photo"}

    # 3. Charger la photo de référence
    ref_b64 = await asyncio.to_thread(load_reference_image, user.avatar_url)
    if not ref_b64:
        logger.error("Biometric: impossible de charger la photo de référence pour %s", user.email)
        return {"match": False, "confidence": 0.0}

    # 4. Préparer l'image en direct (strip data URL prefix si présent)
    live_b64 = body.image
    if "," in live_b64:
        live_b64 = live_b64.split(",", 1)[1]

    # 5. Vérification faciale
    match = False
    confidence = 0.0
    spoof_detected = False

    try:
        match, confidence = await verify_faces(live_b64, ref_b64)
    except SpoofDetectedError:
        spoof_detected = True
        logger.warning("Biometric: tentative de fraude anti-spoofing pour %s", user.email)
    except ValueError as exc:
        logger.warning("Biometric: visage non détecté pour %s — %s", user.email, exc)
    except Exception as exc:
        logger.error("Biometric: erreur inattendue pour %s — %s", user.email, exc)

    # 6. Journalisation d'audit
    action = (
        "biometric_spoof_attempt" if spoof_detected
        else ("biometric_auth_success" if match else "biometric_auth_failed")
    )
    await _log_auth_event(
        db,
        actor=user.email,
        actor_id=user.id,
        actor_role=user.role,
        action=action,
        target=f"account:{user.id}",
        ip_address=ip,
        log_status="success" if match else "error",
    )

    # 7. Accès refusé
    if not match:
        return {
            "match": False,
            "confidence": confidence,
            **({"spoof": True} if spoof_detected else {}),
        }

    # 8. Accès accordé — émettre tokens
    session_id = str(uuid.uuid4())
    access = create_access_token(user.id, user.email, user.role, session_id)
    refresh = create_refresh_token(user.id, session_id)

    logger.info(
        "Biometric auth SUCCESS: user=%s confidence=%.1f%%", user.email, confidence
    )

    return {
        "match": True,
        "confidence": confidence,
        "access_token": access,
        "refresh_token": refresh,
        "expires_in": access_token_expire_seconds(),
        "user": {
            "id": str(user.id),
            "name": user.name,
            "email": user.email,
            "role": user.role,
            "avatar": user.avatar_url,
            "unity_id": str(user.unity_id) if user.unity_id else None,
        },
    }


# ── Rapport d'incident de sécurité ────────────────────────────────────────────

class SecurityIncidentRequest(BaseModel):
    identifier: str
    captured_image: str
    timestamp: str
    user_agent: str
    browser: str | None = None
    os_info: str | None = None
    device_type: str | None = None
    location_approx: str | None = None
    attempt_count: int = 1


@router.post(
    "/security-incident",
    status_code=status.HTTP_201_CREATED,
    summary="Signaler une tentative d'accès non autorisée (photo + métadonnées)",
)
async def report_security_incident(
    request: Request,
    body: SecurityIncidentRequest,
    db: AsyncSession = Depends(get_db),
):
    from api.services.ServiceSecurityIncident import SecurityIncidentService
    svc = SecurityIncidentService(db)
    await svc.create_incident(
        identifier=body.identifier,
        captured_image=body.captured_image,
        timestamp=body.timestamp,
        user_agent=body.user_agent,
        ip_address=_client_ip(request),
        browser=body.browser,
        os_info=body.os_info,
        device_type=body.device_type,
        location_approx=body.location_approx,
        attempt_count=body.attempt_count,
    )
    return {"recorded": True}


@router.post(
    "/reset-password",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Réinitialiser le mot de passe avec le code reçu par email",
)
async def reset_password(
    body: ResetPasswordRequest,
    svc: AccountService = Depends(_svc),
):
    """
    Vérifie le code de réinitialisation et met à jour le mot de passe.
    Le code est à usage unique — il est supprimé après utilisation.
    """
    if len(body.new_password) < 6:
        raise EDGException(
            "Le mot de passe doit contenir au moins 6 caractères.",
            error_code="VALIDATION_ERROR",
            status_code=422,
        )

    result = await _check_reset_code(body.email.strip().lower(), body.code.strip())

    if result == "expired":
        raise EDGException(
            "Ce code de réinitialisation a expiré. Recommencez la procédure.",
            error_code="RESET_CODE_EXPIRED",
            status_code=422,
        )

    if result == "invalid":
        raise EDGException(
            "Code invalide ou déjà utilisé. Recommencez la procédure.",
            error_code="RESET_CODE_INVALID",
            status_code=422,
        )

    try:
        user = await svc.get_by_email(body.email.strip().lower())
    except Exception:
        raise EDGException(
            "Code invalide ou déjà utilisé.",
            error_code="RESET_CODE_INVALID",
            status_code=422,
        )

    await svc.set_password(user.id, body.new_password)
    await _consume_reset_code(body.email.strip().lower())
    logger.info("Password reset completed for user id=%s", user.id)
