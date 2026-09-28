"""
BR-NOTIFICATION-WORKFLOW-001 — Alignement des notifications sur le workflow
métier réel des tickets.

Couvre les correctifs et ajouts de ce lot :
  - création : le demandeur est notifié (absent avant ce lot) ;
  - cohérence assign()/qualify_triage() : le nouvel intervenant est notifié
    quel que soit le chemin technique qui produit `assigned` ;
  - transmission : confirmation App-only à l'émetteur (send_email=False) ;
  - annulation : App-only pour demandeur ET intervenant (pas de bruit email) ;
  - commentaire du demandeur → notifie l'intervenant actuel, généralisé
    au-delà du seul statut `pending` ;
  - `NotificationEmitter.emit(send_email=False)` supprime bien l'envoi email.

N'exerce pas `warn_sla_approaching()` / `mark_sla_breached()` en intégration :
ces méthodes utilisent `TIMESTAMPDIFF` (syntaxe MySQL), non supporté par le
moteur SQLite de la suite de tests — limitation préexistante déjà documentée
pour `mark_sla_breached`/`run_auto_escalation` (KI-SQL-001, voir
`test_sla_reopen.py::test_scheduler_anchors_live_sla_on_last_reopening`, skip
documenté). Le reset du flag anti-répétition à la réouverture (pur Python,
sans SQL brut) est en revanche couvert ci-dessous.
"""
from __future__ import annotations

import asyncio

from sqlalchemy import select

from tests.conftest import MOCK_ACCOUNTS, _TestSession
from tests.api.test_requests_baseline import _ensure_test_account
from tests.api.test_transmit_treatment import (
    _REQUEST_PAYLOAD_BASE,
    _assign_via_admin,
    _call_as,
    _create_ticket,
    _dep,
    _notifications_for,
)


async def _flush_background_emails() -> None:
    """Attend la complétion des tâches d'envoi email fire-and-forget déjà
    planifiées (NotificationEmitter._send_email_fire_and_forget)."""
    from api.services.NotificationEmitter import _background_email_tasks

    if _background_email_tasks:
        await asyncio.gather(*_background_email_tasks, return_exceptions=True)


async def test_create_notifies_requester(auth_client, unity_id):
    request_id = await _create_ticket(auth_client, unity_id, "create-notifies")
    notifs = await _notifications_for(MOCK_ACCOUNTS["user"].id, request_id)
    assert any(n.title == "Ticket créé" for n in notifs)


async def test_qualify_triage_direct_assignment_notifies_new_assignee(auth_client, unity_id):
    await _ensure_test_account(830, unity_id=unity_id, role="chief-service")
    request_id = await _create_ticket(auth_client, unity_id, "qualify-direct")

    async with auth_client("admin") as admin_client:
        resp = await admin_client.post(
            f"/api/v1/requests/{request_id}/qualify",
            json={"category": "panne", "priority": "medium", "unit_id": unity_id, "assignee_id": 830},
        )
        assert resp.status_code == 200, resp.text

    # BR-NOTIFICATION-WORKFLOW-001 §4/§6/§7 — auparavant absent : le nouvel
    # intervenant routé directement depuis la File d'attente n'était jamais
    # notifié (seul assign() le faisait, pas qualify_triage()).
    assignee_notifs = await _notifications_for(830, request_id)
    assert any(n.title == "Ticket assigné" for n in assignee_notifs)

    # BR-TRAITEMENT-PROGRESSIF-001 (2026-09-27) : qualify_triage() avec
    # assignee_id direct ne démarre plus le traitement, il assigne. Le demandeur
    # est donc informé de l'assignation, pas d'un traitement en cours — qui ne
    # commencera qu'au geste explicite du traitant.
    requester_notifs = await _notifications_for(MOCK_ACCOUNTS["user"].id, request_id)
    titles = [n.title for n in requester_notifs]
    assert "Ticket pris en charge" in titles, titles


async def test_assign_notifies_assignee_and_requester_app_only(auth_client, unity_id, monkeypatch):
    await _ensure_test_account(831, unity_id=unity_id, role="chief-service")
    request_id = await _create_ticket(auth_client, unity_id, "assign-coherence")

    email_calls: list[dict] = []

    async def _fake_send(**kwargs):
        email_calls.append(kwargs)
        return True

    monkeypatch.setattr("api.core.mailer.send_notification_email", _fake_send)

    resp = await _call_as(
        _dep(6, "admin"), "POST", f"/api/v1/requests/{request_id}/assign?assignee_id=831",
    )
    assert resp.status_code == 200, resp.text
    await _flush_background_emails()

    assignee_notifs = await _notifications_for(831, request_id)
    assert any(n.title == "Ticket assigné" for n in assignee_notifs)

    requester_notifs = await _notifications_for(MOCK_ACCOUNTS["user"].id, request_id)
    assert any(n.title == "Ticket pris en charge" for n in requester_notifs)

    # send_email=False (requester) ne doit jamais atteindre le mailer ; l'email
    # de l'assigné (send_email=True, défaut) doit lui être tenté.
    assert any(call.get("title") == "Ticket assigné" for call in email_calls)
    assert not any(call.get("title") == "Ticket pris en charge" for call in email_calls)


