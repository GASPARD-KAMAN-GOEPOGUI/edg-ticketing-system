from __future__ import annotations

from types import SimpleNamespace

from httpx import ASGITransport, AsyncClient

from api.dependencies import get_current_user
from api.main import app
from tests.api.test_requests_baseline import _ensure_test_account

_REQUEST_PAYLOAD_BASE = {
    "description": "Description de test pour la directive (Lot 2.7).",
    "category": "panne",
    "priority": "medium",
    "is_external": False,
    "requester_name": "Citoyen Test",
    "requester_email": "citoyen@test.edg.gn",
}


async def _create_ticket(auth_client, unity_id: int, title_suffix: str) -> str:
    async with auth_client("user") as user_client:
        payload = {**_REQUEST_PAYLOAD_BASE, "title": f"Test directive {title_suffix}", "unity_id": unity_id}
        resp = await user_client.post("/api/v1/requests/", json=payload)
        assert resp.status_code == 201, resp.text
        return str(resp.json()["data"]["id"])


async def _assign_ticket(auth_client, request_id: str, unity_id: int, assignee_id: int) -> None:
    async with auth_client("admin") as admin_client:
        resp = await admin_client.post(
            f"/api/v1/requests/{request_id}/qualify",
            json={"category": "panne", "priority": "medium", "unit_id": unity_id, "assignee_id": assignee_id},
        )
        assert resp.status_code == 200, resp.text


async def _post_comment_as(role_dep, request_id: str, body: dict):
    app.dependency_overrides[get_current_user] = role_dep
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return await client.post(f"/api/v1/requests/{request_id}/comments", json=body)
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_chief_service_can_send_directive_to_assigned_agent(auth_client, unity_id):
    request_id = await _create_ticket(auth_client, unity_id, "chief-sends")
    await _assign_ticket(auth_client, request_id, unity_id, assignee_id=801)

    def _chief_dep():
        return SimpleNamespace(id=810, role="chief-service", unity_id=unity_id, direction_id=None, name="Chef Test")

    resp = await _post_comment_as(
        _chief_dep, request_id, {"body": "Merci de traiter en priorité.", "is_directive": True},
    )
    assert resp.status_code == 201, resp.text
    data = resp.json()["data"]
    assert data["infos"]["is_directive"] is True
    assert data["infos"]["target_user_id"] == "801"

    # Notification nominative recue par l'agent assigne (BR-NOTIF-001 : acteur precis).
    def _agent_dep():
        return SimpleNamespace(id=801, role="agent-support", unity_id=unity_id, direction_id=None)

    app.dependency_overrides[get_current_user] = _agent_dep
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            notif_resp = await client.get("/api/v1/notifications/by-recipient/801")
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert notif_resp.status_code == 200, notif_resp.text
    items = notif_resp.json()["data"]["items"]
    assert any("Directive" in item["title"] for item in items)


async def test_chief_departement_can_also_send_directive(auth_client, unity_id):
    """Le meme mecanisme couvre chief-departement (ChiefInbox est un composant partage)."""
    request_id = await _create_ticket(auth_client, unity_id, "department-sends")
    await _assign_ticket(auth_client, request_id, unity_id, assignee_id=802)

    def _chief_dep():
        return SimpleNamespace(id=811, role="chief-departement", unity_id=unity_id, direction_id=None, name="Chef Dept Test")

    resp = await _post_comment_as(
        _chief_dep, request_id, {"body": "Priorite haute sur ce dossier.", "is_directive": True},
    )
    assert resp.status_code == 201, resp.text


async def test_agent_support_cannot_send_directive(auth_client, unity_id):
    request_id = await _create_ticket(auth_client, unity_id, "agent-blocked")
    await _assign_ticket(auth_client, request_id, unity_id, assignee_id=803)

    def _agent_dep():
        return SimpleNamespace(id=803, role="agent-support", unity_id=unity_id, direction_id=None)

    resp = await _post_comment_as(
        _agent_dep, request_id, {"body": "Je me note ceci.", "is_directive": True},
    )
    assert resp.status_code == 403, resp.text


async def test_directive_requires_an_assignee(auth_client, unity_id):
    """Un ticket pas encore affecte n'a personne a cibler — la directive est refusee."""
    request_id = await _create_ticket(auth_client, unity_id, "no-assignee")

    def _chief_dep():
        return SimpleNamespace(id=812, role="chief-service", unity_id=unity_id, direction_id=None, name="Chef Test")

    resp = await _post_comment_as(
        _chief_dep, request_id, {"body": "Directive sans cible.", "is_directive": True},
    )
    assert resp.status_code == 422, resp.text


