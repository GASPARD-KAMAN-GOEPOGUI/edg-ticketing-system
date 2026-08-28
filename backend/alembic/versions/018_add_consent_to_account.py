"""Ajoute le suivi de consentement pour le rattachement post-login.

Contexte : un utilisateur authentifié avec succès par la plateforme centrale
mais sans compte local (aucun central_user_id correspondant) et sans groupe
central de cette application (admin-support/qualify-support/collaborateur-
support) doit désormais passer par un écran de consentement explicite avant
d'être rattaché (POST /auth/consent/accept) — au lieu d'être rejeté avec un
401 sec. Ces deux colonnes tracent cette acceptation.

Revision ID: 018
Revises: 017
Create Date: 2026-08-19
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "018"
down_revision: Union[str, None] = "017"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("account", sa.Column("consent_accepted_at", sa.DateTime(), nullable=True))
    op.add_column("account", sa.Column("consent_version", sa.String(50), nullable=True))


def downgrade() -> None:
    op.drop_column("account", "consent_version")
    op.drop_column("account", "consent_accepted_at")
