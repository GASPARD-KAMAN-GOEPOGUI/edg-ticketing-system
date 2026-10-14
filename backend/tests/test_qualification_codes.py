"""
Qualification d'un ticket — catégorie et priorité réellement enregistrées.

Le formulaire envoyait le LIBELLÉ (« Réseau ») là où le backend cherchait le
CODE (`reseau`) : faute de correspondance, `_translate_codes` retombait en
silence sur « autre » / « medium ». Désormais : code ou libellé exact acceptés,
valeur inconnue refusée — pour le chef de service (qualification) comme pour
le technicien (constat avec écart).
"""
from __future__ import annotations

import pytest
from sqlalchemy import select

from api.core.exceptions import BusinessException
from api.models.ModelAccount import Account
from api.models.ModelPriorityDefinition import PriorityDefinition
from api.models.ModelRequest import Request
from api.models.ModelRequestCategory import RequestCategory
from api.models.ModelRequestStatus import RequestStatus
from api.services.ServiceRequest import RequestService
from tests.support import TestSession


async def _seed() -> tuple[int, int]:
    """Retourne (id du ticket en triage, id du chef de service)."""
    async with TestSession() as s:
        statuses = {
            code: RequestStatus(code=code, label=code, sort_order=i)
            for i, code in enumerate(("new", "qualifying", "assigned", "in_progress"))
        }
        s.add_all(statuses.values())
        s.add_all([
            RequestCategory(code="autre", label="Autre", sort_order=1),
            RequestCategory(code="reseau", label="Réseau", sort_order=2),
            RequestCategory(code="materiel", label="Matériel", sort_order=3),
            PriorityDefinition(slug="medium", label="Moyenne", sort_order=1, color="blue"),
            PriorityDefinition(slug="high", label="Haute", sort_order=2, color="orange"),
            PriorityDefinition(slug="critical", label="Critique", sort_order=3, color="red"),
        ])
        chief = Account(name="Diallo", firstname="Mamadou", email="chef@edg.gn", role="chief-service",
                        account_status="active", status=True)
        requester = Account(name="Bah", firstname="Aissatou", email="user@edg.gn", role="user",
                            account_status="active", status=True)
        s.add_all([chief, requester])
        await s.flush()
        autre = (await s.execute(select(RequestCategory).where(RequestCategory.code == "autre"))).scalar_one()
        medium = (await s.execute(select(PriorityDefinition).where(PriorityDefinition.slug == "medium"))).scalar_one()
        req = Request(
            ref="EDG-26-00001", title="Pas de réseau", description="d", is_external=False, in_triage=True,
            request_status_id=statuses["new"].id, request_category_id=autre.id,
            priority_definition_id=medium.id, requester_id=requester.id,
        )
        s.add(req)
        await s.commit()
        return req.id, chief.id


async def _ticket(req_id: int) -> tuple[str, str]:
    async with TestSession() as s:
        req = (await s.execute(select(Request).where(Request.id == req_id))).scalar_one()
        return req.category, req.priority


async def _qualify(req_id: int, chief_id: int, data: dict) -> None:
    async with TestSession() as s:
        chief = (await s.execute(select(Account).where(Account.id == chief_id))).scalar_one()
        await RequestService(s).qualify_triage(
            str(req_id), data, actor_id=str(chief_id), actor_name="Mamadou Diallo",
            actor_role="chief-service", actor=chief,
        )
        await s.commit()


@pytest.mark.parametrize(("category", "priority", "expected"), [
    ("Réseau", "Haute", ("reseau", "high")),        # libellés (ce qu'envoyait le formulaire)
    ("materiel", "critical", ("materiel", "critical")),  # codes (ce qu'il envoie désormais)
    ("RÉSEAU", "haute", ("reseau", "high")),        # casse indifférente
])
async def test_chief_qualification_is_saved_on_the_ticket(category, priority, expected):
    req_id, chief_id = await _seed()
    await _qualify(req_id, chief_id, {"category": category, "priority": priority})
    assert await _ticket(req_id) == expected


@pytest.mark.parametrize("data", [{"category": "Inexistante"}, {"priority": "urgentissime"}])
async def test_unknown_value_is_refused_and_ticket_unchanged(data):
    req_id, chief_id = await _seed()
    with pytest.raises(BusinessException):
        await _qualify(req_id, chief_id, data)
    assert await _ticket(req_id) == ("autre", "medium")


async def test_technician_gap_requalifies_the_ticket():
    req_id, _ = await _seed()
    async with TestSession() as s:
        await RequestService(s).field_check(
            str(req_id), conformity="ecart", findings="Carte réseau HS",
            observed_category="Matériel", observed_priority="Critique",
            actor=None, actor_id="9", actor_name="Ibrahima Sow", actor_role="technicien",
        )
        await s.commit()
    assert await _ticket(req_id) == ("materiel", "critical")


async def test_technician_unknown_value_is_refused():
    req_id, _ = await _seed()
    async with TestSession() as s:
        with pytest.raises(BusinessException):
            await RequestService(s).field_check(
                str(req_id), conformity="ecart", findings="x", observed_category="Inexistante",
                actor=None, actor_id="9", actor_name="Ibrahima Sow", actor_role="technicien",
            )
    assert await _ticket(req_id) == ("autre", "medium")


async def test_chief_qualification_is_kept_after_technician_requalification():
    """La fiche affiche les deux qualifications : celle du chef de service est
    figée dans `infos` et survit à la requalification par le technicien."""
    req_id, chief_id = await _seed()
    await _qualify(req_id, chief_id, {"category": "Réseau", "priority": "Haute"})
    async with TestSession() as s:
        await RequestService(s).field_check(
            str(req_id), conformity="ecart", findings="Carte réseau HS",
            observed_category="materiel", observed_priority="critical",
            actor=None, actor_id="9", actor_name="Ibrahima Sow", actor_role="technicien",
        )
        await s.commit()
    async with TestSession() as s:
        req = (await s.execute(select(Request).where(Request.id == req_id))).scalar_one()
        assert (req.category, req.priority) == ("materiel", "critical")      # technicien
        assert req.infos["qualified_category"] == "reseau"                   # chef de service
        assert req.infos["qualified_priority"] == "high"
        assert req.infos["qualified_at"]
        assert req.infos["receiver_name"] == "Mamadou Diallo"
