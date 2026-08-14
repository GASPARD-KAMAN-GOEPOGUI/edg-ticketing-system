"""
Rattachement ponctuel du tout premier compte admin à la plateforme centrale
manager-user, via AccountService.create() (même chemin de code que POST
/api/v1/users/) — sans passer par le serveur HTTP en cours d'exécution.

Usage (depuis backend/, venv activé) :
    python scripts/link_first_admin.py
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
                "name": "GOEPOGUI",
                "firstname": "GASPARD",
                "email": "gaspard@edg.com.gn",
                "password": "0123456789",
                "role": "admin",
                "unity_id": 16,
                "is_edg_employee": True,
            },
            validate_org_assignment=True,
        )
        print(
            f"OK — compte local créé : id={obj.id} email={obj.email} "
            f"central_user_id={obj.central_user_id} central_user_uuid={obj.central_user_uuid}"
        )


asyncio.run(main())
