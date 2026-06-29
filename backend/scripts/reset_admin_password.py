"""
Réinitialise le mot de passe du compte admin (id=2 ou premier compte admin trouvé).
Usage :  pipenv run python scripts/reset_admin_password.py
"""
import asyncio
import sys
import os

sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

NEW_PASSWORD = "Admin@EDG2024!"


async def main():
    from api.core.security import hash_password
    from api.configs.Database import engine
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy import text
    async with AsyncSession(engine) as session:
        result = await session.execute(
            text("SELECT id, email, role FROM account WHERE role='admin' AND deleted_at IS NULL LIMIT 5")
        )
        admins = result.fetchall()

        if not admins:
            print("❌ Aucun compte admin trouvé en base.")
            return

        print("Comptes admin trouvés :")
        for row in admins:
            print(f"  id={row.id}  email={row.email}  role={row.role}")

        target = admins[0]
        new_hash = hash_password(NEW_PASSWORD)
        await session.execute(
            text("UPDATE account SET password_hash = :h WHERE id = :id"),
            {"h": new_hash, "id": target.id},
        )
        await session.commit()
        print(f"\n✅ Mot de passe réinitialisé pour {target.email} (id={target.id})")
        print(f"   Nouveau mot de passe : {NEW_PASSWORD}")


if __name__ == "__main__":
    asyncio.run(main())
