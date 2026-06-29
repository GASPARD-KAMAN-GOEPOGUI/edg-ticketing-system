"""
Ajoute un numéro de téléphone au compte admin pour test de connexion par tél.
Usage : pipenv run python scripts/add_phone_to_admin.py
"""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

ADMIN_EMAIL = "gaspardKamangoepogui@gmail.com"
PHONE = "+224622000001"   # ← modifiez ce numéro si besoin


async def main():
    from api.configs.Database import engine
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy import text

    async with AsyncSession(engine) as s:
        r = await s.execute(
            text("SELECT id, email, phone FROM account WHERE email = :email"),
            {"email": ADMIN_EMAIL},
        )
        account = r.fetchone()
        if not account:
            print(f"Compte introuvable : {ADMIN_EMAIL}")
            return

        print(f"Compte trouvé : id={account.id}  email={account.email}  phone actuel={account.phone!r}")

        await s.execute(
            text("UPDATE account SET phone = :phone WHERE id = :id"),
            {"phone": PHONE, "id": account.id},
        )
        await s.commit()
        print(f"✅ Téléphone mis à jour → {PHONE}")
        print(f"   Vous pouvez maintenant vous connecter avec : {PHONE}")


asyncio.run(main())
