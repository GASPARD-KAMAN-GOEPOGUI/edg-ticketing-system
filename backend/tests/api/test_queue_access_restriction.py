"""Module 2 — Restriction d'acces a la File d'attente.

La gestion de la File d'attente (liste de triage + qualification) est reservee
au chef de service (CSSHF, role `chief-service`) et a l'admin. Les autres roles
operationnels (technicien, chef-division-support, chief-departement, director)
n'y ont plus acces.

Verifie aussi la non-regression : les endpoints voisins partageant le garde
`_staff` (/queue, /transmitted, /sla-breached) restent ouverts a ces roles.
"""
from __future__ import annotations

import pytest

from tests.api.test_requests_baseline import _ensure_test_account
from tests.api.test_transmit_treatment import _call_as, _dep

_ALLOWED = ["chief-service", "admin"]
_DENIED = ["technicien", "chef-division-support", "chief-departement", "director"]


@pytest.mark.parametrize("role", _ALLOWED)
async def test_triage_list_autorise_pour_chief_service_et_admin(role, unity_id):
    account_id = 8100 + _ALLOWED.index(role)
    await _ensure_test_account(account_id, unity_id=unity_id, role=role)

    resp = await _call_as(_dep(account_id, role, unity_id), "GET", "/api/v1/requests/triage")
    assert resp.status_code == 200, resp.text


@pytest.mark.parametrize("role", _DENIED)
async def test_triage_list_refuse_pour_les_autres_roles(role, unity_id):
    account_id = 8200 + _DENIED.index(role)
    await _ensure_test_account(account_id, unity_id=unity_id, role=role)

    resp = await _call_as(_dep(account_id, role, unity_id), "GET", "/api/v1/requests/triage")
    assert resp.status_code == 403, resp.text


@pytest.mark.parametrize("role", _DENIED)
async def test_qualify_refuse_pour_les_autres_roles(role, unity_id):
    account_id = 8300 + _DENIED.index(role)
    await _ensure_test_account(account_id, unity_id=unity_id, role=role)

    resp = await _call_as(
        _dep(account_id, role, unity_id), "POST", "/api/v1/requests/1/qualify",
        {"category": "panne", "priority": "medium", "unit_id": str(unity_id)},
    )
    assert resp.status_code == 403, resp.text


@pytest.mark.parametrize("role", _DENIED)
async def test_non_regression_endpoints_voisins_restent_ouverts(role, unity_id):
    """Les endpoints partageant l'ancien garde `_staff` ne doivent PAS avoir ete
    restreints au passage — seule la File d'attente l'est."""
    account_id = 8400 + _DENIED.index(role)
    await _ensure_test_account(account_id, unity_id=unity_id, role=role)

    for path in ("/api/v1/requests/queue", "/api/v1/requests/transmitted", "/api/v1/requests/sla-breached"):
        resp = await _call_as(_dep(account_id, role, unity_id), "GET", path)
        assert resp.status_code == 200, f"{path} -> {resp.status_code} {resp.text}"
