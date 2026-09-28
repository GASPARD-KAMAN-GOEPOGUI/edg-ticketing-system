"""Restauration des notifications de creation de ticket archivees.

Decision produit du 2026-09-26. La notification de creation d'un ticket
(« Ticket cree », emise au demandeur dans `ServiceRequest.create`) doit rester
visible en permanence dans l'espace Notifications du compte concerne : c'est la
trace que sa demande a bien ete enregistree.

Or le panneau de notifications exposait un bouton « archiver » applique a
n'importe quelle notification, y compris celle-la. L'archivage est un
soft-delete (`deleted_at` renseigne) qui masque la ligne de la vue active : les
comptes qui avaient archive cette notification ne la retrouvaient plus, ce qui
donnait l'impression d'une perte de l'historique apres rechargement de la page.

Le bouton « archiver » a ete retire de l'interface (panneau lateral et page
/app/notifications). Cette migration repare les donnees deja produites en
remettant ces notifications dans la vue active.

PORTEE : uniquement les notifications de creation (`title = 'Ticket cree'`
avec un `request_id`) qui sont actuellement archivees. Les autres notifications
archivees ne sont PAS touchees — elles restent consultables dans l'onglet
« Archives », qui demeure en place, et peuvent etre restaurees une par une
depuis l'interface.

AUCUNE PERTE POSSIBLE : l'operation ne fait que remettre `deleted_at` a NULL,
exactement ce que fait la restauration applicative
(`BaseRepository.restore()`). Aucune ligne n'est creee ni supprimee.

Revision ID: 029
Revises: 028
Create Date: 2026-09-26
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "029"
down_revision: Union[str, None] = "028"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# Libelle exact emis par ServiceRequest.create (accent inclus) — seul
# discriminant disponible : la table `notification` ne porte aucune colonne
# de type d'evenement.
_CREATION_TITLE = "Ticket créé"


def upgrade() -> None:
    conn = op.get_bind()
    result = conn.execute(
        sa.text(
            """
            UPDATE notification
               SET deleted_at = NULL
             WHERE deleted_at IS NOT NULL
               AND request_id IS NOT NULL
               AND title = :title
            """
        ),
        {"title": _CREATION_TITLE},
    )
    print(f"[029] Notifications de creation restaurees : {result.rowcount}")


def downgrade() -> None:
    """Sans effet — volontairement.

    Remettre ces notifications a l'etat archive est impossible de facon fidele :
    la date d'archivage d'origine est perdue par `upgrade()` (ecrasee par NULL),
    et rien ne distingue plus les lignes restaurees ici de celles qui n'avaient
    jamais ete archivees. Re-archiver en masse supprimerait de la vue active des
    notifications legitimes, ce qui serait plus destructeur que le statu quo.
    """
