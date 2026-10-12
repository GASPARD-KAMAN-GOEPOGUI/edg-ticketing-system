"""
KPIs de « Ma boîte de traitement » (GET /requests/my-kpis).

Règle vérifiée : chaque KPI est EXACTEMENT le total de la liste qu'il résume,
calculé depuis la base — jamais un compteur indépendant.
  - to_start + in_progress = Ma boîte (GET /requests/?assignee_id=moi&exclude_status=…)
  - resolved               = « Tickets résolus » (GET /requests/resolved-by-me)
  - transmitted            = « Tickets transmis » (GET /requests/transmitted)
  - retransmitted          = idem avec retransmitted_only=true (BR-RETRANSMIT-001 :
                             revenu à moi puis cédé de nouveau par moi)

Les événements de workflow sont écrits avec `WorkflowDetailRepository.create_event`
et les mêmes données que les services (assign, transmit_treatment, distribution),
pour éprouver la requête SQL sur la forme réelle du journal.
"""
from __future__ import annotations

from datetime import datetime

from api.models.ModelPriorityDefinition import PriorityDefinition
from api.models.ModelRequest import Request
from api.models.ModelRequestCategory import RequestCategory
from api.models.ModelRequestStatus import RequestStatus
from api.models.ModelWorkflow import Workflow
from api.repositories.RepositoryWorkflowDetail import WorkflowDetailRepository
from tests.support import TestSession, bearer, login, make_account

_STATUSES = [
    "new", "qualifying", "assigned", "in_progress", "reopened",
    "resolved", "closed", "cancelled", "rejected",
]
_TERMINAL = "resolved,closed,cancelled,rejected"


async def _seed_references() -> dict[str, int]:
    async with TestSession() as s:
        statuses = {}
        for i, code in enumerate(_STATUSES):
            row = RequestStatus(code=code, label=code, sort_order=i)
            s.add(row)
            statuses[code] = row
        prio = PriorityDefinition(slug="medium", label="Moyenne", sort_order=1, color="blue")
        cat = RequestCategory(code="incident", label="Incident", sort_order=1)
        s.add_all([prio, cat])
        await s.commit()
        return {
            "prio": prio.id,
            "cat": cat.id,
            **{f"st:{code}": row.id for code, row in statuses.items()},
        }


class _Builder:
    def __init__(self, refs: dict[str, int]) -> None:
        self.refs = refs
        self.seq = 0

    async def ticket(
        self, status: str, *, assignee: int | None, requester: int | None = None,
        deleted: bool = False,
    ) -> int:
        self.seq += 1
        async with TestSession() as s:
            req = Request(
                ref=f"EDG-26-{self.seq:05d}",
                title=f"Ticket {self.seq}",
                description="desc",
                is_external=False,
                request_status_id=self.refs[f"st:{status}"],
                priority_definition_id=self.refs["prio"],
                request_category_id=self.refs["cat"],
                assignee_id=assignee,
                requester_id=requester,
                deleted_at=datetime(2026, 1, 1) if deleted else None,
            )
            s.add(req)
            await s.flush()
            s.add(Workflow(request_id=req.id))
            await s.commit()
            return req.id

    async def event(self, request_id: int, data: dict) -> None:
        """Ajoute un événement au workflow du ticket, comme les services."""
        async with TestSession() as s:
            from sqlalchemy import select
            wf_id = (await s.execute(
                select(Workflow.id).where(Workflow.request_id == request_id)
            )).scalar_one()
            await WorkflowDetailRepository(s).create_event(
                {"workflow_id": wf_id, "activated": True, **data}, commit=False,
            )
            await s.commit()

    # ── Formes exactes écrites par ServiceRequest ────────────────────────────

    async def assign(self, rid: int, *, actor: int, dest: int, old: int | None) -> None:
        # assign() — `old_assignee_id` = traitant au moment de l'assignation.
        # _clean_infos retire les None : une assignation depuis la file d'attente
        # n'a donc PAS de clé old_assignee_id.
        infos = {"source_role": "chief-service", "new_assignee_id": dest}
        if old is not None:
            infos["old_assignee_id"] = old
        await self.event(rid, {
            "event_type": "assigned", "actor_id": str(actor), "dest_id": dest, "infos": infos,
        })

    async def transmit(self, rid: int, *, actor: int, dest: int, previous: int | None) -> None:
        # transmit_treatment() — `previous_assignee_id` = traitant qui transmet.
        await self.event(rid, {
            "event_type": "treatment_transmitted", "actor_id": str(actor), "dest_id": dest,
            "infos": {"previous_assignee_id": previous, "new_assignee_id": dest},
        })

    async def distribute(self, rid: int, *, actor: int, dest: int) -> None:
        # qualify_triage() vers un chef de division — _record_distribution_event.
        await self.event(rid, {
            "event_type": "distributed_to_division", "actor_id": str(actor), "dest_id": dest,
            "infos": {"source_role": "chief-service", "dest_role": "chef-division-support"},
        })


