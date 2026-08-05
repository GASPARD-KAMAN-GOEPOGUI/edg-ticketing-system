from __future__ import annotations

from types import SimpleNamespace

from httpx import ASGITransport, AsyncClient

from api.dependencies import get_current_user
from api.main import app

_REQUEST_PAYLOAD_BASE = {
    "description": "Description de test pour l'escalade exceptionnelle (Lot 3.3).",
    "category": "panne",
    "priority": "medium",
    "is_external": False,
    "requester_name": "Citoyen Test",
    "requester_email": "citoyen@test.edg.gn",
}


async def _create_ticket(auth_client, unity_id: int, title_suffix: str) -> str:
    async with auth_client("user") as user_client:
        payload = {**_REQUEST_PAYLOAD_BASE, "title": f"Test escalate-to-director {title_suffix}", "unity_id": unity_id}
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


async def test_escalate_to_director_fails_without_reason(auth_client, unity_id):
    request_id = await _create_ticket(auth_client, unity_id, "no-reason")

    def _dept_dep():
        return SimpleNamespace(id=950, role="chief-departement", unity_id=unity_id, direction_id=None)

    resp = await _call_as(_dept_dep, "POST", f"/api/v1/requests/{request_id}/escalate-to-director", {"reason": "  "})
    assert resp.status_code == 400, resp.text
    assert resp.json()["error_code"] == "MISSING_REQUIRED_FIELD"


async def test_escalate_to_director_fails_without_director_in_hierarchy(auth_client, unity_id):
    """La fixture `unity_id` (TSDIR) n'a pas de directeur reel rattache dans l'organigramme
    de test — verifie le message d'erreur explicite plutot qu'un crash."""
    request_id = await _create_ticket(auth_client, unity_id, "no-director-found")

    async with auth_client("admin") as admin_client:
        resp = await admin_client.post(
            f"/api/v1/requests/{request_id}/qualify",
            json={"category": "panne", "priority": "medium", "unit_id": unity_id, "assignee_id": 951},
        )
        assert resp.status_code == 200, resp.text

    def _dept_dep():
        return SimpleNamespace(id=951, role="chief-departement", unity_id=unity_id, direction_id=None)

    resp = await _call_as(
        _dept_dep, "POST", f"/api/v1/requests/{request_id}/escalate-to-director",
        {"reason": "Blocage critique, besoin d'arbitrage direct."},
    )
    assert resp.status_code == 422, resp.text
    assert "directeur" in resp.json()["message"].lower()


async def test_other_roles_cannot_call_escalate_to_director(auth_client, unity_id):
    request_id = await _create_ticket(auth_client, unity_id, "role-blocked")

    for role in ("agent-support", "chief-service", "director", "admin"):
        def _dep(role=role):
            return SimpleNamespace(id=960, role=role, unity_id=unity_id, direction_id=None)

        resp = await _call_as(
            _dep, "POST", f"/api/v1/requests/{request_id}/escalate-to-director",
            {"reason": "Test tentative non autorisee."},
        )
        assert resp.status_code == 403, f"role={role} -> {resp.status_code}: {resp.text}"


async def test_regular_escalate_route_unaffected(auth_client, unity_id):
    """Regression : /escalate (generique, find_hierarchical_chief) reste inchange."""
    request_id = await _create_ticket(auth_client, unity_id, "regular-escalate-unaffected")

    def _agent_dep():
        return SimpleNamespace(id=970, role="agent-support", unity_id=unity_id, direction_id=None)

    async with auth_client("admin") as admin_client:
        resp = await admin_client.post(
            f"/api/v1/requests/{request_id}/qualify",
            json={"category": "panne", "priority": "medium", "unit_id": unity_id, "assignee_id": 970},
        )
        assert resp.status_code == 200, resp.text

    resp = await _call_as(
        _agent_dep, "POST", f"/api/v1/requests/{request_id}/escalate",
        {"reason": "Escalade normale de controle."},
    )
    # Pas de chef trouve dans la hierarchie de test -> 422 attendu, jamais un crash / 500.
    assert resp.status_code in (201, 422), resp.text
