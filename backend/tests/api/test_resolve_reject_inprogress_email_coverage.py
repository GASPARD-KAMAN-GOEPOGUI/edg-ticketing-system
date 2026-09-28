"""
Couverture email manquante identifiée en session (2026-08-27) : `resolve()`,
`reject()` et le passage à `in_progress` via `qualify_triage()` avaient un
comportement email vérifié seulement par lecture de code (default `send_email`
non surchargé), jamais par un test mockant `mailer.send_notification_email`
comme le fait déjà `test_notification_workflow.py` pour create/assign/cancel.
"""
from __future__ import annotations

from tests.conftest import MOCK_ACCOUNTS
from tests.api.test_notification_workflow import _flush_background_emails
from tests.api.test_requests_baseline import _ensure_test_account
from tests.api.test_transmit_treatment import (
    _FULL_RESOLVE_BODY,
    _assign_via_admin,
    _call_as,
    _create_ticket,
    _dep,
    _notifications_for,
)


async def test_qualify_triage_direct_assignment_emails_requester(auth_client, unity_id, monkeypatch):
    await _ensure_test_account(
        MOCK_ACCOUNTS["user"].id, unity_id=None, role="user",
        email=MOCK_ACCOUNTS["user"].email,
    )
    await _ensure_test_account(910, unity_id=unity_id, role="chief-service")
    request_id = await _create_ticket(auth_client, unity_id, "inprogress-email")

    email_calls: list[dict] = []

    async def _fake_send(**kwargs):
        email_calls.append(kwargs)
        return True

    monkeypatch.setattr("api.core.mailer.send_notification_email", _fake_send)

    async with auth_client("admin") as admin_client:
        resp = await admin_client.post(
            f"/api/v1/requests/{request_id}/qualify",
            json={"category": "panne", "priority": "medium", "unit_id": unity_id, "assignee_id": 910},
        )
        assert resp.status_code == 200, resp.text
    await _flush_background_emails()

    requester_email_calls = [c for c in email_calls if c.get("to_email") == MOCK_ACCOUNTS["user"].email]
    assert requester_email_calls, "le demandeur doit recevoir un email dès le passage en in_progress"
    assert any(c.get("title") == "Ticket en cours de traitement" for c in requester_email_calls)


async def test_resolve_emails_requester(auth_client, unity_id, monkeypatch):
    await _ensure_test_account(
        MOCK_ACCOUNTS["user"].id, unity_id=None, role="user",
        email=MOCK_ACCOUNTS["user"].email,
    )
    await _ensure_test_account(920, unity_id=unity_id, role="chief-service")
    request_id = await _create_ticket(auth_client, unity_id, "resolve-email")
    await _assign_via_admin(auth_client, request_id, unity_id, assignee_id=920)

    email_calls: list[dict] = []

    async def _fake_send(**kwargs):
        email_calls.append(kwargs)
        return True

    monkeypatch.setattr("api.core.mailer.send_notification_email", _fake_send)

    resp = await _call_as(
        _dep(920, "chief-service", unity_id), "POST", f"/api/v1/requests/{request_id}/resolve",
        _FULL_RESOLVE_BODY,
    )
    assert resp.status_code == 200, resp.text
    await _flush_background_emails()

    requester_notifs = await _notifications_for(MOCK_ACCOUNTS["user"].id, request_id)
    assert any(n.title == "Ticket résolu" for n in requester_notifs)

    requester_email_calls = [c for c in email_calls if c.get("to_email") == MOCK_ACCOUNTS["user"].email]
    assert requester_email_calls, "le demandeur doit recevoir un email à la résolution"
    assert any(c.get("title") == "Ticket résolu" for c in requester_email_calls)


