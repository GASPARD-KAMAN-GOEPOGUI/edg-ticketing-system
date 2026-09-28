from __future__ import annotations

import pytest


def _payload(response):
    body = response.json()
    return body.get("data", body)


async def _ensure_direction(client) -> str:
    """Retourne l'id d'une direction, en la creant si aucune n'existe.

    Ce test presupposait qu'une direction preexiste, ce que RIEN ne garantit :
    `SEED_ORG_STRUCTURE=False` n'en seme aucune, et les unites creees par les
    autres tests sont libellees « Unite Test N » — or `_kind_from_org` classe par
    prefixe de libelle, donc elles comptent comme des *units*, jamais comme des
    directions. Le test ne passait qu'au gre de l'ordre d'execution.
    """
    existing = await client.get("/api/v1/directions/?limit=20")
    assert existing.status_code == 200, existing.text
    items = _payload(existing)["items"]
    if items:
        return items[0]["id"]

    created = await client.post(
        "/api/v1/directions/",
        json={"name": "Direction Test Hierarchie", "code": "TDIR-HIER"},
    )
    assert created.status_code == 201, created.text
    return _payload(created)["id"]


@pytest.mark.asyncio
async def test_admin_org_hierarchy_department_unit_activation(auth_client):
    async with auth_client("admin") as client:
        direction_id = await _ensure_direction(client)

        department = await client.post(
            "/api/v1/departments/",
            json={
                "name": "Departement Test Codex",
                "code": "TDEP-CODEX",
                "direction_id": direction_id,
                "description": "Test hierarchy",
            },
        )
        assert department.status_code == 201
        department_body = _payload(department)
        assert department_body["direction_id"] == direction_id
        assert department_body["status"] is True

        unit = await client.post(
            "/api/v1/units/",
            json={
                "name": "Service Test Codex",
                "code": "TSRV-CODEX",
                "department_id": department_body["id"],
                "description": "Test hierarchy",
            },
        )
        assert unit.status_code == 201
        unit_body = _payload(unit)
        assert unit_body["department_id"] == department_body["id"]
        assert unit_body["direction_id"] == direction_id
        assert unit_body["status"] is True

        scoped_units = await client.get(f"/api/v1/units/by-direction/{direction_id}?limit=200")
        assert scoped_units.status_code == 200
        assert any(item["id"] == unit_body["id"] for item in _payload(scoped_units)["items"])

        blocked = await client.post(f"/api/v1/departments/{department_body['id']}/deactivate", json={})
        assert blocked.status_code == 409

        deactivated = await client.post(
            f"/api/v1/departments/{department_body['id']}/deactivate?force=true",
            json={},
        )
        assert deactivated.status_code == 200

        department_after = await client.get(f"/api/v1/departments/{department_body['id']}")
        assert department_after.status_code == 200
        assert _payload(department_after)["status"] is False

        unit_after = await client.get(f"/api/v1/units/{unit_body['id']}")
        assert unit_after.status_code == 200
        assert _payload(unit_after)["status"] is False

        reactivated_department = await client.post(f"/api/v1/departments/{department_body['id']}/activate", json={})
        assert reactivated_department.status_code == 200

        reactivated_unit = await client.post(f"/api/v1/units/{unit_body['id']}/activate", json={})
        assert reactivated_unit.status_code == 200

        unit_final = await client.get(f"/api/v1/units/{unit_body['id']}")
        assert unit_final.status_code == 200
        assert _payload(unit_final)["status"] is True
