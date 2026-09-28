"""
Tests d'authentification — plateforme centrale manager-user.

La plateforme centrale n'est jamais appelée en test : `mock_central_auth`
(voir conftest.py) simule source-token/login/refresh/scopes/groupes en
mémoire. Les comptes locaux "rattachés" sont seedés directement en DB de
test avec un `central_user_id` correspondant à l'identité centrale simulée.
"""
from __future__ import annotations

import asyncio

import pytest

from tests.conftest import _TestSession


async def _flush_background_emails() -> None:
    """Attend la complétion des tâches d'envoi email fire-and-forget déjà
    planifiées (NotificationEmitter._send_email_fire_and_forget), y compris
    celles déclenchées par ServiceAccount (_dispatch_account_email)."""
    from api.services.NotificationEmitter import _background_email_tasks

    if _background_email_tasks:
        await asyncio.gather(*_background_email_tasks, return_exceptions=True)


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

    async def test_login_sans_groupe_support_retourne_needs_consent(
        self, anon_client, mock_central_auth, setup_db,
    ):
        """
        Identifiants valides côté central, aucun compte local avec ce
        central_user_id, ET aucun groupe support central (ni aucun groupe du
        tout) → 200 avec needs_consent=true (pas de 401, pas de compte créé).
        """
        mock_central_auth.register(
            email="orphan@test.edg.gn", password="Pwd123!", user_id=9001,
        )
        r = await anon_client.post("/api/v1/auth/login", json={
            "identifier": "orphan@test.edg.gn",
            "password": "Pwd123!",
        })
        assert r.status_code == 200
        body = r.json().get("data", r.json())
        assert body["needs_consent"] is True
        assert body["email"] == "orphan@test.edg.gn"
        assert body["access_token"]
        assert body["consent_version"]

        from tests.conftest import _TestSession
        from api.models.ModelAccount import Account
        from sqlalchemy import select
        async with _TestSession() as session:
            result = await session.execute(select(Account).where(Account.central_user_id == 9001))
            assert result.scalar_one_or_none() is None

    async def test_login_groupe_dautres_applications_uniquement_retourne_needs_consent(
        self, anon_client, mock_central_auth, setup_db,
    ):
        """Groupes centraux d'autres applications (employe-edg, manager-link-hub)
        uniquement → traité comme "aucun groupe support", needs_consent=true."""
        mock_central_auth.register(
            email="other-app@test.edg.gn", password="Pwd123!", user_id=9020,
            groups=["employe-edg", "manager-link-hub"],
        )
        r = await anon_client.post("/api/v1/auth/login", json={
            "identifier": "other-app@test.edg.gn", "password": "Pwd123!",
        })
        assert r.status_code == 200
        assert r.json().get("data", r.json())["needs_consent"] is True

    async def test_login_groupe_support_desactive_retourne_needs_consent(
        self, anon_client, mock_central_auth, setup_db,
    ):
        """Un groupe support central présent mais is_activated=False ne doit pas
        déclencher l'auto-provisioning — traité comme "aucun groupe support"."""
        mock_central_auth.register(
            email="inactive-group@test.edg.gn", password="Pwd123!", user_id=9021,
            inactive_groups=["collaborateur-support"],
        )
        r = await anon_client.post("/api/v1/auth/login", json={
            "identifier": "inactive-group@test.edg.gn", "password": "Pwd123!",
        })
        assert r.status_code == 200
        assert r.json().get("data", r.json())["needs_consent"] is True

    async def test_login_auto_provisionne_si_groupe_support_deja_present(
        self, anon_client, mock_central_auth, setup_db,
    ):
        """
        Identifiants valides côté central, aucun compte local, MAIS l'utilisateur
        appartient déjà à un groupe support central → auto-provisioning silencieux,
        login réussi directement (pas de needs_consent), rôle mappé depuis le groupe.
        """
        mock_central_auth.register(
            email="already-agent@test.edg.gn", password="Pwd123!", user_id=9022,
            groups=["qualify-support"], name="Camara", firstname="Ibrahim", phone="+224620000001",
        )
        r = await anon_client.post("/api/v1/auth/login", json={
            "identifier": "already-agent@test.edg.gn", "password": "Pwd123!",
        })
        assert r.status_code == 200
        body = r.json().get("data", r.json())
        assert "needs_consent" not in body
        assert body["access_token"]
        assert body["user"]["role"] == "chief-service"
        assert body["user"]["central_user_id"] == 9022
        assert body["user"]["name"] == "Camara"

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
        assert data["user"]["role"] == "chief-service"  # qualify-support -> chief-service

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


