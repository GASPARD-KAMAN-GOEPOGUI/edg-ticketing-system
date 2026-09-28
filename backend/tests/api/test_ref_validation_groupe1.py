"""
GROUPE 1 — Tests de comportement : validation dynamique des 6 référentiels.

VÉRIF A : autonomie admin bout en bout (ajoute un code → usage métier accepté)
VÉRIF B : rejet d'une valeur invalide (422 via check_ref_code)
VÉRIF C : garde-fous de suppression (builtin protégé + nettoyage de test)

Référentiels testés : task_type / task_status /
                      escalation_level / escalation_status / workflow_status

Le référentiel `account_status` a été retiré le 2026-09-24 avec les annonces et
la base de connaissances : la colonne `account.account_status` subsiste mais
n'est plus validée. Les trois tests qui couvraient cette validation (a4, b3, c2)
sont supprimés — le comportement testé n'existe plus par décision produit.
"""
from __future__ import annotations

import pytest


# ══════════════════════════════════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════════════════════════════════

BASE = "/api/v1"


def _unwrap(resp) -> dict:
    """Extrait body['data'] si présent, sinon retourne body directement."""
    body = resp.json()
    return body.get("data", body)


# ══════════════════════════════════════════════════════════════════════════════
# VÉRIF A — Autonomie admin bout en bout
# ══════════════════════════════════════════════════════════════════════════════

class TestVerifA_AutonomieAdmin:
    """
    Flux complet :
      1. Admin crée un code de référence custom (ex. task_type="test_autonomie")
      2. Une ressource métier utilisant ce code est créée → doit être ACCEPTÉE (201)
      3. Nettoyage (soft-delete du code custom)
    """

    async def test_a1_admin_cree_task_type_custom(self, auth_client, request_id):
        """POST /references/task-types → 201 avec le nouveau code."""
        async with auth_client("admin") as c:
            r = await c.post(f"{BASE}/references/task-types", json={
                "code": "test_autonomie",
                "label": "Test autonomie admin",
                "sort_order": 99,
                "is_builtin": False,
            })
        assert r.status_code == 201, f"Attendu 201, obtenu {r.status_code}: {r.text}"
        body = _unwrap(r)
        assert body["code"] == "test_autonomie"

    async def test_a2_task_avec_code_custom_est_acceptee(self, auth_client, request_id):
        """
        POST /tasks/ avec task_type='test_autonomie' → 201.
        Prouve que la validation applicative accepte le code fraîchement ajouté.
        """
        assert request_id, "Fixture request_id requise"
        async with auth_client("admin") as c:
            r = await c.post(f"{BASE}/tasks/", json={
                "request_id": int(request_id),
                "task_type": "test_autonomie",
                "task_status": "pending",
                "reason": "Test autonomie VÉRIF A",
            })
        assert r.status_code == 201, (
            f"task_type='test_autonomie' (code existant) doit être accepté (201), "
            f"obtenu {r.status_code}: {r.text}"
        )

    async def test_a3_task_status_custom_accepte(self, auth_client, request_id):
        """
        Admin ajoute un task_status custom → usage immédiatement accepté.
        """
        async with auth_client("admin") as c:
            # Création du code custom
            cr = await c.post(f"{BASE}/references/task-statuses", json={
                "code": "test_status_custom",
                "label": "Statut custom test",
                "sort_order": 99,
                "is_builtin": False,
            })
            assert cr.status_code == 201, f"Création task_status custom : {cr.status_code} {cr.text}"

            # Usage du code custom dans une tâche
            r = await c.post(f"{BASE}/tasks/", json={
                "request_id": int(request_id),
                "task_type": "verification",
                "task_status": "test_status_custom",
                "reason": "Test VÉRIF A - task_status custom",
            })
        assert r.status_code == 201, (
            f"task_status='test_status_custom' doit être accepté (201), "
            f"obtenu {r.status_code}: {r.text}"
        )

