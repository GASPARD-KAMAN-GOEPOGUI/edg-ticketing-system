from __future__ import annotations

from types import SimpleNamespace

from httpx import ASGITransport, AsyncClient

from api.dependencies import get_current_user
from api.main import app
from tests.api.test_requests_baseline import _ensure_test_account

_REQUEST_PAYLOAD_BASE = {
    "description": "Description de test pour le narrowing chief-departement (Lot 3).",
    "category": "panne",
    "priority": "medium",
    "is_external": False,
    "requester_name": "Citoyen Test",
    "requester_email": "citoyen@test.edg.gn",
}


async def _create_ticket(auth_client, unity_id: int, title_suffix: str) -> str:
    async with auth_client("user") as user_client:
        payload = {**_REQUEST_PAYLOAD_BASE, "title": f"Test lot3 narrowing {title_suffix}", "unity_id": unity_id}
        resp = await user_client.post("/api/v1/requests/", json=payload)
        assert resp.status_code == 201, resp.text
        return str(resp.json()["data"]["id"])


async def _assign_via_admin(auth_client, request_id: str, unity_id: int, assignee_id: int) -> None:
    await _ensure_test_account(assignee_id, unity_id=unity_id, role="agent-support")
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


async def test_chief_departement_can_call_assign_route(auth_client, unity_id):
    """Philosophie collaborative : la porte de role laisse passer chief-departement.
    L'assignee_id fictif peut echouer ensuite sur "compte introuvable", mais plus sur
    l'autorisation."""
    request_id = await _create_ticket(auth_client, unity_id, "assign-allowed")

    def _dept_dep():
        return SimpleNamespace(id=901, role="chief-departement", unity_id=unity_id, direction_id=None)

    resp = await _call_as(_dept_dep, "POST", f"/api/v1/requests/{request_id}/assign?assignee_id=902")
    assert resp.status_code != 403, resp.text


async def test_chief_service_can_still_call_assign_route(auth_client, unity_id):
    """Regression : chief-service inchangé par le narrowing 3.1. On vérifie que la porte
    de rôle (assert_action_allowed) laisse passer chief-service — l'assignee_id fictif
    fait échouer plus loin sur "compte introuvable" (404), jamais sur l'autorisation (403).
    Le succès bout-en-bout de l'assignation chief-service est déjà couvert par ailleurs
    (test_ticket_actions.py::test_chief_and_admin_can_assign_other_agents)."""
    request_id = await _create_ticket(auth_client, unity_id, "assign-chief-service-ok")

    def _chief_dep():
        return SimpleNamespace(id=903, role="chief-service", unity_id=unity_id, direction_id=None)

    resp = await _call_as(_chief_dep, "POST", f"/api/v1/requests/{request_id}/assign?assignee_id=904")
    assert resp.status_code == 404, resp.text


_RESOLVE_BODY = {
    "summary": "Résumé final de test",
    "solution": "Solution appliquée de test",
    "work_done": "Travail réalisé de test",
}


async def test_chief_departement_can_call_resolve_route_as_current_handler(auth_client, unity_id):
    """BR-TRANSMIT-001 (remplace l'ancien test_chief_departement_cannot_call_resolve_route) :
    l'exclusion Lot 3.2 est levée — un chef de département devenu intervenant actuel
    (assignee_id == lui) peut désormais terminer le traitement."""
    request_id = await _create_ticket(auth_client, unity_id, "resolve-now-allowed")
    await _assign_via_admin(auth_client, request_id, unity_id, assignee_id=905)

    def _dept_dep():
        return SimpleNamespace(id=905, role="chief-departement", unity_id=unity_id, direction_id=None)

    resp = await _call_as(_dept_dep, "POST", f"/api/v1/requests/{request_id}/resolve", _RESOLVE_BODY)
    assert resp.status_code == 200, resp.text


async def test_chief_departement_cannot_resolve_ticket_not_assigned_to_them(auth_client, unity_id):
    """BR-TRANSMIT-001 : la règle n'est plus le rôle mais l'intervenant actuel — un
    chef de département qui n'est PAS assignee_id du ticket reste refusé."""
    request_id = await _create_ticket(auth_client, unity_id, "resolve-still-blocked")
    await _assign_via_admin(auth_client, request_id, unity_id, assignee_id=905)

    def _dept_dep_other():
        return SimpleNamespace(id=999, role="chief-departement", unity_id=unity_id, direction_id=None)

    resp = await _call_as(_dept_dep_other, "POST", f"/api/v1/requests/{request_id}/resolve", _RESOLVE_BODY)
    assert resp.status_code == 403, resp.text


async def test_agent_support_can_still_call_resolve_route(auth_client, unity_id):
    """Regression : agent-support inchangé par le narrowing 3.2. Le body doit désormais
    porter les champs obligatoires summary/solution/work_done (BR-TRANSMIT-001)."""
    request_id = await _create_ticket(auth_client, unity_id, "resolve-agent-ok")
    await _assign_via_admin(auth_client, request_id, unity_id, assignee_id=906)

    def _agent_dep():
        return SimpleNamespace(id=906, role="agent-support", unity_id=unity_id, direction_id=None)

    resp = await _call_as(_agent_dep, "POST", f"/api/v1/requests/{request_id}/resolve", _RESOLVE_BODY)
    assert resp.status_code == 200, resp.text
