"""BR-DISTRIBUTION-001 — file "Distribution" du chef de division support.

Workflow cible :
  Chef de service ──assigne au CDS──▶ Distribution du CDS
                                          ├─▶ "Prendre en charge"  → CDS traitant
                                          └─▶ "Assigner technicien" → technicien traitant

Point cle du modele : `distributor_id` (destinataire de DISTRIBUTION) est distinct de
`assignee_id` (responsable OPERATIONNEL). Recevoir un ticket ne fait pas du CDS un
traitant — il ne quitte la Distribution que lorsqu'un `assignee_id` est pose.

Couvre les 13 scenarios demandes (TEST 1 a TEST 13).
"""
from __future__ import annotations

import asyncio

import pytest

from tests.conftest import _TestSession
from tests.api.test_requests_baseline import _ensure_test_account
from tests.api.test_transmit_treatment import _call_as, _create_ticket, _dep

# Acteurs
_CSSHF = 9000            # chef de service (unite A)
_CDS_A = 9001            # chef de division support — unite A
_CDS_B = 9002            # chef de division support — unite B
_TECH_A = 9003           # technicien — unite A (division du CDS A)
_TECH_B = 9004           # technicien — unite B (autre division)
_TECH_A_INACTIF = 9005   # technicien — unite A mais inactif
_UNITY_B = 990


async def _setup_actors(unity_id: int) -> None:
    await _ensure_test_account(_CSSHF, unity_id=unity_id, role="chief-service")
    await _ensure_test_account(_CDS_A, unity_id=unity_id, role="chef-division-support")
    await _ensure_test_account(_CDS_B, unity_id=_UNITY_B, role="chef-division-support")
    await _ensure_test_account(_TECH_A, unity_id=unity_id, role="technicien")
    await _ensure_test_account(_TECH_B, unity_id=_UNITY_B, role="technicien")


async def _distribute_to_cds(unity_id: int, request_id: str, cds_id: int = _CDS_A):
    """Le chef de service oriente le ticket vers un chef de division support."""
    return await _call_as(
        _dep(_CSSHF, "chief-service", unity_id), "POST",
        f"/api/v1/requests/{request_id}/qualify",
        {"category": "panne", "priority": "medium", "unit_id": str(unity_id),
         "assignee_id": str(cds_id),
         # Procedure EDG/PS-GSI/Pro-02 tache 1.3 — le descriptif de solution
         # proposee est obligatoire pour imputer a un CDS. Ces tests portent sur
         # la file Distribution elle-meme : on le renseigne pour ne pas melanger
         # les deux regles (voir test_proposed_solution.py).
         "proposed_solution": "Piste de resolution proposee par le chef de service."},
    )


async def _distribution_ids(actor_id: int, unity_id: int) -> list[str]:
    resp = await _call_as(
        _dep(actor_id, "chef-division-support", unity_id), "GET",
        "/api/v1/requests/distribution",
    )
    assert resp.status_code == 200, resp.text
    return [str(item["id"]) for item in resp.json()["data"]["items"]]


async def _ticket_row(request_id: str):
    from api.models.ModelRequest import Request as RequestModel
    async with _TestSession() as session:
        return await session.get(RequestModel, int(request_id))


async def _event_types(request_id: str) -> list[str]:
    from sqlalchemy import select
    from api.models.ModelWorkflow import Workflow
    from api.models.ModelWorkflowDetail import WorkflowDetail
    async with _TestSession() as session:
        rows = await session.execute(
            select(WorkflowDetail.event_type)
            .join(Workflow, WorkflowDetail.workflow_id == Workflow.id)
            .where(Workflow.request_id == int(request_id))
        )
        return [r[0] for r in rows.all()]


# ── TEST 1 — le ticket arrive dans la Distribution du CDS destinataire ───────

