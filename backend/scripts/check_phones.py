"""Vérifie les comptes avec numéro de téléphone."""
import asyncio
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))


async def main():
    from api.configs.Database import engine
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy import text
    async with AsyncSession(engine) as s:
        r = await s.execute(text(
            "SELECT id, email, phone, role FROM account ORDER BY id"
        ))
        rows = r.fetchall()
        print("=== Tous les comptes ===")
        for row in rows:
            print(f"  id={row.id}  role={row.role}  email={row.email}  phone={row.phone!r}")


asyncio.run(main())
