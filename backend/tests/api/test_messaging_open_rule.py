"""
BR-MESSAGING-OPEN-001 — le demandeur ne peut écrire à l'intervenant actuel
qu'après que celui-ci a explicitement ouvert la conversation (≥1 commentaire
public de sa part, dans SA conversation). Généralise BR-MESSAGING-PAIR-001
(peer_id == assignee_id courant, déjà couvert par test_directive_comment.py)
sans jamais coder de logique spécifique à un intervenant précis — le scénario
ci-dessous enchaîne volontairement A -> B -> C -> D pour le prouver.
"""
from __future__ import annotations

from types import SimpleNamespace

from httpx import ASGITransport, AsyncClient

from api.dependencies import get_current_user
from api.main import app
from tests.conftest import MOCK_ACCOUNTS
from tests.api.test_requests_baseline import _ensure_test_account

_REQUEST_PAYLOAD_BASE = {
    "description": "Description de test pour BR-MESSAGING-OPEN-001.",
    "category": "panne",
    "priority": "medium",
    "is_external": False,
    "requester_name": "Citoyen Test",
    "requester_email": "citoyen@test.edg.gn",
}


async def _create_ticket(auth_client, unity_id: int, title_suffix: str) -> str:
    async with auth_client("user") as user_client:
        payload = {**_REQUEST_PAYLOAD_BASE, "title": f"Test open-rule {title_suffix}", "unity_id": unity_id}
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


def _dep(account_id: int, role: str, unity_id: int | None = None):
    def _factory():
        return SimpleNamespace(
            id=account_id, role=role, unity_id=unity_id, direction_id=None,
            name=f"Test Account {account_id}",
        )
    return _factory


async def _call_as(role_dep, method: str, url: str, json: dict | None = None):
    app.dependency_overrides[get_current_user] = role_dep
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return await client.request(method, url, json=json)
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def _requester_write(request_id: str, unity_id: int, peer_id: int):
    return await _call_as(
        _dep(MOCK_ACCOUNTS["user"].id, "user", unity_id),
        "POST", f"/api/v1/requests/{request_id}/comments",
        {"body": "Message du demandeur.", "is_public": False, "peer_id": str(peer_id)},
    )


async def _assignee_open(request_id: str, unity_id: int, assignee_id: int):
    return await _call_as(
        _dep(assignee_id, "agent-support", unity_id),
        "POST", f"/api/v1/requests/{request_id}/comments",
        {"body": "Bonjour, pouvez-vous préciser le problème ?", "is_public": True, "peer_id": str(assignee_id)},
    )


# TEST 1 — aucun assignee -> A ne peut pas écrire.
async def test_requester_cannot_write_without_assignee(auth_client, unity_id):
    request_id = await _create_ticket(auth_client, unity_id, "no-assignee")
    resp = await _requester_write(request_id, unity_id, peer_id=999)
    assert resp.status_code == 422, resp.text
    assert "intervenant assigné" in resp.json()["message"]


# TEST 2 / 11 — B responsable mais n'a rien écrit -> A ne peut pas écrire.
async def test_requester_cannot_write_before_assignee_opens_discussion(auth_client, unity_id):
    await _ensure_test_account(940, unity_id=unity_id, role="agent-support")
    request_id = await _create_ticket(auth_client, unity_id, "not-opened")
    await _assign_ticket(auth_client, request_id, unity_id, assignee_id=940)

    resp = await _requester_write(request_id, unity_id, peer_id=940)
    assert resp.status_code == 422, resp.text
    assert "n'a pas encore ouvert" in resp.json()["message"]


# Point 2/15 — l'intervenant actuel, lui, n'est jamais bloqué par ce verrou :
# il doit pouvoir écrire le tout premier message sans aucun historique préalable.
async def test_assignee_can_always_open_even_with_zero_history(auth_client, unity_id):
    await _ensure_test_account(941, unity_id=unity_id, role="agent-support")
    request_id = await _create_ticket(auth_client, unity_id, "assignee-opens-first")
    await _assign_ticket(auth_client, request_id, unity_id, assignee_id=941)

    resp = await _assignee_open(request_id, unity_id, assignee_id=941)
    assert resp.status_code == 201, resp.text


# TEST 3-9, 12, 13 — chaîne complète A -> B -> C -> D, générique (aucune logique
# spécifique à un intervenant précis : même séquence de vérifications répétée
# à chaque transmission, seul l'id change).
async def test_full_chain_open_write_transmit_repeats_generically(auth_client, unity_id):
    for account_id in (950, 951, 952):
        await _ensure_test_account(account_id, unity_id=unity_id, role="agent-support")
    request_id = await _create_ticket(auth_client, unity_id, "abcd-chain")

    handlers = [950, 951, 952]  # B, C, D
    previous_handlers: list[int] = []

    await _assign_ticket(auth_client, request_id, unity_id, assignee_id=handlers[0])

    for i, current in enumerate(handlers):
        # A ne peut pas encore écrire au responsable courant : rien d'ouvert.
        resp = await _requester_write(request_id, unity_id, peer_id=current)
        assert resp.status_code == 422, f"handler {current}: {resp.text}"

        # A ne peut pas non plus (re)cibler un ancien responsable, même avec
        # historique et discussion déjà ouverte auparavant (TEST 4/7/9/12).
        for old in previous_handlers:
            resp = await _requester_write(request_id, unity_id, peer_id=old)
            assert resp.status_code == 422, f"old handler {old} should stay unreachable: {resp.text}"

        # Le responsable courant ouvre la discussion.
        resp = await _assignee_open(request_id, unity_id, assignee_id=current)
        assert resp.status_code == 201, resp.text

        # A peut désormais lui répondre.
        resp = await _requester_write(request_id, unity_id, peer_id=current)
        assert resp.status_code == 201, f"handler {current}: {resp.text}"

        previous_handlers.append(current)

        # Transmission vers le suivant (sauf au dernier tour).
        if i < len(handlers) - 1:
            next_handler = handlers[i + 1]
            resp = await _call_as(
                _dep(current, "agent-support", unity_id),
                "POST", f"/api/v1/requests/{request_id}/transmit",
                {"to_user_id": str(next_handler), "work_done": "Diagnostic.", "reason": "Transfert de test."},
            )
            assert resp.status_code == 200, resp.text

    # TEST 13 — historique de TOUS les anciens responsables reste consultable
    # par A malgré les 2 transmissions.
    resp = await _call_as(
        _dep(MOCK_ACCOUNTS["user"].id, "user", unity_id),
        "GET", f"/api/v1/requests/{request_id}/comments",
    )
    assert resp.status_code == 200, resp.text
    visible_peer_ids = {str(c["infos"].get("peer_id")) for c in resp.json()["data"]}
    assert visible_peer_ids == {str(h) for h in handlers}


# Rule 24 — les directives (chef -> agent assigné) restent inchangées, pas
# concernées par BR-MESSAGING-OPEN-001.
async def test_directive_untouched_by_open_rule(auth_client, unity_id):
    await _ensure_test_account(960, unity_id=unity_id, role="agent-support")
    request_id = await _create_ticket(auth_client, unity_id, "directive-untouched")
    await _assign_ticket(auth_client, request_id, unity_id, assignee_id=960)

    resp = await _call_as(
        _dep(961, "chief-service", unity_id),
        "POST", f"/api/v1/requests/{request_id}/comments",
        {"body": "Traitez en priorité.", "is_directive": True},
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["data"]["infos"]["is_directive"] is True
