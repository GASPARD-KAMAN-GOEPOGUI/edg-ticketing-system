"""
Client de la plateforme centrale d'authentification manager-user.

Flux : source-token -> login, refresh, scopes, groupes, audit centralisé.
Voir backend/README-integration-plateforme-centrale/README-integration-plateforme-centrale.md.

httpx.AsyncClient(trust_env=False) — évite l'event loop bloquant (le README
utilise httpx.Client synchrone dans son exemple, ce backend est 100% async).
"""
from __future__ import annotations

import logging
from typing import Any, Optional

import httpx

from api.configs.Environment import get_environment

logger = logging.getLogger(__name__)

_MASKED_FIELDS = {
    "password", "client_secret", "secret", "token",
    "source_token", "bearer_token", "refresh_token", "authorization",
}

GROUP_ROLE_PRIORITY: list[tuple[str, str]] = [
    ("admin-support", "admin"),
    ("qualify-support", "agent-support"),
    ("collaborateur-support", "user"),
]

_DEFAULT_GROUP_CODENAME = "collaborateur-support"
_DEFAULT_RESET_PASSWORD = "EDG2026@"


class CentralAuthError(Exception):
    """Erreur générique d'échange avec la plateforme centrale."""


class CentralUnavailableError(CentralAuthError):
    """Réseau/DNS/timeout/5xx central, ou variables centrales non configurées."""


class CentralInvalidClientCredentials(CentralAuthError):
    """CLIENT_APP_CODE/CLIENT_APP_SECRET rejetés — erreur de configuration serveur."""


class CentralInvalidCredentials(CentralAuthError):
    """email/mot de passe utilisateur rejetés par le central."""


class CentralInvalidSourceToken(CentralAuthError):
    """source_token invalide — le retry avec un nouveau token est géré par central_login()."""


class CentralIdentityConflict(CentralAuthError):
    """status == "identity_conflict" sur POST /v1/client-app-users/group-membership."""


class CentralValidationError(CentralAuthError):
    """400/422 renvoyé par le central (ex. politique de mot de passe) — message relayé."""


class CentralPermissionDenied(CentralAuthError):
    """401/403 sur un appel authentifié par le bearer de l'ACTEUR (pas le token
    machine) — l'utilisateur est bien authentifié mais son groupe central n'a pas
    le scope requis pour cette action (ex. delete_central_account -> scope
    "user.delete" absent des scopes du groupe). À ne pas confondre avec
    CentralInvalidClientCredentials (token machine/app rejeté)."""


def _client_kwargs() -> dict[str, Any]:
    env = get_environment()
    if not env.CENTRAL_AUTH_BASE_URL:
        raise CentralUnavailableError("CENTRAL_AUTH_BASE_URL non configurée.")
    return {
        "base_url": env.CENTRAL_AUTH_BASE_URL,
        "timeout": env.HTTP_TIMEOUT_MS / 1000,
        "trust_env": False,
    }


def _mask(payload: dict[str, Any]) -> dict[str, Any]:
    return {
        key: ("***" if key.lower() in _MASKED_FIELDS else value)
        for key, value in payload.items()
    }


async def get_source_token() -> str:
    env = get_environment()
    if not env.CLIENT_APP_CODE or not env.CLIENT_APP_SECRET:
        raise CentralUnavailableError("CLIENT_APP_CODE/CLIENT_APP_SECRET non configurés.")
    try:
        async with httpx.AsyncClient(**_client_kwargs()) as client:
            response = await client.post(
                "/v1/client-app-auth/source-token",
                json={"client_code": env.CLIENT_APP_CODE, "client_secret": env.CLIENT_APP_SECRET},
            )
    except httpx.HTTPError as exc:
        raise CentralUnavailableError(f"Service d'authentification central indisponible : {exc}") from exc

    if response.status_code in (401, 403):
        raise CentralInvalidClientCredentials("CLIENT_APP_CODE/CLIENT_APP_SECRET rejetés par le central.")
    if response.status_code >= 500:
        raise CentralUnavailableError(f"Le central a répondu {response.status_code}.")
    response.raise_for_status()
    return response.json()["source_token"]


