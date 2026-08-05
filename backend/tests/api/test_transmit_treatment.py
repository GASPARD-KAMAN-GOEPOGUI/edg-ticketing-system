"""
BR-TRANSMIT-001 — Workflow collaboratif dynamique post-file d'attente.

Couvre : transmission libre du traitement (assignee_id devient un intervenant
choisi librement, statut préservé), terminaison du traitement (resolve étendu,
champs obligatoires universels, plus de restriction de rôle sur l'intervenant
actuel), cycles d'intervention (workflow_detail append-only), notifications et
contrôle de concurrence.
"""
from __future__ import annotations

from types import SimpleNamespace

from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from api.core.exceptions import ConflictException
from api.dependencies import get_current_user
from api.main import app
from tests.conftest import _TestSession
from tests.api.test_requests_baseline import _ensure_test_account

_REQUEST_PAYLOAD_BASE = {
    "description": "Description de test pour le workflow collaboratif dynamique (BR-TRANSMIT-001).",
    "category": "panne",
    "priority": "medium",
    "is_external": False,
    "requester_name": "Citoyen Test",
    "requester_email": "citoyen@test.edg.gn",
}

_FULL_RESOLVE_BODY = {
    "summary": "Résumé final de test",
    "solution": "Solution appliquée de test",
    "work_done": "Travail réalisé de test",
}


async def _create_ticket(auth_client, unity_id: int, title_suffix: str) -> str:
    async with auth_client("user") as user_client:
        payload = {**_REQUEST_PAYLOAD_BASE, "title": f"Test transmit {title_suffix}", "unity_id": unity_id}
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


async def _timeline(auth_client, request_id: str) -> list[dict]:
    async with auth_client("admin") as admin_client:
        resp = await admin_client.get(f"/api/v1/requests/{request_id}/timeline")
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


async def _notifications_for(recipient_id: int, request_id: str) -> list:
    from api.models.ModelNotification import Notification

    async with _TestSession() as session:
        rows = (
            await session.execute(
                select(Notification).where(
                    Notification.recipient_id == recipient_id,
                    Notification.request_id == int(request_id),
                )
            )
        ).scalars().all()
        return list(rows)


# ── 1-2. Transmission simple : assignee_id change, historique alimenté ────────

