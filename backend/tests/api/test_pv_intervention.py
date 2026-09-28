"""Procedure EDG/PS-GSI/Pro-02, tache 3.1 — PV d'intervention.

Formulaire officiel EDG/PS-GSI/PV-01 version 03. Le PV est la donnee de sortie
unique de la procedure (§3). Aucune donnee n'est collectee pour lui : tout vient
de ce que les blocs 1 et 2 ont deja fige.

Point de confidentialite verifie ici : le PV est remis au DEMANDEUR (c'est lui
qui valide le depannage, tache 3.2), il ne doit donc jamais porter
`proposed_solution`, piste interne du chef de service (tache 1.3).
"""
from __future__ import annotations

from tests.conftest import _TestSession
from tests.api.test_requests_baseline import _ensure_test_account
from tests.api.test_transmit_treatment import _call_as, _create_ticket, _dep

_CSSHF = 9900
_CDS = 9901
_TECH = 9902

_SOLUTION_INTERNE = "PisteInterneChefDeService"
_CONSTAT = "Onduleur hors service, poste intact."
_RESOLVE = {
    "summary": "Onduleur remplace",
    "solution": "Remplacement de l'onduleur defaillant",
    "work_done": "Depose, remplacement et test de charge",
    "recommendations": "Prevoir un contrat de maintenance",
}


async def _setup(unity_id: int) -> None:
    await _ensure_test_account(_CSSHF, unity_id=unity_id, role="chief-service")
    await _ensure_test_account(_CDS, unity_id=unity_id, role="chef-division-support")
    await _ensure_test_account(_TECH, unity_id=unity_id, role="technicien")


async def _set_status(account_id: int, status: str) -> None:
    from api.models.ModelAccount import Account
    async with _TestSession() as session:
        account = await session.get(Account, account_id)
        infos = dict(account.infos or {})
        infos["intervenant_status"] = status
        account.infos = infos
        await session.commit()


async def _full_cycle(auth_client, unity_id: int, suffix: str) -> str:
    """Parcours complet : creation -> qualification/imputation -> affectation
    au technicien -> constat -> resolution."""
    request_id = await _create_ticket(auth_client, unity_id, suffix)
    qualify = await _call_as(
        _dep(_CSSHF, "chief-service", unity_id), "POST",
        f"/api/v1/requests/{request_id}/qualify",
        {"category": "panne", "priority": "medium", "unit_id": str(unity_id),
         "assignee_id": str(_CDS), "proposed_solution": _SOLUTION_INTERNE},
    )
    assert qualify.status_code == 200, qualify.text
    assign = await _call_as(
        _dep(_CDS, "chef-division-support", unity_id), "POST",
        f"/api/v1/requests/{request_id}/distribution/assign",
        {"technician_id": str(_TECH)},
    )
    assert assign.status_code == 200, assign.text
    fc = await _call_as(
        _dep(_TECH, "technicien", unity_id), "POST",
        f"/api/v1/requests/{request_id}/field-check",
        {"conformity": "conforme", "findings": _CONSTAT},
    )
    assert fc.status_code == 200, fc.text
    # BR-TRAITEMENT-PROGRESSIF-001 — le traitement ne demarre plus a
    # l'affectation : il faut le geste explicite du technicien, qui fixe le lieu
    # et l'horodatage de debut repris par le PV.
    started = await _call_as(
        _dep(_TECH, "technicien", unity_id), "POST",
        f"/api/v1/requests/{request_id}/start-treatment",
        {"location": "Siege EDG - bureau 312"},
    )
    assert started.status_code == 200, started.text
    resolved = await _call_as(
        _dep(_TECH, "technicien", unity_id), "POST",
        f"/api/v1/requests/{request_id}/resolve", _RESOLVE,
    )
    assert resolved.status_code == 200, resolved.text
    return request_id


async def _pv_bytes(request_id: str, unity_id: int, actor=None):
    dep = actor or _dep(_TECH, "technicien", unity_id)
    return await _call_as(dep, "GET", f"/api/v1/requests/{request_id}/pv")


# ── Generation ───────────────────────────────────────────────────────────────

async def test_le_pv_est_genere_en_pdf(auth_client, unity_id):
    await _setup(unity_id)
    request_id = await _full_cycle(auth_client, unity_id, "pv-ok")

    resp = await _pv_bytes(request_id, unity_id)

    assert resp.status_code == 200, resp.text
    assert resp.content[:4] == b"%PDF", "le corps n'est pas un PDF"
    assert len(resp.content) > 1000, "PDF suspicieusement petit"
    assert "pdf" in resp.headers.get("content-type", "").lower()


