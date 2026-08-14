"""
Seed de demonstration CDC complet - Ticket 1 "Probleme de connexion VPN EDG"

Logique workflow_detail (alignee avec edgrh) :
  status    = 1 (enregistrement actif, soft-delete)
  activated = 1 (etape ayant ete traitee / en cours)
  accepted  = 1 (etape completee/approuvee)
            = 0 (etape rejetee)
            = NULL (etape en attente de decision)

Pour un workflow COMPLET : toutes les etapes passees -> activated=1, accepted=1
Pour un workflow en cours (RESOLVED) : toutes les etapes passees accepted=1,
                                        le ticket attend la cloture par l'employe.

Chemin CDC ticket 1 :
  new -> qualifying -> qualified -> assigned -> in_progress
      -> escalated -> chief_review (valide) -> in_progress -> resolved
  Commentaires internes et publics inclus.

Usage (depuis backend, venv active) :
    python scripts/seed_demo_workflow.py
"""

import asyncio, json, os, sys, uuid
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))
from dotenv import load_dotenv
load_dotenv(Path(__file__).parent.parent / ".env")

import aiomysql

UNITY_DSI_DEX = 14
UNITY_DSI     = 6


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

        # ── 1. Comptes demo ───────────────────────────────────────────────────
        print("[1/6] Creation / mise a jour des comptes demo...")

        accounts = [
            # (email, name, firstname, role, unity_id, matricule)
            ("blaise@gmail.com",                   "Blaise GOEPOGUI",   "Blaise",   "user",     14, "EDG-EMP-007"),
            ("komano@gmail.com",                   "Mohammed Komano",   "Mohammed", "user",      6, "EDG-EMP-004"),
            ("fatoumata@gmail.com",                "Fatoumata Conte",   "Fatoumata","agent",    14, "EDG-AGT-005"),
            ("diaby@gmail.com",                    "Diaby Directeur",   "Diaby",    "director",  6, "EDG-DIR-006"),
            ("gasparndkamangoepogui502@gmail.com", "Toure DG",          "Toure",    "dg",        1, "EDG-AT-2026"),
            ("gaspardKamangoepogui@gmail.com",     "GOEPOGUI Admin",    "Gaspard",  "admin",     6, "EDG-ADM-001"),
            ("alpha@gmail.com",                    "Komano Directeur",  "Alpha",    "director",  7, "EDG-DIR-003"),
        ]

        for email, name, firstname, role, unity_id, matricule in accounts:
            acc_uuid = str(uuid.uuid4())
            await cur.execute(
                """INSERT INTO account
                   (uuid, name, firstname, email, role, unity_id,
                    matricule, is_edg_employee, account_status, email_verified,
                    mfa_enabled, notif_sla_alerts, notif_escalations,
                    notif_comments, notif_resolutions,
                    status, created_at, updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,1,'active',1,0,1,1,1,1,1,%s,%s)
                   ON DUPLICATE KEY UPDATE
                     name=VALUES(name), firstname=VALUES(firstname),
                     role=VALUES(role), unity_id=VALUES(unity_id),
                     matricule=VALUES(matricule), is_edg_employee=1,
                     account_status='active', status=1""",
                (acc_uuid, name, firstname, email, role, unity_id,
                 matricule, now, now)
            )

        # ── 2. Compte chef de service DSI-DEX ─────────────────────────────────
        print("[2/6] Compte chef de service DSI-DEX (chef.dsi@edg.gn)...")

        chief_uuid = str(uuid.uuid4())
        await cur.execute(
            """INSERT INTO account
               (uuid, name, firstname, email, role, unity_id,
                matricule, is_edg_employee, account_status, email_verified,
                mfa_enabled, notif_sla_alerts, notif_escalations,
                notif_comments, notif_resolutions,
                status, created_at, updated_at)
               VALUES (%s,'Mamadou Diallo','Mamadou','chef.dsi@edg.gn',
                       'chief',14,'EDG-CHF-010',1,'active',1,0,1,1,1,1,1,%s,%s)
               ON DUPLICATE KEY UPDATE
                 name='Mamadou Diallo', role='chief', unity_id=14,
                 matricule='EDG-CHF-010', is_edg_employee=1,
                 account_status='active', status=1""",
            (chief_uuid, now, now)
        )
        await cur.execute("SELECT id FROM account WHERE email='chef.dsi@edg.gn'")
        chief_id = (await cur.fetchone())[0]
        print(f"   Chef OK (id={chief_id})")

        # IDs des acteurs
        await cur.execute("SELECT id FROM account WHERE email='blaise@gmail.com'")
        blaise_id = (await cur.fetchone())[0]
        await cur.execute("SELECT id FROM account WHERE email='fatoumata@gmail.com'")
        fatoumata_id = (await cur.fetchone())[0]

        # IDs statuts
        STATUS = {
            "new": None, "qualifying": None, "qualified": None, "assigned": None,
            "in_progress": None, "escalated": None, "resolved": None,
        }
        for code in STATUS:
            await cur.execute(
                "SELECT id FROM request_status WHERE code=%s AND deleted_at IS NULL LIMIT 1",
                (code,)
            )
            r = await cur.fetchone()
            STATUS[code] = r[0] if r else None

        # IDs priorite et categorie
        await cur.execute(
            "SELECT id FROM priority_definition WHERE slug='high' AND deleted_at IS NULL LIMIT 1"
        )
        r = await cur.fetchone()
        PRIORITY_HIGH = r[0] if r else 3

        await cur.execute(
            "SELECT id FROM request_category WHERE code='acces_applicatif' AND deleted_at IS NULL LIMIT 1"
        )
        r = await cur.fetchone()
        CAT_VPN = r[0] if r else 9

        # ── 3. Ticket ─────────────────────────────────────────────────────────
        print("[3/6] Creation du ticket EDG-2026-00001...")

        # Verifier si le ticket existe deja
        await cur.execute(
            "SELECT id FROM request WHERE ref='EDG-2026-00001' AND deleted_at IS NULL LIMIT 1"
        )
        if await cur.fetchone():
            print("   Ticket deja existant - supprimé pour recréation")
            await cur.execute("DELETE FROM request WHERE ref='EDG-2026-00001'")

        req_uuid = str(uuid.uuid4())
        t_created = now - timedelta(hours=5)

        await cur.execute(
            """INSERT INTO request
               (uuid, ref, title, description,
                request_status_id, priority_definition_id, request_category_id,
                unity_id, requester_id, requester_name, requester_email,
                is_external, submission_mode, requester_type,
                in_triage, sla_hours, sla_elapsed, sla_breached,
                status, created_at, updated_at)
               VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,
                       0,'personal','internal',0,8,5,0,1,%s,%s)""",
            (
                req_uuid, "EDG-2026-00001",
                "Impossible de se connecter au VPN EDG depuis mon poste",
                "Depuis ce matin, je n'arrive plus a me connecter au VPN de l'entreprise. "
                "Le client FortiClient affiche 'Erreur d authentification'. "
                "J'ai redemarrage le poste, verife mes identifiants et reinitialise le MFA "
                "mais le probleme persiste. Je ne peux plus acceder aux applications internes "
                "ni au partage de fichiers reseau. Mon travail est completement bloque.",
                STATUS["resolved"],
                PRIORITY_HIGH, CAT_VPN,
                UNITY_DSI_DEX,
                blaise_id, "Blaise GOEPOGUI", "blaise@gmail.com",
                t_created, now,
            )
        )
        request_id = cur.lastrowid
        print(f"   Ticket cree (id={request_id})")

        # ── 4. Workflow ────────────────────────────────────────────────────────
        print("[4/6] Creation du workflow...")

        wf_uuid = str(uuid.uuid4())
        await cur.execute(
            """INSERT INTO workflow
               (uuid, request_id, workflow_status, status, created_at, updated_at)
               VALUES (%s,%s,'active',1,%s,%s)""",
            (wf_uuid, request_id, t_created, now)
        )
        workflow_id = cur.lastrowid

        # ── 5. Historique complet (logique edgrh) ─────────────────────────────
        print("[5/6] Creation de l'historique (logique edgrh)...")

        #
        # Champs edgrh-alignes :
        #   status    = 1 toujours (soft-delete = actif)
        #   activated = 1 pour une etape qui a ete traitee
        #             = 0 pour une etape future en attente de son tour
        #   accepted  = 1 etape completee/approuvee
        #             = 0 etape rejetee
        #             = NULL etape en attente de decision
        #
        # Pour ce ticket RESOLVED (workflow complet sauf cloture finale) :
        #   toutes les etapes passees : activated=1, accepted=1
        #   le ticket attend que l'employe le cloture depuis le frontend.
        #

        # (event_type, label, comment, actor_name, agent_id, delta_min,
        #  accepted, dest_role, is_public)
        steps = [
            (
                "created",
                "Demande soumise par l'employe",
                "Demande creee via le portail employe (connexion VPN impossible).",
                "Blaise GOEPOGUI", blaise_id, 0,
                True,   # accepted : etape completee
                None, True,
            ),
            (
                "qualifying",
                "Prise en triage — ticket receptione par le support DSI",
                "Ticket receptione. Analyse de la nature de la demande en cours. "
                "Categorie provisoire : acces_applicatif.",
                "Fatoumata Conte", fatoumata_id, 15,
                True, "agent", False,
            ),
            (
                "qualified",
                "Ticket qualifie — route vers DSI-DEX (Exploitation)",
                "Probleme identifie : incident VPN / acces_applicatif. "
                "Route vers le service DSI-DEX (equipe Exploitation).",
                "Fatoumata Conte", fatoumata_id, 30,
                True, "agent", False,
            ),
            (
                "assigned",
                "Ticket assigne a Fatoumata Conte (agent DSI-DEX)",
                "Prise en charge directe par l'agent disponible (charge la plus faible).",
                "Fatoumata Conte", fatoumata_id, 35,
                True, None, False,
            ),
            (
                "in_progress",
                "Traitement en cours — analyse du probleme VPN",
                "Prise en main a distance demandee. Analyse du journal FortiClient.",
                "Fatoumata Conte", fatoumata_id, 40,
                True, None, False,
            ),
            (
                "comment_added",
                "Analyse technique (interne)",
                "[Interne] Diagnostic : le certificat VPN cote serveur (FortiGate) a expire. "
                "Le serveur RADIUS refuse les nouvelles authentifications. "
                "Action : renouvellement du certificat + redemarrage du service VPN. "
                "Test de reconnexion prevu dans 20 min.",
                "Fatoumata Conte", fatoumata_id, 55,
                True, None, False,  # commentaire interne : is_public=False
            ),
            (
                "comment_added",
                "Commentaire employe (public)",
                "Bonjour, toujours aucune connexion possible. "
                "J'ai essaye depuis un autre poste, le meme probleme apparait. "
                "Pouvez-vous accelerer car je ne peux pas travailler ?",
                "Blaise GOEPOGUI", blaise_id, 70,
                True, None, True,   # commentaire public : is_public=True
            ),
            (
                "escalated",
                "Escalade L1 -> L2 (Chef de service DSI-DEX)",
                "Escalade vers le chef de service : le probleme affecte potentiellement "
                "plusieurs utilisateurs (serveur RADIUS central). "
                "Autorisation de modification de configuration serveur requise.",
                "Fatoumata Conte", fatoumata_id, 80,
                True, "chief", False,
            ),
            (
                "chief_review",
                "Validation escalade par le Chef de service — Mamadou Diallo",
                "Escalade validee. J'autorise la modification de la configuration "
                "du serveur RADIUS et du certificat FortiGate. "
                "Priorite haute maintenue. Coordonner avec DSI-SEC si necessaire.",
                "Mamadou Diallo", chief_id, 95,
                True, "agent", False,  # chief a approuve : accepted=True
            ),
            (
                "in_progress",
                "Reprise du traitement apres autorisation chef",
                "Intervention sur le serveur FortiGate en cours. "
                "Renouvellement du certificat SSL/TLS du service VPN.",
                "Fatoumata Conte", fatoumata_id, 100,
                True, None, False,
            ),
            (
                "comment_added",
                "Mise a jour technique (interne)",
                "[Interne] Certificat renouvele sur FortiGate. "
                "Service RADIUS redémarre. Propagation en cours (env. 10 min). "
                "Test de reconnexion a effectuer.",
                "Fatoumata Conte", fatoumata_id, 110,
                True, None, False,
            ),
            (
                "resolved",
                "Incident resolu — acces VPN retabli",
                "Probleme resolu : certificat VPN renouvele + configuration RADIUS corrigee. "
                "L'acces VPN est retabli. Cause racine : expiration du certificat serveur "
                "non detectee par l'alerte monitoring. "
                "Action preventive : alerte ajoutee a J-30 avant expiration.",
                "Fatoumata Conte", fatoumata_id, 180,
                True, None, False,
            ),
        ]

        _role_map = {blaise_id: "user", fatoumata_id: "agent", chief_id: "chief"}
        _estatus = {
            "created": "new", "qualifying": "qualifying", "qualified": "qualified",
            "assigned": "assigned", "in_progress": "in_progress", "escalated": "escalated",
            "chief_review": "escalated", "resolved": "resolved", "comment_added": "in_progress",
        }

        for etype, label, comment, actor, agent_id, delta, accepted, dest_role, is_public in steps:
            ts = t_created + timedelta(minutes=delta)
            source_role = _role_map.get(agent_id, "user")

            infos: dict = {
                "event_status": _estatus.get(etype, etype),
                "source_role":  source_role,
            }
            if dest_role:
                infos["dest_role"] = dest_role
            if etype == "comment_added":
                infos["is_public"] = is_public

            await cur.execute(
                """INSERT INTO workflow_detail
                   (uuid, workflow_id, agent_id, event_type, label, comment,
                    actor_name, unity_id, accepted, activated, infos,
                    status, created_at, updated_at)
                   VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,1,%s,1,%s,%s)""",
                (
                    str(uuid.uuid4()), workflow_id, agent_id,
                    etype, label, comment, actor,
                    UNITY_DSI_DEX,
                    accepted,                           # True pour toutes les etapes terminees
                    json.dumps(infos, ensure_ascii=False),
                    ts, ts,
                )
            )

        # ── 6. Notifications ──────────────────────────────────────────────────
        print("[6/6] Notifications...")

        await cur.execute(
            """INSERT INTO notification
               (uuid, recipient_id, request_id, type, channel, title, body,
                action_label, action_url, is_read, visibility, status, created_at, updated_at)
               VALUES (%s,%s,%s,'success','in_app',
                       'Votre demande VPN a ete resolue',
                       'L incident EDG-2026-00001 a ete traite par DSI-DEX. '
                       'Vous pouvez confirmer la resolution et cloturer la demande.',
                       'Voir le ticket',%s,0,'public',1,%s,%s)""",
            (str(uuid.uuid4()), blaise_id, request_id,
             f"/app/requests/{req_uuid}", now, now)
        )

        await cur.execute(
            """INSERT INTO notification
               (uuid, recipient_id, request_id, type, channel, title, body,
                action_label, action_url, is_read, visibility, status, created_at, updated_at)
               VALUES (%s,%s,%s,'info','in_app',
                       'Escalade validee — ticket VPN',
                       'Le chef de service a valide l escalade d EDG-2026-00001. '
                       'Reprenez le traitement.',
                       'Voir le ticket',%s,0,'public',1,%s,%s)""",
            (str(uuid.uuid4()), fatoumata_id, request_id,
             f"/app/requests/{req_uuid}", now, now)
        )

        await conn.commit()

    conn.close()

    print()
    print("=" * 65)
    print("TICKET 1 CREE")
    print("=" * 65)
    print(f"  Ref     : EDG-2026-00001")
    print(f"  Statut  : RESOLVED (a cloturer par Blaise depuis le frontend)")
    print(f"  Etapes  : {len(steps)} workflow_detail")
    print(f"  Logique : status=1 / activated=1 / accepted=1 (toutes terminees)")
    print()
    print("COMPTES (mot de passe : Edg@2024!)")
    print("-" * 65)
    print("  EMPLOYE   blaise@gmail.com")
    print("  EMPLOYE   komano@gmail.com")
    print("  AGENT     fatoumata@gmail.com")
    print("  CHEF      chef.dsi@edg.gn")
    print("  DIRECTEUR diaby@gmail.com")
    print("  DG        gasparndkamangoepogui502@gmail.com")
    print("  ADMIN     gaspardKamangoepogui@gmail.com")
    print("=" * 65)


if __name__ == "__main__":
    asyncio.run(main())
