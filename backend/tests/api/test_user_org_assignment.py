from __future__ import annotations

from uuid import uuid4

import pytest


def _payload(response):
    body = response.json()
    return body.get("data", body)


async def _create_org_chain(client):
    directions = await client.get("/api/v1/directions/?limit=20")
    assert directions.status_code == 200
    direction_id = _payload(directions)["items"][0]["id"]
    suffix = uuid4().hex[:8].upper()

    department = await client.post(
        "/api/v1/departments/",
        json={
            "name": f"Departement Roles {suffix}",
            "code": f"RDEP-{suffix}",
            "direction_id": direction_id,
        },
    )
    assert department.status_code == 201
    department_id = _payload(department)["id"]

    unit = await client.post(
        "/api/v1/units/",
        json={
            "name": f"Service Roles {suffix}",
            "code": f"RSRV-{suffix}",
            "department_id": department_id,
        },
    )
    assert unit.status_code == 201
    unit_id = _payload(unit)["id"]
    return direction_id, department_id, unit_id, suffix.lower()


@pytest.mark.asyncio
async def test_admin_user_role_org_assignment_validation(auth_client):
    async with auth_client("admin") as client:
        direction_id, department_id, unit_id, suffix = await _create_org_chain(client)

        director = await client.post(
            "/api/v1/users/",
            json={
                "name": "Directeur Validation",
                "email": f"director-{suffix}@edg.gn",
                "role": "director",
                "direction_id": direction_id,
                "is_edg_employee": True,
            },
        )
        assert director.status_code == 201
        assert str(_payload(director)["unity_id"]) == str(direction_id)

        department_chief = await client.post(
            "/api/v1/users/",
            json={
                "name": "Chef Departement Validation",
                "email": f"chief-dept-{suffix}@edg.gn",
                "role": "chief",
                "department_id": department_id,
                "is_edg_employee": True,
            },
        )
        assert department_chief.status_code == 201
        assert str(_payload(department_chief)["unity_id"]) == str(department_id)

        service_chief = await client.post(
            "/api/v1/users/",
            json={
                "name": "Chef Service Validation",
                "email": f"chief-service-{suffix}@edg.gn",
                "role": "chief",
                "unit_id": unit_id,
                "is_edg_employee": True,
            },
        )
        assert service_chief.status_code == 201
        assert str(_payload(service_chief)["unity_id"]) == str(unit_id)

        agent = await client.post(
            "/api/v1/users/",
            json={
                "name": "Agent Validation",
                "email": f"agent-{suffix}@edg.gn",
                "role": "agent",
                "unit_id": unit_id,
                "is_edg_employee": True,
            },
        )
        assert agent.status_code == 201
        agent_id = _payload(agent)["id"]

        bad_director = await client.post(
            "/api/v1/users/",
            json={
                "name": "Directeur Invalide",
                "email": f"bad-director-{suffix}@edg.gn",
                "role": "director",
                "unit_id": unit_id,
                "is_edg_employee": True,
            },
        )
        assert bad_director.status_code == 400

        bad_admin = await client.post(
            "/api/v1/users/",
            json={
                "name": "Admin Invalide",
                "email": f"bad-admin-{suffix}@edg.gn",
                "role": "admin",
                "department_id": department_id,
                "is_edg_employee": True,
            },
        )
        assert bad_admin.status_code == 400

        invalid_update = await client.patch(
            f"/api/v1/users/{agent_id}",
            json={"role": "director", "unit_id": unit_id},
        )
        assert invalid_update.status_code == 400

        valid_update = await client.patch(
            f"/api/v1/users/{agent_id}",
            json={"role": "director", "direction_id": direction_id},
        )
        assert valid_update.status_code == 200
        valid_body = _payload(valid_update)
        assert valid_body["role"] == "director"
        assert str(valid_body["unity_id"]) == str(direction_id)
