"""
Client de la plateforme centrale d'authentification manager-user.

Flux : source-token -> login, refresh, scopes, groupes, audit centralisé.
Voir backend/README-integration-plateforme-centrale/README-integration-plateforme-centrale.md.

httpx.AsyncClient(trust_env=False) — évite l'event loop bloquant (le README
utilise httpx.Client synchrone dans son exemple, ce backend est 100% async).
"""
from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from typing import Any, AsyncIterator, Optional

import httpx

from api.configs.Environment import get_environment

logger = logging.getLogger(__name__)

_MASKED_FIELDS = {
    "password", "client_secret", "secret", "token",
    "source_token", "bearer_token", "refresh_token", "authorization",
}

# Correspondance groupe central <-> role EDG Connect, lue DANS LES DEUX SENS :
#   - role_from_groups()  : groupes centraux -> role local (a la connexion)
#   - group_for_role()    : role local -> groupe central (creation/modification
#                           de compte depuis le backoffice EDG Connect)
# Une seule table pour les deux sens : toute correspondance manquante ici ferait
# retomber le role sur `collaborateur-support`, ce qui annulerait silencieusement
# un changement de role fait dans le backoffice a la connexion suivante.
# L'ordre compte : premier groupe trouve gagne si un compte appartient a plusieurs
# groupes (du plus privilegie au moins privilegie).
GROUP_ROLE_PRIORITY: list[tuple[str, str]] = [
    ("admin-support", "admin"),
    ("qualify-support", "chief-service"),
    ("chef-division-support", "chef-division-support"),
    ("technicien-support", "technicien"),
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
    """HTTP 409 (status "identity_already_exists") sur POST /v1/client-app-users/
    group-membership — un compte existe déjà avec le même email/téléphone."""


class CentralValidationError(CentralAuthError):
    """400/422 renvoyé par le central (ex. politique de mot de passe) — message relayé."""


class CentralInvalidPhoneFormat(CentralValidationError):
    """422 (status "invalid_phone_format") sur POST /v1/client-app-users/
    group-membership — statut fonctionnel documenté, message fixe dédié
    (voir create_central_account), distinct des CentralValidationError génériques."""


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


# ── Client HTTP partagé ───────────────────────────────────────────────────────
#
# Chaque appel ouvrait son propre AsyncClient, donc sa propre connexion TLS vers
# le central. Une connexion se paie ici jusqu'à 5 s de poignée de main, et un
# simple login en enchaîne quatre (source-token, login, scopes, groupes) : la
# somme frôlait HTTP_TIMEOUT_MS et retombait par intermittence en
# « Service d'authentification central indisponible » (503) — alors que le
# central, lui, répondait très bien.
#
# Un client unique garde ses connexions ouvertes (keep-alive) : la poignée de
# main TLS est payée une fois, puis réutilisée par tous les appels suivants.
_shared: Optional[httpx.AsyncClient] = None
_shared_lock = asyncio.Lock()


async def _get_shared_client() -> httpx.AsyncClient:
    global _shared
    if _shared is not None and not _shared.is_closed:
        return _shared
    async with _shared_lock:
        if _shared is None or _shared.is_closed:
            _shared = httpx.AsyncClient(
                **_client_kwargs(),
                limits=httpx.Limits(
                    max_keepalive_connections=10,
                    max_connections=20,
                    # Mesure du 2026-09-28 sur liaison lente : une connexion
                    # DÉJÀ établie répond en ~800 ms, une connexion à froid en
                    # 16 à 25 s — la poignée de main TLS coûte donc l'essentiel
                    # du temps. Les 60 s d'origine couvraient « un parcours
                    # utilisateur », mais pas une pause : dès que l'utilisateur
                    # lisait un écran plus d'une minute, le clic suivant
                    # repayait le TLS complet. D'où la lenteur ressentie au
                    # PREMIER clic après une pause, et elle seule.
                    #
                    # 10 minutes couvrent les pauses réelles. Aucune contrepartie
                    # de sécurité : garder une connexion TCP ouverte ne prolonge
                    # aucune autorisation, contrairement au cache des scopes.
                    keepalive_expiry=600.0,
                ),
            )
    return _shared


@asynccontextmanager
async def _client() -> AsyncIterator[httpx.AsyncClient]:
    """Prête le client partagé SANS le fermer en sortie de bloc.

    Garde la forme `async with ... as client:` des appels existants, pour que la
    seule différence soit la réutilisation de la connexion.
    """
    yield await _get_shared_client()


async def close_central_client() -> None:
    """Ferme le client partagé — appelé à l'arrêt de l'application (lifespan)."""
    global _shared
    if _shared is not None and not _shared.is_closed:
        await _shared.aclose()
    _shared = None


def _readable_validation_error(response: httpx.Response) -> str:
    """Traduit un refus de validation du central en phrase lisible.

    Le central renvoie le format d'erreur FastAPI/pydantic — une LISTE d'objets
    `{loc, msg, type, ctx}`. Relayée telle quelle, elle s'affichait à
    l'utilisateur sous sa forme brute :

        [{'loc': ['body', 'password'], 'msg': 'ensure this value has at least
         8 characters', 'type': 'value_error.any_str.min_length', ...}]

    On en extrait le champ et la contrainte pour en faire une phrase française.
    Le JSON brut n'est jamais montré : il part dans les logs, pas à l'écran.
    """
    prefix = "La plateforme centrale a refusé la demande"
    try:
        body = response.json()
    except Exception:
        return f"{prefix}."

    detail = body.get("detail") if isinstance(body, dict) else body

    if isinstance(detail, str) and detail.strip():
        return f"{prefix} : {detail.strip()}"

    if isinstance(detail, list):
        champs = {
            "password": "le mot de passe",
            "email": "l'adresse email",
            "phone": "le numéro de téléphone",
        }
        messages: list[str] = []
        for item in detail:
            if not isinstance(item, dict):
                continue
            loc = item.get("loc") or []
            champ = champs.get(str(loc[-1]) if loc else "", None)
            limite = (item.get("ctx") or {}).get("limit_value")
            type_ = str(item.get("type") or "")
            if champ and "min_length" in type_ and limite:
                messages.append(f"{champ} doit contenir au moins {limite} caractères")
            elif champ and "max_length" in type_ and limite:
                messages.append(f"{champ} ne doit pas dépasser {limite} caractères")
            elif champ:
                messages.append(f"{champ} n'est pas valide")
        if messages:
            return f"{prefix} : " + ", ".join(messages) + "."

    return f"{prefix} (format ou politique de mot de passe)."


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
        async with _client() as client:
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


# ── TEMPORAIRE (2026-08) — diagnostic public du rejet CLIENT_APP_CODE/SECRET ──
# À SUPPRIMER avec la route qui l'utilise (RouteAuth.py::debug_source_token) une
# fois l'investigation terminée. Ne masque rien de la réponse centrale (sauf le
# secret, jamais renvoyé) pour permettre de voir la cause exacte du rejet.
async def debug_source_token_exchange(
    client_code: str | None = None, client_secret: str | None = None,
) -> dict[str, Any]:
    env = get_environment()
    code = client_code or env.CLIENT_APP_CODE
    secret = client_secret or env.CLIENT_APP_SECRET
    if not code or not secret:
        return {
            "ok": False,
            "error": "CLIENT_APP_CODE/CLIENT_APP_SECRET non configurés (et non fournis en paramètre).",
        }
    try:
        async with _client() as client:
            response = await client.post(
                "/v1/client-app-auth/source-token",
                json={"client_code": code, "client_secret": secret},
            )
    except httpx.HTTPError as exc:
        return {
            "ok": False,
            "error": f"Service central indisponible : {exc}",
            "client_code_used": code,
            "central_base_url": env.CENTRAL_AUTH_BASE_URL,
        }

    try:
        body: Any = response.json()
    except Exception:
        body = response.text

    return {
        "ok": response.status_code < 400,
        "status_code": response.status_code,
        "client_code_used": code,
        "central_base_url": env.CENTRAL_AUTH_BASE_URL,
        "response_body": body,
    }


async def get_machine_token() -> str:
    """POST /v1/client-app-auth/token — token machine pour les opérations d'administration
    de comptes (update/activate/deactivate/reset-password/groupes). Pas de cache : refetch
    à chaque invocation de méthode de service (opérations admin peu fréquentes)."""
    env = get_environment()
    if not env.CLIENT_APP_CODE or not env.CLIENT_APP_SECRET:
        raise CentralUnavailableError("CLIENT_APP_CODE/CLIENT_APP_SECRET non configurés.")
    try:
        async with _client() as client:
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
        async with _client() as client:
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
    # 400/422 — la plateforme centrale REFUSE la requête sur le fond (politique de
    # mot de passe, format d'email…). Sans ce cas, `raise_for_status()` laissait
    # remonter un `HTTPStatusError` brut jusqu'au middleware, et l'utilisateur
    # recevait « Une erreur interne s'est produite » (500) pour un simple mot de
    # passe trop court — message trompeur, et diagnostic impossible.
    if response.status_code in (400, 422):
        raise CentralValidationError(_readable_validation_error(response))
    if response.status_code >= 500:
        raise CentralUnavailableError(
            f"La plateforme centrale a répondu {response.status_code}."
        )
    response.raise_for_status()
    return _normalize_token_response(response.json())


async def central_refresh(refresh_token: str) -> dict[str, Any]:
    try:
        async with _client() as client:
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
        async with _client() as client:
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
        async with _client() as client:
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
    """Mappe les groupes centraux actifs vers un rôle EDG Support (priorité admin > chief-service > user)."""
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
    Inverse de GROUP_ROLE_PRIORITY : rôle local EDG Support -> groupe central.
    Rôles sans groupe central dédié (chief-departement, director,
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


async def get_profile(bearer_token: str) -> dict[str, Any]:
    """GET /api/me — profil complet (nom, prénom, téléphone, uuid) de l'utilisateur
    connecté. Distinct de get_scopes()/get_groups() : ceux-ci ne renvoient que
    user_id/email/codenames, jamais assez pour matérialiser un compte local
    (nom NOT NULL) lors d'un rattachement (auto-provisioning ou consentement)."""
    try:
        async with _client() as client:
            response = await client.get(
                "/api/me",
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


def parse_profile_identity(profile: dict[str, Any]) -> dict[str, Optional[str]]:
    """
    Extrait uuid/nom/prénom/téléphone d'une réponse GET /api/me.

    Convention centrale déjà observée ailleurs dans ce module
    (create_central_account/update_central_account) : le payload envoyé AU central
    utilise "name" pour le prénom et "last_name" pour le nom de famille. On suppose
    la même convention en LECTURE ici. Si "last_name" est absent de la réponse, on
    retombe sur "name" comme nom de famille (colonne locale account.name, NOT NULL)
    sans deviner de prénom, plutôt que de mal assigner les deux.

    Ne lève jamais d'exception — un profil partiel ou de forme inattendue reste
    exploitable : les champs manquants restent None et sont alors complétés
    manuellement par l'utilisateur sur l'écran de rattachement (consentement).
    """
    uuid = profile.get("uuid") or profile.get("user_uuid")
    phone = profile.get("phone") or profile.get("telephone")
    if profile.get("last_name"):
        last_name = profile.get("last_name")
        first_name = profile.get("name") or profile.get("first_name") or profile.get("firstname")
    else:
        last_name = profile.get("name") or profile.get("full_name")
        first_name = profile.get("first_name") or profile.get("firstname")
    return {"uuid": uuid, "name": last_name, "firstname": first_name, "phone": phone}


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
    password: str,
) -> dict[str, Any]:
    """POST /v1/client-app-users/group-membership — authentifié par source_token
    dans le corps de la requête (mise à jour du endpoint central, plus de token
    machine ni d'en-tête Authorization pour cet appel précis — contrairement aux
    autres mutations /v1/client-app-users/* qui restent au token machine).
    Retry une fois avec un nouveau source_token si le central le signale invalide/
    expiré, même mécanisme que central_login()."""
    source_token = await get_source_token()
    payload = {
        "group_codename": group_codename,
        "email": email,
        "phone": phone,
        "name": firstname,
        "last_name": last_name,
        "password": password,
    }

    async def _attempt(token: str) -> httpx.Response:
        async with _client() as client:
            return await client.post(
                "/v1/client-app-users/group-membership",
                json={**payload, "source_token": token},
            )

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

    if response.status_code in (401, 403):
        raise CentralInvalidClientCredentials("source_token rejeté par le central.")
    if response.status_code == 409:
        try:
            message = response.json().get("message")
        except Exception:
            message = None
        raise CentralIdentityConflict(
            message or "Un compte existe déjà avec cet email ou ce téléphone (identity_already_exists)."
        )
    if response.status_code == 422:
        # invalid_phone_format — seul statut 422 documenté pour cet endpoint.
        # Message fixe volontaire (pas de relais du message central), demandé
        # explicitement pour cet écran d'inscription.
        raise CentralInvalidPhoneFormat("Le numéro de téléphone n'est pas au bon format.")
    if response.status_code == 400:
        try:
            message = response.json().get("message")
        except Exception:
            message = None
        raise CentralValidationError(message or "Requête rejetée par le central.")
    if response.status_code >= 500:
        raise CentralUnavailableError(f"Le central a répondu {response.status_code}.")
    response.raise_for_status()

    return response.json()


async def update_central_account(
    user_uuid: str, *, email: str, phone: str, firstname: str, last_name: str, machine_token: str,
) -> dict[str, Any]:
    """PUT /v1/client-app-users/{user_uuid} — token machine."""
    payload = {"email": email, "phone": phone, "name": firstname, "last_name": last_name}
    try:
        async with _client() as client:
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
        async with _client() as client:
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
        async with _client() as client:
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
        async with _client() as client:
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
        async with _client() as client:
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
        async with _client() as client:
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
        async with _client() as client:
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
        async with _client() as client:
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