async def get_machine_token() -> str:
    """POST /v1/client-app-auth/token — token machine pour les opérations d'administration
    de comptes (update/activate/deactivate/reset-password/groupes). Pas de cache : refetch
    à chaque invocation de méthode de service (opérations admin peu fréquentes)."""
    env = get_environment()
    if not env.CLIENT_APP_CODE or not env.CLIENT_APP_SECRET:
        raise CentralUnavailableError("CLIENT_APP_CODE/CLIENT_APP_SECRET non configurés.")
    try:
        async with httpx.AsyncClient(**_client_kwargs()) as client:
            response = await client.post(
                "/v1/client-app-auth/token",
                json={"client_app_code": env.CLIENT_APP_CODE, "client_app_secret": env.CLIENT_APP_SECRET},
            )
    except httpx.HTTPError as exc:
        raise CentralUnavailableError(f"Service d'authentification central indisponible : {exc}") from exc

    if response.status_code in (401, 403):
        raise CentralInvalidClientCredentials("CLIENT_APP_CODE/CLIENT_APP_SECRET rejetés par le central.")
    if response.status_code >= 500:
        raise CentralUnavailableError(f"Le central a répondu {response.status_code}.")
    response.raise_for_status()
    return response.json()["access_token"]


def _normalize_token_response(data: dict[str, Any]) -> dict[str, Any]:
    bearer = data.get("bearer_token") or data.get("access_token")
    return {**data, "bearer_token": bearer}


def _is_invalid_source_token(response: httpx.Response) -> bool:
    """Le central signale un source_token invalide/expiré en 401 OU 403 (observé en
    prod : 403 {"detail":{"code":"invalid_source_token",...}}) — à distinguer d'un
    401/403 pour identifiants utilisateur invalides ({"detail":"Invalid email or
    password"})."""
    if response.status_code not in (401, 403):
        return False
    try:
        detail = response.json().get("detail")
    except Exception:
        return "source_token" in response.text.lower() or "source token" in response.text.lower()
    if isinstance(detail, dict):
        if detail.get("code") == "invalid_source_token":
            return True
        return "source token" in str(detail.get("message", "")).lower()
    return "source" in str(detail).lower() and "token" in str(detail).lower()


async def central_login(email: str, password: str) -> dict[str, Any]:
    source_token = await get_source_token()
    payload = {"email": email, "password": password, "source_token": source_token}

    async def _attempt(token: str) -> httpx.Response:
        async with httpx.AsyncClient(**_client_kwargs()) as client:
            return await client.post("/v1/auth/login", json={**payload, "source_token": token})

    try:
        response = await _attempt(source_token)
    except httpx.HTTPError as exc:
        raise CentralUnavailableError(f"Service d'authentification central indisponible : {exc}") from exc

    if _is_invalid_source_token(response):
        source_token = await get_source_token()
        try:
            response = await _attempt(source_token)
        except httpx.HTTPError as exc:
            raise CentralUnavailableError(f"Service d'authentification central indisponible : {exc}") from exc

    # Identifiants utilisateur invalides : observé en 403 en prod ("Invalid email or
    # password"), 401 gardé pour compatibilité avec la doc générique du README.
    if response.status_code in (401, 403):
        raise CentralInvalidCredentials("Identifiant ou mot de passe incorrect.")
    if response.status_code >= 500:
        raise CentralUnavailableError(f"Le central a répondu {response.status_code}.")
    response.raise_for_status()
    return _normalize_token_response(response.json())


async def central_refresh(refresh_token: str) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(**_client_kwargs()) as client:
            response = await client.post("/v1/auth/refresh", json={"refresh_token": refresh_token})
    except httpx.HTTPError as exc:
        raise CentralUnavailableError(f"Service d'authentification central indisponible : {exc}") from exc

    if response.status_code == 401:
        raise CentralInvalidCredentials("Session expirée. Veuillez vous reconnecter.")
    if response.status_code >= 500:
        raise CentralUnavailableError(f"Le central a répondu {response.status_code}.")
    response.raise_for_status()
    return _normalize_token_response(response.json())


