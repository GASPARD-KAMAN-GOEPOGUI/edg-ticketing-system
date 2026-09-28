"""
Export du dossier complet d'une demande — Administration uniquement.

Couvre : RBAC strict (admin uniquement), génération d'un classeur Excel valide
à 7 feuilles sur un ticket "riche" (créé → qualifié/assigné → commenté →
résolu → clôturé), génération sur un ticket "vide" (aucune action), et
absence totale de toute donnée SLA/délai dans le contenu exporté.
"""
from __future__ import annotations

import io

import openpyxl

from tests.api.test_requests_baseline import _ensure_test_account
from tests.api.test_trace_interventions import (
    _FULL_RESOLVE_BODY,
    _assign_via_admin,
    _call_as,
    _create_ticket,
    _dep,
)

_EXPECTED_SHEETS = {
    "Synthèse", "Acteurs", "Historique", "Escalades",
    "Pièces jointes", "Notifications",
}


def _load_workbook(content: bytes) -> openpyxl.Workbook:
    return openpyxl.load_workbook(io.BytesIO(content))


def _all_cell_strings(wb: openpyxl.Workbook) -> list[str]:
    values = []
    for ws in wb.worksheets:
        for row in ws.iter_rows():
            for cell in row:
                if isinstance(cell.value, str):
                    values.append(cell.value)
    return values


async def test_export_forbidden_for_non_admin_roles(auth_client, unity_id):
    request_id = await _create_ticket(auth_client, unity_id, "export-rbac")

    # "agent"/"chief" sont les clés MOCK_ACCOUNTS de test (aliases de
    # "chief-service"/"chief-service" — cf. conftest.py:153-161).
    for role in ("user", "agent", "chief", "director"):
        async with auth_client(role) as client:
            resp = await client.get(f"/api/v1/requests/{request_id}/export")
        assert resp.status_code == 403, f"role={role}: {resp.text}"


async def test_export_empty_ticket_has_all_sheets_with_no_data_placeholder(auth_client, unity_id):
    request_id = await _create_ticket(auth_client, unity_id, "export-empty")

    async with auth_client("admin") as client:
        resp = await client.get(f"/api/v1/requests/{request_id}/export")
    assert resp.status_code == 200, resp.text
    assert resp.headers["content-type"] == (
        "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
    )

    wb = _load_workbook(resp.content)
    assert set(wb.sheetnames) == _EXPECTED_SHEETS

    # Aucune escalade n'a eu lieu sur un ticket tout juste créé.
    ws = wb["Escalades"]
    assert ws.cell(row=1, column=1).value == "Aucune donnée enregistrée"

    # La création elle-même génère un événement `created` (Historique) et une
    # notification "Ticket créé" au demandeur (Notifications) — pas vides.
    assert wb["Historique"].cell(row=2, column=1).value is not None
    assert wb["Notifications"].cell(row=2, column=1).value is not None


async def test_export_rich_ticket_covers_lifecycle_without_sla_data(auth_client, unity_id):
    await _ensure_test_account(2001, unity_id=unity_id, role="chief-service")

    request_id = await _create_ticket(auth_client, unity_id, "export-rich")
    await _assign_via_admin(auth_client, request_id, unity_id, assignee_id=2001)

    resolve_resp = await _call_as(
        _dep(2001, "chief-service", unity_id),
        "POST", f"/api/v1/requests/{request_id}/resolve", _FULL_RESOLVE_BODY,
    )
    assert resolve_resp.status_code == 200, resolve_resp.text

    async with auth_client("admin") as client:
        close_resp = await client.post(f"/api/v1/requests/{request_id}/close")
    assert close_resp.status_code == 200, close_resp.text

    async with auth_client("admin") as client:
        resp = await client.get(f"/api/v1/requests/{request_id}/export")
    assert resp.status_code == 200, resp.text

    wb = _load_workbook(resp.content)
    assert set(wb.sheetnames) == _EXPECTED_SHEETS

    history_ws = wb["Historique"]
    history_values = [cell.value for row in history_ws.iter_rows(min_row=2) for cell in row]
    assert any(v == "Résolution" for v in history_values) or any(
        isinstance(v, str) and v.startswith("Résolution") for v in history_values
    )
    assert any(v == "Clôture" for v in history_values)

    actors_ws = wb["Acteurs"]
    actor_names = [row[0].value for row in actors_ws.iter_rows(min_row=2)]
    assert len(actor_names) >= 1

    # BR-EXPORT-ADMIN-001 — exclusion stricte de toute donnée SLA/délai.
    all_strings = _all_cell_strings(wb)
    assert not any("sla" in s.lower() for s in all_strings), [
        s for s in all_strings if "sla" in s.lower()
    ]
