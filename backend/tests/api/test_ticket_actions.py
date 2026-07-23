from __future__ import annotations

from types import SimpleNamespace

import pytest

from api.core.exceptions import BusinessException, ForbiddenException
from api.core.ticket_actions import (
    assert_assignment_allowed,
    assert_action_allowed,
    assert_escalation_allowed,
    assert_service_reassignment_allowed,
    assert_ticket_action,
    assert_ticket_scope,
    assert_transition_allowed,
    normalize_status,
)


def actor(role: str, *, id: int = 1, unity_id: int | None = 1):
    return SimpleNamespace(role=role, id=id, unity_id=unity_id)


def ticket(
    *,
    status: str = "new",
    requester_id: int = 10,
    unity_id: int | None = 1,
    direction_id: int | None = 1,
    assignee_id: int | None = None,
    in_triage: bool = False,
):
    return SimpleNamespace(
        request_status=status,
        requester_id=requester_id,
        unity_id=unity_id,
        direction_id=direction_id,
        assignee_id=assignee_id,
        in_triage=in_triage,
    )


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("new", "qualifying"),
        ("qualifying", "assigned"),
        ("assigned", "in_progress"),
        ("escalated", "in_progress"),
        ("in_progress", "pending"),
        ("assigned", "resolved"),
        ("in_progress", "resolved"),
        ("pending", "resolved"),
        ("escalated", "qualifying"),
        ("resolved", "closed"),
        ("closed", "reopened"),
        ("assigned", "rejected"),
        ("assigned", "cancelled"),
    ],
)
def test_transition_matrix_allows_expected_paths(current, target):
    assert_transition_allowed(current, target)


@pytest.mark.parametrize(
    ("current", "target"),
    [
        ("new", "resolved"),
        ("qualifying", "resolved"),
        ("new", "closed"),
        ("closed", "assigned"),
        ("resolved", "assigned"),
        ("cancelled", "resolved"),
        ("rejected", "closed"),
    ],
)
def test_transition_matrix_rejects_invalid_paths(current, target):
    with pytest.raises(BusinessException):
        assert_transition_allowed(current, target)


def test_status_aliases_are_normalized():
    assert normalize_status("cancalled") == "cancelled"
    assert normalize_status("escaladed") == "escalated"


@pytest.mark.parametrize("current", ["cancelled", "cancalled", "closed", "resolved", "rejected"])
def test_terminal_statuses_cannot_transition_to_assigned(current):
    with pytest.raises(BusinessException):
        assert_transition_allowed(current, "assigned")


def test_transition_bypass_is_explicit_for_admin_and_dg():
    assert_transition_allowed(
        "closed",
        "assigned",
        actor_role="admin",
        allow_bypass=True,
    )
    with pytest.raises(BusinessException):
        assert_transition_allowed("closed", "assigned", actor_role="admin")


@pytest.mark.parametrize(
    ("role", "action"),
    [
        ("agent", "resolve"),
        ("chief", "reject"),
        ("director", "reassign"),
        ("admin", "escalate"),
        ("user", "close"),
    ],
)
def test_action_roles_allow_expected_actions(role, action):
    assert_action_allowed(role, action)


@pytest.mark.parametrize(
    ("role", "action"),
    [
        ("user", "resolve"),
        ("agent", "reject"),
        ("agent", "reopen"),
        ("agent", "reject_reopen"),
        ("admin", "merge"),
        ("admin", "duplicate"),
        ("dg", "assign"),
    ],
)
def test_action_roles_reject_unauthorized_actions(role, action):
    with pytest.raises(ForbiddenException):
        assert_action_allowed(role, action)


def test_user_scope_is_limited_to_own_requests():
    current_actor = actor("user", id=10, unity_id=None)
    assert_ticket_scope(current_actor, ticket(requester_id=10), action="close")

    with pytest.raises(ForbiddenException):
        assert_ticket_scope(current_actor, ticket(requester_id=99), action="close")


