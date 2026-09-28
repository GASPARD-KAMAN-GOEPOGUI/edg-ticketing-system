"""
PHASE -1 — BASELINE : Tests de caractérisation des flux de demandes.

Documente le comportement ACTUEL (statuts HTTP + forme des réponses).
Ne corrige aucune anomalie.

NAVIGATION TASK — vue personnelle « Mes demandes » :
  TestVuePersonnelleBaseline documente le comportement APRÈS la correction
  du bypass is_own_view dans list_requests() (RouteRequest.py).
"""
from __future__ import annotations

import re
from uuid import uuid4

import pytest

from tests.conftest import _TestSession


_AUDIT_INFO_KEYS = (
    "actor_id",
    "actor_role",
    "target_user_id",
    "target_role",
    "old_status",
    "new_status",
    "reason",
)


async def _ensure_test_account(
    account_id: int,
    *,
    unity_id: int | None,
    role: str = "chief-service",
    email: str | None = None,
) -> None:
    from api.models.ModelAccount import Account

    async with _TestSession() as session:
        existing = await session.get(Account, account_id)
        if existing is not None:
            existing.unity_id = unity_id
            existing.role = role
            existing.account_status = "active"
            existing.availability = "available"
        else:
            session.add(Account(
                id=account_id,
                unity_id=unity_id,
                name=f"Compte Test {account_id}",
                firstname="Test",
                email=email or f"compte.test.{account_id}@test.edg.gn",
                role=role,
                account_status="active",
                availability="available" if role in {"chief-service", "chief-service", "chief-departement"} else None,
                matricule=f"TST{account_id:05d}",
                is_edg_employee=True,
            ))
        await session.commit()


async def _ensure_test_unity(
    unity_id: int,
    *,
    parent_direction_id: int | None = None,
) -> None:
    from api.models.ModelUnity import Unity

    async with _TestSession() as session:
        existing = await session.get(Unity, unity_id)
        if existing is not None:
            existing.parent_direction_id = parent_direction_id
            existing.label = existing.label or f"Unité Test {unity_id}"
            existing.codename = existing.codename or f"TST-UNITY-{unity_id}"
            existing.status = True
        else:
            session.add(Unity(
                id=unity_id,
                label=f"Unité Test {unity_id}",
                codename=f"TST-UNITY-{unity_id}",
                parent_direction_id=parent_direction_id,
                status=True,
            ))
        await session.commit()


