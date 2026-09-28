"""Procedure EDG/PS-GSI/Pro-02, tache 1.3 — descriptif de la solution proposee.

Point de controle de l'imputation : en orientant une requisition vers un chef de
division support, le chef de service doit decrire la solution qu'il envisage.
Ce descriptif circule ensuite le long de la chaine de traitement — CDS puis
technicien — et n'est JAMAIS montre au demandeur : c'est une piste de travail
interne, qui peut se reveler fausse au diagnostic terrain.

La confidentialite est assuree par construction plutot que par effacement : le
champ n'existe sur aucun schema qu'un demandeur peut obtenir. Il n'est servi que
par `GET /requests/{id}/proposed-solution` (garde) et par la file Distribution
(endpoint deja garde). Les tests de non-fuite ci-dessous verrouillent ce choix.
"""
from __future__ import annotations

from tests.conftest import _TestSession
from tests.api.test_requests_baseline import _ensure_test_account
from tests.api.test_transmit_treatment import _call_as, _create_ticket, _dep

_CSSHF = 9700
_CDS = 9701
_TECH = 9702

_SOLUTION = "Remplacer le disque dur et restaurer la sauvegarde de la veille."


async def _setup(unity_id: int) -> None:
    await _ensure_test_account(_CSSHF, unity_id=unity_id, role="chief-service")
    await _ensure_test_account(_CDS, unity_id=unity_id, role="chef-division-support")
    await _ensure_test_account(_TECH, unity_id=unity_id, role="technicien")


async def _qualify(unity_id: int, request_id: str, *, assignee_id, solution=None):
    body = {"category": "panne", "priority": "medium", "unit_id": str(unity_id)}
    if assignee_id is not None:
        body["assignee_id"] = str(assignee_id)
    if solution is not None:
        body["proposed_solution"] = solution
    return await _call_as(
        _dep(_CSSHF, "chief-service", unity_id), "POST",
        f"/api/v1/requests/{request_id}/qualify", body,
    )


async def _ticket_row(request_id: str):
    from api.models.ModelRequest import Request as RequestModel
    async with _TestSession() as session:
        return await session.get(RequestModel, int(request_id))


# ── Le point de controle lui-meme ────────────────────────────────────────────

async def test_imputation_sans_solution_proposee_est_refusee(auth_client, unity_id):
    """Coeur de la tache 1.3 : pas d'imputation sans descriptif."""
    await _setup(unity_id)
    request_id = await _create_ticket(auth_client, unity_id, "sol-refus")

    resp = await _qualify(unity_id, request_id, assignee_id=_CDS)

    assert resp.status_code == 422, resp.text
    # Le ticket n'a pas bouge : aucune imputation, aucun descriptif enregistre.
    row = await _ticket_row(request_id)
    assert row.distributor_id is None
    assert row.proposed_solution is None


async def test_solution_vide_ou_blanche_ne_compte_pas(auth_client, unity_id):
    """Un descriptif reduit a des espaces ne vaut pas descriptif."""
    await _setup(unity_id)
    request_id = await _create_ticket(auth_client, unity_id, "sol-blanche")

    resp = await _qualify(unity_id, request_id, assignee_id=_CDS, solution="    ")

    assert resp.status_code == 422, resp.text


async def test_imputation_avec_solution_est_acceptee_et_persistee(auth_client, unity_id):
    await _setup(unity_id)
    request_id = await _create_ticket(auth_client, unity_id, "sol-ok")

    resp = await _qualify(unity_id, request_id, assignee_id=_CDS, solution=_SOLUTION)

    assert resp.status_code == 200, resp.text
    row = await _ticket_row(request_id)
    assert row.proposed_solution == _SOLUTION
    assert str(row.distributor_id) == str(_CDS)


async def test_prise_pour_soi_meme_ne_l_exige_pas(auth_client, unity_id):
    """Prendre le ticket pour son propre traitement n'est pas une imputation :
    la tache 1.3 ne s'applique pas, le descriptif reste facultatif."""
    await _setup(unity_id)
    request_id = await _create_ticket(auth_client, unity_id, "sol-self")

    resp = await _qualify(unity_id, request_id, assignee_id=_CSSHF)

    assert resp.status_code == 200, resp.text


async def test_qualification_sans_destinataire_ne_l_exige_pas(auth_client, unity_id):
    """Qualifier sans orienter (pas d'assignee) n'est pas davantage une imputation."""
    await _setup(unity_id)
    request_id = await _create_ticket(auth_client, unity_id, "sol-noassign")

    resp = await _qualify(unity_id, request_id, assignee_id=None)

    assert resp.status_code == 200, resp.text


# ── Circulation le long de la chaine de traitement ───────────────────────────

async def test_le_cds_voit_la_solution_dans_sa_file_distribution(auth_client, unity_id):
    """Le CDS decide de prendre ou d'affecter DEPUIS la liste : le descriptif
    doit donc y figurer, sans ouvrir la fiche."""
    await _setup(unity_id)
    request_id = await _create_ticket(auth_client, unity_id, "sol-cds-liste")
    assert (await _qualify(unity_id, request_id, assignee_id=_CDS, solution=_SOLUTION)).status_code == 200

    resp = await _call_as(
        _dep(_CDS, "chef-division-support", unity_id), "GET", "/api/v1/requests/distribution",
    )

    assert resp.status_code == 200, resp.text
    item = next(i for i in resp.json()["data"]["items"] if str(i["id"]) == str(request_id))
    assert item["proposed_solution"] == _SOLUTION


