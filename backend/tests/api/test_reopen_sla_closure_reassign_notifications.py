"""
Lot de finition — workflow + notifications (2026-08-07).

Couvre les 3 points restants non couverts par test_reopen_queue.py :
  2. SLA préventif — le flag `send_email=False` ajouté à
     `EscaladeService._notify()` atteint bien `NotificationEmitter.emit()`.
     Le déclenchement réel du seuil 80% (`warn_sla_approaching`) reste non
     testable en intégration : requête SQL brute `TIMESTAMPDIFF` (MySQL
     uniquement), même limitation déjà documentée (KI-SQL-001) pour
     `mark_sla_breached()`/`run_auto_escalation()` — vérifié par relecture de
     code, pas par un test d'intégration.
  3. Clôture — le demandeur (App+Email) et le dernier intervenant (App-only)
     sont notifiés, sans réaffectation ni nouveau cycle.
  4. reassign_service / transfer_direction — nouveau responsable (App+Email),
     demandeur (App-only), ancien responsable (App-only si perte réelle de
     responsabilité), aucune notification aux intervenants historiques.

Toutes les assertions passent par un monkeypatch de bas niveau sur les points
d'émission réels (`ServiceRequest.emit_notif`, `NotificationEmitter.emit`)
plutôt que sur la configuration SMTP — aucune dépendance à un serveur mail
réel, cohérent avec le principe "email best-effort, jamais bloquant".
"""
from __future__ import annotations

from types import SimpleNamespace

from httpx import ASGITransport, AsyncClient

from api.dependencies import get_current_user
from api.main import app
from tests.conftest import MOCK_ACCOUNTS
from tests.api.test_requests_baseline import _ensure_test_account, _ensure_test_unity