async def test_1_ticket_arrive_dans_la_distribution_du_cds(auth_client, unity_id):
    await _setup_actors(unity_id)
    request_id = await _create_ticket(auth_client, unity_id, "distrib-1")

    resp = await _distribute_to_cds(unity_id, request_id)
    assert resp.status_code == 200, resp.text

    # Destinataire de distribution posé, mais AUCUN responsable opérationnel.
    row = await _ticket_row(request_id)
    assert str(row.distributor_id) == str(_CDS_A)
    assert row.assignee_id is None
    assert row.in_triage is False  # a bien quitté la file d'attente du chef de service

    assert request_id in await _distribution_ids(_CDS_A, unity_id)
    assert "distributed_to_division" in await _event_types(request_id)


# ── TEST 2 — cloisonnement entre CDS ────────────────────────────────────────

async def test_2_un_autre_cds_ne_voit_pas_le_ticket(auth_client, unity_id):
    await _setup_actors(unity_id)
    request_id = await _create_ticket(auth_client, unity_id, "distrib-2")
    await _distribute_to_cds(unity_id, request_id)

    assert request_id not in await _distribution_ids(_CDS_B, _UNITY_B)


# ── TEST 3 — prise en charge par le CDS ─────────────────────────────────────

async def test_3_cds_prend_le_ticket_en_charge(auth_client, unity_id):
    await _setup_actors(unity_id)
    request_id = await _create_ticket(auth_client, unity_id, "distrib-3")
    await _distribute_to_cds(unity_id, request_id)

    resp = await _call_as(
        _dep(_CDS_A, "chef-division-support", unity_id), "POST",
        f"/api/v1/requests/{request_id}/distribution/take",
    )
    assert resp.status_code == 200, resp.text
    assert str(resp.json()["data"]["assignee_id"]) == str(_CDS_A)

    # Sorti de Distribution, entré dans SA boîte de traitement.
    assert request_id not in await _distribution_ids(_CDS_A, unity_id)
    row = await _ticket_row(request_id)
    assert str(row.assignee_id) == str(_CDS_A)
    # BR-TRAITEMENT-PROGRESSIF-001 — la sortie de Distribution designe le
    # responsable operationnel sans demarrer son traitement, qui commence a son
    # geste explicite (`start-treatment`).
    assert row.request_status == "assigned"
    assert "distribution_taken" in await _event_types(request_id)


# ── TEST 4 — assignation a un technicien de sa division ─────────────────────

async def test_4_cds_assigne_a_un_technicien_de_sa_division(auth_client, unity_id):
    await _setup_actors(unity_id)
    request_id = await _create_ticket(auth_client, unity_id, "distrib-4")
    await _distribute_to_cds(unity_id, request_id)

    resp = await _call_as(
        _dep(_CDS_A, "chef-division-support", unity_id), "POST",
        f"/api/v1/requests/{request_id}/distribution/assign",
        {"technician_id": str(_TECH_A)},
    )
    assert resp.status_code == 200, resp.text
    assert str(resp.json()["data"]["assignee_id"]) == str(_TECH_A)

    assert request_id not in await _distribution_ids(_CDS_A, unity_id)
    row = await _ticket_row(request_id)
    assert str(row.assignee_id) == str(_TECH_A)
    assert "distribution_assigned" in await _event_types(request_id)

    # Notification envoyée au technicien.
    from tests.api.test_transmit_treatment import _notifications_for
    notifs = await _notifications_for(_TECH_A, request_id)
    assert any("assigné" in (n.title or "").lower() for n in notifs)


# ── TEST 5 — technicien d'une autre division : REFUS ────────────────────────

async def test_5_refus_technicien_autre_division(auth_client, unity_id):
    await _setup_actors(unity_id)
    request_id = await _create_ticket(auth_client, unity_id, "distrib-5")
    await _distribute_to_cds(unity_id, request_id)

    resp = await _call_as(
        _dep(_CDS_A, "chef-division-support", unity_id), "POST",
        f"/api/v1/requests/{request_id}/distribution/assign",
        {"technician_id": str(_TECH_B)},
    )
    assert resp.status_code == 403, resp.text
    row = await _ticket_row(request_id)
    assert row.assignee_id is None  # le ticket n'a pas bougé


# ── TEST 6 — IDOR : un CDS manipule l'ID d'un ticket d'un autre CDS ─────────

