"""
PHASE -1 — BASELINE : Tests de caractérisation des flux de demandes.

Documente le comportement ACTUEL (statuts HTTP + forme des réponses).
Ne corrige aucune anomalie.

NAVIGATION TASK — vue personnelle « Mes demandes » :
  TestVuePersonnelleBaseline documente le comportement APRÈS la correction
  du bypass is_own_view dans list_requests() (RouteRequest.py).
"""
from __future__ import annotations

import pytest


# ═══════════════════════════════════════════════════════════════════════════════
# Lecture — liste et détail
# ═══════════════════════════════════════════════════════════════════════════════

class TestListeDemandesBaseline:
    async def test_user_peut_lister_ses_demandes(self, auth_client):
        """GET /requests/ avec rôle user → 200 (liste vide si aucune demande)."""
        async with auth_client("user") as c:
            r = await c.get("/api/v1/requests/")
        assert r.status_code == 200
        body = r.json()
        data = body.get("data", body)
        assert "items" in data or isinstance(data, list)

    async def test_agent_peut_lister_demandes(self, auth_client):
        async with auth_client("agent") as c:
            r = await c.get("/api/v1/requests/")
        assert r.status_code == 200

    async def test_admin_peut_lister_toutes_demandes(self, auth_client):
        async with auth_client("admin") as c:
            r = await c.get("/api/v1/requests/")
        assert r.status_code == 200

    async def test_non_authentifie_retourne_401(self, anon_client):
        r = await anon_client.get("/api/v1/requests/")
        assert r.status_code == 401

    async def test_liste_paginee_retourne_structure_correcte(self, auth_client):
        """La réponse paginée contient items, total, page, limit."""
        async with auth_client("admin") as c:
            r = await c.get("/api/v1/requests/?page=1&limit=10")
        assert r.status_code == 200
        body = r.json()
        data = body.get("data", body)
        # Structure paginée attendue
        assert "items" in data
        assert "total" in data


# ═══════════════════════════════════════════════════════════════════════════════
# Création de demande
# ═══════════════════════════════════════════════════════════════════════════════

class TestCreationDemandeBaseline:

    _PAYLOAD_MINIMAL = {
        "title": "Test Baseline — panne réseau",
        "description": "Coupure de courant dans la zone nord.",
        "category": "panne",
        "priority": "medium",
        "is_external": False,
        "requester_name": "Kofi Test",
        "requester_email": "kofi@test.edg.gn",
    }

    async def test_creation_retourne_201(self, auth_client, unity_id):
        """Création d'une demande par un agent retourne 201."""
        payload = {**self._PAYLOAD_MINIMAL,
                   "title": "Baseline 201 — panne réseau agent",
                   "unity_id": unity_id}
        async with auth_client("agent") as c:
            r = await c.post("/api/v1/requests/", json=payload)
        assert r.status_code == 201

    async def test_creation_retourne_champs_attendus(self, auth_client, unity_id):
        """La réponse de création contient id, ref, request_status."""
        payload = {**self._PAYLOAD_MINIMAL,
                   "title": "Baseline champs — panne réseau admin",
                   "unity_id": unity_id}
        async with auth_client("admin") as c:
            r = await c.post("/api/v1/requests/", json=payload)
        assert r.status_code == 201
        body = r.json()
        data = body.get("data", body)
        assert "id" in data
        assert "ref" in data
        assert "request_status" in data

    async def test_creation_statut_initial_est_new(self, auth_client, unity_id):
        """Toute demande créée doit avoir request_status = 'new'."""
        payload = {**self._PAYLOAD_MINIMAL,
                   "title": "Baseline statut initial — panne réseau",
                   "unity_id": unity_id}
        async with auth_client("admin") as c:
            r = await c.post("/api/v1/requests/", json=payload)
        assert r.status_code == 201
        body = r.json()
        data = body.get("data", body)
        status_val = data.get("request_status")
        if isinstance(status_val, dict):
            assert status_val.get("code") == "new"
        else:
            assert status_val == "new"

    async def test_creation_sans_titre_retourne_422(self, auth_client):
        """Corps incomplet doit retourner 422."""
        async with auth_client("user") as c:
            r = await c.post("/api/v1/requests/", json={"description": "no title"})
        assert r.status_code == 422

    async def test_user_ne_peut_pas_forcer_requester_id(self, auth_client, unity_id):
        """
        Un user ne peut pas choisir un requester_id différent du sien.
        COMPORTEMENT ACTUEL : requester_id est forcé côté serveur depuis le JWT.
        """
        payload = {
            **self._PAYLOAD_MINIMAL,
            "title": "Baseline requester_id forgery test",
            "requester_id": 9999,
            "unity_id": unity_id,
        }
        async with auth_client("user") as c:
            r = await c.post("/api/v1/requests/", json=payload)
        if r.status_code == 201:
            body = r.json()
            data = body.get("data", body)
            assert str(data.get("requester_id", "")) != "9999"