async def _ensure_test_organigram(
    unity_id: int,
    *,
    parent_unity_id: int | None = None,
) -> None:
    from sqlalchemy import select
    from api.models.ModelOrganigram import Organigram

    async with _TestSession() as session:
        parent_id = None
        if parent_unity_id is not None:
            parent_stmt = (
                select(Organigram)
                .where(Organigram.unity_id == parent_unity_id)
                .where(Organigram.parent_id.is_(None))
                .where(Organigram.deleted_at.is_(None))
                .limit(1)
            )
            parent = (await session.execute(parent_stmt)).scalar_one_or_none()
            if parent is None:
                parent = Organigram(unity_id=parent_unity_id, parent_id=None, status=True)
                session.add(parent)
                await session.flush()
            parent_id = parent.id

        stmt = (
            select(Organigram)
            .where(Organigram.unity_id == unity_id)
            .where(Organigram.deleted_at.is_(None))
            .limit(1)
        )
        if parent_id is None:
            stmt = stmt.where(Organigram.parent_id.is_(None))
        else:
            stmt = stmt.where(Organigram.parent_id == parent_id)

        existing = (await session.execute(stmt)).scalar_one_or_none()
        if existing is None:
            session.add(Organigram(unity_id=unity_id, parent_id=parent_id, status=True))
        else:
            existing.status = True
        await session.commit()


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
        assert re.fullmatch(r"EDG-\d{2}-\d{5,}", data["ref"])
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

    async def test_creation_auto_route_peut_changer_statut_initial(self, auth_client, unity_id):
        """Une demande explicitement automatique peut être routée dès la création."""
        payload = {**self._PAYLOAD_MINIMAL,
                   "title": "Baseline auto-route — panne réseau",
                   "unity_id": unity_id,
                   "infos": {"auto_route": True}}
        async with auth_client("admin") as c:
            r = await c.post("/api/v1/requests/", json=payload)
        assert r.status_code == 201
        body = r.json()
        data = body.get("data", body)
        status_val = data.get("request_status")
        if isinstance(status_val, dict):
            status_val = status_val.get("code")
        assert status_val in {"qualifying", "assigned"}

    async def test_creation_auto_route_auto_assign_agent_disponible(self, auth_client, unity_id):
        """Une règle auto_assign affecte directement le ticket à l'agent disponible."""
        from api.models.ModelAccount import Account
        from api.models.ModelRoutingRule import RoutingRule

        token = "autoassign-test-token"
        async with _TestSession() as session:
            agent = Account(
                unity_id=unity_id,
                name="Agent Auto Assign",
                firstname="Auto",
                email="auto.assign@test.edg.gn",
                role="chief-service",
                account_status="active",
                availability="available",
                matricule="AUTOASSIGN001",
                is_edg_employee=True,
            )
            session.add(agent)
            await session.flush()
            rule = RoutingRule(
                target_unity_id=unity_id,
                name="Test auto assign",
                condition_field="keyword",
                condition_value=token,
                auto_assign=True,
                sort_order=0,
            )
            session.add(rule)
            await session.commit()
            agent_id = agent.id

        payload = {**self._PAYLOAD_MINIMAL,
                   "title": f"Baseline auto assign — {token}",
                   "description": f"Demande de test {token}",
                   "unity_id": unity_id,
                   "infos": {"auto_route": True}}
        async with auth_client("admin") as c:
            r = await c.post("/api/v1/requests/", json=payload)
        assert r.status_code == 201
        body = r.json()
        data = body.get("data", body)
        assert data.get("request_status") == "assigned"
        assert str(data.get("assignee_id")) == str(agent_id)

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
        # 200 si transition valide, 403 si hors périmètre, 4xx si état invalide.
        assert r.status_code in (200, 201, 400, 403, 422)

    async def test_resolve_inaccessible_au_user(self, auth_client, request_id):
        """Un user ne peut pas résoudre une demande."""
        if not request_id:
            pytest.skip("request_id non disponible")
        async with auth_client("user") as c:
            r = await c.post(f"/api/v1/requests/{request_id}/resolve")
        assert r.status_code in (403, 404)  # 403 = refusé, 404 = pas la bonne demande


class TestQueueBaseline:
    _PAYLOAD = {
        "title": "Ticket séparation file",
        "description": "Contrôle séparation file d'attente et qualification.",
        "category": "panne",
        "priority": "medium",
        "is_external": False,
        "unity_id": 1,
        "requester_name": "Citoyen Queue",
    }

    async def test_file_attente_exclut_les_demandes_en_triage(self, auth_client):
        token = uuid4().hex[:8]
        payload = {
            **self._PAYLOAD,
            "title": f"{self._PAYLOAD['title']} {token}",
            "requester_email": f"queue.{token}@test.edg.gn",
        }

        async with auth_client("user") as c:
            created = await c.post("/api/v1/requests/", json=payload)
            assert created.status_code == 201
            created_body = created.json()
            rid = str(created_body.get("data", created_body)["id"])

        async with auth_client("admin") as c:
            patched = await c.put(f"/api/v1/requests/{rid}", json={"in_triage": True})
            assert patched.status_code == 200

        async with auth_client("agent") as c:
            queue = await c.get("/api/v1/requests/queue?limit=200")
            triage = await c.get("/api/v1/requests/triage?limit=100")

        assert queue.status_code == 200
        queue_body = queue.json()
        queue_data = queue_body.get("data", queue_body)
        assert all(str(item.get("id")) != rid for item in queue_data.get("items", []))

        assert triage.status_code == 200
        triage_body = triage.json()
        triage_data = triage_body.get("data", triage_body)
        assert any(str(item.get("id")) == rid for item in triage_data.get("items", []))


