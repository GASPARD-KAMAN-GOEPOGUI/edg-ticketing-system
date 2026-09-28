"""
BR-TRAITEMENT-PROGRESSIF-001 — workflow progressif du traitement d'un ticket.

Remplace BR-QUEUE-AUTO-START-001 : une prise ou une assignation ne démarre plus
le traitement, elle désigne un intervenant. Le traitement suit désormais trois
gestes explicites et exclusifs :

    Constat  ->  Démarrer  ->  Terminer

Ce fichier verrouille l'ordre (le backend refuse toute séquence invalide),
l'horodatage serveur, le lieu d'intervention, et la non-régression de
« Transmettre le traitement », qui reste indépendant du workflow progressif.
"""
from __future__ import annotations

from tests.api.test_requests_baseline import _ensure_test_account
from tests.api.test_transmit_treatment import (
    _FULL_RESOLVE_BODY,
    _assign_via_admin,
    _call_as,
    _create_ticket,
    _dep,
)

_LOCATION = "Siège EDG — 3e étage, bureau 312"


async def _status(auth_client, request_id: str) -> str:
    async with auth_client("admin") as client:
        resp = await client.get(f"/api/v1/requests/{request_id}")
        assert resp.status_code == 200, resp.text
        return resp.json()["data"]["request_status"]


async def _field_check(actor_id: int, unity_id, request_id: str):
    return await _call_as(
        _dep(actor_id, "technicien", unity_id),
        "POST",
        f"/api/v1/requests/{request_id}/field-check",
        {"conformity": "conforme", "findings": "État réel conforme à la demande."},
    )


async def _start(actor_id: int, unity_id, request_id: str, location: str = _LOCATION):
    return await _call_as(
        _dep(actor_id, "technicien", unity_id),
        "POST",
        f"/api/v1/requests/{request_id}/start-treatment",
        {"location": location},
    )


async def _resolve(actor_id: int, unity_id, request_id: str):
    return await _call_as(
        _dep(actor_id, "technicien", unity_id),
        "POST",
        f"/api/v1/requests/{request_id}/resolve",
        _FULL_RESOLVE_BODY,
    )


async def _prepare(auth_client, unity_id, actor_id: int, suffix: str) -> str:
    """Ticket assigné à `actor_id`, prêt pour le workflow progressif."""
    await _ensure_test_account(actor_id, unity_id=unity_id, role="technicien")
    request_id = await _create_ticket(auth_client, unity_id, suffix)
    # `start=False` : ces tests observent justement l'état « assigned » et les
    # refus de séquence, donc ils ne veulent pas du démarrage que le helper
    # enchaîne par défaut.
    await _assign_via_admin(
        auth_client, request_id, unity_id, assignee_id=actor_id, start=False,
    )
    return request_id


# ── L'assignation ne démarre plus le traitement ───────────────────────────────

async def test_assignation_laisse_le_ticket_assigned(auth_client, unity_id):
    request_id = await _prepare(auth_client, unity_id, 972, "prog-assigned")
    assert await _status(auth_client, request_id) == "assigned"


# ── Workflow nominal ──────────────────────────────────────────────────────────

async def test_workflow_progressif_complet(auth_client, unity_id):
    request_id = await _prepare(auth_client, unity_id, 973, "prog-complet")

    assert (await _field_check(973, unity_id, request_id)).status_code == 200
    assert await _status(auth_client, request_id) == "assigned"

    assert (await _start(973, unity_id, request_id)).status_code == 200
    assert await _status(auth_client, request_id) == "in_progress"

    assert (await _resolve(973, unity_id, request_id)).status_code == 200
    assert await _status(auth_client, request_id) == "resolved"


