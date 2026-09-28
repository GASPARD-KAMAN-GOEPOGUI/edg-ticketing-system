"""Edition des referentiels depuis l'Administration (statuts, categories, priorites).

Deux regles, a ne pas confondre :

1. **Le libelle est librement modifiable**, y compris sur une valeur integree —
   ce n'est que de l'affichage.
2. **Le code d'une valeur integree est immuable** : les codes de statut sont des
   litteraux a une centaine d'endroits du backend, et les politiques SLA
   retrouvent categories et priorites par le TEXTE de leur code.

Et pour l'archivage, la protection porte desormais sur l'USAGE et non sur le
caractere integre : une valeur integree que plus aucun ticket ne porte est
inoffensive, alors qu'une valeur creee a la main mais portee par des tickets ne
doit pas disparaitre.
"""
from __future__ import annotations

import pytest

from tests.conftest import _TestSession

_BASE = "/api/v1/references"


def _payload(response):
    body = response.json()
    return body.get("data", body)


async def _seed(model_cls, **fields):
    async with _TestSession() as session:
        obj = model_cls(**fields)
        session.add(obj)
        await session.commit()
        await session.refresh(obj)
        return obj.id


async def _make_status(code: str, *, builtin: bool) -> int:
    from api.models.ModelRequestStatus import RequestStatus
    return await _seed(
        RequestStatus, code=code, label=f"Libelle {code}",
        sort_order=90, is_builtin=builtin, status=True,
    )


async def _make_category(code: str, *, builtin: bool) -> int:
    from api.models.ModelRequestCategory import RequestCategory
    return await _seed(
        RequestCategory, code=code, label=f"Libelle {code}",
        sort_order=90, is_builtin=builtin, status=True,
    )


# ── Libelle : modifiable partout ─────────────────────────────────────────────

@pytest.mark.parametrize("builtin", [True, False])
async def test_le_libelle_est_modifiable_y_compris_sur_une_valeur_integree(auth_client, builtin):
    status_id = await _make_status(f"tst_lib_{int(builtin)}", builtin=builtin)

    async with auth_client("admin") as client:
        resp = await client.put(
            f"{_BASE}/request-statuses/{status_id}", json={"label": "Nouveau libelle"},
        )

    assert resp.status_code == 200, resp.text
    assert _payload(resp)["label"] == "Nouveau libelle"


# ── Code : immuable sur une valeur integree ──────────────────────────────────

async def test_le_code_d_une_valeur_integree_ne_peut_pas_etre_modifie(auth_client):
    status_id = await _make_status("tst_code_builtin", builtin=True)

    async with auth_client("admin") as client:
        resp = await client.put(
            f"{_BASE}/request-statuses/{status_id}", json={"code": "tst_code_renomme"},
        )

    assert resp.status_code == 400, resp.text
    assert "int" in resp.text.lower()  # message mentionnant « intégrée »


async def test_le_code_d_une_valeur_creee_reste_modifiable(auth_client):
    status_id = await _make_status("tst_code_libre", builtin=False)

    async with auth_client("admin") as client:
        resp = await client.put(
            f"{_BASE}/request-statuses/{status_id}", json={"code": "tst_code_libre2"},
        )

    assert resp.status_code == 200, resp.text
    assert _payload(resp)["code"] == "tst_code_libre2"


async def test_reecrire_le_meme_code_n_est_pas_un_changement(auth_client):
    """Renvoyer le code inchange (cas d'un formulaire qui poste tous ses champs)
    ne doit pas etre refuse."""
    status_id = await _make_status("tst_code_idem", builtin=True)

    async with auth_client("admin") as client:
        resp = await client.put(
            f"{_BASE}/request-statuses/{status_id}",
            json={"code": "tst_code_idem", "label": "Libelle revise"},
        )

    assert resp.status_code == 200, resp.text
    assert _payload(resp)["label"] == "Libelle revise"


async def test_la_categorie_suit_la_meme_regle(auth_client):
    builtin_id = await _make_category("tst_cat_builtin", builtin=True)
    libre_id = await _make_category("tst_cat_libre", builtin=False)

    async with auth_client("admin") as client:
        refuse = await client.put(
            f"{_BASE}/request-categories/{builtin_id}", json={"code": "tst_cat_autre"},
        )
        accepte = await client.put(
            f"{_BASE}/request-categories/{libre_id}", json={"code": "tst_cat_libre2"},
        )

    assert refuse.status_code == 400, refuse.text
    assert accepte.status_code == 200, accepte.text


# ── Archivage : la protection porte sur l'USAGE ──────────────────────────────

async def test_une_valeur_integree_inutilisee_peut_etre_archivee(auth_client):
    """C'est le changement de fond : « integre » ne protege plus."""
    status_id = await _make_status("tst_arch_builtin", builtin=True)

    async with auth_client("admin") as client:
        resp = await client.delete(f"{_BASE}/request-statuses/{status_id}")

    assert resp.status_code in (200, 204), resp.text


async def test_une_valeur_utilisee_ne_peut_pas_etre_archivee(auth_client, unity_id):
    """Meme creee a la main, une valeur portee par des tickets ne disparait pas."""
    from tests.api.test_transmit_treatment import _create_ticket
    from api.models.ModelRequest import Request as RequestModel

    category_id = await _make_category("tst_cat_utilisee", builtin=False)
    request_id = await _create_ticket(auth_client, unity_id, "ref-usage")
    async with _TestSession() as session:
        obj = await session.get(RequestModel, int(request_id))
        obj.request_category_id = category_id
        await session.commit()

    async with auth_client("admin") as client:
        resp = await client.delete(f"{_BASE}/request-categories/{category_id}")

    assert resp.status_code == 400, resp.text
    assert "1 ticket" in resp.text, resp.text  # le message dit COMBIEN
    assert "sactiv" in resp.text  # et propose la desactivation


async def test_une_valeur_archivee_peut_etre_restauree(auth_client):
    status_id = await _make_status("tst_arch_restore", builtin=True)

    async with auth_client("admin") as client:
        archived = await client.delete(f"{_BASE}/request-statuses/{status_id}")
        assert archived.status_code in (200, 204), archived.text
        restored = await client.put(f"{_BASE}/request-statuses/{status_id}/restore")

    assert restored.status_code == 200, restored.text
