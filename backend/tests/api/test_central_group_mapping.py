"""Correspondance groupes plateforme centrale <-> roles EDG Connect.

La table `GROUP_ROLE_PRIORITY` est lue DANS LES DEUX SENS :
  - `role_from_groups()` : groupes centraux -> role local (a la connexion)
  - `group_for_role()`   : role local -> groupe central (backoffice EDG Connect)

Une correspondance manquante ferait retomber le role sur `collaborateur-support`,
ce qui annulerait silencieusement, a la connexion suivante, un changement de role
effectue dans le backoffice. Ces tests verrouillent les deux sens et l'aller-retour.
"""
from __future__ import annotations

import pytest

from api.core.central_auth import group_for_role, role_from_groups
from api.dependencies import _ROLE_SYNC_SPACE

# Correspondance de reference — toute evolution doit etre volontaire.
_MAPPING = {
    "admin": "admin-support",
    "chief-service": "qualify-support",
    "chef-division-support": "chef-division-support",
    "technicien": "technicien-support",
    "user": "collaborateur-support",
}

# Roles purement locaux : aucun groupe central dedie, jamais ecrases par la synchro.
_LOCAL_ONLY = ["chief-departement", "director"]


@pytest.mark.parametrize("role,group", sorted(_MAPPING.items()))
def test_sens_backoffice_vers_central(role, group):
    """Changer un role dans le backoffice EDG Connect doit pousser le BON groupe."""
    assert group_for_role(role) == group


@pytest.mark.parametrize("role,group", sorted(_MAPPING.items()))
def test_sens_central_vers_edg_connect(role, group):
    """Changer un groupe cote central doit donner le BON role a la connexion."""
    assert role_from_groups([{"codename": group}]) == role


@pytest.mark.parametrize("role", sorted(_MAPPING))
def test_aller_retour_sans_revert_silencieux(role):
    """Un role pousse vers son groupe puis relu doit redonner le meme role —
    sinon le changement du backoffice s'annulerait tout seul a la reconnexion."""
    assert role_from_groups([{"codename": group_for_role(role)}]) == role


@pytest.mark.parametrize("role", sorted(_MAPPING))
def test_roles_mappes_sont_synchronisables(role):
    """Tout role ayant un groupe central dedie doit etre dans l'espace de synchro,
    sinon un changement cote central ne descendrait jamais jusqu'au role local."""
    assert role in _ROLE_SYNC_SPACE


@pytest.mark.parametrize("role", _LOCAL_ONLY)
def test_roles_purement_locaux_jamais_ecrases(role):
    """chief-departement et director n'ont pas de groupe central : ils doivent
    rester hors de l'espace de synchro pour ne jamais etre ecrases."""
    assert role not in _ROLE_SYNC_SPACE


def test_priorite_si_plusieurs_groupes():
    """Si un compte appartient a plusieurs groupes, le plus privilegie gagne."""
    groups = [
        {"codename": "collaborateur-support"},
        {"codename": "technicien-support"},
        {"codename": "admin-support"},
    ]
    assert role_from_groups(groups) == "admin"


def test_groupe_inactif_ignore():
    """Un groupe desactive (`is_activated=False`) ne doit pas attribuer son role."""
    groups = [
        {"codename": "technicien-support", "is_activated": False},
        {"codename": "collaborateur-support"},
    ]
    assert role_from_groups(groups) == "user"


def test_aucun_groupe_connu_ne_donne_aucun_role():
    assert role_from_groups([{"codename": "groupe-inconnu"}]) is None