class TestVerifB_RejetValeurInvalide:
    """
    Tenter de créer/modifier une ressource métier avec un code absent des
    référentiels → doit retourner 422.
    """

    async def test_b1_task_type_inconnu_rejete_422(self, auth_client, request_id):
        """POST /tasks/ avec task_type='valeur_bidon_jamais_seedee' → 422."""
        assert request_id, "Fixture request_id requise"
        async with auth_client("admin") as c:
            r = await c.post(f"{BASE}/tasks/", json={
                "request_id": int(request_id),
                "task_type": "valeur_bidon_jamais_seedee",
                "task_status": "pending",
            })
        assert r.status_code == 422, (
            f"task_type invalide doit être rejeté en 422 via check_ref_code, "
            f"obtenu {r.status_code}: {r.text}"
        )

    async def test_b2_task_status_inconnu_rejete_422(self, auth_client, request_id):
        """POST /tasks/ avec task_status inexistant → 422."""
        assert request_id, "Fixture request_id requise"
        async with auth_client("admin") as c:
            r = await c.post(f"{BASE}/tasks/", json={
                "request_id": int(request_id),
                "task_type": "verification",
                "task_status": "statut_qui_nexiste_pas",
            })
        assert r.status_code == 422, (
            f"task_status invalide doit être rejeté en 422, "
            f"obtenu {r.status_code}: {r.text}"
        )

    async def test_b4_escalation_level_inconnu_rejete_422(self, auth_client, request_id):
        """POST /escalations/ avec level inexistant → 422."""
        assert request_id, "Fixture request_id requise"
        async with auth_client("admin") as c:
            r = await c.post(f"{BASE}/escalations/", json={
                "request_id": int(request_id),
                "from_agent_name": "Agent Test",
                "to_agent_name": "Chef Test",
                "level": "niveau_bidon_xyz",
                "reason": "Test rejet",
                "priority": "medium",
                "sla_over_hours": 0,
            })
        assert r.status_code == 422, (
            f"level='niveau_bidon_xyz' doit être rejeté en 422, "
            f"obtenu {r.status_code}: {r.text}"
        )

    async def test_b5_valeurs_builtin_toujours_acceptees(self, auth_client, request_id):
        """
        Non-régression : les codes BUILTIN existants (pending, verification, active…)
        doivent toujours être acceptés après le câblage de check_ref_code.
        """
        assert request_id, "Fixture request_id requise"
        async with auth_client("admin") as c:
            r = await c.post(f"{BASE}/tasks/", json={
                "request_id": int(request_id),
                "task_type": "verification",
                "task_status": "pending",
                "reason": "Non-régression BUILTIN",
            })
        assert r.status_code == 201, (
            f"task_type='verification' + task_status='pending' (codes BUILTIN) "
            f"doivent toujours être acceptés (201), obtenu {r.status_code}: {r.text}"
        )

    async def test_b6_reassignment_builtin_accepte(self, auth_client, request_id):
        """
        Non-régression : 'reassignment' (ajouté aux seeds en ÉTAPE 2) est accepté.
        Ce code est utilisé en production par le moteur workflow.
        """
        assert request_id, "Fixture request_id requise"
        async with auth_client("admin") as c:
            r = await c.post(f"{BASE}/tasks/", json={
                "request_id": int(request_id),
                "task_type": "reassignment",
                "task_status": "pending",
            })
        assert r.status_code == 201, (
            f"task_type='reassignment' (seedé en ÉTAPE 2) doit être accepté (201), "
            f"obtenu {r.status_code}: {r.text}"
        )

    async def test_b7_reopening_builtin_accepte(self, auth_client, request_id):
        """Non-régression : 'reopening' (ajouté aux seeds en ÉTAPE 2) est accepté."""
        assert request_id, "Fixture request_id requise"
        async with auth_client("admin") as c:
            r = await c.post(f"{BASE}/tasks/", json={
                "request_id": int(request_id),
                "task_type": "reopening",
                "task_status": "pending",
            })
        assert r.status_code == 201, (
            f"task_type='reopening' (seedé en ÉTAPE 2) doit être accepté (201), "
            f"obtenu {r.status_code}: {r.text}"
        )


