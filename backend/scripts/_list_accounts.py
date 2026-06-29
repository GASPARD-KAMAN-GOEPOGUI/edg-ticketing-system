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
        await cur.execute("SELECT id, name, email, role, account_status, unity_id, matricule FROM account ORDER BY role, id")
        rows = await cur.fetchall()
        print(f"{'ID':<5} {'Nom':<25} {'Email':<35} {'Role':<12} {'Statut':<10} {'Unity':<6} {'Matricule'}")
        print("-" * 110)
        for r in rows:
            print(f"  {r[0]:<3} {r[1]:<25} {r[2]:<35} {r[3]:<12} {r[4]:<10} {str(r[5]):<6} {r[6] or ''}")
        # Also list unities
        print()
        await cur.execute("SELECT id, name, code, type, parent_id FROM unity ORDER BY type, id")
        rows2 = await cur.fetchall()
        print(f"{'ID':<5} {'Nom':<30} {'Code':<15} {'Type':<12} {'Parent'}")
        print("-" * 75)
        for r in rows2:
            print(f"  {r[0]:<3} {r[1]:<30} {r[2]:<15} {r[3]:<12} {str(r[4]) or ''}")
    conn.close()

asyncio.run(check())
