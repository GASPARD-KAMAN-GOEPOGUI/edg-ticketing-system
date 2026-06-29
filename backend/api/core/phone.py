"""Utilitaires de normalisation des numéros de téléphone — EDG Connect (Guinée)."""
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


def is_phone_identifier(identifier: str) -> bool:
    """
    Retourne True si l'identifiant ressemble à un numéro de téléphone
    (contient surtout des chiffres, +, espaces, tirets).
    """
    stripped = re.sub(r"[\s\-\+\.\(\)]", "", identifier)
    return bool(stripped) and stripped.isdigit()
