"""
BR-ESCALATE-HANDOFF-001 — verifie de bout en bout que lorsqu'un agent-support A
escalade un ticket, celui-ci (1) atterrit bien dans la boite de traitement du
chef hierarchique B (meme requete que "Ma boite de traitement" cote frontend :
GET /requests?assignee_id=<B>) et (2) que B, devenu l'intervenant actuel du
ticket, dispose reellement des actions de traitement (commentaire, puis
resolution) dessus — pas seulement d'une visibilite passive.
"""
from __future__ import annotations

from types import SimpleNamespace

from httpx import ASGITransport, AsyncClient

from api.dependencies import get_current_user
from api.main import app
from tests.api.test_requests_baseline import _ensure_test_account

_REQUEST_PAYLOAD_BASE = {
    "description": "Description de test pour la verification handoff escalade -> chef.",
    "category": "panne",
    "priority": "medium",
    "is_external": False,
    "requester_name": "Citoyen Test",
    "requester_email": "citoyen.handoff@test.edg.gn",
}


async def _call_as(role_dep, method: str, url: str, json: dict | None = None):
    app.dependency_overrides[get_current_user] = role_dep
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return await client.request(method, url, json=json)
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_escalated_ticket_lands_in_chief_inbox_with_full_treatment_actions(auth_client, unity_id):
    agent_id = 8801
    chief_id = 8802
    # Meme unite pour A et B : find_hierarchical_chief() (ServiceEscalade.py) trouve
    # le chef au premier niveau (meme unity_id), sans besoin de remonter l'organigramme.
    await _ensure_test_account(agent_id, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(chief_id, unity_id=unity_id, role="chief-service")

    # 1. Creation de la demande + qualification/assignation initiale a l'agent A.
    async with auth_client("user") as user_client:
        payload = {**_REQUEST_PAYLOAD_BASE, "title": "Test handoff escalade vers chef", "unity_id": unity_id}
        resp = await user_client.post("/api/v1/requests/", json=payload)
        assert resp.status_code == 201, resp.text
        request_id = str(resp.json()["data"]["id"])

    async with auth_client("admin") as admin_client:
        resp = await admin_client.post(
            f"/api/v1/requests/{request_id}/qualify",
            json={"category": "panne", "priority": "medium", "unit_id": unity_id, "assignee_id": agent_id},
        )
        assert resp.status_code == 200, resp.text

    def _agent_dep():
        return SimpleNamespace(id=agent_id, role="agent-support", unity_id=unity_id, direction_id=None, name="Agent A", firstname="Test")

    def _chief_dep():
        return SimpleNamespace(id=chief_id, role="chief-service", unity_id=unity_id, direction_id=None, name="Chef B", firstname="Test")

    # 2. A escalade — doit reussir puisque B (chief-service, meme unite) existe desormais.
    resp = await _call_as(
        _agent_dep, "POST", f"/api/v1/requests/{request_id}/escalate",
        {"reason": "Blocage technique, besoin du chef de service."},
    )
    assert resp.status_code == 201, resp.text

    # Verifie l'etat reel du ticket apres escalade (independant de la forme exacte
    # de la reponse /escalate, qui renvoie un EscalationResponse et non le ticket).
    resp = await _call_as(_chief_dep, "GET", f"/api/v1/requests/{request_id}")
    assert resp.status_code == 200, resp.text
    updated = resp.json()["data"]
    assert updated["request_status"] == "escalated", updated
    assert str(updated["assignee_id"]) == str(chief_id), updated

    # 3. Le ticket apparait dans la boite de traitement de B — meme filtre que
    #    app.my-tickets.tsx (assignee_id=<moi>, cf. is_own_assignee_view bypass RBAC
    #    dans RouteRequest.py::list_requests).
    resp = await _call_as(_chief_dep, "GET", f"/api/v1/requests/?assignee_id={chief_id}&limit=50")
    assert resp.status_code == 200, resp.text
    items = resp.json()["data"]["items"]
    assert any(str(item["id"]) == request_id for item in items), (
        "Le ticket escalade n'apparait pas dans la boite de traitement du chef B."
    )
    matched = next(item for item in items if str(item["id"]) == request_id)
    assert matched["request_status"] == "escalated"

    # 4. B peut ecrire dans la messagerie (intervenant courant du ticket
    #    desormais, cf. BR-MESSAGING-PAIR-001 : conversation privee
    #    demandeur <-> assigne courant).
    resp = await _call_as(
        _chief_dep, "POST", f"/api/v1/requests/{request_id}/comments",
        {"body": "Pris en compte, je regarde ca.", "is_public": False, "peer_id": "1"},
    )
    assert resp.status_code == 201, resp.text

    # 5. B peut terminer le traitement (intervenant actuel, role autorise a resoudre —
    #    cf. ACTION_ALLOWED_ROLES["resolve"] et assert_is_current_handler).
    resp = await _call_as(
        _chief_dep, "POST", f"/api/v1/requests/{request_id}/resolve",
        {
            "summary": "Panne corrigee.",
            "solution": "Remplacement du disjoncteur defectueux.",
            "work_done": "Intervention terrain effectuee par le chef de service.",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["request_status"] == "resolved"


async def test_escalated_ticket_agent_a_loses_it_from_own_inbox(auth_client, unity_id):
    """Corollaire : une fois escalade vers B, le ticket ne doit plus apparaitre
    dans la boite de traitement de A (il n'en est plus l'assigne)."""
    agent_id = 8811
    chief_id = 8812
    await _ensure_test_account(agent_id, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(chief_id, unity_id=unity_id, role="chief-service")

    async with auth_client("user") as user_client:
        payload = {**_REQUEST_PAYLOAD_BASE, "title": "Test handoff escalade - perte boite A", "unity_id": unity_id}
        resp = await user_client.post("/api/v1/requests/", json=payload)
        assert resp.status_code == 201, resp.text
        request_id = str(resp.json()["data"]["id"])

    async with auth_client("admin") as admin_client:
        resp = await admin_client.post(
            f"/api/v1/requests/{request_id}/qualify",
            json={"category": "panne", "priority": "medium", "unit_id": unity_id, "assignee_id": agent_id},
        )
        assert resp.status_code == 200, resp.text

    def _agent_dep():
        return SimpleNamespace(id=agent_id, role="agent-support", unity_id=unity_id, direction_id=None, name="Agent A", firstname="Test")

    resp = await _call_as(
        _agent_dep, "POST", f"/api/v1/requests/{request_id}/escalate",
        {"reason": "Blocage technique, besoin du chef de service."},
    )
    assert resp.status_code == 201, resp.text

    resp = await _call_as(_agent_dep, "GET", f"/api/v1/requests/?assignee_id={agent_id}&limit=50")
    assert resp.status_code == 200, resp.text
    items = resp.json()["data"]["items"]
    assert not any(str(item["id"]) == request_id for item in items), (
        "Le ticket escalade est reste dans la boite de traitement de A alors qu'il ne devrait plus y etre."
    )
