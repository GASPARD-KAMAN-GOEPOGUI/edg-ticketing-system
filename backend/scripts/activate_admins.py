import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

async def main():
    from api.configs.Database import engine
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy import text
    async with AsyncSession(engine) as s:
        await s.execute(text("UPDATE account SET status=1 WHERE role='admin'"))
        await s.commit()
        r = await s.execute(text("SELECT id, email, status FROM account WHERE role='admin'"))
        for row in r.fetchall():
            print(f"id={row.id}  email={row.email}  status={row.status}")
        print("OK - comptes admin actives")

asyncio.run(main())
