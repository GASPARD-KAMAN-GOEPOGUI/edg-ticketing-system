"""Utilitaires de normalisation des numéros de téléphone — EDG Support (Guinée)."""
from __future__ import annotations

import re

_GUINEA_CODE = "224"


def normalize_phone(raw: str | None, country_code: str = _GUINEA_CODE) -> str | None:
    """
    Normalise un numéro de téléphone guinéen vers le format +224XXXXXXXXX.

    Variantes acceptées :
      +224622123456   → +224622123456  (déjà normalisé)
      224622123456    → +224622123456  (indicatif sans +)
      00224622123456  → +224622123456  (format 00 + indicatif)
      622123456       → +224622123456  (numéro local uniquement)

    Retourne None si raw est None ou vide.
    """
    if not raw:
        return raw
    # Supprimer espaces, tirets, points, parenthèses
    digits = re.sub(r"[^\d]", "", raw)
    if not digits:
        return raw
    prefix_00 = "00" + country_code          # 00224
    prefix_cc = country_code                  # 224
    if digits.startswith(prefix_00):
        local = digits[len(prefix_00):]
    elif digits.startswith(prefix_cc) and len(digits) > 9:
        # Plus de 9 chiffres débutant par l'indicatif → indicatif inclus
        local = digits[len(prefix_cc):]
    else:
        # Numéro local (≤ 9 chiffres ou ne commençant pas par l'indicatif)
        local = digits
    return f"+{country_code}{local}"


_GUINEA_MOBILE_RE = re.compile(r"^6\d{8}$")

PHONE_FORMAT_HINT = "+224 6XX XX XX XX, 224 6XX XX XX XX ou 6XX XX XX XX"


def validate_guinea_phone(raw: str | None) -> str | None:
    """
    Valide puis normalise un numéro de téléphone mobile guinéen.

    Formats acceptés (espaces/tirets ignorés) : +224 6XX XX XX XX,
    224 6XX XX XX XX, 6XX XX XX XX — un numéro local à 9 chiffres commençant
    par 6, avec ou sans l'indicatif 224.

    Retourne None si raw est None/vide (champ optionnel). Lève ValueError
    si raw est renseigné mais ne correspond à aucun de ces formats.
    """
    if raw is None or not raw.strip():
        return None
    normalized = normalize_phone(raw) or raw
    local = normalized[len(_GUINEA_CODE) + 1:] if normalized.startswith(f"+{_GUINEA_CODE}") else normalized
    if not _GUINEA_MOBILE_RE.match(local):
        raise ValueError(
            f"Numéro de téléphone invalide. Formats acceptés : {PHONE_FORMAT_HINT}."
        )
    return normalized


def is_phone_identifier(identifier: str) -> bool:
    """
    Retourne True si l'identifiant ressemble à un numéro de téléphone
    (contient surtout des chiffres, +, espaces, tirets).
    """
    stripped = re.sub(r"[\s\-\+\.\(\)]", "", identifier)
    return bool(stripped) and stripped.isdigit()