async def test_6_refus_idor_ticket_d_un_autre_cds(auth_client, unity_id):
    await _setup_actors(unity_id)
    request_id = await _create_ticket(auth_client, unity_id, "distrib-6")
    await _distribute_to_cds(unity_id, request_id)  # destiné au CDS A

    # Le CDS B tente de le prendre...
    resp = await _call_as(
        _dep(_CDS_B, "chef-division-support", _UNITY_B), "POST",
        f"/api/v1/requests/{request_id}/distribution/take",
    )
    assert resp.status_code == 403, resp.text

    # ...puis de l'assigner à SON propre technicien.
    resp = await _call_as(
        _dep(_CDS_B, "chef-division-support", _UNITY_B), "POST",
        f"/api/v1/requests/{request_id}/distribution/assign",
        {"technician_id": str(_TECH_B)},
    )
    assert resp.status_code == 403, resp.text

    row = await _ticket_row(request_id)
    assert row.assignee_id is None


# ── TEST 7 — double prise en charge ─────────────────────────────────────────

async def test_7_double_prise_en_charge_refusee(auth_client, unity_id):
    await _setup_actors(unity_id)
    request_id = await _create_ticket(auth_client, unity_id, "distrib-7")
    await _distribute_to_cds(unity_id, request_id)

    first = await _call_as(
        _dep(_CDS_A, "chef-division-support", unity_id), "POST",
        f"/api/v1/requests/{request_id}/distribution/take",
    )
    assert first.status_code == 200, first.text

    second = await _call_as(
        _dep(_CDS_A, "chef-division-support", unity_id), "POST",
        f"/api/v1/requests/{request_id}/distribution/take",
    )
    assert second.status_code == 409, second.text  # conflit propre, pas de 500


# ── TEST 8 — concurrence : prise en charge VS assignation ───────────────────

@pytest.mark.skip(
    reason=(
        "Concurrence reelle non testable sous ce harness : la base de test est SQLite "
        "in-memory avec poolclass=StaticPool (conftest.py), donc toutes les sessions "
        "partagent UNE connexion physique — le rollback de l'operation perdante annule "
        "l'ecriture de la gagnante et le resultat depend de l'ordonnancement. La garde "
        "reelle est le compare-and-set SQL `WHERE assignee_id IS NULL` "
        "(ServiceRequest._exit_distribution), et l'invariant 'un seul responsable' est "
        "verifie de facon deterministe par test_8bis_invariant_un_seul_responsable."
    )
)
async def test_8_actions_concurrentes_une_seule_reussit(auth_client, unity_id):
    await _setup_actors(unity_id)
    request_id = await _create_ticket(auth_client, unity_id, "distrib-8")
    await _distribute_to_cds(unity_id, request_id)

    take, assign = await asyncio.gather(
        _call_as(
            _dep(_CDS_A, "chef-division-support", unity_id), "POST",
            f"/api/v1/requests/{request_id}/distribution/take",
        ),
        _call_as(
            _dep(_CDS_A, "chef-division-support", unity_id), "POST",
            f"/api/v1/requests/{request_id}/distribution/assign",
            {"technician_id": str(_TECH_A)},
        ),
        return_exceptions=True,
    )
    codes = [getattr(r, "status_code", 500) for r in (take, assign)]
    assert codes.count(200) == 1, f"exactement une operation doit reussir — {codes}"
    assert 409 in codes, f"la seconde doit echouer proprement en conflit — {codes}"

    # NB harness : la base de test est SQLite in-memory avec `poolclass=StaticPool`
    # (conftest.py) — toutes les sessions partagent UNE connexion physique, donc le
    # rollback de l'operation perdante annule aussi l'ecriture de la gagnante. L'etat
    # final n'est donc pas observable ici (il l'est en production, ou chaque requete a
    # sa propre connexion MySQL). L'invariant "jamais deux boites de traitement" est
    # verifie de maniere deterministe juste en dessous.


