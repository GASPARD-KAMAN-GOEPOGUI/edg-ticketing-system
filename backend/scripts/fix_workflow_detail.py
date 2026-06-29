"""
Correctif traçabilité workflow_detail — tickets EDG-2026-00001/00002/00003

Champs manquants dans les seeds initiaux :
  - unity_id   : NULL -> 14 (DSI-DEX) pour toutes les étapes
  - infos      : NULL -> JSON { event_status, source_role, dest_role?, is_public? }
  - event_type : "status_change" -> type canonique (qualifying / in_progress / reopened …)
               : "comment"       -> "comment_added"

Usage (depuis backend, venv active) :
    python scripts/fix_workflow_detail.py
"""

import asyncio, json, os, re, sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import aiomysql

UNITY_DSI_DEX = 14

# Mapping event_status par event_type final
_STATUS_FOR_ETYPE = {
    "created":        "new",
    "qualifying":     "qualifying",
    "qualified":      "qualified",
    "assigned":       "assigned",
    "in_progress":    "in_progress",
    "pending":        "pending",
    "escalated":      "escalated",
    "chief_review":   "escalated",
    "reopen_request": "rejected",
    "reopened":       "reopened",
    "rejected":       "rejected",
    "resolved":       "resolved",
    "closed":         "closed",
    "comment_added":  "in_progress",
    "routed_to_service": "qualifying",
    "routed_to_support": "qualifying",
}

# Destination implicite par event_type
_DEST_FOR_ETYPE = {
    "escalated":         "chief",
    "chief_review":      "agent",
    "reopen_request":    "chief",
    "reopened":          "agent",
    "routed_to_service": "chief",
    "routed_to_support": "agent",
}


def _canonical_etype(etype: str, label: str) -> str:
    """Traduit 'status_change' / 'comment' en type canonique via le label."""
    if etype == "comment":
        return "comment_added"

    if etype != "status_change":
        return etype  # déjà canonique

    label_low = (label or "").lower()

    if "rouvert" in label_low or "reopened" in label_low:
        return "reopened"
    if "in_progress" in label_low or "reprise en traitement" in label_low or "reprise du traitement" in label_low:
        return "in_progress"
    if "qualifying" in label_low or "triage" in label_low:
        return "qualifying"
    if "qualified" in label_low:
        return "qualified"
    if "assigned" in label_low:
        return "assigned"
    if "pending" in label_low or "attente" in label_low:
        return "pending"

    # fallback : keep original (unexpected)
    return etype


def _build_infos(etype: str, source_role: str, comment: str | None) -> dict:
    infos: dict = {
        "event_status": _STATUS_FOR_ETYPE.get(etype, etype),
        "source_role":  source_role,
    }
    dest = _DEST_FOR_ETYPE.get(etype)
    if dest:
        infos["dest_role"] = dest

    if etype == "comment_added":
        comment_text = comment or ""
        infos["is_public"] = not comment_text.strip().startswith("[Interne]")

    return infos


async def main():
    conn = await aiomysql.connect(
        host=os.getenv("DATABASE_HOSTNAME", "localhost"),
        port=int(os.getenv("DATABASE_PORT", 3306)),
        db=os.getenv("DATABASE_NAME"),
        user=os.getenv("DATABASE_USERNAME"),
        password=os.getenv("DATABASE_PASSWORD", ""),
        charset="utf8mb4",
        autocommit=False,
    )

    async with conn.cursor() as cur:
        # Récupérer les rôles de tous les comptes (cache local)
        await cur.execute("SELECT id, role FROM account WHERE deleted_at IS NULL")
        role_map: dict[int, str] = {row[0]: row[1] for row in await cur.fetchall()}

        # Traiter les 3 tickets
        refs = ("EDG-2026-00001", "EDG-2026-00002", "EDG-2026-00003")
        await cur.execute(
            f"SELECT id, ref FROM request WHERE ref IN {refs} AND deleted_at IS NULL"
        )
        tickets = await cur.fetchall()

        if not tickets:
            print("[ERREUR] Aucun des tickets demo n'a ete trouve en base.")
            print("  -> Lancez d'abord : python scripts/seed_demo_workflow.py")
            print("  -> puis          : python scripts/seed_tickets_2_3.py")
            conn.close()
            return

        total_fixed = 0

        for req_id, ref in tickets:
            print(f"\n[{ref}] request_id={req_id}")

            # Trouver le workflow
            await cur.execute(
                "SELECT id FROM workflow WHERE request_id=%s AND deleted_at IS NULL "
                "ORDER BY id DESC LIMIT 1",
                (req_id,)
            )
            wf_row = await cur.fetchone()
            if not wf_row:
                print("  [SKIP] Pas de workflow trouvé")
                continue
            wf_id = wf_row[0]

            # Lire toutes les étapes
            await cur.execute(
                "SELECT id, event_type, label, comment, agent_id, unity_id, infos "
                "FROM workflow_detail WHERE workflow_id=%s AND deleted_at IS NULL "
                "ORDER BY created_at ASC",
                (wf_id,)
            )
            rows = await cur.fetchall()
            print(f"  workflow_id={wf_id} | {len(rows)} étapes trouvées")

            for (det_id, etype, label, comment, agent_id, unity_id_cur, infos_cur) in rows:
                # 1. Corriger event_type
                new_etype = _canonical_etype(etype or "", label or "")

                # 2. Rôle de l'acteur
                source_role = role_map.get(agent_id, "user") if agent_id else "user"

                # 3. Construire infos
                # Si infos existe déjà avec des clés métier → ne pas écraser
                existing = infos_cur if isinstance(infos_cur, dict) else {}
                if existing.get("event_status") and existing.get("source_role"):
                    new_infos_json = json.dumps(infos_cur)  # déjà complet
                else:
                    new_infos = _build_infos(new_etype, source_role, comment)
                    # Fusionner avec les métadonnées existantes (rule_id etc.)
                    merged = {**new_infos, **{k: v for k, v in existing.items() if k not in new_infos}}
                    new_infos_json = json.dumps(merged, ensure_ascii=False)

                # 4. Mettre à jour
                await cur.execute(
                    "UPDATE workflow_detail "
                    "SET event_type=%s, unity_id=%s, infos=%s "
                    "WHERE id=%s",
                    (new_etype, UNITY_DSI_DEX, new_infos_json, det_id)
                )

                changed = []
                if new_etype != etype:
                    changed.append(f"event_type: {etype!r} -> {new_etype!r}")
                if unity_id_cur != UNITY_DSI_DEX:
                    changed.append(f"unity_id: {unity_id_cur} -> {UNITY_DSI_DEX}")
                if not existing.get("event_status"):
                    changed.append("infos: [ajouté]")

                status_str = ", ".join(changed) if changed else "déjà correct"
                print(f"    #{det_id} {new_etype:<20} | {status_str}")
                total_fixed += 1

        await conn.commit()

    conn.close()

    print(f"\n{'='*60}")
    print(f"CORRECTIF APPLIQUE — {total_fixed} workflow_detail mis a jour")
    print(f"{'='*60}")
    print("  unity_id    -> 14 (DSI-DEX) pour toutes les etapes")
    print("  event_type  -> types canoniques CDC")
    print("  infos       -> JSON { event_status, source_role, dest_role?, is_public? }")
    print()
    print("Redemarrez le backend pour que les changements soient visibles.")


if __name__ == "__main__":
    asyncio.run(main())
