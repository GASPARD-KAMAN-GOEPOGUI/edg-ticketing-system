"""Ajoute password_hash dans la table account

Contexte : la colonne manquait dans la base MySQL (erreur SQL 1054).
Le champ est nullable pour conserver la compatibilité avec les comptes
SSO (keycloak_id) qui n'ont pas de mot de passe local.
L'authentification locale exige un hash non-null (validé au niveau service).

Revision ID: 001
Revises:
Create Date: 2026-06-12
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "001"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Vérifie si la colonne existe déjà (idempotent)
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            "SELECT COUNT(*) FROM information_schema.columns "
            "WHERE table_schema = DATABASE() "
            "AND table_name = 'account' "
            "AND column_name = 'password_hash'"
        )
    )
    if result.scalar() == 0:
        op.add_column(
            "account",
            sa.Column(
                "password_hash",
                sa.String(255),
                nullable=True,
                comment="Hash Argon2id du mot de passe. NULL pour les comptes SSO.",
            ),
        )


def downgrade() -> None:
    op.drop_column("account", "password_hash")
