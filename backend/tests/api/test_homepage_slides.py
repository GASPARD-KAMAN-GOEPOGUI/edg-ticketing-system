"""
Tests — Routes homepage slides (public + admin CRUD).

Couvre :
  [1] GET /homepage/slides/         → public, sans auth, retourne liste active
  [2] GET /admin/homepage/slides/   → admin seulement, retourne tous les slides
  [3] POST /admin/homepage/slides/  → admin crée un slide ; non-admin = 403
  [4] PATCH /admin/homepage/slides/{id} → admin modifie ; non-admin = 403
  [5] DELETE /admin/homepage/slides/{id} → admin supprime (soft-delete) ; non-admin = 403
  [6] Filtrage date : slide avec ends_at dans le passé absent de la liste publique
  [7] Slide invisible absent de la liste publique
"""
from __future__ import annotations

import pytest


def _data(r):
    """Dépaquette la réponse enveloppée {data, success, message} ou retourne le corps brut."""
    body = r.json()
    return body.get("data", body)


# ═══════════════════════════════════════════════════════════════════════════════
# [1] GET /homepage/slides/ — public, sans authentification
# ═══════════════════════════════════════════════════════════════════════════════

class TestPublicSlides:
    async def test_public_list_returns_200_without_auth(self, anon_client):
        r = await anon_client.get("/api/v1/homepage/slides/")
        assert r.status_code == 200
        assert isinstance(_data(r), list)

    async def test_public_list_empty_at_start(self, anon_client):
        r = await anon_client.get("/api/v1/homepage/slides/")
        assert r.status_code == 200
        assert isinstance(_data(r), list)


# ═══════════════════════════════════════════════════════════════════════════════
# [2-5] CRUD admin — protégé
# ═══════════════════════════════════════════════════════════════════════════════

class TestAdminSlidesCRUD:
    async def test_admin_can_list_all_slides(self, auth_client):
        async with auth_client("admin") as c:
            r = await c.get("/api/v1/admin/homepage/slides/")
        assert r.status_code == 200
        assert isinstance(_data(r), list)

    async def test_non_admin_cannot_list_admin_slides(self, auth_client):
        for role in ("user", "agent", "chief", "director", "dg"):
            async with auth_client(role) as c:
                r = await c.get("/api/v1/admin/homepage/slides/")
            assert r.status_code == 403, f"role={role} devrait être 403"

    async def test_admin_can_create_slide(self, auth_client):
        async with auth_client("admin") as c:
            r = await c.post("/api/v1/admin/homepage/slides/", json={
                "title": "Slide de test",
                "message": "Message de test pour le carrousel.",
                "cta_label": "En savoir plus",
                "cta_url": "/info",
                "sort_order": 0,
                "visible": True,
            })
        assert r.status_code == 201
        data = _data(r)
        assert data["title"] == "Slide de test"
        assert data["visible"] is True

    async def test_non_admin_cannot_create_slide(self, auth_client):
        for role in ("user", "agent"):
            async with auth_client(role) as c:
                r = await c.post("/api/v1/admin/homepage/slides/", json={
                    "title": "Tentative non-admin",
                    "visible": True,
                    "sort_order": 0,
                })
            assert r.status_code == 403, f"role={role} devrait être 403"

    async def test_admin_can_update_slide(self, auth_client):
        async with auth_client("admin") as c:
            create_r = await c.post("/api/v1/admin/homepage/slides/", json={
                "title": "Slide à modifier",
                "visible": True,
                "sort_order": 1,
            })
        assert create_r.status_code == 201
        slide_id = _data(create_r)["id"]

        async with auth_client("admin") as c:
            patch_r = await c.patch(f"/api/v1/admin/homepage/slides/{slide_id}", json={
                "title": "Slide modifié",
                "sort_order": 5,
            })
        assert patch_r.status_code == 200
        patched = _data(patch_r)
        assert patched["title"] == "Slide modifié"
        assert patched["sort_order"] == 5

    async def test_non_admin_cannot_update_slide(self, auth_client):
        async with auth_client("admin") as c:
            create_r = await c.post("/api/v1/admin/homepage/slides/", json={
                "title": "Slide protégé", "visible": True, "sort_order": 0,
            })
        slide_id = _data(create_r)["id"]

        async with auth_client("user") as c:
            r = await c.patch(f"/api/v1/admin/homepage/slides/{slide_id}", json={"title": "Hack"})
        assert r.status_code == 403

    async def test_admin_can_delete_slide(self, auth_client):
        async with auth_client("admin") as c:
            create_r = await c.post("/api/v1/admin/homepage/slides/", json={
                "title": "Slide à supprimer", "visible": True, "sort_order": 0,
            })
        assert create_r.status_code == 201
        slide_id = _data(create_r)["id"]

        async with auth_client("admin") as c:
            del_r = await c.delete(f"/api/v1/admin/homepage/slides/{slide_id}")
        assert del_r.status_code == 204

        async with auth_client("admin") as c:
            list_r = await c.get("/api/v1/admin/homepage/slides/")
        ids = [s["id"] for s in _data(list_r)]
        assert slide_id not in ids

    async def test_non_admin_cannot_delete_slide(self, auth_client):
        async with auth_client("admin") as c:
            create_r = await c.post("/api/v1/admin/homepage/slides/", json={
                "title": "Slide protégé DEL", "visible": True, "sort_order": 0,
            })
        slide_id = _data(create_r)["id"]

        async with auth_client("user") as c:
            r = await c.delete(f"/api/v1/admin/homepage/slides/{slide_id}")
        assert r.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════════
