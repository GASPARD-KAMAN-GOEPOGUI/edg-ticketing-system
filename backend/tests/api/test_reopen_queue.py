"""
BR-REOPEN-QUEUE-001 (révision — réouverture immédiate) — le demandeur réouvre
son ticket lui-même, sans approbation hiérarchique. Le ticket retourne
directement dans la File d'attente (assignee_id=None, in_triage=True) pour un
nouveau cycle de traitement entièrement dynamique.

Remplace l'ancien mécanisme en deux phases (request_reopen → approbation
chef/directeur/admin → reopen), supprimé : /request-reopen et /reject-reopen
n'existent plus, un seul comportement métier officiel subsiste sur /reopen.
"""
from __future__ import annotations

from types import SimpleNamespace

from httpx import ASGITransport, AsyncClient

from api.dependencies import get_current_user
from api.main import app
from tests.conftest import MOCK_ACCOUNTS
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


async def _create_ticket_as(role_dep, unity_id: int, title_suffix: str) -> str:
    """Crée un ticket avec `role_dep` comme demandeur (requester_id forcé depuis
    l'acteur authentifié, cf. RouteRequest.create_request) — utilisé pour les
    scénarios où le demandeur porte un rôle traitant (agent-support, etc.)."""
    payload = {**_REQUEST_PAYLOAD_BASE, "title": f"Test reopen-queue {title_suffix}", "unity_id": unity_id}
    resp = await _call_as(role_dep, "POST", "/api/v1/requests/", payload)
    assert resp.status_code == 201, resp.text
    return str(resp.json()["data"]["id"])


async def _assign_via_admin(auth_client, request_id: str, unity_id: int, assignee_id: int) -> None:
    async with auth_client("admin") as admin_client:
        resp = await admin_client.post(
            f"/api/v1/requests/{request_id}/qualify",
            json={"category": "panne", "priority": "medium", "unit_id": unity_id, "assignee_id": assignee_id},
        )
        assert resp.status_code == 200, resp.text


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


async def _reopen_as_user(auth_client, request_id: str, reason: str):
    async with auth_client("user") as user_client:
        return await user_client.post(
            f"/api/v1/requests/{request_id}/reopen",
            json={"reason": reason},
        )


# ── 1-6. Réouverture immédiate : aucune approbation, statut/assignee/in_triage ─