async def _token(client, email: str) -> str:
    res = await login(client, email)
    assert res["status"] == 200, res
    return res["body"]["data"]["access_token"]


async def _get(client, token: str, url: str) -> dict:
    resp = await client.get(f"/api/v1{url}", headers=bearer(token))
    assert resp.status_code == 200, resp.text
    return resp.json()["data"]


async def _setup(central):
    refs = await _seed_references()
    chief = await make_account(central, email="chef@edg.gn", role="chief-service", central_id=1)
    tech_a = await make_account(central, email="a@edg.gn", role="technicien", central_id=2)
    tech_b = await make_account(central, email="b@edg.gn", role="technicien", central_id=3)
    cds = await make_account(central, email="cds@edg.gn", role="chef-division-support", central_id=4)
    user = await make_account(central, email="u@edg.gn", role="user", central_id=5)
    return _Builder(refs), chief, tech_a, tech_b, cds, user


async def _scenario(b: _Builder, chief: int, tech_a: int, tech_b: int, cds: int, user: int) -> dict:
    """Construit la situation de référence du chef ; retourne les ids utiles."""
    ids: dict = {}
    # Ma boîte du chef
    ids["assigned"] = await b.ticket("assigned", assignee=chief, requester=user)
    ids["in_progress"] = await b.ticket("in_progress", assignee=chief, requester=user)
    ids["reopened"] = await b.ticket("reopened", assignee=chief, requester=user)
    # Résolus / clôturés : hors boîte, comptés dans Total résolus
    ids["resolved"] = await b.ticket("resolved", assignee=chief, requester=user)
    ids["closed"] = await b.ticket("closed", assignee=chief, requester=user)
    # Terminal non résolu : compté nulle part
    await b.ticket("cancelled", assignee=chief, requester=user)
    # Le chef est le demandeur : jamais dans sa boîte (BR-REQUESTER-NO-SELF-TREATMENT-001)
    await b.ticket("assigned", assignee=chief, requester=chief)
    # Supprimé (soft-delete) : compté nulle part
    await b.ticket("in_progress", assignee=chief, requester=user, deleted=True)

    # Auto-prise (« Prendre le ticket ») : pas une cession → boîte seulement
    t = await b.ticket("assigned", assignee=chief, requester=user)
    await b.assign(t, actor=chief, dest=chief, old=None)
    ids["self_taken"] = t

    # Assigné depuis la file d'attente à A : transmis, pas retransmis
    t = await b.ticket("assigned", assignee=tech_a, requester=user)
    await b.assign(t, actor=chief, dest=tech_a, old=None)
    ids["queue_assign"] = t

    # Correction de pilotage A -> B sans retour : transmis, PAS retransmis
    t = await b.ticket("assigned", assignee=tech_b, requester=user)
    await b.assign(t, actor=chief, dest=tech_a, old=None)
    await b.assign(t, actor=chief, dest=tech_b, old=tech_a)
    ids["correction"] = t

    # Vrai retour : chef -> A, A renvoie au chef, chef -> B : retransmis
    t = await b.ticket("in_progress", assignee=tech_b, requester=user)
    await b.assign(t, actor=chief, dest=tech_a, old=None)
    await b.transmit(t, actor=tech_a, dest=chief, previous=tech_a)
    await b.transmit(t, actor=chief, dest=tech_b, previous=chief)
    ids["returned"] = t

    # Transmis puis revenu au chef, toujours chez lui : boîte, PAS transmis
    t = await b.ticket("in_progress", assignee=chief, requester=user)
    await b.assign(t, actor=chief, dest=tech_a, old=None)
    await b.transmit(t, actor=tech_a, dest=chief, previous=tech_a)
    ids["back_home"] = t

    # Imputé au chef de division (file Distribution, pas de traitant) : transmis
    t = await b.ticket("qualifying", assignee=None, requester=user)
    await b.distribute(t, actor=chief, dest=cds)
    ids["distributed"] = t
    return ids