async def test_8bis_invariant_un_seul_responsable(auth_client, unity_id):
    """Invariant central verifie de facon deterministe : une fois un responsable
    designe, aucune seconde designation ne peut passer — le ticket ne peut jamais
    se retrouver dans deux boites de traitement."""
    await _setup_actors(unity_id)
    request_id = await _create_ticket(auth_client, unity_id, "distrib-8bis")
    await _distribute_to_cds(unity_id, request_id)

    first = await _call_as(
        _dep(_CDS_A, "chef-division-support", unity_id), "POST",
        f"/api/v1/requests/{request_id}/distribution/take",
    )
    assert first.status_code == 200, first.text

    second = await _call_as(
        _dep(_CDS_A, "chef-division-support", unity_id), "POST",
        f"/api/v1/requests/{request_id}/distribution/assign",
        {"technician_id": str(_TECH_A)},
    )
    assert second.status_code == 409, second.text

    row = await _ticket_row(request_id)
    assert str(row.assignee_id) == str(_CDS_A)  # un seul responsable, le premier
    assert request_id not in await _distribution_ids(_CDS_A, unity_id)


# ── TEST 9 — technicien inactif ─────────────────────────────────────────────

async def test_9_technicien_inactif_refuse(auth_client, unity_id):
    await _setup_actors(unity_id)
    await _ensure_test_account(_TECH_A_INACTIF, unity_id=unity_id, role="technicien")
    # Désactivation explicite.
    from api.models.ModelAccount import Account
    async with _TestSession() as session:
        acc = await session.get(Account, _TECH_A_INACTIF)
        acc.account_status = "inactive"
        await session.commit()

    request_id = await _create_ticket(auth_client, unity_id, "distrib-9")
    await _distribute_to_cds(unity_id, request_id)

    resp = await _call_as(
        _dep(_CDS_A, "chef-division-support", unity_id), "POST",
        f"/api/v1/requests/{request_id}/distribution/assign",
        {"technician_id": str(_TECH_A_INACTIF)},
    )
    assert resp.status_code == 403, resp.text

    # Et il n'est pas proposé comme destinataire.
    techs = await _call_as(
        _dep(_CDS_A, "chef-division-support", unity_id), "GET",
        "/api/v1/requests/distribution/technicians",
    )
    assert techs.status_code == 200, techs.text
    ids = [t["id"] for t in techs.json()["data"]]
    assert str(_TECH_A_INACTIF) not in ids
    assert str(_TECH_A) in ids
    assert str(_TECH_B) not in ids  # ni les techniciens d'une autre division


# ── TEST 10 — roles non autorises sur les endpoints Distribution ────────────

@pytest.mark.parametrize("role", ["user", "chief-service", "technicien", "chief-departement", "director"])
async def test_10_roles_non_autorises_refuses(auth_client, unity_id, role):
    await _setup_actors(unity_id)
    account_id = 9100 + ["user", "chief-service", "technicien", "chief-departement", "director"].index(role)
    await _ensure_test_account(account_id, unity_id=unity_id, role=role)
    request_id = await _create_ticket(auth_client, unity_id, f"distrib-10-{role}")
    await _distribute_to_cds(unity_id, request_id)

    for method, path, body in (
        ("GET", "/api/v1/requests/distribution", None),
        ("GET", "/api/v1/requests/distribution/technicians", None),
        ("POST", f"/api/v1/requests/{request_id}/distribution/take", None),
        ("POST", f"/api/v1/requests/{request_id}/distribution/assign", {"technician_id": str(_TECH_A)}),
    ):
        resp = await _call_as(_dep(account_id, role, unity_id), method, path, body)
        assert resp.status_code == 403, f"{role} {method} {path} → {resp.status_code}"


# ── TEST 11 — ticket qui n'est plus dans la Distribution ────────────────────

async def test_11_assigner_un_ticket_hors_distribution_refuse(auth_client, unity_id):
    await _setup_actors(unity_id)
    request_id = await _create_ticket(auth_client, unity_id, "distrib-11")
    await _distribute_to_cds(unity_id, request_id)

    taken = await _call_as(
        _dep(_CDS_A, "chef-division-support", unity_id), "POST",
        f"/api/v1/requests/{request_id}/distribution/take",
    )
    assert taken.status_code == 200, taken.text

    resp = await _call_as(
        _dep(_CDS_A, "chef-division-support", unity_id), "POST",
        f"/api/v1/requests/{request_id}/distribution/assign",
        {"technician_id": str(_TECH_A)},
    )
    assert resp.status_code == 409, resp.text