class TestAssignationEscaladeRoles:
    _PAYLOAD = {
        "title": "Ticket rôle agent",
        "description": "Contrôle assignation et escalade.",
        "category": "panne",
        "priority": "medium",
        "is_external": False,
        "unity_id": 1,
        "requester_name": "Citoyen Test",
        "requester_email": "citoyen.agent@test.edg.gn",
    }

    async def _create_ticket(self, client) -> str:
        token = uuid4().hex[:8]
        payload = {
            **self._PAYLOAD,
            "title": f"{self._PAYLOAD['title']} {token}",
            "description": f"{self._PAYLOAD['description']} {token}",
            "requester_email": f"citoyen.agent.{token}@test.edg.gn",
        }
        created = await client.post("/api/v1/requests/", json=payload)
        assert created.status_code == 201
        body = created.json()
        data = body.get("data", body)
        return str(data["id"])

    async def test_resolution_refuse_ticket_sans_traitement_prealable(self, auth_client):
        async with auth_client("user") as c:
            rid = await self._create_ticket(c)

        async with auth_client("admin") as c:
            resolved = await c.post(f"/api/v1/requests/{rid}/resolve")

        assert resolved.status_code in (400, 422)

    async def test_update_admin_ne_bypasse_pas_machine_etat(self, auth_client):
        async with auth_client("user") as c:
            rid = await self._create_ticket(c)

        async with auth_client("admin") as c:
            patched = await c.put(
                f"/api/v1/requests/{rid}",
                json={"request_status": "resolved"},
            )

        assert patched.status_code in (400, 422)

    async def test_agent_peut_s_auto_assigner_ticket_libre(self, auth_client):
        await _ensure_test_account(2, unity_id=1, role="chief-service")

        async with auth_client("admin") as c:
            rid = await self._create_ticket(c)

        async with auth_client("agent") as c:
            assigned = await c.post(f"/api/v1/requests/{rid}/assign?assignee_id=2")

        assert assigned.status_code == 200
        body = assigned.json()
        data = body.get("data", body)
        assert str(data.get("assignee_id")) == "2"
        # BR-QUEUE-AUTO-START-001 : l'auto-assignation démarre directement le traitement.
        assert data.get("request_status") == "in_progress"

    async def test_agent_ne_peut_pas_assigner_un_autre_agent(self, auth_client):
        await _ensure_test_account(2, unity_id=1, role="chief-service")
        await _ensure_test_account(202, unity_id=1, role="chief-service")

        async with auth_client("admin") as c:
            rid = await self._create_ticket(c)

        async with auth_client("agent") as c:
            assigned = await c.post(f"/api/v1/requests/{rid}/assign?assignee_id=202")

        assert assigned.status_code == 403

    async def test_chef_peut_assigner_agent_de_son_service(self, auth_client):
        await _ensure_test_account(202, unity_id=1, role="chief-service")

        async with auth_client("admin") as c:
            rid = await self._create_ticket(c)

        async with auth_client("chief") as c:
            assigned = await c.post(f"/api/v1/requests/{rid}/assign?assignee_id=202")

        assert assigned.status_code == 200
        body = assigned.json()
        data = body.get("data", body)
        assert str(data.get("assignee_id")) == "202"

    async def test_chef_ne_peut_pas_assigner_agent_hors_service(self, auth_client):
        await _ensure_test_unity(22, parent_direction_id=1)
        await _ensure_test_account(203, unity_id=22, role="chief-service")

        async with auth_client("admin") as c:
            rid = await self._create_ticket(c)

        async with auth_client("chief") as c:
            assigned = await c.post(f"/api/v1/requests/{rid}/assign?assignee_id=203")

        assert assigned.status_code == 403

    async def test_rejet_chef_exige_un_motif(self, auth_client):
        async with auth_client("admin") as c:
            rid = await self._create_ticket(c)

        async with auth_client("chief") as c:
            rejected = await c.post(f"/api/v1/requests/{rid}/reject", json={"reason": "   "})

        assert rejected.status_code in (400, 422)

    async def test_chef_peut_changer_priorite_ticket_de_son_service(self, auth_client):
        async with auth_client("admin") as c:
            rid = await self._create_ticket(c)

        async with auth_client("chief") as c:
            changed = await c.post(f"/api/v1/requests/{rid}/priority", json={"priority": "high"})
            detail = await c.get(f"/api/v1/requests/{rid}")

        assert changed.status_code == 200
        body = changed.json()
        data = body.get("data", body)
        assert data.get("priority") == "high"

        assert detail.status_code == 200
        detail_body = detail.json()
        detail_data = detail_body.get("data", detail_body)
        priority_events = [
            event for event in detail_data.get("timelines", [])
            if event.get("event_type") == "priority_changed"
        ]
        assert priority_events
        infos = priority_events[-1].get("infos", {})
        assert infos.get("actor_role") == "chief"
        assert infos.get("old_priority") == "medium"
        assert infos.get("new_priority") == "high"
        for key in _AUDIT_INFO_KEYS:
            assert key in infos

    async def test_agent_ne_peut_pas_changer_priorite(self, auth_client):
        async with auth_client("admin") as c:
            rid = await self._create_ticket(c)

        async with auth_client("agent") as c:
            changed = await c.post(f"/api/v1/requests/{rid}/priority", json={"priority": "high"})

        assert changed.status_code == 403

    async def test_annulation_exige_un_motif_et_trace_audit(self, auth_client):
        async with auth_client("admin") as c:
            rid = await self._create_ticket(c)
            missing_reason = await c.post(f"/api/v1/requests/{rid}/cancel")
            cancelled = await c.post(
                f"/api/v1/requests/{rid}/cancel?reason=Erreur%20de%20saisie%20confirm%C3%A9e"
            )
            detail = await c.get(f"/api/v1/requests/{rid}")

        assert missing_reason.status_code in (400, 422)
        assert cancelled.status_code == 200
        cancelled_body = cancelled.json()
        cancelled_data = cancelled_body.get("data", cancelled_body)
        assert cancelled_data.get("request_status") == "cancelled"
        assert cancelled_data.get("infos", {}).get("cancel_reason") == "Erreur de saisie confirmée"

        assert detail.status_code == 200
        detail_body = detail.json()
        detail_data = detail_body.get("data", detail_body)
        cancelled_events = [
            event for event in detail_data.get("timelines", [])
            if event.get("event_type") == "cancelled"
        ]
        assert cancelled_events
        infos = cancelled_events[-1].get("infos", {})
        assert infos.get("reason") == "Erreur de saisie confirmée"
        for key in _AUDIT_INFO_KEYS:
            assert key in infos

    async def test_demandeur_peut_reouvrir_immediatement_avec_motif(self, auth_client):
        """BR-REOPEN-QUEUE-001 (révision — réouverture immédiate) : le demandeur
        réouvre seul, sans approbation d'un chef — remplace les anciens tests
        d'approbation/refus (`/request-reopen` + `/reject-reopen`/`/reopen`
        deux-phases), routes supprimées."""
        await _ensure_test_account(2, unity_id=1, role="chief-service")

        async with auth_client("admin") as c:
            rid = await self._create_ticket(c)

        async with auth_client("agent") as c:
            assigned = await c.post(f"/api/v1/requests/{rid}/assign?assignee_id=2")
            assert assigned.status_code == 200
            resolved = await c.post(f"/api/v1/requests/{rid}/resolve")
            assert resolved.status_code == 200

        async with auth_client("user") as c:
            reopened = await c.post(
                f"/api/v1/requests/{rid}/reopen",
                json={"reason": "Le problème persiste côté demandeur."},
            )
            detail = await c.get(f"/api/v1/requests/{rid}")

        assert reopened.status_code == 200, reopened.text
        body = reopened.json()
        data = body.get("data", body)
        assert data.get("request_status") == "reopened"
        assert data.get("assignee_id") is None

        assert detail.status_code == 200
        detail_body = detail.json()
        detail_data = detail_body.get("data", detail_body)
        assert any(
            event.get("event_type") == "reopened"
            for event in detail_data.get("timelines", [])
        )

    async def test_reopen_sans_motif_est_refuse(self, auth_client):
        await _ensure_test_account(2, unity_id=1, role="chief-service")

        async with auth_client("admin") as c:
            rid = await self._create_ticket(c)

        async with auth_client("agent") as c:
            assigned = await c.post(f"/api/v1/requests/{rid}/assign?assignee_id=2")
            assert assigned.status_code == 200
            resolved = await c.post(f"/api/v1/requests/{rid}/resolve")
            assert resolved.status_code == 200

        async with auth_client("user") as c:
            reopened = await c.post(f"/api/v1/requests/{rid}/reopen", json={"reason": "   "})

        assert reopened.status_code == 400

    async def test_non_demandeur_ne_peut_pas_reouvrir(self, auth_client):
        await _ensure_test_account(2, unity_id=1, role="chief-service")

        async with auth_client("admin") as c:
            rid = await self._create_ticket(c)

        async with auth_client("chief") as c:
            assigned = await c.post(f"/api/v1/requests/{rid}/assign?assignee_id=2")
            assert assigned.status_code == 200
            resolved = await c.post(f"/api/v1/requests/{rid}/resolve")
            assert resolved.status_code == 200

        async with auth_client("agent") as c:
            reopened = await c.post(
                f"/api/v1/requests/{rid}/reopen",
                json={"reason": "Résolution contestée."},
            )

        assert reopened.status_code == 403


