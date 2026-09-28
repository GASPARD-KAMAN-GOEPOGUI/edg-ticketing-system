"""
BR-REQUESTER-NO-SELF-TREATMENT-001 — le demandeur d'un ticket ne peut jamais
devenir son intervenant (request.assignee_id), quel que soit son rôle
professionnel (chief-service, chief-service, chief-departement, director,
admin). Couvre : assign, qualify_triage (routage direct depuis la file
d'attente), transmit_treatment, le PATCH générique admin, la défense en
profondeur en lecture ("Ma boîte de traitement"), et l'intégrité de l'état
après un refus (aucun effet de bord).

Ne modifie ni ne restreint le workflow collaboratif dynamique par ailleurs :
un intervenant autre que le demandeur peut toujours revenir plusieurs fois
(couvert par test_transmit_treatment.py, non dupliqué ici).
"""
from __future__ import annotations

from tests.api.test_requests_baseline import _ensure_test_account
from tests.api.test_transmit_treatment import (
    _REQUEST_PAYLOAD_BASE,
    _FULL_RESOLVE_BODY,
    _assign_via_admin,
    _call_as,
    _dep,
    _timeline,
)


async def _create_ticket_as(role_dep, unity_id: int, title_suffix: str) -> str:
    """Crée un ticket avec `role_dep` comme demandeur (requester_id forcé par le
    backend depuis l'acteur authentifié, cf. RouteRequest.create_request)."""
    payload = {**_REQUEST_PAYLOAD_BASE, "title": f"Test self-treatment {title_suffix}", "unity_id": unity_id}
    resp = await _call_as(role_dep, "POST", "/api/v1/requests/", payload)
    assert resp.status_code == 201, resp.text
    return str(resp.json()["data"]["id"])


async def _my_tickets_ids(role_dep, assignee_id: int) -> set[str]:
    resp = await _call_as(role_dep, "GET", f"/api/v1/requests/?assignee_id={assignee_id}&limit=1000")
    assert resp.status_code == 200, resp.text
    return {str(item["id"]) for item in resp.json()["data"]["items"]}


async def _my_requests_ids(role_dep, requester_id: int) -> set[str]:
    resp = await _call_as(role_dep, "GET", f"/api/v1/requests/?requester_id={requester_id}&limit=1000")
    assert resp.status_code == 200, resp.text
    return {str(item["id"]) for item in resp.json()["data"]["items"]}


# ── 1. Assignation directe vers le demandeur, par un tiers ────────────────────