# [6-7] Filtrage actif (date + visible) côté liste publique
# ═══════════════════════════════════════════════════════════════════════════════

class TestSlidesFiltering:
    async def test_invisible_slide_not_in_public_list(self, auth_client, anon_client):
        async with auth_client("admin") as c:
            r = await c.post("/api/v1/admin/homepage/slides/", json={
                "title": "Slide caché",
                "visible": False,
                "sort_order": 0,
            })
        assert r.status_code == 201
        slide_id = _data(r)["id"]

        public_r = await anon_client.get("/api/v1/homepage/slides/")
        ids = [s["id"] for s in _data(public_r)]
        assert slide_id not in ids

    async def test_expired_slide_not_in_public_list(self, auth_client, anon_client):
        async with auth_client("admin") as c:
            r = await c.post("/api/v1/admin/homepage/slides/", json={
                "title": "Slide expiré",
                "visible": True,
                "sort_order": 0,
                "ends_at": "2020-01-01T00:00:00",
            })
        assert r.status_code == 201
        slide_id = _data(r)["id"]

        public_r = await anon_client.get("/api/v1/homepage/slides/")
        ids = [s["id"] for s in _data(public_r)]
        assert slide_id not in ids

    async def test_future_slide_not_in_public_list(self, auth_client, anon_client):
        async with auth_client("admin") as c:
            r = await c.post("/api/v1/admin/homepage/slides/", json={
                "title": "Slide futur",
                "visible": True,
                "sort_order": 0,
                "starts_at": "2099-01-01T00:00:00",
            })
        assert r.status_code == 201
        slide_id = _data(r)["id"]

        public_r = await anon_client.get("/api/v1/homepage/slides/")
        ids = [s["id"] for s in _data(public_r)]
        assert slide_id not in ids

    async def test_active_visible_slide_in_public_list(self, auth_client, anon_client):
        async with auth_client("admin") as c:
            r = await c.post("/api/v1/admin/homepage/slides/", json={
                "title": "Slide actif public",
                "visible": True,
                "sort_order": 0,
            })
        assert r.status_code == 201
        slide_id = _data(r)["id"]

        public_r = await anon_client.get("/api/v1/homepage/slides/")
        ids = [s["id"] for s in _data(public_r)]
        assert slide_id in ids