async def test_demarrage_enregistre_lieu_et_horodatage_serveur(auth_client, unity_id):
    request_id = await _prepare(auth_client, unity_id, 974, "prog-lieu")
    await _field_check(974, unity_id, request_id)

    resp = await _start(974, unity_id, request_id)
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]

    # Le lieu alimente `location_label`, que le PV imprime déjà (`place`).
    assert data["location_label"] == _LOCATION
    # Date et heure de début prises côté serveur, jamais reçues du client.
    assert data["infos"]["treatment_started_at"]
    assert data["infos"]["treatment_location"] == _LOCATION


# ── Séquences invalides : le backend refuse ───────────────────────────────────

async def test_demarrage_refuse_sans_constat(auth_client, unity_id):
    request_id = await _prepare(auth_client, unity_id, 975, "prog-sans-constat")
    resp = await _start(975, unity_id, request_id)
    assert resp.status_code == 400, resp.text
    assert await _status(auth_client, request_id) == "assigned"


async def test_double_demarrage_refuse(auth_client, unity_id):
    request_id = await _prepare(auth_client, unity_id, 976, "prog-double-start")
    await _field_check(976, unity_id, request_id)
    assert (await _start(976, unity_id, request_id)).status_code == 200

    resp = await _start(976, unity_id, request_id)
    assert resp.status_code == 400, resp.text
    assert await _status(auth_client, request_id) == "in_progress"


async def test_terminaison_refusee_sans_demarrage(auth_client, unity_id):
    request_id = await _prepare(auth_client, unity_id, 977, "prog-sans-start")
    await _field_check(977, unity_id, request_id)

    resp = await _resolve(977, unity_id, request_id)
    assert resp.status_code == 400, resp.text
    assert await _status(auth_client, request_id) == "assigned"


async def test_double_terminaison_refusee(auth_client, unity_id):
    request_id = await _prepare(auth_client, unity_id, 978, "prog-double-end")
    await _field_check(978, unity_id, request_id)
    await _start(978, unity_id, request_id)
    assert (await _resolve(978, unity_id, request_id)).status_code == 200

    resp = await _resolve(978, unity_id, request_id)
    assert resp.status_code in (400, 403, 409), resp.text


async def test_lieu_obligatoire_au_demarrage(auth_client, unity_id):
    request_id = await _prepare(auth_client, unity_id, 979, "prog-lieu-vide")
    await _field_check(979, unity_id, request_id)

    resp = await _start(979, unity_id, request_id, location="   ")
    assert resp.status_code == 400, resp.text
    assert await _status(auth_client, request_id) == "assigned"


async def test_demarrage_refuse_a_un_tiers(auth_client, unity_id):
    """Un intervenant qui n'est pas le traitant actuel ne démarre rien."""
    request_id = await _prepare(auth_client, unity_id, 980, "prog-tiers")
    await _field_check(980, unity_id, request_id)
    await _ensure_test_account(981, unity_id=unity_id, role="technicien")

    resp = await _start(981, unity_id, request_id)
    assert resp.status_code in (400, 403), resp.text
    assert await _status(auth_client, request_id) == "assigned"


# ── Non-régression : « Transmettre le traitement » reste indépendant ──────────

