"""
Tests d'authentification — plateforme centrale manager-user.

La plateforme centrale n'est jamais appelée en test : `mock_central_auth`
(voir conftest.py) simule source-token/login/refresh/scopes/groupes en
mémoire. Les comptes locaux "rattachés" sont seedés directement en DB de
test avec un `central_user_id` correspondant à l'identité centrale simulée.
"""
from __future__ import annotations

import pytest

from tests.conftest import _TestSession


async def _create_linked_account(
    *, email: str, role: str, central_user_id: int, account_status: str = "active",
) -> None:
    from api.models.ModelAccount import Account
    async with _TestSession() as session:
        acc = Account()
        acc.name = f"Test {role}"
        acc.email = email
        acc.role = role
        acc.status = True
        acc.account_status = account_status
        acc.central_user_id = central_user_id
        session.add(acc)
        await session.commit()


# ═══════════════════════════════════════════════════════════════════════════════
# Auth — accès non authentifié
# ═══════════════════════════════════════════════════════════════════════════════

class TestUnauthenticated:
    async def test_health_accessible_sans_token(self, anon_client):
        """GET /health est accessible publiquement."""
        r = await anon_client.get("/health")
        assert r.status_code == 200

    async def test_route_protegee_sans_token_retourne_401(self, anon_client):
        """Toute route protégée sans token doit retourner 401."""
        r = await anon_client.get("/api/v1/requests/")
        assert r.status_code == 401

    async def test_me_sans_token_retourne_401(self, anon_client):
        r = await anon_client.get("/api/v1/auth/me")
        assert r.status_code == 401

    async def test_notifications_sans_token_retourne_401(self, anon_client):
        r = await anon_client.get("/api/v1/notifications/")
        assert r.status_code == 401

    async def test_users_sans_token_retourne_401(self, anon_client):
        r = await anon_client.get("/api/v1/users/")
        assert r.status_code == 401

    async def test_appreciations_sans_token_retourne_401(self, anon_client):
        r = await anon_client.get("/api/v1/appreciations/")
        assert r.status_code == 401


# ═══════════════════════════════════════════════════════════════════════════════
# Auth — inscription publique (central-first, rôle forcé "user")
# ═══════════════════════════════════════════════════════════════════════════════

class TestRegisterEndpoint:
    async def test_register_succes_retourne_compte_role_user(self, anon_client, mock_central_auth):
        r = await anon_client.post("/api/v1/auth/register", json={
            "name": "Test",
            "firstname": "Public",
            "email": "public.register@test.edg.gn",
            "password": "Password123!",
        })
        assert r.status_code == 201
        body = r.json().get("data", r.json())
        assert body["role"] == "user"
        assert body["central_user_id"] is not None

    async def test_register_email_deja_utilise_retourne_409(self, anon_client, mock_central_auth):
        payload = {
            "name": "Test", "email": "duplicate.register@test.edg.gn", "password": "Password123!",
        }
        first = await anon_client.post("/api/v1/auth/register", json=payload)
        assert first.status_code == 201
        second = await anon_client.post("/api/v1/auth/register", json=payload)
        assert second.status_code == 409

    async def test_register_mot_de_passe_trop_court_retourne_422(self, anon_client):
        r = await anon_client.post("/api/v1/auth/register", json={
            "name": "Test", "email": "short.pwd@test.edg.gn", "password": "short",
        })
        assert r.status_code == 422

    async def test_register_ignore_role_envoye_par_le_client(self, anon_client, mock_central_auth):
        """C-01 — l'auto-élévation via le payload d'inscription est impossible."""
        r = await anon_client.post("/api/v1/auth/register", json={
            "name": "Test", "email": "no.escalation@test.edg.gn", "password": "Password123!",
            "role": "admin",
        })
        assert r.status_code == 201
        body = r.json().get("data", r.json())
        assert body["role"] == "user"


# ═══════════════════════════════════════════════════════════════════════════════
# Auth — login (relais central)
# ═══════════════════════════════════════════════════════════════════════════════

