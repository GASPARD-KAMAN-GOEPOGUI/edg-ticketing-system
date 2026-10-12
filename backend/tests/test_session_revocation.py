"""
Révocation des sessions après une modification Admin (rôle, désactivation,
suppression) + synchronisation temps réel ciblée.

La plateforme centrale est simulée (tests/conftest.py::FakeCentral) : comme la
vraie, elle continue d'accepter un token après un changement de rôle LOCAL —
c'est précisément ce que la révocation côté EDG Connect doit neutraliser.
"""
from __future__ import annotations

import asyncio

import pytest

from api.core import session_registry
from api.core.event_bus import AppEvent, event_bus
from tests.support import TestSession, bearer, drain, login, make_account


async def _login_ok(client, email: str) -> dict:
    res = await login(client, email)
    assert res["status"] == 200, res
    return res["body"]["data"]


async def _setup(client, central):
    admin_id = await make_account(central, email="admin@edg.gn", role="admin", central_id=1)
    a_id = await make_account(central, email="a@edg.gn", role="chief-service", central_id=2)
    b_id = await make_account(central, email="b@edg.gn", role="user", central_id=3)
    admin = await _login_ok(client, "admin@edg.gn")
    return admin_id, a_id, b_id, admin


async def _me(client, token):
    return await client.get("/api/v1/auth/me", headers=bearer(token))


async def _set_role(client, admin, user_id, role):
    resp = await client.put(
        f"/api/v1/users/{user_id}/role", json={"role": role}, headers=bearer(admin["access_token"]),
    )
    assert resp.status_code == 200, resp.text
    return resp


# ── Cas 1 / 9 — changement de rôle d'un utilisateur connecté ─────────────────

async def test_role_change_revokes_open_session_and_targets_only_that_user(client, central, subscribe):
    admin_id, a_id, b_id, admin = await _setup(client, central)
    a = await _login_ok(client, "a@edg.gn")
    b = await _login_ok(client, "b@edg.gn")
    assert (await _me(client, a["access_token"])).status_code == 200

    q_a = await subscribe(a_id, "chief-service")
    q_b = await subscribe(b_id, "user")
    q_admin1 = await subscribe(admin_id, "admin")
    q_admin2 = await subscribe(admin_id, "admin")  # second Backoffice ouvert

    await _set_role(client, admin, a_id, "technicien")

    # Ancienne session refusée côté backend, avec un motif exploitable.
    old = await _me(client, a["access_token"])
    assert old.status_code == 401
    assert old.json()["error_code"] == "SESSION_REVOKED"
    assert old.json()["value"] == "role_changed"
    assert "rôle a été modifié" in old.json()["message"]

    # Événement ciblé : A seul est révoqué ; B ne reçoit rien ; les deux
    # Backoffices reçoivent la mise à jour, sans révocation.
    revoked = [e for e in drain(q_a) if e["type"] == "user.session_revoked"]
    assert len(revoked) == 1
    assert revoked[0]["payload"]["user_id"] == a_id
    assert revoked[0]["payload"]["reason"] == "role_changed"
    assert set(revoked[0]["payload"]) == {"user_id", "reason", "timestamp"}  # rien de sensible
    assert drain(q_b) == []
    for q in (q_admin1, q_admin2):
        types = [(e["type"], e["payload"].get("id")) for e in drain(q)]
        assert ("user.updated", a_id) in types
        assert all(t != "user.session_revoked" for t, _ in types)

    # Les autres sessions restent valides.
    assert (await _me(client, b["access_token"])).status_code == 200
    assert (await _me(client, admin["access_token"])).status_code == 200


async def test_stale_cached_groups_of_old_token_never_revert_new_role(client, central, monkeypatch):
    """Régression : les groupes centraux sont mis en cache par token. Ceux de
    l'ancien token reflètent l'ancien rôle ; s'ils étaient synchronisés avant
    le contrôle de révocation, ils réécriraient en base le rôle choisi par
    l'admin."""
    from api import dependencies
    from api.repositories import AccountRepository

    monkeypatch.setattr(dependencies._env, "CENTRAL_AUTH_CACHE_TTL", 180)
    dependencies.invalidate_central_auth_cache()
    _, a_id, _, admin = await _setup(client, central)
    a = await _login_ok(client, "a@edg.gn")
    assert (await _me(client, a["access_token"])).status_code == 200  # groupes « chief » en cache

    await _set_role(client, admin, a_id, "technicien")
    from api.core.central_auth import group_for_role
    assert central.groups[2] == {group_for_role("technicien")}  # central à jour

    assert (await _me(client, a["access_token"])).status_code == 401
    async with TestSession() as session:
        account = await AccountRepository(session).get_by_id(a_id)
    assert account is not None and account.role == "technicien"
    dependencies.invalidate_central_auth_cache()