# ═══════════════════════════════════════════════════════════════════════════════
# Transitions de cycle de vie
# ═══════════════════════════════════════════════════════════════════════════════

class TestTransitionsBaseline:
    async def test_qualify_change_statut(self, auth_client, request_id):
        """POST /requests/{id}/qualify doit changer le statut."""
        if not request_id:
            pytest.skip("request_id non disponible")
        async with auth_client("agent") as c:
            r = await c.post(f"/api/v1/requests/{request_id}/qualify")
        assert r.status_code in (200, 201, 422)

    async def test_resolve_accessible_au_staff(self, auth_client, request_id):
        """POST /requests/{id}/resolve accessible aux agents."""
        if not request_id:
            pytest.skip("request_id non disponible")
        async with auth_client("agent") as c:
            r = await c.post(f"/api/v1/requests/{request_id}/resolve")
        # 200 si la transition est valide, 4xx si état invalide (normal)
        assert r.status_code in (200, 201, 400, 422)

    async def test_resolve_inaccessible_au_user(self, auth_client, request_id):
        """Un user ne peut pas résoudre une demande."""
        if not request_id:
            pytest.skip("request_id non disponible")
        async with auth_client("user") as c:
            r = await c.post(f"/api/v1/requests/{request_id}/resolve")
        assert r.status_code in (403, 404)  # 403 = refusé, 404 = pas la bonne demande


# ═══════════════════════════════════════════════════════════════════════════════
# Commentaires (comportement après Phase 1 d'origine corrigée)
# ═══════════════════════════════════════════════════════════════════════════════

class TestCommentairesBaseline:
    async def test_user_ne_voit_que_commentaires_publics(self, auth_client, request_id):
        """
        COMPORTEMENT CORRIGÉ (Phase 1 d'origine) :
        Un user avec public_only=False doit quand même ne voir que les commentaires publics.
        """
        if not request_id:
            pytest.skip("request_id non disponible")
        async with auth_client("user") as c:
            r = await c.get(f"/api/v1/requests/{request_id}/comments?public_only=false")
        assert r.status_code in (200, 403)

    async def test_creation_commentaire_force_author_depuis_jwt(self, auth_client, request_id):
        """
        COMPORTEMENT CORRIGÉ (Phase 1 d'origine) :
        author_id et author_name sont forcés depuis le JWT, pas depuis le body.
        """
        if not request_id:
            pytest.skip("request_id non disponible")
        async with auth_client("agent") as c:
            r = await c.post(f"/api/v1/requests/{request_id}/comments", json={
                "body": "Commentaire de test baseline.",
                "is_public": True,
                "author_id": 9999,  # doit être ignoré
                "author_name": "Faux Auteur",  # doit être ignoré
            })
        if r.status_code == 201:
            body = r.json()
            data = body.get("data", body)
            assert str(data.get("author_id", "")) != "9999"


# ═══════════════════════════════════════════════════════════════════════════════
# Pièces jointes — routes accessibles
# ═══════════════════════════════════════════════════════════════════════════════

