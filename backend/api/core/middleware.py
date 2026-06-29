"""
Middlewares transverses EDG Connect.

1. RequestLoggingMiddleware
   ─────────────────────────
   Log chaque requête HTTP avec méthode, chemin, durée et statut.
   Intercepte TOUTES les exceptions non gérées et retourne une réponse
   JSON propre (jamais de traceback brut dans les logs de production).

2. ResponseWrapperMiddleware
   ─────────────────────────
   Enveloppe automatiquement toutes les réponses 2xx JSON dans :
     {"success": true, "message": "...", "data": <payload_original>}

   Exclusions (réponses non enveloppées) :
     /, /health, /docs, /redoc, /openapi.json, /favicon.ico
     + toute réponse dont le Content-Type n'est pas application/json
     + réponses déjà enveloppées (contenant "success" à la racine)

Enregistrement dans main.py (ordre important — Logging en dernier = exécuté en premier) :
    app.add_middleware(ResponseWrapperMiddleware)
    app.add_middleware(RequestLoggingMiddleware)
"""
from __future__ import annotations

import json
import time
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response, JSONResponse
from starlette.types import ASGIApp

from api.core.logger import get_logger

_req_log  = get_logger("middleware.request")
_wrap_log = get_logger("middleware.wrapper")

# Chemins dont la réponse n'est PAS enveloppée
_SKIP_WRAP_PATHS: frozenset[str] = frozenset({
    "/",
    "/health",
    "/docs",
    "/redoc",
    "/openapi.json",
    "/favicon.ico",
})

# Préfixes de chemins exclus du wrapping (SSE, téléchargements…)
_SKIP_WRAP_PREFIXES: tuple[str, ...] = ("/api/v1/events",)


def _make_500_response(method: str = "", path: str = "", exc: BaseException | None = None) -> JSONResponse:
    """
    Retourne une réponse JSON 500 propre et logue UNE seule ligne d'erreur.
    Ne laisse jamais fuiter de détails techniques dans la réponse.
    """
    cause = _unwrap_exception(exc) if exc is not None else None

    if cause is not None:
        _req_log.error(
            f"❌ 500 {method:<6} {path} — {type(cause).__name__}: {str(cause)[:200]}"
        )
    return JSONResponse(
        status_code=500,
        content={
            "success":    False,
            "message":    "Une erreur interne s'est produite. Nos équipes ont été notifiées.",
            "error_code": "INTERNAL_ERROR",
            "hint":       "Si le problème persiste, contactez le support avec la date et l'heure.",
        },
    )


def _unwrap_exception(exc: BaseException) -> BaseException:
    """
    Extrait la cause réelle depuis un ExceptionGroup/BaseExceptionGroup (Python 3.11+).
    Retourne l'exception elle-même si ce n'est pas un groupe.
    """
    inner = getattr(exc, "exceptions", None)
    if inner:
        return _unwrap_exception(inner[0])
    cause = getattr(exc, "__cause__", None)
    if cause is not None:
        return cause
    return exc


# ── Middleware 1 : Logging des requêtes ───────────────────────────────────────

