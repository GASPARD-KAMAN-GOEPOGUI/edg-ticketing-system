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
    tables = ["request", "workflow", "workflow_detail", "task", "appreciation", "attachment", "notification"]
    async with conn.cursor() as cur:
        for t in tables:
            await cur.execute(f"SELECT COUNT(*) FROM `{t}`")
            (n,) = await cur.fetchone()
            print(f"  {t:<20} : {n} ligne(s)")
    conn.close()

asyncio.run(check())
