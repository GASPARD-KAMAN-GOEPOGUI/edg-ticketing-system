"""Affiche les IDs des references (categories, statuts, priorites) en ASCII pur."""
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
        charset="utf8mb4",
    )
    async with conn.cursor() as cur:
        await cur.execute("SELECT id, code FROM request_category ORDER BY id")
        rows = await cur.fetchall()
        print("CATEGORIES:")
        for r in rows:
            print(f"  {r[0]} -> {r[1]}")

        await cur.execute("SELECT id, code FROM request_status ORDER BY id")
        rows = await cur.fetchall()
        print("STATUTS:")
        for r in rows:
            print(f"  {r[0]} -> {r[1]}")

        await cur.execute("SELECT id, slug FROM priority_definition ORDER BY id")
        rows = await cur.fetchall()
        print("PRIORITES:")
        for r in rows:
            print(f"  {r[0]} -> {r[1]}")

        await cur.execute("SELECT id, codename FROM unity ORDER BY id")
        rows = await cur.fetchall()
        print("UNITES:")
        for r in rows:
            label = r[1].encode('ascii', errors='replace').decode()
            print(f"  {r[0]} -> {label}")
    conn.close()

asyncio.run(check())
