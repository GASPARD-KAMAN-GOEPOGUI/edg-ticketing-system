"""
Stockage de l'état partagé (liaisons de session, limitation des tentatives) — EDG Support.

STATE_BACKEND :
  auto  (défaut) : Redis si REDIS_URL est renseigné, sinon mémoire du
                   processus (développement monoprocessus) — comportement
                   historique, inchangé.
  redis          : Redis obligatoire (REDIS_URL requis).
  mysql          : tables session_binding et rate_limit_counter, partagées
                   entre processus (cPanel/Passenger sans Redis). Aucun repli
                   en mémoire.

Le bus d'événements temps réel n'en dépend pas (REDIS_URL seul, lot 5).
"""
from __future__ import annotations

from api.configs.Environment import get_environment

VALID_STATE_BACKENDS = frozenset({"auto", "redis", "mysql"})


def configured() -> str:
    return (get_environment().STATE_BACKEND or "auto").strip().lower()


def effective() -> str:
    """'mysql', 'redis' ou 'memory'."""
    value = configured()
    if value == "mysql":
        return "mysql"
    if value == "redis" or get_environment().REDIS_URL:
        return "redis"
    return "memory"


def use_mysql() -> bool:
    return effective() == "mysql"