async def test_le_nom_du_fichier_porte_la_reference(auth_client, unity_id):
    await _setup(unity_id)
    request_id = await _full_cycle(auth_client, unity_id, "pv-nom")

    resp = await _pv_bytes(request_id, unity_id)

    disposition = resp.headers.get("content-disposition", "")
    assert "PV_" in disposition, disposition


async def test_pv_disponible_avant_resolution(auth_client, unity_id):
    """Un ticket non encore resolu doit produire un PV vierge exploitable, pas
    une erreur : le technicien peut vouloir l'imprimer avant d'intervenir."""
    await _setup(unity_id)
    request_id = await _create_ticket(auth_client, unity_id, "pv-vierge")

    resp = await _pv_bytes(request_id, unity_id, actor=_dep(_CSSHF, "chief-service", unity_id))

    assert resp.status_code == 200, resp.text
    assert resp.content[:4] == b"%PDF"


# ── Confidentialite ──────────────────────────────────────────────────────────

async def test_le_pv_ne_contient_jamais_la_solution_proposee(auth_client, unity_id):
    """Verrou : le PV est remis au demandeur, la piste interne du chef de
    service ne doit pas s'y trouver."""
    await _setup(unity_id)
    request_id = await _full_cycle(auth_client, unity_id, "pv-confid")

    resp = await _pv_bytes(request_id, unity_id)

    assert resp.status_code == 200, resp.text
    assert _SOLUTION_INTERNE.encode() not in resp.content


async def test_le_demandeur_peut_telecharger_son_pv(auth_client, unity_id):
    """Tache 3.2 — c'est le demandeur qui valide le depannage et signe le PV."""
    await _setup(unity_id)
    request_id = await _full_cycle(auth_client, unity_id, "pv-demandeur")

    async with auth_client("user") as client:
        resp = await client.get(f"/api/v1/requests/{request_id}/pv")

    assert resp.status_code == 200, resp.text
    assert resp.content[:4] == b"%PDF"
    assert _SOLUTION_INTERNE.encode() not in resp.content


async def test_un_tiers_sans_acces_au_ticket_est_refuse(auth_client, unity_id):
    """La visibilite du PV est celle du ticket, pas plus large."""
    await _setup(unity_id)
    request_id = await _full_cycle(auth_client, unity_id, "pv-tiers")

    from tests.conftest import MOCK_OTHER_USER
    from api.main import app
    from api.dependencies import get_current_user

    app.dependency_overrides[get_current_user] = lambda: MOCK_OTHER_USER
    try:
        from httpx import AsyncClient, ASGITransport
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get(f"/api/v1/requests/{request_id}/pv")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code in (403, 404), resp.text


# ── Contenu ──────────────────────────────────────────────────────────────────

async def test_le_statut_de_l_intervenant_est_fige_dans_le_pv(auth_client, unity_id):
    """Le statut coche sur le PV est celui du jour de l'intervention : le
    modifier apres coup ne doit pas reecrire un PV deja produit."""
    await _setup(unity_id)
    await _set_status(_TECH, "stagiaire")
    request_id = await _full_cycle(auth_client, unity_id, "pv-statut")

    from api.models.ModelRequest import Request as RequestModel
    async with _TestSession() as session:
        obj = await session.get(RequestModel, int(request_id))
        interventions = obj.interventions
    assert interventions, "aucune intervention reconstruite"
    assert interventions[-1]["actor_status"] == "stagiaire"

    # Le technicien devient titulaire APRES coup.
    await _set_status(_TECH, "titulaire")
    async with _TestSession() as session:
        obj = await session.get(RequestModel, int(request_id))
        interventions = obj.interventions
    assert interventions[-1]["actor_status"] == "stagiaire", \
        "le statut a suivi la mutation du compte"


async def test_le_responsable_de_reception_est_fige(auth_client, unity_id):
    """Bloc « Reception » du PV : le chef de service qui qualifie n'ouvre aucune
    intervention quand il impute a un CDS — son identite doit donc etre figee a
    la qualification, sans quoi le PV ne pourrait pas la restituer."""
    await _setup(unity_id)
    request_id = await _full_cycle(auth_client, unity_id, "pv-receveur")

    from api.models.ModelRequest import Request as RequestModel
    async with _TestSession() as session:
        obj = await session.get(RequestModel, int(request_id))
        infos = obj.infos or {}
    assert infos.get("receiver_id") == str(_CSSHF), infos


