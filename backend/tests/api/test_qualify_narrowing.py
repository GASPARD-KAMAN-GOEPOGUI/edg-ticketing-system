from __future__ import annotations

from types import SimpleNamespace

from httpx import ASGITransport, AsyncClient

from api.dependencies import get_current_user
from api.main import app

_REQUEST_PAYLOAD_BASE = {
    "description": "Description de test pour le narrowing qualify (Lot 2.4).",
    "category": "panne",
    "priority": "medium",
    "is_external": False,
    "requester_name": "Citoyen Test",
    "requester_email": "citoyen@test.edg.gn",
}


async def _create_ticket(client, unity_id: int, title_suffix: str) -> str:
    payload = {**_REQUEST_PAYLOAD_BASE, "title": f"Test qualify narrowing {title_suffix}", "unity_id": unity_id}
    resp = await client.post("/api/v1/requests/", json=payload)
    assert resp.status_code == 201, resp.text
    return str(resp.json()["data"]["id"])


async def _qualify_as(role_dep, request_id: str, unity_id: int, assignee_id: int | None):
    app.dependency_overrides[get_current_user] = role_dep
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            body = {"category": "panne", "priority": "medium", "unit_id": unity_id}
            if assignee_id is not None:
                body["assignee_id"] = assignee_id
            return await client.post(f"/api/v1/requests/{request_id}/qualify", json=body)
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_agent_support_cannot_qualify_to_a_third_party(auth_client, unity_id):
    """Lot 2.4 : le routage vers une personne precise (bouton 'Assigner') est retire a
    agent-support — meme via appel API direct (pas seulement masquage frontend)."""
    async with auth_client("user") as user_client:
        request_id = await _create_ticket(user_client, unity_id, "third-party-blocked")

    def _agent_dep():
        return SimpleNamespace(id=601, role="agent-support", unity_id=unity_id, direction_id=None)

    resp = await _qualify_as(_agent_dep, request_id, unity_id, assignee_id=602)
    assert resp.status_code == 403, resp.text


async def test_agent_support_can_still_self_assign(auth_client, unity_id):
    """Regression : 'Prendre la demande' (auto-assignation, assignee_id == actor.id)
    reste fonctionnel pour agent-support."""
    async with auth_client("user") as user_client:
        request_id = await _create_ticket(user_client, unity_id, "self-assign-ok")

    def _agent_dep():
        return SimpleNamespace(id=603, role="agent-support", unity_id=unity_id, direction_id=None)

    resp = await _qualify_as(_agent_dep, request_id, unity_id, assignee_id=603)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["request_status"] == "assigned"


async def test_chief_service_can_still_route_to_a_third_party(auth_client, unity_id):
    """Regression : chief-service garde le routage vers une personne precise (le
    narrowing du Lot 2.4 ne cible que agent-support)."""
    async with auth_client("user") as user_client:
        request_id = await _create_ticket(user_client, unity_id, "chief-routes-third-party")

    def _chief_dep():
        return SimpleNamespace(id=604, role="chief-service", unity_id=unity_id, direction_id=None)

    resp = await _qualify_as(_chief_dep, request_id, unity_id, assignee_id=605)
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["request_status"] == "assigned"


async def test_admin_can_still_route_to_a_third_party(auth_client, unity_id):
    """Regression : admin inchange."""
    async with auth_client("user") as user_client:
        request_id = await _create_ticket(user_client, unity_id, "admin-routes-third-party")

    async with auth_client("admin") as admin_client:
        resp = await admin_client.post(
            f"/api/v1/requests/{request_id}/qualify",
            json={"category": "panne", "priority": "medium", "unit_id": unity_id, "assignee_id": 606},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["request_status"] == "assigned"