class RequestLoggingMiddleware(BaseHTTPMiddleware):
    """
    Log chaque requête entrante avec durée et code statut.
    Intercepte les exceptions non capturées en aval et retourne
    une réponse JSON 500 propre — aucun traceback brut affiché.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        method = request.method
        path   = request.url.path
        is_sse = path.startswith(_SKIP_WRAP_PREFIXES)

        _req_log.info(f"→ {method:<6} {path}")
        t0 = time.perf_counter()

        try:
            response = await call_next(request)
        except Exception as exc:
            elapsed = int((time.perf_counter() - t0) * 1000)
            return _make_500_response(method, path, exc)
        except BaseException as exc:
            # Capture BaseExceptionGroup (Python 3.11 + anyio) et autres BaseException
            # non-Exception — sauf KeyboardInterrupt / SystemExit
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            elapsed = int((time.perf_counter() - t0) * 1000)
            return _make_500_response(method, path, exc)

        if is_sse:
            _req_log.info(f"✅ {response.status_code} {method:<6} {path}  [SSE]")
            return response

        elapsed = int((time.perf_counter() - t0) * 1000)
        status  = response.status_code

        if status >= 500:
            _req_log.error(f"❌ {status} {method:<6} {path}  {elapsed}ms")
        elif status >= 400:
            _req_log.warning(f"⚠️  {status} {method:<6} {path}  {elapsed}ms")
        else:
            _req_log.info(f"✅ {status} {method:<6} {path}  {elapsed}ms")

        return response


# ── Middleware 2 : Enveloppement des réponses 2xx ─────────────────────────────

_METHOD_MESSAGES: dict[str, dict[int, str]] = {
    "POST":   {201: "Ressource créée avec succès.", 200: "Opération effectuée avec succès."},
    "PUT":    {200: "Ressource mise à jour avec succès."},
    "PATCH":  {200: "Ressource mise à jour avec succès."},
    "DELETE": {200: "Ressource supprimée avec succès.", 204: "Ressource supprimée avec succès."},
    "GET":    {200: "Données récupérées avec succès."},
}

_PATH_MESSAGES: dict[str, str] = {
    "/accounts":                "Compte",
    "/directions":              "Direction",
    "/units":                   "Service/Unité",
    "/requests":                "Demande",
    "/comments":                "Commentaire",
    "/attachments":             "Pièce jointe",
    "/escalations":             "Escalade",
    "/categories":              "Catégorie",
    "/sla-policies":            "Politique SLA",
    "/routing-rules":           "Règle de routage",
    "/workflows":               "Workflow",
    "/tasks":                   "Tâche",
    "/notifications":           "Notification",
    "/activity-logs":           "Journal d'activité",
    "/knowledge":               "Article de connaissance",
    "/announcements":           "Annonce",
    "/appreciations":           "Appréciation",
    "/employees":               "Employé",
    "/homepage-config":         "Configuration",
    "/communication-settings":  "Paramètre de communication",
    "/stats":                   "Statistique",
    "/references":              "Référentiel",
}


def _infer_message(method: str, status_code: int, path: str) -> str:
    entity = next(
        (label for fragment, label in _PATH_MESSAGES.items() if fragment in path),
        "Ressource",
    )
    templates = _METHOD_MESSAGES.get(method.upper(), {})
    base_msg  = templates.get(status_code, "Opération effectuée avec succès.")
    return base_msg.replace("Ressource", entity, 1)


class ResponseWrapperMiddleware(BaseHTTPMiddleware):
    """
    Enveloppe les réponses 2xx JSON dans {success, message, data}.
    Les erreurs (4xx/5xx) sont déjà formatées par les exception handlers
    ou par RequestLoggingMiddleware.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        try:
            response = await call_next(request)
        except Exception as exc:
            # Filet de sécurité : ne devrait pas arriver si RequestLoggingMiddleware
            # est bien enregistré en dernier (= exécuté en premier).
            _wrap_log.error(
                f"❌ Exception non capturée dans ResponseWrapper: "
                f"{type(_unwrap_exception(exc)).__name__}"
            )
            return _make_500_response(request.method, request.url.path, exc)
        except BaseException as exc:
            if isinstance(exc, (KeyboardInterrupt, SystemExit)):
                raise
            return _make_500_response(request.method, request.url.path, exc)

        # Exclure les chemins non-API
        if request.url.path in _SKIP_WRAP_PATHS:
            return response

        # Exclure les flux SSE et streaming
        if request.url.path.startswith(_SKIP_WRAP_PREFIXES):
            return response

        # Exclure les erreurs (gérées par les handlers)
        if response.status_code >= 400:
            return response

        # Exclure les non-JSON
        content_type = response.headers.get("content-type", "")
        if "application/json" not in content_type:
            return response

        # Lire le corps de la réponse
        body_bytes = b""
        async for chunk in response.body_iterator:
            body_bytes += chunk

        if not body_bytes:
            return response

        try:
            payload = json.loads(body_bytes)
        except (json.JSONDecodeError, ValueError):
            return Response(
                content=body_bytes,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=content_type,
            )

        # Si déjà enveloppé, ne pas ré-envelopper
        if isinstance(payload, dict) and "success" in payload:
            return Response(
                content=body_bytes,
                status_code=response.status_code,
                headers=dict(response.headers),
                media_type=content_type,
            )

        message = _infer_message(request.method, response.status_code, request.url.path)
        wrapped = {
            "success": True,
            "message": message,
            "data":    payload,
        }

        new_body = json.dumps(wrapped, ensure_ascii=False)
        new_headers = dict(response.headers)
        new_headers["content-length"] = str(len(new_body.encode()))

        return Response(
            content=new_body,
            status_code=response.status_code,
            headers=new_headers,
            media_type="application/json",
        )
