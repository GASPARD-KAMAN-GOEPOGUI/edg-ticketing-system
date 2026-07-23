from __future__ import annotations

import re
from pathlib import Path

import pytest

from tests.conftest import MOCK_ACCOUNTS
from tests.api.test_requests_baseline import (
    _ensure_test_account,
    _ensure_test_organigram,
    _ensure_test_unity,
)


ROOT = Path(__file__).resolve().parents[3]


def _extract_object_array(text: str, object_name: str, key: str) -> list[str]:
    constants = {
        "AUTHENTICATED_ROLES": ["user", "agent", "chief", "director", "dg", "admin"],
    }
    start = text.index(f"const {object_name}")
    next_decl = text.find("\nconst ", start + 1)
    end = next_decl if next_decl != -1 else text.index("};", start)
    object_text = text[start:end]
    match = re.search(rf"\b{re.escape(key)}:\s*\[([^\]]*)\]", object_text)
    if match is None:
        const_match = re.search(rf"\b{re.escape(key)}:\s*([A-Z_]+)", object_text)
        if const_match and const_match.group(1) in constants:
            return constants[const_match.group(1)]
    assert match is not None, f"Configuration introuvable pour {key!r}"
    return re.findall(r'"([^"]+)"', match.group(1))


def test_cdc_interface_actions_ticket_par_role_sont_coherentes():
    """Point 2 CDC: les actions affichees par l'interface suivent la matrice par role."""
    capabilities = (ROOT / "frontend/src/lib/capabilities.ts").read_text(encoding="utf-8")
    detail_page = (ROOT / "frontend/src/routes/app.requests.$id.tsx").read_text(encoding="utf-8")

    expected_roles = {
        "assign": ["chief", "admin"],
        "resolve": ["agent", "chief", "director", "admin"],
        "reject": ["chief", "admin"],
        "escalate": ["agent", "chief", "director", "admin"],
        "change_priority": ["chief", "director", "admin"],
        "change_service": ["chief", "director", "admin"],
        "transfer_direction": ["director", "admin"],
        "close": ["user", "agent", "chief", "director", "dg", "admin"],
        "request_reopen": ["user", "agent", "chief", "director", "dg", "admin"],
    }

    requester_actions = {"close", "request_reopen"}
    for action, roles in expected_roles.items():
        assert _extract_object_array(capabilities, "TICKET_ACTION_ROLES", action) == roles
        if action not in requester_actions:
            assert f'canTicketAction(role, "{action}"' in detail_page

    assert "isRequesterView" in detail_page
    assert "closeMut.mutate()" in detail_page
    assert "requestReopenMut.mutate" in detail_page

    assert "changeRequestPriority" in detail_page
    assert "changeRequestPriority(id, priority)" in detail_page


@pytest.mark.parametrize("role", ["user", "agent", "chief", "director", "dg", "admin"])
async def test_cdc_tous_les_roles_peuvent_creer_leur_propre_demande(auth_client, role):
    """Tout acteur connecte peut etre demandeur de son propre ticket."""
    await _ensure_test_unity(1, parent_direction_id=None)

    async with auth_client(role) as c:
        created = await c.post("/api/v1/requests/", json={
            "title": f"CDC demande personnelle {role}",
            "description": "Chaque role peut creer sa propre demande.",
            "category": "panne",
            "priority": "medium",
            "is_external": False,
            "unity_id": 1,
            "requester_name": f"Demandeur {role}",
            "requester_email": f"demandeur.{role}@test.edg.gn",
        })

    assert created.status_code == 201
    data = created.json().get("data", created.json())
    assert str(data["requester_id"]) == str(MOCK_ACCOUNTS[role].id)


@pytest.mark.parametrize(
    ("role", "method", "path_suffix", "json_body", "query"),
    [
        ("agent", "post", "/resolve", None, ""),
        ("chief", "post", "/assign", None, "?assignee_id=202"),
        ("director", "post", "/transfer-direction", {
            "target_direction_id": "9900",
            "reason": "Tentative de traitement de sa propre demande.",
        }, ""),
        ("admin", "post", "/priority", {"priority": "high"}, ""),
    ],
)
async def test_cdc_role_privilegie_ne_traite_pas_sa_propre_demande(
    auth_client,
    role,
    method,
    path_suffix,
    json_body,
    query,
):
    await _ensure_test_unity(1, parent_direction_id=None)
    await _ensure_test_unity(9900, parent_direction_id=None)
    await _ensure_test_account(202, unity_id=1, role="agent")

    async with auth_client(role) as c:
        created = await c.post("/api/v1/requests/", json={
            "title": f"CDC conflit interet {role}",
            "description": "Le createur ne doit pas traiter son propre ticket.",
            "category": "panne",
            "priority": "medium",
            "is_external": False,
            "unity_id": 1,
            "requester_name": f"Demandeur {role}",
            "requester_email": f"conflit.{role}@test.edg.gn",
        })
        assert created.status_code == 201
        rid = str(created.json().get("data", created.json())["id"])
        kwargs = {"json": json_body} if json_body is not None else {}
        response = await getattr(c, method)(
            f"/api/v1/requests/{rid}{path_suffix}{query}",
            **kwargs,
        )

    assert response.status_code == 403


