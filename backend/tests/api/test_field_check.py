"""Procedure EDG/PS-GSI/Pro-02, tache 2.1 — constat d'intervention.

« Qualifier la demande », point de controle « verification de l'etat reel de la
requete ». L'intervenant confronte ce qu'il trouve a ce qui a ete decrit, AVANT
d'intervenir — la tache 2.1 precede la 2.2 (« resoudre le probleme »).

A ne pas confondre avec la qualification du chef de service (taches 1.2/1.3),
reservee a la File d'attente : celle-la oriente le ticket sur piece, celle-ci
constate sur le terrain. Les deux coexistent.

Aucune table ni colonne : un evenement `field_check` du `workflow_detail`,
rattache a l'INTERVENTION en cours (pas au ticket), donc refait par chaque
nouvel intervenant apres une transmission.
"""
from __future__ import annotations

from tests.conftest import _TestSession
from tests.api.test_requests_baseline import _ensure_test_account
from tests.api.test_transmit_treatment import _call_as, _create_ticket, _dep

_CSSHF = 9800
_CDS = 9801
_TECH = 9802
_TECH_2 = 9803

_SOLUTION = "Piste proposee par le chef de service."
_FINDINGS = "Le poste demarre normalement ; c'est l'onduleur qui est hors service."

_RESOLVE_BODY = {
    "summary": "Onduleur remplace",
    "solution": "Remplacement de l'onduleur defaillant",
    "work_done": "Depose, remplacement et test de charge",
}


async def _setup(unity_id: int) -> None:
    await _ensure_test_account(_CSSHF, unity_id=unity_id, role="chief-service")
    await _ensure_test_account(_CDS, unity_id=unity_id, role="chef-division-support")
    await _ensure_test_account(_TECH, unity_id=unity_id, role="technicien")
    await _ensure_test_account(_TECH_2, unity_id=unity_id, role="technicien")


async def _ticket_assigned_to_technician(auth_client, unity_id: int, suffix: str) -> str:
    """Parcours reel : creation -> qualification/imputation au CDS -> affectation
    au technicien. C'est cette affectation qui ouvre l'intervention, donc qui
    pose le drapeau `field_check_required`."""
    request_id = await _create_ticket(auth_client, unity_id, suffix)
    qualify = await _call_as(
        _dep(_CSSHF, "chief-service", unity_id), "POST",
        f"/api/v1/requests/{request_id}/qualify",
        {"category": "panne", "priority": "medium", "unit_id": str(unity_id),
         "assignee_id": str(_CDS), "proposed_solution": _SOLUTION},
    )
    assert qualify.status_code == 200, qualify.text
    assign = await _call_as(
        _dep(_CDS, "chef-division-support", unity_id), "POST",
        f"/api/v1/requests/{request_id}/distribution/assign",
        {"technician_id": str(_TECH)},
    )
    assert assign.status_code == 200, assign.text
    return request_id


async def _field_check(actor_id: int, unity_id: int, request_id: str, **body):
    payload = {"conformity": "conforme", "findings": _FINDINGS, **body}
    return await _call_as(
        _dep(actor_id, "technicien", unity_id), "POST",
        f"/api/v1/requests/{request_id}/field-check", payload,
    )


async def _start(actor_id: int, unity_id: int, request_id: str):
    """BR-TRAITEMENT-PROGRESSIF-001 — le traitement ne demarre plus a
    l'assignation ; il faut ce geste avant de pouvoir terminer."""
    return await _call_as(
        _dep(actor_id, "technicien", unity_id), "POST",
        f"/api/v1/requests/{request_id}/start-treatment", {"location": "Site EDG"},
    )


async def _resolve(actor_id: int, unity_id: int, request_id: str):
    return await _call_as(
        _dep(actor_id, "technicien", unity_id), "POST",
        f"/api/v1/requests/{request_id}/resolve", _RESOLVE_BODY,
    )


async def _events(request_id: str) -> list:
    from sqlalchemy import select
    from api.models.ModelWorkflow import Workflow
    from api.models.ModelWorkflowDetail import WorkflowDetail
    async with _TestSession() as session:
        rows = await session.execute(
            select(WorkflowDetail)
            .join(Workflow, WorkflowDetail.workflow_id == Workflow.id)
            .where(Workflow.request_id == int(request_id))
        )
        return list(rows.scalars().all())