@pytest.mark.parametrize(
    ("role", "action"),
    [
        ("agent", "resolve"),
        ("agent", "escalate"),
        ("chief", "assign"),
        ("chief", "reject"),
        ("chief", "change_priority"),
        ("director", "transfer_direction"),
        ("director", "reassign"),
        ("admin", "resolve"),
        ("admin", "reassign"),
        ("admin", "change_priority"),
    ],
)
def test_privileged_actor_cannot_process_own_request(role, action):
    current_actor = actor(role, id=42, unity_id=1)
    own_ticket = ticket(requester_id=42, unity_id=1, direction_id=1, assignee_id=42)

    with pytest.raises(ForbiddenException):
        assert_ticket_scope(
            current_actor,
            own_ticket,
            action=action,
            allowed_dir_unity_ids={1},
        )


@pytest.mark.parametrize("action", ["close", "cancel", "request_reopen"])
def test_requester_actions_remain_allowed_on_own_request(action):
    current_actor = actor("director", id=42, unity_id=1)
    assert_ticket_scope(current_actor, ticket(requester_id=42), action=action)


def test_request_reopen_is_only_for_the_requester():
    current_ticket = ticket(status="resolved", requester_id=10)
    assert_ticket_scope(actor("user", id=10, unity_id=None), current_ticket, action="request_reopen")

    with pytest.raises(ForbiddenException):
        assert_ticket_scope(actor("admin", id=6, unity_id=None), current_ticket, action="request_reopen")


def test_agent_scope_accepts_same_unity_assigned_ticket_and_triage():
    current_actor = actor("agent", id=2, unity_id=1)

    assert_ticket_scope(current_actor, ticket(unity_id=1), action="assign")
    assert_ticket_scope(current_actor, ticket(unity_id=99, assignee_id=2), action="resolve")
    assert_ticket_scope(
        current_actor,
        ticket(unity_id=None, assignee_id=None, in_triage=True),
        action="qualify",
    )

    with pytest.raises(ForbiddenException):
        assert_ticket_scope(current_actor, ticket(unity_id=99, assignee_id=3), action="assign")


def test_agent_scope_accepts_explicit_queue_unity_scope_only():
    current_actor = actor("agent", id=2, unity_id=1)

    assert_ticket_scope(
        current_actor,
        ticket(unity_id=2, direction_id=1),
        action="assign",
        allowed_dir_unity_ids={1, 2},
    )

    with pytest.raises(ForbiddenException):
        assert_ticket_scope(
            current_actor,
            ticket(unity_id=99, direction_id=1),
            action="assign",
            allowed_dir_unity_ids={1, 2},
        )


def test_agent_can_only_self_assign_free_ticket():
    current_actor = actor("agent", id=2, unity_id=1)
    current_ticket = ticket(status="new", unity_id=1, assignee_id=None)

    assert_ticket_action(
        current_actor,
        current_ticket,
        "assign",
        target_status="assigned",
    )
    assert_assignment_allowed(current_actor, current_ticket, assignee_id=2)

    with pytest.raises(ForbiddenException):
        assert_assignment_allowed(current_actor, current_ticket, assignee_id=3)

    with pytest.raises(BusinessException):
        assert_assignment_allowed(
            current_actor,
            ticket(status="assigned", unity_id=1, assignee_id=3),
            assignee_id=2,
        )


def test_chief_and_admin_can_assign_other_agents():
    current_ticket = ticket(status="qualified", unity_id=1, assignee_id=None)

    assert_assignment_allowed(
        actor("chief", id=3, unity_id=1),
        current_ticket,
        assignee_id=2,
        target_unity_id=1,
        target_role="agent",
    )
    assert_assignment_allowed(
        actor("admin", id=6, unity_id=None),
        current_ticket,
        assignee_id=2,
        target_unity_id=99,
        target_role="chief",
    )

    with pytest.raises(ForbiddenException):
        assert_assignment_allowed(
            actor("chief", id=3, unity_id=1),
            current_ticket,
            assignee_id=2,
            target_unity_id=2,
            target_role="agent",
        )

    with pytest.raises(ForbiddenException):
        assert_assignment_allowed(
            actor("chief", id=3, unity_id=1),
            current_ticket,
            assignee_id=2,
            target_unity_id=1,
            target_role="chief",
        )


