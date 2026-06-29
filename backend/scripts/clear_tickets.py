"""
Vide tous les tickets (requests) et leurs données liées.
Conserve : comptes, références, annonces, articles, règles, SLA, etc.

Usage (depuis le dossier backend, venv activé) :
    python scripts/clear_tickets.py
"""

import asyncio
import os
import sys
from pathlib import Path

# Ajouter le dossier backend au path
sys.path.insert(0, str(Path(__file__).parent.parent))

from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import aiomysql


async def main():
    db_host = os.getenv("DATABASE_HOSTNAME", "localhost")
    db_port = int(os.getenv("DATABASE_PORT", "3306"))
    db_name = os.getenv("DATABASE_NAME", "edg_ticketing")
    db_user = os.getenv("DATABASE_USERNAME", "root")
    db_pass = os.getenv("DATABASE_PASSWORD", "")

    print(f"Connexion à {db_user}@{db_host}:{db_port}/{db_name} ...")

    conn = await aiomysql.connect(
        host=db_host,
        port=db_port,
        db=db_name,
        user=db_user,
        password=db_pass,
        autocommit=False,
    )

    async with conn.cursor() as cur:
        # Désactiver les contraintes FK temporairement
        await cur.execute("SET FOREIGN_KEY_CHECKS = 0;")

        tables_to_clear = [
            ("workflow_detail", "Détails workflow / historique"),
            ("workflow",        "Workflows"),
            ("task",            "Tâches"),
            ("appreciation",    "Appréciations CSAT"),
            ("attachment",      "Pièces jointes"),
            ("notification",    "Notifications liées aux tickets"),
            ("request",         "Tickets (requests)"),
        ]

        total = 0
        for table, label in tables_to_clear:
            await cur.execute(f"SELECT COUNT(*) FROM `{table}`;")
            (count,) = await cur.fetchone()
            await cur.execute(f"DELETE FROM `{table}`;")
            await cur.execute(f"ALTER TABLE `{table}` AUTO_INCREMENT = 1;")
            print(f"  [OK] {label:<35} {count} ligne(s) supprimee(s)")
            total += count

        # Reactiver les contraintes FK
        await cur.execute("SET FOREIGN_KEY_CHECKS = 1;")

        await conn.commit()
        print(f"\n[DONE] {total} ligne(s) supprimee(s) au total.")
        print("       Comptes, references, annonces, articles et regles conserves.")

    conn.close()


if __name__ == "__main__":
    asyncio.run(main())