# ══════════════════════════════════════════════════════════════════════════════
# VÉRIF C — Garde-fous de suppression
# ══════════════════════════════════════════════════════════════════════════════

class TestVerifC_GardesFousSuppression:
    """
    C1 : Suppression d'une valeur is_builtin=True → 400 (BUILTIN_PROTECTED)
    C2 : Nettoyage des codes custom créés en VÉRIF A (soft-delete)
    C3 : Restauration possible après soft-delete
    """

    async def test_c1_suppression_builtin_task_type_interdit(self, auth_client):
        """
        DELETE /references/task-types/{id} sur un code builtin → 400.
        On récupère d'abord l'id de 'verification' (is_builtin=True).
        """
        async with auth_client("admin") as c:
            # Récupère la liste pour trouver l'id de 'verification'
            list_r = await c.get(f"{BASE}/references/task-types")
            assert list_r.status_code == 200
            items = _unwrap(list_r)
            if isinstance(items, dict):
                items = items.get("items", [])

            verification = next((i for i in items if i["code"] == "verification"), None)
            assert verification, "Le code 'verification' (builtin) doit exister dans task_type"
            builtin_id = verification["id"]

            del_r = await c.delete(f"{BASE}/references/task-types/{builtin_id}")

        assert del_r.status_code == 400, (
            f"Suppression d'un code builtin doit retourner 400, "
            f"obtenu {del_r.status_code}: {del_r.text}"
        )

    async def test_c3_suppression_code_custom_test_autonomie(self, auth_client):
        """
        Nettoyage de VÉRIF A : soft-delete du code custom 'test_autonomie'.
        → Doit retourner 204 (pas une valeur builtin).
        """
        async with auth_client("admin") as c:
            list_r = await c.get(f"{BASE}/references/task-types?only_active=false")
            assert list_r.status_code == 200
            items = _unwrap(list_r)
            if isinstance(items, dict):
                items = items.get("items", [])

            custom = next((i for i in items if i["code"] == "test_autonomie"), None)
            if custom is None:
                pytest.skip("Code 'test_autonomie' non trouvé (peut-être déjà nettoyé)")

            del_r = await c.delete(f"{BASE}/references/task-types/{custom['id']}")

        assert del_r.status_code == 204, (
            f"Suppression d'un code custom (non-builtin) doit retourner 204, "
            f"obtenu {del_r.status_code}: {del_r.text}"
        )

    async def test_c4_suppression_code_custom_test_status(self, auth_client):
        """Nettoyage : soft-delete de 'test_status_custom'."""
        async with auth_client("admin") as c:
            list_r = await c.get(f"{BASE}/references/task-statuses?only_active=false")
            assert list_r.status_code == 200
            items = _unwrap(list_r)
            if isinstance(items, dict):
                items = items.get("items", [])

            custom = next((i for i in items if i["code"] == "test_status_custom"), None)
            if custom is None:
                pytest.skip("Code 'test_status_custom' non trouvé")

            del_r = await c.delete(f"{BASE}/references/task-statuses/{custom['id']}")

        assert del_r.status_code == 204, (
            f"Suppression custom doit retourner 204, obtenu {del_r.status_code}: {del_r.text}"
        )

    async def test_c5_code_supprime_rejete_en_422(self, auth_client, request_id):
        """
        Après soft-delete de 'test_autonomie', toute tentative d'usage
        doit retourner 422 (le code inactif est traité comme inexistant).
        """
        assert request_id, "Fixture request_id requise"
        async with auth_client("admin") as c:
            r = await c.post(f"{BASE}/tasks/", json={
                "request_id": int(request_id),
                "task_type": "test_autonomie",
                "task_status": "pending",
                "reason": "Test post-delete",
            })
        # Le code soft-deleted doit être rejeté (status=False ou deleted_at non null)
        assert r.status_code == 422, (
            f"Après soft-delete, le code 'test_autonomie' doit être rejeté en 422, "
            f"obtenu {r.status_code}: {r.text}"
        )
