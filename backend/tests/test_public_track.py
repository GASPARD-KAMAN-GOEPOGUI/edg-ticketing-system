"""
Suivi public d'un ticket (GET /requests/track, sans connexion) :
  - accès par référence + e-mail ou téléphone du demandeur, téléphone reconnu
    quelle que soit son écriture (+224, 00224, local) ;
  - réponse réduite à ce que la page affiche : ni `infos`, ni interventions,
    ni organisation traitante, ni coordonnées ;
  - essais limités à 10 par minute et par adresse (références séquentielles,
    e-mails devinables).
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from api import dependencies
from api.main import app
from api.models.ModelAccount import Account
from api.models.ModelPriorityDefinition import PriorityDefinition
from api.models.ModelRequest import Request
from api.models.ModelRequestCategory import RequestCategory
from api.models.ModelRequestStatus import RequestStatus
from api.models.ModelWorkflow import Workflow
from api.models.ModelWorkflowDetail import WorkflowDetail
from tests.support import TestSession

REF = "EDG-26-00042"


def _client(peer: str) -> AsyncClient:
    # Une adresse par test : la limite d'essais est comptée par adresse.
    return AsyncClient(transport=ASGITransport(app=app, client=(peer, 40000)), base_url="http://test")


@pytest.fixture(autouse=True)
def _no_proxy(monkeypatch):
    monkeypatch.setattr(dependencies._env, "TRUSTED_PROXIES", [])


async def _seed() -> None:
    async with TestSession() as s:
        status = RequestStatus(code="closed", label="Clôturé", sort_order=1)
        prio = PriorityDefinition(slug="critical", label="Critique", sort_order=1, color="red")
        cat = RequestCategory(code="incident", label="Incident", sort_order=1)
        requester = Account(
            name="Goepogui", firstname="Gaspard", email="Gaspard@EDG.gn", phone="+224 626 11 11 11",
            role="user", account_status="active", status=True,
        )
        s.add_all([status, prio, cat, requester])
        await s.flush()
        req = Request(
            ref=REF, title="Mon ordinateur ne s'allume pas", description="Écran noir",
            is_external=False, request_status_id=status.id, priority_definition_id=prio.id,
            request_category_id=cat.id, requester_id=requester.id,
            infos={"receiver_name": "Chef interne", "distributor_name": "CDS interne"},
        )
        s.add(req)
        await s.flush()
        workflow = Workflow(request_id=req.id, workflow_status="open")
        s.add(workflow)
        await s.flush()
        s.add(WorkflowDetail(
            workflow_id=workflow.id, event_type="created", label="Ticket créé", actor_name="Gaspard Goepogui",
            activated=True, comment="note interne", infos={"secret": "interne"},
        ))
        await s.commit()


@pytest.mark.parametrize("credential", [
    {"email": "gaspard@edg.gn"},
    {"phone": "+224 626 11 11 11"},
    {"phone": "626111111"},
    {"phone": "00224 626 11 11 11"},
    {"phone": "224626111111"},
])
async def test_found_with_email_or_any_phone_writing(credential):
    await _seed()
    async with _client("203.0.113.80") as c:
        resp = await c.get("/api/v1/requests/track", params={"ref": REF.lower(), **credential})
    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["ref"] == REF


@pytest.mark.parametrize("credential", [
    {"email": "autre@edg.gn"},
    {"phone": "620000000"},
    {},
])
async def test_not_found_without_the_requester_contact(credential):
    await _seed()
    async with _client("203.0.113.81") as c:
        resp = await c.get("/api/v1/requests/track", params={"ref": REF, **credential})
    assert resp.status_code == 404


async def test_public_response_hides_internal_data():
    await _seed()
    async with _client("203.0.113.82") as c:
        data = (await c.get("/api/v1/requests/track", params={"ref": REF, "email": "gaspard@edg.gn"})).json()["data"]

    # Ce que la page affiche reste présent.
    assert data["title"] == "Mon ordinateur ne s'allume pas"
    assert data["description"] == "Écran noir"
    assert [e["label"] for e in data["timelines"]] == ["Ticket créé"]
    assert data["timelines"][0]["actor_name"] == "Gaspard Goepogui"
    # Le reste est retiré.
    assert data["infos"] is None
    assert data["interventions"] == [] and data["participant_avatars"] == {}
    for field in ("requester_email", "requester_phone", "assignee_name", "handler_service_label",
                  "distributor_id", "employee_matricule"):
        assert data[field] is None, field
    assert data["timelines"][0]["comment"] is None
    assert data["timelines"][0]["infos"] is None


async def test_attempts_limited_to_ten_per_minute():
    await _seed()
    async with _client("203.0.113.83") as c:
        codes = [
            (await c.get("/api/v1/requests/track", params={"ref": REF, "email": f"essai{i}@edg.gn"})).status_code
            for i in range(11)
        ]
    assert codes[:10] == [404] * 10
    assert codes[10] == 429