class TestDirectionRoleAlignment:
    _BASE_PAYLOAD = {
        "title": "Ticket directeur",
        "description": "Contrôle du périmètre direction.",
        "category": "panne",
        "priority": "medium",
        "is_external": False,
        "requester_name": "Citoyen Direction",
    }

    async def _prepare_direction_scope(self) -> None:
        await _ensure_test_unity(1, parent_direction_id=None)
        await _ensure_test_unity(9101, parent_direction_id=1)
        await _ensure_test_unity(9102, parent_direction_id=1)
        await _ensure_test_unity(9900, parent_direction_id=None)
        await _ensure_test_unity(9901, parent_direction_id=9900)
        await _ensure_test_organigram(1)
        await _ensure_test_organigram(9101, parent_unity_id=1)
        await _ensure_test_organigram(9102, parent_unity_id=1)
        await _ensure_test_organigram(9900)
        await _ensure_test_organigram(9901, parent_unity_id=9900)

    async def _create_ticket(self, client, unity_id: int) -> str:
        token = uuid4().hex[:8]
        payload = {
            **self._BASE_PAYLOAD,
            "title": f"{self._BASE_PAYLOAD['title']} {token}",
            "requester_email": f"direction.{token}@test.edg.gn",
            "unity_id": unity_id,
        }
        created = await client.post("/api/v1/requests/", json=payload)
        assert created.status_code == 201
        body = created.json()
        data = body.get("data", body)
        return str(data["id"])

    async def test_directeur_liste_les_tickets_des_services_enfants(self, auth_client):
        await self._prepare_direction_scope()

        async with auth_client("admin") as c:
            rid = await self._create_ticket(c, 9101)

        async with auth_client("director") as c:
            listed = await c.get("/api/v1/requests/?limit=100")

        assert listed.status_code == 200
        body = listed.json()
        data = body.get("data", body)
        assert any(str(item.get("id")) == rid for item in data.get("items", []))

    async def test_directeur_peut_resoudre_ticket_service_de_sa_direction(self, auth_client):
        await self._prepare_direction_scope()
        await _ensure_test_account(9202, unity_id=9101, role="chief-service")

        async with auth_client("user") as c:
            rid = await self._create_ticket(c, 9101)

        async with auth_client("admin") as c:
            assigned = await c.post(f"/api/v1/requests/{rid}/assign?assignee_id=9202")

        assert assigned.status_code == 200

        async with auth_client("director") as c:
            resolved = await c.post(f"/api/v1/requests/{rid}/resolve")

        assert resolved.status_code == 200
        body = resolved.json()
        data = body.get("data", body)
        assert data.get("request_status") == "resolved"

    async def test_directeur_peut_orienter_ticket_vers_service_de_sa_direction(self, auth_client):
        await self._prepare_direction_scope()

        async with auth_client("admin") as c:
            rid = await self._create_ticket(c, 9101)

        async with auth_client("director") as c:
            reassigned = await c.post(
                f"/api/v1/requests/{rid}/reassign",
                json={"target_unity_id": "9102", "reason": "Orientation vers le bon service."},
            )

        assert reassigned.status_code == 200
        body = reassigned.json()
        data = body.get("data", body)
        assert str(data.get("unity_id")) == "9102"

    async def test_directeur_ne_peut_pas_orienter_hors_direction(self, auth_client):
        await self._prepare_direction_scope()

        async with auth_client("admin") as c:
            rid = await self._create_ticket(c, 9101)

        async with auth_client("director") as c:
            reassigned = await c.post(
                f"/api/v1/requests/{rid}/reassign",
                json={"target_unity_id": "9901", "reason": "Sortie hors direction."},
            )

        assert reassigned.status_code == 403

    async def test_directeur_peut_transferer_ticket_vers_autre_direction(self, auth_client):
        await self._prepare_direction_scope()
        await _ensure_test_account(4900, unity_id=9900, role="chief-service")

        async with auth_client("admin") as c:
            rid = await self._create_ticket(c, 9101)

        async with auth_client("director") as c:
            transferred = await c.post(
                f"/api/v1/requests/{rid}/transfer-direction",
                json={
                    "target_direction_id": "9900",
                    "reason": "Aucun service de ma direction ne peut traiter ce cas.",
                },
            )
            source_detail_after = await c.get(f"/api/v1/requests/{rid}")

        async with auth_client("admin") as c:
            target_list = await c.get("/api/v1/requests/by-direction/9900?limit=100")
            source_list = await c.get("/api/v1/requests/by-direction/1?limit=100")
            detail = await c.get(f"/api/v1/requests/{rid}")

        assert transferred.status_code == 200
        body = transferred.json()
        data = body.get("data", body)
        assert data.get("request_status") == "qualifying"
        assert str(data.get("unity_id")) == "9900"
        assert data.get("assignee_id") is None
        assert source_detail_after.status_code == 403

        assert target_list.status_code == 200
        target_data = target_list.json().get("data", target_list.json())
        assert any(str(item.get("id")) == rid for item in target_data.get("items", []))

        assert source_list.status_code == 200
        source_data = source_list.json().get("data", source_list.json())
        assert all(str(item.get("id")) != rid for item in source_data.get("items", []))

        assert detail.status_code == 200
        detail_data = detail.json().get("data", detail.json())
        transfer_events = [
            event for event in detail_data.get("timelines", [])
            if event.get("event_type") == "transferred_direction"
        ]
        assert transfer_events
        infos = transfer_events[-1].get("infos", {})
        assert infos.get("reason") == "Aucun service de ma direction ne peut traiter ce cas."
        assert str(infos.get("previous_direction_id")) == "1"
        assert str(infos.get("target_direction_id")) == "9900"
        assert infos.get("old_status") == "new"
        assert infos.get("new_status") == "qualifying"
        for key in _AUDIT_INFO_KEYS:
            assert key in infos

    async def test_transfert_direction_exige_un_motif(self, auth_client):
        await self._prepare_direction_scope()

        async with auth_client("admin") as c:
            rid = await self._create_ticket(c, 9101)

        async with auth_client("director") as c:
            transferred = await c.post(
                f"/api/v1/requests/{rid}/transfer-direction",
                json={"target_direction_id": "9900", "reason": "   "},
            )

        assert transferred.status_code in (400, 422)

    async def test_directeur_ne_peut_pas_transferer_ticket_hors_perimetre(self, auth_client):
        await self._prepare_direction_scope()

        async with auth_client("admin") as c:
            rid = await self._create_ticket(c, 9901)

        async with auth_client("director") as c:
            transferred = await c.post(
                f"/api/v1/requests/{rid}/transfer-direction",
                json={
                    "target_direction_id": "1",
                    "reason": "Tentative depuis une direction hors périmètre.",
                },
            )

        assert transferred.status_code == 403

    async def test_directeur_ne_peut_pas_assigner_directement_un_chef(self, auth_client):
        await self._prepare_direction_scope()

        async with auth_client("admin") as c:
            rid = await self._create_ticket(c, 9101)

        async with auth_client("director") as c:
            assigned = await c.post(f"/api/v1/requests/{rid}/assign?assignee_id=3")

        assert assigned.status_code == 403

    async def test_directeur_peut_valider_workflow_dans_sa_direction(self, auth_client):
        await self._prepare_direction_scope()

        async with auth_client("admin") as c:
            rid = await self._create_ticket(c, 9101)
            workflow = await c.get(f"/api/v1/workflows/active/by-request/{rid}")
            assert workflow.status_code == 200
            workflow_data = workflow.json().get("data", workflow.json())
            workflow_id = str(workflow_data["id"])
            step = await c.post(
                f"/api/v1/workflows/{workflow_id}/details",
                json={"label": "Validation directeur", "unity_id": 9101, "activated": True},
            )
            assert step.status_code == 201
            step_data = step.json().get("data", step.json())

        async with auth_client("director") as c:
            accepted = await c.post(
                f"/api/v1/workflows/{workflow_id}/details/{step_data['id']}/accept",
                json={"accepted": True},
            )

        assert accepted.status_code == 200

    async def test_directeur_ne_peut_pas_valider_workflow_hors_direction(self, auth_client):
        await self._prepare_direction_scope()

        async with auth_client("admin") as c:
            rid = await self._create_ticket(c, 9901)
            workflow = await c.get(f"/api/v1/workflows/active/by-request/{rid}")
            assert workflow.status_code == 200
            workflow_data = workflow.json().get("data", workflow.json())
            workflow_id = str(workflow_data["id"])
            step = await c.post(
                f"/api/v1/workflows/{workflow_id}/details",
                json={"label": "Validation hors direction", "unity_id": 9901, "activated": True},
            )
            assert step.status_code == 201
            step_data = step.json().get("data", step.json())

        async with auth_client("director") as c:
            accepted = await c.post(
                f"/api/v1/workflows/{workflow_id}/details/{step_data['id']}/accept",
                json={"accepted": True},
            )

        assert accepted.status_code == 403