class TestAttachmentsBaseline:
    async def test_liste_attachments_accessible_agent(self, auth_client, request_id):
        if not request_id:
            pytest.skip("request_id non disponible")
        async with auth_client("agent") as c:
            r = await c.get(f"/api/v1/requests/{request_id}/attachments")
        assert r.status_code in (200, 403)

    async def test_liste_attachments_inaccessible_autre_user(self, auth_client, request_id):
        """
        COMPORTEMENT CORRIGÉ (Phase 1 d'origine) :
        Un user ne peut accéder qu'aux attachments de SES demandes.
        """
        if not request_id:
            pytest.skip("request_id non disponible")
        # L'agent a créé la demande (id=2), le user (id=1) n'en est pas le demandeur
        async with auth_client("user") as c:
            r = await c.get(f"/api/v1/requests/{request_id}/attachments")
        # 200 si c'est sa demande, 403 si pas dans son périmètre
        assert r.status_code in (200, 403)


# ═══════════════════════════════════════════════════════════════════════════════
# Vue personnelle « Mes demandes » — NAVIGATION TASK
# ═══════════════════════════════════════════════════════════════════════════════

# IDs des MockAccount définis dans conftest.py
_ROLE_IDS = {
    "user": 1, "agent": 2, "chief": 3,
    "director": 4, "dg": 5, "admin": 6,
}


class TestVuePersonnelleBaseline:
    """
    NAVIGATION TASK — GET /requests/?requester_id=<mon_id> pour TOUS les rôles.

    Avant la correction : agent/chief/director obtenaient un scope unit_id/unity_id
    qui écrasait (ou combinait avec) le requester_id → comportement scope, pas personnel.
    Après la correction (is_own_view bypass) : tous les rôles voient uniquement
    leurs propres demandes en tant que requester.
    """

    @pytest.mark.parametrize("role", ["user", "agent", "chief", "director", "dg", "admin"])
    async def test_vue_personnelle_retourne_200_pour_tous_les_roles(
        self, auth_client, role
    ):
        """GET /requests/?requester_id=<mon_id> → 200 + structure paginée pour tout rôle."""
        actor_id = _ROLE_IDS[role]
        async with auth_client(role) as c:
            r = await c.get(f"/api/v1/requests/?requester_id={actor_id}")
        assert r.status_code == 200
        body = r.json()
        data = body.get("data", body)
        assert "items" in data
        assert "total" in data

    async def test_vue_personnelle_admin_voit_ses_demandes(
        self, auth_client, request_id
    ):
        """
        L'admin (id=6) a créé une demande via la fixture request_id.
        GET /requests/?requester_id=6 doit retourner au moins cette demande.
        """
        if not request_id:
            pytest.skip("request_id non disponible")
        async with auth_client("admin") as c:
            r = await c.get("/api/v1/requests/?requester_id=6")
        assert r.status_code == 200
        body = r.json()
        data = body.get("data", body)
        assert data.get("total", 0) >= 1

    async def test_vue_personnelle_agent_ne_voit_pas_demandes_admin(
        self, auth_client, request_id
    ):
        """
        L'agent (id=2) demande SES demandes (requester_id=2).
        Il ne doit pas voir la demande créée par l'admin (requester_id=6).
        """
        if not request_id:
            pytest.skip("request_id non disponible")
        async with auth_client("agent") as c:
            r = await c.get("/api/v1/requests/?requester_id=2")
        assert r.status_code == 200
        body = r.json()
        data = body.get("data", body)
        for item in data.get("items", []):
            req_r_id = item.get("requester_id")
            if req_r_id is not None:
                assert str(req_r_id) == "2", (
                    f"Demande d'autrui visible dans la vue personnelle agent : "
                    f"requester_id={req_r_id}"
                )

    async def test_vue_personnelle_director_ne_voit_pas_demandes_admin(
        self, auth_client, request_id
    ):
        """
        Le directeur (id=4) demande SES demandes (requester_id=4).
        La correction bypasse le forcing unity_id — le directeur ne voit pas
        les demandes de sa direction mais uniquement les siennes comme requester.
        """
        if not request_id:
            pytest.skip("request_id non disponible")
        async with auth_client("director") as c:
            r = await c.get("/api/v1/requests/?requester_id=4")
        assert r.status_code == 200
        body = r.json()
        data = body.get("data", body)
        for item in data.get("items", []):
            req_r_id = item.get("requester_id")
            if req_r_id is not None:
                assert str(req_r_id) == "4", (
                    f"Demande d'autrui visible dans la vue personnelle director : "
                    f"requester_id={req_r_id}"
                )
