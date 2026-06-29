"""
Gestionnaires d'exceptions globaux FastAPI — EDG Connect.

Chaque handler :
  1. Logue UNE seule ligne d'erreur (lisible, pas de traceback brut)
  2. Retourne une réponse JSON structurée et lisible
  3. Ne laisse JAMAIS fuiter d'informations système (traceback, SQL, chemins)

Ordre d'évaluation (du plus spécifique au plus général) :
    EDGException → RequestValidationError → StarletteHTTPException
    → SQLAlchemyError → Exception

Enregistrement dans main.py :
    from api.core.exception_handlers import register_exception_handlers
    register_exception_handlers(app)
"""
from __future__ import annotations

import logging
import traceback
from typing import TYPE_CHECKING

from fastapi import FastAPI, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from api.core.exceptions import EDGException
from api.core.logger import get_logger

if TYPE_CHECKING:
    pass

logger = get_logger("exception_handlers")


# ── Constructeur de corps d'erreur ────────────────────────────────────────────

def _error_body(
    *,
    message: str,
    error_code: str,
    field: str | None = None,
    value=None,
    hint: str | None = None,
    details: list | None = None,
) -> dict:
    """Construit le dictionnaire de réponse d'erreur standardisé."""
    body: dict = {
        "success": False,
        "message": message,
        "error_code": error_code,
    }
    if field is not None:
        body["field"] = field
    if value is not None:
        body["value"] = str(value)
    if hint is not None:
        body["hint"] = hint
    if details:
        body["details"] = details
    return body


def _unwrap_exception(exc: BaseException) -> BaseException:
    """
    Extrait la cause réelle depuis un ExceptionGroup/BaseExceptionGroup (Python 3.11+).
    Parcourt __cause__ et les groupes d'exceptions anyio de façon récursive.
    """
    inner = getattr(exc, "exceptions", None)
    if inner:
        return _unwrap_exception(inner[0])
    cause = getattr(exc, "__cause__", None)
    if cause is not None:
        return cause
    return exc


# ── Handler 1 : Exceptions métier EDG ────────────────────────────────────────

async def edg_exception_handler(request: Request, exc: EDGException) -> JSONResponse:
    """
    Gère toutes les exceptions héritant de EDGException.
    Couvre : NotFoundException, ConflictException, ForeignKeyException,
             BusinessException, ForbiddenException, DatabaseException, etc.

    Log affiché :
        WARNING │ [exception_handlers] ⚠️  DIRECTION_NOT_FOUND [422] — La direction...
    """
    log_parts = [f"❌ {exc.error_code} [{exc.status_code}] — {exc.message}"]
    if exc.field:
        log_parts.append(f"champ={exc.field!r}")
    if exc.value:
        log_parts.append(f"valeur={exc.value!r}")

    if exc.status_code >= 500:
        logger.error(" | ".join(log_parts))
    elif exc.status_code >= 400:
        logger.warning(" | ".join(log_parts))
    else:
        logger.info(" | ".join(log_parts))

    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(
            message=exc.message,
            error_code=exc.error_code,
            field=exc.field,
            value=exc.value,
            hint=exc.hint,
            details=exc.details,
        ),
    )


# ── Handler 2 : HTTPException FastAPI (legacy) ────────────────────────────────

_HTTP_STATUS_DEFAULTS: dict[int, tuple[str, str]] = {
    400: ("Requête invalide.",                                          "INVALID_REQUEST"),
    401: ("Authentification requise.",                                  "UNAUTHORIZED"),
    403: ("Accès refusé à cette ressource.",                            "FORBIDDEN"),
    404: ("La ressource demandée est introuvable.",                     "NOT_FOUND"),
    405: ("Méthode HTTP non autorisée sur cet endpoint.",               "METHOD_NOT_ALLOWED"),
    409: ("Conflit — cette ressource existe déjà.",                     "ALREADY_EXISTS"),
    422: ("Les données fournies sont invalides.",                       "VALIDATION_ERROR"),
    429: ("Trop de requêtes. Veuillez patienter avant de réessayer.",   "RATE_LIMITED"),
    500: ("Erreur interne du serveur.",                                 "INTERNAL_ERROR"),
    503: ("Service temporairement indisponible.",                       "SERVICE_UNAVAILABLE"),
}

# Messages FastAPI par défaut (en anglais) — remplacés par nos traductions françaises
_FASTAPI_GENERIC_DETAILS: frozenset[str] = frozenset({
    "Not Found", "Method Not Allowed", "Forbidden", "Unauthorized",
    "Bad Request", "Conflict", "Unprocessable Entity",
    "Internal Server Error", "Service Unavailable", "Too Many Requests",
})