# ── TEST 12 & 13 — sortie effective de la file dans les deux cas ────────────

async def test_12_ticket_pris_en_charge_disparait_de_la_distribution(auth_client, unity_id):
    await _setup_actors(unity_id)
    request_id = await _create_ticket(auth_client, unity_id, "distrib-12")
    await _distribute_to_cds(unity_id, request_id)
    assert request_id in await _distribution_ids(_CDS_A, unity_id)

    await _call_as(
        _dep(_CDS_A, "chef-division-support", unity_id), "POST",
        f"/api/v1/requests/{request_id}/distribution/take",
    )
    assert request_id not in await _distribution_ids(_CDS_A, unity_id)


async def test_13_ticket_assigne_disparait_de_la_distribution(auth_client, unity_id):
    await _setup_actors(unity_id)
    request_id = await _create_ticket(auth_client, unity_id, "distrib-13")
    await _distribute_to_cds(unity_id, request_id)
    assert request_id in await _distribution_ids(_CDS_A, unity_id)

    await _call_as(
        _dep(_CDS_A, "chef-division-support", unity_id), "POST",
        f"/api/v1/requests/{request_id}/distribution/assign",
        {"technician_id": str(_TECH_A)},
    )
    assert request_id not in await _distribution_ids(_CDS_A, unity_id)


# ── REVUE — la Distribution est la seule porte de sortie (anti-contournement) ─

async def test_14_technicien_ne_peut_pas_s_auto_assigner_un_ticket_en_distribution(
    auth_client, unity_id,
):
    """Anomalie identifiee en revue : `distributor_id` pose + `assignee_id` NULL rendait
    le ticket "libre" pour le chemin d'assignation generique — un technicien du service
    pouvait s'auto-assigner via POST /{id}/assign et court-circuiter la repartition."""
    await _setup_actors(unity_id)
    request_id = await _create_ticket(auth_client, unity_id, "bypass-assign")
    await _distribute_to_cds(unity_id, request_id)

    resp = await _call_as(
        _dep(_TECH_A, "technicien", unity_id), "POST",
        f"/api/v1/requests/{request_id}/assign?assignee_id={_TECH_A}",
    )
    assert resp.status_code == 403, resp.text

    row = await _ticket_row(request_id)
    assert row.assignee_id is None  # toujours en Distribution
    assert request_id in await _distribution_ids(_CDS_A, unity_id)


async def test_15_chef_service_ne_peut_pas_requalifier_un_ticket_en_distribution(
    auth_client, unity_id,
):
    """Anomalie identifiee en revue : le chef de service pouvait re-qualifier un ticket
    deja distribue et se le reattribuer, le sortant silencieusement de la file du CDS."""
    await _setup_actors(unity_id)
    request_id = await _create_ticket(auth_client, unity_id, "bypass-requalify")
    await _distribute_to_cds(unity_id, request_id)

    resp = await _call_as(
        _dep(_CSSHF, "chief-service", unity_id), "POST",
        f"/api/v1/requests/{request_id}/qualify",
        {"category": "panne", "priority": "high", "unit_id": str(unity_id),
         "assignee_id": str(_CSSHF)},
    )
    assert resp.status_code == 403, resp.text

    row = await _ticket_row(request_id)
    assert row.assignee_id is None
    assert str(row.distributor_id) == str(_CDS_A)
    assert request_id in await _distribution_ids(_CDS_A, unity_id)


async def test_16_admin_conserve_son_bypass(auth_client, unity_id):
    """L'admin reste non contraint, conformement aux conventions du projet."""
    await _setup_actors(unity_id)
    request_id = await _create_ticket(auth_client, unity_id, "admin-bypass")
    await _distribute_to_cds(unity_id, request_id)

    resp = await _call_as(
        _dep(6, "admin", unity_id), "POST",
        f"/api/v1/requests/{request_id}/assign?assignee_id={_TECH_A}",
    )
    assert resp.status_code == 200, resp.text


