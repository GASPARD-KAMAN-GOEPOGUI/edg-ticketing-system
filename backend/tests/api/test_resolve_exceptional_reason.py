from __future__ import annotations

from types import SimpleNamespace

from httpx import ASGITransport, AsyncClient

from api.dependencies import get_current_user
from api.main import app

_REQUEST_PAYLOAD_BASE = {
    "description": "Description de test pour la resolution exceptionnelle (Lot 2.6).",
    "category": "panne",
    "priority": "medium",
    "is_external": False,
    "requester_name": "Citoyen Test",
    "requester_email": "citoyen@test.edg.gn",
}


async def _create_assigned_ticket(auth_client, unity_id: int, title_suffix: str, assignee_id: int) -> str:
    async with auth_client("user") as user_client:
        payload = {**_REQUEST_PAYLOAD_BASE, "title": f"Test resolve reason {title_suffix}", "unity_id": unity_id}
        resp = await user_client.post("/api/v1/requests/", json=payload)
        assert resp.status_code == 201, resp.text
        request_id = str(resp.json()["data"]["id"])
    async with auth_client("admin") as admin_client:
        resp = await admin_client.post(
            f"/api/v1/requests/{request_id}/qualify",
            json={"category": "panne", "priority": "medium", "unit_id": unity_id, "assignee_id": assignee_id},
        )
        assert resp.status_code == 200, resp.text
    return request_id


async def _resolve_as(role_dep, request_id: str, body: dict | None):
    app.dependency_overrides[get_current_user] = role_dep
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return await client.post(f"/api/v1/requests/{request_id}/resolve", json=body)
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_chief_service_resolve_requires_reason(auth_client, unity_id):
    request_id = await _create_assigned_ticket(auth_client, unity_id, "chief-no-reason", 701)

    def _chief_dep():
        return SimpleNamespace(id=701, role="chief-service", unity_id=unity_id, direction_id=None)

    resp = await _resolve_as(_chief_dep, request_id, {})
    assert resp.status_code == 422, resp.text


async def test_chief_service_resolve_succeeds_with_reason(auth_client, unity_id):
    request_id = await _create_assigned_ticket(auth_client, unity_id, "chief-with-reason", 702)

    def _chief_dep():
        return SimpleNamespace(id=702, role="chief-service", unity_id=unity_id, direction_id=None)

    resp = await _resolve_as(_chief_dep, request_id, {"reason": "Agent absent, resolution exceptionnelle."})
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["request_status"] == "resolved"


async def test_agent_support_resolve_unaffected_no_reason_needed(auth_client, unity_id):
    """Regression : agent-support n'a pas besoin de motif (narrowing limite a chief-service)."""
    request_id = await _create_assigned_ticket(auth_client, unity_id, "agent-no-reason", 703)

    def _agent_dep():
        return SimpleNamespace(id=703, role="agent-support", unity_id=unity_id, direction_id=None)

    resp = await _resolve_as(_agent_dep, request_id, {})
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["request_status"] == "resolved"


async def test_resolve_without_body_still_works_for_agent_support(auth_client, unity_id):
    """Regression : l'appel front historique envoie un body vide '{}' — doit rester compatible."""
    request_id = await _create_assigned_ticket(auth_client, unity_id, "agent-empty-body", 704)

    def _agent_dep():
        return SimpleNamespace(id=704, role="agent-support", unity_id=unity_id, direction_id=None)

    resp = await _resolve_as(_agent_dep, request_id, None)
    assert resp.status_code == 200, resp.text