async def test_old_refresh_token_cannot_bypass_role_change(client, central):
    _, a_id, _, admin = await _setup(client, central)
    a = await _login_ok(client, "a@edg.gn")
    await _set_role(client, admin, a_id, "user")

    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": a["refresh_token"]})
    assert resp.status_code == 401
    assert resp.json()["error_code"] == "SESSION_REVOKED"


async def test_relogin_gets_new_role_and_new_permissions(client, central):
    _, a_id, _, admin = await _setup(client, central)
    a = await _login_ok(client, "a@edg.gn")
    # chief-service : accès à l'annuaire du personnel.
    assert (await client.get("/api/v1/users/", headers=bearer(a["access_token"]))).status_code == 200

    await _set_role(client, admin, a_id, "user")
    # Ancien token : refusé.
    assert (await client.get("/api/v1/users/", headers=bearer(a["access_token"]))).status_code == 401

    fresh = await _login_ok(client, "a@edg.gn")
    assert fresh["user"]["role"] == "user"
    me = await _me(client, fresh["access_token"])
    assert me.status_code == 200 and me.json()["data"]["role"] == "user"
    # Nouvelles permissions appliquées : l'annuaire est désormais interdit.
    assert (await client.get("/api/v1/users/", headers=bearer(fresh["access_token"]))).status_code == 403


async def test_refresh_after_relogin_still_works(client, central):
    _, a_id, _, admin = await _setup(client, central)
    await _set_role(client, admin, a_id, "technicien")
    fresh = await _login_ok(client, "a@edg.gn")
    resp = await client.post("/api/v1/auth/refresh", json={"refresh_token": fresh["refresh_token"]})
    assert resp.status_code == 200, resp.text
    me = await _me(client, resp.json()["data"]["access_token"])
    assert me.status_code == 200 and me.json()["data"]["role"] == "technicien"


# ── Cas 5 — rôle modifié alors que l'utilisateur est déconnecté ──────────────

async def test_role_change_while_logged_out_applies_at_next_login(client, central):
    _, a_id, _, admin = await _setup(client, central)
    await _set_role(client, admin, a_id, "technicien")
    fresh = await _login_ok(client, "a@edg.gn")
    assert fresh["user"]["role"] == "technicien"
    assert (await _me(client, fresh["access_token"])).status_code == 200


# ── Cas 2 / 3 / 8 — désactivation ────────────────────────────────────────────

async def test_deactivation_revokes_session_and_blocks_login(client, central, subscribe):
    _, a_id, b_id, admin = await _setup(client, central)
    a = await _login_ok(client, "a@edg.gn")
    b = await _login_ok(client, "b@edg.gn")
    q_a = await subscribe(a_id, "chief-service")
    q_b = await subscribe(b_id, "user")

    resp = await client.post(f"/api/v1/users/{a_id}/deactivate", headers=bearer(admin["access_token"]))
    assert resp.status_code == 200, resp.text

    old = await _me(client, a["access_token"])
    assert old.status_code == 401
    assert old.json()["error_code"] == "ACCOUNT_DISABLED"
    assert old.json()["value"] == "disabled"

    revoked = [e for e in drain(q_a) if e["type"] == "user.session_revoked"]
    assert revoked and revoked[0]["payload"]["reason"] == "disabled"
    assert drain(q_b) == []
    assert (await _me(client, b["access_token"])).status_code == 200

    # Connexion refusée avec le vrai motif (le central refuse comme un mauvais
    # mot de passe ; le compte local donne la raison).
    res = await login(client, "a@edg.gn")
    assert res["status"] == 401
    assert res["body"]["error_code"] == "ACCOUNT_DISABLED"

    # Refresh de l'ancienne session refusé.
    ref = await client.post("/api/v1/auth/refresh", json={"refresh_token": a["refresh_token"]})
    assert ref.status_code == 401 and ref.json()["error_code"] == "ACCOUNT_DISABLED"


async def test_deactivated_user_never_connected_cannot_login(client, central):
    _, a_id, _, admin = await _setup(client, central)
    resp = await client.post(f"/api/v1/users/{a_id}/deactivate", headers=bearer(admin["access_token"]))
    assert resp.status_code == 200, resp.text
    res = await login(client, "a@edg.gn")
    assert res["status"] == 401 and res["body"]["error_code"] == "ACCOUNT_DISABLED"