async def http_exception_handler(
    request: Request, exc: StarletteHTTPException
) -> JSONResponse:
    """
    Convertit les HTTPException FastAPI natives (raise HTTPException(...))
    au format de réponse standardisé EDG.

    Règle de message :
      - Si le detail est un message personnalisé (non vide, non FastAPI générique) → l'utiliser
      - Sinon → utiliser la traduction française standard
    """
    default_msg, default_code = _HTTP_STATUS_DEFAULTS.get(
        exc.status_code, ("Erreur inattendue.", "UNEXPECTED_ERROR")
    )

    detail = exc.detail
    if (
        isinstance(detail, str)
        and detail
        and detail not in _FASTAPI_GENERIC_DETAILS
    ):
        message = detail
    elif isinstance(detail, dict) and "message" in detail:
        message = str(detail["message"])
    else:
        message = default_msg

    logger.warning(
        f"⚠️  HTTP {exc.status_code} — {message} "
        f"| {request.method} {request.url.path}"
    )

    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(message=message, error_code=default_code),
    )


# ── Handler 3 : Erreurs de validation Pydantic ────────────────────────────────

_PYDANTIC_MSG_FR: dict[str, str] = {
    "value_error.missing":            "Ce champ est obligatoire.",
    "value_error.email":              "Adresse email invalide.",
    "type_error.none.not_allowed":    "Ce champ ne peut pas être nul.",
    "value_error.str.min_length":     "Valeur trop courte.",
    "value_error.str.max_length":     "Valeur trop longue.",
    "type_error.integer":             "Un entier est attendu.",
    "type_error.float":               "Un nombre décimal est attendu.",
    "type_error.bool":                "Un booléen (true/false) est attendu.",
    "value_error.number.not_ge":      "La valeur doit être supérieure ou égale au minimum.",
    "value_error.number.not_le":      "La valeur doit être inférieure ou égale au maximum.",
    "value_error.list.min_items":     "La liste doit contenir au moins un élément.",
    "value_error.url.scheme":         "URL invalide.",
    "missing":                        "Ce champ est obligatoire.",
    "string_too_short":               "Valeur trop courte.",
    "string_too_long":                "Valeur trop longue.",
    "int_parsing":                    "Un entier est attendu.",
    "float_parsing":                  "Un nombre décimal est attendu.",
    "bool_parsing":                   "Un booléen (true/false) est attendu.",
    "value_error":                    "Valeur invalide.",
    "json_invalid":                   "JSON invalide dans le corps de la requête.",
}


async def validation_exception_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    """
    Convertit les erreurs de validation Pydantic en réponse lisible.

    Transforme :
        [{"loc": ["body", "email"], "msg": "value is not a valid email address", "type": "value_error.email"}]
    En :
        {"field": "email", "message": "Adresse email invalide.", "type": "value_error.email"}
    """
    details = []
    for error in exc.errors():
        loc = error.get("loc", ())
        field_parts = [str(part) for part in loc if part not in ("body", "query", "path")]
        field = " → ".join(field_parts) if field_parts else (str(loc[0]) if loc else "?")

        err_type = error.get("type", "")
        raw_msg  = error.get("msg", "Valeur invalide.")
        message  = _PYDANTIC_MSG_FR.get(err_type, raw_msg)

        details.append({"field": field, "message": message, "type": err_type})

    logger.warning(
        f"⚠️  VALIDATION_ERROR — {len(details)} erreur(s) "
        f"| {request.method} {request.url.path}"
    )

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_error_body(
            message="Les données fournies sont invalides. Corrigez les erreurs indiquées.",
            error_code="VALIDATION_ERROR",
            details=details,
        ),
    )


# ── Handler 4 : Erreurs SQLAlchemy / base de données ─────────────────────────

# Codes d'erreur MySQL → message utilisateur lisible
_MYSQL_ERROR_MESSAGES: dict[int, str] = {
    1054: "La base de données contient une erreur de configuration (colonne inconnue). Contactez l'administrateur.",
    1045: "Erreur d'authentification à la base de données.",
    1049: "Base de données introuvable.",
    1062: "Duplication de données : cet enregistrement existe déjà.",
    1064: "Erreur de syntaxe SQL interne. Contactez l'administrateur.",
    1146: "Table de base de données introuvable. Une migration est peut-être nécessaire.",
    1215: "Violation de contrainte de clé étrangère.",
    1216: "Impossible d'ajouter une ligne : contrainte de clé étrangère échouée.",
    1217: "Impossible de supprimer cette ressource : elle est référencée ailleurs.",
    1406: "La valeur fournie dépasse la taille maximale autorisée.",
    2003: "Impossible de se connecter à la base de données. Vérifiez la connexion.",
    2013: "Connexion à la base de données perdue. Réessayez dans un instant.",
}


