"""
Seed du compte administrateur local par défaut.
Appelé au démarrage — crée un compte admin miroir si aucun n'existe en base.
Idempotent : ne fait rien si un admin existe déjà.

Ce compte n'a pas de mot de passe local (authentification déléguée à la
plateforme centrale manager-user) — il sert de compte de secours pour le
mode DISABLE_AUTH et de cible pour un rattachement central ultérieur
(central_user_id/central_user_uuid, voir gestion des comptes phase 2).
"""
from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

logger = logging.getLogger(__name__)

_DEFAULT_ADMIN = {
    "name":            "Administrateur EDG",
    "email":           "admin@edg.gn",
    "role":            "admin",
    "account_status":  "active",
    "is_edg_employee": True,
    "email_verified":  True,
    "status":          True,
}


async def seed_admin(session: AsyncSession) -> None:
    """Crée un compte admin local par défaut si aucun n'existe."""
    from api.repositories import AccountRepository

    repo = AccountRepository(session)
    items, _ = await repo.list(filters={"role": "admin"}, limit=1)
    if items:
        logger.debug("seed_admin: admin déjà présent (id=%s)", items[0].id)
        return

    admin = await repo.create(dict(_DEFAULT_ADMIN))
    logger.info(
        "✅ seed_admin: compte admin local créé — id=%s email=%s  /!\\  "
        "Rattachez-le à une identité centrale (central_user_id/central_user_uuid) "
        "pour permettre la connexion via manager-user.",
        admin.id,
        admin.email,
    )
