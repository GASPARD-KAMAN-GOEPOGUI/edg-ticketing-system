"""BR-DISTRIBUTION-001 — ajoute `request.distributor_id` (FK account.id, NULLABLE).

Distingue le destinataire de DISTRIBUTION (chef de division support qui doit
repartir le ticket) du responsable OPERATIONNEL (`assignee_id`). Sans cette
colonne, orienter un ticket vers un CDS le designait immediatement comme
traitant et le faisait tomber dans sa boite de traitement.

Migration ADDITIVE et NON DESTRUCTIVE : colonne nullable, aucune donnee
existante lue ni modifiee, aucun backfill. Tous les tickets anterieurs restent
a `distributor_id = NULL`, c'est-a-dire exactement leur comportement actuel.
La table `account` (partagee avec la plateforme centrale) n'est pas modifiee :
seule une FK en lecture est ajoutee depuis `request`.

Revision ID: 024
Revises: 023
Create Date: 2026-09-21
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "024"
down_revision: Union[str, None] = "023"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "request",
        sa.Column("distributor_id", sa.Integer(), nullable=True),
    )
    op.create_index("ix_request_distributor_id", "request", ["distributor_id"])
    op.create_foreign_key(
        "fk_request_distributor_id_account",
        "request", "account",
        ["distributor_id"], ["id"],
    )


def downgrade() -> None:
    op.drop_constraint("fk_request_distributor_id_account", "request", type_="foreignkey")
    op.drop_index("ix_request_distributor_id", table_name="request")
    op.drop_column("request", "distributor_id")