# ═══════════════════════════════════════════════════════════════════════════════
# Auth — consentement (rattachement sans groupe support central)
# ═══════════════════════════════════════════════════════════════════════════════

class TestConsentAccept:
    async def _login_needs_consent(self, anon_client, mock_central_auth, *, email: str, user_id: int):
        mock_central_auth.register(email=email, password="Pwd123!", user_id=user_id)
        login_r = await anon_client.post("/api/v1/auth/login", json={
            "identifier": email, "password": "Pwd123!",
        })
        assert login_r.status_code == 200
        body = login_r.json().get("data", login_r.json())
        assert body["needs_consent"] is True
        return body

    async def test_consent_accept_succes_cree_compte_role_user(
        self, anon_client, mock_central_auth, setup_db,
    ):
        consent = await self._login_needs_consent(
            anon_client, mock_central_auth, email="consent-ok@test.edg.gn", user_id=9030,
        )
        r = await anon_client.post(
            "/api/v1/auth/consent/accept",
            headers={"Authorization": f"Bearer {consent['access_token']}"},
            json={
                "refresh_token": consent["refresh_token"],
                "expires_in": consent["expires_in"],
                "consent_version": consent["consent_version"],
                "name": "Diallo",
                "firstname": "Mamadou",
                "phone": "+224620000099",
            },
        )
        assert r.status_code == 200
        body = r.json().get("data", r.json())
        assert body["access_token"] == consent["access_token"]
        assert body["user"]["role"] == "user"
        assert body["user"]["name"] == "Diallo"
        assert body["user"]["central_user_id"] == 9030

        # Rattaché au groupe collaborateur-support côté central (idempotence de
        # groupe déjà garantie par le central — ici on vérifie juste l'appel).
        assert any(g == "collaborateur-support" for _, g in mock_central_auth.added_memberships)

        from tests.conftest import _TestSession
        from api.models.ModelAccount import Account
        from sqlalchemy import select
        async with _TestSession() as session:
            result = await session.execute(select(Account).where(Account.central_user_id == 9030))
            account = result.scalar_one()
            assert account.consent_accepted_at is not None
            assert account.consent_version == consent["consent_version"]

    async def test_consent_accept_idempotent_sur_double_appel(
        self, anon_client, mock_central_auth, setup_db,
    ):
        """Un second appel avec le même bearer (retry réseau / double clic) ne doit
        pas créer un second compte — juste retourner le compte déjà rattaché."""
        consent = await self._login_needs_consent(
            anon_client, mock_central_auth, email="consent-retry@test.edg.gn", user_id=9031,
        )
        payload = {
            "refresh_token": consent["refresh_token"],
            "expires_in": consent["expires_in"],
            "consent_version": consent["consent_version"],
            "name": "Bah", "firstname": "Fatoumata",
        }
        headers = {"Authorization": f"Bearer {consent['access_token']}"}

        first = await anon_client.post("/api/v1/auth/consent/accept", headers=headers, json=payload)
        assert first.status_code == 200
        second = await anon_client.post("/api/v1/auth/consent/accept", headers=headers, json=payload)
        assert second.status_code == 200
        assert (
            first.json().get("data", first.json())["user"]["id"]
            == second.json().get("data", second.json())["user"]["id"]
        )

        from tests.conftest import _TestSession
        from api.models.ModelAccount import Account
        from sqlalchemy import select, func
        async with _TestSession() as session:
            result = await session.execute(
                select(func.count()).select_from(Account).where(Account.central_user_id == 9031)
            )
            assert result.scalar_one() == 1

    async def test_consent_accept_sans_bearer_retourne_401(self, anon_client):
        r = await anon_client.post("/api/v1/auth/consent/accept", json={
            "refresh_token": "x", "expires_in": 180, "consent_version": "1.0", "name": "Test",
        })
        assert r.status_code == 401

    async def test_consent_accept_bearer_invalide_retourne_401(self, anon_client, mock_central_auth):
        r = await anon_client.post(
            "/api/v1/auth/consent/accept",
            headers={"Authorization": "Bearer not-a-real-token"},
            json={"refresh_token": "x", "expires_in": 180, "consent_version": "1.0", "name": "Test"},
        )
        assert r.status_code == 401

    async def test_consent_accept_nom_vide_retourne_422(
        self, anon_client, mock_central_auth, setup_db,
    ):
        consent = await self._login_needs_consent(
            anon_client, mock_central_auth, email="consent-badname@test.edg.gn", user_id=9032,
        )
        r = await anon_client.post(
            "/api/v1/auth/consent/accept",
            headers={"Authorization": f"Bearer {consent['access_token']}"},
            json={
                "refresh_token": consent["refresh_token"],
                "expires_in": consent["expires_in"],
                "consent_version": consent["consent_version"],
                "name": "   ",
            },
        )
        assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════════
