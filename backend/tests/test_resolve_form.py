"""
Formulaire « Terminer le traitement » (2026-10-14) : seuls « Solution
appliquée » (obligatoire) et « Recommandations » (facultatif) restent ; le
résumé final et le travail réalisé ne sont plus exigés.
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
from api.models.ModelWorkflowDetail import WorkflowDetail
from api.routes.RouteRequest import ResolveBody
from api.services.ServiceRequest import RequestService
from tests.support import TestSession


async def _seed_in_progress() -> int:
    async with TestSession() as s:
        statuses = {
            code: RequestStatus(code=code, label=code, sort_order=i)
            for i, code in enumerate(("new", "assigned", "in_progress", "resolved"))
        }
        s.add_all(statuses.values())
        cat = RequestCategory(code="reseau", label="Réseau", sort_order=1)
        prio = PriorityDefinition(slug="high", label="Haute", sort_order=1, color="orange")
        requester = Account(name="Bah", firstname="Aissatou", email="user@edg.gn", role="user",
                            account_status="active", status=True)
        s.add_all([cat, prio, requester])
        await s.flush()
        req = Request(
            ref="EDG-26-00007", title="Pas de réseau", description="d", is_external=False,
            request_status_id=statuses["in_progress"].id, request_category_id=cat.id,
            priority_definition_id=prio.id, requester_id=requester.id,
        )
        s.add(req)
        await s.commit()
        return req.id


async def _resolve(req_id: int, **fields):
    async with TestSession() as s:
        await RequestService(s).resolve(
            str(req_id), actor=None, actor_id="5", actor_name="Mamadou Diallo", actor_role="admin", **fields,
        )
        await s.commit()


def test_api_body_requires_only_the_solution():
    body = ResolveBody(solution="Carte réseau remplacée")
    assert body.summary is None and body.work_done is None and body.recommendations is None
    with pytest.raises(Exception):
        ResolveBody()  # solution manquante


async def test_resolve_with_solution_and_recommendations_only():
    req_id = await _seed_in_progress()
    await _resolve(req_id, solution="Carte réseau remplacée", recommendations="Prévoir un onduleur")
    async with TestSession() as s:
        req = (await s.execute(select(Request).where(Request.id == req_id))).scalar_one()
        assert req.request_status == "resolved"
        event = (await s.execute(
            select(WorkflowDetail).where(WorkflowDetail.event_type == "treatment_completed")
        )).scalar_one()
        assert event.label == "Traitement terminé — Carte réseau remplacée"
        assert event.infos["solution"] == "Carte réseau remplacée"
        assert event.infos["recommendations"] == "Prévoir un onduleur"
        assert "work_done" not in event.infos and "summary" not in event.infos


async def test_resolve_without_solution_is_refused():
    req_id = await _seed_in_progress()
    with pytest.raises(BusinessException):
        await _resolve(req_id, solution="   ")
    async with TestSession() as s:
        req = (await s.execute(select(Request).where(Request.id == req_id))).scalar_one()
        assert req.request_status == "in_progress"
