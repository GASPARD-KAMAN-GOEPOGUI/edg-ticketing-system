import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

async def main():
    from api.configs.Database import engine
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy import text
    async with AsyncSession(engine) as s:
        r = await s.execute(text("SHOW COLUMNS FROM announcement"))
        cols_ann = [row[0] for row in r.fetchall()]
        print("announcement:", cols_ann)

        r = await s.execute(text("SHOW COLUMNS FROM request"))
        cols_req = [row[0] for row in r.fetchall()]
        print("request:", cols_req)

asyncio.run(main())
