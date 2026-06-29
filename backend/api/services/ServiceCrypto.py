"""
Chiffrement/déchiffrement des champs sensibles — EDG Connect.

Utilise Fernet (AES-128-CBC + HMAC-SHA256) de la bibliothèque `cryptography`.
La clé doit être une chaîne base64-url de 32 octets générée par Fernet.generateKey().

Configuration :
  ENCRYPTION_KEY=<clé Fernet 32-bytes base64-url>   dans backend/.env
  Si ENCRYPTION_KEY est vide, les fonctions retournent les valeurs en clair
  (mode dégradé — pratique pour le développement).

Usage :
  from api.services.ServiceCrypto import encrypt_field, decrypt_field

  # Dans ServiceRequest.create() avant d'écrire en base :
  data["description"] = encrypt_field(data["description"])

  # Dans ServiceRequest._serialize() après lecture :
  item["description"] = decrypt_field(item["description"])

Générer une clé :
  python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
"""
from __future__ import annotations

import logging
from functools import lru_cache

logger = logging.getLogger(__name__)

# Marqueur préfixe pour distinguer les valeurs chiffrées des valeurs en clair
_PREFIX = "enc:"


@lru_cache(maxsize=1)
def _get_fernet():
    """Retourne une instance Fernet ou None si la clé n'est pas configurée."""
    try:
        from api.configs.Environment import get_environment
        key = get_environment().ENCRYPTION_KEY
        if not key:
            return None
        from cryptography.fernet import Fernet
        return Fernet(key.encode() if isinstance(key, str) else key)
    except Exception as exc:
        logger.error("ServiceCrypto : impossible d'initialiser Fernet : %s", exc)
        return None


def encrypt_field(value: str | None) -> str | None:
    """
    Chiffre `value` avec Fernet.
    Retourne une chaîne préfixée par 'enc:' (base64-url).
    Si la clé n'est pas configurée ou si value est None/vide, retourne value inchangé.
    """
    if not value:
        return value
    f = _get_fernet()
    if f is None:
        return value
    try:
        encrypted = f.encrypt(value.encode("utf-8")).decode("ascii")
        return f"{_PREFIX}{encrypted}"
    except Exception as exc:
        logger.warning("ServiceCrypto : chiffrement échoué : %s", exc)
        return value


def decrypt_field(value: str | None) -> str | None:
    """
    Déchiffre `value` si elle commence par le préfixe 'enc:'.
    Retourne la valeur en clair, ou value inchangé si non chiffré.
    """
    if not value or not value.startswith(_PREFIX):
        return value
    f = _get_fernet()
    if f is None:
        logger.warning("ServiceCrypto : valeur chiffrée mais ENCRYPTION_KEY absent.")
        return value
    try:
        token = value[len(_PREFIX):].encode("ascii")
        return f.decrypt(token).decode("utf-8")
    except Exception as exc:
        logger.warning("ServiceCrypto : déchiffrement échoué : %s", exc)
        return value
