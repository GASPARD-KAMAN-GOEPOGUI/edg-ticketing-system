"""
Garde-fou : routes accessibles SANS session (sans `get_current_user`).

Une route de diagnostic « temporaire » (POST /auth/debug/source-token) est
restée publique en production : elle échangeait les identifiants secrets de
l'application contre un jeton de la plateforme centrale et le renvoyait à
n'importe qui. Toute nouvelle route sans session doit désormais être ajoutée
ici, explicitement, après revue.
"""
from __future__ import annotations

from fastapi.routing import APIRoute

from api.dependencies import get_current_user
from api.main import app

# Écritures sans session : uniquement le parcours d'authentification, chacune
# protégée autrement (identifiants, code, jeton fourni, limitation d'essais).
PUBLIC_WRITE_ROUTES = {
    "POST /api/v1/auth/login",
    "POST /api/v1/auth/register",
    "POST /api/v1/auth/forgot-password",
    "POST /api/v1/auth/reset-password",
    "POST /api/v1/auth/consent/accept",
    "POST /api/v1/auth/refresh",
    "POST /api/v1/auth/logout",
}

# Lectures sans session (certaines vérifient elles-mêmes un jeton).
PUBLIC_READ_ROUTES = {
    "GET /",
    "GET /health",
    "GET /api/v1/public/directions/count",
    "GET /api/v1/requests/track",
    "GET /api/v1/users/avatars/{filename}",
    "GET /api/v1/events",
    "GET /api/v1/auth/me/groups",
    "GET /api/v1/auth/me/scopes",
}


def _needs_session(dependant) -> bool:
    return any(d.call is get_current_user or _needs_session(d) for d in dependant.dependencies)


def _routes_without_session() -> tuple[set[str], set[str]]:
    writes, reads = set(), set()
    for route in app.routes:
        if not isinstance(route, APIRoute) or _needs_session(route.dependant):
            continue
        for method in route.methods - {"HEAD"}:
            (reads if method == "GET" else writes).add(f"{method} {route.path}")
    return writes, reads


def test_only_reviewed_routes_are_reachable_without_session():
    writes, reads = _routes_without_session()
    assert writes == PUBLIC_WRITE_ROUTES, f"écritures publiques non revues : {sorted(writes ^ PUBLIC_WRITE_ROUTES)}"
    assert reads == PUBLIC_READ_ROUTES, f"lectures publiques non revues : {sorted(reads ^ PUBLIC_READ_ROUTES)}"


async def test_debug_source_token_route_is_gone(client):
    resp = await client.post("/api/v1/auth/debug/source-token", json={})
    assert resp.status_code in (404, 405)