async def test_assign_to_requester_rejected_when_requester_is_staff(auth_client, unity_id):
    """A (chief-service) crée T1 ; un chef tente de l'assigner à A lui-même — refusé,
    même si A porte un rôle traitant habilité (le conflit d'intérêt prime sur le rôle)."""
    await _ensure_test_account(930, unity_id=unity_id, role="chief-service")  # A, requester
    await _ensure_test_account(931, unity_id=unity_id, role="chief-service")  # acteur

    request_id = await _create_ticket_as(_dep(930, "chief-service", unity_id), unity_id, "assign-requester")

    resp = await _call_as(
        _dep(931, "chief-service", unity_id), "POST",
        f"/api/v1/requests/{request_id}/assign?assignee_id=930",
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["error_code"] == "REQUESTER_CANNOT_TREAT_OWN_TICKET"


# ── 2. Qualification directe (routage triage) vers le demandeur ───────────────

async def test_qualify_triage_target_requester_rejected(auth_client, unity_id):
    await _ensure_test_account(932, unity_id=unity_id, role="chief-service")  # A, requester

    request_id = await _create_ticket_as(_dep(932, "chief-service", unity_id), unity_id, "qualify-requester")

    async with auth_client("admin") as admin_client:
        resp = await admin_client.post(
            f"/api/v1/requests/{request_id}/qualify",
            json={"category": "panne", "priority": "medium", "unit_id": unity_id, "assignee_id": 932},
        )
    assert resp.status_code == 400, resp.text
    assert resp.json()["error_code"] == "REQUESTER_CANNOT_TREAT_OWN_TICKET"


# ── 3. Transmission vers le demandeur, par l'intervenant actuel ───────────────

async def test_transmit_to_requester_rejected(auth_client, unity_id):
    """A (chief-service) crée T1, pris en charge par B. B tente de transmettre à A — refusé."""
    await _ensure_test_account(933, unity_id=unity_id, role="chief-service")  # A, requester
    await _ensure_test_account(934, unity_id=unity_id, role="chief-service")  # B, intervenant

    request_id = await _create_ticket_as(_dep(933, "chief-service", unity_id), unity_id, "transmit-requester")
    await _assign_via_admin(auth_client, request_id, unity_id, assignee_id=934)

    resp = await _call_as(
        _dep(934, "chief-service", unity_id), "POST", f"/api/v1/requests/{request_id}/transmit",
        {"to_user_id": "933", "work_done": "Diagnostic.", "reason": "Tentative de transmission au demandeur."},
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["error_code"] == "REQUESTER_CANNOT_TREAT_OWN_TICKET"


# ── 4. Aucun effet de bord après un refus ──────────────────────────────────────

async def test_rejected_transmit_leaves_state_unchanged(auth_client, unity_id):
    await _ensure_test_account(935, unity_id=unity_id, role="chief-service")  # A, requester
    await _ensure_test_account(936, unity_id=unity_id, role="chief-service")  # B, intervenant

    request_id = await _create_ticket_as(_dep(935, "chief-service", unity_id), unity_id, "no-side-effect")
    await _assign_via_admin(auth_client, request_id, unity_id, assignee_id=936)

    events_before = await _timeline(auth_client, request_id)

    resp = await _call_as(
        _dep(936, "chief-service", unity_id), "POST", f"/api/v1/requests/{request_id}/transmit",
        {"to_user_id": "935", "work_done": "Diagnostic.", "reason": "Tentative refusée."},
    )
    assert resp.status_code == 400, resp.text

    async with auth_client("admin") as admin_client:
        detail = await admin_client.get(f"/api/v1/requests/{request_id}")
    assert detail.status_code == 200, detail.text
    data = detail.json()["data"]
    assert str(data["assignee_id"]) == "936", "l'assignation ne doit pas avoir changé"
    # BR-QUEUE-AUTO-START-001 : la prise en charge initiale démarre déjà le
    # traitement (in_progress) — la valeur de référence change, l'invariant
    # testé ici (aucun changement après un refus) reste identique.
    assert data["request_status"] == "in_progress", "le statut ne doit pas avoir changé"

    events_after = await _timeline(auth_client, request_id)
    assert len(events_after) == len(events_before), "aucun nouvel événement workflow_detail après un refus"


# ── 5. PATCH générique admin — même garde ──────────────────────────────────────

async def test_admin_generic_patch_to_requester_rejected(auth_client, unity_id):
    await _ensure_test_account(937, unity_id=unity_id, role="chief-service")  # A, requester

    request_id = await _create_ticket_as(_dep(937, "chief-service", unity_id), unity_id, "admin-patch-requester")

    async with auth_client("admin") as admin_client:
        resp = await admin_client.put(
            f"/api/v1/requests/{request_id}",
            json={"assignee_id": 937},
        )
    assert resp.status_code == 400, resp.text
    assert resp.json()["error_code"] == "REQUESTER_CANNOT_TREAT_OWN_TICKET"


# ── 6. Scénario complet : A (chief-service) reste demandeur de bout en bout ───

async def test_requester_agent_support_never_in_own_treatment_box(auth_client, unity_id):
    """
    A (chief-service) crée T1 -> B prend -> B transmet à C -> C termine le
    traitement -> A retrouve T1 dans "Mes demandes" mais jamais dans "Ma boîte
    de traitement", à aucune étape, y compris après résolution et après une
    réouverture immédiate (le ticket retourne en file d'attente sans jamais
    redevenir accessible à A comme intervenant).
    """
    await _ensure_test_account(940, unity_id=unity_id, role="chief-service")  # A, requester
    await _ensure_test_account(941, unity_id=unity_id, role="chief-service")  # B
    await _ensure_test_account(942, unity_id=unity_id, role="chief-service")  # C
    a = _dep(940, "chief-service", unity_id)
    b = _dep(941, "chief-service", unity_id)
    c = _dep(942, "chief-service", unity_id)

    request_id = await _create_ticket_as(a, unity_id, "requester-full-cycle")

    # Immédiatement après création : visible pour A dans "Mes demandes", absent
    # de sa boîte de traitement (pas encore assigné de toute façon).
    assert request_id in await _my_requests_ids(a, 940)
    assert request_id not in await _my_tickets_ids(a, 940)

    await _assign_via_admin(auth_client, request_id, unity_id, assignee_id=941)  # B prend

    assert request_id in await _my_requests_ids(a, 940)
    assert request_id not in await _my_tickets_ids(a, 940)
    assert request_id in await _my_tickets_ids(b, 941)

    resp = await _call_as(
        b, "POST", f"/api/v1/requests/{request_id}/transmit",
        {"to_user_id": "942", "work_done": "Diagnostic B.", "reason": "Passage à C."},
    )
    assert resp.status_code == 200, resp.text

    assert request_id not in await _my_tickets_ids(a, 940)
    assert request_id in await _my_tickets_ids(c, 942)

    resp = await _call_as(c, "POST", f"/api/v1/requests/{request_id}/resolve", _FULL_RESOLVE_BODY)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["request_status"] == "resolved"

    # Après résolution : toujours dans "Mes demandes" de A, jamais dans sa boîte
    # de traitement — même si assignee_id (C) n'est de toute façon pas A ici.
    assert request_id in await _my_requests_ids(a, 940)
    assert request_id not in await _my_tickets_ids(a, 940)

    # A réouvre lui-même son ticket — réouverture immédiate, sans approbation
    # hiérarchique (BR-REOPEN-QUEUE-001, révision). `actor_name` fourni
    # explicitement (le mock d'acteur _dep() n'expose pas d'attribut `.name`,
    # requis en repli par cette route quand `actor_name` est absent —
    # spécificité du test, pas du métier).
    resp = await _call_as(
        a, "POST", f"/api/v1/requests/{request_id}/reopen",
        {"reason": "Le problème persiste.", "actor_name": "Agent A"},
    )
    assert resp.status_code == 200, resp.text
    reopened = resp.json()["data"]
    assert reopened["request_status"] == "reopened"
    assert reopened["assignee_id"] is None, "BR-REOPEN-QUEUE-001 : assignee libéré, jamais réaffecté à A"

    # T1 est de retour en file d'attente, non assigné — toujours absent de la
    # boîte de traitement de A, qui reste seulement son demandeur.
    assert request_id in await _my_requests_ids(a, 940)
    assert request_id not in await _my_tickets_ids(a, 940)

    async with auth_client("admin") as admin_client:
        triage_resp = await admin_client.get("/api/v1/requests/triage?limit=100")
    assert triage_resp.status_code == 200, triage_resp.text
    triage_ids = {str(item["id"]) for item in triage_resp.json()["data"]["items"]}
    assert request_id in triage_ids, "le ticket réouvert doit réapparaître en file d'attente"

    # Un nouvel intervenant (B) peut le reprendre depuis la file d'attente — le
    # workflow dynamique n'est pas restreint par ailleurs (couvert par
    # test_reopen_queue.py, non dupliqué ici).