async def test_transmit_confirms_emitter_app_only(auth_client, unity_id, monkeypatch):
    email_calls: list[dict] = []

    async def _fake_send(**kwargs):
        email_calls.append(kwargs)
        return True

    # Monkeypatché avant toute action métier : la qualification (assignation
    # initiale à 840) émet elle aussi un email réel désormais (cohérence
    # assign()/qualify_triage(), ce lot) — on l'intercepte comme le reste.
    monkeypatch.setattr("api.core.mailer.send_notification_email", _fake_send)

    await _ensure_test_account(840, unity_id=unity_id, role="chief-service")
    await _ensure_test_account(841, unity_id=unity_id, role="chief-service")
    request_id = await _create_ticket(auth_client, unity_id, "transmit-app-only")
    await _assign_via_admin(auth_client, request_id, unity_id, assignee_id=840)
    email_calls.clear()

    resp = await _call_as(
        _dep(840, "chief-service", unity_id), "POST", f"/api/v1/requests/{request_id}/transmit",
        {"to_user_id": "841", "work_done": "Diagnostic.", "reason": "Motif de test."},
    )
    assert resp.status_code == 200, resp.text
    await _flush_background_emails()

    # 840 a aussi reçu "Ticket assigné" lors de la qualification (attendu,
    # cohérence assign()/qualify_triage()) — on isole ici la confirmation de
    # transmission proprement dite.
    emitter_notifs = [n for n in await _notifications_for(840, request_id) if n.title == "Ticket transmis"]
    assert len(emitter_notifs) == 1

    new_handler_email_calls = [c for c in email_calls if c.get("to_email") and "compte.test.841" in c["to_email"]]
    emitter_email_calls = [c for c in email_calls if c.get("to_email") and "compte.test.840" in c["to_email"]]
    assert new_handler_email_calls, "le nouvel intervenant doit recevoir un email"
    assert not emitter_email_calls, "l'émetteur ne doit recevoir qu'une confirmation App-only"


async def test_cancel_emails_requester_but_stays_app_only_for_assignee(auth_client, unity_id, monkeypatch):
    # L'email de confirmation au demandeur suppose une ligne Account en base
    # (NotificationEmitter y va chercher l'adresse par recipient_id) — le
    # MockAccount d'injection de rôle n'y suffit pas.
    await _ensure_test_account(
        MOCK_ACCOUNTS["user"].id, unity_id=None, role="user",
        email=MOCK_ACCOUNTS["user"].email,
    )
    await _ensure_test_account(850, unity_id=unity_id, role="chief-service")
    request_id = await _create_ticket(auth_client, unity_id, "cancel-requester-email")
    await _assign_via_admin(auth_client, request_id, unity_id, assignee_id=850)

    email_calls: list[dict] = []

    async def _fake_send(**kwargs):
        email_calls.append(kwargs)
        return True

    monkeypatch.setattr("api.core.mailer.send_notification_email", _fake_send)

    async with auth_client("user") as user_client:
        resp = await user_client.post(
            f"/api/v1/requests/{request_id}/cancel?reason=Ne+concerne+plus+le+service."
        )
        assert resp.status_code == 200, resp.text
    await _flush_background_emails()

    requester_notifs = await _notifications_for(MOCK_ACCOUNTS["user"].id, request_id)
    assert any(n.title == "Ticket annulé" for n in requester_notifs)
    assignee_notifs = await _notifications_for(850, request_id)
    assert any(n.title == "Ticket annulé" for n in assignee_notifs)

    # Le demandeur qui annule reçoit désormais une confirmation par email ;
    # l'intervenant assigné, lui, reste en App-only (BR-NOTIFICATION-WORKFLOW-001 §20/§22).
    assert len(email_calls) == 1
    assert email_calls[0]["to_email"] == MOCK_ACCOUNTS["user"].email