# ── Taches 3.3 et 3.4 — circuit du PV ────────────────────────────────────────

async def _submit(request_id: str, unity_id: int, actor=None):
    dep = actor or _dep(_TECH, "technicien", unity_id)
    return await _call_as(dep, "POST", f"/api/v1/requests/{request_id}/pv/submit", {})


async def _archive(request_id: str, unity_id: int, actor=None):
    dep = actor or _dep(_CDS, "chef-division-support", unity_id)
    return await _call_as(dep, "POST", f"/api/v1/requests/{request_id}/pv/archive", {})


async def _infos(request_id: str) -> dict:
    from api.models.ModelRequest import Request as RequestModel
    async with _TestSession() as session:
        obj = await session.get(RequestModel, int(request_id))
        return obj.infos or {}


async def test_3_3_le_technicien_soumet_le_pv_au_chef_de_division(auth_client, unity_id):
    await _setup(unity_id)
    request_id = await _full_cycle(auth_client, unity_id, "pv-submit")
    assert (await _validate(auth_client, request_id)).status_code == 201

    resp = await _submit(request_id, unity_id)

    assert resp.status_code == 200, resp.text
    assert (await _infos(request_id)).get("pv_submitted_at")


async def test_3_3_soumission_refusee_avant_resolution(auth_client, unity_id):
    """La tache 3.3 vient apres la 2.2 : pas de PV sans traitement termine."""
    await _setup(unity_id)
    request_id = await _create_ticket(auth_client, unity_id, "pv-submit-tot")

    resp = await _submit(request_id, unity_id)

    assert resp.status_code in (400, 403), resp.text


async def test_3_3_un_autre_intervenant_ne_peut_pas_soumettre(auth_client, unity_id):
    await _setup(unity_id)
    await _ensure_test_account(9903, unity_id=unity_id, role="technicien")
    request_id = await _full_cycle(auth_client, unity_id, "pv-submit-autre")

    resp = await _submit(request_id, unity_id, actor=_dep(9903, "technicien", unity_id))

    assert resp.status_code == 403, resp.text


async def test_3_4_le_chef_de_division_archive_le_pv(auth_client, unity_id):
    await _setup(unity_id)
    request_id = await _full_cycle(auth_client, unity_id, "pv-archive")
    assert (await _validate(auth_client, request_id)).status_code == 201
    assert (await _submit(request_id, unity_id)).status_code == 200

    resp = await _archive(request_id, unity_id)

    assert resp.status_code == 200, resp.text
    assert (await _infos(request_id)).get("pv_archived_at")


async def test_3_4_archivage_refuse_si_le_pv_n_a_pas_ete_soumis(auth_client, unity_id):
    """La tache 3.3 precede la 3.4."""
    await _setup(unity_id)
    request_id = await _full_cycle(auth_client, unity_id, "pv-archive-tot")

    resp = await _archive(request_id, unity_id)

    assert resp.status_code == 400, resp.text


async def test_3_4_un_autre_chef_de_division_ne_peut_pas_archiver(auth_client, unity_id):
    """Seul le CDS qui a REPARTI le ticket archive son PV."""
    await _setup(unity_id)
    await _ensure_test_account(9904, unity_id=unity_id, role="chef-division-support")
    request_id = await _full_cycle(auth_client, unity_id, "pv-archive-autre")
    assert (await _validate(auth_client, request_id)).status_code == 201
    assert (await _submit(request_id, unity_id)).status_code == 200

    resp = await _archive(request_id, unity_id,
                          actor=_dep(9904, "chef-division-support", unity_id))

    assert resp.status_code == 403, resp.text


async def test_tsi_suit_les_tickets_repartis_jusqu_a_l_archivage(auth_client, unity_id):
    """Le TSI (livrable 3.4) suit le ticket APRES sa sortie de la file
    Distribution — contrairement a cette derniere, qui ne montre que ce qui
    reste a repartir."""
    await _setup(unity_id)
    request_id = await _full_cycle(auth_client, unity_id, "pv-tsi")
    assert (await _validate(auth_client, request_id)).status_code == 201
    assert (await _submit(request_id, unity_id)).status_code == 200

    resp = await _call_as(
        _dep(_CDS, "chef-division-support", unity_id), "GET",
        "/api/v1/requests/pv-tracking",
    )

    assert resp.status_code == 200, resp.text
    items = resp.json()["data"]["items"]
    row = next((i for i in items if str(i["id"]) == str(request_id)), None)
    assert row is not None, "le ticket reparti doit figurer au TSI"
    assert row["pv_submitted_at"], row
    assert row["pv_archived_at"] is None
    assert row["intervenant_badge"], "le TSI doit nommer l'intervenant"

    # Le ticket a bien quitte la file Distribution, lui.
    distribution = await _call_as(
        _dep(_CDS, "chef-division-support", unity_id), "GET",
        "/api/v1/requests/distribution",
    )
    ids = [str(i["id"]) for i in distribution.json()["data"]["items"]]
    assert str(request_id) not in ids


