"""Changement de mot de passe depuis l'espace connecté (page Profil).

Se distingue de /forgot-password + /reset-password : l'utilisateur etant deja
authentifie, AUCUN email ni code OTP n'est envoye. Le mot de passe n'existe que
sur la plateforme centrale (la table `account` n'a pas de colonne mot de passe),
donc l'ecriture centrale vaut mise a jour partout — rien a synchroniser en local.
"""
from __future__ import annotations

from types import SimpleNamespace
from unittest.mock import AsyncMock, patch

import pytest

from api.main import app
from api.dependencies import get_current_user

_URL = "/api/v1/auth/change-password"


def _actor(account_id: int = 7001, *, uuid: str | None = "uuid-test-7001", role: str = "user"):
    def _factory():
        return SimpleNamespace(
            id=account_id, role=role, unity_id=None, direction_id=None,
            email=f"user{account_id}@test.edg.gn", central_user_uuid=uuid,
        )
    return _factory


async def _post(client, body: dict, actor_dep):
    app.dependency_overrides[get_current_user] = actor_dep
    try:
        return await client.post(_URL, json=body)
    finally:
        app.dependency_overrides.pop(get_current_user, None)


async def test_change_password_met_a_jour_la_plateforme_centrale(auth_client):
    """Cas nominal : appelle la centrale avec le nouveau mot de passe, sans email."""
    async with auth_client("user") as client:
        with patch("api.core.central_auth.get_machine_token", new=AsyncMock(return_value="tok")), \
             patch("api.core.central_auth.reset_central_password", new=AsyncMock()) as reset:
            resp = await _post(
                client,
                {"new_password": "NouveauMdp123", "confirm_password": "NouveauMdp123"},
                _actor(),
            )

    assert resp.status_code == 200, resp.text
    assert resp.json()["data"] == {"changed": True}
    reset.assert_awaited_once()
    # Le mot de passe choisi par l'utilisateur est bien celui transmis.
    assert reset.await_args.kwargs["new_password"] == "NouveauMdp123"
    assert reset.await_args.args[0] == "uuid-test-7001"


async def test_confirmation_differente_est_refusee(auth_client):
    async with auth_client("user") as client:
        with patch("api.core.central_auth.reset_central_password", new=AsyncMock()) as reset:
            resp = await _post(
                client,
                {"new_password": "NouveauMdp123", "confirm_password": "AutreMdp123"},
                _actor(),
            )

    assert resp.status_code == 422, resp.text
    reset.assert_not_awaited()  # rien n'est envoyé à la centrale


async def test_mot_de_passe_trop_court_est_refuse(auth_client):
    async with auth_client("user") as client:
        with patch("api.core.central_auth.reset_central_password", new=AsyncMock()) as reset:
            resp = await _post(client, {"new_password": "court", "confirm_password": "court"}, _actor())

    assert resp.status_code == 422, resp.text
    reset.assert_not_awaited()


async def test_compte_sans_identite_centrale_est_refuse(auth_client):
    """Sans rattachement central, il n'existe aucun endroit ou ecrire le mot de passe."""
    async with auth_client("user") as client:
        with patch("api.core.central_auth.reset_central_password", new=AsyncMock()) as reset:
            resp = await _post(
                client,
                {"new_password": "NouveauMdp123", "confirm_password": "NouveauMdp123"},
                _actor(uuid=None),
            )

    assert resp.status_code == 422, resp.text
    reset.assert_not_awaited()


async def test_endpoint_exige_une_authentification(auth_client):
    """Sans session, pas de changement de mot de passe possible."""
    async with auth_client("user") as client:
        app.dependency_overrides.pop(get_current_user, None)
        resp = await client.post(
            _URL, json={"new_password": "NouveauMdp123", "confirm_password": "NouveauMdp123"},
        )
    assert resp.status_code in (401, 403), resp.text


@pytest.mark.parametrize("role", ["user", "chief-service", "technicien", "chef-division-support", "admin"])
async def test_accessible_a_tous_les_roles_connectes(auth_client, role):
    """La page Profil est commune à tous les rôles : aucun n'est exclu."""
    async with auth_client("user") as client:
        with patch("api.core.central_auth.get_machine_token", new=AsyncMock(return_value="tok")), \
             patch("api.core.central_auth.reset_central_password", new=AsyncMock()):
            resp = await _post(
                client,
                {"new_password": "NouveauMdp123", "confirm_password": "NouveauMdp123"},
                _actor(role=role),
            )
    assert resp.status_code == 200, resp.text