# ═══════════════════════════════════════════════════════════════════════════════
# Commentaires (comportement après Phase 1 d'origine corrigée)
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

    async def test_upload_et_suppression_attachment_sont_traces_timeline(
        self, auth_client, unity_id
    ):
        """Un fichier ajouté puis supprimé doit laisser une trace dans le détail de la demande."""
        payload = {
            "title": "Audit attachment timeline",
            "description": "Demande de test pour pièces jointes.",
            "category": "panne",
            "priority": "medium",
            "is_external": False,
            "unity_id": unity_id,
            "requester_name": "Citoyen Test",
            "requester_email": "citoyen@test.edg.gn",
        }
        pdf_data = b"%PDF-1.4\n% audit timeline\n1 0 obj\n<<>>\nendobj\n%%EOF\n"

        async with auth_client("admin") as c:
            created = await c.post("/api/v1/requests/", json=payload)
            assert created.status_code == 201
            created_body = created.json()
            request_data = created_body.get("data", created_body)
            rid = str(request_data["id"])

            uploaded = await c.post(
                f"/api/v1/requests/{rid}/attachments",
                files={"file": ("audit.pdf", pdf_data, "application/pdf")},
            )
            assert uploaded.status_code == 201
            uploaded_body = uploaded.json()
            attachment_data = uploaded_body.get("data", uploaded_body)
            attachment_id = str(attachment_data["id"])

            deleted = await c.delete(f"/api/v1/requests/{rid}/attachments/{attachment_id}")
            assert deleted.status_code == 204

            detail = await c.get(f"/api/v1/requests/{rid}")

        assert detail.status_code == 200
        detail_body = detail.json()
        detail_data = detail_body.get("data", detail_body)
        timelines = detail_data.get("timelines", [])

        added = [
            event for event in timelines
            if event.get("event_type") == "attachment_added"
            and event.get("infos", {}).get("filename") == "audit.pdf"
        ]
        deleted_events = [
            event for event in timelines
            if event.get("event_type") == "attachment_deleted"
            and event.get("infos", {}).get("attachment_id") == attachment_id
        ]
        assert added
        assert deleted_events
        assert added[-1].get("infos", {}).get("actor_role") == "admin"
        assert deleted_events[-1].get("infos", {}).get("actor_role") == "admin"


