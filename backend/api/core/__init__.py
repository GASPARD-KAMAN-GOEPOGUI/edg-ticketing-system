"""
api.core — Composants transverses EDG Connect.

Exports principaux :
    ErrorCode               — codes d'erreur constants
    EDGException            — base de toutes les exceptions métier
    NotFoundException       — 404
    ConflictException       — 409
    ForeignKeyException     — 422 (contrainte FK)
    ValidationException     — 422 (données invalides)
    BusinessException       — 400 (règle métier)
    ForbiddenException      — 403
    UnauthorizedException   — 401
    DatabaseException       — 500

    ApiResponse             — enveloppe succès {success, message, data}
    ErrorResponse           — enveloppe erreur {success, message, error_code, ...}

    get_logger              — retourne un logger EDG coloré
    setup_logging           — configure le logging global (à appeler au démarrage)

    register_exception_handlers — enregistre les handlers sur l'app FastAPI

    Security :
    hash_password / verify_password — Argon2 password hashing
    create_access_token / create_refresh_token / decode_token — JWT
    Permission / ROLE_PERMISSIONS / has_permission — RBAC
    token_blacklist — blacklist de tokens révoqués
"""
from api.core.error_codes import ErrorCode
from api.core.exceptions import (
    EDGException,
    NotFoundException,
    ConflictException,
    ForeignKeyException,
    ValidationException,
    BusinessException,
    ForbiddenException,
    UnauthorizedException,
    DatabaseException,
)
from api.core.responses import ApiResponse, ErrorResponse, ValidationErrorDetail
from api.core.logger import get_logger, setup_logging
from api.core.exception_handlers import register_exception_handlers
from api.core.security import (
    hash_password,
    verify_password,
    create_access_token,
    create_refresh_token,
    decode_token,
    access_token_expire_seconds,
)
from api.core.rbac import Permission, ROLE_PERMISSIONS, has_permission, has_role, role_at_least
from api.core.token_blacklist import token_blacklist
from api.core.event_bus import event_bus, AppEvent, emit as emit_event

__all__ = [
    # Codes d'erreur
    "ErrorCode",
    # Exceptions
    "EDGException", "NotFoundException", "ConflictException",
    "ForeignKeyException", "ValidationException", "BusinessException",
    "ForbiddenException", "UnauthorizedException", "DatabaseException",
    # Réponses
    "ApiResponse", "ErrorResponse", "ValidationErrorDetail",
    # Logger
    "get_logger", "setup_logging",
    # Handlers
    "register_exception_handlers",
    # Sécurité — JWT
    "hash_password", "verify_password",
    "create_access_token", "create_refresh_token", "decode_token",
    "access_token_expire_seconds",
    # RBAC
    "Permission", "ROLE_PERMISSIONS", "has_permission", "has_role", "role_at_least",
    # Token blacklist
    "token_blacklist",
    # Event bus
    "event_bus", "AppEvent", "emit_event",
]
