"""
Compteurs de l'accueil `/app` (GET /requests/my-requests-stats).

Règle vérifiée : comptes par statut des tickets dont l'utilisateur est le
DEMANDEUR, calculés en SQL — sans plafond (l'ancien calcul côté client ne
voyait que les 100 premiers tickets), hors tickets supprimés, et jamais ceux
d'un autre compte.
"""
from __future__ import annotations

from datetime import datetime

from api.models.ModelPriorityDefinition import PriorityDefinition
from api.models.ModelRequest import Request
from api.models.ModelRequestCategory import RequestCategory
from api.models.ModelRequestStatus import RequestStatus
from tests.support import TestSession, bearer, login, make_account

_STATUSES = ["new", "in_progress", "resolved", "closed", "cancelled"]


async def _seed(rows: list[tuple[str, int, bool]]) -> None:
    """rows : (statut, requester_id, supprimé)."""
    async with TestSession() as s:
        statuses = {}
        for i, code in enumerate(_STATUSES):
            statuses[code] = RequestStatus(code=code, label=code, sort_order=i)
            s.add(statuses[code])
        prio = PriorityDefinition(slug="medium", label="Moyenne", sort_order=1, color="blue")
        cat = RequestCategory(code="incident", label="Incident", sort_order=1)
        s.add_all([prio, cat])
        await s.flush()
        for n, (status, requester, deleted) in enumerate(rows, start=1):
            s.add(Request(
                ref=f"EDG-26-{n:05d}", title=f"T{n}", description="d", is_external=False,
                request_status_id=statuses[status].id,
                priority_definition_id=prio.id, request_category_id=cat.id,
                requester_id=requester,
                deleted_at=datetime(2026, 1, 1) if deleted else None,
            ))
        await s.commit()


async def test_counts_only_my_requests_by_status_without_cap(client, central):
    me = await make_account(central, email="me@edg.gn", role="user", central_id=10)
    other = await make_account(central, email="other@edg.gn", role="user", central_id=11)
    rows = [("new", me, False)] * 120          # au-delà de l'ancien plafond de 100
    rows += [("resolved", me, False)] * 3
    rows += [("cancelled", me, False)] * 2
    rows += [("closed", me, True)]             # supprimé : exclu
    rows += [("in_progress", other, False)] * 5  # autre demandeur : exclu
    await _seed(rows)

    session = (await login(client, "me@edg.gn"))["body"]["data"]
    resp = await client.get("/api/v1/requests/my-requests-stats", headers=bearer(session["access_token"]))
    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["by_status"] == {"new": 120, "resolved": 3, "cancelled": 2}
    assert data["total"] == 125


async def test_requires_authentication(client, central):
    resp = await client.get("/api/v1/requests/my-requests-stats")
    assert resp.status_code == 401
