"""
Script principal de seed demo — a executer UNE FOIS apres creation de la base.

Ordre d'execution :
  1. seed_demo_workflow.py  — comptes demo + ticket 1 (VPN / RESOLVED)
  2. seed_tickets_2_3.py    — tickets 2 (SAP/CLOSED) et 3 (Badge/CLOSED+reouverture)

Pre-requis :
  - Base de donnees creee et vide (CREATE DATABASE edg_ticketing)
  - Backend demarre au moins une fois (pour que create_all + seed_references s'executent)
    OU alembic upgrade head execute

Usage :
  cd backend
  .\\venv\\Scripts\\Activate.ps1
  python scripts/seed_all_demo.py
"""

import asyncio, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


async def run_all():
    print("=" * 65)
    print("SEED COMPLET — EDG Connect Demo")
    print("=" * 65)

    # Import et execution de seed_demo_workflow
    print("\n>>> ETAPE 1 : Ticket 1 + comptes demo")
    from scripts.seed_demo_workflow import main as seed1
    await seed1()

    # Import et execution de seed_tickets_2_3
    print("\n>>> ETAPE 2 : Tickets 2 & 3")
    from scripts.seed_tickets_2_3 import main as seed2
    await seed2()

    print()
    print("=" * 65)
    print("SEED COMPLET TERMINE")
    print("=" * 65)
    print()
    print("3 tickets crees avec workflow complet (logique edgrh) :")
    print("  EDG-2026-00001 : VPN       RESOLVED  (a cloturer par Blaise)")
    print("  EDG-2026-00002 : SAP-FI    CLOSED    (CSAT 5/5)")
    print("  EDG-2026-00003 : Badge     CLOSED    (CSAT 3/5, rejet+reouverture)")
    print()
    print("IDENTIFIANTS (mot de passe : Edg@2024!)")
    print("-" * 65)
    print("  user      blaise@gmail.com")
    print("  user      komano@gmail.com")
    print("  agent     fatoumata@gmail.com")
    print("  chief     chef.dsi@edg.gn")
    print("  director  diaby@gmail.com")
    print("  dg        gasparndkamangoepogui502@gmail.com")
    print("  admin     gaspardKamangoepogui@gmail.com")
    print("=" * 65)
    print()
    print("Lancez maintenant verify_db.py pour verifier les donnees :")
    print("  python scripts/verify_db.py")


if __name__ == "__main__":
    asyncio.run(run_all())
