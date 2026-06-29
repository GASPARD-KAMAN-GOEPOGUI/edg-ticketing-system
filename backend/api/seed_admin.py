"""
Seed du compte administrateur par défaut.
Appelé au démarrage — crée un admin si aucun compte admin n'existe en base.
Idempotent : ne fait rien si un admin existe déjà.
"""
from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

# Identifiants du compte admin par défaut (à changer après la première connexion)
_DEFAULT_ADMIN = {
    "name":            "Administrateur EDG",
    "email":           "admin@edg.gn",
    "password":        "Admin@EDG2024!",
    "role":            "admin",
    "account_status":  "active",
    "is_edg_employee": True,
    "email_verified":  True,
    "status":          True,
}


async def seed_admin(session: AsyncSession) -> None:
    """Crée un compte admin par défaut si aucun n'existe."""
    from api.repositories import AccountRepository
    from api.core.security import hash_password

    repo = AccountRepository(session)
    items, _ = await repo.list(filters={"role": "admin"}, limit=1)
    if items:
        logger.debug("seed_admin: admin déjà présent (id=%s)", items[0].id)
        return

    data = dict(_DEFAULT_ADMIN)
    plain = data.pop("password")
    data["password_hash"] = hash_password(plain)
    admin = await repo.create(data)
    logger.info(
        "✅ seed_admin: compte admin créé — id=%s email=%s  /!\\  "
        "Changez le mot de passe après la première connexion.",
        admin.id,
        admin.email,
    )