async def test_requester_reopens_immediately_no_approval_needed(auth_client, unity_id):
    await _ensure_test_account(701, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(702, unity_id=unity_id, role="agent-support")
    request_id = await _build_resolved_ticket_with_two_cycles(auth_client, unity_id, "immediate", 701, 702)

    resp = await _reopen_as_user(auth_client, request_id, "Le probleme persiste apres la premiere resolution.")
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    assert data["request_status"] == "reopened", "aucune phase intermediaire — reouvert directement"
    assert data["assignee_id"] is None
    assert data["in_triage"] is True


async def test_reopen_without_reason_rejected(auth_client, unity_id):
    await _ensure_test_account(703, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(704, unity_id=unity_id, role="agent-support")
    request_id = await _build_resolved_ticket_with_two_cycles(auth_client, unity_id, "no-reason", 703, 704)

    resp = await _reopen_as_user(auth_client, request_id, "   ")
    assert resp.status_code == 400, resp.text


# ── 7-10. Historique intact, nouveau cycle créé, ancien intervenant non réaffecté ─

async def test_reopen_preserves_history_and_creates_new_cycle(auth_client, unity_id):
    await _ensure_test_account(705, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(706, unity_id=unity_id, role="agent-support")
    request_id = await _build_resolved_ticket_with_two_cycles(auth_client, unity_id, "history-intact", 705, 706)

    events_before = await _timeline(auth_client, request_id)
    count_before = len(events_before)

    resp = await _reopen_as_user(auth_client, request_id, "Nouvelle panne liee au meme incident.")
    assert resp.status_code == 200, resp.text

    events_after = await _timeline(auth_client, request_id)
    assert len(events_after) == count_before + 1, "aucun ancien evenement ne doit disparaitre, un seul nouveau ajoute"

    reopened_event = events_after[-1]
    assert reopened_event["event_type"] == "reopened"
    infos = reopened_event["infos"]
    assert infos["previous_assignee_id"] == 706
    assert infos.get("new_assignee_id") is None  # _clean_infos supprime les cles None
    assert infos["reopen_reason"] == "Nouvelle panne liee au meme incident."
    assert infos["previous_status"] == "resolved"
    assert infos["new_status"] == "reopened"
    assert infos["previous_cycle_number"] == 2  # transmit (cycle 1) + resolve (cycle 2)
    assert infos["next_cycle_number"] == 3
    assert reopened_event["comment"] == "Nouvelle panne liee au meme incident."

    # Anciens cycles et anciens participants intacts (rien supprime/modifie).
    event_types = [e["event_type"] for e in events_after]
    assert "treatment_transmitted" in event_types
    assert "treatment_completed" in event_types
    transmitted_event = next(e for e in events_after if e["event_type"] == "treatment_transmitted")
    assert transmitted_event["infos"]["previous_assignee_id"] == 705
    assert str(transmitted_event["infos"]["new_assignee_id"]) == "706"
    resolved_event = next(e for e in events_after if e["event_type"] == "treatment_completed")
    assert resolved_event.get("agent_id") == 706


# ── 5-6. Critères File d'attente / absence de la boîte de l'ancien intervenant ──

async def test_reopened_ticket_appears_in_triage_and_leaves_old_assignee_list(auth_client, unity_id):
    await _ensure_test_account(707, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(708, unity_id=unity_id, role="agent-support")
    request_id = await _build_resolved_ticket_with_two_cycles(auth_client, unity_id, "queue-visible", 707, 708)

    resp = await _reopen_as_user(auth_client, request_id, "Necessite une nouvelle intervention.")
    assert resp.status_code == 200, resp.text

    triage_resp = await _call_as(_dep(707, "agent-support", unity_id), "GET", "/api/v1/requests/triage?limit=100")
    assert triage_resp.status_code == 200, triage_resp.text
    triage_ids = {str(item["id"]) for item in triage_resp.json()["data"]["items"]}
    assert request_id in triage_ids, "le ticket reouvert doit apparaitre dans la File d'attente (/requests/triage)"

    old_assignee_resp = await _call_as(
        _dep(708, "agent-support", unity_id), "GET", "/api/v1/requests/?assignee_id=708",
    )
    assert old_assignee_resp.status_code == 200, old_assignee_resp.text
    old_assignee_ids = {str(item["id"]) for item in old_assignee_resp.json()["data"]["items"]}
    assert request_id not in old_assignee_ids, "le ticket ne doit plus figurer dans la liste active de l'ancien assignee"


# ── Reprise depuis la File d'attente -> nouveau cycle collaboratif (non-régression) ─

async def test_new_agent_can_take_ticket_and_resume_collaborative_workflow(auth_client, unity_id):
    await _ensure_test_account(709, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(710, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(712, unity_id=unity_id, role="agent-support")  # nouvel agent C
    await _ensure_test_account(713, unity_id=unity_id, role="agent-support")  # agent D
    request_id = await _build_resolved_ticket_with_two_cycles(auth_client, unity_id, "resume-workflow", 709, 710)

    resp = await _reopen_as_user(auth_client, request_id, "Necessite une nouvelle intervention.")
    assert resp.status_code == 200, resp.text

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
    # BR-QUEUE-AUTO-START-001 : la prise depuis la File d'attente (même sur un
    # ticket réouvert, nouveau cycle) démarre directement le traitement.
    assert taken_data["request_status"] == "in_progress"

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


# ── Autorisation : seul le demandeur peut réouvrir ─────────────────────────────

async def test_non_requester_cannot_reopen(auth_client, unity_id):
    await _ensure_test_account(714, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(715, unity_id=unity_id, role="agent-support")
    request_id = await _build_resolved_ticket_with_two_cycles(auth_client, unity_id, "unauthorized", 714, 715)

    resp = await _call_as(
        _dep(715, "agent-support", unity_id), "POST", f"/api/v1/requests/{request_id}/reopen",
        {"reason": "Tentative non autorisee."},
    )
    assert resp.status_code == 403, resp.text


async def test_double_reopen_is_rejected(auth_client, unity_id):
    await _ensure_test_account(716, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(717, unity_id=unity_id, role="agent-support")
    request_id = await _build_resolved_ticket_with_two_cycles(auth_client, unity_id, "double-reopen", 716, 717)

    first = await _reopen_as_user(auth_client, request_id, "Motif de test.")
    assert first.status_code == 200, first.text

    # Le ticket est maintenant "reopened", pas resolved/rejected/closed — le
    # meme demandeur ne peut pas le reouvrir une seconde fois immediatement.
    second = await _reopen_as_user(auth_client, request_id, "Deuxieme tentative.")
    assert second.status_code == 400, second.text


# ── Requester ne devient jamais intervenant (BR-REQUESTER-NO-SELF-TREATMENT-001) ─

async def test_requester_cannot_take_own_reopened_ticket(auth_client, unity_id):
    """A (agent-support) crée son propre ticket, B le traite et le résout, A le
    réouvre — A ne doit jamais pouvoir se le réassigner lui-même depuis la File
    d'attente, même après réouverture (intégration avec BR-REQUESTER-NO-SELF-
    TREATMENT-001, non affaibli par la réouverture immédiate)."""
    a = _dep(718, "agent-support", unity_id)
    b = _dep(719, "agent-support", unity_id)
    await _ensure_test_account(718, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(719, unity_id=unity_id, role="agent-support")

    request_id = await _create_ticket_as(a, unity_id, "no-self-take-after-reopen")
    await _assign_via_admin(auth_client, request_id, unity_id, assignee_id=719)

    resolve_resp = await _call_as(b, "POST", f"/api/v1/requests/{request_id}/resolve", _FULL_RESOLVE_BODY)
    assert resolve_resp.status_code == 200, resolve_resp.text

    reopen_resp = await _call_as(
        a, "POST", f"/api/v1/requests/{request_id}/reopen",
        {"reason": "Le probleme persiste.", "actor_name": "Agent A"},
    )
    assert reopen_resp.status_code == 200, reopen_resp.text
    assert reopen_resp.json()["data"]["assignee_id"] is None

    # A lui-même ne peut agir sur son propre ticket (garde générale — conflit
    # d'intérêt acteur == demandeur, indépendante de la cible visée).
    self_take_resp = await _call_as(
        a, "POST", f"/api/v1/requests/{request_id}/qualify",
        {"category": "panne", "priority": "medium", "unit_id": str(unity_id), "assignee_id": "718"},
    )
    assert self_take_resp.status_code == 403, self_take_resp.text

    # Un tiers (admin) qui tenterait de réaffecter explicitement le ticket réouvert
    # à A est bloqué par la garde dédiée cible == demandeur (BR-REQUESTER-NO-SELF-
    # TREATMENT-001), qui survit donc bien à la réouverture immédiate.
    third_party_resp = await _call_as(
        _dep(999, "admin", None), "POST", f"/api/v1/requests/{request_id}/qualify",
        {"category": "panne", "priority": "medium", "unit_id": str(unity_id), "assignee_id": "718"},
    )
    assert third_party_resp.status_code == 400, third_party_resp.text
    assert third_party_resp.json()["error_code"] == "REQUESTER_CANNOT_TREAT_OWN_TICKET"


# ── Notifications réouverture (demandeur App+Email, ancien intervenant App-only) ─

async def test_reopen_notifications_requester_and_previous_handler(auth_client, unity_id):
    from sqlalchemy import select
    from tests.conftest import _TestSession
    from api.models.ModelNotification import Notification

    await _ensure_test_account(720, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(721, unity_id=unity_id, role="agent-support")
    request_id = await _build_resolved_ticket_with_two_cycles(auth_client, unity_id, "notify-requester", 720, 721)

    resp = await _reopen_as_user(auth_client, request_id, "Motif de test notification.")
    assert resp.status_code == 200, resp.text

    async with _TestSession() as session:
        rows = (
            await session.execute(
                select(Notification).where(
                    Notification.recipient_id == MOCK_ACCOUNTS["user"].id,
                    Notification.request_id == int(request_id),
                    Notification.title == "Ticket réouvert",
                )
            )
        ).scalars().all()
        assert len(rows) == 1, "le demandeur doit recevoir exactement une notification de réouverture"

        old_assignee_notifs = (
            await session.execute(
                select(Notification).where(
                    Notification.recipient_id == 721,
                    Notification.request_id == int(request_id),
                    Notification.title == "Ticket réouvert",
                )
            )
        ).scalars().all()
        assert len(old_assignee_notifs) == 1, "l'ancien intervenant recoit une notification informative (pas de reaffectation)"


# ── Pas d'affectation automatique de l'ancien intervenant ──────────────────────

async def test_no_automatic_reassignment_to_previous_agent(auth_client, unity_id):
    await _ensure_test_account(722, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(723, unity_id=unity_id, role="agent-support")
    request_id = await _build_resolved_ticket_with_two_cycles(auth_client, unity_id, "no-auto-reassign", 722, 723)

    resp = await _reopen_as_user(auth_client, request_id, "Test non-reaffectation automatique.")
    assert resp.status_code == 200
    assert resp.json()["data"]["assignee_id"] is None, "assignee_id doit rester null tant que personne n'a repris le ticket"


# ── Ancien mécanisme supprimé : les routes n'existent plus ─────────────────────

async def test_old_two_phase_routes_no_longer_exist(auth_client, unity_id):
    await _ensure_test_account(724, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(725, unity_id=unity_id, role="agent-support")
    request_id = await _build_resolved_ticket_with_two_cycles(auth_client, unity_id, "old-routes-gone", 724, 725)

    # Les anciens chemins ne mènent plus à aucun comportement métier fonctionnel
    # (404 chemin inconnu, ou 405 si Starlette signale qu'aucune méthode n'est
    # enregistrée sur un préfixe de route proche — dans les deux cas, la requête
    # échoue et aucune mutation ne peut avoir lieu par ces anciens chemins).
    async with auth_client("user") as user_client:
        old_request_reopen = await user_client.post(
            f"/api/v1/requests/{request_id}/request-reopen",
            json={"reason": "Ancien mecanisme."},
        )
    assert old_request_reopen.status_code in (404, 405), old_request_reopen.text

    old_reject_reopen = await _call_as(
        _dep(725, "chief-service", unity_id), "POST", f"/api/v1/requests/{request_id}/reject-reopen",
        {"reason": "Ancien mecanisme."},
    )
    assert old_reject_reopen.status_code in (404, 405), old_reject_reopen.text