async def test_self_take_from_queue_emails_the_taking_agent(auth_client, unity_id, monkeypatch):
    """BR-QUEUE-AUTO-START-001 — "Prendre le ticket" : l'agent se qualifie lui-même
    comme assignee_id depuis la file d'attente. Vérifie que ce chemin (distinct
    d'une assignation par un tiers) envoie bien un email à l'agent qui prend."""
    await _ensure_test_account(950, unity_id=unity_id, role="chief-service")
    request_id = await _create_ticket(auth_client, unity_id, "self-take-email")

    email_calls: list[dict] = []

    async def _fake_send(**kwargs):
        email_calls.append(kwargs)
        return True

    monkeypatch.setattr("api.core.mailer.send_notification_email", _fake_send)

    resp = await _call_as(
        _dep(950, "chief-service", unity_id), "POST", f"/api/v1/requests/{request_id}/qualify",
        {"category": "panne", "priority": "medium", "unit_id": unity_id, "assignee_id": "950"},
    )
    assert resp.status_code == 200, resp.text
    await _flush_background_emails()

    taker_notifs = await _notifications_for(950, request_id)
    assert any(n.title == "Ticket assigné" for n in taker_notifs)

    taker_email_calls = [c for c in email_calls if c.get("title") == "Ticket assigné"]
    assert taker_email_calls, "l'agent qui prend son propre ticket depuis la file doit recevoir un email"


async def test_assign_route_emails_the_assignee(auth_client, unity_id, monkeypatch):
    """Chemin dédié /assign (assignation par un tiers, distinct de qualify_triage)."""
    await _ensure_test_account(960, unity_id=unity_id, role="chief-service")
    request_id = await _create_ticket(auth_client, unity_id, "assign-route-email")

    email_calls: list[dict] = []

    async def _fake_send(**kwargs):
        email_calls.append(kwargs)
        return True

    monkeypatch.setattr("api.core.mailer.send_notification_email", _fake_send)

    resp = await _call_as(
        _dep(6, "admin"), "POST", f"/api/v1/requests/{request_id}/assign?assignee_id=960",
    )
    assert resp.status_code == 200, resp.text
    await _flush_background_emails()

    assignee_email_calls = [c for c in email_calls if c.get("title") == "Ticket assigné"]
    assert assignee_email_calls, "l'agent assigné via /assign doit recevoir un email"


async def test_transmit_emails_the_new_handler(auth_client, unity_id, monkeypatch):
    """Chemin transmission (/transmit) — le nouvel intervenant reçoit un email."""
    await _ensure_test_account(970, unity_id=unity_id, role="chief-service")
    await _ensure_test_account(971, unity_id=unity_id, role="chief-service")
    request_id = await _create_ticket(auth_client, unity_id, "transmit-email")
    await _assign_via_admin(auth_client, request_id, unity_id, assignee_id=970)

    email_calls: list[dict] = []

    async def _fake_send(**kwargs):
        email_calls.append(kwargs)
        return True

    monkeypatch.setattr("api.core.mailer.send_notification_email", _fake_send)

    resp = await _call_as(
        _dep(970, "chief-service", unity_id), "POST", f"/api/v1/requests/{request_id}/transmit",
        {"to_user_id": "971", "work_done": "Diagnostic.", "reason": "Motif de test."},
    )
    assert resp.status_code == 200, resp.text
    await _flush_background_emails()

    new_handler_email_calls = [c for c in email_calls if c.get("title") == "Ticket transmis"]
    assert new_handler_email_calls, "le nouvel intervenant transmis doit recevoir un email"


async def test_reject_emails_requester(auth_client, unity_id, monkeypatch):
    await _ensure_test_account(
        MOCK_ACCOUNTS["user"].id, unity_id=None, role="user",
        email=MOCK_ACCOUNTS["user"].email,
    )
    request_id = await _create_ticket(auth_client, unity_id, "reject-email")

    email_calls: list[dict] = []

    async def _fake_send(**kwargs):
        email_calls.append(kwargs)
        return True

    monkeypatch.setattr("api.core.mailer.send_notification_email", _fake_send)

    resp = await _call_as(
        _dep(6, "admin"), "POST", f"/api/v1/requests/{request_id}/reject",
        {"reason": "Hors périmètre du support."},
    )
    assert resp.status_code == 200, resp.text
    await _flush_background_emails()

    requester_notifs = await _notifications_for(MOCK_ACCOUNTS["user"].id, request_id)
    assert any(n.title == "Ticket rejeté" for n in requester_notifs)

    requester_email_calls = [c for c in email_calls if c.get("to_email") == MOCK_ACCOUNTS["user"].email]
    assert requester_email_calls, "le demandeur doit recevoir un email au rejet"
    assert any(c.get("title") == "Ticket rejeté" for c in requester_email_calls)
