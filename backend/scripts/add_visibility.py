"""
Migration : ajout du champ visibility sur notification et announcement.
- visibility ENUM('public','admin_only') NOT NULL DEFAULT 'public'
Les alertes sécurité seront tagguées admin_only par le code applicatif.
"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

STMTS = [
    (
        "notification",
        "ALTER TABLE `notification` ADD COLUMN `visibility` ENUM('public','admin_only') "
        "NOT NULL DEFAULT 'public' AFTER `is_read`",
    ),
    (
        "announcement",
        "ALTER TABLE `announcement` ADD COLUMN `visibility` ENUM('public','admin_only') "
        "NOT NULL DEFAULT 'public' AFTER `attachment_name`",
    ),
]


async def run_stmts(session, stmts):
    from sqlalchemy import text
    print("\n=== visibility : ajout sur notification + announcement ===")
    for table, sql in stmts:
        short = sql[:120].replace('\n', ' ')
        try:
            await session.execute(text(sql))
            await session.commit()
            print(f"  OK    [{table}] {short}")
        except Exception as e:
            err = str(e)
            if (
                "Duplicate column" in err
                or "already exists" in err
                or "Duplicate key name" in err
            ):
                print(f"  SKIP  [{table}] colonne deja presente")
            else:
                print(f"  ERR   [{table}] {err[:300]}")
                raise


async def verify(session):
    from sqlalchemy import text
    print("\n--- Verification ---")
    for table in ("notification", "announcement"):
        r = await session.execute(
            text(f"SHOW COLUMNS FROM `{table}` LIKE 'visibility'")
        )
        row = r.fetchone()
        status = "OK" if row else "ABSENT"
        print(f"  {table}.visibility : {status}")


async def main():
    from api.configs.Database import engine
    from sqlalchemy.ext.asyncio import AsyncSession
    async with AsyncSession(engine) as s:
        await run_stmts(s, STMTS)
    async with AsyncSession(engine) as s:
        await verify(s)
    print("\nMigration terminee.")


asyncio.run(main())
