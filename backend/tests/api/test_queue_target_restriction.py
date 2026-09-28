"""Module 2 — Issues autorisees depuis la File d'attente.

Le chef de service (CSSHF) qui qualifie un ticket depuis la file d'attente n'a
que deux issues :
  1. le prendre pour SON propre traitement (assignee_id = lui-meme) ;
  2. l'envoyer a un chef de division support (CDS) de SON service.

Tout le reste est refuse (technicien, chef-departement, director, un autre chef
de service, ou un CDS d'un autre service). L'admin n'est pas contraint.

Non-regression majeure : la chaine de transmission dynamique qui suit la sortie
de file d'attente (transmit_treatment, A -> An) reste libre — voir le dernier test.
"""
from __future__ import annotations

import pytest

from tests.api.test_requests_baseline import _ensure_test_account
from tests.api.test_transmit_treatment import _call_as, _create_ticket, _dep

_CSSHF_ID = 8500
_OTHER_UNITY_ID = 999


def _qualify_body(unity_id: int, assignee_id: int | str) -> dict:
    return {
        "category": "panne",
        "priority": "medium",
        "unit_id": str(unity_id),
        "assignee_id": str(assignee_id),
        # Procedure EDG/PS-GSI/Pro-02 tache 1.3 — point de controle obligatoire
        # a l'imputation vers un chef de division support. Ces tests portent sur
        # la regle de CIBLAGE, pas sur ce point de controle : on le renseigne
        # donc systematiquement pour ne tester qu'une chose a la fois (voir
        # test_proposed_solution.py pour le point de controle lui-meme).
        "proposed_solution": "Piste de resolution proposee par le chef de service.",
    }


# ── Issue 1 — le chef de service prend le ticket pour lui-meme ───────────────

async def test_chef_service_peut_prendre_le_ticket_pour_lui_meme(auth_client, unity_id):
    await _ensure_test_account(_CSSHF_ID, unity_id=unity_id, role="chief-service")
    request_id = await _create_ticket(auth_client, unity_id, "self-take")

    resp = await _call_as(
        _dep(_CSSHF_ID, "chief-service", unity_id), "POST",
        f"/api/v1/requests/{request_id}/qualify", _qualify_body(unity_id, _CSSHF_ID),
    )
    assert resp.status_code == 200, resp.text
    assert str(resp.json()["data"]["assignee_id"]) == str(_CSSHF_ID)


# ── Issue 2 — envoi a un CDS de son service ─────────────────────────────────

async def test_chef_service_peut_envoyer_a_un_cds_de_son_service(auth_client, unity_id):
    await _ensure_test_account(_CSSHF_ID, unity_id=unity_id, role="chief-service")
    await _ensure_test_account(8501, unity_id=unity_id, role="chef-division-support")
    request_id = await _create_ticket(auth_client, unity_id, "to-cds")

    resp = await _call_as(
        _dep(_CSSHF_ID, "chief-service", unity_id), "POST",
        f"/api/v1/requests/{request_id}/qualify", _qualify_body(unity_id, 8501),
    )
    assert resp.status_code == 200, resp.text
    # BR-DISTRIBUTION-001 — le CDS devient destinataire de DISTRIBUTION, pas traitant :
    # le ticket entre dans sa file "Distribution" sans responsable operationnel.
    # Le detail du comportement est couvert par test_distribution.py.
    from tests.conftest import _TestSession
    from api.models.ModelRequest import Request as RequestModel
    async with _TestSession() as session:
        row = await session.get(RequestModel, int(request_id))
    assert str(row.distributor_id) == "8501"
    assert row.assignee_id is None


# ── Refus — CDS d'un AUTRE service ──────────────────────────────────────────

