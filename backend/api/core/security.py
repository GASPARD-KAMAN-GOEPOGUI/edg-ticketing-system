"""
Utilitaires de sécurité — JWT (HS256) + hachage Argon2.

Tokens :
  access  — courte durée (30 min), porte { sub, email, role, session_id }
  refresh — longue durée (7 j), porte { sub, session_id }

Le champ `jti` (JWT ID, uuid4) permet la révocation dans la blacklist.
Le champ `session_id` (uuid4) permet la validation de session unique (WhatsApp-like).
"""
from __future__ import annotations

import uuid
from datetime import datetime, timedelta, timezone
from typing import Any

from jose import JWTError, jwt
from passlib.context import CryptContext

from api.configs.Environment import get_environment
from api.core.exceptions import UnauthorizedException

_env = get_environment()

# ── Argon2 password context ───────────────────────────────────────────────────

_pwd_ctx = CryptContext(schemes=["argon2"], deprecated="auto")


def hash_password(plain: str) -> str:
    """Hache un mot de passe avec Argon2id."""
    return _pwd_ctx.hash(plain)


def verify_password(plain: str, hashed: str) -> bool:
    """Vérifie un mot de passe contre son hash Argon2."""
    return _pwd_ctx.verify(plain, hashed)


# ── JWT helpers ───────────────────────────────────────────────────────────────

def _build_token(payload: dict[str, Any], expire_delta: timedelta) -> str:
    now = datetime.now(timezone.utc)
    payload = {
        **payload,
        "iat": now,
        "exp": now + expire_delta,
        "jti": str(uuid.uuid4()),
    }
    return jwt.encode(payload, _env.SECRET_KEY, algorithm=_env.ALGORITHM)


def create_access_token(account_id: int, email: str, role: str, session_id: str) -> str:
    """Crée un access token portant le session_id pour la validation de session unique."""
    return _build_token(
        {
            "sub": str(account_id),
            "email": email,
            "role": role,
            "session_id": session_id,
            "type": "access",
        },
        timedelta(minutes=_env.ACCESS_TOKEN_EXPIRE_MINUTES),
    )


def create_refresh_token(account_id: int, session_id: str) -> str:
    """Crée un refresh token portant le session_id pour valider la session lors du refresh."""
    return _build_token(
        {"sub": str(account_id), "session_id": session_id, "type": "refresh"},
        timedelta(days=_env.REFRESH_TOKEN_EXPIRE_DAYS),
    )


def decode_token(token: str) -> dict[str, Any]:
    """
    Décode et valide un JWT.
    Lève UnauthorizedException si le token est invalide ou expiré.
    """
    try:
        return jwt.decode(token, _env.SECRET_KEY, algorithms=[_env.ALGORITHM])
    except JWTError as exc:
        raise UnauthorizedException("Jeton invalide ou expiré.") from exc


def access_token_expire_seconds() -> int:
    return _env.ACCESS_TOKEN_EXPIRE_MINUTES * 60