async def test_cdc_scenario_soutenance_ticket_complet(auth_client):
    """Point 3 CDC: creation -> transfert direction -> assignation -> escalade -> resolution -> cloture."""
    await _ensure_test_unity(1, parent_direction_id=None)
    await _ensure_test_organigram(1)
    await _ensure_test_unity(9101, parent_direction_id=1)
    await _ensure_test_organigram(9101, parent_unity_id=1)

    await _ensure_test_unity(9900, parent_direction_id=None)
    await _ensure_test_organigram(9900)
    await _ensure_test_unity(9901, parent_direction_id=9900)
    await _ensure_test_organigram(9901, parent_unity_id=9900)
    await _ensure_test_account(2, unity_id=9101, role="agent")
    await _ensure_test_account(3, unity_id=9901, role="chief")

    snapshots = {
        role: {
            "id": MOCK_ACCOUNTS[role].id,
            "unity_id": MOCK_ACCOUNTS[role].unity_id,
        }
        for role in ("agent", "chief", "director")
    }

    try:
        async with auth_client("user") as c:
            created = await c.post("/api/v1/requests/", json={
                "title": "CDC soutenance - demande complete",
                "description": "Scenario complet de validation CDC.",
                "category": "panne",
                "priority": "medium",
                "is_external": False,
                "unity_id": 9101,
                "requester_name": "Demandeur CDC",
                "requester_email": "demandeur.cdc@test.edg.gn",
            })
        assert created.status_code == 201
        rid = str(created.json().get("data", created.json())["id"])

        MOCK_ACCOUNTS["chief"].unity_id = 9101
        async with auth_client("chief") as c:
            assigned = await c.post(f"/api/v1/requests/{rid}/assign?assignee_id=2")
        assert assigned.status_code == 200
        assigned_data = assigned.json().get("data", assigned.json())
        assert str(assigned_data["assignee_id"]) == "2"
        assert assigned_data["request_status"] == "assigned"

        MOCK_ACCOUNTS["agent"].id = 2
        MOCK_ACCOUNTS["agent"].unity_id = 9101
        async with auth_client("agent") as c:
            commented = await c.post(
                f"/api/v1/requests/{rid}/comments",
                json={"body": "Analyse agent CDC.", "is_public": False},
            )
            escalated = await c.post(
                f"/api/v1/requests/{rid}/escalate",
                json={
                    "level": "Chef de service",
                    "reason": "Validation chef requise avant resolution.",
                },
            )
        assert commented.status_code == 201
        assert escalated.status_code == 201

        MOCK_ACCOUNTS["director"].unity_id = 1
        async with auth_client("director") as c:
            transferred = await c.post(
                f"/api/v1/requests/{rid}/transfer-direction",
                json={
                    "target_direction_id": "9900",
                    "reason": "Aucun service de la direction source ne peut traiter.",
                },
            )
        assert transferred.status_code == 200
        transferred_data = transferred.json().get("data", transferred.json())
        assert transferred_data["request_status"] == "qualifying"
        assert str(transferred_data["unity_id"]) == "9900"

        MOCK_ACCOUNTS["director"].unity_id = 9900
        async with auth_client("director") as c:
            reassigned = await c.post(
                f"/api/v1/requests/{rid}/reassign",
                json={
                    "target_unity_id": "9901",
                    "reason": "Routage vers le service competent de la direction cible.",
                },
            )
        assert reassigned.status_code == 200
        reassigned_data = reassigned.json().get("data", reassigned.json())
        assert str(reassigned_data["unity_id"]) == "9901"
        assert str(reassigned_data["assignee_id"]) == "3"

        MOCK_ACCOUNTS["chief"].unity_id = 9901
        async with auth_client("chief") as c:
            resolved = await c.post(f"/api/v1/requests/{rid}/resolve")
        assert resolved.status_code == 200
        resolved_data = resolved.json().get("data", resolved.json())
        assert resolved_data["request_status"] == "resolved"

        async with auth_client("user") as c:
            closed = await c.post(f"/api/v1/requests/{rid}/close")
        assert closed.status_code == 200
        closed_data = closed.json().get("data", closed.json())
        assert closed_data["request_status"] == "closed"

        async with auth_client("admin") as c:
            detail = await c.get(f"/api/v1/requests/{rid}")
        assert detail.status_code == 200

        detail_data = detail.json().get("data", detail.json())
        events = {event["event_type"] for event in detail_data.get("timelines", [])}
        assert {
            "transferred_direction",
            "reassigned_service",
            "assigned",
            "comment_added",
            "escalation_manual",
            "resolved",
            "closed",
        }.issubset(events)
    finally:
        for role, values in snapshots.items():
            MOCK_ACCOUNTS[role].id = values["id"]
            MOCK_ACCOUNTS[role].unity_id = values["unity_id"]
