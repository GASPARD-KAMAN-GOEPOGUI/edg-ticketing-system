"""
BR-REOPEN-QUEUE-001 — Retour automatique d'un ticket réouvert dans la File d'attente.

Couvre : l'approbation de réouverture libère l'intervenant (assignee_id=None),
remet le ticket en file d'attente (in_triage=True), conserve intégralement
l'historique/les cycles/les participants précédents, notifie sans réaffecter
automatiquement personne, et permet à un nouvel intervenant de reprendre le
workflow collaboratif dynamique (transmission/résolution) depuis un nouveau cycle.
"""
from __future__ import annotations

from types import SimpleNamespace

from httpx import ASGITransport, AsyncClient

from api.dependencies import get_current_user
from api.main import app
from tests.api.test_requests_baseline import _ensure_test_account

_REQUEST_PAYLOAD_BASE = {
    "description": "Description de test pour le retour en file d'attente apres reouverture (BR-REOPEN-QUEUE-001).",
    "category": "panne",
    "priority": "medium",
    "is_external": False,
    "requester_name": "Citoyen Test",
    "requester_email": "citoyen@test.edg.gn",
}

_FULL_RESOLVE_BODY = {
    "summary": "Resume final de test",
    "solution": "Solution appliquee de test",
    "work_done": "Travail realise de test",
}


async def _create_ticket(auth_client, unity_id: int, title_suffix: str) -> str:
    async with auth_client("user") as user_client:
        payload = {**_REQUEST_PAYLOAD_BASE, "title": f"Test reopen-queue {title_suffix}", "unity_id": unity_id}
        resp = await user_client.post("/api/v1/requests/", json=payload)
        assert resp.status_code == 201, resp.text
        return str(resp.json()["data"]["id"])


async def _assign_via_admin(auth_client, request_id: str, unity_id: int, assignee_id: int) -> None:
    async with auth_client("admin") as admin_client:
        resp = await admin_client.post(
            f"/api/v1/requests/{request_id}/qualify",
            json={"category": "panne", "priority": "medium", "unit_id": unity_id, "assignee_id": assignee_id},
        )
        assert resp.status_code == 200, resp.text


async def _call_as(role_dep, method: str, url: str, json: dict | None = None):
    app.dependency_overrides[get_current_user] = role_dep
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return await client.request(method, url, json=json)
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def _dep(account_id: int, role: str, unity_id: int | None = None):
    def _factory():
        return SimpleNamespace(id=account_id, role=role, unity_id=unity_id, direction_id=None)
    return _factory


async def _timeline(auth_client, request_id: str) -> list[dict]:
    async with auth_client("admin") as admin_client:
        resp = await admin_client.get(f"/api/v1/requests/{request_id}/timeline")
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


async def _build_resolved_ticket_with_two_cycles(auth_client, unity_id: int, suffix: str, agent_a: int, agent_b: int) -> str:
    """Ticket pris par agent_a, transmis a agent_b, resolu par agent_b — 2 cycles avant reouverture."""
    request_id = await _create_ticket(auth_client, unity_id, suffix)
    await _assign_via_admin(auth_client, request_id, unity_id, assignee_id=agent_a)

    transmit_resp = await _call_as(
        _dep(agent_a, "agent-support", unity_id), "POST", f"/api/v1/requests/{request_id}/transmit",
        {"to_user_id": str(agent_b), "work_done": "Diagnostic effectue.", "reason": "Intervention specialisee necessaire."},
    )
    assert transmit_resp.status_code == 200, transmit_resp.text

    resolve_resp = await _call_as(
        _dep(agent_b, "agent-support", unity_id), "POST", f"/api/v1/requests/{request_id}/resolve",
        _FULL_RESOLVE_BODY,
    )
    assert resolve_resp.status_code == 200, resolve_resp.text
    return request_id


# ── 1-3. Cycle de vie de la demande de reouverture ─────────────────────────────

