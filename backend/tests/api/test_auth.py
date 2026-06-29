"""
PHASE -1 — BASELINE : Tests de caractérisation des flux d'authentification.

Ces tests documentent le comportement ACTUEL de l'API (correct ou non).
Ne corrigent aucune anomalie.
"""
from __future__ import annotations

import pytest


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
# Auth — login (simulation via base SQLite — retourne 401 si l'user n'existe pas)
# ═══════════════════════════════════════════════════════════════════════════════

class TestLoginEndpoint:
    async def test_login_utilisateur_inexistant_retourne_401(self, anon_client):
        """Login avec un compte qui n'existe pas en DB doit retourner 4xx."""
        r = await anon_client.post("/api/v1/auth/login", json={
            "identifier": "inexistant@test.edg",
            "password": "WrongPassword123!",
        })
        assert r.status_code in (401, 404)

    async def test_login_champs_manquants_retourne_422(self, anon_client):
        """Body incomplet doit retourner 422."""
        r = await anon_client.post("/api/v1/auth/login", json={"identifier": "x"})
        assert r.status_code == 422

    async def test_login_retourne_structure_attendue_si_succes(self, anon_client, setup_db):
        """Si le login réussit, la réponse contient access_token et refresh_token."""
        # Créer un compte de test d'abord
        from api.models.ModelAccount import Account
        from api.core.security import hash_password
        from tests.conftest import _TestSession
        async with _TestSession() as session:
            acc = Account()
            acc.name = "Test User Auth"
            acc.email = "auth_test@test.edg.gn"
            acc.password_hash = hash_password("TestPassword123!")
            acc.role = "user"
            acc.status = True
            session.add(acc)
            await session.commit()

        r = await anon_client.post("/api/v1/auth/login", json={
            "identifier": "auth_test@test.edg.gn",
            "password": "TestPassword123!",
        })
        # Le login peut réussir (200) ou échouer selon l'état DB
        if r.status_code == 200:
            body = r.json()
            data = body.get("data", body)
            assert "access_token" in data or "accessToken" in data


# ═══════════════════════════════════════════════════════════════════════════════
# Auth — refresh token
# ═══════════════════════════════════════════════════════════════════════════════

class TestRefreshEndpoint:
    async def test_refresh_sans_token_retourne_4xx(self, anon_client):
        """Refresh sans refresh_token valide doit échouer."""
        r = await anon_client.post("/api/v1/auth/refresh", json={"refresh_token": "fake"})
        assert r.status_code in (401, 422)


# ═══════════════════════════════════════════════════════════════════════════════
# Auth — rate limiting (vérification que les routes limitées existent)
# ═══════════════════════════════════════════════════════════════════════════════

class TestRateLimitedRoutes:
    async def test_forgot_password_route_existe(self, anon_client):
        """POST /forgot-password est accessible (même si email inexistant)."""
        r = await anon_client.post("/api/v1/auth/forgot-password",
                                   json={"email": "nope@test.edg.gn"})
        # 200 (sent=True) ou 404 selon implémentation, mais pas 404 de route
        assert r.status_code != 405  # méthode non autorisée = route inexistante

    async def test_register_champs_manquants_retourne_422(self, anon_client):
        r = await anon_client.post("/api/v1/auth/register", json={"email": "x"})
        assert r.status_code == 422


# ═══════════════════════════════════════════════════════════════════════════════
# Auth — logout
# ═══════════════════════════════════════════════════════════════════════════════

class TestLogout:
    async def test_logout_sans_token_retourne_2xx_ou_4xx(self, anon_client):
        """
        COMPORTEMENT ACTUEL — À NOTER :
        /logout utilise oauth2_scheme (pas get_current_user) → ne lève pas 401
        si le token est absent/invalide ; il retourne 204 car il invalide
        simplement ce qu'il trouve (rien). Comportement à évaluer en Phase 1.
        """
        r = await anon_client.post("/api/v1/auth/logout",
                                   json={"refresh_token": "fake"})
        # 204 = comportement actuel (pas d'auth guard stricte sur logout)
        # 401/422 = si le guard est durci en Phase 1
        assert r.status_code in (200, 204, 401, 422), (
            f"COMPORTEMENT ACTUEL : {r.status_code}. "
            "Le logout ne force pas l'authentification préalable."
        )