async def get_scopes(bearer_token: str) -> dict[str, Any]:
    try:
        async with httpx.AsyncClient(**_client_kwargs()) as client:
            response = await client.get(
                "/v1/auth/me/scopes",
                headers={"Authorization": f"Bearer {bearer_token}"},
            )
    except httpx.HTTPError as exc:
        raise CentralUnavailableError(f"Service d'authentification central indisponible : {exc}") from exc

    if response.status_code in (401, 403):
        raise CentralInvalidCredentials("Session invalide ou expirée.")
    if response.status_code >= 500:
        raise CentralUnavailableError(f"Le central a répondu {response.status_code}.")
    response.raise_for_status()
    return response.json()


async def get_groups(bearer_token: str) -> list[dict[str, Any]]:
    try:
        async with httpx.AsyncClient(**_client_kwargs()) as client:
            response = await client.get(
                "/api/me/groups",
                headers={"Authorization": f"Bearer {bearer_token}"},
            )
    except httpx.HTTPError as exc:
        raise CentralUnavailableError(f"Service d'authentification central indisponible : {exc}") from exc

    if response.status_code in (401, 403):
        raise CentralInvalidCredentials("Session invalide ou expirée.")
    if response.status_code >= 500:
        raise CentralUnavailableError(f"Le central a répondu {response.status_code}.")
    response.raise_for_status()
    return response.json()


def role_from_groups(groups: list[dict[str, Any]]) -> Optional[str]:
    """Mappe les groupes centraux actifs vers un rôle EDG Connect (priorité admin > agent-support > user)."""
    active = {
        (group.get("codename") or "").strip().lower()
        for group in groups
        if group.get("is_activated") is not False
    }
    for codename, role in GROUP_ROLE_PRIORITY:
        if codename in active:
            return role
    return None


def group_for_role(role: str) -> str:
    """
    Inverse de GROUP_ROLE_PRIORITY : rôle local EDG Connect -> groupe central.
    Rôles sans groupe central dédié (chief-service, chief-departement, director,
    public) retombent sur "collaborateur-support" — établit une identité centrale
    et une capacité d'authentification de base, sans jamais influencer le rôle
    LOCAL stocké (voir dependencies.py _ROLE_SYNC_SPACE, qui ignore ces rôles).
    """
    from api.core.rbac import normalize_role

    normalized = normalize_role(role)
    for codename, mapped_role in GROUP_ROLE_PRIORITY:
        if mapped_role == normalized:
            return codename
    return _DEFAULT_GROUP_CODENAME


def _raise_for_mutation_status(response: httpx.Response) -> None:
    """Branchement de statut commun aux appels de mutation de compte (machine token)."""
    if response.status_code in (401, 403):
        raise CentralInvalidClientCredentials("Token machine rejeté par le central.")
    if response.status_code in (400, 422):
        try:
            message = response.json().get("message")
        except Exception:
            message = None
        raise CentralValidationError(message or "Requête rejetée par le central.")
    if response.status_code >= 500:
        raise CentralUnavailableError(f"Le central a répondu {response.status_code}.")
    response.raise_for_status()


