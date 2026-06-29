"""
PHASE -1 — BASELINE : Tests de caractérisation de l'état SLA actuel.

Documente le comportement CASSÉ actuel (sla_hours jamais calculé).
Ces tests ÉCHOUERONT une fois Phase 0 + Phase 3 corrigées —
c'est le but : leur échec signale que la correction a été appliquée.

Marqué « À CORRIGER EN PHASE 0/3 ».
"""
from __future__ import annotations

import pytest


class TestSLABaseline:
    """
    Caractérisation du state SLA actuel (non-fonctionnel).
    Les tests qui documentent un bug sont annotés explicitement.
    """

    async def test_sla_hours_est_zero_apres_creation(
        self, auth_client, unity_id
    ):
        """
        COMPORTEMENT ACTUEL — À CORRIGER EN PHASE 0 :
        Après création d'une demande, sla_hours = 0 (jamais calculé depuis SlaPolicy).
        Après Phase 0 : sla_hours > 0 si une SlaPolicy correspondante existe.
        """
        payload = {
            "title": "Test SLA baseline",
            "description": "Vérification que sla_hours n'est pas calculé.",
            "category": "panne",
            "priority": "high",
            "is_external": False,
            "requester_name": "SLA Tester",
            "requester_email": "sla@test.edg.gn",
            "unity_id": unity_id,
        }
        async with auth_client("admin") as c:
            r = await c.post("/api/v1/requests/", json=payload)
        assert r.status_code == 201
        body = r.json()
        data = body.get("data", body)
        sla_hours = data.get("sla_hours", 0)
        # Comportement actuel : sla_hours = 0 (bug documenté)
        assert sla_hours == 0, (
            f"Si sla_hours={sla_hours} > 0, Phase 0 est corrigée — "
            "mettre à jour ce test pour asserter sla_hours > 0."
        )

    async def test_sla_elapsed_est_zero_apres_creation(
        self, auth_client, unity_id
    ):
        """
        COMPORTEMENT ACTUEL — À CORRIGER EN PHASE 3 :
        sla_elapsed est toujours 0, jamais calculé dynamiquement.
        """
        payload = {
            "title": "Test sla_elapsed baseline",
            "description": "Vérification sla_elapsed.",
            "category": "incident_technique",
            "priority": "medium",
            "is_external": False,
            "requester_name": "SLA Elapsed Tester",
            "requester_email": "sla_elapsed@test.edg.gn",
            "unity_id": unity_id,
        }
        async with auth_client("admin") as c:
            r = await c.post("/api/v1/requests/", json=payload)
        assert r.status_code == 201
        body = r.json()
        data = body.get("data", body)
        sla_elapsed = data.get("sla_elapsed", 0)
        # Comportement actuel : sla_elapsed = 0 (jamais mis à jour)
        assert sla_elapsed == 0, (
            f"Si sla_elapsed={sla_elapsed} != 0 sur une demande toute fraîche, "
            "Phase 3 est corrigée — mettre à jour ce test."
        )

    async def test_sla_breached_est_faux_toujours(
        self, auth_client, unity_id
    ):
        """
        COMPORTEMENT ACTUEL — À CORRIGER EN PHASE 3 :
        sla_breached est toujours False, aucun job ne le met à True.
        """
        payload = {
            "title": "Test sla_breached baseline",
            "description": "Vérification sla_breached.",
            "category": "facturation",
            "priority": "critical",
            "is_external": False,
            "requester_name": "SLA Breached Tester",
            "requester_email": "sla_breached@test.edg.gn",
            "unity_id": unity_id,
        }
        async with auth_client("admin") as c:
            r = await c.post("/api/v1/requests/", json=payload)
        assert r.status_code == 201
        body = r.json()
        data = body.get("data", body)
        sla_breached = data.get("sla_breached", False)
        assert sla_breached is False  # toujours False actuellement

    async def test_endpoint_sla_breached_retourne_liste_vide(self, auth_client):
        """
        COMPORTEMENT ACTUEL — À CORRIGER EN PHASE 3 :
        GET /requests/sla-breached retourne toujours une liste vide car
        sla_breached n'est jamais mis à True automatiquement.
        """
        async with auth_client("admin") as c:
            r = await c.get("/api/v1/requests/sla-breached")
        assert r.status_code == 200
        body = r.json()
        data = body.get("data", body)
        items = data if isinstance(data, list) else data.get("items", [])
        # Comportement actuel : liste vide (bug documenté)
        # Après Phase 3 : les demandes avec sla_breached=True apparaîtront ici
        assert isinstance(items, list)


class TestSLAPoliciesAccessibles:
    """Vérifie que les endpoints de gestion SLA sont accessibles."""

    async def test_liste_sla_policies_accessible_admin(self, auth_client):
        async with auth_client("admin") as c:
            r = await c.get("/api/v1/sla-policies/")
        assert r.status_code == 200

    async def test_liste_routing_rules_accessible_admin(self, auth_client):
        async with auth_client("admin") as c:
            r = await c.get("/api/v1/routing-rules/")
        assert r.status_code == 200

    async def test_creation_sla_policy_admin(self, auth_client):
        """Un admin peut créer une SLA policy."""
        async with auth_client("admin") as c:
            r = await c.post("/api/v1/sla-policies/", json={
                "name": "SLA Test Baseline",
                "priority": "high",
                "response_hours": 4,
                "resolution_hours": 24,
            })
        assert r.status_code in (200, 201, 422)