async def test_17_tickets_anciens_sans_distributeur_non_impactes(auth_client, unity_id):
    """Donnees anciennes (`distributor_id = NULL`) : le chemin d'assignation generique
    doit continuer a fonctionner exactement comme avant."""
    await _setup_actors(unity_id)
    request_id = await _create_ticket(auth_client, unity_id, "legacy-null")

    row = await _ticket_row(request_id)
    assert row.distributor_id is None  # ticket "ancien style"

    resp = await _call_as(
        _dep(6, "admin", unity_id), "POST",
        f"/api/v1/requests/{request_id}/assign?assignee_id={_TECH_A}",
    )
    assert resp.status_code == 200, resp.text
    assert str(resp.json()["data"]["assignee_id"]) == str(_TECH_A)


# ── NON-REGRESSION — la chaine dynamique A → An reste libre ─────────────────

async def test_non_regression_transmission_dynamique_apres_distribution(auth_client, unity_id):
    """Une fois sorti de la Distribution, le ticket reste transmissible librement
    entre intervenants (BR-TRANSMIT-001), sans contrainte de division."""
    await _setup_actors(unity_id)
    request_id = await _create_ticket(auth_client, unity_id, "distrib-chain")
    await _distribute_to_cds(unity_id, request_id)
    await _call_as(
        _dep(_CDS_A, "chef-division-support", unity_id), "POST",
        f"/api/v1/requests/{request_id}/distribution/assign",
        {"technician_id": str(_TECH_A)},
    )

    resp = await _call_as(
        _dep(_TECH_A, "technicien", unity_id), "POST",
        f"/api/v1/requests/{request_id}/transmit",
        {"to_user_id": str(_CDS_A), "work_done": "Diagnostic pose.", "reason": "Arbitrage requis."},
    )
    assert resp.status_code == 200, resp.text
    assert str(resp.json()["data"]["assignee_id"]) == str(_CDS_A)


# ── BR-TRANSMIT-HANDOVER-001 — le CDS retrouve ce qu'il a reparti ─────────────

async def _transmitted_ids(actor_id: int, unity_id: int) -> set[str]:
    resp = await _call_as(
        _dep(actor_id, "chef-division-support", unity_id),
        "GET",
        "/api/v1/requests/transmitted?limit=100",
    )
    assert resp.status_code == 200, resp.text
    return {str(item["id"]) for item in resp.json()["data"]["items"]}


async def test_cds_retrouve_dans_tickets_transmis_ce_qu_il_a_distribue(auth_client, unity_id):
    """Repartir un ticket a un technicien depuis le menu Distribution est un
    dessaisissement : le chef de division doit le retrouver dans
    « Tickets transmis »."""
    await _setup_actors(unity_id)
    request_id = await _create_ticket(auth_client, unity_id, "distrib-transmis")
    await _distribute_to_cds(unity_id, request_id)

    # Avant repartition, le ticket est dans SA file Distribution, pas transmis.
    assert request_id not in await _transmitted_ids(_CDS_A, unity_id)

    resp = await _call_as(
        _dep(_CDS_A, "chef-division-support", unity_id), "POST",
        f"/api/v1/requests/{request_id}/distribution/assign",
        {"technician_id": str(_TECH_A)},
    )
    assert resp.status_code == 200, resp.text

    assert request_id in await _transmitted_ids(_CDS_A, unity_id)


async def test_cds_qui_se_prend_le_ticket_ne_le_voit_pas_comme_transmis(auth_client, unity_id):
    """`distribution_taken` : le CDS se l'assigne a lui-meme, il ne transmet
    rien — le ticket ne doit pas figurer dans « Tickets transmis »."""
    await _setup_actors(unity_id)
    request_id = await _create_ticket(auth_client, unity_id, "distrib-pris")
    await _distribute_to_cds(unity_id, request_id)

    resp = await _call_as(
        _dep(_CDS_A, "chef-division-support", unity_id), "POST",
        f"/api/v1/requests/{request_id}/distribution/take",
    )
    assert resp.status_code == 200, resp.text

    assert request_id not in await _transmitted_ids(_CDS_A, unity_id)
