from __future__ import annotations

from types import SimpleNamespace

import pytest
from httpx import ASGITransport, AsyncClient

from api.dependencies import get_current_user
from api.main import app

_REQUEST_PAYLOAD_BASE = {
    "description": "Description de test pour le scope director du dashboard stratégique (Lot 4.4).",
    "category": "panne",
    "priority": "medium",
    "is_external": False,
    "requester_name": "Citoyen Test",
    "requester_email": "citoyen@test.edg.gn",
}

# Lot 4.4 — DECOUVERTE FAITE EN ECRIVANT CE TEST (pas liee au code du Lot 4) :
# ServiceReport._decision_rows() utilise GROUP_CONCAT(... SEPARATOR ' | ') dans sa
# sous-requete workflow_detail (lignes ~391-400) — syntaxe MySQL uniquement. SQLite
# (moteur de la suite de tests, cf. conftest.py) ne supporte pas le mot-cle SEPARATOR
# et leve "OperationalError: near SEPARATOR: syntax error" pour TOUT appel HTTP a
# /reports/decision, quel que soit le role. Verifie : aucun test existant dans la
# suite n'appelait cet endpoint via HTTP avant celui-ci (grep sur tous les fichiers
# de tests) — la couverture reelle etait donc nulle, pas seulement pour director.
# Consequence pour ce lot : le round-trip HTTP complet (creer un ticket, appeler
# /reports/decision, verifier le contenu de la reponse) est impossible a executer
# ici tant que cette incompatibilite SQLite n'est pas corrigee (hors perimetre du
# Lot 4 — correctif de portabilite SQL a valider separement). Les tests ci-dessous
# restent ecrits et documentent precisement le scenario a verifier ; ils sont
# marques `skip` avec la raison exacte plutot que supprimes, pour rester
# executables tels quels des que le correctif SQL sera fait (ou en environnement
# MySQL reel).
_SKIP_REASON = (
    "GROUP_CONCAT(...SEPARATOR...) dans ServiceReport._decision_rows() est une "
    "syntaxe MySQL non supportee par SQLite (moteur de test) — /reports/decision "
    "renvoie 500 pour tout role via HTTP dans cette suite. Bug pre-existant, "
    "decouvert par ce test, hors perimetre du Lot 4."
)


@pytest.mark.skip(reason=_SKIP_REASON)
async def test_director_decision_report_is_scoped_to_own_direction_not_empty(auth_client, unity_id):
    """Lot 4.4 — garde-fou avant la mise en prod du dashboard stratégique.

    `Account.direction_id` (ModelAccount.py) est une propriété Python qui retourne
    `unity_id` uniquement quand role == "director" — `_apply_decision_scope` s'appuie
    dessus (`actor.direction_id`). Un acteur de test mal construit (sans cette
    propriété, ex. un SimpleNamespace sans `direction_id` explicite) forcerait un
    repli `direction_id = -1` et retournerait TOUJOURS une réponse vide, quel que
    soit le contenu réel de la base — ce test simule explicitement la valeur que la
    propriété réelle calculerait, pour prouver que le scope fonctionne bout-en-bout
    et que le dashboard stratégique ne serait pas silencieusement vide pour un
    directeur réel.
    """
    async with auth_client("user") as user_client:
        payload = {**_REQUEST_PAYLOAD_BASE, "title": "Test director scope ticket", "unity_id": unity_id}
        resp = await user_client.post("/api/v1/requests/", json=payload)
        assert resp.status_code == 201, resp.text

    def _director_dep():
        # Simule Account.direction_id : pour un director reel, cette propriete
        # retourne unity_id — on le reproduit explicitement ici.
        return SimpleNamespace(id=980, role="director", unity_id=unity_id, direction_id=unity_id)

    app.dependency_overrides[get_current_user] = _director_dep
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/reports/decision?group_by=service")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200, resp.text
    data = resp.json()["data"]
    assert data["kpis"]["total_tickets"] >= 1
    assert len(data["tables"]["analytical"]["rows"]) >= 1


@pytest.mark.skip(reason=_SKIP_REASON)
async def test_director_without_direction_id_gets_empty_scope_not_a_crash(auth_client, unity_id):
    """Regression inverse : si `direction_id` est bien absent (compte mal rattaché),
    le scope doit rester vide et sûr (repli -1), jamais une vue globale non filtrée
    ni une erreur serveur."""
    async with auth_client("user") as user_client:
        payload = {**_REQUEST_PAYLOAD_BASE, "title": "Test director no direction_id", "unity_id": unity_id}
        resp = await user_client.post("/api/v1/requests/", json=payload)
        assert resp.status_code == 201, resp.text

    def _director_dep():
        return SimpleNamespace(id=981, role="director", unity_id=None, direction_id=None)

    app.dependency_overrides[get_current_user] = _director_dep
    try:
        async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as client:
            resp = await client.get("/api/v1/reports/decision?group_by=service")
    finally:
        app.dependency_overrides.pop(get_current_user, None)

    assert resp.status_code == 200, resp.text
    assert resp.json()["data"]["kpis"]["total_tickets"] == 0
