"""
BR-TRACE-001 — Traçabilité complète des interventions.

Couvre : une intervention est un conteneur logique explicite (intervention_id/
intervention_order/cycle_number enregistrés au moment de l'action, jamais
recalculés) regroupant le travail complet d'un intervenant (commentaires,
pièces jointes, travail effectué) jusqu'à sa transmission ou sa résolution ;
l'ordre repart à 1 à chaque nouveau cycle SLA ; rien n'est jamais perdu,
modifié ou fusionné même après plusieurs réouvertures et plusieurs passages
du même intervenant.
"""
from __future__ import annotations

from types import SimpleNamespace

from httpx import ASGITransport, AsyncClient

from api.dependencies import get_current_user
from api.main import app
from tests.api.test_requests_baseline import _ensure_test_account
from tests.conftest import _TestSession

_REQUEST_PAYLOAD_BASE = {
    "description": "Description de test pour la tracabilite des interventions (BR-TRACE-001).",
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
        payload = {**_REQUEST_PAYLOAD_BASE, "title": f"Test trace {title_suffix}", "unity_id": unity_id}
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


async def _ensure_test_unity(codename: str, label: str) -> int:
    from sqlalchemy import select

    from api.models.ModelUnity import Unity

    async with _TestSession() as session:
        existing = (await session.execute(select(Unity).where(Unity.codename == codename))).scalar_one_or_none()
        if existing is not None:
            return int(existing.id)
        unity = Unity(codename=codename, label=label, aleas=codename, status=True)
        session.add(unity)
        await session.commit()
        await session.refresh(unity)
        return int(unity.id)


async def _call_as(role_dep, method: str, url: str, json: dict | None = None):
    app.dependency_overrides[get_current_user] = role_dep
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            return await client.request(method, url, json=json)
    finally:
        app.dependency_overrides.pop(get_current_user, None)


def _dep(account_id: int, role: str, unity_id: int | None = None):
    def _factory():
        return SimpleNamespace(
            id=account_id, role=role, unity_id=unity_id, direction_id=None,
            name=f"Test{account_id}", firstname="Compte",
        )
    return _factory


async def _detail(auth_client, request_id: str) -> dict:
    async with auth_client("admin") as admin_client:
        resp = await admin_client.get(f"/api/v1/requests/{request_id}")
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


async def _add_comment_as(request_id: str, account_id: int, role: str, unity_id: int, body: str):
    # account_id est systématiquement l'assigné courant du ticket au moment de
    # l'appel (cf. sites d'appel) -> BR-MESSAGING-PAIR-001 : peer_id est
    # toujours le côté intervenant de la conversation, donc account_id lui-même
    # ici (pas le demandeur), que le message vienne de lui ou du demandeur.
    resp = await _call_as(
        _dep(account_id, role, unity_id), "POST", f"/api/v1/requests/{request_id}/comments",
        {"body": body, "is_public": False, "peer_id": str(account_id)},
    )
    assert resp.status_code in (200, 201), resp.text
    return resp


async def test_intervention_container_groups_comment_and_transmission(auth_client, unity_id):
    """Intervention 1 (agent A) : commentaire + transmission -> conteneur unique,
    intervention_order=1, cycle_number=1. Intervention 2 (agent B) : resolution."""
    await _ensure_test_account(1001, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(1002, unity_id=unity_id, role="agent-support")

    request_id = await _create_ticket(auth_client, unity_id, "container")
    await _assign_via_admin(auth_client, request_id, unity_id, assignee_id=1001)

    await _add_comment_as(request_id, 1001, "agent-support", unity_id, "Diagnostic matériel.")

    transmit_resp = await _call_as(
        _dep(1001, "agent-support", unity_id), "POST", f"/api/v1/requests/{request_id}/transmit",
        {"to_user_id": "1002", "work_done": "Diagnostic effectue.", "reason": "Remplacement necessaire."},
    )
    assert transmit_resp.status_code == 200, transmit_resp.text

    resolve_resp = await _call_as(
        _dep(1002, "agent-support", unity_id), "POST", f"/api/v1/requests/{request_id}/resolve",
        _FULL_RESOLVE_BODY,
    )
    assert resolve_resp.status_code == 200, resolve_resp.text

    detail = await _detail(auth_client, request_id)
    interventions = detail["interventions"]
    assert len(interventions) == 2

    iv1, iv2 = interventions
    assert iv1["cycle_number"] == 1
    assert iv1["intervention_order"] == 1
    assert str(iv1["actor_id"]) == "1001"
    assert iv1["comment_count"] == 1
    assert iv1["decision"] == "transmission"
    assert iv1["destination_name"] is not None
    assert str(iv1["destination_id"]) == "1002"
    assert iv1["work_done"] == "Diagnostic effectue."
    assert iv1["transmission_reason"] == "Remplacement necessaire."

    assert iv2["cycle_number"] == 1
    assert iv2["intervention_order"] == 2
    assert str(iv2["actor_id"]) == "1002"
    assert iv2["decision"] == "resolution"
    assert iv2["sla_breached"] is False


async def test_intervention_order_resets_per_cycle_and_history_never_lost(auth_client, unity_id):
    """3 cycles (2 reouvertures) : l'ordre des interventions repart a 1 a chaque
    cycle, et les interventions des cycles precedents restent intactes."""
    await _ensure_test_account(1003, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(1004, unity_id=unity_id, role="chief-service")
    await _ensure_test_account(1005, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(1006, unity_id=unity_id, role="agent-support")

    request_id = await _create_ticket(auth_client, unity_id, "multi-cycle")
    await _assign_via_admin(auth_client, request_id, unity_id, assignee_id=1003)

    resolve1 = await _call_as(
        _dep(1003, "agent-support", unity_id), "POST", f"/api/v1/requests/{request_id}/resolve",
        _FULL_RESOLVE_BODY,
    )
    assert resolve1.status_code == 200, resolve1.text

    detail1 = await _detail(auth_client, request_id)
    assert len(detail1["interventions"]) == 1
    cycle1_intervention_id = detail1["interventions"][0]["intervention_id"]
    assert detail1["interventions"][0]["intervention_order"] == 1
    assert detail1["interventions"][0]["cycle_number"] == 1

    # ── Reouverture (immediate, BR-REOPEN-QUEUE-001) -> cycle 2 ─────────────────
    async with auth_client("user") as user_client:
        req_resp = await user_client.post(
            f"/api/v1/requests/{request_id}/reopen", json={"reason": "Le probleme persiste."},
        )
        assert req_resp.status_code == 200, req_resp.text

    await _assign_via_admin(auth_client, request_id, unity_id, assignee_id=1005)
    resolve2 = await _call_as(
        _dep(1005, "agent-support", unity_id), "POST", f"/api/v1/requests/{request_id}/resolve",
        _FULL_RESOLVE_BODY,
    )
    assert resolve2.status_code == 200, resolve2.text

    detail2 = await _detail(auth_client, request_id)
    interventions2 = detail2["interventions"]
    assert len(interventions2) == 2
    # L'intervention du cycle 1 reste identique — rien n'a ete modifie/fusionne.
    iv1_after = next(iv for iv in interventions2 if iv["intervention_id"] == cycle1_intervention_id)
    assert iv1_after == detail1["interventions"][0]
    iv_cycle2 = next(iv for iv in interventions2 if iv["intervention_id"] != cycle1_intervention_id)
    assert iv_cycle2["cycle_number"] == 2
    assert iv_cycle2["intervention_order"] == 1, "l'ordre doit repartir a 1 pour le nouveau cycle"

    # ── 2e reouverture (immediate) -> cycle 3, meme intervenant (1003) qu'au cycle 1 ─
    async with auth_client("user") as user_client:
        req_resp2 = await user_client.post(
            f"/api/v1/requests/{request_id}/reopen", json={"reason": "Nouvelle panne."},
        )
        assert req_resp2.status_code == 200, req_resp2.text

    # Agent 1003 reprend le ticket — un meme intervenant peut revenir plusieurs
    # fois, chaque passage restant une intervention distincte.
    await _assign_via_admin(auth_client, request_id, unity_id, assignee_id=1003)
    transmit3 = await _call_as(
        _dep(1003, "agent-support", unity_id), "POST", f"/api/v1/requests/{request_id}/transmit",
        {"to_user_id": "1006", "work_done": "Reinstallation en cours.", "reason": "Besoin d'un second avis."},
    )
    assert transmit3.status_code == 200, transmit3.text
    resolve3 = await _call_as(
        _dep(1006, "agent-support", unity_id), "POST", f"/api/v1/requests/{request_id}/resolve",
        _FULL_RESOLVE_BODY,
    )
    assert resolve3.status_code == 200, resolve3.text

    detail3 = await _detail(auth_client, request_id)
    interventions3 = detail3["interventions"]
    assert len(interventions3) == 4  # cycle1:1, cycle2:1, cycle3:2 (transmit + resolve)

    # Les 2 premieres interventions (cycles 1 et 2) restent parfaitement intactes.
    assert interventions3[0] == detail1["interventions"][0]
    assert interventions3[1] == iv_cycle2

    cycle3_ivs = [iv for iv in interventions3 if iv["cycle_number"] == 3]
    assert len(cycle3_ivs) == 2
    assert [iv["intervention_order"] for iv in cycle3_ivs] == [1, 2], "ordre reparti a 1 pour le 3e cycle"
    assert str(cycle3_ivs[0]["actor_id"]) == "1003"
    assert str(cycle3_ivs[1]["actor_id"]) == "1006"
    # Agent 1003 est intervenu 2 fois au total (cycle 1 et cycle 3) — 2
    # interventions distinctes, pas fusionnees, chacune avec son propre id.
    agent_1003_interventions = [iv for iv in interventions3 if str(iv["actor_id"]) == "1003"]
    assert len(agent_1003_interventions) == 2
    assert agent_1003_interventions[0]["intervention_id"] != agent_1003_interventions[1]["intervention_id"]

    assert detail3["reopen_count"] == 2


async def test_actor_identity_snapshot_is_frozen(auth_client, unity_id):
    """L'identite (matricule/service) figee dans l'intervention ne doit pas
    changer meme si le compte de l'intervenant est modifie ensuite."""
    from sqlalchemy import select
    from tests.conftest import _TestSession
    from api.models.ModelAccount import Account

    await _ensure_test_account(1007, unity_id=unity_id, role="agent-support")

    async with _TestSession() as session:
        acc = (await session.execute(select(Account).where(Account.id == 1007))).scalar_one()
        acc.matricule = "MAT-ORIGINAL"
        await session.commit()

    request_id = await _create_ticket(auth_client, unity_id, "identity-frozen")
    await _assign_via_admin(auth_client, request_id, unity_id, assignee_id=1007)
    resolve_resp = await _call_as(
        _dep(1007, "agent-support", unity_id), "POST", f"/api/v1/requests/{request_id}/resolve",
        _FULL_RESOLVE_BODY,
    )
    assert resolve_resp.status_code == 200, resolve_resp.text

    # Le matricule change APRES l'intervention.
    async with _TestSession() as session:
        acc = (await session.execute(select(Account).where(Account.id == 1007))).scalar_one()
        acc.matricule = "MAT-CHANGED"
        await session.commit()

    detail = await _detail(auth_client, request_id)
    assert detail["interventions"][0]["actor_matricule"] == "MAT-ORIGINAL"


async def test_non_current_handler_comment_not_attached_to_intervention(auth_client, unity_id):
    """Un commentaire du demandeur (jamais intervenant courant) reste visible
    dans l'historique mais n'est rattache a aucun conteneur d'intervention."""
    await _ensure_test_account(1008, unity_id=unity_id, role="agent-support")
    request_id = await _create_ticket(auth_client, unity_id, "requester-comment")
    await _assign_via_admin(auth_client, request_id, unity_id, assignee_id=1008)

    # BR-MESSAGING-OPEN-001 — l'intervenant actuel doit d'abord ouvrir la
    # conversation avant que le demandeur puisse y écrire.
    app.dependency_overrides[get_current_user] = _dep(1008, "agent-support", unity_id)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            opened = await client.post(
                f"/api/v1/requests/{request_id}/comments",
                json={"body": "Bonjour, une précision ?", "is_public": True, "peer_id": "1008"},
            )
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert opened.status_code == 201, opened.text

    async with auth_client("user") as user_client:
        resp = await user_client.post(
            f"/api/v1/requests/{request_id}/comments",
            json={"body": "Toujours en panne ?", "is_public": True, "peer_id": "1008"},
        )
        assert resp.status_code in (200, 201), resp.text

    async with auth_client("admin") as admin_client:
        timeline_resp = await admin_client.get(f"/api/v1/requests/{request_id}/timeline")
    assert timeline_resp.status_code == 200
    comment_event = next(
        e for e in timeline_resp.json()["data"]
        if e["event_type"] == "comment_added" and e["comment"] == "Toujours en panne ?"
    )
    assert comment_event["infos"].get("intervention_id") is None


async def test_attachment_attached_to_current_intervention(auth_client, unity_id):
    """Une piece jointe ajoutee par l'intervenant courant est rattachee a son
    intervention ouverte, au meme titre qu'un commentaire."""
    await _ensure_test_account(1009, unity_id=unity_id, role="agent-support")
    request_id = await _create_ticket(auth_client, unity_id, "attachment-linked")
    await _assign_via_admin(auth_client, request_id, unity_id, assignee_id=1009)

    app.dependency_overrides[get_current_user] = _dep(1009, "agent-support", unity_id)
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            upload_resp = await client.post(
                f"/api/v1/requests/{request_id}/attachments",
                files={"file": ("photo_01.jpg", b"\xff\xd8\xff\xe0fake-jpeg-bytes", "image/jpeg")},
            )
    finally:
        app.dependency_overrides.pop(get_current_user, None)
    assert upload_resp.status_code in (200, 201), upload_resp.text

    detail = await _detail(auth_client, request_id)
    interventions = detail["interventions"]
    assert len(interventions) == 1
    assert interventions[0]["attachment_count"] == 1


async def test_intervention_report_aggregates_by_agent_service(auth_client, unity_id):
    """BR-TRACE-001 — /reports/interventions agrege transmissions/resolutions et
    temps par agent/service sans affecter les rapports existants."""
    await _ensure_test_account(1010, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(1011, unity_id=unity_id, role="agent-support")

    request_id = await _create_ticket(auth_client, unity_id, "report-aggregate")
    await _assign_via_admin(auth_client, request_id, unity_id, assignee_id=1010)
    transmit_resp = await _call_as(
        _dep(1010, "agent-support", unity_id), "POST", f"/api/v1/requests/{request_id}/transmit",
        {"to_user_id": "1011", "work_done": "Diagnostic.", "reason": "Deuxieme avis."},
    )
    assert transmit_resp.status_code == 200, transmit_resp.text
    resolve_resp = await _call_as(
        _dep(1011, "agent-support", unity_id), "POST", f"/api/v1/requests/{request_id}/resolve",
        _FULL_RESOLVE_BODY,
    )
    assert resolve_resp.status_code == 200, resolve_resp.text

    async with auth_client("admin") as admin_client:
        report_resp = await admin_client.get("/api/v1/reports/interventions")
    assert report_resp.status_code == 200, report_resp.text
    data = report_resp.json()["data"]
    assert data["report_type"] == "intervention_stats"
    assert data["transmissions"] >= 1
    assert data["resolutions"] >= 1
    agent_ids = {row["label"] for row in data["by_agent"]}
    assert agent_ids  # au moins un intervenant agrege


async def test_intervention_report_chief_service_is_scoped_to_own_service(auth_client, unity_id):
    """Sécurité — un chef de service ne voit pas les interventions d'un autre service
    en appelant directement /reports/interventions."""
    other_unity_id = await _ensure_test_unity("TST-SCOPE-OTHER", "Service Test Hors Scope")
    await _ensure_test_account(1020, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(1021, unity_id=other_unity_id, role="agent-support")

    own_request_id = await _create_ticket(auth_client, unity_id, "scope-own-service")
    await _assign_via_admin(auth_client, own_request_id, unity_id, assignee_id=1020)
    own_resolve = await _call_as(
        _dep(1020, "agent-support", unity_id), "POST", f"/api/v1/requests/{own_request_id}/resolve",
        _FULL_RESOLVE_BODY,
    )
    assert own_resolve.status_code == 200, own_resolve.text

    other_request_id = await _create_ticket(auth_client, other_unity_id, "scope-other-service")
    await _assign_via_admin(auth_client, other_request_id, other_unity_id, assignee_id=1021)
    other_resolve = await _call_as(
        _dep(1021, "agent-support", other_unity_id), "POST", f"/api/v1/requests/{other_request_id}/resolve",
        _FULL_RESOLVE_BODY,
    )
    assert other_resolve.status_code == 200, other_resolve.text

    report_resp = await _call_as(
        _dep(9001, "chief-service", unity_id), "GET", "/api/v1/reports/interventions"
    )
    assert report_resp.status_code == 200, report_resp.text
    labels = {row["label"] for row in report_resp.json()["data"]["by_agent"]}
    assert "Test Compte Test 1020" in labels
    assert "Test Compte Test 1021" not in labels


async def test_reopened_ticket_history_is_never_mutated_by_later_actions(auth_client, unity_id):
    """Principe 2 (BR-TRACE-001) : une intervention figee reste bit-a-bit
    identique apres des actions ulterieures sur d'AUTRES tickets."""
    await _ensure_test_account(1012, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(1013, unity_id=unity_id, role="agent-support")

    request_id = await _create_ticket(auth_client, unity_id, "immutable-history")
    await _assign_via_admin(auth_client, request_id, unity_id, assignee_id=1012)
    resolve_resp = await _call_as(
        _dep(1012, "agent-support", unity_id), "POST", f"/api/v1/requests/{request_id}/resolve",
        _FULL_RESOLVE_BODY,
    )
    assert resolve_resp.status_code == 200, resolve_resp.text
    detail_before = await _detail(auth_client, request_id)

    # Actions non liees sur un AUTRE ticket, du meme intervenant.
    other_request_id = await _create_ticket(auth_client, unity_id, "unrelated")
    await _assign_via_admin(auth_client, other_request_id, unity_id, assignee_id=1012)
    other_resolve = await _call_as(
        _dep(1012, "agent-support", unity_id), "POST", f"/api/v1/requests/{other_request_id}/resolve",
        _FULL_RESOLVE_BODY,
    )
    assert other_resolve.status_code == 200, other_resolve.text

    detail_after = await _detail(auth_client, request_id)
    assert detail_after["interventions"] == detail_before["interventions"]
    assert len(detail_after["timelines"]) == len(detail_before["timelines"])
