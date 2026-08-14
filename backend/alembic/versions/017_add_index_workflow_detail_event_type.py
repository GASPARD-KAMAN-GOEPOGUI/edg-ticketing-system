"""Ajoute un index sur workflow_detail.event_type.

Contexte : `workflow_detail` est un journal d'audit append-only qui ne fait
que grandir. Plusieurs chemins chauds filtrent directement sur `event_type`
sans autre condition indexée (ex. `ServiceStats.escalation_stats`,
`RepositoryRequest.list_transmitted_by_actor`, `ServiceEscalade`) — sans
index, ce sont des scans complets de table de plus en plus coûteux au fil
du temps.

Revision ID: 017
Revises: 016
Create Date: 2026-08-13
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op

revision: str = "017"
down_revision: Union[str, None] = "016"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_index(
        "idx_wfd_event_type", "workflow_detail", ["event_type", "deleted_at"]
    )


def downgrade() -> None:
    op.drop_index("idx_wfd_event_type", table_name="workflow_detail")
