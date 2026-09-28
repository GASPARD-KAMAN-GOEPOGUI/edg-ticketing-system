"""Retrait des fonctionnalites Annonces et Base de connaissances + referentiel Statuts de compte.

Decision produit : les deux fonctionnalites sont retirees de l'application.
Le referentiel `account_status` disparait egalement, mais PAS la colonne
`account.account_status` qui le consommait : celle-ci est un VARCHAR(50) libre
et reste en place, alimentee par le code (`active`, `inactive`...). Seule la
validation referentielle qui verifiait ces valeurs est supprimee.

Tables retirees (8) :
  - annonces  : announcement, announcement_target_role, announcement_category,
                announcement_priority, announcement_status
  - savoir    : knowledge_article, knowledge_category
  - comptes   : account_status

Aucune donnee metier perdue : `announcement` et `knowledge_article` etaient
vides au moment de la migration, les six autres tables ne contenaient que des
lignes de reference semees au demarrage.

ORDRE DE SUPPRESSION : `announcement` porte trois cles etrangeres vers
announcement_category/priority/status, et `announcement_target_role` reference
`announcement`. On descend donc des tables porteuses vers les referentiels.

MIGRATION DESTRUCTIVE ET NON REVERSIBLE EN DONNEES : `downgrade()` recree la
structure des tables pour permettre un retour arriere du schema, mais ne peut
evidemment pas restaurer leur contenu.

Revision ID: 026
Revises: 025
Create Date: 2026-09-24
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "026"
down_revision: Union[str, None] = "025"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Tables ordonnees des porteuses vers les referentiels (voir docstring).
_TABLES_IN_DROP_ORDER = (
    "announcement_target_role",
    "announcement",
    "announcement_category",
    "announcement_priority",
    "announcement_status",
    "knowledge_article",
    "knowledge_category",
    "account_status",
)


def _base_columns() -> list[sa.Column]:
    """Colonnes de `BaseColumns`, communes a toutes les tables recreees."""
    return [
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("uuid", sa.String(36), nullable=False, unique=True),
        sa.Column("status", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("infos", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    ]


def _ref_table(name: str) -> None:
    """Recree une table de reference (code/label) au format commun."""
    op.create_table(
        name,
        sa.Column("code", sa.String(50), nullable=False, unique=True),
        sa.Column("label", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        *_base_columns(),
    )


def upgrade() -> None:
    for table in _TABLES_IN_DROP_ORDER:
        op.drop_table(table)


def downgrade() -> None:
    # Referentiels d'abord : `announcement` en depend par cle etrangere.
    for name in ("announcement_category", "announcement_priority",
                 "announcement_status", "knowledge_category", "account_status"):
        _ref_table(name)

    op.create_table(
        "announcement",
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("account.id"), nullable=True),
        sa.Column("announcement_category_id", sa.Integer(),
                  sa.ForeignKey("announcement_category.id"), nullable=True),
        sa.Column("announcement_priority_id", sa.Integer(),
                  sa.ForeignKey("announcement_priority.id"), nullable=True),
        sa.Column("announcement_status_id", sa.Integer(),
                  sa.ForeignKey("announcement_status.id"), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        sa.Column("closed_at", sa.DateTime(), nullable=True),
        *_base_columns(),
    )
    op.create_table(
        "announcement_target_role",
        sa.Column("announcement_id", sa.Integer(),
                  sa.ForeignKey("announcement.id"), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        *_base_columns(),
    )
    op.create_table(
        "knowledge_article",
        sa.Column("author_id", sa.Integer(), sa.ForeignKey("account.id"), nullable=True),
        sa.Column("title", sa.String(500), nullable=False),
        sa.Column("excerpt", sa.Text(), nullable=True),
        sa.Column("body", sa.Text(), nullable=True),
        sa.Column("category", sa.String(50), nullable=True),
        sa.Column("read_time", sa.SmallInteger(), nullable=True),
        sa.Column("author", sa.String(200), nullable=True),
        sa.Column("is_published", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("is_archived", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("tags", sa.JSON(), nullable=True),
        sa.Column("published_at", sa.DateTime(), nullable=True),
        *_base_columns(),
    )
