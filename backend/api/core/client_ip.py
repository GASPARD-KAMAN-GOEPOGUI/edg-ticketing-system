"""
Adresse IP du client — EDG Support.

Source unique pour la limitation des tentatives (RateLimitMiddleware) et le
journal d'audit (RouteAuth).

`X-Forwarded-For` est fourni par le client : n'importe qui peut y écrire
n'importe quoi. Il n'est donc lu QUE si la connexion vient d'un proxy de
confiance (TRUSTED_PROXIES : IP ou plages CIDR). Dans ce cas, on parcourt la
chaîne de droite à gauche en sautant les proxies de confiance : la première
adresse restante est celle que le dernier proxy de confiance a vue se
connecter, la seule qu'un client ne peut pas choisir.

Sans proxy de confiance (défaut), l'IP est l'adresse de la connexion
(REMOTE_ADDR sous Passenger, transmise par a2wsgi dans request.client).
"""
from __future__ import annotations

import ipaddress
from functools import lru_cache
from typing import Iterable

from starlette.requests import Request

from api.configs.Environment import get_environment

_Network = ipaddress.IPv4Network | ipaddress.IPv6Network


@lru_cache(maxsize=8)
def _parse_networks(entries: tuple[str, ...]) -> tuple[_Network, ...]:
    networks = []
    for entry in entries:
        try:
            networks.append(ipaddress.ip_network(entry.strip(), strict=False))
        except ValueError as exc:
            raise ValueError(f"TRUSTED_PROXIES : entrée invalide {entry!r} ({exc})") from exc
    return tuple(networks)


def _is_trusted(address: str, networks: Iterable[_Network]) -> bool:
    try:
        ip = ipaddress.ip_address(address)
    except ValueError:
        return False
    return any(ip in net for net in networks)


def trusted_networks() -> tuple[_Network, ...]:
    return _parse_networks(tuple(get_environment().TRUSTED_PROXIES))


def client_ip(request: Request) -> str | None:
    peer = request.client.host if request.client else None
    networks = trusted_networks()
    if not peer or not _is_trusted(peer, networks):
        return peer

    hops = [h.strip() for h in request.headers.get("X-Forwarded-For", "").split(",") if h.strip()]
    for hop in reversed(hops):
        if not _is_trusted(hop, networks):
            try:
                ipaddress.ip_address(hop)
            except ValueError:
                return peer  # valeur malformée juste avant un proxy de confiance
            return hop
    return hops[0] if hops else peer