async def test_le_technicien_affecte_voit_la_solution(auth_client, unity_id):
    await _setup(unity_id)
    request_id = await _create_ticket(auth_client, unity_id, "sol-tech")
    assert (await _qualify(unity_id, request_id, assignee_id=_CDS, solution=_SOLUTION)).status_code == 200
    assign = await _call_as(
        _dep(_CDS, "chef-division-support", unity_id), "POST",
        f"/api/v1/requests/{request_id}/distribution/assign",
        {"technician_id": str(_TECH)},
    )
    assert assign.status_code == 200, assign.text

    resp = await _call_as(
        _dep(_TECH, "technicien", unity_id), "GET",
        f"/api/v1/requests/{request_id}/proposed-solution",
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["proposed_solution"] == _SOLUTION


async def test_le_chef_de_service_relit_sa_propre_solution(auth_client, unity_id):
    await _setup(unity_id)
    request_id = await _create_ticket(auth_client, unity_id, "sol-csshf-relit")
    assert (await _qualify(unity_id, request_id, assignee_id=_CDS, solution=_SOLUTION)).status_code == 200

    resp = await _call_as(
        _dep(_CSSHF, "chief-service", unity_id), "GET",
        f"/api/v1/requests/{request_id}/proposed-solution",
    )

    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["proposed_solution"] == _SOLUTION


# ── Non-fuite vers le demandeur ──────────────────────────────────────────────

async def test_le_demandeur_ne_peut_pas_lire_la_solution(auth_client, unity_id):
    """Un utilisateur simple est demandeur par nature : acces refuse."""
    await _setup(unity_id)
    request_id = await _create_ticket(auth_client, unity_id, "sol-demandeur")
    assert (await _qualify(unity_id, request_id, assignee_id=_CDS, solution=_SOLUTION)).status_code == 200

    async with auth_client("user") as client:
        resp = await client.get(f"/api/v1/requests/{request_id}/proposed-solution")

    assert resp.status_code == 403, resp.text


async def test_un_intervenant_demandeur_de_CE_ticket_ne_la_voit_pas(auth_client, unity_id):
    """Un technicien cree aussi ses propres tickets depuis son espace personnel.
    Sur SON ticket a lui, il est demandeur : le descriptif lui reste ferme, meme
    si son role figure parmi les lecteurs autorises."""
    await _setup(unity_id)
    creation = await _call_as(
        _dep(_TECH, "technicien", unity_id), "POST", "/api/v1/requests/",
        {
            "title": "Ticket cree par le technicien lui-meme",
            "description": "Demande personnelle, pas une intervention.",
            "category": "panne", "priority": "medium", "is_external": False,
            "requester_name": "Technicien Test", "unity_id": unity_id,
        },
    )
    assert creation.status_code == 201, creation.text
    request_id = str(creation.json()["data"]["id"])
    assert (await _qualify(unity_id, request_id, assignee_id=_CDS, solution=_SOLUTION)).status_code == 200

    resp = await _call_as(
        _dep(_TECH, "technicien", unity_id), "GET",
        f"/api/v1/requests/{request_id}/proposed-solution",
    )

    assert resp.status_code == 403, resp.text


async def test_la_fiche_du_ticket_ne_contient_jamais_la_solution(auth_client, unity_id):
    """Verrou de conception : `proposed_solution` ne doit apparaitre sur AUCUNE
    reponse detail, quel que soit le lecteur. C'est ce qui rend la fuite
    impossible sans effacement repete a chaque endpoint."""
    await _setup(unity_id)
    request_id = await _create_ticket(auth_client, unity_id, "sol-absente-fiche")
    assert (await _qualify(unity_id, request_id, assignee_id=_CDS, solution=_SOLUTION)).status_code == 200

    for dep in (
        _dep(_CDS, "chef-division-support", unity_id),
        _dep(_CSSHF, "chief-service", unity_id),
    ):
        resp = await _call_as(dep, "GET", f"/api/v1/requests/{request_id}")
        assert resp.status_code == 200, resp.text
        assert "proposed_solution" not in resp.json()["data"]

    async with auth_client("user") as client:
        resp = await client.get(f"/api/v1/requests/{request_id}")
    assert "proposed_solution" not in resp.json().get("data", {})


async def test_la_liste_personnelle_ne_contient_jamais_la_solution(auth_client, unity_id):
    """« Mes tickets » (espace personnel) partage son schema avec toutes les
    listes generiques : le descriptif ne doit y figurer sous aucun role."""
    await _setup(unity_id)
    request_id = await _create_ticket(auth_client, unity_id, "sol-absente-liste")
    assert (await _qualify(unity_id, request_id, assignee_id=_CDS, solution=_SOLUTION)).status_code == 200

    async with auth_client("admin") as client:
        resp = await client.get("/api/v1/requests/?limit=200")

    assert resp.status_code == 200, resp.text
    for item in resp.json()["data"]["items"]:
        assert "proposed_solution" not in item