async def test_send_email_false_suppresses_mailer_call(monkeypatch, unity_id):
    """Test unitaire ciblé du nouveau paramètre `send_email` de
    NotificationEmitter.emit — indépendant du workflow ticket."""
    await _ensure_test_account(870, unity_id=unity_id, role="chief-service", email="compte.test.870@test.edg.gn")

    email_calls: list[dict] = []

    async def _fake_send(**kwargs):
        email_calls.append(kwargs)
        return True

    monkeypatch.setattr("api.core.mailer.send_notification_email", _fake_send)

    from api.services.NotificationEmitter import emit as emit_notif

    async with _TestSession() as session:
        await emit_notif(
            session,
            recipient_id="870",
            title="Test App-only",
            body="Corps de test.",
            send_email=False,
        )
        await session.commit()
    await _flush_background_emails()

    assert not email_calls

    async with _TestSession() as session:
        await emit_notif(
            session,
            recipient_id="870",
            title="Test avec email",
            body="Corps de test.",
        )
        await session.commit()
    await _flush_background_emails()

    assert any(c.get("title") == "Test avec email" for c in email_calls)


# ── File d'attente : les chefs de service doivent être prévenus ───────────────
# L'événement SSE `request.created` ne fait que rafraîchir les écrans déjà
# ouverts. Un chef de service déconnecté au moment de la création n'apprenait
# donc jamais qu'une demande attendait sa qualification.

async def test_create_notifies_chief_service_holding_the_queue(auth_client, unity_id):
    await _ensure_test_account(841, unity_id=unity_id, role="chief-service")
    request_id = await _create_ticket(auth_client, unity_id, "queue-notify-chief")

    notifs = await _notifications_for(841, request_id)
    assert any(n.title == "Nouvelle demande à qualifier" for n in notifs)


async def test_create_does_not_notify_admin(auth_client, unity_id):
    """L'admin voit la File d'attente mais ne qualifie pas : le notifier à chaque
    création ne produirait que du bruit (décision produit 2026-09-26)."""
    await _ensure_test_account(842, unity_id=None, role="admin")
    request_id = await _create_ticket(auth_client, unity_id, "queue-notify-admin")

    notifs = await _notifications_for(842, request_id)
    assert not any(n.title == "Nouvelle demande à qualifier" for n in notifs)


async def test_create_does_not_notify_chief_service_requester_twice(auth_client, unity_id):
    """Un chef de service qui crée sa propre demande reçoit « Ticket créé » ; il
    ne doit pas recevoir en plus l'alerte de file d'attente pour son ticket."""
    requester_id = MOCK_ACCOUNTS["user"].id
    await _ensure_test_account(requester_id, unity_id=unity_id, role="chief-service")
    request_id = await _create_ticket(auth_client, unity_id, "queue-notify-self")

    notifs = await _notifications_for(requester_id, request_id)
    assert any(n.title == "Ticket créé" for n in notifs)
    assert not any(n.title == "Nouvelle demande à qualifier" for n in notifs)


async def test_create_emails_chief_service_of_the_queue(auth_client, monkeypatch, unity_id):
    """Le fan-out email de `emit_bulk` est enveloppé dans un try/except qui
    journalise sans lever : une panne y serait invisible. Ce test verrouille le
    canal email choisi pour l'alerte de file d'attente (in-app + email)."""
    await _ensure_test_account(
        843, unity_id=unity_id, role="chief-service", email="compte.test.843@test.edg.gn"
    )

    email_calls: list[dict] = []

    async def _fake_send(**kwargs):
        email_calls.append(kwargs)
        return True

    monkeypatch.setattr("api.core.mailer.send_notification_email", _fake_send)

    await _create_ticket(auth_client, unity_id, "queue-notify-email")
    await _flush_background_emails()

    queue_emails = [c for c in email_calls if c.get("title") == "Nouvelle demande à qualifier"]
    assert queue_emails, f"aucun email de file d'attente envoyé — reçus : {[c.get('title') for c in email_calls]}"
    assert any(c["to_email"] == "compte.test.843@test.edg.gn" for c in queue_emails)


async def test_create_does_not_notify_technicien_nor_chef_division(auth_client, unity_id):
    """Garde-fou contre l'expansion de groupe de `_role_filter` : elle élargit
    `chief-service` à {chief-service, technicien, chef-division-support}. Utiliser
    `list_by_role()` ici notifierait des rôles qui n'ont même pas accès à la File
    d'attente. Seul `list_by_role_strict()` est correct."""
    await _ensure_test_account(844, unity_id=unity_id, role="technicien")
    await _ensure_test_account(845, unity_id=unity_id, role="chef-division-support")
    request_id = await _create_ticket(auth_client, unity_id, "queue-strict-role")

    for account_id in (844, 845):
        notifs = await _notifications_for(account_id, request_id)
        titles = [n.title for n in notifs]
        assert "Nouvelle demande à qualifier" not in titles, (
            f"le compte {account_id} ne tient pas la File d'attente — reçu : {titles}"
        )
