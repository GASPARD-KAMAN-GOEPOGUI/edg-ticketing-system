"""
Création ponctuelle d'un compte admin (admin@gmail.com), via AccountService.create()
(même chemin de code que POST /auth/register / /api/v1/users, y compris la
création côté plateforme centrale) — sans passer par le serveur HTTP en cours
d'exécution. Même pattern que scripts/link_first_admin.py.

Usage (depuis backend/, venv activé) :
    python scripts/create_admin_gmail.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


async def main():
    from sqlalchemy.ext.asyncio import AsyncSession
    from api.configs.Database import engine
    from api.services.ServiceAccount import AccountService

    async with AsyncSession(engine) as session:
        svc = AccountService(session)
        obj = await svc.create(
            {
                "name": "Admin",
                "firstname": "Admin",
                "email": "admin@gmail.com",
                "password": "0123456789",
                "role": "admin",
            },
            validate_org_assignment=False,
        )
        print(
            f"OK — compte local créé : id={obj.id} email={obj.email} "
            f"central_user_id={obj.central_user_id} central_user_uuid={obj.central_user_uuid}"
        )


asyncio.run(main())