async def test_resolved_ticket_stays_resolved_until_approval(auth_client, unity_id):
    await _ensure_test_account(701, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(702, unity_id=unity_id, role="agent-support")
    request_id = await _build_resolved_ticket_with_two_cycles(auth_client, unity_id, "stays-resolved", 701, 702)

    async with auth_client("user") as user_client:
        req_resp = await user_client.post(
            f"/api/v1/requests/{request_id}/request-reopen",
            json={"reason": "Le probleme persiste apres la premiere resolution."},
        )
    assert req_resp.status_code == 200, req_resp.text
    assert req_resp.json()["data"]["request_status"] == "resolved"
    assert req_resp.json()["data"]["assignee_id"] == 702


# ── 4-8. Approbation : assignee libere, statut, historique/motif conserves ────

async def test_approval_frees_assignee_and_returns_to_queue(auth_client, unity_id):
    await _ensure_test_account(703, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(704, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(705, unity_id=unity_id, role="chief-service")
    request_id = await _build_resolved_ticket_with_two_cycles(auth_client, unity_id, "frees-assignee", 703, 704)

    async with auth_client("user") as user_client:
        await user_client.post(
            f"/api/v1/requests/{request_id}/request-reopen",
            json={"reason": "Le probleme persiste apres la premiere resolution."},
        )

    events_before = await _timeline(auth_client, request_id)
    count_before = len(events_before)

    approve_resp = await _call_as(
        _dep(705, "chief-service", unity_id), "POST", f"/api/v1/requests/{request_id}/reopen",
    )
    assert approve_resp.status_code == 200, approve_resp.text
    data = approve_resp.json()["data"]

    assert data["request_status"] == "reopened"
    assert data["assignee_id"] is None

    events_after = await _timeline(auth_client, request_id)
    assert len(events_after) == count_before + 1, "aucun ancien evenement ne doit disparaitre, un seul nouveau ajoute"

    reopened_event = events_after[-1]
    assert reopened_event["event_type"] == "reopened"
    infos = reopened_event["infos"]
    assert infos["previous_assignee_id"] == 704
    assert infos.get("new_assignee_id") is None  # _clean_infos supprime les cles None
    assert infos["reopen_reason"] == "Le probleme persiste apres la premiere resolution."
    assert infos["previous_status"] == "resolved"
    assert infos["new_status"] == "reopened"
    assert infos["previous_cycle_number"] == 2  # transmit (cycle 1) + resolve (cycle 2)
    assert infos["next_cycle_number"] == 3
    assert reopened_event["comment"] == "Le probleme persiste apres la premiere resolution."

    # Anciens cycles et anciens participants intacts (rien supprime/modifie).
    event_types = [e["event_type"] for e in events_after]
    assert "treatment_transmitted" in event_types
    assert "treatment_completed" in event_types
    transmitted_event = next(e for e in events_after if e["event_type"] == "treatment_transmitted")
    assert transmitted_event["infos"]["previous_assignee_id"] == 703
    assert str(transmitted_event["infos"]["new_assignee_id"]) == "704"
    resolved_event = next(e for e in events_after if e["event_type"] == "treatment_completed")
    assert resolved_event.get("agent_id") == 704


# ── 9-10. Criteres File d'attente ──────────────────────────────────────────────

async def test_reopened_ticket_appears_in_triage_and_leaves_old_assignee_list(auth_client, unity_id):
    await _ensure_test_account(706, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(707, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(708, unity_id=unity_id, role="chief-service")
    request_id = await _build_resolved_ticket_with_two_cycles(auth_client, unity_id, "queue-visible", 706, 707)

    async with auth_client("user") as user_client:
        await user_client.post(
            f"/api/v1/requests/{request_id}/request-reopen",
            json={"reason": "Nouvelle panne liee au meme incident."},
        )
    await _call_as(_dep(708, "chief-service", unity_id), "POST", f"/api/v1/requests/{request_id}/reopen")

    triage_resp = await _call_as(_dep(706, "agent-support", unity_id), "GET", "/api/v1/requests/triage?limit=100")
    assert triage_resp.status_code == 200, triage_resp.text
    triage_ids = {str(item["id"]) for item in triage_resp.json()["data"]["items"]}
    assert request_id in triage_ids, "le ticket reouvert doit apparaitre dans la File d'attente (/requests/triage)"

    old_assignee_resp = await _call_as(
        _dep(707, "agent-support", unity_id), "GET", "/api/v1/requests/?assignee_id=707",
    )
    assert old_assignee_resp.status_code == 200, old_assignee_resp.text
    old_assignee_ids = {str(item["id"]) for item in old_assignee_resp.json()["data"]["items"]}
    assert request_id not in old_assignee_ids, "le ticket ne doit plus figurer dans la liste active de l'ancien assignee"


# ── 11-15. Reprise depuis la File d'attente -> nouveau cycle collaboratif ─────

async def test_new_agent_can_take_ticket_and_resume_collaborative_workflow(auth_client, unity_id):
    await _ensure_test_account(709, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(710, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(711, unity_id=unity_id, role="chief-service")
    await _ensure_test_account(712, unity_id=unity_id, role="agent-support")  # nouvel agent C
    await _ensure_test_account(713, unity_id=unity_id, role="agent-support")  # agent D
    request_id = await _build_resolved_ticket_with_two_cycles(auth_client, unity_id, "resume-workflow", 709, 710)

    async with auth_client("user") as user_client:
        await user_client.post(
            f"/api/v1/requests/{request_id}/request-reopen",
            json={"reason": "Necessite une nouvelle intervention."},
        )
    await _call_as(_dep(711, "chief-service", unity_id), "POST", f"/api/v1/requests/{request_id}/reopen")

    # Un acteur non courant (assignee=None) ne peut ni transmettre ni resoudre tant
    # que personne n'a repris le ticket.
    blocked_transmit = await _call_as(
        _dep(709, "agent-support", unity_id), "POST", f"/api/v1/requests/{request_id}/transmit",
        {"to_user_id": "710", "work_done": "x", "reason": "x"},
    )
    assert blocked_transmit.status_code in (400, 403), blocked_transmit.text

    # Agent C (jamais implique avant) prend le ticket depuis la File d'attente.
    take_resp = await _call_as(
        _dep(712, "agent-support", unity_id), "POST", f"/api/v1/requests/{request_id}/qualify",
        {"category": "panne", "priority": "medium", "unit_id": str(unity_id), "assignee_id": "712"},
    )
    assert take_resp.status_code == 200, take_resp.text
    taken_data = take_resp.json()["data"]
    assert taken_data["assignee_id"] == 712
    assert taken_data["request_status"] == "assigned"

    # Agent C transmet a Agent D — le workflow collaboratif dynamique a bien repris.
    transmit_resp = await _call_as(
        _dep(712, "agent-support", unity_id), "POST", f"/api/v1/requests/{request_id}/transmit",
        {"to_user_id": "713", "work_done": "Nouveau diagnostic apres reouverture.", "reason": "Intervention complementaire necessaire."},
    )
    assert transmit_resp.status_code == 200, transmit_resp.text
    assert transmit_resp.json()["data"]["assignee_id"] == 713

    # Agent D termine le nouveau traitement.
    final_resolve = await _call_as(
        _dep(713, "agent-support", unity_id), "POST", f"/api/v1/requests/{request_id}/resolve",
        _FULL_RESOLVE_BODY,
    )
    assert final_resolve.status_code == 200, final_resolve.text
    assert final_resolve.json()["data"]["request_status"] == "resolved"

    events = await _timeline(auth_client, request_id)
    cycle_events = [e for e in events if e["event_type"] in ("treatment_transmitted", "treatment_completed")]
    cycle_numbers = [e["infos"]["cycle_number"] for e in cycle_events]
    assert cycle_numbers == sorted(cycle_numbers), "la numerotation des cycles continue sans etre reinitialisee"
    # L'ancien intervenant du premier cycle (709) reste visible dans l'historique.
    first_transmit = next(e for e in events if e["event_type"] == "treatment_transmitted")
    assert first_transmit["infos"]["previous_assignee_id"] == 709, "l'ancien intervenant (cycle 1) reste dans l'historique"


# ── 16-17. Autorisation et double approbation ──────────────────────────────────

async def test_unauthorized_role_cannot_approve_reopen(auth_client, unity_id):
    await _ensure_test_account(714, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(715, unity_id=unity_id, role="agent-support")
    request_id = await _build_resolved_ticket_with_two_cycles(auth_client, unity_id, "unauthorized-approve", 714, 715)

    async with auth_client("user") as user_client:
        await user_client.post(
            f"/api/v1/requests/{request_id}/request-reopen",
            json={"reason": "Motif de test."},
        )
    resp = await _call_as(_dep(715, "agent-support", unity_id), "POST", f"/api/v1/requests/{request_id}/reopen")
    assert resp.status_code == 403, resp.text


async def test_double_approval_is_rejected(auth_client, unity_id):
    await _ensure_test_account(716, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(717, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(718, unity_id=unity_id, role="chief-service")
    request_id = await _build_resolved_ticket_with_two_cycles(auth_client, unity_id, "double-approval", 716, 717)

    async with auth_client("user") as user_client:
        await user_client.post(
            f"/api/v1/requests/{request_id}/request-reopen",
            json={"reason": "Motif de test."},
        )
    first = await _call_as(_dep(718, "chief-service", unity_id), "POST", f"/api/v1/requests/{request_id}/reopen")
    assert first.status_code == 200, first.text

    second = await _call_as(_dep(718, "chief-service", unity_id), "POST", f"/api/v1/requests/{request_id}/reopen")
    assert second.status_code == 400, second.text


# ── 19. Notification demandeur ─────────────────────────────────────────────────

async def test_requester_notified_on_reopen_approval(auth_client, unity_id):
    from sqlalchemy import select
    from tests.conftest import _TestSession, MOCK_ACCOUNTS
    from api.models.ModelNotification import Notification

    await _ensure_test_account(719, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(720, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(721, unity_id=unity_id, role="chief-service")
    request_id = await _build_resolved_ticket_with_two_cycles(auth_client, unity_id, "notify-requester", 719, 720)

    async with auth_client("user") as user_client:
        await user_client.post(
            f"/api/v1/requests/{request_id}/request-reopen",
            json={"reason": "Motif de test notification."},
        )
    await _call_as(_dep(721, "chief-service", unity_id), "POST", f"/api/v1/requests/{request_id}/reopen")

    async with _TestSession() as session:
        rows = (
            await session.execute(
                select(Notification).where(
                    Notification.recipient_id == MOCK_ACCOUNTS["user"].id,
                    Notification.request_id == int(request_id),
                    Notification.title == "Votre demande de réouverture a été approuvée",
                )
            )
        ).scalars().all()
        assert len(rows) == 1, "le demandeur doit recevoir exactement une notification d'approbation"

        old_assignee_notifs = (
            await session.execute(
                select(Notification).where(
                    Notification.recipient_id == 720,
                    Notification.request_id == int(request_id),
                    Notification.title == "Ticket réouvert",
                )
            )
        ).scalars().all()
        assert len(old_assignee_notifs) == 1, "l'ancien intervenant recoit une notification informative (pas de reaffectation)"


# ── 21-22. Immutabilite historique + pas d'affectation automatique ────────────

async def test_no_automatic_reassignment_to_previous_agent(auth_client, unity_id):
    await _ensure_test_account(722, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(723, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(724, unity_id=unity_id, role="chief-service")
    request_id = await _build_resolved_ticket_with_two_cycles(auth_client, unity_id, "no-auto-reassign", 722, 723)

    async with auth_client("user") as user_client:
        await user_client.post(
            f"/api/v1/requests/{request_id}/request-reopen",
            json={"reason": "Test non-reaffectation automatique."},
        )
    approve_resp = await _call_as(_dep(724, "chief-service", unity_id), "POST", f"/api/v1/requests/{request_id}/reopen")
    assert approve_resp.status_code == 200
    assert approve_resp.json()["data"]["assignee_id"] is None, "assignee_id doit rester null tant que personne n'a repris le ticket"
