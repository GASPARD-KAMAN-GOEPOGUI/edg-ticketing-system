"""
Déconnexion = révocation côté serveur de l'access ET du refresh token
(table revoked_token, vue par tous les processus).

La plateforme centrale simulée (FakeCentral), comme la vraie, continue
d'accepter les jetons après la déconnexion : ces tests prouvent que c'est
EDG Connect qui les refuse.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy import select

from api.core import token_revocation
from api.models.ModelRevokedToken import RevokedToken
from tests.support import TestSession, bearer, login, make_account


async def _session(client, central, email="me@edg.gn", central_id=10) -> dict:
    await make_account(central, email=email, role="user", central_id=central_id)
    return (await login(client, email))["body"]["data"]


async def test_logout_revokes_access_and_refresh_tokens(client, central):
    s = await _session(client, central)
    assert (await client.get("/api/v1/auth/me", headers=bearer(s["access_token"]))).status_code == 200

    resp = await client.post(
        "/api/v1/auth/logout", json={"refresh_token": s["refresh_token"]}, headers=bearer(s["access_token"]),
    )
    assert resp.status_code == 204, resp.text

    # Le central accepterait encore ces jetons ; EDG Connect les refuse.
    assert s["access_token"] in central.access and s["refresh_token"] in central.refresh
    me = await client.get("/api/v1/auth/me", headers=bearer(s["access_token"]))
    assert me.status_code == 401
    ref = await client.post("/api/v1/auth/refresh", json={"refresh_token": s["refresh_token"]})
    assert ref.status_code == 401
    assert ref.json()["error_code"] == "SESSION_REVOKED"


async def test_refresh_works_before_logout_and_other_sessions_untouched(client, central):
    mine = await _session(client, central)
    other = await _session(client, central, email="other@edg.gn", central_id=11)
    ok = await client.post("/api/v1/auth/refresh", json={"refresh_token": mine["refresh_token"]})
    assert ok.status_code == 200  # témoin : le refresh fonctionne avant la déconnexion

    await client.post(
        "/api/v1/auth/logout", json={"refresh_token": mine["refresh_token"]}, headers=bearer(mine["access_token"]),
    )
    assert (await client.get("/api/v1/auth/me", headers=bearer(other["access_token"]))).status_code == 200
    ref = await client.post("/api/v1/auth/refresh", json={"refresh_token": other["refresh_token"]})
    assert ref.status_code == 200


async def test_second_logout_is_harmless_and_only_hashes_are_stored(client, central):
    s = await _session(client, central)
    for _ in range(2):
        resp = await client.post(
            "/api/v1/auth/logout", json={"refresh_token": s["refresh_token"]}, headers=bearer(s["access_token"]),
        )
        assert resp.status_code == 204
    async with TestSession() as db:
        rows = (await db.execute(select(RevokedToken))).scalars().all()
    stored = {r.token_hash for r in rows}
    assert stored == {token_revocation.token_hash(s["access_token"]), token_revocation.token_hash(s["refresh_token"])}
    assert all(s["access_token"] not in h and s["refresh_token"] not in h for h in stored)
    retention = rows[0].expires_at - rows[0].revoked_at
    assert retention == timedelta(seconds=token_revocation.REVOCATION_TTL_SECONDS) == timedelta(hours=24)


async def test_expired_revocation_no_longer_applies():
    async with TestSession() as db:
        db.add(RevokedToken(
            token_hash=token_revocation.token_hash("vieux"),
            revoked_at=datetime.utcnow() - timedelta(days=2),
            expires_at=datetime.utcnow() - timedelta(days=1),
        ))
        await db.commit()
        assert await token_revocation.is_revoked(db, "vieux") is False
