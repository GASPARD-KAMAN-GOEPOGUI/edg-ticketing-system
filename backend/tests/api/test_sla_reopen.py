"""
BR-SLA-REOPEN-001 — Gestion du SLA lors d'une réouverture.

Couvre : le premier cycle SLA (créé -> résolu) est gelé définitivement dans
l'événement `treatment_completed` correspondant et n'est jamais recalculé ;
chaque réouverture ouvre un nouveau cycle SLA indépendant, mesuré depuis la
date de réouverture ; les compteurs "live" (`sla_breached`/`sla_elapsed`)
repartent de zéro à la réouverture ; plusieurs réouvertures successives sont
mesurées avec des cycles distincts sans perte des données historiques.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from api.dependencies import get_current_user
from api.main import app
from api.models.ModelRequest import Request as RequestModel
from api.models.ModelWorkflowDetail import WorkflowDetail
from tests.conftest import _TestSession
from tests.api.test_requests_baseline import _ensure_test_account

# EscaladeService.mark_sla_breached() utilise `UPDATE request r JOIN request_status
# rs ON ... LEFT JOIN (...) ...` (syntaxe MySQL multi-table UPDATE...JOIN) — non
# supportee par SQLite (moteur de cette suite de tests, cf. conftest.py). Deja vrai
# avant BR-SLA-REOPEN-001 (aucun test existant n'appelait mark_sla_breached()) ;
# la correction de l'ancre temporelle (COALESCE sur la derniere reouverture) reste
# donc verifiee par relecture de code uniquement dans cette suite, testable en
# environnement MySQL reel.
_SCHEDULER_SKIP_REASON = (
    "EscaladeService.mark_sla_breached() utilise une syntaxe UPDATE...JOIN "
    "MySQL non supportee par SQLite (moteur de test) — pre-existant, jamais "
    "couvert par un test avant BR-SLA-REOPEN-001, hors perimetre a corriger ici."
)

_REQUEST_PAYLOAD_BASE = {
    "description": "Description de test pour la gestion du SLA en reouverture (BR-SLA-REOPEN-001).",
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
        payload = {**_REQUEST_PAYLOAD_BASE, "title": f"Test sla-reopen {title_suffix}", "unity_id": unity_id}
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


async def _detail(auth_client, request_id: str) -> dict:
    async with auth_client("admin") as admin_client:
        resp = await admin_client.get(f"/api/v1/requests/{request_id}")
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


def _now() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


async def _set_request_fields(request_id: str, **fields) -> None:
    async with _TestSession() as session:
        obj = (
            await session.execute(select(RequestModel).where(RequestModel.id == int(request_id)))
        ).scalar_one()
        for key, value in fields.items():
            setattr(obj, key, value)
        await session.commit()


async def _backdate_last_event(request_id: str, event_type: str, delta: timedelta) -> None:
    """Recule artificiellement created_at du dernier evenement `event_type` de la
    demande, pour simuler un ecart temporel reel sans attendre en test (le calcul
    des cycles SLA se base uniquement sur les horodatages workflow_detail)."""
    from api.models.ModelWorkflow import Workflow

    async with _TestSession() as session:
        row = (
            await session.execute(
                select(WorkflowDetail)
                .join(Workflow, Workflow.id == WorkflowDetail.workflow_id)
                .where(Workflow.request_id == int(request_id), WorkflowDetail.event_type == event_type)
                .order_by(WorkflowDetail.created_at.desc())
                .limit(1)
            )
        ).scalar_one()
        row.created_at = _now() - delta
        await session.commit()


async def _reopen_cycle(auth_client, request_id: str, unity_id: int, *, chief_id: int, reason: str, delta: timedelta) -> None:
    """Demande + approuve une reouverture, puis recule artificiellement l'horodatage
    de l'evenement `reopened` pour simuler le temps ecoule reel du cycle suivant."""
    async with auth_client("user") as user_client:
        resp = await user_client.post(
            f"/api/v1/requests/{request_id}/request-reopen", json={"reason": reason},
        )
        assert resp.status_code == 200, resp.text
    approve_resp = await _call_as(
        _dep(chief_id, "chief-service", unity_id), "POST", f"/api/v1/requests/{request_id}/reopen",
    )
    assert approve_resp.status_code == 200, approve_resp.text
    await _backdate_last_event(request_id, "reopened", delta)