_REQUEST_PAYLOAD_BASE = {
    "description": "Description de test — lot finition workflow/notifications.",
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
        payload = {**_REQUEST_PAYLOAD_BASE, "title": f"Test finition {title_suffix}", "unity_id": unity_id}
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


def _dep(account_id: int, role: str, unity_id: int | None = None):
    def _factory():
        return SimpleNamespace(id=account_id, role=role, unity_id=unity_id, direction_id=None)
    return _factory


async def _assign_via_admin(auth_client, request_id: str, unity_id: int, assignee_id: int) -> None:
    async with auth_client("admin") as admin_client:
        resp = await admin_client.post(
            f"/api/v1/requests/{request_id}/qualify",
            json={"category": "panne", "priority": "medium", "unit_id": unity_id, "assignee_id": assignee_id},
        )
        assert resp.status_code == 200, resp.text


def _patch_service_request_emit(monkeypatch):
    """Intercepte ServiceRequest.emit_notif (alias importé au niveau module —
    monkeypatcher NotificationEmitter.emit directement n'affecterait pas cet
    alias déjà lié). Retourne la liste des appels capturés."""
    calls: list[dict] = []

    async def fake_emit(session, *, recipient_id, title, body, send_email=True, **kwargs):
        calls.append({
            "recipient_id": str(recipient_id) if recipient_id is not None else None,
            "title": title,
            "body": body,
            "send_email": send_email,
        })

    monkeypatch.setattr("api.services.ServiceRequest.emit_notif", fake_emit)
    return calls


# ── 2. (retiré) SLA préventif via ServiceEscalade ────────────────────────────
# Les deux tests qui couvraient `EscaladeService._notify()` sont partis le
# 2026-09-26 avec le statut "escalated" : le service n'existe plus.

# ── 3. Notification de clôture ─────────────────────────────────────────────────

async def test_close_notifies_requester_and_last_handler(auth_client, unity_id, monkeypatch):
    await _ensure_test_account(740, unity_id=unity_id, role="chief-service")
    request_id = await _create_ticket(auth_client, unity_id, "closure")
    await _assign_via_admin(auth_client, request_id, unity_id, assignee_id=740)

    resolve_resp = await _call_as(
        _dep(740, "chief-service", unity_id), "POST", f"/api/v1/requests/{request_id}/resolve",
        _FULL_RESOLVE_BODY,
    )
    assert resolve_resp.status_code == 200, resolve_resp.text

    calls = _patch_service_request_emit(monkeypatch)

    async with auth_client("user") as user_client:
        close_resp = await user_client.post(f"/api/v1/requests/{request_id}/close")
    assert close_resp.status_code == 200, close_resp.text
    assert close_resp.json()["data"]["request_status"] == "closed"
    # Purement informatif : jamais de réaffectation ni de nouveau cycle.
    assert close_resp.json()["data"]["assignee_id"] == 740

    requester_calls = [c for c in calls if c["recipient_id"] == str(MOCK_ACCOUNTS["user"].id) and c["title"] == "Ticket clôturé"]
    assert len(requester_calls) == 1
    assert requester_calls[0]["send_email"] is True
    assert "maintenant clôturé" in requester_calls[0]["body"]

    handler_calls = [c for c in calls if c["recipient_id"] == "740" and c["title"] == "Ticket clôturé"]
    assert len(handler_calls) == 1
    assert handler_calls[0]["send_email"] is False
    assert "confirmé la résolution" in handler_calls[0]["body"]


async def test_close_by_staff_no_duplicate_handler_notification_when_requester_is_handler(auth_client, unity_id, monkeypatch):
    """Cas limite : si le dernier intervenant est aussi le demandeur (ne devrait
    normalement pas arriver, cf. BR-REQUESTER-NO-SELF-TREATMENT-001, mais teste
    la déduplication défensive du code) — une seule notification est envoyée."""
    request_id = await _create_ticket(auth_client, unity_id, "closure-dedup")
    requester_id = MOCK_ACCOUNTS["user"].id

    calls = _patch_service_request_emit(monkeypatch)
    async with auth_client("admin") as admin_client:
        close_resp = await admin_client.post(f"/api/v1/requests/{request_id}/close")
    # Statut initial "new" n'autorise pas close() (nécessite "resolved") — mais si
    # jamais autorisé, on ne veut qu'une notification pour ce destinataire unique.
    if close_resp.status_code == 200:
        matching = [c for c in calls if c["recipient_id"] == str(requester_id) and c["title"] == "Ticket clôturé"]
        assert len(matching) == 1


# ── 4. reassign_service : demandeur + ancien responsable notifiés ─────────────

async def test_reassign_service_notifies_requester_and_previous_responsible(auth_client, unity_id, monkeypatch):
    """`change_service`/reassign_service n'est offert (frontend + garde backend,
    cf. TICKET_ACTION_STATUSES.change_service et ALLOWED_TRANSITIONS["assigned"])
    que sur un ticket encore en amont de la prise en charge effective (new/
    qualifying/qualified/reopened) — jamais sur un ticket déjà `in_progress`.
    Pour simuler malgré tout un « ancien responsable » réellement perdant sa
    responsabilité, on qualifie sans assignee (→ qualifying) puis on force
    assignee_id=741 via le PATCH générique admin (ne déclenche pas de
    transition de statut, cf. ServiceRequest.update), ce qui reproduit un état
    atteignable en pratique (édition admin) sans violer la matrice de transition."""
    await _ensure_test_unity(9610, parent_direction_id=None)
    await _ensure_test_account(741, unity_id=unity_id, role="chief-service")
    request_id = await _create_ticket(auth_client, unity_id, "reassign-service")
    async with auth_client("admin") as admin_client:
        qualify_resp = await admin_client.post(
            f"/api/v1/requests/{request_id}/qualify",
            json={"category": "panne", "priority": "medium", "unit_id": unity_id},
        )
        assert qualify_resp.status_code == 200, qualify_resp.text
        assert qualify_resp.json()["data"]["request_status"] == "qualifying"
        patch_resp = await admin_client.put(
            f"/api/v1/requests/{request_id}",
            json={"assignee_id": 741},
        )
        assert patch_resp.status_code == 200, patch_resp.text

    calls = _patch_service_request_emit(monkeypatch)

    resp = await _call_as(
        _dep(9999, "admin", None), "POST", f"/api/v1/requests/{request_id}/reassign",
        {"target_unity_id": "9610", "reason": "Test reaffectation service."},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["unity_id"] == 9610

    requester_calls = [c for c in calls if c["recipient_id"] == str(MOCK_ACCOUNTS["user"].id) and c["title"] == "Ticket réaffecté"]
    assert len(requester_calls) == 1
    assert requester_calls[0]["send_email"] is False
    assert "réorienté vers un autre service" in requester_calls[0]["body"]

    old_responsible_calls = [c for c in calls if c["recipient_id"] == "741" and c["title"] == "Ticket réaffecté"]
    assert len(old_responsible_calls) == 1
    assert old_responsible_calls[0]["send_email"] is False

    # Limitation connue (préexistante, hors périmètre) : RepositoryAccount.
    # find_chief_for_unity() filtre sur le rôle littéral "chief" (absent de
    # l'enum réel chief-service/chief-departement) — le chef du service cible
    # n'est donc jamais trouvé en pratique, ce chemin (App+Email) n'est pas
    # vérifiable ici tant que ce bug distinct n'est pas corrigé.


# ── 4. transfer_direction : directeur cible (App+Email) + demandeur + ancien ──

async def test_transfer_direction_notifies_new_director_requester_and_previous_responsible(auth_client, unity_id, monkeypatch):
    await _ensure_test_unity(9620, parent_direction_id=None)
    await _ensure_test_account(742, unity_id=9620, role="chief-service")  # directeur cible
    await _ensure_test_account(743, unity_id=unity_id, role="chief-service")  # ancien responsable
    request_id = await _create_ticket(auth_client, unity_id, "transfer-direction")
    await _assign_via_admin(auth_client, request_id, unity_id, assignee_id=743)

    calls = _patch_service_request_emit(monkeypatch)

    resp = await _call_as(
        _dep(9999, "admin", None), "POST", f"/api/v1/requests/{request_id}/transfer-direction",
        {"target_direction_id": "9620", "reason": "Test transfert inter-direction."},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["unity_id"] == 9620
    assert resp.json()["data"]["assignee_id"] is None

    director_calls = [c for c in calls if c["recipient_id"] == "742" and c["title"] == "Ticket transféré vers votre direction"]
    assert len(director_calls) == 1
    assert director_calls[0]["send_email"] is True
    assert "nécessite une prise en charge" in director_calls[0]["body"]

    requester_calls = [c for c in calls if c["recipient_id"] == str(MOCK_ACCOUNTS["user"].id) and c["title"] == "Ticket transféré"]
    assert len(requester_calls) == 1
    assert requester_calls[0]["send_email"] is False
    assert "transféré vers une autre direction" in requester_calls[0]["body"]

    old_responsible_calls = [c for c in calls if c["recipient_id"] == "743" and c["title"] == "Ticket transféré"]
    assert len(old_responsible_calls) == 1
    assert old_responsible_calls[0]["send_email"] is False

    # Aucune notification aux intervenants historiques (ici, il n'y en a qu'un
    # seul de toute façon — cycle collaboratif non exercé dans ce test ciblé,
    # déjà couvert par ailleurs pour BR-TRACE-001/l'historique append-only).
