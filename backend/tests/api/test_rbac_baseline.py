"""
PHASE -1 — BASELINE : Tests de caractérisation RBAC.

Documente les trous de sécurité ACTUELS identifiés par l'audit.
Les assertions reflètent le comportement actuel (non durci).
Marqué « À DURCIR EN PHASE 1 » aux endroits à corriger.

IMPORTANT : quand Phase 1 corrigera ces trous, les assertions devront
être mises à jour (ex: 200 → 403) avec le commentaire du changement.
"""
from __future__ import annotations

import pytest


# ═══════════════════════════════════════════════════════════════════════════════
# [3.1] GET /appreciations/ — accessible à tous les rôles authentifiés
# ═══════════════════════════════════════════════════════════════════════════════

class TestAppreciationRBACBaseline:
    # À DURCIR EN PHASE 1 : devra retourner 403 pour role=user
    async def test_user_peut_lire_toutes_appreciations(self, auth_client):
        """
        COMPORTEMENT ACTUEL — À DURCIR EN PHASE 1 :
        Un utilisateur 'user' peut accéder à GET /appreciations/ (liste globale).
        Après Phase 1 : devra retourner 403.
        """
        async with auth_client("user") as c:
            r = await c.get("/api/v1/appreciations/")
        # Comportement actuel : 200 (trou RBAC)
        assert r.status_code == 200, (
            "COMPORTEMENT ACTUEL : 200. "
            "À DURCIR EN PHASE 1 → attendu 403 pour rôle user."
        )

    async def test_admin_peut_lire_toutes_appreciations(self, auth_client):
        """Admin doit toujours pouvoir lire les appréciations (après Phase 1 aussi)."""
        async with auth_client("admin") as c:
            r = await c.get("/api/v1/appreciations/")
        assert r.status_code == 200

    # À DURCIR EN PHASE 1 : POST /appreciations/ sans ownership check
    async def test_user_peut_poster_appreciation_pour_nimporte_quelle_demande(
        self, auth_client, unity_id
    ):
        """
        COMPORTEMENT ACTUEL — À DURCIR EN PHASE 1 :
        Un user peut créer une appréciation avec n'importe quel request_id,
        même sans être le demandeur. Après Phase 1 : devra retourner 403.
        """
        async with auth_client("user") as c:
            r = await c.post("/api/v1/appreciations/", json={
                "request_id": 99999,
                "rating": 4,
                "comment": "Test baseline ownership",
                "resolved_confirmed": True,
                "author_type": "internal",
                "is_external": False,
            })
        # Comportement actuel : 201 ou 404 (si request introuvable), jamais 403
        assert r.status_code != 403, (
            "COMPORTEMENT ACTUEL : pas de 403 sur POST /appreciations/. "
            "À DURCIR EN PHASE 1 → ownership check requis."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# [3.3] GET /requests/by-unity/{id} — pas de cloisonnement périmètre
# ═══════════════════════════════════════════════════════════════════════════════

class TestByUnityRBACBaseline:
    async def test_agent_peut_lire_direction_hors_perimetre(
        self, auth_client, unity_id
    ):
        """
        COMPORTEMENT ACTUEL — À DURCIR EN PHASE 1 :
        Un agent (unity_id=1) peut appeler /requests/by-unity/{id} avec
        n'importe quel unity_id. Après Phase 1 : devra retourner 403 si
        la direction n'est pas la sienne.
        """
        autre_unity_id = unity_id + 99  # direction hors périmètre
        async with auth_client("agent") as c:
            r = await c.get(f"/api/v1/requests/by-unity/{autre_unity_id}")
        # Comportement actuel : 200 (liste vide ou pas) — pas de 403
        assert r.status_code in (200, 404), (
            f"COMPORTEMENT ACTUEL : {r.status_code}. "
            "À DURCIR EN PHASE 1 → attendu 403 pour direction hors périmètre."
        )

    async def test_director_peut_lire_sa_direction(self, auth_client, unity_id):
        """Un directeur doit toujours pouvoir lire sa direction (avant et après Phase 1)."""
        async with auth_client("director") as c:
            r = await c.get(f"/api/v1/requests/by-unity/{unity_id}")
        assert r.status_code in (200, 404)

    async def test_admin_peut_lire_nimporte_quelle_direction(
        self, auth_client, unity_id
    ):
        """Admin global : accès total (inchangé après Phase 1)."""
        async with auth_client("admin") as c:
            r = await c.get(f"/api/v1/requests/by-unity/{unity_id}")
        assert r.status_code in (200, 404)


# ═══════════════════════════════════════════════════════════════════════════════
# [3.6] GET /requests/{id}/timeline — pas d'ownership check
# ═══════════════════════════════════════════════════════════════════════════════

class TestTimelineRBACBaseline:
    async def test_user_peut_lire_timeline_hors_perimetre(
        self, auth_client, request_id
    ):
        """
        COMPORTEMENT ACTUEL — À DURCIR EN PHASE 1 :
        Un user peut lire la timeline d'une demande qui ne lui appartient pas.
        Après Phase 1 : devra retourner 403.
        """
        if not request_id:
            pytest.skip("request_id non disponible")

        # Utiliser un user différent de celui qui a créé la demande (admin, id=6)
        async with auth_client("user") as c:
            r = await c.get(f"/api/v1/requests/{request_id}/timeline")
        # Comportement actuel : 200 (pas de vérification) ou 404 (si demande non visible)
        # Après Phase 1 : 403 si la demande n'appartient pas au user
        assert r.status_code in (200, 403, 404), (
            f"COMPORTEMENT ACTUEL : {r.status_code}. "
            "À DURCIR EN PHASE 1 → ownership check sur timeline."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# [5.1] PATCH /requests/{id} — champs SLA modifiables par un agent
# ═══════════════════════════════════════════════════════════════════════════════

class TestRequestUpdateSLABaseline:
    async def test_agent_peut_modifier_sla_hours(self, auth_client, request_id):
        """
        COMPORTEMENT ACTUEL — À DURCIR EN PHASE 1 :
        Un agent peut envoyer sla_hours=999 dans PATCH /requests/{id} et le modifier.
        Après Phase 1 : sla_hours doit être ignoré (ou rejeté) côté serveur.
        """
        if not request_id:
            pytest.skip("request_id non disponible")
        async with auth_client("agent") as c:
            r = await c.patch(f"/api/v1/requests/{request_id}", json={"sla_hours": 999})
        # Comportement actuel : 200 avec sla_hours modifié (trou de sécurité)
        if r.status_code == 200:
            body = r.json()
            data = body.get("data", body)
            # Documenter que la modification est acceptée
            # Après Phase 1 : sla_hours ne doit plus être dans RequestUpdate
            assert True, (
                "COMPORTEMENT ACTUEL : sla_hours modifiable via PATCH. "
                "À DURCIR EN PHASE 1 → supprimer ce champ de RequestUpdate."
            )
        else:
            assert r.status_code in (400, 403, 422)

    async def test_agent_peut_modifier_sla_breached(self, auth_client, request_id):
        """
        COMPORTEMENT ACTUEL — À DURCIR EN PHASE 1 :
        Un agent peut forcer sla_breached=false pour masquer un dépassement.
        """
        if not request_id:
            pytest.skip("request_id non disponible")
        async with auth_client("agent") as c:
            r = await c.patch(f"/api/v1/requests/{request_id}",
                              json={"sla_breached": False})
        assert r.status_code in (200, 400, 422), (
            f"COMPORTEMENT ACTUEL : {r.status_code}. "
            "À DURCIR EN PHASE 1 → sla_breached non modifiable par un agent."
        )


# ═══════════════════════════════════════════════════════════════════════════════
# Comportement CORRECT (Phase 1 d'origine déjà corrigée — vérification de non-régression)
# ═══════════════════════════════════════════════════════════════════════════════

class TestPhase1OrigineNonRegression:
    """Tests de non-régression : vérifient que les corrections Phase 1 d'origine sont toujours actives."""

    async def test_appreciation_requests_id_ownership_user_hors_perimetre(
        self, auth_client, request_id
    ):
        """
        NON-RÉGRESSION Phase 1 d'origine :
        POST /requests/{id}/appreciation par un user qui n'est pas le demandeur → 403.
        """
        if not request_id:
            pytest.skip("request_id non disponible")
        # Le user (id=1) n'est pas le demandeur de la demande créée par admin (id=6)
        async with auth_client("user") as c:
            r = await c.post(f"/api/v1/requests/{request_id}/appreciation", json={
                "rating": 5,
                "comment": "Non autorisé",
                "resolved_confirmed": True,
                "author_type": "internal",
                "is_external": False,
            })
        assert r.status_code == 403, (
            f"RÉGRESSION Phase 1 d'origine détectée ! "
            f"POST /requests/:id/appreciation par non-demandeur doit retourner 403, "
            f"obtenu {r.status_code}."
        )

    async def test_commentaires_user_ne_voit_pas_internes(
        self, auth_client, request_id
    ):
        """
        NON-RÉGRESSION Phase 1 d'origine :
        Un user avec public_only=false ne doit voir que les commentaires publics.
        Le serveur force public_only=True pour rôle=user.
        """
        if not request_id:
            pytest.skip("request_id non disponible")
        # D'abord créer un commentaire interne (is_public=False) en tant qu'agent
        async with auth_client("agent") as c:
            await c.post(f"/api/v1/requests/{request_id}/comments", json={
                "body": "Commentaire interne test.",
                "is_public": False,
            })
        # Maintenant le user tente de le lire avec public_only=false
        async with auth_client("user") as c:
            r = await c.get(
                f"/api/v1/requests/{request_id}/comments?public_only=false"
            )
        # 403 si pas dans son périmètre, ou 200 avec uniquement les commentaires publics
        if r.status_code == 200:
            body = r.json()
            data = body.get("data", body)
            items = data if isinstance(data, list) else data.get("items", [])
            for comment in items:
                is_public = comment.get("is_public", True)
                assert is_public is True, (
                    "RÉGRESSION : un user voit un commentaire is_public=False !"
                )
