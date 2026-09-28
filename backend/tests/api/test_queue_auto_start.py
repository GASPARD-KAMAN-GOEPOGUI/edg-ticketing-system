"""
Prise / assignation depuis la File d'attente — ce que produit ce geste.

BR-TRAITEMENT-PROGRESSIF-001 (2026-09-27) a REMPLACÉ BR-QUEUE-AUTO-START-001 :
une prise ou une assignation depuis la File d'attente ne démarre plus le
traitement, elle désigne un intervenant et le ticket s'arrête à `assigned`. Le
démarrage est devenu un geste explicite (`POST /{id}/start-treatment`), seul
capable d'horodater le vrai début et d'enregistrer le lieu.

Couvre : prise directe (qualify_triage avec assignee_id=soi-même), assignation à
un tiers (qualify_triage + assign() dédié), sortie de la File d'attente, entrée
dans "Ma boîte de traitement", notifications, continuité de la transmission
dynamique, réouverture, non-régression BR-REQUESTER-NO-SELF-TREATMENT-001.

Le parcours complet du workflow progressif est couvert par
`test_treatment_progressive.py`.
"""
from __future__ import annotations

from sqlalchemy import select

from tests.conftest import MOCK_ACCOUNTS, _TestSession
from tests.api.test_requests_baseline import _ensure_test_account
from tests.api.test_transmit_treatment import (
    _REQUEST_PAYLOAD_BASE,
    _call_as,
    _create_ticket,
    _dep,
    _notifications_for,
    _timeline,
)

_FULL_RESOLVE_BODY = {
    "summary": "Résumé final de test",
    "solution": "Solution appliquée de test",
    "work_done": "Travail réalisé de test",
}


async def _in_queue(request_id: str) -> bool:
    from api.models.ModelRequest import Request as RequestModel

    async with _TestSession() as session:
        obj = await session.get(RequestModel, int(request_id))
        return bool(obj.in_triage) and obj.request_status in ("new", "qualifying", "qualified", "reopened")


# ── CAS A — Prise directe (qualify_triage, assignee_id = soi-même) ────────────

