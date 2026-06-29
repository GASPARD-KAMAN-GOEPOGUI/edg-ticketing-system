"""Ajoute dg_comment dans la table escalation

Contexte : la colonne manquait dans la base MySQL (erreur SQL 1054 au GET /requests/).
Le champ est nullable — il n'est renseigné que quand le DG approuve ou rejette
une escalade via l'interface de la Direction Générale.

Revision ID: 002
Revises: 001
Create Date: 2026-06-15
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002"
down_revision: Union[str, None] = "001"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() "
            "AND table_name = 'escalation' "
            "AND column_name = 'dg_comment'"
        )
    )
    if result.scalar() == 0:
        op.add_column(
            "escalation",
            sa.Column(
                "dg_comment",
                sa.Text,
                nullable=True,
                comment="Commentaire du DG lors de l'approbation ou du rejet d'une escalade.",
            ),
        )


def downgrade() -> None:
    op.drop_column("escalation", "dg_comment")