async def test_regular_comment_unaffected_by_directive_flag(auth_client, unity_id):
    """Regression : un commentaire normal (is_directive omis) continue de fonctionner
    pour un intervenant reel du ticket (BR-MESSAGING-PARTICIPANTS-001)."""
    await _ensure_test_account(813, unity_id=unity_id, role="chief-service")
    request_id = await _create_ticket(auth_client, unity_id, "regular-comment")
    await _assign_ticket(auth_client, request_id, unity_id, assignee_id=813)

    def _chief_dep():
        return SimpleNamespace(id=813, role="chief-service", unity_id=unity_id, direction_id=None, name="Chef Test")

    resp = await _post_comment_as(
        _chief_dep, request_id, {"body": "Commentaire normal.", "is_public": False, "peer_id": "813"},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["data"]["infos"].get("is_directive") is not True


# ── C-05.1 — reply_to_id (fil de discussion) ─────────────────────────────────

def _agent_dep_factory(agent_id: int, unity_id: int):
    def _dep():
        return SimpleNamespace(
            id=agent_id, role="agent-support", unity_id=unity_id, direction_id=None, name="Agent Test",
        )
    return _dep


async def test_reply_to_existing_comment_round_trips(auth_client, unity_id):
    await _ensure_test_account(820, unity_id=unity_id, role="agent-support")
    request_id = await _create_ticket(auth_client, unity_id, "reply-roundtrip")
    await _assign_ticket(auth_client, request_id, unity_id, assignee_id=820)
    agent_dep = _agent_dep_factory(820, unity_id)

    first = await _post_comment_as(
        agent_dep, request_id, {"body": "Premier message.", "is_public": False, "peer_id": "820"},
    )
    assert first.status_code == 201, first.text
    first_id = first.json()["data"]["id"]

    reply = await _post_comment_as(
        agent_dep, request_id,
        {"body": "Reponse ciblee.", "is_public": False, "reply_to_id": str(first_id), "peer_id": "820"},
    )
    assert reply.status_code == 201, reply.text
    assert reply.json()["data"]["infos"]["reply_to_id"] == str(first_id)


async def test_reply_to_comment_from_different_request_rejected(auth_client, unity_id):
    await _ensure_test_account(821, unity_id=unity_id, role="agent-support")
    request_a = await _create_ticket(auth_client, unity_id, "reply-cross-a")
    request_b = await _create_ticket(auth_client, unity_id, "reply-cross-b")
    # Intervenant reel des DEUX tickets — le test verifie le rejet du croisement
    # de reply_to_id entre demandes, pas la restriction de participation.
    await _assign_ticket(auth_client, request_a, unity_id, assignee_id=821)
    await _assign_ticket(auth_client, request_b, unity_id, assignee_id=821)
    agent_dep = _agent_dep_factory(821, unity_id)

    comment_a = await _post_comment_as(
        agent_dep, request_a, {"body": "Message sur A.", "is_public": False, "peer_id": "821"},
    )
    assert comment_a.status_code == 201, comment_a.text
    comment_a_id = comment_a.json()["data"]["id"]

    resp = await _post_comment_as(
        agent_dep, request_b,
        {"body": "Reponse invalide.", "is_public": False, "reply_to_id": str(comment_a_id), "peer_id": "821"},
    )
    assert resp.status_code == 422, resp.text


async def test_reply_to_nonexistent_comment_rejected(auth_client, unity_id):
    await _ensure_test_account(822, unity_id=unity_id, role="agent-support")
    request_id = await _create_ticket(auth_client, unity_id, "reply-missing")
    await _assign_ticket(auth_client, request_id, unity_id, assignee_id=822)
    agent_dep = _agent_dep_factory(822, unity_id)

    resp = await _post_comment_as(
        agent_dep, request_id,
        {"body": "Reponse a du vide.", "is_public": False, "reply_to_id": "999999999", "peer_id": "822"},
    )
    assert resp.status_code == 422, resp.text


async def test_reply_to_non_comment_event_rejected(auth_client, unity_id):
    """Un id de workflow_detail existant mais dont l'event_type n'est pas 'comment_added'
    (ex. l'evenement de creation du ticket) doit etre refuse comme cible de reponse."""
    await _ensure_test_account(823, unity_id=unity_id, role="agent-support")
    request_id = await _create_ticket(auth_client, unity_id, "reply-non-comment")
    await _assign_ticket(auth_client, request_id, unity_id, assignee_id=823)
    agent_dep = _agent_dep_factory(823, unity_id)

    async with auth_client("admin") as admin_client:
        detail_resp = await admin_client.get(f"/api/v1/requests/{request_id}")
    assert detail_resp.status_code == 200, detail_resp.text
    timelines = detail_resp.json()["data"]["timelines"]
    non_comment_event = next(t for t in timelines if t["event_type"] != "comment_added")

    resp = await _post_comment_as(
        agent_dep,
        request_id,
        {
            "body": "Reponse invalide.", "is_public": False,
            "reply_to_id": str(non_comment_event["id"]), "peer_id": "823",
        },
    )
    assert resp.status_code == 422, resp.text
