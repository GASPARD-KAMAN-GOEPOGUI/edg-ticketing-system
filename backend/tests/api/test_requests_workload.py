from __future__ import annotations

from types import SimpleNamespace

from api.dependencies import get_current_user
from api.main import app

_REQUEST_PAYLOAD_BASE = {
    "title": "Test workload ticket",
    "description": "Description de test pour la charge par agent.",
    "category": "panne",
    "priority": "medium",
    "is_external": False,
    "requester_name": "Citoyen Test",
    "requester_email": "citoyen@test.edg.gn",
}


async def _create_as_user(client, unity_id: int, title_suffix: str) -> str:
    """Crée la demande via le rôle `user` — le rôle `admin` qui qualifie ensuite ne doit pas
    être le demandeur, sinon BR-OWN-001 (conflit d'intérêt) bloque l'action `qualify`.
    Un titre distinct par appel évite la détection anti-doublon (même requester + même titre)."""
    payload = {**_REQUEST_PAYLOAD_BASE, "title": f"Test workload ticket {title_suffix}", "unity_id": unity_id}
    resp = await client.post("/api/v1/requests/", json=payload)
    assert resp.status_code == 201, resp.text
    return str(resp.json()["data"]["id"])


async def _qualify_and_assign(client, request_id: str, unity_id: int, assignee_id: int) -> None:
    resp = await client.post(
        f"/api/v1/requests/{request_id}/qualify",
        json={"category": "panne", "priority": "medium", "unit_id": unity_id, "assignee_id": assignee_id},
    )
    assert resp.status_code == 200, resp.text


async def test_workload_by_unit_counts_and_scope(auth_client, test_unity):
    """Une seule unity de test (fixture partagée, codename fixe) pour éviter toute collision
    entre plusieurs invocations de `test_unity` dans le même fichier.

    Vérifie deux choses en une seule passe :
    1. L'agrégation compte les tickets non terminaux par agent et ignore les tickets clôturés.
    2. Le périmètre chief-service est forcé sur `actor.unity_id`, le paramètre `unit_id` de la
       requête ne permet pas de l'élargir (BR-SCOPE-001, même garde que list_requests).
    """
    unity_id = test_unity["id"]
    async with auth_client("user") as user_client:
        ticket_1 = await _create_as_user(user_client, unity_id, "1")
        ticket_2 = await _create_as_user(user_client, unity_id, "2")
        ticket_to_close = await _create_as_user(user_client, unity_id, "3")

    async with auth_client("admin") as client:
        await _qualify_and_assign(client, ticket_1, unity_id, assignee_id=101)
        await _qualify_and_assign(client, ticket_2, unity_id, assignee_id=102)
        await _qualify_and_assign(client, ticket_to_close, unity_id, assignee_id=101)

        resp = await client.post(f"/api/v1/requests/{ticket_to_close}/resolve", json={})
        assert resp.status_code == 200, resp.text
        resp = await client.post(f"/api/v1/requests/{ticket_to_close}/close", json={})
        assert resp.status_code == 200, resp.text

        resp = await client.get(f"/api/v1/requests/workload-by-unit?unit_id={unity_id}")
        assert resp.status_code == 200, resp.text
        rows = {row["assignee_id"]: row["active_count"] for row in resp.json()["data"]}

    # Agent 101 avait 2 tickets actifs, 1 a été clôturé entre-temps → charge active = 1.
    assert rows.get(101) == 1
    assert rows.get(102) == 1

    def _chief_dep():
        return SimpleNamespace(id=3, role="chief-service", unity_id=unity_id, direction_id=None)

    from httpx import ASGITransport, AsyncClient

    app.dependency_overrides[get_current_user] = _chief_dep
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            other_unit_id = unity_id + 999999
            resp = await client.get(f"/api/v1/requests/workload-by-unit?unit_id={other_unit_id}")
            assert resp.status_code == 200, resp.text
            scoped_rows = {row["assignee_id"]: row["active_count"] for row in resp.json()["data"]}
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    # Le serveur a ignoré other_unit_id et forcé le périmètre réel de l'acteur (unity_id).
    assert scoped_rows.get(101) == 1
    assert scoped_rows.get(102) == 1
