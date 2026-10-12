"""
Limitation des tentatives et CORS : les requêtes préalables OPTIONS ne sont
pas comptées, et la réponse 429 reste lisible par le frontend (en-têtes CORS).
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient

from api import dependencies
from api.main import app

ORIGIN = "https://support.edgportal.com"
PREFLIGHT = {
    "Origin": ORIGIN,
    "Access-Control-Request-Method": "POST",
    "Access-Control-Request-Headers": "content-type",
}


def _client(peer: str) -> AsyncClient:
    return AsyncClient(transport=ASGITransport(app=app, client=(peer, 40000)), base_url="http://test")


async def test_preflight_not_counted_and_429_on_eleventh_real_attempt(central, monkeypatch):
    monkeypatch.setattr(dependencies._env, "TRUSTED_PROXIES", [])
    async with _client("203.0.113.70") as c:
        for _ in range(15):  # OPTIONS répétés : jamais limités, jamais comptés
            assert (await c.options("/api/v1/auth/login", headers=PREFLIGHT)).status_code == 200
        codes = [
            (await c.post("/api/v1/auth/login", json={"identifier": "x@edg.gn", "password": "x"},
                          headers={"Origin": ORIGIN})).status_code
            for _ in range(11)
        ]
    assert 429 not in codes[:10] and codes[10] == 429


async def test_429_response_carries_cors_headers(central, monkeypatch):
    monkeypatch.setattr(dependencies._env, "TRUSTED_PROXIES", [])
    async with _client("203.0.113.71") as c:
        for _ in range(10):
            await c.post("/api/v1/auth/login", json={"identifier": "x@edg.gn", "password": "x"},
                         headers={"Origin": ORIGIN})
        resp = await c.post("/api/v1/auth/login", json={"identifier": "x@edg.gn", "password": "x"},
                            headers={"Origin": ORIGIN})
    assert resp.status_code == 429
    assert resp.headers.get("access-control-allow-origin") in (ORIGIN, "*")


async def test_500_from_middleware_carries_cors_headers(central):
    """Exception non gérée dans une route : RequestLoggingMiddleware produit la
    réponse 500 JSON ; CORS, plus externe, doit y ajouter ses en-têtes."""
    async def boom():
        raise RuntimeError("panne simulée")

    app.add_api_route("/__test_boom", boom, methods=["GET"])
    try:
        async with _client("203.0.113.72") as c:
            resp = await c.get("/__test_boom", headers={"Origin": ORIGIN})
    finally:
        app.router.routes[:] = [r for r in app.router.routes if getattr(r, "path", "") != "/__test_boom"]
    assert resp.status_code == 500
    assert resp.headers.get("access-control-allow-origin") in (ORIGIN, "*")