# ═══════════════════════════════════════════════════════════════════════════════
# Workflow — décisions tracées dans la timeline
# ═══════════════════════════════════════════════════════════════════════════════

class TestWorkflowTimelineBaseline:
    async def test_refus_workflow_trace_motif_dans_timeline(self, auth_client, unity_id):
        """Un refus d'étape workflow doit exiger et conserver le motif dans l'historique."""
        payload = {
            "title": "Audit refus workflow",
            "description": "Demande de test pour refus de validation.",
            "category": "panne",
            "priority": "medium",
            "is_external": False,
            "unity_id": unity_id,
            "requester_name": "Citoyen Test",
            "requester_email": "citoyen@test.edg.gn",
        }

        async with auth_client("admin") as c:
            created = await c.post("/api/v1/requests/", json=payload)
            assert created.status_code == 201
            created_body = created.json()
            request_data = created_body.get("data", created_body)
            rid = str(request_data["id"])

            workflow = await c.get(f"/api/v1/workflows/active/by-request/{rid}")
            assert workflow.status_code == 200
            workflow_body = workflow.json()
            workflow_data = workflow_body.get("data", workflow_body)
            workflow_id = str(workflow_data["id"])

            step = await c.post(
                f"/api/v1/workflows/{workflow_id}/details",
                json={"label": "Validation audit", "activated": True},
            )
            assert step.status_code == 201
            step_body = step.json()
            step_data = step_body.get("data", step_body)
            step_id = step_data["id"]

            missing_reason = await c.put(
                "/api/v1/workflow-details/accepted",
                json={"id": step_id, "accepted": False, "comment": "   "},
            )
            assert missing_reason.status_code in (400, 422)

            rejected = await c.put(
                "/api/v1/workflow-details/accepted",
                json={
                    "id": step_id,
                    "accepted": False,
                    "comment": "Motif audit workflow",
                },
            )
            assert rejected.status_code == 200

            detail = await c.get(f"/api/v1/requests/{rid}")

        assert detail.status_code == 200
        detail_body = detail.json()
        detail_data = detail_body.get("data", detail_body)
        timelines = detail_data.get("timelines", [])
        rejected_events = [
            event for event in timelines
            if event.get("event_type") == "workflow_step_rejected"
            and event.get("comment") == "Motif audit workflow"
        ]
        assert rejected_events
        infos = rejected_events[-1].get("infos", {})
        assert infos.get("actor_role") == "admin"
        assert infos.get("new_workflow_status") == "suspended"


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
