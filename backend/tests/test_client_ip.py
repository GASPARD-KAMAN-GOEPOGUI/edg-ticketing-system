"""
IP du client (api/core/client_ip.py) : X-Forwarded-For n'est cru que s'il
arrive d'un proxy de confiance (TRUSTED_PROXIES, IP ou CIDR). Même fonction
pour la limitation des tentatives et pour le journal d'audit.
"""
from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select
from starlette.requests import Request

from api import dependencies
from api.main import app
from api.core.client_ip import client_ip
from api.models.ModelActivityLog import ActivityLog
from tests.support import TestSession, make_account


def _req(peer: str, xff: str | None = None) -> Request:
    """Vraie requête Starlette, comme celle construite par a2wsgi (client = REMOTE_ADDR)."""
    headers = [(b"x-forwarded-for", xff.encode())] if xff is not None else []
    return Request({"type": "http", "method": "GET", "path": "/", "headers": headers, "client": (peer, 40000)})


def _trust(monkeypatch, *entries: str) -> None:
    monkeypatch.setattr(dependencies._env, "TRUSTED_PROXIES", list(entries))


def test_forged_header_ignored_without_trusted_proxy(monkeypatch):
    _trust(monkeypatch)
    assert client_ip(_req("203.0.113.7", "1.2.3.4")) == "203.0.113.7"


def test_header_used_from_listed_proxy(monkeypatch):
    _trust(monkeypatch, "10.0.0.5")
    assert client_ip(_req("10.0.0.5", "198.51.100.9")) == "198.51.100.9"


def test_proxy_declared_as_cidr_range(monkeypatch):
    _trust(monkeypatch, "10.0.0.0/8")
    assert client_ip(_req("10.20.30.40", "198.51.100.9")) == "198.51.100.9"
    assert client_ip(_req("11.0.0.1", "198.51.100.9")) == "11.0.0.1"  # hors plage


def test_chain_of_proxies_takes_rightmost_untrusted(monkeypatch):
    _trust(monkeypatch, "10.0.0.0/8", "172.16.0.1")
    # client falsifie la 1re valeur ; le proxy externe ajoute l'IP réelle ;
    # deux proxies de confiance suivent.
    req = _req("172.16.0.1", "6.6.6.6, 198.51.100.9, 10.1.1.1")
    assert client_ip(req) == "198.51.100.9"


def test_ipv6_and_malformed_values(monkeypatch):
    _trust(monkeypatch, "2001:db8::/32")
    assert client_ip(_req("2001:db8::1", "2001:db9::42")) == "2001:db9::42"
    assert client_ip(_req("2001:db8::1", "pas-une-ip")) == "2001:db8::1"


def test_invalid_trusted_proxy_entry_is_rejected(monkeypatch):
    _trust(monkeypatch, "pas-un-reseau")
    with pytest.raises(ValueError, match="TRUSTED_PROXIES"):
        client_ip(_req("10.0.0.5", "1.2.3.4"))


def _client_from(peer: str) -> AsyncClient:
    """Client HTTP dont la connexion vient de `peer` (REMOTE_ADDR)."""
    return AsyncClient(transport=ASGITransport(app=app, client=(peer, 40000)), base_url="http://test")


async def test_rate_limit_not_bypassed_by_rotating_header(central, monkeypatch):
    _trust(monkeypatch)  # aucun proxy de confiance : production par défaut
    codes = []
    async with _client_from("203.0.113.50") as c:
        for i in range(12):
            resp = await c.post(
                "/api/v1/auth/login", json={"identifier": "x@edg.gn", "password": "x"},
                headers={"X-Forwarded-For": f"10.9.{i}.{i}"},
            )
            codes.append(resp.status_code)
    assert codes[:10].count(429) == 0 and codes[10:] == [429, 429]


async def test_audit_log_uses_same_client_ip(central, monkeypatch):
    _trust(monkeypatch)
    await make_account(central, email="me@edg.gn", role="user", central_id=10)
    async with _client_from("203.0.113.60") as c:
        resp = await c.post(
            "/api/v1/auth/login", json={"identifier": "me@edg.gn", "password": "secret"},
            headers={"X-Forwarded-For": "6.6.6.6"},
        )
    assert resp.status_code == 200, resp.text
    async with TestSession() as s:
        ips = (await s.execute(select(ActivityLog.ip_address).where(ActivityLog.action == "login"))).scalars().all()
    assert ips == ["203.0.113.60"]  # adresse de connexion, pas l'en-tête falsifié