async def test_take_from_queue_assigns_without_starting(auth_client, unity_id):
    await _ensure_test_account(901, unity_id=unity_id, role="chief-service")
    request_id = await _create_ticket(auth_client, unity_id, "take-direct")

    resp = await _call_as(
        _dep(901, "chief-service", unity_id), "POST", f"/api/v1/requests/{request_id}/qualify",
        {"category": "panne", "priority": "medium", "unit_id": str(unity_id), "assignee_id": "901"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert str(data["assignee_id"]) == "901"
    # BR-QUEUE-AUTO-START-001 — statut résultant direct, pas d'étape "assigned".
    assert data["request_status"] == "assigned"
    assert data["in_triage"] is False

    assert not await _in_queue(request_id)

    # "Ma boîte de traitement" (assignee_id=soi-même) doit déjà inclure ce ticket.
    async with auth_client("admin") as admin_client:
        my_box = await admin_client.get(f"/api/v1/requests/?assignee_id=901")
    assert my_box.status_code == 200, my_box.text
    ids = [str(item["id"]) for item in my_box.json()["data"]["items"]]
    assert request_id in ids

    # Plus besoin d'un second appel "Démarrer traitement" : la transition
    # in_progress -> in_progress n'est plus une transition valide (déjà démarré).
    already_started = await _call_as(
        _dep(901, "chief-service", unity_id), "PATCH", f"/api/v1/requests/{request_id}",
        {"request_status": "in_progress"},
    )
    assert already_started.status_code == 400, already_started.text


# ── CAS B — Assignation à un tiers depuis la File (qualify_triage) ────────────

async def test_assign_from_queue_assigns_without_starting(auth_client, unity_id):
    await _ensure_test_account(902, unity_id=unity_id, role="chief-service")
    # BR-DISTRIBUTION-001 — cibler un chef de division support depuis la File
    # d'attente n'en fait plus un traitant (le ticket entre dans sa Distribution, cf.
    # test_distribution.py). Ce test porte sur BR-QUEUE-AUTO-START-001 : une
    # assignation EFFECTIVE a un traitant demarre immediatement le traitement. On
    # cible donc un technicien, via l'admin (le chef de service, lui, ne peut cibler
    # que lui-meme ou un CDS — cf. test_queue_target_restriction.py).
    await _ensure_test_account(903, unity_id=unity_id, role="technicien")
    request_id = await _create_ticket(auth_client, unity_id, "assign-direct")

    resp = await _call_as(
        _dep(6, "admin", unity_id), "POST", f"/api/v1/requests/{request_id}/qualify",
        {"category": "panne", "priority": "medium", "unit_id": str(unity_id), "assignee_id": "903"},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert str(data["assignee_id"]) == "903"
    assert data["request_status"] == "assigned"
    assert data["in_triage"] is False
    assert not await _in_queue(request_id)

    # C notifié (App+Email, cohérence assign()/qualify_triage() — nouvel
    # intervenant toujours notifié), demandeur informé (App-only) — cf.
    # BR-NOTIFICATION-WORKFLOW-001. Le titre du demandeur reflète le chemin
    # générique update()/_notif_map (qualify_triage), distinct du titre de
    # assign() dédié ("Ticket pris en charge") — même fait métier, message différent.
    assignee_notifs = await _notifications_for(903, request_id)
    assert any(n.title == "Ticket assigné" for n in assignee_notifs)
    # Le demandeur est informé de la prise en charge, plus d'un traitement « en
    # cours » : celui-ci ne commencera qu'au geste explicite du traitant.
    requester_notifs = await _notifications_for(MOCK_ACCOUNTS["user"].id, request_id)
    titles = [n.title for n in requester_notifs]
    assert "Ticket pris en charge" in titles, titles


# ── assign() dédié (ex. "M'assigner" / "Assigner" depuis la fiche détail) ─────

async def test_dedicated_assign_endpoint_assigns_without_starting(auth_client, unity_id):
    await _ensure_test_account(904, unity_id=unity_id, role="chief-service")
    request_id = await _create_ticket(auth_client, unity_id, "dedicated-assign")

    resp = await _call_as(
        _dep(6, "admin"), "POST", f"/api/v1/requests/{request_id}/assign?assignee_id=904",
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["request_status"] == "assigned"

    events = await _timeline(auth_client, request_id)
    assigned_events = [e for e in events if e["event_type"] == "assigned"]
    # Une seule ligne de journal pour une seule action utilisateur. Le libellé ne
    # mentionne plus de « traitement démarré » : l'assignation ne démarre plus
    # rien, le démarrage a son propre événement `treatment_started`.
    assert len(assigned_events) == 1
    assert not [e for e in events if e["event_type"] == "treatment_started"]

    # Pas de double transition possible ensuite.
    redundant = await _call_as(
        _dep(904, "chief-service", unity_id), "PATCH", f"/api/v1/requests/{request_id}",
        {"request_status": "in_progress"},
    )
    assert redundant.status_code == 400, redundant.text


# ── Transmission dynamique après démarrage : continuité, pas de redémarrage ───

async def test_transmission_after_take_preserves_cycle_no_restart(auth_client, unity_id):
    await _ensure_test_account(905, unity_id=unity_id, role="chief-service")
    await _ensure_test_account(906, unity_id=unity_id, role="chief-service")
    request_id = await _create_ticket(auth_client, unity_id, "transmit-after-take")

    take_resp = await _call_as(
        _dep(905, "chief-service", unity_id), "POST", f"/api/v1/requests/{request_id}/qualify",
        {"category": "panne", "priority": "medium", "unit_id": str(unity_id), "assignee_id": "905"},
    )
    assert take_resp.status_code == 200, take_resp.text
    assert take_resp.json()["data"]["request_status"] == "assigned"

    started = await _call_as(
        _dep(905, "chief-service", unity_id), "POST",
        f"/api/v1/requests/{request_id}/start-treatment", {"location": "Site EDG"},
    )
    assert started.status_code == 200, started.text


    transmit_resp = await _call_as(
        _dep(905, "chief-service", unity_id), "POST", f"/api/v1/requests/{request_id}/transmit",
        {"to_user_id": "906", "work_done": "Diagnostic initial.", "reason": "Compétence réseau requise."},
    )
    assert transmit_resp.status_code == 200, transmit_resp.text
    transmit_data = transmit_resp.json()["data"]
    assert str(transmit_data["assignee_id"]) == "906"
    # BR-QUEUE-AUTO-START-001 §6 — la transmission ne remet jamais en File
    # d'attente ni ne redemande un "Démarrer traitement" : même statut actif.
    assert transmit_data["request_status"] == "in_progress"
    assert transmit_data["in_triage"] is False

    events = await _timeline(auth_client, request_id)
    transmitted = [e for e in events if e["event_type"] == "treatment_transmitted"]
    assert len(transmitted) == 1
    assert transmitted[0]["infos"]["cycle_number"] == 1  # même cycle, pas de redémarrage

    # C (906) peut directement résoudre — aucune étape "Démarrer traitement" requise.
    resolve_resp = await _call_as(
        _dep(906, "chief-service", unity_id), "POST", f"/api/v1/requests/{request_id}/resolve",
        _FULL_RESOLVE_BODY,
    )
    assert resolve_resp.status_code == 200, resolve_resp.text


# ── Réouverture : nouveau cycle démarré immédiatement à la reprise ────────────

async def test_reopened_ticket_taken_from_queue_starts_new_cycle_immediately(auth_client, unity_id):
    """BR-REOPEN-QUEUE-001 (révision — réouverture immédiate, hors périmètre de ce
    lot) : le demandeur réouvre lui-même son ticket, sans approbation. Ce test
    vérifie uniquement la partie BR-QUEUE-AUTO-START-001 : une fois le ticket
    réouvert et de retour en File d'attente, une nouvelle prise démarre
    immédiatement un nouveau cycle de traitement."""
    await _ensure_test_account(907, unity_id=unity_id, role="chief-service")
    await _ensure_test_account(909, unity_id=unity_id, role="chief-service")
    request_id = await _create_ticket(auth_client, unity_id, "reopen-then-take")

    take_resp = await _call_as(
        _dep(907, "chief-service", unity_id), "POST", f"/api/v1/requests/{request_id}/qualify",
        {"category": "panne", "priority": "medium", "unit_id": str(unity_id), "assignee_id": "907"},
    )
    assert take_resp.status_code == 200, take_resp.text

    started = await _call_as(
        _dep(907, "chief-service", unity_id), "POST",
        f"/api/v1/requests/{request_id}/start-treatment", {"location": "Site EDG"},
    )
    assert started.status_code == 200, started.text

    resolve_resp = await _call_as(
        _dep(907, "chief-service", unity_id), "POST", f"/api/v1/requests/{request_id}/resolve",
        _FULL_RESOLVE_BODY,
    )
    assert resolve_resp.status_code == 200, resolve_resp.text

    async with auth_client("user") as user_client:
        reopen_resp = await user_client.post(
            f"/api/v1/requests/{request_id}/reopen",
            json={"reason": "Le problème persiste."},
        )
    assert reopen_resp.status_code == 200, reopen_resp.text
    reopened_data = reopen_resp.json()["data"]
    assert reopened_data["request_status"] == "reopened"
    assert reopened_data["assignee_id"] is None
    assert await _in_queue(request_id)

    # Nouvel intervenant (jamais impliqué avant) prend le ticket réouvert.
    take_again = await _call_as(
        _dep(909, "chief-service", unity_id), "POST", f"/api/v1/requests/{request_id}/qualify",
        {"category": "panne", "priority": "medium", "unit_id": str(unity_id), "assignee_id": "909"},
    )
    assert take_again.status_code == 200, take_again.text
    take_again_data = take_again.json()["data"]
    # BR-TRAITEMENT-PROGRESSIF-001 — la reprise après réouverture assigne le
    # nouveau cycle sans le démarrer, comme toute prise depuis la File d'attente.
    assert take_again_data["request_status"] == "assigned"
    assert not await _in_queue(request_id)

    events = await _timeline(auth_client, request_id)
    completed = [e for e in events if e["event_type"] == "treatment_completed"]
    assert len(completed) == 1  # ancien cycle intact, jamais réutilisé/modifié


# ── Non-régression BR-REQUESTER-NO-SELF-TREATMENT-001 ─────────────────────────

async def test_requester_still_cannot_take_own_ticket_from_queue(auth_client, unity_id):
    async with auth_client("user") as user_client:
        payload = {**_REQUEST_PAYLOAD_BASE, "title": "Requester self-take blocked", "unity_id": unity_id}
        created = await user_client.post("/api/v1/requests/", json=payload)
        assert created.status_code == 201, created.text
        request_id = str(created.json()["data"]["id"])

    resp = await _call_as(
        _dep(MOCK_ACCOUNTS["user"].id, "chief-service", unity_id), "POST",
        f"/api/v1/requests/{request_id}/qualify",
        {"category": "panne", "priority": "medium", "unit_id": str(unity_id), "assignee_id": str(MOCK_ACCOUNTS["user"].id)},
    )
    # Bloqué en amont par le conflit d'intérêt générique (assert_ticket_scope,
    # 403) avant même d'atteindre la garde dédiée assert_requester_is_not_handler
    # (400) — BR-REQUESTER-NO-SELF-TREATMENT-001 reste strictement appliquée,
    # l'automatisation "Prendre/Assigner = démarrer" ne la contourne pas.
    assert resp.status_code == 403, resp.text
    assert resp.json()["error_code"] == "FORBIDDEN"
