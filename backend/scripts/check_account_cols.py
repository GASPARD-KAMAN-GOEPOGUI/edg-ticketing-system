import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

async def main():
    from api.configs.Database import engine
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy import text
    async with AsyncSession(engine) as s:
        r1 = await s.execute(text("SHOW COLUMNS FROM `account` LIKE 'firstname'"))
        r2 = await s.execute(text("SHOW COLUMNS FROM `account` LIKE 'phone'"))
        fc = r1.fetchone()
        pc = r2.fetchone()
        print("firstname:", fc)
        print("phone    :", pc)
        if fc and pc:
            print("OK - both columns present")
        else:
            print("MISSING COLUMNS")

asyncio.run(main())
