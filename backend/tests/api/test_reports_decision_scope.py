from __future__ import annotations

from types import SimpleNamespace

import pytest

from api.routes.RouteReports import _apply_decision_scope


def actor(role: str, *, id: int = 1, unity_id: int | None = 1, direction_id: int | None = None):
    return SimpleNamespace(role=role, id=id, unity_id=unity_id, direction_id=direction_id)


class _SvcNeverCalled:
    """Stand-in ReportService qui échoue si `_scoped_unity_ids` est appelée."""

    async def _scoped_unity_ids(self, unity_id: int) -> list[int]:
        raise AssertionError("_scoped_unity_ids ne doit pas être appelée sans unity_id sur le compte.")


class _SvcStub:
    """Stand-in ReportService renvoyant un périmètre départemental canné."""

    def __init__(self, department_scope: list[int]) -> None:
        self.department_scope = department_scope
        self.called_with: int | None = None

    async def _scoped_unity_ids(self, unity_id: int) -> list[int]:
        self.called_with = unity_id
        return self.department_scope


@pytest.mark.asyncio
async def test_chief_departement_without_unity_id_falls_back_to_sentinel():
    """Repli explicite [-1] (aucun résultat) quand le compte chief-departement n'a pas d'unité."""
    svc = _SvcNeverCalled()
    direction_id, unity_id = await _apply_decision_scope(
        actor("chief-departement", unity_id=None), None, None, svc,
    )
    assert direction_id is None
    assert unity_id == [-1]


@pytest.mark.asyncio
async def test_chief_departement_expands_scope_via_scoped_unity_ids():
    """Avec une unité de rattachement, le périmètre est élargi via _scoped_unity_ids (département + services)."""
    svc = _SvcStub(department_scope=[1, 2, 3])
    direction_id, unity_id = await _apply_decision_scope(
        actor("chief-departement", unity_id=7), None, None, svc,
    )
    assert direction_id is None
    assert unity_id == [1, 2, 3]
    assert svc.called_with == 7


@pytest.mark.asyncio
async def test_chief_service_keeps_exact_unity_match_unchanged():
    """Régression : chief-service garde la correspondance exacte, sans expansion département."""
    svc = _SvcNeverCalled()
    direction_id, unity_id = await _apply_decision_scope(
        actor("chief-service", unity_id=7), None, None, svc,
    )
    assert direction_id is None
    assert unity_id == 7


@pytest.mark.asyncio
async def test_chief_service_without_unity_id_falls_back_to_sentinel():
    svc = _SvcNeverCalled()
    direction_id, unity_id = await _apply_decision_scope(
        actor("chief-service", unity_id=None), None, None, svc,
    )
    assert unity_id == -1


@pytest.mark.asyncio
async def test_director_forces_own_direction_unchanged():
    """Régression : le scope director n'est pas affecté par ce correctif."""
    svc = _SvcNeverCalled()
    direction_id, unity_id = await _apply_decision_scope(
        actor("director", unity_id=None, direction_id=5), None, None, svc,
    )
    assert direction_id == 5
    assert unity_id is None