def test_service_reassignment_is_limited_by_role_scope():
    current_ticket = ticket(status="qualified", unity_id=10, direction_id=1)

    assert_service_reassignment_allowed(
        actor("chief", id=3, unity_id=10),
        current_ticket,
        target_unity_id=11,
        target_direction_id=1,
    )
    assert_service_reassignment_allowed(
        actor("director", id=4, unity_id=1),
        current_ticket,
        target_unity_id=11,
        target_direction_id=1,
    )
    assert_service_reassignment_allowed(
        actor("admin", id=6, unity_id=None),
        current_ticket,
        target_unity_id=99,
        target_direction_id=99,
    )

    with pytest.raises(ForbiddenException):
        assert_service_reassignment_allowed(
            actor("chief", id=3, unity_id=10),
            current_ticket,
            target_unity_id=99,
            target_direction_id=2,
        )

    assert_service_reassignment_allowed(
        actor("chief", id=3, unity_id=10),
        ticket(status="qualified", unity_id=10, direction_id=None),
        target_unity_id=11,
        target_direction_id=1,
        actor_direction_id=1,
    )

    with pytest.raises(ForbiddenException):
        assert_service_reassignment_allowed(
            actor("director", id=4, unity_id=1),
            current_ticket,
            target_unity_id=99,
            target_direction_id=2,
        )

    with pytest.raises(ForbiddenException):
        assert_service_reassignment_allowed(
            actor("chief", id=3, unity_id=10),
            ticket(status="qualified", unity_id=10, direction_id=None),
            target_unity_id=99,
            target_direction_id=2,
            actor_direction_id=1,
        )


def test_agent_escalation_requires_own_assigned_ticket():
    current_actor = actor("agent", id=2, unity_id=1)

    assert_escalation_allowed(
        current_actor,
        ticket(status="in_progress", unity_id=1, assignee_id=2),
    )

    with pytest.raises(ForbiddenException):
        assert_escalation_allowed(
            current_actor,
            ticket(status="in_progress", unity_id=1, assignee_id=3),
        )


def test_director_scope_is_limited_to_direction_services():
    current_actor = actor("director", id=4, unity_id=1)

    assert_ticket_scope(
        current_actor,
        ticket(unity_id=2, direction_id=1),
        action="resolve",
        allowed_dir_unity_ids={1, 2, 3},
    )

    with pytest.raises(ForbiddenException):
        assert_ticket_scope(
            current_actor,
            ticket(unity_id=99, direction_id=99),
            action="resolve",
            allowed_dir_unity_ids={1, 2, 3},
        )


def test_director_resolves_only_escalated_tickets():
    current_actor = actor("director", id=4, unity_id=1)

    assert_ticket_action(
        current_actor,
        ticket(status="escalated", unity_id=2, direction_id=1),
        "resolve",
        target_status="resolved",
        allowed_dir_unity_ids={1, 2, 3},
    )

    for status in ("assigned", "in_progress", "pending"):
        with pytest.raises(ForbiddenException):
            assert_ticket_action(
                current_actor,
                ticket(status=status, unity_id=2, direction_id=1),
                "resolve",
                target_status="resolved",
                allowed_dir_unity_ids={1, 2, 3},
            )


def test_ticket_action_combines_role_scope_and_transition():
    current_actor = actor("agent", id=2, unity_id=1)
    current_ticket = ticket(status="assigned", unity_id=1, assignee_id=2)

    assert_ticket_action(
        current_actor,
        current_ticket,
        "resolve",
        target_status="resolved",
    )

    with pytest.raises(BusinessException):
        assert_ticket_action(
            current_actor,
            ticket(status="closed", unity_id=1, assignee_id=2),
            "resolve",
            target_status="resolved",
        )

    with pytest.raises(ForbiddenException):
        assert_ticket_action(
            actor("user", id=10, unity_id=None),
            ticket(status="assigned", requester_id=10),
            "resolve",
            target_status="resolved",
        )