async def create_central_account(
    *, group_codename: str, email: str, phone: str, firstname: str, last_name: str,
    password: str, machine_token: str,
) -> dict[str, Any]:
    """POST /v1/client-app-users/group-membership — authentifié par token machine.
    Le README générique (Link Hub) décrit cet appel comme public, sans bearer — ce
    n'est pas le cas pour cette instance manager-user, qui exige le token machine
    même pour la création de compte."""
    payload = {
        "group_codename": group_codename,
        "email": email,
        "phone": phone,
        "name": firstname,
        "last_name": last_name,
        "password": password,
    }
    try:
        async with httpx.AsyncClient(**_client_kwargs()) as client:
            response = await client.post(
                "/v1/client-app-users/group-membership",
                json=payload,
                headers={"Authorization": f"Bearer {machine_token}"},
            )
    except httpx.HTTPError as exc:
        raise CentralUnavailableError(f"Service d'authentification central indisponible : {exc}") from exc

    if response.status_code in (401, 403):
        raise CentralInvalidClientCredentials("Token machine rejeté par le central.")
    if response.status_code in (400, 422):
        try:
            message = response.json().get("message")
        except Exception:
            message = None
        raise CentralValidationError(message or "Requête rejetée par le central.")
    if response.status_code >= 500:
        raise CentralUnavailableError(f"Le central a répondu {response.status_code}.")
    response.raise_for_status()

    data = response.json()
    if data.get("status") == "identity_conflict":
        raise CentralIdentityConflict(data.get("message") or "Conflit d'identité détecté par la plateforme centrale.")
    return data


async def update_central_account(
    user_uuid: str, *, email: str, phone: str, firstname: str, last_name: str, machine_token: str,
) -> dict[str, Any]:
    """PUT /v1/client-app-users/{user_uuid} — token machine."""
    payload = {"email": email, "phone": phone, "name": firstname, "last_name": last_name}
    try:
        async with httpx.AsyncClient(**_client_kwargs()) as client:
            response = await client.put(
                f"/v1/client-app-users/{user_uuid}",
                json=payload,
                headers={"Authorization": f"Bearer {machine_token}"},
            )
    except httpx.HTTPError as exc:
        raise CentralUnavailableError(f"Service d'authentification central indisponible : {exc}") from exc
    _raise_for_mutation_status(response)
    return response.json()


async def add_group_membership(user_uuid: str, group_codename: str, machine_token: str) -> None:
    """PUT /v1/client-app-users/group-membership — token machine."""
    try:
        async with httpx.AsyncClient(**_client_kwargs()) as client:
            response = await client.put(
                "/v1/client-app-users/group-membership",
                json={"user_uuid": user_uuid, "group_codename": group_codename},
                headers={"Authorization": f"Bearer {machine_token}"},
            )
    except httpx.HTTPError as exc:
        raise CentralUnavailableError(f"Service d'authentification central indisponible : {exc}") from exc
    _raise_for_mutation_status(response)


async def remove_group_membership(user_uuid: str, group_codename: str, machine_token: str) -> None:
    """DELETE /v1/client-app-users/group-membership — token machine, corps JSON."""
    try:
        async with httpx.AsyncClient(**_client_kwargs()) as client:
            response = await client.request(
                "DELETE",
                "/v1/client-app-users/group-membership",
                json={"user_uuid": user_uuid, "group_codename": group_codename},
                headers={"Authorization": f"Bearer {machine_token}"},
            )
    except httpx.HTTPError as exc:
        raise CentralUnavailableError(f"Service d'authentification central indisponible : {exc}") from exc
    _raise_for_mutation_status(response)


async def activate_central_account(user_uuid: str, machine_token: str) -> None:
    """POST /v1/client-app-users/{user_uuid}/activate — token machine, corps {}."""
    try:
        async with httpx.AsyncClient(**_client_kwargs()) as client:
            response = await client.post(
                f"/v1/client-app-users/{user_uuid}/activate",
                json={},
                headers={"Authorization": f"Bearer {machine_token}"},
            )
    except httpx.HTTPError as exc:
        raise CentralUnavailableError(f"Service d'authentification central indisponible : {exc}") from exc
    _raise_for_mutation_status(response)


async def deactivate_central_account(user_uuid: str, machine_token: str) -> None:
    """POST /v1/client-app-users/{user_uuid}/deactivate — token machine, corps {}."""
    try:
        async with httpx.AsyncClient(**_client_kwargs()) as client:
            response = await client.post(
                f"/v1/client-app-users/{user_uuid}/deactivate",
                json={},
                headers={"Authorization": f"Bearer {machine_token}"},
            )
    except httpx.HTTPError as exc:
        raise CentralUnavailableError(f"Service d'authentification central indisponible : {exc}") from exc
    _raise_for_mutation_status(response)


