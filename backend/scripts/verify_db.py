"""
Script de verification de la base de donnees EDG Support.

Verifie :
  1. Tables existantes (schema)
  2. Donnees de reference (statuts, categories, priorites)
  3. Comptes utilisateurs demo
  4. Tickets et leur statut
  5. Workflow + workflow_detail (logique edgrh)
     - status=1 (soft-delete)
     - activated=1 (traite)
     - accepted=1 (complete) / 0 (rejet) / NULL (en attente)
  6. CSAT (appreciation)
  7. Notifications

Usage (depuis backend, venv active) :
    python scripts/verify_db.py
"""

import asyncio, json, os, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")
import aiomysql

OK   = "[OK]"
WARN = "[WARN]"
ERR  = "[ERR]"
SEP  = "-" * 65


def _accepted_label(val) -> str:
    if val is None:
        return "NULL (en attente)"
    return "1 (complete/approuve)" if val else "0 (rejet/negatif)"


async def main():
    conn = await aiomysql.connect(
        host=os.getenv("DATABASE_HOSTNAME", "localhost"),
        port=int(os.getenv("DATABASE_PORT", 3306)),
        db=os.getenv("DATABASE_NAME"),
        user=os.getenv("DATABASE_USERNAME"),
        password=os.getenv("DATABASE_PASSWORD", ""),
        charset="utf8mb4",
    )

    errors: list[str] = []

    async with conn.cursor() as cur:

        # ── 1. Tables ─────────────────────────────────────────────────────────
        print("\n" + SEP)
        print("1. SCHEMA — TABLES")
        print(SEP)

        required_tables = [
            "account", "unity", "organigram", "request", "request_status",
            "request_category", "priority_definition", "workflow", "workflow_detail",
            "notification", "appreciation", "attachment", "task",
        ]
        await cur.execute("SHOW TABLES")
        existing = {row[0] for row in await cur.fetchall()}

        for t in required_tables:
            if t in existing:
                print(f"  {OK} {t}")
            else:
                print(f"  {ERR} {t} MANQUANTE")
                errors.append(f"Table manquante : {t}")

        # ── 2. Donnees de reference ───────────────────────────────────────────
        print("\n" + SEP)
        print("2. DONNEES DE REFERENCE")
        print(SEP)

        ref_checks = [
            ("request_status", ["new", "qualifying", "qualified", "assigned",
                                "in_progress", "pending", "escalated",
                                "resolved", "closed", "rejected", "reopened"]),
            ("request_category", ["acces_applicatif", "logiciel", "incident",
                                  "maintenance_si", "habilitation"]),
            ("priority_definition", ["low", "medium", "high", "critical"]),
        ]

        for table, codes in ref_checks:
            col = "slug" if table == "priority_definition" else "code"
            await cur.execute(
                f"SELECT {col} FROM {table} WHERE deleted_at IS NULL"
            )
            found = {row[0] for row in await cur.fetchall()}
            missing = [c for c in codes if c not in found]
            if missing:
                print(f"  {ERR} {table} : manquants = {missing}")
                errors.append(f"Reference manquante dans {table}: {missing}")
            else:
                print(f"  {OK} {table} ({len(found)} entrees)")

        # ── 3. Comptes demo ───────────────────────────────────────────────────
        print("\n" + SEP)
        print("3. COMPTES DEMO")
        print(SEP)

        demo_accounts = [
            ("blaise@gmail.com",                   "user",     14, "Blaise GOEPOGUI"),
            ("komano@gmail.com",                   "user",      6, "Mohammed Komano"),
            ("fatoumata@gmail.com",                "agent",    14, "Fatoumata Conte"),
            ("chef.dsi@edg.gn",                    "chief",    14, "Mamadou Diallo"),
            ("diaby@gmail.com",                    "director",  6, "Diaby Directeur"),
            ("gasparndkamangoepogui502@gmail.com", "dg",        1, "Toure DG"),
            ("gaspardKamangoepogui@gmail.com",     "admin",     6, "GOEPOGUI Admin"),
        ]

        for email, expected_role, expected_unity, expected_name in demo_accounts:
            await cur.execute(
                "SELECT id, role, unity_id, name, account_status FROM account WHERE email=%s LIMIT 1",
                (email,)
            )
            row = await cur.fetchone()
            if not row:
                print(f"  {ERR} {email} INTROUVABLE")
                errors.append(f"Compte manquant : {email}")
                continue
            acc_id, role, unity_id, name, status_val = row
            issues = []
            if role != expected_role:
                issues.append(f"role={role} (attendu {expected_role})")
            if unity_id != expected_unity:
                issues.append(f"unity_id={unity_id} (attendu {expected_unity})")
            if status_val != "active":
                issues.append(f"account_status={status_val}")
            if issues:
                print(f"  {WARN} {email} (id={acc_id}) — {', '.join(issues)}")
            else:
                print(f"  {OK} {email} | {role} | unity={unity_id} | {name}")

        # ── 4. Tickets ────────────────────────────────────────────────────────
        print("\n" + SEP)
        print("4. TICKETS DE DEMO")
        print(SEP)

        expected_tickets = {
            "EDG-2026-00001": "resolved",
            "EDG-2026-00002": "closed",
            "EDG-2026-00003": "closed",
        }

        for ref, expected_status in expected_tickets.items():
            await cur.execute(
                """SELECT r.id, rs.code, r.unity_id, r.requester_name
                   FROM request r
                   JOIN request_status rs ON rs.id = r.request_status_id
                   WHERE r.ref=%s AND r.deleted_at IS NULL LIMIT 1""",
                (ref,)
            )
            row = await cur.fetchone()
            if not row:
                print(f"  {ERR} {ref} INTROUVABLE")
                errors.append(f"Ticket manquant : {ref}")
                continue
            req_id, status_code, unity_id, requester = row
            ok = status_code == expected_status
            mark = OK if ok else WARN
            print(f"  {mark} {ref} | statut={status_code} | unity_id={unity_id} | par={requester}")
            if not ok:
                errors.append(f"{ref} : statut attendu={expected_status}, trouve={status_code}")

        # ── 5. Workflow + workflow_detail ─────────────────────────────────────
        print("\n" + SEP)
        print("5. WORKFLOW & WORKFLOW_DETAIL (logique edgrh)")
        print(SEP)

        await cur.execute(
            """SELECT r.ref, w.id, w.workflow_status,
                      COUNT(wd.id) as total_steps,
                      SUM(wd.status) as active_status,
                      SUM(wd.activated) as activated_count,
                      SUM(CASE WHEN wd.accepted IS NULL THEN 1 ELSE 0 END) as pending_count,
                      SUM(CASE WHEN wd.accepted = 1 THEN 1 ELSE 0 END) as accepted_count,
                      SUM(CASE WHEN wd.accepted = 0 THEN 1 ELSE 0 END) as rejected_count,
                      SUM(CASE WHEN wd.unity_id IS NULL THEN 1 ELSE 0 END) as null_unity,
                      SUM(CASE WHEN wd.infos IS NULL THEN 1 ELSE 0 END) as null_infos
               FROM request r
               JOIN workflow w ON w.request_id = r.id AND w.deleted_at IS NULL
               JOIN workflow_detail wd ON wd.workflow_id = w.id AND wd.deleted_at IS NULL
               WHERE r.ref IN ('EDG-2026-00001','EDG-2026-00002','EDG-2026-00003')
               GROUP BY r.ref, w.id, w.workflow_status
               ORDER BY r.ref"""
        )
        rows = await cur.fetchall()

        if not rows:
            print(f"  {ERR} Aucun workflow_detail trouve !")
            errors.append("Aucun workflow_detail")
        else:
            for (ref, wf_id, wf_status, total, act_status,
                 activated, pending, accepted, rejected, null_unity, null_infos) in rows:
                print(f"\n  Ticket {ref} | workflow_id={wf_id} | wf_status={wf_status}")
                print(f"    Total etapes     : {total}")
                print(f"    status=1         : {int(act_status)}/{total}  "
                      f"{'(tous actifs)' if act_status == total else ERR + ' PROBLEME'}")
                print(f"    activated=1      : {int(activated)}/{total}  "
                      f"{'(toutes traitees)' if activated == total else WARN + ' certaines inactives'}")
                print(f"    accepted=1       : {int(accepted)} etapes completees")
                print(f"    accepted=0       : {int(rejected)} etapes rejet")
                print(f"    accepted=NULL    : {int(pending)} etapes en attente")
                print(f"    unity_id rempli  : {int(total - null_unity)}/{total}  "
                      f"{'(OK)' if null_unity == 0 else ERR + ' NULLs!'}")
                print(f"    infos rempli     : {int(total - null_infos)}/{total}  "
                      f"{'(OK)' if null_infos == 0 else ERR + ' NULLs!'}")

                # Erreurs
                if act_status != total:
                    errors.append(f"{ref}: status!=1 pour certaines etapes")
                if null_unity > 0:
                    errors.append(f"{ref}: {null_unity} workflow_detail sans unity_id")
                if null_infos > 0:
                    errors.append(f"{ref}: {null_infos} workflow_detail sans infos")

        # Detail par etape
        print("\n  Detail des etapes par ticket :")
        await cur.execute(
            """SELECT r.ref, wd.event_type, wd.actor_name,
                      wd.status, wd.activated, wd.accepted, wd.unity_id, wd.infos
               FROM request r
               JOIN workflow w ON w.request_id = r.id AND w.deleted_at IS NULL
               JOIN workflow_detail wd ON wd.workflow_id = w.id AND wd.deleted_at IS NULL
               WHERE r.ref IN ('EDG-2026-00001','EDG-2026-00002','EDG-2026-00003')
               ORDER BY r.ref, wd.created_at"""
        )
        detail_rows = await cur.fetchall()
        prev_ref = None
        for ref, etype, actor, st, activated, accepted, unity_id, infos_raw in detail_rows:
            if ref != prev_ref:
                print(f"\n  === {ref} ===")
                prev_ref = ref
            inf = {}
            if infos_raw:
                try:
                    inf = json.loads(infos_raw) if isinstance(infos_raw, str) else infos_raw
                except Exception:
                    pass
            estat = inf.get("event_status", "?")
            srole = inf.get("source_role", "?")
            drole = " dest=" + inf["dest_role"] if "dest_role" in inf else ""
            ispub = " pub=" + str(inf["is_public"]) if "is_public" in inf else ""

            # Verifier coherence
            checks = []
            if st != 1:
                checks.append(f"status={st}!")
            if not activated:
                checks.append("activated=0!")

            acc_str = "1" if accepted else ("0" if accepted is not None else "NULL")
            warn_str = " " + " ".join(checks) if checks else ""
            print(f"    {etype:<20} uid={unity_id} acc={acc_str} {srole}{drole}{ispub} [{estat}]{warn_str}")

        # ── 6. CSAT ────────────────────────────────────────────────────────────
        print("\n" + SEP)
        print("6. CSAT (appreciation)")
        print(SEP)

        await cur.execute(
            """SELECT r.ref, a.rating, a.resolved_confirmed, a.author_type
               FROM appreciation a
               JOIN request r ON r.id = a.request_id
               WHERE r.ref IN ('EDG-2026-00002','EDG-2026-00003')
               AND a.deleted_at IS NULL"""
        )
        csat_rows = await cur.fetchall()
        if not csat_rows:
            print(f"  {ERR} Aucun CSAT trouve")
            errors.append("CSAT manquant pour tickets 2 et 3")
        for ref, rating, confirmed, author_type in csat_rows:
            print(f"  {OK} {ref} : rating={rating}/5 | confirmed={confirmed} | type={author_type}")

        # ── 7. Notifications ───────────────────────────────────────────────────
        print("\n" + SEP)
        print("7. NOTIFICATIONS")
        print(SEP)

        await cur.execute(
            """SELECT r.ref, COUNT(n.id) as nb
               FROM notification n
               JOIN request r ON r.id = n.request_id
               WHERE r.ref IN ('EDG-2026-00001','EDG-2026-00002','EDG-2026-00003')
               AND n.deleted_at IS NULL
               GROUP BY r.ref"""
        )
        notif_rows = await cur.fetchall()
        for ref, nb in notif_rows:
            print(f"  {OK} {ref} : {nb} notifications")

        # ── Bilan ──────────────────────────────────────────────────────────────
        print("\n" + SEP)
        print("BILAN")
        print(SEP)

        if not errors:
            print(f"  {OK} TOUT EST CORRECT — base prete pour les tests")
        else:
            print(f"  {ERR} {len(errors)} PROBLEME(S) DETECTE(S) :")
            for e in errors:
                print(f"    - {e}")

        print()
        print("  Logique edgrh verifiee :")
        print("  workflow_detail.status    = 1 (soft-delete = actif)")
        print("  workflow_detail.activated = 1 (etape traitee)")
        print("  workflow_detail.accepted  = 1 (complete) / 0 (rejet) / NULL (attente)")
        print("  workflow_detail.unity_id  = unite de l'etape (14=DSI-DEX)")
        print("  workflow_detail.infos     = JSON { event_status, source_role, ...}")
        print(SEP)

    conn.close()


if __name__ == "__main__":
    asyncio.run(main())
