"""
Migration : ajout de firstname et phone sur la table account.
- firstname VARCHAR(200) NULL (nom de famille séparé du prénom)
- phone     VARCHAR(30)  NULL UNIQUE
Lance chaque statement séparément ; ignore les erreurs "already exists".
"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

STMTS = [
    # 1. Ajout de la colonne firstname après name
    "ALTER TABLE `account` ADD COLUMN `firstname` VARCHAR(200) NULL AFTER `name`",
    # 2. Ajout de la colonne phone après email
    "ALTER TABLE `account` ADD COLUMN `phone` VARCHAR(30) NULL AFTER `email`",
    # 3. Contrainte UNIQUE sur phone
    "ALTER TABLE `account` ADD UNIQUE INDEX `uk_account_phone` (`phone`)",
]


async def run_stmts(session, stmts: list[str]):
    from sqlalchemy import text
    print("\n=== account : ajout firstname + phone ===")
    for sql in stmts:
        short = sql[:100].replace('\n', ' ')
        try:
            await session.execute(text(sql))
            await session.commit()
            print(f"  OK    {short}")
        except Exception as e:
            err = str(e)
            if (
                "Duplicate column" in err
                or "already exists" in err
                or "Duplicate key name" in err
            ):
                print(f"  SKIP  {short}")
            else:
                print(f"  ERR   {short}")
                print(f"        {err[:300]}")
                raise


async def main():
    from api.configs.Database import engine
    from sqlalchemy.ext.asyncio import AsyncSession
    async with AsyncSession(engine) as s:
        await run_stmts(s, STMTS)

    # Vérification rapide
    from sqlalchemy.ext.asyncio import AsyncSession
    from sqlalchemy import text
    async with AsyncSession(engine) as s:
        r = await s.execute(text("SHOW COLUMNS FROM `account` LIKE 'firstname'"))
        fc = r.fetchone()
        r2 = await s.execute(text("SHOW COLUMNS FROM `account` LIKE 'phone'"))
        pc = r2.fetchone()
        print(f"\n✅ firstname : {'trouvé' if fc else '❌ ABSENT'}")
        print(f"✅ phone     : {'trouvé' if pc else '❌ ABSENT'}")

    print("\nMigration terminée.")


asyncio.run(main())
