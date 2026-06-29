"""
Seed tickets EDG-2026-00002 et EDG-2026-00003

Logique workflow_detail (alignee avec edgrh) :
  status    = 1 (soft-delete = enregistrement actif)
  activated = 1 (etape qui a ete activee/traitee)
  accepted  = 1 (etape completee / decision positive)
            = 0 (etape rejetee / decision negative)
            = NULL (etape en attente de decision — uniquement etape courante)

Ticket 2 (CLOSED) — chemin PENDING :
  new -> qualifying -> qualified -> assigned -> in_progress
      -> pending (agent demande infos) -> user repond
      -> in_progress -> resolved -> closed + CSAT 5/5
  Toutes les etapes : activated=1, accepted=1 (workflow complet)

Ticket 3 (CLOSED) — chemin REJET + REOUVERTURE :
  Phase 1 : new -> qualifying -> rejected (hors perimetre DSI)
              "rejected" event : accepted=0 (decision negative)
  Phase 2 : reopen_request (employe) -> chief_review (valide) -> reopened
  Phase 3 : qualifying -> qualified -> assigned -> in_progress -> resolved -> closed + CSAT 3/5
  Toutes les etapes post-reouverture : activated=1, accepted=1

Usage (depuis backend, venv active) :
    python scripts/seed_tickets_2_3.py
"""

import asyncio, json, os, sys, uuid
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")
import aiomysql

# ── IDs comptes (verifies au runtime) ────────────────────────────────────────
UNITY_DSI_DEX = 14
UNITY_DSI     = 6


async def _get_account_id(cur, email: str) -> int:
    await cur.execute("SELECT id FROM account WHERE email=%s LIMIT 1", (email,))
    row = await cur.fetchone()
    if not row:
        raise RuntimeError(f"Compte introuvable : {email} — lancez d'abord seed_demo_workflow.py")
    return row[0]


async def _get_status_id(cur, code: str) -> int:
    await cur.execute(
        "SELECT id FROM request_status WHERE code=%s AND deleted_at IS NULL LIMIT 1", (code,)
    )
    row = await cur.fetchone()
    return row[0] if row else None


async def _get_priority_id(cur, slug: str) -> int:
    await cur.execute(
        "SELECT id FROM priority_definition WHERE slug=%s AND deleted_at IS NULL LIMIT 1", (slug,)
    )
    row = await cur.fetchone()
    return row[0] if row else None


async def _get_category_id(cur, code: str) -> int:
    await cur.execute(
        "SELECT id FROM request_category WHERE code=%s AND deleted_at IS NULL LIMIT 1", (code,)
    )
    row = await cur.fetchone()
    return row[0] if row else None


async def insert_notif(cur, recipient_id, request_id, req_uuid, ntype, title, body, ts):
    await cur.execute(
        """INSERT INTO notification
           (uuid, recipient_id, request_id, type, channel, title, body,
            action_label, action_url, is_read, visibility, status, created_at, updated_at)
           VALUES (%s,%s,%s,%s,'in_app',%s,%s,'Voir le ticket',%s,0,'public',1,%s,%s)""",
        (str(uuid.uuid4()), recipient_id, request_id, ntype,
         title, body, f"/app/requests/{req_uuid}", ts, ts)
    )


def _infos(etype: str, source_role: str, dest_role: str = None, is_public: bool = None) -> str:
    _estatus = {
        "created": "new", "qualifying": "qualifying", "qualified": "qualified",
        "assigned": "assigned", "in_progress": "in_progress", "pending": "pending",
        "escalated": "escalated", "rejected": "rejected", "reopen_request": "rejected",
        "chief_review": "rejected", "reopened": "reopened",
        "resolved": "resolved", "closed": "closed", "comment_added": "in_progress",
    }
    d: dict = {
        "event_status": _estatus.get(etype, etype),
        "source_role":  source_role,
    }
    if dest_role:
        d["dest_role"] = dest_role
    if is_public is not None:
        d["is_public"] = is_public
    return json.dumps(d, ensure_ascii=False)