async def sqlalchemy_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Gère les exceptions SQLAlchemy (OperationalError, IntegrityError, etc.)
    avant qu'elles n'atteignent le handler générique.

    Log : une seule ligne avec le code MySQL et le type d'erreur.
    Réponse : message lisible en français, SANS aucun détail SQL.
    """
    from sqlalchemy.exc import SQLAlchemyError  # import local pour éviter la dépendance circulaire

    real_exc = _unwrap_exception(exc)

    # Extraire le code d'erreur MySQL original (orig.args[0])
    orig = getattr(real_exc, "orig", None)
    mysql_code: int | None = None
    if orig is not None and getattr(orig, "args", None):
        try:
            mysql_code = int(orig.args[0])
        except (TypeError, ValueError):
            mysql_code = None

    message = _MYSQL_ERROR_MESSAGES.get(
        mysql_code or 0,
        "Une erreur de base de données s'est produite.",
    )

    # Log concis — afficher le message réel quand le code MySQL est None
    orig_msg = ""
    if mysql_code is None and orig is not None:
        orig_msg = f" | détail : {str(orig.args)[:300]}"
    elif mysql_code is None:
        orig_msg = f" | {str(real_exc)[:300]}"

    if mysql_code in (1045, 2003, 2013):
        logger.critical(
            f"🔴 DB_ERROR ({mysql_code}) — {type(real_exc).__name__} "
            f"| {request.method} {request.url.path}{orig_msg}"
        )
    else:
        logger.error(
            f"❌ DB_ERROR ({mysql_code}) — {type(real_exc).__name__} "
            f"| {request.method} {request.url.path}{orig_msg}"
        )

    return JSONResponse(
        status_code=500,
        content=_error_body(
            message=message,
            error_code="DATABASE_ERROR",
            hint="Si le problème persiste, contactez l'administrateur système.",
        ),
    )


# ── Handler 5 : Exception générique (filet de sécurité final) ────────────────

async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """
    Capture toutes les exceptions non gérées par les handlers précédents.
    - Console : UNE seule ligne d'erreur (type + message court)
    - Traceback complet uniquement en mode DEBUG
    - Réponse publique : ZÉRO information technique
    """
    real_exc = _unwrap_exception(exc)

    # Vérifier si c'est en réalité une exception SQLAlchemy non capturée par son handler
    try:
        from sqlalchemy.exc import SQLAlchemyError
        if isinstance(real_exc, SQLAlchemyError):
            return await sqlalchemy_exception_handler(request, exc)
    except ImportError:
        pass

    # Log concis à ERROR level (une seule ligne)
    logger.error(
        f"❌ ERREUR NON GÉRÉE — {type(real_exc).__name__}: {str(real_exc)[:200]} "
        f"| {request.method} {request.url.path}"
    )

    # Traceback complet uniquement en mode DEBUG (jamais en production)
    if logger.isEnabledFor(logging.DEBUG):
        tb_str = "".join(
            traceback.format_exception(type(exc), exc, exc.__traceback__)
        )
        logger.debug(f"Stack trace complète :\n{tb_str}")

    return JSONResponse(
        status_code=500,
        content=_error_body(
            message=(
                "Une erreur interne s'est produite. "
                "Nos équipes ont été automatiquement notifiées."
            ),
            error_code="INTERNAL_ERROR",
            hint="Si le problème persiste, contactez le support avec la date et l'heure de l'erreur.",
        ),
    )


# ── Enregistrement centralisé ─────────────────────────────────────────────────

def register_exception_handlers(app: FastAPI) -> None:
    """
    Enregistre tous les gestionnaires d'exceptions sur l'application FastAPI.
    À appeler une seule fois dans main.py.

    Ordre d'évaluation (du plus spécifique au plus général) :
        EDGException → RequestValidationError → StarletteHTTPException
        → SQLAlchemyError → Exception
    """
    from sqlalchemy.exc import SQLAlchemyError

    app.add_exception_handler(EDGException, edg_exception_handler)               # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)    # type: ignore[arg-type]
    app.add_exception_handler(SQLAlchemyError, sqlalchemy_exception_handler)     # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)            # type: ignore[arg-type]

    _log = get_logger("startup")
    _log.info(
        "✅ Gestionnaires d'exceptions enregistrés "
        "(EDG + HTTP + Validation + SQLAlchemy + Générique)"
    )
