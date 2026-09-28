from __future__ import annotations

from types import SimpleNamespace

from httpx import ASGITransport, AsyncClient

from api.dependencies import get_current_user
from api.main import app

_REQUEST_PAYLOAD_BASE = {
    "title": "Test patch scope ticket",
    "description": "Description de test pour le verrou PATCH generique.",
    "category": "panne",
    "priority": "medium",
    "is_external": False,
    "requester_name": "Citoyen Test",
    "requester_email": "citoyen@test.edg.gn",
}


async def _create_ticket(client, unity_id: int, title_suffix: str) -> str:
    payload = {**_REQUEST_PAYLOAD_BASE, "title": f"Test patch scope ticket {title_suffix}", "unity_id": unity_id}
    resp = await client.post("/api/v1/requests/", json=payload)
    assert resp.status_code == 201, resp.text
    return str(resp.json()["data"]["id"])


async def _create_assigned_ticket(auth_client, unity_id: int, title_suffix: str, assignee_id: int) -> str:
    """Cree un ticket (role user) puis le fait passer en statut 'assigned' (une des sources
    valides pour la transition 'in_progress' selon ALLOWED_TRANSITIONS) via un PATCH admin
    direct — PAS via /qualify, qui depuis BR-QUEUE-AUTO-START-001 demarre desormais
    directement le traitement (in_progress) pour une prise/assignation reelle depuis la
    File d'attente. Ce helper a besoin d'un etat "assigned mais non demarre" intermediaire
    (scenario legitime residuel, ex. reassign_service) pour tester que la route PATCH
    generique peut encore transitionner explicitement vers in_progress.
    Deux blocs `async with` SEQUENTIELS (pas combines) : l'override de get_current_user est un
    etat global de l'app — les ouvrir simultanement fait gagner le dernier partout."""
    async with auth_client("user") as user_client:
        request_id = await _create_ticket(user_client, unity_id, title_suffix)
    async with auth_client("admin") as admin_client:
        resp = await admin_client.put(
            f"/api/v1/requests/{request_id}",
            json={"assignee_id": assignee_id, "request_status": "assigned"},
        )
        assert resp.status_code == 200, resp.text
    return request_id


async def test_patch_blocks_staff_outside_perimeter(auth_client, unity_id):
    """Lot 2.1 : PATCH /requests/{id} verifiait uniquement require_roles — un chief-service
    hors perimetre pouvait modifier n'importe quel ticket. _resolve_access doit maintenant
    bloquer cet acces (meme garde que les autres routes d'action)."""
    async with auth_client("user") as user_client:
        request_id = await _create_ticket(user_client, unity_id, "outsider")

    def _outsider_dep():
        return SimpleNamespace(id=555, role="chief-service", unity_id=unity_id + 999999, direction_id=None)

    app.dependency_overrides[get_current_user] = _outsider_dep
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.put(f"/api/v1/requests/{request_id}", json={"request_status": "in_progress"})
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 403, resp.text


async def test_patch_allows_in_scope_staff_to_transition_status(auth_client, unity_id):
    """Regression : take_ownership/resume/request_info (in_progress, pending) doivent
    continuer a fonctionner pour un staff DANS son perimetre — c'est le seul usage front
    reel de cette route generique (5 appels verifies : app.supervision.tsx, app.requests.$id.tsx,
    app.direction.tsx, tous limites a request_status/status_reason)."""
    request_id = await _create_assigned_ticket(auth_client, unity_id, "in-scope-status", 556)

    def _agent_dep():
        return SimpleNamespace(id=556, role="chief-service", unity_id=unity_id, direction_id=None)

    app.dependency_overrides[get_current_user] = _agent_dep
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.put(f"/api/v1/requests/{request_id}", json={"request_status": "in_progress"})
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["request_status"] == "in_progress"


async def test_patch_silently_drops_non_status_fields_for_non_admin_staff(auth_client, unity_id):
    """Le correctif restreint les champs acceptes pour tout staff non-admin a
    {request_status, status_reason} — category/priority/assignee_id ne doivent plus
    passer par cette route generique (routes dediees : qualify/assign/priority)."""
    async with auth_client("user") as user_client:
        request_id = await _create_ticket(user_client, unity_id, "field-restriction")

    def _agent_dep():
        return SimpleNamespace(id=557, role="chief-service", unity_id=unity_id, direction_id=None)

    app.dependency_overrides[get_current_user] = _agent_dep
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.put(
                f"/api/v1/requests/{request_id}",
                json={"category": "reclamation", "priority": "critical"},
            )
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200, resp.text
    # Les deux champs envoyes ne font pas partie des champs autorises pour un staff
    # non-admin : ils doivent rester inchanges (valeurs de creation d'origine).
    assert resp.json()["data"]["category"] == "panne"
    assert resp.json()["data"]["priority"] == "medium"


async def test_patch_director_status_transition_unaffected(auth_client, unity_id):
    """Point d'attention explicite : director n'utilise cette route que pour
    request_status=in_progress (app.direction.tsx) — la restriction aux champs
    {request_status, status_reason} ne change donc rien pour ce role."""
    request_id = await _create_assigned_ticket(auth_client, unity_id, "director-status", 559)

    def _director_dep():
        return SimpleNamespace(id=558, role="chief-service", unity_id=unity_id, direction_id=None)

    app.dependency_overrides[get_current_user] = _director_dep
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.put(f"/api/v1/requests/{request_id}", json={"request_status": "in_progress"})
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["request_status"] == "in_progress"


async def test_patch_admin_keeps_full_field_access(auth_client, unity_id):
    """Regression : admin garde l'acces complet (toutes permissions, rbac.py) — le
    correctif ne restreint que les roles staff non-admin."""
    async with auth_client("user") as user_client:
        request_id = await _create_ticket(user_client, unity_id, "admin-full-access")

    async with auth_client("admin") as admin_client:
        resp = await admin_client.put(
            f"/api/v1/requests/{request_id}",
            json={"priority": "critical"},
        )
        assert resp.status_code == 200, resp.text
        assert resp.json()["data"]["priority"] == "critical"