async def create_ticket_2(cur, now, blaise_id, mohammed_id, fatoumata_id, chief_id,
                          statuses, priorities, categories):
    """
    Ticket 2 : Erreur acces SAP Finance (chemin PENDING)
    Demandeur : Mohammed Komano  | Agent : Fatoumata Conte
    Statut final : CLOSED + CSAT 5/5
    """
    print("\n[TICKET 2] Chemin PENDING — SAP Finance")
    print("-" * 50)

    t0 = now - timedelta(hours=3, minutes=30)
    req_uuid = str(uuid.uuid4())
    ref = "EDG-2026-00002"

    # Verifier si existe
    await cur.execute(
        "SELECT id FROM request WHERE ref=%s AND deleted_at IS NULL LIMIT 1", (ref,)
    )
    if await cur.fetchone():
        print("  Ticket existant — supprimé pour recréation")
        await cur.execute("DELETE FROM request WHERE ref=%s", (ref,))

    await cur.execute(
        """INSERT INTO request
           (uuid, ref, title, description,
            request_status_id, priority_definition_id, request_category_id,
            unity_id, requester_id, requester_name, requester_email,
            is_external, submission_mode, requester_type,
            in_triage, sla_hours, sla_elapsed, sla_breached,
            resolved_at, closed_at, status, created_at, updated_at)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                   0,'personal','internal',0,8,3,0,%s,%s,1,%s,%s)""",
        (
            req_uuid, ref,
            "Erreur 403 - Acces refuse sur le module SAP Finance",
            "Depuis ce matin je n'arrive plus a acceder au module SAP-FI (Finance). "
            "Message : 'Erreur 403 - Vous n avez pas les autorisations necessaires'. "
            "J'ai besoin de cet acces pour valider les ecritures comptables de fin de mois. "
            "Mon acces fonctionnait normalement vendredi dernier.",
            statuses["closed"], priorities["medium"], categories["logiciel"],
            UNITY_DSI_DEX, mohammed_id, "Mohammed Komano", "komano@gmail.com",
            t0 + timedelta(hours=3),
            t0 + timedelta(hours=3, minutes=20),
            t0, t0 + timedelta(hours=3, minutes=20),
        )
    )
    request_id = cur.lastrowid
    print(f"  Ticket cree (id={request_id})")

    wf_uuid = str(uuid.uuid4())
    await cur.execute(
        """INSERT INTO workflow
           (uuid, request_id, workflow_status, status, created_at, updated_at)
           VALUES (%s,%s,'completed',1,%s,%s)""",
        (wf_uuid, request_id, t0, t0 + timedelta(hours=3, minutes=20))
    )
    workflow_id = cur.lastrowid

    # ── Historique ── logique edgrh ────────────────────────────────────────────
    # Workflow COMPLET (CLOSED) → toutes les etapes : activated=1, accepted=1
    # (delta, etype, label, comment, actor_name, agent_id, accepted, dest_role, is_public)
    steps = [
        (0,   "created",
               "Demande soumise par l'employe",
               "Demande creee via le portail employe (erreur SAP Finance 403).",
               "Mohammed Komano", mohammed_id,
               True, None, True),

        (10,  "qualifying",
               "Prise en triage — support DSI",
               "Ticket receptione par le support DSI. Analyse de la demande d'habilitation.",
               "Fatoumata Conte", fatoumata_id,
               True, "agent", False),

        (20,  "qualified",
               "Ticket qualifie — probleme droits SAP-FI",
               "Probleme d'habilitation applicative confirme. "
               "Route vers DSI-DEX (equipe Exploitation / SAP Basis).",
               "Fatoumata Conte", fatoumata_id,
               True, "agent", False),

        (25,  "assigned",
               "Ticket assigne a Fatoumata Conte",
               "Prise en charge directe par l'agent disponible.",
               "Fatoumata Conte", fatoumata_id,
               True, None, False),

        (30,  "in_progress",
               "Traitement en cours — analyse des droits SAP",
               "Connexion SAP Basis pour verifier les profils d'autorisation.",
               "Fatoumata Conte", fatoumata_id,
               True, None, False),

        (45,  "pending",
               "En attente d'informations complementaires",
               "[Interne] Impossible de diagnostiquer sans connaitre le profil d'autorisation exact "
               "du nouveau poste de Mohammed. Mise en attente de la reponse du demandeur.",
               "Fatoumata Conte", fatoumata_id,
               True, "user", False),

        (46,  "comment_added",
               "Demande d'informations (public)",
               "Bonjour Mohammed, pour traiter votre demande j'ai besoin de precisions : "
               "1) Quel sous-module SAP-FI exactement (FI-GL, FI-AP, FI-AR) ? "
               "2) Votre profil de poste a-t-il change recemment ? "
               "3) Avez-vous recu un email RH de modification de droits ?",
               "Fatoumata Conte", fatoumata_id,
               True, None, True),

        (80,  "comment_added",
               "Reponse de l'employe",
               "Bonjour Fatoumata. Reponses : "
               "1) FI-GL (Comptabilite Generale) et FI-AP (Fournisseurs). "
               "2) Oui, j'ai change de poste il y a 10 jours "
               "(Charge Comptable -> Responsable Comptable). "
               "3) Oui, email RH recu indiquant la mise a jour de mon profil.",
               "Mohammed Komano", mohammed_id,
               True, None, True),

        (85,  "in_progress",
               "Reprise du traitement apres reponse employe",
               "Informations recues. Cause probable : profil SAP non mis a jour "
               "lors du changement de poste.",
               "Fatoumata Conte", fatoumata_id,
               True, None, False),

        (100, "comment_added",
               "Diagnostic technique (interne)",
               "[Interne] Verification SAP Basis : profils ZRSP_COMPTA_GENERAL et "
               "ZRSP_FOURNISSEURS non attribues au user MKOMANO. "
               "Action : attribution des profils requis pour Responsable Comptable. "
               "Coordination equipe SAP Basis.",
               "Fatoumata Conte", fatoumata_id,
               True, None, False),

        (120, "resolved",
               "Incident resolu — droits SAP mis a jour",
               "Profils SAP-FI attribues avec succes : ZRSP_COMPTA_GENERAL + ZRSP_FOURNISSEURS. "
               "Acces confirme par l'employe. "
               "Cause racine : changement de poste ne declenchait pas la MAJ des droits applicatifs. "
               "Recommandation : automatiser via integration RH-SAP.",
               "Fatoumata Conte", fatoumata_id,
               True, None, False),

        (200, "closed",
               "Demande cloturee par l'employe",
               "Probleme resolu, acces SAP-FI pleinement fonctionnel. "
               "Satisfaction : 5/5. Merci pour la rapidite !",
               "Mohammed Komano", mohammed_id,
               True, None, True),
    ]

    _role_map = {mohammed_id: "user", fatoumata_id: "agent", chief_id: "chief"}

    for delta, etype, label, comment, actor, agent_id, accepted, dest_role, is_public in steps:
        ts = t0 + timedelta(minutes=delta)
        source_role = _role_map.get(agent_id, "user")
        ip = is_public if etype == "comment_added" else None
        await cur.execute(
            """INSERT INTO workflow_detail
               (uuid, workflow_id, agent_id, event_type, label, comment,
                actor_name, unity_id, accepted, activated, infos,
                status, created_at, updated_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,1,%s,1,%s,%s)""",
            (str(uuid.uuid4()), workflow_id, agent_id, etype, label, comment, actor,
             UNITY_DSI_DEX, accepted,
             _infos(etype, source_role, dest_role, ip),
             ts, ts)
        )

    # CSAT
    await cur.execute(
        """INSERT INTO appreciation
           (uuid, request_id, rating, comment, resolved_confirmed, is_modified,
            author_type, status, created_at, updated_at)
           VALUES (%s,%s,5,%s,1,0,'internal',1,%s,%s)""",
        (
            str(uuid.uuid4()), request_id,
            "Excellent service. Fatoumata a identifie le probleme rapidement. "
            "Je recommande d automatiser la MAJ des droits lors des changements de poste.",
            t0 + timedelta(hours=3, minutes=20),
            t0 + timedelta(hours=3, minutes=20),
        )
    )

    # Notifications
    notifs = [
        (mohammed_id, "info",    "Demande recue",
         "Votre demande EDG-2026-00002 est enregistree.",
         t0),
        (mohammed_id, "warning", "Informations requises",
         "L agent DSI a besoin de precisions pour resoudre EDG-2026-00002.",
         t0 + timedelta(minutes=46)),
        (fatoumata_id, "info",   "Reponse recue — EDG-2026-00002",
         "Mohammed a repondu. Reprenez le traitement.",
         t0 + timedelta(minutes=80)),
        (mohammed_id, "success", "Votre demande a ete resolue",
         "L incident SAP-FI (EDG-2026-00002) est resolu. Vous pouvez cloturer.",
         t0 + timedelta(hours=2)),
    ]
    for recip, ntype, title, body, ts in notifs:
        await insert_notif(cur, recip, request_id, req_uuid, ntype, title, body, ts)

    print(f"  {len(steps)} etapes workflow_detail (activated=1 / accepted=1 pour toutes)")
    print(f"  CSAT 5/5 | {len(notifs)} notifications | Statut : CLOSED")
    return ref


