"""Retrait des roles `director` et `chief-departement` de l'ENUM `account.role`.

Decision produit du 2026-09-25. Ces deux roles etaient les SEULS a ne pas etre
adosses a un groupe de la plateforme centrale : absents de
`GROUP_ROLE_PRIORITY` et volontairement exclus de `_ROLE_SYNC_SPACE`, ils
restaient purement locaux et ne pouvaient etre poses qu'a la main par un admin.
Leur retrait n'exige donc aucune coordination avec la plateforme centrale.

AUCUN COMPTE CONCERNE : aucune ligne `account` ne portait l'un de ces deux roles
au moment de la migration (le seul compte existant est un admin). Il n'y a donc
ni requalification ni perte de donnees.

L'escalade n'a volontairement PAS ete modifiee (consigne explicite) :
`ServiceEscalade.find_hierarchical_chief()` et `find_director_for_department()`
ciblent toujours ces roles et ne remonteront plus aucun compte. L'escalade
hierarchique, y compris l'escalade automatique sur depassement SLA, devient donc
un chemin mort tant qu'elle n'est pas recablee.

Revision ID: 028
Revises: 027
Create Date: 2026-09-25
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "028"
down_revision: Union[str, None] = "027"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


_ROLES_AFTER = ("public", "user", "chief-service", "technicien",
                "chef-division-support", "admin")
_ROLES_BEFORE = ("public", "user", "chief-service", "technicien",
                 "chef-division-support", "chief-departement", "director", "admin")

_LOG_ROLES_AFTER = _ROLES_AFTER
_LOG_ROLES_BEFORE = _ROLES_BEFORE


def _enum(values: tuple[str, ...]) -> str:
    return "ENUM(" + ", ".join(f"'{v}'" for v in values) + ")"


def upgrade() -> None:
    # Filet de securite : requalifier en `admin` tout compte qui porterait encore
    # l'un des deux roles (aucun au moment de la migration, mais un ALTER sur un
    # ENUM tronquerait silencieusement la valeur en chaine vide).
    op.execute(
        "UPDATE account SET role = 'admin' "
        "WHERE role IN ('chief-departement', 'director')"
    )
    op.execute(
        "UPDATE activity_log SET actor_role = 'admin' "
        "WHERE actor_role IN ('chief-departement', 'director')"
    )
    op.execute(f"ALTER TABLE account MODIFY role {_enum(_ROLES_AFTER)} NOT NULL")
    op.execute(f"ALTER TABLE activity_log MODIFY actor_role {_enum(_LOG_ROLES_AFTER)}")


def downgrade() -> None:
    # Restaure les valeurs de l'ENUM ; les comptes requalifies en `admin` ne sont
    # evidemment pas restitues a leur role d'origine.
    op.execute(f"ALTER TABLE account MODIFY role {_enum(_ROLES_BEFORE)} NOT NULL")
    op.execute(f"ALTER TABLE activity_log MODIFY actor_role {_enum(_LOG_ROLES_BEFORE)}")