# Notification email — compte créé / associé, après validation centrale réelle
# ═══════════════════════════════════════════════════════════════════════════════

class TestAccountValidationEmails:
    """
    Couvre §10 de la demande "notification email post-validation centrale" :
      - Cas 1 (création) : POST /auth/register -> AccountService.create() ->
        email de création seulement après le succès réel de
        central_auth.create_central_account() (mock_central_auth simule ce
        succès ; un échec central lève avant toute persistance locale, donc
        avant tout envoi -- voir test dédié ci-dessous).
      - Cas 2 (association) : login auto-provisioning ET consent/accept ->
        AccountService.provision_from_central() -> email d'association,
        jamais le mot "groupe".
      - Anti-doublon : un compte ne peut être créé deux fois pour le même
        email/central_user_id (contrainte unique) -> un seul envoi possible
        par identité, vérifié explicitement sur les scénarios de retry déjà
        couverts par ailleurs (409 sur email dupliqué, idempotence consent).
      - Erreur d'envoi : ne remet jamais en cause la validation du compte.
    """

    def _patch_created(self, monkeypatch):
        calls: list[dict] = []

        async def _fake_send(to_email, name=""):
            calls.append({"to_email": to_email, "name": name})
            return True

        monkeypatch.setattr("api.core.mailer.send_account_created_email", _fake_send)
        return calls

    def _patch_associated(self, monkeypatch):
        calls: list[dict] = []

        async def _fake_send(to_email, name=""):
            calls.append({"to_email": to_email, "name": name})
            return True

        monkeypatch.setattr("api.core.mailer.send_account_associated_email", _fake_send)
        return calls

    # ── Cas 1 — création ──────────────────────────────────────────────────────

    async def test_register_succes_envoie_email_creation(
        self, anon_client, mock_central_auth, monkeypatch,
    ):
        calls = self._patch_created(monkeypatch)
        r = await anon_client.post("/api/v1/auth/register", json={
            "name": "Test", "firstname": "Creation", "email": "creation.email@test.edg.gn",
            "password": "Password123!",
        })
        assert r.status_code == 201
        await _flush_background_emails()

        assert len(calls) == 1
        assert calls[0]["to_email"] == "creation.email@test.edg.gn"

    async def test_register_echec_central_naucun_email(
        self, anon_client, mock_central_auth, monkeypatch,
    ):
        """Si la plateforme centrale rejette la création (ex. politique de mot de
        passe), AccountService.create() lève avant toute persistance locale —
        aucun compte créé, donc aucun email de succès ne doit être envoyé."""
        calls = self._patch_created(monkeypatch)

        import api.core.central_auth as central_auth_module

        async def _fake_create_central_account_fails(**kwargs):
            raise central_auth_module.CentralValidationError("Politique de mot de passe non respectée.")

        monkeypatch.setattr(central_auth_module, "create_central_account", _fake_create_central_account_fails)

        r = await anon_client.post("/api/v1/auth/register", json={
            "name": "Test", "email": "central-fail@test.edg.gn", "password": "Password123!",
        })
        assert r.status_code >= 400
        await _flush_background_emails()
        assert calls == []

        from api.models.ModelAccount import Account
        from sqlalchemy import select
        async with _TestSession() as session:
            result = await session.execute(select(Account).where(Account.email == "central-fail@test.edg.gn"))
            assert result.scalar_one_or_none() is None

    async def test_register_double_soumission_un_seul_email(
        self, anon_client, mock_central_auth, monkeypatch,
    ):
        """La deuxième tentative de création avec le même email échoue en 409
        (compte déjà créé) avant tout appel central -- un seul email envoyé au total."""
        calls = self._patch_created(monkeypatch)
        payload = {
            "name": "Test", "email": "double.register@test.edg.gn", "password": "Password123!",
        }
        first = await anon_client.post("/api/v1/auth/register", json=payload)
        assert first.status_code == 201
        second = await anon_client.post("/api/v1/auth/register", json=payload)
        assert second.status_code == 409
        await _flush_background_emails()

        assert len(calls) == 1

    async def test_register_echec_smtp_compte_reste_cree(
        self, anon_client, mock_central_auth, monkeypatch,
    ):
        """Un échec temporaire d'envoi (ex. SMTP indisponible) ne doit jamais
        remettre en cause la création/validation du compte -- il reste actif.
        L'erreur est journalisée par _dispatch_account_email() (warning avec
        account_id/email/exception -- voir ServiceAccount.py) ; on vérifie ici
        le comportement observable (tentative faite, compte quand même actif)
        plutôt que le flux stdout du logger (StreamHandler lié à un stdout figé
        à sa création, non fiable à capturer via capsys une fois d'autres tests
        déjà passés par ce logger)."""
        attempts: list[str] = []

        async def _fake_send_raises(to_email, name=""):
            attempts.append(to_email)
            raise RuntimeError("SMTP timeout simulé")

        monkeypatch.setattr("api.core.mailer.send_account_created_email", _fake_send_raises)

        r = await anon_client.post("/api/v1/auth/register", json={
            "name": "Test", "email": "smtp-fail@test.edg.gn", "password": "Password123!",
        })
        assert r.status_code == 201
        await _flush_background_emails()

        assert attempts == ["smtp-fail@test.edg.gn"]

        from api.models.ModelAccount import Account
        from sqlalchemy import select
        async with _TestSession() as session:
            result = await session.execute(select(Account).where(Account.email == "smtp-fail@test.edg.gn"))
            account = result.scalar_one()
            assert account.status is True
            assert account.account_status == "active"

        from api.models.ModelAccount import Account
        from sqlalchemy import select
        async with _TestSession() as session:
            result = await session.execute(select(Account).where(Account.email == "smtp-fail@test.edg.gn"))
            account = result.scalar_one()
            assert account.status is True
            assert account.account_status == "active"

    # ── Cas 2 — association (login auto-provisioning) ────────────────────────

    async def test_login_auto_provision_envoie_email_association(
        self, anon_client, mock_central_auth, setup_db, monkeypatch,
    ):
        calls = self._patch_associated(monkeypatch)
        mock_central_auth.register(
            email="assoc-login@test.edg.gn", password="Pwd123!", user_id=9040,
            groups=["qualify-support"], name="Sow", firstname="Alpha",
        )
        r = await anon_client.post("/api/v1/auth/login", json={
            "identifier": "assoc-login@test.edg.gn", "password": "Pwd123!",
        })
        assert r.status_code == 200
        await _flush_background_emails()

        assert len(calls) == 1
        assert calls[0]["to_email"] == "assoc-login@test.edg.gn"

    # ── Cas 2 — association (consentement explicite) ──────────────────────────

    async def test_consent_accept_envoie_email_association(
        self, anon_client, mock_central_auth, setup_db, monkeypatch,
    ):
        calls = self._patch_associated(monkeypatch)
        mock_central_auth.register(email="assoc-consent@test.edg.gn", password="Pwd123!", user_id=9041)
        login_r = await anon_client.post("/api/v1/auth/login", json={
            "identifier": "assoc-consent@test.edg.gn", "password": "Pwd123!",
        })
        consent = login_r.json().get("data", login_r.json())
        assert consent["needs_consent"] is True

        r = await anon_client.post(
            "/api/v1/auth/consent/accept",
            headers={"Authorization": f"Bearer {consent['access_token']}"},
            json={
                "refresh_token": consent["refresh_token"],
                "expires_in": consent["expires_in"],
                "consent_version": consent["consent_version"],
                "name": "Barry",
            },
        )
        assert r.status_code == 200
        await _flush_background_emails()

        assert len(calls) == 1
        assert calls[0]["to_email"] == "assoc-consent@test.edg.gn"

    async def test_consent_accept_double_appel_un_seul_email(
        self, anon_client, mock_central_auth, setup_db, monkeypatch,
    ):
        """Répétition de la validation (double clic / retry réseau sur le même
        bearer) -- provision_from_central() n'est appelée qu'une fois, le second
        appel emprunte la branche de synchronisation (compte déjà existant)."""
        calls = self._patch_associated(monkeypatch)
        mock_central_auth.register(email="assoc-retry@test.edg.gn", password="Pwd123!", user_id=9042)
        login_r = await anon_client.post("/api/v1/auth/login", json={
            "identifier": "assoc-retry@test.edg.gn", "password": "Pwd123!",
        })
        consent = login_r.json().get("data", login_r.json())
        payload = {
            "refresh_token": consent["refresh_token"],
            "expires_in": consent["expires_in"],
            "consent_version": consent["consent_version"],
            "name": "Diallo",
        }
        headers = {"Authorization": f"Bearer {consent['access_token']}"}

        first = await anon_client.post("/api/v1/auth/consent/accept", headers=headers, json=payload)
        assert first.status_code == 200
        second = await anon_client.post("/api/v1/auth/consent/accept", headers=headers, json=payload)
        assert second.status_code == 200
        await _flush_background_emails()

        assert len(calls) == 1

    # Garde-fou "le mot 'groupe' n'apparaît jamais dans l'email d'association"
    # -> tests/core/test_mailer_templates.py::test_send_account_associated_email_content_ne_mentionne_jamais_groupe
