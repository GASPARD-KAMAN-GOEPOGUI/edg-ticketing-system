"""
Modèles de réponse API uniformisés EDG Connect.

Toutes les réponses de l'API suivent l'un de ces deux formats :

  Succès :
    {
      "success": true,
      "message": "Compte créé avec succès.",
      "data": { ...payload... }
    }

  Erreur :
    {
      "success": false,
      "message": "Cette adresse email est déjà utilisée.",
      "error_code": "EMAIL_ALREADY_EXISTS",
      "field": "email",
      "value": "test@edg.gn",
      "hint": "Utilisez une adresse email différente.",
      "details": [...]          ← présent pour VALIDATION_ERROR uniquement
    }

Ces modèles sont utilisés pour la documentation OpenAPI.
L'enveloppement automatique des réponses 2xx est géré par ResponseWrapperMiddleware.
"""
from __future__ import annotations

from typing import Any, Generic, List, Optional, TypeVar

from pydantic import BaseModel
from pydantic.generics import GenericModel

T = TypeVar("T")


# ── Réponse succès ────────────────────────────────────────────────────────────

class ApiResponse(GenericModel, Generic[T]):
    """
    Enveloppe standard pour les réponses de succès.

    Utilisation dans les routes (OpenAPI) :
        @router.post("/", response_model=ApiResponse[AccountResponse])
        async def create(...):
            ...
    """
    success: bool = True
    message: str = "Opération effectuée avec succès."
    data: Optional[T] = None

    class Config:
        orm_mode = True


# ── Réponse erreur ────────────────────────────────────────────────────────────

class ValidationErrorDetail(BaseModel):
    """Un sous-erreur de validation (présent dans ErrorResponse.details)."""
    field: str
    message: str
    type: Optional[str] = None


class ErrorResponse(BaseModel):
    """
    Réponse standard pour toutes les erreurs de l'API.
    Retournée par les exception handlers.

    Exemple FK :
        {
          "success": false,
          "message": "La direction spécifiée n'existe pas.",
          "error_code": "DIRECTION_NOT_FOUND",
          "field": "direction_id",
          "value": "DIR-DSI-001",
          "hint": "Vérifiez que direction_id est un identifiant valide."
        }

    Exemple validation :
        {
          "success": false,
          "message": "Les données fournies sont invalides.",
          "error_code": "VALIDATION_ERROR",
          "details": [
            { "field": "email", "message": "Adresse email invalide.", "type": "value_error.email" }
          ]
        }
    """
    success: bool = False
    message: str
    error_code: str
    field: Optional[str] = None
    value: Optional[Any] = None
    hint: Optional[str] = None
    details: Optional[List[ValidationErrorDetail]] = None