async def test_first_sla_cycle_frozen_and_never_recalculated(auth_client, unity_id):
    """Cycle 1 clos (2h, cible 3h -> respecte) : reste inchange apres 2 reouvertures
    successives, meme si la cible SLA live change entre-temps."""
    await _ensure_test_account(901, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(902, unity_id=unity_id, role="chief-service")
    await _ensure_test_account(903, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(904, unity_id=unity_id, role="agent-support")

    request_id = await _create_ticket(auth_client, unity_id, "cycle1-frozen")
    await _set_request_fields(request_id, sla_hours=3, created_at=_now() - timedelta(hours=2))
    await _assign_via_admin(auth_client, request_id, unity_id, assignee_id=901)

    resolve1 = await _call_as(
        _dep(901, "agent-support", unity_id), "POST", f"/api/v1/requests/{request_id}/resolve",
        _FULL_RESOLVE_BODY,
    )
    assert resolve1.status_code == 200, resolve1.text

    detail = await _detail(auth_client, request_id)
    cycles = detail["sla_cycles"]
    assert len(cycles) == 1
    assert cycles[0]["cycle_number"] == 1
    assert cycles[0]["closed"] is True
    assert cycles[0]["sla_hours"] == 3
    assert cycles[0]["elapsed_hours"] == 2.0
    assert cycles[0]["breached"] is False
    frozen_cycle1 = cycles[0]

    # ── Cycle 2 : reouverture (1h30), cible SLA toujours 3h -> respecte ──────────
    # Note technique : les deltas de reouvertures successives doivent decroitre
    # (ou rester egaux) d'une reouverture a l'autre. Chaque reouverture est
    # "reculee" artificiellement dans le temps depuis SA propre date d'appel
    # (reelle, en quelques millisecondes) pour simuler un ecart reel sans
    # attendre en test ; avec des appels reels rapprochés de quelques
    # millisecondes, un delta plus grand pour une reouverture plus tardive
    # inverserait leur ordre chronologique reel (la reouverture n°2
    # semblerait avoir eu lieu avant la n°1). Ceci est un artefact de cette
    # technique de test, sans equivalent possible en usage reel ou les
    # reouvertures successives sont toujours strictement ordonnees dans le temps.
    await _reopen_cycle(
        auth_client, request_id, unity_id,
        chief_id=902, reason="Le probleme persiste.", delta=timedelta(minutes=90),
    )
    detail_after_reopen = await _detail(auth_client, request_id)
    assert detail_after_reopen["request_status"] == "reopened"
    assert detail_after_reopen["assignee_id"] is None
    assert detail_after_reopen["sla_breached"] is False
    assert detail_after_reopen["sla_elapsed"] == 0

    await _assign_via_admin(auth_client, request_id, unity_id, assignee_id=903)
    resolve2 = await _call_as(
        _dep(903, "agent-support", unity_id), "POST", f"/api/v1/requests/{request_id}/resolve",
        _FULL_RESOLVE_BODY,
    )
    assert resolve2.status_code == 200, resolve2.text

    detail2 = await _detail(auth_client, request_id)
    cycles2 = detail2["sla_cycles"]
    assert len(cycles2) == 2
    assert cycles2[0] == frozen_cycle1, "le premier cycle SLA ne doit jamais etre recalcule"
    assert cycles2[1]["cycle_number"] == 2
    assert cycles2[1]["elapsed_hours"] == 1.5
    assert cycles2[1]["breached"] is False
    assert cycles2[1]["reopen_reason"] == "Le probleme persiste."
    frozen_cycle2 = cycles2[1]

    # ── Cycle 3 : 2e reouverture (1h10), cible SLA abaissee a 1h -> depasse ──────
    await _reopen_cycle(
        auth_client, request_id, unity_id,
        chief_id=902, reason="Nouvelle panne apres la 2e resolution.",
        delta=timedelta(hours=1, minutes=10),
    )
    # Simule un changement de priorite/cible SLA survenu pendant ce 3e cycle —
    # ne doit affecter que ce cycle, jamais les deux precedents deja geles.
    await _set_request_fields(request_id, sla_hours=1)
    await _assign_via_admin(auth_client, request_id, unity_id, assignee_id=904)
    resolve3 = await _call_as(
        _dep(904, "agent-support", unity_id), "POST", f"/api/v1/requests/{request_id}/resolve",
        _FULL_RESOLVE_BODY,
    )
    assert resolve3.status_code == 200, resolve3.text

    detail3 = await _detail(auth_client, request_id)
    cycles3 = detail3["sla_cycles"]
    assert len(cycles3) == 3
    assert cycles3[0] == frozen_cycle1, "le premier cycle SLA reste intact apres une 2e reouverture"
    assert cycles3[1] == frozen_cycle2, "le 2e cycle deja clos reste intact, avec sa propre cible SLA (jamais celle du 3e)"
    assert cycles3[2]["cycle_number"] == 3
    assert cycles3[2]["sla_hours"] == 1
    assert round(cycles3[2]["elapsed_hours"], 2) == 1.17
    assert cycles3[2]["breached"] is True
    assert cycles3[2]["reopen_reason"] == "Nouvelle panne apres la 2e resolution."

    assert detail3["reopen_count"] == 2


async def test_reopen_resets_live_sla_counters(auth_client, unity_id):
    await _ensure_test_account(905, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(906, unity_id=unity_id, role="chief-service")
    request_id = await _create_ticket(auth_client, unity_id, "live-reset")
    await _set_request_fields(request_id, sla_hours=1, sla_breached=True, sla_elapsed=99)
    await _assign_via_admin(auth_client, request_id, unity_id, assignee_id=905)

    resolve_resp = await _call_as(
        _dep(905, "agent-support", unity_id), "POST", f"/api/v1/requests/{request_id}/resolve",
        _FULL_RESOLVE_BODY,
    )
    assert resolve_resp.status_code == 200, resolve_resp.text

    # Remet volontairement les compteurs live a un etat "en retard" avant la
    # reouverture, pour verifier que l'approbation les reinitialise bien.
    await _set_request_fields(request_id, sla_breached=True, sla_elapsed=50)
    async with auth_client("user") as user_client:
        req_resp = await user_client.post(
            f"/api/v1/requests/{request_id}/request-reopen", json={"reason": "Test reset live."},
        )
        assert req_resp.status_code == 200, req_resp.text
    approve_resp = await _call_as(
        _dep(906, "chief-service", unity_id), "POST", f"/api/v1/requests/{request_id}/reopen",
    )
    assert approve_resp.status_code == 200, approve_resp.text
    data = approve_resp.json()["data"]
    assert data["sla_breached"] is False
    assert data["sla_elapsed"] == 0


@pytest.mark.skip(reason=_SCHEDULER_SKIP_REASON)
async def test_scheduler_anchors_live_sla_on_last_reopening(auth_client, unity_id):
    """BR-SLA-REOPEN-001 — mark_sla_breached() doit ancrer sla_elapsed sur la
    derniere reouverture, jamais sur la date de creation d'origine.
    Scenario documente pour execution en environnement MySQL reel (voir
    _SCHEDULER_SKIP_REASON) : sans le correctif d'ancre, un ticket cree il y a
    10h (sla_hours=5, donc deja hors delai avant reouverture) mais reouvert il y
    a seulement 1h serait a tort marque sla_breached=True apres mark_sla_breached()."""
    from api.services.ServiceEscalade import EscaladeService

    await _ensure_test_account(907, unity_id=unity_id, role="agent-support")
    await _ensure_test_account(908, unity_id=unity_id, role="chief-service")
    request_id = await _create_ticket(auth_client, unity_id, "scheduler-anchor")
    await _set_request_fields(request_id, sla_hours=5, created_at=_now() - timedelta(hours=10))
    await _assign_via_admin(auth_client, request_id, unity_id, assignee_id=907)

    resolve_resp = await _call_as(
        _dep(907, "agent-support", unity_id), "POST", f"/api/v1/requests/{request_id}/resolve",
        _FULL_RESOLVE_BODY,
    )
    assert resolve_resp.status_code == 200, resolve_resp.text

    await _reopen_cycle(
        auth_client, request_id, unity_id,
        chief_id=908, reason="Reouverture recente.", delta=timedelta(hours=1),
    )

    async with _TestSession() as session:
        svc = EscaladeService(session)
        await svc.mark_sla_breached()
        await session.commit()

    detail = await _detail(auth_client, request_id)
    # Ancre sur la reouverture (~1h) : sous la cible de 5h -> pas en retard.
    # Si l'ancre etait restee `created_at` (~10h avant), le ticket serait a tort
    # marque sla_breached=True malgre une reouverture toute recente.
    assert detail["sla_breached"] is False
    assert detail["sla_elapsed"] <= 2
