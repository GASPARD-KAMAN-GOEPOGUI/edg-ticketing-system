import asyncio, os, sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")
import aiomysql

async def check():
    conn = await aiomysql.connect(
        host=os.getenv("DATABASE_HOSTNAME", "localhost"),
        port=int(os.getenv("DATABASE_PORT", 3306)),
        db=os.getenv("DATABASE_NAME"),
        user=os.getenv("DATABASE_USERNAME"),
        password=os.getenv("DATABASE_PASSWORD", ""),
    )
    async with conn.cursor() as cur:
        # Unities
        await cur.execute("SELECT id, label, codename, aleas FROM unity ORDER BY id")
        rows = await cur.fetchall()
        print("=== UNITES ===")
        for r in rows:
            print(f"  id={r[0]}  label={r[1]}  codename={r[2]}  aleas={r[3]}")
        print()

        # References: categories, statuts, priorites
        await cur.execute("SELECT id, code, label FROM request_category ORDER BY id")
        rows = await cur.fetchall()
        print("=== CATEGORIES ===")
        for r in rows:
            print(f"  id={r[0]}  code={r[1]}  label={r[2]}")
        print()

        await cur.execute("SELECT id, code FROM request_status ORDER BY id")
        rows = await cur.fetchall()
        print("=== STATUTS ===")
        for r in rows:
            print(f"  id={r[0]}  code={r[1]}")
        print()

        await cur.execute("SELECT id, slug FROM priority_definition ORDER BY id")
        rows = await cur.fetchall()
        print("=== PRIORITES ===")
        for r in rows:
            print(f"  id={r[0]}  slug={r[1]}")

    conn.close()

asyncio.run(check())