async def test_agent_transmits_to_another_agent(auth_client, unity_id):
    await _ensure_test_account(801, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(802, unity_id=unity_id, role="agent-support")
    request_id = await _create_ticket(auth_client, unity_id, "agent-to-agent")
    await _assign_via_admin(auth_client, request_id, unity_id, assignee_id=801)

    resp = await _call_as(
        _dep(801, "agent-support", unity_id), "POST", f"/api/v1/requests/{request_id}/transmit",
        {"to_user_id": "802", "work_done": "Diagnostic effectué.", "reason": "Intervention réseau nécessaire."},
    )
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert str(data["assignee_id"]) == "802"
    # Le statut actif n'est jamais forcé/rétrogradé par la transmission.
    assert data["request_status"] == "assigned"

    events = await _timeline(auth_client, request_id)
    transmitted = [e for e in events if e["event_type"] == "treatment_transmitted"]
    assert len(transmitted) == 1
    infos = transmitted[0]["infos"]
    assert infos["previous_assignee_id"] == 801
    assert str(infos["new_assignee_id"]) == "802"
    assert infos["work_done"] == "Diagnostic effectué."
    assert infos["reason"] == "Intervention réseau nécessaire."
    assert infos["cycle_number"] == 1


# ── 3-4. Historique conservé, un même acteur peut avoir plusieurs cycles ──────

async def test_previous_handler_stays_in_history_and_can_return_later(auth_client, unity_id):
    await _ensure_test_account(803, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(804, unity_id=unity_id, role="agent-support")
    request_id = await _create_ticket(auth_client, unity_id, "multi-cycle")
    await _assign_via_admin(auth_client, request_id, unity_id, assignee_id=803)

    resp1 = await _call_as(
        _dep(803, "agent-support", unity_id), "POST", f"/api/v1/requests/{request_id}/transmit",
        {"to_user_id": "804", "work_done": "Diagnostic initial.", "reason": "Besoin d'un second avis."},
    )
    assert resp1.status_code == 200, resp1.text

    resp2 = await _call_as(
        _dep(804, "agent-support", unity_id), "POST", f"/api/v1/requests/{request_id}/transmit",
        {"to_user_id": "803", "work_done": "Analyse complémentaire.", "reason": "Retour à l'agent initial pour finalisation."},
    )
    assert resp2.status_code == 200, resp2.text
    assert str(resp2.json()["data"]["assignee_id"]) == "803"

    events = await _timeline(auth_client, request_id)
    transmitted = [e for e in events if e["event_type"] == "treatment_transmitted"]
    assert len(transmitted) == 2
    # Rien n'est écrasé : les deux passages restent visibles séparément, dans l'ordre.
    assert transmitted[0]["infos"]["previous_assignee_id"] == 803
    assert transmitted[1]["infos"]["previous_assignee_id"] == 804
    assert str(transmitted[1]["infos"]["new_assignee_id"]) == "803"
    # Numéro de cycle strictement croissant.
    assert [e["infos"]["cycle_number"] for e in transmitted] == [1, 2]


# ── 5. Un acteur non courant ne peut pas transmettre ──────────────────────────

async def test_non_current_handler_cannot_transmit(auth_client, unity_id):
    await _ensure_test_account(805, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(806, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(807, unity_id=unity_id, role="agent-support")
    request_id = await _create_ticket(auth_client, unity_id, "not-current-handler")
    await _assign_via_admin(auth_client, request_id, unity_id, assignee_id=805)

    resp = await _call_as(
        _dep(806, "agent-support", unity_id), "POST", f"/api/v1/requests/{request_id}/transmit",
        {"to_user_id": "807", "work_done": "Tentative.", "reason": "Tentative non autorisée."},
    )
    assert resp.status_code == 403, resp.text


# ── 6-7. Champs obligatoires (motif / travail effectué) ───────────────────────

async def test_transmit_without_reason_rejected(auth_client, unity_id):
    await _ensure_test_account(808, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(809, unity_id=unity_id, role="agent-support")
    request_id = await _create_ticket(auth_client, unity_id, "no-reason")
    await _assign_via_admin(auth_client, request_id, unity_id, assignee_id=808)

    resp = await _call_as(
        _dep(808, "agent-support", unity_id), "POST", f"/api/v1/requests/{request_id}/transmit",
        {"to_user_id": "809", "work_done": "Diagnostic.", "reason": "   "},
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["error_code"] == "MISSING_REQUIRED_FIELD"


async def test_transmit_without_work_done_rejected(auth_client, unity_id):
    await _ensure_test_account(810, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(811, unity_id=unity_id, role="agent-support")
    request_id = await _create_ticket(auth_client, unity_id, "no-work-done")
    await _assign_via_admin(auth_client, request_id, unity_id, assignee_id=810)

    resp = await _call_as(
        _dep(810, "agent-support", unity_id), "POST", f"/api/v1/requests/{request_id}/transmit",
        {"to_user_id": "811", "work_done": "", "reason": "Motif renseigné."},
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["error_code"] == "MISSING_REQUIRED_FIELD"


# ── 8-9. Cible inactive / rôle non autorisé ────────────────────────────────────

async def test_transmit_to_inactive_target_rejected(auth_client, unity_id):
    await _ensure_test_account(812, unity_id=unity_id, role="agent-support")
    from api.models.ModelAccount import Account

    await _ensure_test_account(813, unity_id=unity_id, role="agent-support")
    async with _TestSession() as session:
        acc = await session.get(Account, 813)
        acc.status = False
        await session.commit()

    request_id = await _create_ticket(auth_client, unity_id, "inactive-target")
    await _assign_via_admin(auth_client, request_id, unity_id, assignee_id=812)

    resp = await _call_as(
        _dep(812, "agent-support", unity_id), "POST", f"/api/v1/requests/{request_id}/transmit",
        {"to_user_id": "813", "work_done": "Diagnostic.", "reason": "Transmission vers cible inactive."},
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["error_code"] == "INVALID_FIELD_VALUE"


async def test_transmit_to_unauthorized_role_rejected(auth_client, unity_id):
    await _ensure_test_account(814, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(815, unity_id=unity_id, role="user")
    request_id = await _create_ticket(auth_client, unity_id, "unauthorized-role-target")
    await _assign_via_admin(auth_client, request_id, unity_id, assignee_id=814)

    resp = await _call_as(
        _dep(814, "agent-support", unity_id), "POST", f"/api/v1/requests/{request_id}/transmit",
        {"to_user_id": "815", "work_done": "Diagnostic.", "reason": "Transmission vers un rôle non traitant."},
    )
    assert resp.status_code == 400, resp.text
    assert resp.json()["error_code"] == "INVALID_FIELD_VALUE"


# ── 10. Transmission inter-direction autorisée (annuaire libre) ───────────────

async def test_transmit_across_directions_allowed(auth_client, unity_id):
    from api.models.ModelUnity import Unity

    async with _TestSession() as session:
        other = Unity(label="Autre Direction Test", codename="TST-OTHER-DIR", status=True)
        session.add(other)
        await session.commit()
        await session.refresh(other)
        other_direction_id = other.id

    await _ensure_test_account(816, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(817, unity_id=other_direction_id, role="director")
    request_id = await _create_ticket(auth_client, unity_id, "cross-direction")
    await _assign_via_admin(auth_client, request_id, unity_id, assignee_id=816)

    resp = await _call_as(
        _dep(816, "agent-support", unity_id), "POST", f"/api/v1/requests/{request_id}/transmit",
        {"to_user_id": "817", "work_done": "Diagnostic.", "reason": "Besoin d'arbitrage d'une autre direction."},
    )
    assert resp.status_code == 200, resp.text
    assert str(resp.json()["data"]["assignee_id"]) == "817"


# ── 11-12. Terminer le traitement : chief-departement et director sans restriction ──

async def test_chief_departement_can_terminate_treatment_as_current_handler(auth_client, unity_id):
    await _ensure_test_account(818, unity_id=unity_id, role="chief-departement")
    request_id = await _create_ticket(auth_client, unity_id, "dept-can-terminate")
    await _assign_via_admin(auth_client, request_id, unity_id, assignee_id=818)

    resp = await _call_as(
        _dep(818, "chief-departement", unity_id), "POST", f"/api/v1/requests/{request_id}/resolve",
        _FULL_RESOLVE_BODY,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["request_status"] == "resolved"


async def test_director_can_terminate_without_prior_escalation(auth_client, unity_id):
    await _ensure_test_account(819, unity_id=unity_id, role="director")
    request_id = await _create_ticket(auth_client, unity_id, "director-no-escalation")
    await _assign_via_admin(auth_client, request_id, unity_id, assignee_id=819)

    async with auth_client("admin") as admin_client:
        detail = await admin_client.get(f"/api/v1/requests/{request_id}")
    assert detail.json()["data"]["request_status"] == "assigned"

    resp = await _call_as(
        _dep(819, "director", unity_id), "POST", f"/api/v1/requests/{request_id}/resolve",
        _FULL_RESOLVE_BODY,
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["request_status"] == "resolved"


# ── 13-17. Notifications, audit, cycle sur transmission + terminaison ─────────

async def test_transmit_then_terminate_notifies_and_tracks_cycles(auth_client, unity_id):
    await _ensure_test_account(820, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(821, unity_id=unity_id, role="chief-service")
    request_id = await _create_ticket(auth_client, unity_id, "notify-and-cycle")
    await _assign_via_admin(auth_client, request_id, unity_id, assignee_id=820)

    transmit_resp = await _call_as(
        _dep(820, "agent-support", unity_id), "POST", f"/api/v1/requests/{request_id}/transmit",
        {"to_user_id": "821", "work_done": "Diagnostic agent.", "reason": "Validation chef nécessaire."},
    )
    assert transmit_resp.status_code == 200, transmit_resp.text

    # Le nouvel intervenant reçoit une notification de transmission.
    new_handler_notifs = await _notifications_for(821, request_id)
    assert len(new_handler_notifs) == 1
    assert new_handler_notifs[0].title == "Traitement transmis"

    resolve_resp = await _call_as(
        _dep(821, "chief-service", unity_id), "POST", f"/api/v1/requests/{request_id}/resolve",
        _FULL_RESOLVE_BODY,
    )
    assert resolve_resp.status_code == 200, resolve_resp.text

    # Le demandeur (compte "user" du fixture auth_client) reçoit une notification de résolution.
    from tests.conftest import MOCK_ACCOUNTS

    requester_notifs = await _notifications_for(MOCK_ACCOUNTS["user"].id, request_id)
    assert any(n.title == "Demande résolue" for n in requester_notifs)

    events = await _timeline(auth_client, request_id)
    completed = [e for e in events if e["event_type"] == "treatment_completed"]
    assert len(completed) == 1
    completed_infos = completed[0]["infos"]
    assert completed_infos["summary"] == _FULL_RESOLVE_BODY["summary"]
    assert completed_infos["solution"] == _FULL_RESOLVE_BODY["solution"]
    assert completed_infos["cycle_number"] == 2  # 1 transmission + 1 terminaison


# ── 18. Conflit de transmission simultanée refusé ─────────────────────────────

async def test_concurrent_transmission_conflict_is_rejected(auth_client, unity_id):
    """Simule une transmission concurrente : entre la lecture initiale et l'écriture,
    un autre acteur a déjà changé l'assignee_id (ici simulé directement en base). L'écriture
    atomique conditionnelle (`_atomic_conditional_update`) doit refuser d'écraser la nouvelle
    affectation plutôt que de l'ignorer silencieusement."""
    from api.services.ServiceRequest import RequestService

    from api.models.ModelRequest import Request as RequestModel

    await _ensure_test_account(822, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(823, unity_id=unity_id, role="agent-support")
    request_id = await _create_ticket(auth_client, unity_id, "concurrent-conflict")
    await _assign_via_admin(auth_client, request_id, unity_id, assignee_id=822)

    # Un autre acteur (ex. une seconde transmission concurrente déjà validée) a
    # réassigné le ticket entre-temps — simulé directement en base pour isoler le
    # test de la logique métier de transition (pas l'objet du test).
    async with _TestSession() as session:
        req = await session.get(RequestModel, int(request_id))
        req.assignee_id = 823
        await session.commit()

    async with _TestSession() as session:
        svc = RequestService(session)
        # Snapshot volontairement obsolète : l'acteur croit encore que 822 est assignee.
        stale_current = SimpleNamespace(id=int(request_id), assignee_id=822)
        try:
            await svc._atomic_conditional_update(
                stale_current,
                values={"in_triage": False},
                require_current_assignee=True,
            )
            raised = False
        except ConflictException as exc:
            raised = True
            assert exc.error_code == "TICKET_STATE_CONFLICT"
        assert raised, "un conflit d'assignation obsolète doit lever ConflictException"
