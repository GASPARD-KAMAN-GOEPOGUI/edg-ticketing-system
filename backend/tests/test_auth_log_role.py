"""
Les événements de connexion sans compte authentifié (échec, consentement en
attente) sont journalisés avec actor_role='public', valeur de l'ENUM
activity_log.actor_role. L'ancienne valeur 'unknown' faisait renvoyer 500 au
login sur un MySQL strict et cassait la lecture du journal admin.
"""
from __future__ import annotations

from sqlalchemy import select

from api.core import central_auth
from api.models.ModelActivityLog import ActivityLog
from tests.support import TestSession, bearer, login, make_account


async def _roles_for(action: str) -> list[str]:
    async with TestSession() as s:
        return list((await s.execute(
            select(ActivityLog.actor_role).where(ActivityLog.action == action)
        )).scalars().all())


async def test_failed_login_logged_as_public_and_journal_readable(client, central):
    await make_account(central, email="adm@edg.gn", role="admin", central_id=1)
    bad = await client.post("/api/v1/auth/login", json={"identifier": "inconnu@edg.gn", "password": "x"},
                            headers={"X-Forwarded-For": "10.8.0.1"})
    assert bad.status_code == 401
    bad_matricule = await client.post("/api/v1/auth/login", json={"identifier": "MAT-404", "password": "x"},
                                      headers={"X-Forwarded-For": "10.8.0.2"})
    assert bad_matricule.status_code == 401
    assert await _roles_for("login_failed") == ["public", "public"]

    tok = (await login(client, "adm@edg.gn"))["body"]["data"]["access_token"]
    journal = await client.get("/api/v1/activity-logs/?limit=50", headers=bearer(tok))
    assert journal.status_code == 200, journal.text


async def test_consent_pending_logged_as_public(client, central, monkeypatch):
    async def no_profile(bearer_token):  # aucun appel réseau à la plateforme centrale
        return {}

    monkeypatch.setattr(central_auth, "get_profile", no_profile)
    central.users["nouveau@edg.gn"] = 99
    central.groups[99] = set()  # aucun groupe support : consentement requis
    resp = await client.post("/api/v1/auth/login", json={"identifier": "nouveau@edg.gn", "password": "secret"},
                             headers={"X-Forwarded-For": "10.8.0.3"})
    assert resp.status_code == 200 and resp.json()["data"]["needs_consent"] is True
    assert await _roles_for("login_needs_consent") == ["public"]
