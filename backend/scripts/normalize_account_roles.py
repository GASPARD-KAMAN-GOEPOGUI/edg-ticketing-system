import asyncio
import os
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
import aiomysql

load_dotenv(Path(__file__).parent.parent / ".env")

ROLE_MAP = {
    "agent": "chief-service",
    "chief": "chief-service",
    "chief-department": "chief-departement",
    "chief-dept": "chief-departement",
    "dg": "director",
}


def infer_role(name: str, email: str) -> str:
    text = f"{name} {email}".lower()
    if any(token in text for token in ("chief", "chef", "service")):
        return "chief-service"
    if any(token in text for token in ("agent", "support", "agt")):
        return "chief-service"
    if any(token in text for token in ("directeur", "director", "dir")):
        return "director"
    if "admin" in text:
        return "admin"
    return "user"


async def main() -> None:
    conn = await aiomysql.connect(
        host=os.getenv("DATABASE_HOSTNAME", "localhost"),
        port=int(os.getenv("DATABASE_PORT", 3306)),
        db=os.getenv("DATABASE_NAME", "edg_ticketing"),
        user=os.getenv("DATABASE_USERNAME", "root"),
        password=os.getenv("DATABASE_PASSWORD", ""),
        autocommit=True,
    )

    async with conn.cursor() as cur:
        await cur.execute("SHOW COLUMNS FROM account LIKE 'role'")
        column = await cur.fetchone()
        enum_def = column[1] if column else ""
        if "chief-service" not in enum_def:
            await cur.execute(
                "ALTER TABLE account MODIFY role ENUM('public','user','chief-service','chief-service','chief-departement','director','admin') NOT NULL"
            )
            print("account.role enum migrated to canonical values.")

        await cur.execute(
            "SELECT id, name, email, role FROM account WHERE role IN ('agent', 'chief', 'dg', '') OR role IS NULL"
        )
        rows = await cur.fetchall()
        total = len(rows)
        normalized = 0

        for account_id, name, email, current_role in rows:
            new_role = ROLE_MAP.get(current_role)
            if new_role is None and (current_role in ("", None)):
                new_role = infer_role(name or "", email or "")
            if new_role is None:
                continue
            await cur.execute(
                "UPDATE account SET role = %s WHERE id = %s AND (role = %s OR role = '')",
                (new_role, account_id, current_role),
            )
            normalized += 1

        print(f"account.role legacy cleanup: {total} legacy/blank rows processed; {normalized} rows normalized.")

        await cur.execute(
            "SELECT role, COUNT(*) AS cnt FROM account GROUP BY role ORDER BY role"
        )
        rows = await cur.fetchall()
        print("role distribution after cleanup:")
        for role, cnt in rows:
            print(f"  {role}: {cnt}")

    conn.close()


if __name__ == "__main__":
    asyncio.run(main())