# ── L'enchainement 2.1 -> 2.2 ────────────────────────────────────────────────

async def test_resolution_refusee_sans_constat(auth_client, unity_id):
    """Coeur de la regle : on ne resout pas sans avoir constate."""
    await _setup(unity_id)
    request_id = await _ticket_assigned_to_technician(auth_client, unity_id, "fc-sans")

    resp = await _resolve(_TECH, unity_id, request_id)

    assert resp.status_code == 400, resp.text
    assert "constat" in resp.text.lower()


async def test_resolution_acceptee_apres_constat(auth_client, unity_id):
    await _setup(unity_id)
    request_id = await _ticket_assigned_to_technician(auth_client, unity_id, "fc-avec")

    assert (await _field_check(_TECH, unity_id, request_id)).status_code == 200
    assert (await _start(_TECH, unity_id, request_id)).status_code == 200
    resp = await _resolve(_TECH, unity_id, request_id)

    assert resp.status_code == 200, resp.text


async def test_le_constat_est_journalise(auth_client, unity_id):
    await _setup(unity_id)
    request_id = await _ticket_assigned_to_technician(auth_client, unity_id, "fc-journal")

    assert (await _field_check(_TECH, unity_id, request_id)).status_code == 200

    events = [e for e in await _events(request_id) if e.event_type == "field_check"]
    assert len(events) == 1
    infos = events[0].infos or {}
    assert infos["conformity"] == "conforme"
    assert infos["findings"] == _FINDINGS
    # Rattache a l'intervention, pas seulement au ticket.
    assert infos.get("intervention_id")


# ── Validation d'entree ──────────────────────────────────────────────────────

async def test_constat_vide_refuse(auth_client, unity_id):
    await _setup(unity_id)
    request_id = await _ticket_assigned_to_technician(auth_client, unity_id, "fc-vide")

    resp = await _field_check(_TECH, unity_id, request_id, findings="   ")

    assert resp.status_code == 400, resp.text


async def test_conformite_invalide_refusee(auth_client, unity_id):
    await _setup(unity_id)
    request_id = await _ticket_assigned_to_technician(auth_client, unity_id, "fc-conf")

    resp = await _field_check(_TECH, unity_id, request_id, conformity="peut-etre")

    assert resp.status_code == 400, resp.text


# ── Qui peut constater ───────────────────────────────────────────────────────

async def test_seul_l_intervenant_en_cours_peut_constater(auth_client, unity_id):
    """Ce n'est pas un rôle qui constate, c'est celui qui detient le ticket."""
    await _setup(unity_id)
    request_id = await _ticket_assigned_to_technician(auth_client, unity_id, "fc-autre")

    resp = await _field_check(_TECH_2, unity_id, request_id)

    assert resp.status_code == 403, resp.text


async def test_le_demandeur_ne_peut_pas_constater(auth_client, unity_id):
    await _setup(unity_id)
    request_id = await _ticket_assigned_to_technician(auth_client, unity_id, "fc-demandeur")

    async with auth_client("user") as client:
        resp = await client.post(
            f"/api/v1/requests/{request_id}/field-check",
            json={"conformity": "conforme", "findings": _FINDINGS},
        )

    assert resp.status_code in (401, 403), resp.text


# ── Ecart constate ───────────────────────────────────────────────────────────

async def test_ecart_notifie_le_chef_de_service(auth_client, unity_id):
    """L'ecart remet en cause la qualification, qui appartient au CSSHF."""
    from sqlalchemy import select
    from api.models.ModelNotification import Notification

    await _setup(unity_id)
    request_id = await _ticket_assigned_to_technician(auth_client, unity_id, "fc-ecart")

    resp = await _field_check(
        _TECH, unity_id, request_id, conformity="ecart",
        findings="L'equipement decrit n'est pas celui trouve sur place.",
        observed_category="materiel", observed_priority="high",
    )
    assert resp.status_code == 200, resp.text

    async with _TestSession() as session:
        rows = await session.execute(
            select(Notification).where(Notification.recipient_id == _CSSHF)
        )
        titles = [n.title for n in rows.scalars().all()]
    assert any("cart" in t for t in titles), titles