async def test_transmettre_le_traitement_reste_fonctionnel(auth_client, unity_id):
    """Le workflow progressif ne doit pas toucher à la transmission.

    Elle reste disponible au traitant actuel et conserve son comportement : le
    ticket change d'intervenant, sans passer par le démarrage.
    """
    request_id = await _prepare(auth_client, unity_id, 982, "prog-transmit")
    await _ensure_test_account(983, unity_id=unity_id, role="technicien")
    await _field_check(982, unity_id, request_id)
    await _start(982, unity_id, request_id)

    resp = await _call_as(
        _dep(982, "technicien", unity_id),
        "POST",
        f"/api/v1/requests/{request_id}/transmit",
        {
            "to_user_id": "983",
            "work_done": "Diagnostic réalisé.",
            "reason": "Compétence réseau requise.",
        },
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["assignee_id"] in (983, "983")


async def test_transmission_ouvre_une_intervention_exigeant_son_propre_constat(
    auth_client, unity_id,
):
    """Le constat du précédent ne vaut pas pour le suivant : après réception,
    le nouvel intervenant doit refaire constat puis démarrage."""
    request_id = await _prepare(auth_client, unity_id, 984, "prog-transmit-constat")
    await _ensure_test_account(985, unity_id=unity_id, role="technicien")
    await _field_check(984, unity_id, request_id)
    await _start(984, unity_id, request_id)
    await _call_as(
        _dep(984, "technicien", unity_id),
        "POST",
        f"/api/v1/requests/{request_id}/transmit",
        {"to_user_id": "985", "work_done": "Diagnostic.", "reason": "Escalade technique."},
    )

    # Le nouvel intervenant ne peut pas terminer sans avoir fait son constat.
    resp = await _resolve(985, unity_id, request_id)
    assert resp.status_code == 400, resp.text


# ── BR-TRANSMIT-HANDOVER-001 étendue — l'assignation directe compte comme un
#    dessaisissement, mais jamais l'auto-assignation ────────────────────────────

async def _transmitted_ids(actor_id: int, unity_id) -> set[str]:
    resp = await _call_as(
        _dep(actor_id, "chief-service", unity_id),
        "GET",
        "/api/v1/requests/transmitted?limit=100",
    )
    assert resp.status_code == 200, resp.text
    return {str(item["id"]) for item in resp.json()["data"]["items"]}


async def test_assignation_directe_apparait_dans_tickets_transmis(auth_client, unity_id):
    """Un chef de service qui assigne directement un ticket à un technicien
    depuis la File d'attente doit le retrouver dans « Tickets transmis » : il
    s'en est dessaisi, exactement comme par une transmission."""
    await _ensure_test_account(986, unity_id=unity_id, role="chief-service")
    await _ensure_test_account(987, unity_id=unity_id, role="technicien")
    request_id = await _create_ticket(auth_client, unity_id, "handover-direct")

    async with auth_client("admin") as admin_client:
        resp = await admin_client.post(
            f"/api/v1/requests/{request_id}/qualify",
            json={"category": "panne", "priority": "medium",
                  "unit_id": unity_id, "assignee_id": 987},
        )
        assert resp.status_code == 200, resp.text

    # L'admin (compte 6 dans les mocks) est l'émetteur de cette assignation.
    assert request_id in await _transmitted_ids(6, unity_id)


async def test_auto_assignation_n_apparait_jamais_dans_tickets_transmis(auth_client, unity_id):
    """« Prendre le ticket » produit le même événement `assigned` qu'une
    assignation à un tiers. Sans garde, le ticket finirait par apparaître comme
    « transmis » par celui qui se l'était simplement attribué — ici on vérifie
    qu'il n'y apparaît pas, même une fois passé à quelqu'un d'autre."""
    await _ensure_test_account(988, unity_id=unity_id, role="chief-service")
    await _ensure_test_account(989, unity_id=unity_id, role="technicien")
    request_id = await _create_ticket(auth_client, unity_id, "handover-self")

    # 988 se prend le ticket pour lui-même depuis la File d'attente.
    take = await _call_as(
        _dep(988, "chief-service", unity_id), "POST",
        f"/api/v1/requests/{request_id}/qualify",
        {"category": "panne", "priority": "medium",
         "unit_id": str(unity_id), "assignee_id": "988"},
    )
    assert take.status_code == 200, take.text
    assert request_id not in await _transmitted_ids(988, unity_id)

    # Le ticket part ensuite à quelqu'un d'autre : 988 n'en est plus le traitant,
    # mais il ne l'a pas transmis pour autant — il ne doit toujours pas y figurer.
    async with auth_client("admin") as admin_client:
        moved = await admin_client.post(
            f"/api/v1/requests/{request_id}/assign?assignee_id=989",
        )
        assert moved.status_code == 200, moved.text

    assert request_id not in await _transmitted_ids(988, unity_id)