async def test_login_refused_when_local_account_disabled_even_if_central_accepts(client, central):
    _, a_id, _, admin = await _setup(client, central)
    # Désactivation via la mise à jour générique : le central n'est pas prévenu.
    resp = await client.put(f"/api/v1/users/{a_id}", json={"status": False}, headers=bearer(admin["access_token"]))
    assert resp.status_code == 200, resp.text
    res = await login(client, "a@edg.gn")
    assert res["status"] == 401
    assert res["body"]["error_code"] == "ACCOUNT_DISABLED"


async def test_deactivation_through_generic_update_also_revokes(client, central, subscribe):
    _, a_id, _, admin = await _setup(client, central)
    a = await _login_ok(client, "a@edg.gn")
    q_a = await subscribe(a_id, "chief-service")
    resp = await client.put(
        f"/api/v1/users/{a_id}", json={"account_status": "inactive"}, headers=bearer(admin["access_token"]),
    )
    assert resp.status_code == 200, resp.text
    assert (await _me(client, a["access_token"])).status_code == 401
    assert any(e["type"] == "user.session_revoked" for e in drain(q_a))


# ── Cas 4 — réactivation ─────────────────────────────────────────────────────

async def test_reactivation_allows_fresh_login_but_never_restores_old_session(client, central):
    _, a_id, _, admin = await _setup(client, central)
    a = await _login_ok(client, "a@edg.gn")
    await client.post(f"/api/v1/users/{a_id}/deactivate", headers=bearer(admin["access_token"]))
    resp = await client.post(f"/api/v1/users/{a_id}/activate", headers=bearer(admin["access_token"]))
    assert resp.status_code == 200, resp.text

    # L'ancien token (toujours accepté par le central simulé) reste refusé.
    assert (await _me(client, a["access_token"])).status_code == 401
    ref = await client.post("/api/v1/auth/refresh", json={"refresh_token": a["refresh_token"]})
    assert ref.status_code == 401

    fresh = await _login_ok(client, "a@edg.gn")
    me = await _me(client, fresh["access_token"])
    assert me.status_code == 200
    assert me.json()["data"]["account_status"] == "active"
    assert me.json()["data"]["role"] == "chief-service"


# ── Backoffice — modifications non sensibles ─────────────────────────────────

async def test_identity_update_syncs_admins_without_logging_user_out(client, central, subscribe):
    admin_id, a_id, _, admin = await _setup(client, central)
    a = await _login_ok(client, "a@edg.gn")
    q_a = await subscribe(a_id, "chief-service")
    q_admin = await subscribe(admin_id, "admin")

    resp = await client.put(f"/api/v1/users/{a_id}", json={"name": "Nouveau"}, headers=bearer(admin["access_token"]))
    assert resp.status_code == 200, resp.text

    assert (await _me(client, a["access_token"])).status_code == 200
    assert [e["type"] for e in drain(q_admin)] == ["user.updated"]
    assert [e["type"] for e in drain(q_a)] == ["user.updated"]  # rafraîchit son propre profil


async def test_activation_is_broadcast_to_backoffice(client, central, subscribe):
    admin_id, a_id, _, admin = await _setup(client, central)
    await client.post(f"/api/v1/users/{a_id}/deactivate", headers=bearer(admin["access_token"]))
    q_admin = await subscribe(admin_id, "admin")
    await client.post(f"/api/v1/users/{a_id}/activate", headers=bearer(admin["access_token"]))
    assert [(e["type"], e["payload"]["id"]) for e in drain(q_admin)] == [("user.updated", a_id)]


async def test_client_supplied_infos_cannot_rewind_session_version(client, central):
    _, a_id, _, admin = await _setup(client, central)
    a = await _login_ok(client, "a@edg.gn")
    await _set_role(client, admin, a_id, "user")
    # Tentative de ramener la version à 0 pour revalider l'ancien token.
    await client.put(
        f"/api/v1/users/{a_id}", json={"infos": {"session_version": 0}}, headers=bearer(admin["access_token"]),
    )
    assert (await _me(client, a["access_token"])).status_code == 401


# ── Cas 6 — deux modifications rapprochées ───────────────────────────────────

async def test_successive_admin_changes_keep_database_state_and_revoke_each_time(client, central):
    _, a_id, _, admin = await _setup(client, central)
    await _set_role(client, admin, a_id, "technicien")
    middle = await _login_ok(client, "a@edg.gn")
    await _set_role(client, admin, a_id, "user")

    assert (await _me(client, middle["access_token"])).status_code == 401
    final = await _login_ok(client, "a@edg.gn")
    assert final["user"]["role"] == "user"


