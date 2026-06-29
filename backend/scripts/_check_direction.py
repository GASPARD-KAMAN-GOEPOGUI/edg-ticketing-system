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
        print("=== COMPTES ET UNITES ===")
        await cur.execute("""
            SELECT a.id, a.name, a.email, a.role, a.unity_id, u.label, u.codename
            FROM account a
            LEFT JOIN unity u ON u.id = a.unity_id
            ORDER BY a.role, a.id
        """)
        for r in await cur.fetchall():
            codename = r[6] if r[6] else "AUCUNE"
            label = r[5] if r[5] else "AUCUNE"
            print(f"  id={r[0]} | {r[1]:<22} | role={r[3]:<10} | unity_id={str(r[4]):<4} | {codename} ({label})")

        print()
        print("=== ORGANIGRAMME (hierarchie DSI) ===")
        await cur.execute("""
            SELECT o.id, u.codename, u.label, p.codename as parent_code, o.depth, o.path
            FROM organigram o
            JOIN unity u ON u.id = o.unity_id
            LEFT JOIN unity p ON p.id = o.parent_unity_id
            WHERE o.path LIKE '%DSI%' OR u.codename = 'DSI'
            ORDER BY o.path
        """)
        for r in await cur.fetchall():
            print(f"  {r[1]:<12} parent={str(r[3]):<12} depth={r[4]} path={r[5]}")

        print()
        print("=== TICKETS ET LEUR UNITE CIBLE ===")
        await cur.execute("""
            SELECT r.id, r.ref, r.request_status_id, r.unity_id, u.codename,
                   a.name as requester, a.role as req_role, a2.unity_id as req_unity_id, u2.codename as req_codename
            FROM request r
            LEFT JOIN unity u ON u.id = r.unity_id
            LEFT JOIN account a ON a.id = r.requester_id
            LEFT JOIN unity u2 ON u2.id = a.unity_id
            LEFT JOIN account a2 ON a2.id = r.requester_id
            ORDER BY r.id
        """)
        for r in await cur.fetchall():
            print(f"  {r[1]} | statut_id={r[2]} | cible={r[3]}({r[4]}) | demandeur={r[5]}({r[6]}) unity={r[7]}({r[8]})")

    conn.close()

asyncio.run(check())