async def create_ticket_3(cur, now, blaise_id, mohammed_id, fatoumata_id, chief_id,
                          statuses, priorities, categories):
    """
    Ticket 3 : Badge desactive — chemin REJET + REOUVERTURE
    Demandeur : Blaise GOEPOGUI  | Agent : Fatoumata Conte | Chef : Mamadou Diallo
    Statut final : CLOSED + CSAT 3/5

    Logique edgrh sur le REJET :
      - L'etape "rejected" est une decision NEGATIVE  → accepted=0 (False)
      - Le workflow s'arrete apres un rejet (pas de next step active)
      - La reouverture est une NOUVELLE sequence d'etapes (reopen_request → chief_review → reopened)
      - Toutes les etapes post-reouverture sont terminees → activated=1, accepted=1
    """
    print("\n[TICKET 3] Chemin REJET + REOUVERTURE")
    print("-" * 50)

    t0 = now - timedelta(hours=6)
    req_uuid = str(uuid.uuid4())
    ref = "EDG-2026-00003"

    await cur.execute(
        "SELECT id FROM request WHERE ref=%s AND deleted_at IS NULL LIMIT 1", (ref,)
    )
    if await cur.fetchone():
        print("  Ticket existant — supprimé pour recréation")
        await cur.execute("DELETE FROM request WHERE ref=%s", (ref,))

    await cur.execute(
        """INSERT INTO request
           (uuid, ref, title, description,
            request_status_id, priority_definition_id, request_category_id,
            unity_id, requester_id, requester_name, requester_email,
            is_external, submission_mode, requester_type,
            in_triage, sla_hours, sla_elapsed, sla_breached,
            resolved_at, closed_at, status, created_at, updated_at)
           VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                   0,'personal','internal',0,8,6,0,%s,%s,1,%s,%s)""",
        (
            req_uuid, ref,
            "Badge d acces physique desactive — impossible d entrer dans le batiment",
            "Mon badge d acces au batiment principal a ete desactive ce matin. "
            "Je ne peux plus acceder au bureau. La securite m a dit que c est une demande IT. "
            "Merci de reactiver mon badge au plus vite.",
            statuses["closed"], priorities["high"], categories["incident"],
            UNITY_DSI_DEX, blaise_id, "Blaise GOEPOGUI", "blaise@gmail.com",
            t0 + timedelta(hours=5, minutes=30),
            t0 + timedelta(hours=5, minutes=50),
            t0, t0 + timedelta(hours=5, minutes=50),
        )
    )
    request_id = cur.lastrowid
    print(f"  Ticket cree (id={request_id})")

    wf_uuid = str(uuid.uuid4())
    await cur.execute(
        """INSERT INTO workflow
           (uuid, request_id, workflow_status, status, created_at, updated_at)
           VALUES (%s,%s,'completed',1,%s,%s)""",
        (wf_uuid, request_id, t0, t0 + timedelta(hours=5, minutes=50))
    )
    workflow_id = cur.lastrowid

    # ── Historique ── logique edgrh ────────────────────────────────────────────
    #
    # Regle edgrh sur le REJET :
    #   - "rejected" → accepted=0 (False) : decision NEGATIVE de l'agent
    #     Le workflow s'arrete. Aucun next step n'est active automatiquement.
    #   - "reopen_request" → accepted=1 : l'employe a soumis la demande (action completee)
    #   - "chief_review"   → accepted=1 : le chef a valide la reouverture (decision positive)
    #   - Toutes les etapes suivantes → accepted=1 (workflow repris et complete)
    #
    _role_map = {blaise_id: "user", fatoumata_id: "agent", chief_id: "chief"}

    # Phase 1 — Rejet initial
    phase1 = [
        (0,   "created",
               "Demande soumise par l'employe",
               "Demande creee via le portail employe (badge desactive).",
               "Blaise GOEPOGUI", blaise_id,
               True, None, True),

        (12,  "qualifying",
               "Prise en triage — support DSI",
               "Ticket receptione. Analyse de la nature de la demande.",
               "Fatoumata Conte", fatoumata_id,
               True, "agent", False),

        (20,  "rejected",
               "Demande rejetee — hors perimetre DSI",
               "Cette demande concerne la gestion des badges d acces physiques. "
               "Ce service releve de la Direction des Infrastructures / Securite physique, "
               "et NON de la DSI. Raison du rejet : hors perimetre informatique.",
               "Fatoumata Conte", fatoumata_id,
               False,   # <-- accepted=False : decision NEGATIVE (rejet du ticket)
               None, False),
    ]

    # Phase 2 — Reouverture
    phase2 = [
        (35,  "reopen_request",
               "Demande de reouverture par l'employe",
               "Je conteste ce rejet. La securite physique m a confirme que la "
               "desactivation vient d une action IT (Active Directory / controle d acces). "
               "C est bien un probleme informatique. Merci de reexaminer.",
               "Blaise GOEPOGUI", blaise_id,
               True, "chief", True),

        (50,  "chief_review",
               "Reouverture validee par le Chef de service — Mamadou Diallo",
               "Verification faite : le controle d acces physique est integre a l AD "
               "(solution Lenel OnGuard). C est bien un probleme DSI. "
               "Je valide la reouverture. Route vers DSI-SSH (Securite systemes).",
               "Mamadou Diallo", chief_id,
               True, "agent", False),  # chief a approuve : accepted=True

        (55,  "reopened",
               "Ticket rouvert apres validation chef",
               "Reouverture validee par Mamadou Diallo (Chef DSI-DEX). "
               "Nouveau cycle de traitement lance.",
               "Mamadou Diallo", chief_id,
               True, None, False),
    ]

    # Phase 3 — Nouveau cycle de traitement complet
    phase3 = [
        (60,  "qualifying",
               "Requalification du ticket rouvert",
               "Nouveau triage. Reroute vers DSI-DEX (systemes & securite AD).",
               "Fatoumata Conte", fatoumata_id,
               True, "agent", False),

        (70,  "qualified",
               "Ticket requalifie — controle d acces Active Directory",
               "Cause confirmee : badge desactive par un script AD de nettoyage "
               "des comptes inactifs. Compte de Blaise marque inactif (etait en conge).",
               "Fatoumata Conte", fatoumata_id,
               True, "agent", False),

        (75,  "assigned",
               "Ticket assigne a Fatoumata Conte",
               "Traitement direct (intervention AD depuis le poste agent).",
               "Fatoumata Conte", fatoumata_id,
               True, None, False),

        (80,  "in_progress",
               "Traitement en cours — intervention Active Directory",
               "Connexion console AD. Verification de l OU Employes.",
               "Fatoumata Conte", fatoumata_id,
               True, None, False),

        (90,  "comment_added",
               "Diagnostic technique (interne)",
               "[Interne] Attribut 'msDS-UserAccountDisabled' = TRUE sur BGOEPOGUI "
               "(OU=Employes). Script batch week-end a marque le compte inactif "
               "(Blaise etait en conge lors de la fenetre de detection). "
               "Action : reactivation AD + badge via API Lenel OnGuard. "
               "Signalement au responsable securite pour correction du script.",
               "Fatoumata Conte", fatoumata_id,
               True, None, False),

        (120, "resolved",
               "Incident resolu — badge et compte AD reactives",
               "Compte AD BGOEPOGUI reactivite. Badge physique synchronise via Lenel OnGuard. "
               "Acces au batiment confirme par l employe. "
               "Cause racine : script de desactivation ne prend pas en compte les conges. "
               "Correction planifiee.",
               "Fatoumata Conte", fatoumata_id,
               True, None, False),

        (330, "closed",
               "Demande cloturee par l'employe",
               "Acces retabli. Le rejet initial est a deplorer mais le traitement "
               "apres reouverture a ete efficace. Note : 3/5.",
               "Blaise GOEPOGUI", blaise_id,
               True, None, True),
    ]

    all_steps = phase1 + phase2 + phase3

    for delta, etype, label, comment, actor, agent_id, accepted, dest_role, is_public in all_steps:
        ts = t0 + timedelta(minutes=delta)
        source_role = _role_map.get(agent_id, "user")
        ip = is_public if etype == "comment_added" else None
        await cur.execute(
            """INSERT INTO workflow_detail
               (uuid, workflow_id, agent_id, event_type, label, comment,
                actor_name, unity_id, accepted, activated, infos,
                status, created_at, updated_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,1,%s,1,%s,%s)""",
            (str(uuid.uuid4()), workflow_id, agent_id, etype, label, comment, actor,
             UNITY_DSI_DEX, accepted,
             _infos(etype, source_role, dest_role, ip),
             ts, ts)
        )

    # CSAT
    await cur.execute(
        """INSERT INTO appreciation
           (uuid, request_id, rating, comment, resolved_confirmed, is_modified,
            author_type, status, created_at, updated_at)
           VALUES (%s,%s,3,%s,1,0,'internal',1,%s,%s)""",
        (
            str(uuid.uuid4()), request_id,
            "Probleme resolu mais le rejet initial etait injustifie et a perdu du temps. "
            "Le traitement apres reouverture a ete rapide. "
            "Recommandation : mieux former les agents sur le perimetre des systemes de controle acces.",
            t0 + timedelta(hours=5, minutes=50),
            t0 + timedelta(hours=5, minutes=50),
        )
    )

    # Notifications
    notifs = [
        (blaise_id, "info",    "Demande recue",
         "Votre demande EDG-2026-00003 est enregistree.",
         t0),
        (blaise_id, "warning", "Demande rejetee — action requise",
         "Votre demande EDG-2026-00003 a ete rejetee. "
         "Raison : hors perimetre. Vous pouvez contester.",
         t0 + timedelta(minutes=20)),
        (chief_id,  "info",    "Demande de reouverture — EDG-2026-00003",
         "Blaise GOEPOGUI conteste le rejet d EDG-2026-00003. Votre validation est requise.",
         t0 + timedelta(minutes=35)),
        (blaise_id, "success", "Reouverture validee",
         "Le chef de service a valide la reouverture de EDG-2026-00003. "
         "Elle est en cours de retraitement.",
         t0 + timedelta(minutes=55)),
        (blaise_id, "success", "Incident resolu",
         "Votre badge et compte AD sont reactives (EDG-2026-00003).",
         t0 + timedelta(hours=2)),
    ]
    for recip, ntype, title, body, ts in notifs:
        await insert_notif(cur, recip, request_id, req_uuid, ntype, title, body, ts)

    p1_rejected = [s for s in phase1 if s[0] == 20]  # etape rejected
    print(f"  {len(all_steps)} etapes workflow_detail")
    print(f"    Phase 1 ({len(phase1)} etapes) : rejet -> accepted=0 sur 'rejected'")
    print(f"    Phase 2 ({len(phase2)} etapes) : reouverture validee")
    print(f"    Phase 3 ({len(phase3)} etapes) : traitement complet -> accepted=1")
    print(f"  CSAT 3/5 | {len(notifs)} notifications | Statut : CLOSED")
    return ref


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

    now = datetime.now()

    async with conn.cursor() as cur:
        # Charger les IDs runtime
        blaise_id    = await _get_account_id(cur, "blaise@gmail.com")
        mohammed_id  = await _get_account_id(cur, "komano@gmail.com")
        fatoumata_id = await _get_account_id(cur, "fatoumata@gmail.com")
        chief_id     = await _get_account_id(cur, "chef.dsi@edg.gn")

        statuses = {
            c: await _get_status_id(cur, c)
            for c in ("new", "qualifying", "qualified", "assigned", "in_progress",
                      "pending", "resolved", "closed", "rejected", "reopened")
        }
        priorities = {
            s: await _get_priority_id(cur, s) for s in ("low", "medium", "high", "critical")
        }
        categories = {
            c: await _get_category_id(cur, c)
            for c in ("logiciel", "incident", "acces_applicatif", "maintenance", "autre")
        }

        ref2 = await create_ticket_2(
            cur, now, blaise_id, mohammed_id, fatoumata_id, chief_id,
            statuses, priorities, categories
        )
        ref3 = await create_ticket_3(
            cur, now, blaise_id, mohammed_id, fatoumata_id, chief_id,
            statuses, priorities, categories
        )

        await conn.commit()

    conn.close()

    print()
    print("=" * 65)
    print("TICKETS 2 & 3 CREES")
    print("=" * 65)
    print(f"  {ref2} : CLOSED (CSAT 5/5) — chemin pending")
    print(f"  {ref3} : CLOSED (CSAT 3/5) — chemin rejet + reouverture")
    print()
    print("Logique edgrh appliquee :")
    print("  status=1 (soft-delete=actif)")
    print("  activated=1 (toutes les etapes traitees)")
    print("  accepted=1 (etapes completees)")
    print("  accepted=0 (etape 'rejected' : decision negative)")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(main())