async def test_categorie_et_priorite_observees_sont_consignees(auth_client, unity_id):
    await _setup(unity_id)
    request_id = await _ticket_assigned_to_technician(auth_client, unity_id, "fc-observe")

    assert (await _field_check(
        _TECH, unity_id, request_id, conformity="ecart",
        findings="Panne plus grave que decrite.",
        observed_category="materiel", observed_priority="critical",
    )).status_code == 200

    infos = [e for e in await _events(request_id) if e.event_type == "field_check"][0].infos or {}
    assert infos["observed_category"] == "materiel"
    assert infos["observed_priority"] == "critical"


async def test_un_constat_conforme_ne_notifie_pas(auth_client, unity_id):
    from sqlalchemy import select
    from api.models.ModelNotification import Notification

    await _setup(unity_id)
    request_id = await _ticket_assigned_to_technician(auth_client, unity_id, "fc-conforme-silence")

    async with _TestSession() as session:
        before = len((await session.execute(
            select(Notification).where(Notification.recipient_id == _CSSHF)
        )).scalars().all())

    assert (await _field_check(_TECH, unity_id, request_id)).status_code == 200

    async with _TestSession() as session:
        after = len((await session.execute(
            select(Notification).where(Notification.recipient_id == _CSSHF)
        )).scalars().all())
    assert after == before, "un constat conforme ne doit alerter personne"


# ── Visibilite demandeur ─────────────────────────────────────────────────────

async def test_le_demandeur_voit_le_constat_dans_le_journal(auth_client, unity_id):
    """Contrairement a la solution proposee (interne), le constat est un fait
    etabli sur le materiel du demandeur : il le voit."""
    await _setup(unity_id)
    request_id = await _ticket_assigned_to_technician(auth_client, unity_id, "fc-visible")
    assert (await _field_check(_TECH, unity_id, request_id)).status_code == 200

    async with auth_client("user") as client:
        resp = await client.get(f"/api/v1/requests/{request_id}")

    assert resp.status_code == 200, resp.text
    types = [e["event_type"] for e in resp.json()["data"]["timelines"]]
    assert "field_check" in types


# ── Non-regression : interventions anterieures a la regle ───────────────────

async def test_intervention_sans_drapeau_reste_resolvable(auth_client, unity_id):
    """Les interventions ouvertes AVANT la mise en service de la regle ne
    portent pas `field_check_required` : elles doivent rester resolvables, sans
    quoi des tickets en cours seraient bloques du jour au lendemain."""
    from api.models.ModelRequest import Request as RequestModel

    await _setup(unity_id)
    request_id = await _ticket_assigned_to_technician(auth_client, unity_id, "fc-legacy")

    # On retire le drapeau pour simuler une intervention anterieure.
    async with _TestSession() as session:
        obj = await session.get(RequestModel, int(request_id))
        infos = dict(obj.infos or {})
        infos.pop("field_check_required", None)
        obj.infos = infos
        await session.commit()

    # Sans le drapeau, le demarrage passe sans constat prealable.
    assert (await _start(_TECH, unity_id, request_id)).status_code == 200
    resp = await _resolve(_TECH, unity_id, request_id)

    assert resp.status_code == 200, resp.text


# ── Le constat appartient a l'intervention, pas au ticket ────────────────────

async def test_apres_transmission_le_suivant_refait_son_constat(auth_client, unity_id):
    """Le constat de l'intervenant precedent ne vaut pas pour le suivant : il
    doit verifier l'etat reel par lui-meme avant de resoudre."""
    await _setup(unity_id)
    request_id = await _ticket_assigned_to_technician(auth_client, unity_id, "fc-transmis")
    assert (await _field_check(_TECH, unity_id, request_id)).status_code == 200
    assert (await _start(_TECH, unity_id, request_id)).status_code == 200

    transmit = await _call_as(
        _dep(_TECH, "technicien", unity_id), "POST",
        f"/api/v1/requests/{request_id}/transmit",
        {"to_user_id": str(_TECH_2), "work_done": "Diagnostic initial pose.",
         "reason": "Competence reseau requise."},
    )
    assert transmit.status_code == 200, transmit.text

    # Le nouvel intervenant herite du ticket mais pas du constat.
    blocked = await _resolve(_TECH_2, unity_id, request_id)
    assert blocked.status_code == 400, blocked.text

    assert (await _field_check(_TECH_2, unity_id, request_id)).status_code == 200
    assert (await _resolve(_TECH_2, unity_id, request_id)).status_code == 200
