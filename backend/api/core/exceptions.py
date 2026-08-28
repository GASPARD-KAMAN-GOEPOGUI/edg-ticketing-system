"""
Hiérarchie d'exceptions métier EDG Support.

Chaque exception transporte :
  - message   : texte lisible par l'utilisateur
  - error_code: identifiant machine (cf. ErrorCode)
  - status_code: code HTTP à retourner
  - field     : champ concerné (pour les erreurs de formulaire)
  - value     : valeur qui a causé l'erreur
  - hint      : suggestion de résolution
  - details   : liste de sous-erreurs (validation)
"""
from __future__ import annotations

from typing import Any, Optional

from api.core.error_codes import ErrorCode


class EDGException(Exception):
    """Exception métier de base — toutes les exceptions EDG Support en héritent."""

    def __init__(
        self,
        message: str,
        *,
        error_code: str = ErrorCode.INTERNAL_ERROR,
        status_code: int = 400,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        hint: Optional[str] = None,
        details: Optional[list] = None,
    ) -> None:
        super().__init__(message)
        self.message = message
        self.error_code = error_code.value if hasattr(error_code, "value") else str(error_code)
        self.status_code = status_code
        self.field = field
        self.value = value
        self.hint = hint
        self.details = details

    def __repr__(self) -> str:
        return (
            f"{self.__class__.__name__}("
            f"message={self.message!r}, "
            f"error_code={self.error_code!r}, "
            f"status={self.status_code})"
        )


# ── 404 Not Found ─────────────────────────────────────────────────────────────

class NotFoundException(EDGException):
    """La ressource demandée n'existe pas ou a été supprimée (404)."""

    def __init__(
        self,
        message: str = "La ressource demandée est introuvable.",
        *,
        error_code: str = ErrorCode.NOT_FOUND,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        hint: Optional[str] = None,
    ) -> None:
        super().__init__(
            message,
            error_code=error_code,
            status_code=404,
            field=field,
            value=value,
            hint=hint,
        )


# ── 409 Conflict ─────────────────────────────────────────────────────────────

class ConflictException(EDGException):
    """Violation d'une contrainte d'unicité (409)."""

    def __init__(
        self,
        message: str = "Cette ressource existe déjà.",
        *,
        error_code: str = ErrorCode.ALREADY_EXISTS,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        hint: Optional[str] = None,
    ) -> None:
        super().__init__(
            message,
            error_code=error_code,
            status_code=409,
            field=field,
            value=value,
            hint=hint,
        )


# ── 422 Unprocessable ─────────────────────────────────────────────────────────

class ForeignKeyException(EDGException):
    """
    Violation de clé étrangère (422).
    Levée quand un champ référence une entité qui n'existe pas dans la base.

    Exemple :
        ForeignKeyException(
            "La direction spécifiée n'existe pas.",
            error_code=ErrorCode.DIRECTION_NOT_FOUND,
            field="direction_id",
            value="DIR-DSI-001",
            hint="Créez d'abord la direction ou utilisez un identifiant existant.",
        )
    """

    def __init__(
        self,
        message: str = "Une référence vers une entité inexistante a été fournie.",
        *,
        error_code: str = ErrorCode.FOREIGN_KEY_VIOLATION,
        field: Optional[str] = None,
        value: Optional[Any] = None,
        hint: Optional[str] = None,
    ) -> None:
        super().__init__(
            message,
            error_code=error_code,
            status_code=422,
            field=field,
            value=value,
            hint=hint,
        )


class ValidationException(EDGException):
    """Données d'entrée invalides (422)."""

    def __init__(
        self,
        message: str = "Les données fournies sont invalides.",
        *,
        error_code: str = ErrorCode.VALIDATION_ERROR,
        details: Optional[list] = None,
    ) -> None:
        super().__init__(
            message,
            error_code=error_code,
            status_code=422,
            details=details,
        )


# ── 400 Bad Request ──────────────────────────────────────────────────────────

class BusinessException(EDGException):
    """
    Violation d'une règle métier (400).
    Utilisée quand l'opération est techniquement valide mais interdite par les règles.

    Exemple :
        BusinessException(
            "Impossible de fermer une demande déjà résolue.",
            error_code=ErrorCode.INVALID_STATUS_TRANSITION,
            hint="Une demande résolue doit d'abord être rouverte.",
        )
    """

    def __init__(
        self,
        message: str = "L'opération demandée n'est pas autorisée.",
        *,
        error_code: str = ErrorCode.BUSINESS_RULE_VIOLATION,
        field: Optional[str] = None,
        hint: Optional[str] = None,
        details: Optional[list] = None,
    ) -> None:
        super().__init__(
            message,
            error_code=error_code,
            status_code=400,
            field=field,
            hint=hint,
            details=details,
        )


# ── 403 / 401 ────────────────────────────────────────────────────────────────

class ForbiddenException(EDGException):
    """Accès interdit — authentifié mais non autorisé (403)."""

    def __init__(
        self,
        message: str = "Vous n'êtes pas autorisé à effectuer cette opération.",
        *,
        error_code: str = ErrorCode.FORBIDDEN,
        hint: Optional[str] = None,
    ) -> None:
        super().__init__(message, error_code=error_code, status_code=403, hint=hint)


class UnauthorizedException(EDGException):
    """Non authentifié (401)."""

    def __init__(
        self,
        message: str = "Authentification requise pour accéder à cette ressource.",
        *,
        error_code: str = ErrorCode.UNAUTHORIZED,
    ) -> None:
        super().__init__(message, error_code=error_code, status_code=401)


# ── 500 Internal ─────────────────────────────────────────────────────────────

class DatabaseException(EDGException):
    """
    Erreur de base de données masquée (500).
    Les détails techniques ne sont JAMAIS exposés dans la réponse publique.
    """

    def __init__(
        self,
        message: str = "Une erreur de base de données s'est produite. Nos équipes ont été notifiées.",
        *,
        error_code: str = ErrorCode.DATABASE_ERROR,
        hint: Optional[str] = None,
    ) -> None:
        super().__init__(message, error_code=error_code, status_code=500, hint=hint)