class TestLoginEndpoint:
    async def test_login_identifiants_invalides_retourne_401(self, anon_client, mock_central_auth):
        """Un email/mot de passe rejeté par le central retourne 401."""
        r = await anon_client.post("/api/v1/auth/login", json={
            "identifier": "inexistant@test.edg",
            "password": "WrongPassword123!",
        })
        assert r.status_code == 401

    async def test_login_champs_manquants_retourne_422(self, anon_client):
        """Body incomplet doit retourner 422."""
        r = await anon_client.post("/api/v1/auth/login", json={"identifier": "x"})
        assert r.status_code == 422

    async def test_login_compte_non_rattache_retourne_401(self, anon_client, mock_central_auth, setup_db):
        """
        Identifiants valides côté central mais aucun compte local avec ce
        central_user_id → 401 explicite (pas de rattachement automatique).
        """
        mock_central_auth.register(
            email="orphan@test.edg.gn", password="Pwd123!", user_id=9001,
        )
        r = await anon_client.post("/api/v1/auth/login", json={
            "identifier": "orphan@test.edg.gn",
            "password": "Pwd123!",
        })
        assert r.status_code == 401

    async def test_login_succes_retourne_tokens_et_role_mappe(self, anon_client, mock_central_auth, setup_db):
        """
        Compte local pré-rattaché (central_user_id) + groupe central actif
        mappé sur un rôle du sous-ensemble synchronisable → login réussi,
        tokens renvoyés, rôle synchronisé.
        """
        await _create_linked_account(email="agent@test.edg.gn", role="user", central_user_id=9002)
        mock_central_auth.register(
            email="agent@test.edg.gn", password="Pwd123!", user_id=9002,
            groups=["qualify-support"],
        )

        r = await anon_client.post("/api/v1/auth/login", json={
            "identifier": "agent@test.edg.gn",
            "password": "Pwd123!",
        })
        assert r.status_code == 200
        body = r.json()
        data = body.get("data", body)
        assert data["access_token"]
        assert data["refresh_token"]
        assert data["user"]["role"] == "agent-support"  # qualify-support -> agent-support

    async def test_login_compte_inactif_retourne_401(self, anon_client, mock_central_auth, setup_db):
        """
        Compte local rattaché mais `account_status != "active"` (désactivé via le
        backoffice, indépendamment du flag générique `status`) → login refusé,
        même si les identifiants sont valides côté central.
        """
        await _create_linked_account(
            email="inactive@test.edg.gn", role="user", central_user_id=9010,
            account_status="inactive",
        )
        mock_central_auth.register(email="inactive@test.edg.gn", password="Pwd123!", user_id=9010)

        r = await anon_client.post("/api/v1/auth/login", json={
            "identifier": "inactive@test.edg.gn",
            "password": "Pwd123!",
        })
        assert r.status_code == 401

    async def test_session_active_bloquee_apres_desactivation(self, anon_client, mock_central_auth, setup_db):
        """
        Un compte désactivé (`account_status="inactive"`) en cours de session doit
        être rejeté dès sa prochaine requête authentifiée — pas seulement au login,
        `resolve_central_account` gate aussi `get_current_user`.
        """
        await _create_linked_account(
            email="live-deactivate@test.edg.gn", role="user", central_user_id=9011,
        )
        mock_central_auth.register(email="live-deactivate@test.edg.gn", password="Pwd123!", user_id=9011)

        login_r = await anon_client.post("/api/v1/auth/login", json={
            "identifier": "live-deactivate@test.edg.gn", "password": "Pwd123!",
        })
        assert login_r.status_code == 200
        access_token = login_r.json().get("data", login_r.json())["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        me_r = await anon_client.get("/api/v1/auth/me", headers=headers)
        assert me_r.status_code == 200

        from api.models.ModelAccount import Account
        from sqlalchemy import update
        async with _TestSession() as session:
            await session.execute(
                update(Account).where(Account.central_user_id == 9011).values(account_status="inactive")
            )
            await session.commit()

        me_after_r = await anon_client.get("/api/v1/auth/me", headers=headers)
        assert me_after_r.status_code == 401

    async def test_login_matricule_resolu_en_email_avant_appel_central(
        self, anon_client, mock_central_auth, setup_db,
    ):
        """Un identifiant non-email est résolu en email local (matricule) avant l'appel central."""
        from api.models.ModelAccount import Account
        async with _TestSession() as session:
            acc = Account()
            acc.name = "Test Matricule"
            acc.email = "matricule@test.edg.gn"
            acc.matricule = "M12345"
            acc.role = "user"
            acc.status = True
            acc.central_user_id = 9003
            session.add(acc)
            await session.commit()

        mock_central_auth.register(
            email="matricule@test.edg.gn", password="Pwd123!", user_id=9003,
        )

        r = await anon_client.post("/api/v1/auth/login", json={
            "identifier": "M12345",
            "password": "Pwd123!",
        })
        assert r.status_code == 200


# ═══════════════════════════════════════════════════════════════════════════════
# Auth — refresh token (relais central)
# ═══════════════════════════════════════════════════════════════════════════════

class TestRefreshEndpoint:
    async def test_refresh_token_invalide_retourne_401(self, anon_client, mock_central_auth):
        r = await anon_client.post("/api/v1/auth/refresh", json={"refresh_token": "fake"})
        assert r.status_code == 401

    async def test_refresh_champs_manquants_retourne_422(self, anon_client):
        r = await anon_client.post("/api/v1/auth/refresh", json={})
        assert r.status_code == 422

    async def test_refresh_succes_retourne_nouvel_access_token(
        self, anon_client, mock_central_auth, setup_db,
    ):
        await _create_linked_account(email="refresh@test.edg.gn", role="user", central_user_id=9004)
        mock_central_auth.register(email="refresh@test.edg.gn", password="Pwd123!", user_id=9004)

        login_r = await anon_client.post("/api/v1/auth/login", json={
            "identifier": "refresh@test.edg.gn", "password": "Pwd123!",
        })
        refresh_token = login_r.json()["data" if "data" in login_r.json() else "refresh_token"]
        if isinstance(refresh_token, dict):
            refresh_token = refresh_token["refresh_token"]

        r = await anon_client.post("/api/v1/auth/refresh", json={"refresh_token": refresh_token})
        assert r.status_code == 200
        assert r.json().get("data", r.json())["access_token"]


# ═══════════════════════════════════════════════════════════════════════════════
# Auth — me / me/scopes / me/groups
# ═══════════════════════════════════════════════════════════════════════════════

class TestMeEndpoints:
    async def test_me_scopes_sans_token_retourne_401(self, anon_client):
        r = await anon_client.get("/api/v1/auth/me/scopes")
        assert r.status_code == 401

    async def test_me_groups_sans_token_retourne_401(self, anon_client):
        r = await anon_client.get("/api/v1/auth/me/groups")
        assert r.status_code == 401

    async def test_me_scopes_et_groups_relayes_apres_login(
        self, anon_client, mock_central_auth, setup_db,
    ):
        await _create_linked_account(email="scopes@test.edg.gn", role="admin", central_user_id=9005)
        mock_central_auth.register(
            email="scopes@test.edg.gn", password="Pwd123!", user_id=9005,
            groups=["admin-support"],
        )
        login_r = await anon_client.post("/api/v1/auth/login", json={
            "identifier": "scopes@test.edg.gn", "password": "Pwd123!",
        })
        access_token = login_r.json().get("data", login_r.json())["access_token"]
        headers = {"Authorization": f"Bearer {access_token}"}

        scopes_r = await anon_client.get("/api/v1/auth/me/scopes", headers=headers)
        assert scopes_r.status_code == 200
        assert scopes_r.json().get("data", scopes_r.json())["user_id"] == 9005

        groups_r = await anon_client.get("/api/v1/auth/me/groups", headers=headers)
        assert groups_r.status_code == 200
        groups_body = groups_r.json().get("data", groups_r.json())
        assert any(g["codename"] == "admin-support" for g in groups_body)


# ═══════════════════════════════════════════════════════════════════════════════
# Auth — logout
# ═══════════════════════════════════════════════════════════════════════════════

class TestLogout:
    async def test_logout_sans_token_retourne_204(self, anon_client):
        """Logout sans session active reste un no-op silencieux (204)."""
        r = await anon_client.post("/api/v1/auth/logout", json={"refresh_token": "fake"})
        assert r.status_code == 204