async def test_tsi_refuse_aux_roles_non_autorises(auth_client, unity_id):
    await _setup(unity_id)

    resp = await _call_as(
        _dep(_TECH, "technicien", unity_id), "GET", "/api/v1/requests/pv-tracking",
    )

    assert resp.status_code == 403, resp.text


# ── Tache 3.2 — validation du depannage par le demandeur ─────────────────────

async def _validate(auth_client, request_id: str, *, confirmed: bool = True, rating: int = 5):
    """Le demandeur valide (ou conteste) via son appreciation — la tache 3.2 ne
    cree pas une seconde validation, elle reutilise celle-ci."""
    async with auth_client("user") as client:
        return await client.post(
            f"/api/v1/requests/{request_id}/appreciation",
            json={"rating": rating, "comment": "Intervention conforme.",
                  "resolved_confirmed": confirmed},
        )


async def test_3_2_la_validation_du_demandeur_alimente_le_circuit_du_pv(auth_client, unity_id):
    await _setup(unity_id)
    request_id = await _full_cycle(auth_client, unity_id, "pv-valide")

    resp = await _validate(auth_client, request_id)

    assert resp.status_code == 201, resp.text
    assert (await _infos(request_id)).get("pv_validated_at")


async def test_3_3_soumission_refusee_sans_validation_du_demandeur(auth_client, unity_id):
    """La tache 3.2 precede la 3.3 : on ne soumet pas un PV non valide."""
    await _setup(unity_id)
    request_id = await _full_cycle(auth_client, unity_id, "pv-sans-validation")

    resp = await _submit(request_id, unity_id)

    assert resp.status_code == 400, resp.text
    assert "valid" in resp.text.lower()


async def test_3_3_soumission_acceptee_apres_validation(auth_client, unity_id):
    await _setup(unity_id)
    request_id = await _full_cycle(auth_client, unity_id, "pv-apres-validation")
    assert (await _validate(auth_client, request_id)).status_code == 201

    resp = await _submit(request_id, unity_id)

    assert resp.status_code == 200, resp.text


async def test_3_2_contestation_reinitialise_le_circuit_du_pv(auth_client, unity_id):
    """Le demandeur conteste : le ticket est rouvert et le PV de l'intervention
    precedente ne vaut plus — celle qui suivra devra produire le sien."""
    await _setup(unity_id)
    request_id = await _full_cycle(auth_client, unity_id, "pv-conteste")

    resp = await _validate(auth_client, request_id, confirmed=False, rating=2)

    assert resp.status_code == 201, resp.text
    infos = await _infos(request_id)
    assert not infos.get("pv_validated_at")
    assert not infos.get("pv_submitted_at")


async def test_le_circuit_complet_apparait_au_journal(auth_client, unity_id):
    """Les quatre etapes du bloc 3 doivent etre lisibles dans le journal."""
    await _setup(unity_id)
    request_id = await _full_cycle(auth_client, unity_id, "pv-journal-complet")
    assert (await _validate(auth_client, request_id)).status_code == 201
    assert (await _submit(request_id, unity_id)).status_code == 200
    assert (await _archive(request_id, unity_id)).status_code == 200

    from sqlalchemy import select
    from api.models.ModelWorkflow import Workflow
    from api.models.ModelWorkflowDetail import WorkflowDetail
    async with _TestSession() as session:
        rows = await session.execute(
            select(WorkflowDetail.event_type)
            .join(Workflow, WorkflowDetail.workflow_id == Workflow.id)
            .where(Workflow.request_id == int(request_id))
        )
        types = [r[0] for r in rows.all()]

    for step in ("field_check", "treatment_completed", "pv_validated",
                 "pv_submitted", "pv_archived"):
        assert step in types, f"{step} absent du journal : {types}"