async def test_chef_service_ne_peut_pas_envoyer_a_un_cds_d_un_autre_service(auth_client, unity_id):
    await _ensure_test_account(_CSSHF_ID, unity_id=unity_id, role="chief-service")
    await _ensure_test_account(8502, unity_id=_OTHER_UNITY_ID, role="chef-division-support")
    request_id = await _create_ticket(auth_client, unity_id, "cds-other-unit")

    resp = await _call_as(
        _dep(_CSSHF_ID, "chief-service", unity_id), "POST",
        f"/api/v1/requests/{request_id}/qualify", _qualify_body(unity_id, 8502),
    )
    assert resp.status_code == 403, resp.text


# ── Refus — tout autre role, meme dans son service ──────────────────────────

@pytest.mark.parametrize("target_role", ["technicien", "chief-departement", "director", "chief-service"])
async def test_chef_service_ne_peut_pas_envoyer_aux_autres_roles(auth_client, unity_id, target_role):
    await _ensure_test_account(_CSSHF_ID, unity_id=unity_id, role="chief-service")
    target_id = 8510 + ["technicien", "chief-departement", "director", "chief-service"].index(target_role)
    await _ensure_test_account(target_id, unity_id=unity_id, role=target_role)
    request_id = await _create_ticket(auth_client, unity_id, f"deny-{target_role}")

    resp = await _call_as(
        _dep(_CSSHF_ID, "chief-service", unity_id), "POST",
        f"/api/v1/requests/{request_id}/qualify", _qualify_body(unity_id, target_id),
    )
    assert resp.status_code == 403, resp.text


# ── L'admin reste non contraint (role bypass) ───────────────────────────────

async def test_admin_n_est_pas_contraint_par_la_regle(auth_client, unity_id):
    await _ensure_test_account(8520, unity_id=unity_id, role="technicien")
    request_id = await _create_ticket(auth_client, unity_id, "admin-free")

    resp = await _call_as(
        _dep(6, "admin", unity_id), "POST",
        f"/api/v1/requests/{request_id}/qualify", _qualify_body(unity_id, 8520),
    )
    assert resp.status_code == 200, resp.text
    assert str(resp.json()["data"]["assignee_id"]) == "8520"


# ── NON-REGRESSION — le workflow dynamique A -> An reste libre ──────────────

async def test_transmission_dynamique_reste_libre_apres_la_file_d_attente(auth_client, unity_id):
    """Une fois le ticket sorti de la file d'attente, la transmission entre
    intervenants n'est PAS restreinte par la regle ci-dessus : le chef de service
    peut transmettre a un technicien, qui peut transmettre plus loin."""
    await _ensure_test_account(_CSSHF_ID, unity_id=unity_id, role="chief-service")
    await _ensure_test_account(8530, unity_id=unity_id, role="technicien")
    await _ensure_test_account(8531, unity_id=unity_id, role="chef-division-support")
    request_id = await _create_ticket(auth_client, unity_id, "dynamic-chain")

    # Sortie de file d'attente : le chef de service prend le ticket (issue 1).
    resp = await _call_as(
        _dep(_CSSHF_ID, "chief-service", unity_id), "POST",
        f"/api/v1/requests/{request_id}/qualify", _qualify_body(unity_id, _CSSHF_ID),
    )
    assert resp.status_code == 200, resp.text

    # A -> B : le chef de service transmet a un TECHNICIEN (interdit depuis la
    # file d'attente, mais autorise ici — c'est tout l'enjeu de la non-regression).
    resp = await _call_as(
        _dep(_CSSHF_ID, "chief-service", unity_id), "POST",
        f"/api/v1/requests/{request_id}/transmit",
        {"to_user_id": "8530", "work_done": "Analyse initiale.", "reason": "Intervention technique."},
    )
    assert resp.status_code == 200, resp.text
    assert str(resp.json()["data"]["assignee_id"]) == "8530"

    # B -> C : le technicien transmet a son tour au CDS.
    resp = await _call_as(
        _dep(8530, "technicien", unity_id), "POST",
        f"/api/v1/requests/{request_id}/transmit",
        {"to_user_id": "8531", "work_done": "Diagnostic pose.", "reason": "Arbitrage CDS requis."},
    )
    assert resp.status_code == 200, resp.text
    assert str(resp.json()["data"]["assignee_id"]) == "8531"