# ── Suppression ──────────────────────────────────────────────────────────────

async def test_delete_revokes_session(client, central, subscribe, monkeypatch):
    from api.core import central_auth

    async def _noop(*args, **kwargs):
        return None

    monkeypatch.setattr(central_auth, "delete_central_account", _noop)
    admin_id, a_id, _, admin = await _setup(client, central)
    a = await _login_ok(client, "a@edg.gn")
    q_a = await subscribe(a_id, "chief-service")
    q_admin = await subscribe(admin_id, "admin")

    resp = await client.delete(f"/api/v1/users/{a_id}", headers=bearer(admin["access_token"]))
    assert resp.status_code == 204, resp.text
    assert (await _me(client, a["access_token"])).status_code == 401
    assert [e["payload"]["reason"] for e in drain(q_a) if e["type"] == "user.session_revoked"] == ["deleted"]
    assert ("user.deleted", a_id) in [(e["type"], e["payload"].get("id")) for e in drain(q_admin)]


# ── Flux SSE — fermeture sur révocation (Cas 1/2, 7, 10) ─────────────────────

class _FakeRequest:
    async def is_disconnected(self) -> bool:
        return False


async def _open_stream(monkeypatch, token: str):
    from api.routes import RouteSSE

    monkeypatch.setattr(RouteSSE, "AsyncSessionLocal", TestSession)
    response = await RouteSSE.stream_events(_FakeRequest(), token=token)
    stream = response.body_iterator
    first = await stream.__anext__()
    assert first["event"] == "connected"
    return RouteSSE, stream


async def test_sse_stream_sends_revocation_then_closes(client, central, monkeypatch):
    _, a_id, _, _ = await _setup(client, central)
    a = await _login_ok(client, "a@edg.gn")
    _, stream = await _open_stream(monkeypatch, a["access_token"])

    await event_bus.publish(AppEvent(
        type="user.session_revoked", payload={"user_id": a_id, "reason": "role_changed"},
        target={"user_ids": [a_id]},
    ))
    msg = await asyncio.wait_for(stream.__anext__(), timeout=2)
    assert msg["event"] == "user.session_revoked"
    assert '"reason": "role_changed"' in msg["data"]
    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(stream.__anext__(), timeout=2)


async def test_sse_keepalive_revalidates_against_database(client, central, monkeypatch):
    """Filet si l'événement est perdu : à chaque keepalive le serveur relit le
    compte et ferme le flux si l'état n'est plus celui de la connexion."""
    _, a_id, _, _ = await _setup(client, central)
    a = await _login_ok(client, "a@edg.gn")
    RouteSSE, stream = await _open_stream(monkeypatch, a["access_token"])
    monkeypatch.setattr(RouteSSE, "_PING_INTERVAL", 0.05)

    ping = await asyncio.wait_for(stream.__anext__(), timeout=2)
    assert ping["event"] == "ping"

    # Désactivation écrite directement en base (ex. par la plateforme centrale
    # qui partage la table), sans aucun événement.
    from api.repositories import AccountRepository
    async with TestSession() as session:
        await AccountRepository(session).update(a_id, {"status": False, "account_status": "inactive"})

    msg = await asyncio.wait_for(stream.__anext__(), timeout=2)
    assert msg["event"] == "user.session_revoked"
    assert '"reason": "disabled"' in msg["data"]
    with pytest.raises(StopAsyncIteration):
        await asyncio.wait_for(stream.__anext__(), timeout=2)


async def test_sse_connection_with_revoked_token_is_refused(client, central, monkeypatch):
    _, a_id, _, admin = await _setup(client, central)
    a = await _login_ok(client, "a@edg.gn")
    await _set_role(client, admin, a_id, "user")
    from api.routes import RouteSSE

    monkeypatch.setattr(RouteSSE, "AsyncSessionLocal", TestSession)
    with pytest.raises(session_registry.SessionRevokedException):
        await RouteSSE.stream_events(_FakeRequest(), token=a["access_token"])


# ── Token inconnu (émis hors des routes EDG Connect) ─────────────────────────

async def test_unknown_token_is_bound_on_first_use_then_revocable(client, central):
    _, a_id, _, admin = await _setup(client, central)
    foreign = central.issue(2)["access_token"]  # jamais passé par /auth/login
    assert (await _me(client, foreign)).status_code == 200
    await _set_role(client, admin, a_id, "user")
    assert (await _me(client, foreign)).status_code == 401