async def test_kpis_match_reality_and_their_lists(client, central):
    b, chief, tech_a, tech_b, cds, user = await _setup(central)
    await _scenario(b, chief, tech_a, tech_b, cds, user)
    token = await _token(client, "chef@edg.gn")

    kpis = await _get(client, token, "/requests/my-kpis")
    assert kpis == {
        "to_start": 3,       # assigned, reopened, self_taken
        "in_progress": 2,    # in_progress, back_home
        "resolved": 2,       # resolved, closed
        "transmitted": 4,    # queue_assign, correction, returned, distributed
        "retransmitted": 1,  # returned seulement
    }

    # Chaque KPI = total de la liste qu'il résume (aucune différence inexpliquée).
    box = await _get(
        client, token,
        f"/requests/?assignee_id={chief}&exclude_status={_TERMINAL}&limit=1000",
    )
    assert box["total"] == kpis["to_start"] + kpis["in_progress"]
    in_progress_items = [i for i in box["items"] if i["request_status"] == "in_progress"]
    assert len(in_progress_items) == kpis["in_progress"]

    resolved = await _get(client, token, "/requests/resolved-by-me")
    assert resolved["total"] == kpis["resolved"]

    transmitted = await _get(client, token, "/requests/transmitted")
    assert transmitted["total"] == kpis["transmitted"]

    retransmitted = await _get(client, token, "/requests/transmitted?retransmitted_only=true")
    assert retransmitted["total"] == kpis["retransmitted"]


async def test_no_ticket_is_counted_twice(client, central):
    b, chief, tech_a, tech_b, cds, user = await _setup(central)
    ids = await _scenario(b, chief, tech_a, tech_b, cds, user)
    token = await _token(client, "chef@edg.gn")

    box = await _get(
        client, token,
        f"/requests/?assignee_id={chief}&exclude_status={_TERMINAL}&limit=1000",
    )
    resolved = await _get(client, token, "/requests/resolved-by-me")
    transmitted = await _get(client, token, "/requests/transmitted")
    groups = [
        {int(i["id"]) for i in box["items"]},
        {int(i["id"]) for i in resolved["items"]},
        {int(i["id"]) for i in transmitted["items"]},
    ]
    # Ma boîte, Résolus et Transmis sont disjoints deux à deux.
    for i in range(3):
        for j in range(i + 1, 3):
            assert not (groups[i] & groups[j])
    # Un ticket revenu au chef quitte « Transmis » et compte dans sa boîte.
    assert ids["back_home"] in groups[0]
    assert ids["back_home"] not in groups[2]


async def test_kpis_follow_a_transition(client, central):
    """Une transition en base se reflète immédiatement : aucun état figé."""
    b, chief, tech_a, tech_b, cds, user = await _setup(central)
    t = await b.ticket("assigned", assignee=chief, requester=user)
    token = await _token(client, "chef@edg.gn")

    before = await _get(client, token, "/requests/my-kpis")
    assert (before["to_start"], before["in_progress"], before["transmitted"]) == (1, 0, 0)

    # Le chef transmet son ticket à A.
    await b.transmit(t, actor=chief, dest=tech_a, previous=chief)
    async with TestSession() as s:
        req = await s.get(Request, t)
        req.assignee_id = tech_a
        await s.commit()

    after = await _get(client, token, "/requests/my-kpis")
    assert (after["to_start"], after["in_progress"], after["transmitted"]) == (0, 0, 1)
    assert after["retransmitted"] == 0


async def test_kpis_are_scoped_to_the_authenticated_actor(client, central):
    b, chief, tech_a, tech_b, cds, user = await _setup(central)
    await _scenario(b, chief, tech_a, tech_b, cds, user)

    # Le technicien A voit SES compteurs : le ticket que le chef lui a assigné
    # depuis la file est dans sa boîte ; il a renvoyé deux tickets au chef
    # (l'un est reparti chez B, l'autre est resté chez le chef).
    token_a = await _token(client, "a@edg.gn")
    kpis_a = await _get(client, token_a, "/requests/my-kpis")
    assert kpis_a == {
        "to_start": 1, "in_progress": 0, "resolved": 0,
        "transmitted": 2, "retransmitted": 0,
    }
    transmitted_a = await _get(client, token_a, "/requests/transmitted")
    assert transmitted_a["total"] == kpis_a["transmitted"]

    # Le chef de division a l'accès (rôle de traitement), sans rien à compter.
    token_cds = await _token(client, "cds@edg.gn")
    assert (await _get(client, token_cds, "/requests/my-kpis"))["transmitted"] == 0

    # Un demandeur n'a pas de boîte de traitement.
    token_u = await _token(client, "u@edg.gn")
    resp = await client.get("/api/v1/requests/my-kpis", headers=bearer(token_u))
    assert resp.status_code == 403