async def reset_central_password(
    user_uuid: str, machine_token: str, new_password: str | None = None
) -> str:
    """POST /v1/client-app-users/{user_uuid}/reset-password — token machine.
    new_password absent -> reset admin vers la valeur par défaut fixe (README §12/§15 :
    l'admin ne saisit jamais le nouveau mot de passe). new_password fourni -> reset
    self-service (RouteAuth /auth/reset-password) après vérification du code OTP envoyé
    par email — la plateforme centrale n'a pas d'endpoint self-service, ce flux ne fait
    que déverrouiller ce même appel machine-token avec le mot de passe choisi."""
    password = new_password or _DEFAULT_RESET_PASSWORD
    try:
        async with httpx.AsyncClient(**_client_kwargs()) as client:
            response = await client.post(
                f"/v1/client-app-users/{user_uuid}/reset-password",
                json={"password": password},
                headers={"Authorization": f"Bearer {machine_token}"},
            )
    except httpx.HTTPError as exc:
        raise CentralUnavailableError(f"Service d'authentification central indisponible : {exc}") from exc
    _raise_for_mutation_status(response)
    return password


async def delete_central_account(user_id: int, user_bearer: str) -> None:
    """DELETE /v1/users/{user_id} — bearer de l'ACTEUR, jamais le token machine.
    Ne réutilise pas _raise_for_mutation_status() : ce helper attribue tout 401/403
    à un "token machine rejeté", ce qui est faux ici (aucun token machine en jeu) et
    masque le cas réel observé en prod — un 403 "missing_scope" du central quand le
    groupe de l'acteur n'a pas le scope "user.delete"."""
    try:
        async with httpx.AsyncClient(**_client_kwargs()) as client:
            response = await client.delete(
                f"/v1/users/{user_id}",
                headers={"Authorization": f"Bearer {user_bearer}"},
            )
    except httpx.HTTPError as exc:
        raise CentralUnavailableError(f"Service d'authentification central indisponible : {exc}") from exc

    if response.status_code in (401, 403):
        detail = None
        try:
            detail = response.json().get("detail")
        except Exception:
            pass
        if isinstance(detail, dict) and detail.get("code") == "missing_scope":
            scope = detail.get("required_scope", "user.delete")
            raise CentralPermissionDenied(
                f"Votre compte central n'a pas le droit de supprimer un utilisateur "
                f"(scope requis manquant côté plateforme centrale : {scope}). "
                f"Contactez l'équipe de la plateforme centrale pour faire accorder ce scope."
            )
        message = detail if isinstance(detail, str) else None
        raise CentralPermissionDenied(
            message or "Suppression refusée par la plateforme centrale (droits insuffisants ou session invalide)."
        )
    if response.status_code in (400, 422):
        try:
            message = response.json().get("message")
        except Exception:
            message = None
        raise CentralValidationError(message or "Requête rejetée par le central.")
    if response.status_code >= 500:
        raise CentralUnavailableError(f"Le central a répondu {response.status_code}.")
    response.raise_for_status()


async def log_central_event(
    bearer_token: str,
    *,
    object_id: str,
    action: str,
    status: str,
    message: str,
    before: Optional[dict[str, Any]] = None,
    after: Optional[dict[str, Any]] = None,
) -> None:
    """Audit centralisé non bloquant (POST /v1/logs/) — n'exceptionne jamais."""
    try:
        async with httpx.AsyncClient(**_client_kwargs()) as client:
            await client.post(
                "/v1/logs/",
                headers={"Authorization": f"Bearer {bearer_token}"},
                json={
                    "object_id": object_id,
                    "infos": {
                        "action": action,
                        "action_family": "account",
                        "status": status,
                        "object_id": object_id,
                        "message": message,
                        "before": _mask(before or {}),
                        "after": _mask(after or {}),
                    },
                },
            )
    except Exception as exc:
        logger.warning("central_auth: échec envoi audit centralisé (%s) : %s", action, exc)
