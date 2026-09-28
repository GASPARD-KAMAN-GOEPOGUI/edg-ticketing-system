"""Procedure EDG/PS-GSI/Pro-02 tache 1.3 — ajoute `request.proposed_solution` (TEXT, NULLABLE).

Point de controle de la tache 1.3 (« Recevoir et imputer la requisition au chef
de division support pour traitement ») : le CSSHF doit joindre un « descriptif
de la solution proposee » a l'imputation. Ce descriptif est ensuite lu par le
chef de division support (qui decide de prendre ou d'affecter) puis par le
technicien qui traite.

A NE PAS CONFONDRE avec la cle `solution` deja stockee dans les `infos` de
l'evenement `treatment_completed` : celle-ci est la solution REELLEMENT
APPLIQUEE par le technicien a la resolution. Les deux coexistent et decrivent
deux moments differents du meme ticket.

Migration ADDITIVE et NON DESTRUCTIVE : colonne nullable, aucune donnee
existante lue ni modifiee, aucun backfill. Tous les tickets anterieurs restent
a `proposed_solution = NULL`, c'est-a-dire exactement leur comportement actuel.

Revision ID: 025
Revises: 024
Create Date: 2026-09-22
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "025"
down_revision: Union[str, None] = "024"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "request",
        sa.Column("proposed_solution", sa.Text(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("request", "proposed_solution")
