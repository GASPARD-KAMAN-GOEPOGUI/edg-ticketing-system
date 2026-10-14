"""
Statut « Qualifié » (`qualified`, rétabli le 2026-10-14) : un ticket que le chef
de service oriente vers un chef de division vient d'être QUALIFIÉ et attend sa
répartition. Il était laissé en « En qualification » (`qualifying`), trompeur.

  Nouvelle ─(orienté vers le chef de division)→ Qualifié ─(réparti)→ Assignée
"""
from __future__ import annotations

from sqlalchemy import select

from api.models.ModelAccount import Account
from api.models.ModelPriorityDefinition import PriorityDefinition
from api.models.ModelRequest import Request
from api.models.ModelRequestCategory import RequestCategory
from api.models.ModelRequestStatus import RequestStatus
from api.models.ModelUnity import Unity
from api.services.ServiceRequest import RequestService
from tests.support import TestSession


async def _seed() -> dict[str, int]:
    async with TestSession() as s:
        statuses = {
            code: RequestStatus(code=code, label=code, sort_order=i)
            for i, code in enumerate(("new", "qualifying", "qualified", "assigned", "in_progress"))
        }
        s.add_all(statuses.values())
        cat = RequestCategory(code="reseau", label="Réseau", sort_order=1)
        prio = PriorityDefinition(slug="high", label="Haute", sort_order=1, color="orange")
        division = Unity(label="Division Support", codename="DSU")
        s.add_all([cat, prio, division])
        await s.flush()
        chief = Account(name="Diallo", firstname="Mamadou", email="chef@edg.gn", role="chief-service",
                        account_status="active", status=True)
        cds = Account(name="Camara", firstname="Fatoumata", email="cds@edg.gn", role="chef-division-support",
                      unity_id=division.id, account_status="active", status=True)
        tech = Account(name="Sow", firstname="Ibrahima", email="tech@edg.gn", role="technicien",
                       unity_id=division.id, account_status="active", status=True)
        requester = Account(name="Bah", firstname="Aissatou", email="user@edg.gn", role="user",
                            account_status="active", status=True)
        s.add_all([chief, cds, tech, requester])
        await s.flush()
        req = Request(
            ref="EDG-26-00010", title="Pas de réseau", description="d", is_external=False, in_triage=True,
            request_status_id=statuses["new"].id, request_category_id=cat.id,
            priority_definition_id=prio.id, requester_id=requester.id,
        )
        s.add(req)
        await s.commit()
        return {"req": req.id, "chief": chief.id, "cds": cds.id, "tech": tech.id}


async def _account(session, account_id: int) -> Account:
    return (await session.execute(select(Account).where(Account.id == account_id))).scalar_one()


async def _status(req_id: int) -> str:
    async with TestSession() as s:
        return (await s.execute(select(Request).where(Request.id == req_id))).scalar_one().request_status


async def _orient_to_division_chief(ids: dict[str, int]) -> None:
    async with TestSession() as s:
        await RequestService(s).qualify_triage(
            str(ids["req"]), {"category": "reseau", "priority": "high", "assignee_id": ids["cds"]},
            actor_id=str(ids["chief"]), actor_name="Mamadou Diallo", actor_role="chief-service",
            actor=await _account(s, ids["chief"]),
        )
        await s.commit()


async def test_oriented_to_division_chief_is_qualified_and_in_his_distribution_queue():
    ids = await _seed()
    await _orient_to_division_chief(ids)
    assert await _status(ids["req"]) == "qualified"
    async with TestSession() as s:
        page = await RequestService(s).list_distribution(str(ids["cds"]))
    refs = [item.ref for item in page.items]
    assert refs == ["EDG-26-00010"]


async def test_distribution_to_technician_moves_to_assigned():
    ids = await _seed()
    await _orient_to_division_chief(ids)
    async with TestSession() as s:
        await RequestService(s).distribution_assign(
            str(ids["req"]), str(ids["tech"]), actor=await _account(s, ids["cds"]), actor_name="Fatoumata Camara",
        )
        await s.commit()
    assert await _status(ids["req"]) == "assigned"


async def test_qualification_without_target_stays_in_qualification():
    ids = await _seed()
    async with TestSession() as s:
        await RequestService(s).qualify_triage(
            str(ids["req"]), {"category": "reseau", "priority": "high"},
            actor_id=str(ids["chief"]), actor_name="Mamadou Diallo", actor_role="chief-service",
            actor=await _account(s, ids["chief"]),
        )
        await s.commit()
    assert await _status(ids["req"]) == "qualifying"


async def test_orientation_without_proposed_solution_is_accepted_by_the_api(client, central):
    """Solution proposée facultative depuis le 2026-10-14, y compris pour orienter
    vers un chef de division (l'API répondait 422)."""
    from tests.support import bearer, login, make_account

    ids = await _seed()
    chief_id = await make_account(central, email="chef.api@edg.gn", role="chief-service", central_id=501)
    async with TestSession() as s:
        chief = await _account(s, chief_id)
        cds = await _account(s, ids["cds"])
        chief.unity_id = cds.unity_id
        await s.commit()

    token = (await login(client, "chef.api@edg.gn"))["body"]["data"]["access_token"]
    resp = await client.post(
        f"/api/v1/requests/{ids['req']}/qualify",
        json={"category": "reseau", "priority": "high", "assignee_id": str(ids["cds"])},
        headers=bearer(token),
    )
    assert resp.status_code == 200, resp.text
    assert await _status(ids["req"]) == "qualified"
