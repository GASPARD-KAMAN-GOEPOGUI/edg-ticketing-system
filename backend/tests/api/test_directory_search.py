"""
Sélecteur @mention (annuaire) — GET /users/?search=...

Couvre la recherche tokenisée multi-mots (prénom+nom dans les deux ordres),
la tolérance de formatage téléphone (core/phone.py), la non-régression du
cas mono-mot (matricule, nom seul), la gestion des homonymes (aucune
sélection automatique, désambiguïsation par matricule/service), et la
combinaison recherche libre + filtre organigramme (direction_id/unit_id).

N'exerce aucune règle de transmission/traitement (transmit_treatment,
assignee_id) — lecture seule sur l'annuaire.
"""
from __future__ import annotations

from tests.conftest import _TestSession
from tests.api.test_requests_baseline import _ensure_test_unity
from tests.api.test_transmit_treatment import _call_as, _dep


async def _make_person(
    account_id: int,
    *,
    unity_id: int,
    firstname: str,
    name: str,
    matricule: str,
    phone: str | None = None,
    role: str = "chief-service",
) -> None:
    from api.models.ModelAccount import Account

    async with _TestSession() as session:
        existing = await session.get(Account, account_id)
        if existing is not None:
            existing.unity_id = unity_id
            existing.firstname = firstname
            existing.name = name
            existing.matricule = matricule
            existing.phone = phone
            existing.role = role
            existing.account_status = "active"
            existing.availability = "available"
        else:
            session.add(Account(
                id=account_id,
                unity_id=unity_id,
                name=name,
                firstname=firstname,
                email=f"{matricule.lower()}@test.edg.gn",
                phone=phone,
                role=role,
                account_status="active",
                availability="available",
                matricule=matricule,
                is_edg_employee=True,
            ))
        await session.commit()


async def _search_ids(role_dep, term: str, **extra) -> set[str]:
    qs = f"search={term}"
    for key, value in extra.items():
        qs += f"&{key}={value}"
    resp = await _call_as(role_dep, "GET", f"/api/v1/users/?{qs}")
    assert resp.status_code == 200, resp.text
    return {str(item["id"]) for item in resp.json()["data"]["items"]}


def _admin():
    return _dep(9999, "admin", None)


# ── 1-2. Prénom+Nom dans les deux ordres ───────────────────────────────────────

async def test_search_firstname_lastname_both_orders(unity_id):
    await _make_person(950, unity_id=unity_id, firstname="Fatoumata", name="Conté", matricule="EDG-00950")

    assert "950" in await _search_ids(_admin(), "Fatoumata Conté")
    assert "950" in await _search_ids(_admin(), "Conté Fatoumata")


# ── 3. Insensible à la casse ───────────────────────────────────────────────────

async def test_search_case_insensitive(unity_id):
    await _make_person(951, unity_id=unity_id, firstname="Fatoumata", name="Conte", matricule="EDG-00951")

    assert "951" in await _search_ids(_admin(), "fatoumata conte")
    assert "951" in await _search_ids(_admin(), "FATOUMATA CONTE")


# ── 4. Matricule (mono-mot, non-régression) ────────────────────────────────────

async def test_search_by_matricule(unity_id):
    await _make_person(952, unity_id=unity_id, firstname="Ibrahima", name="Bah", matricule="EDG-00952")

    assert "952" in await _search_ids(_admin(), "EDG-00952")


# ── 5. Téléphone tolérant au formatage ─────────────────────────────────────────

async def test_search_by_phone_tolerant_formatting(unity_id):
    await _make_person(
        953, unity_id=unity_id, firstname="Aissatou", name="Barry",
        matricule="EDG-00953", phone="+224621123456",
    )

    assert "953" in await _search_ids(_admin(), "621123456")
    assert "953" in await _search_ids(_admin(), "621 12 34 56")
    assert "953" in await _search_ids(_admin(), "00224621123456")


# ── 6-7-8. Homonymes : aucune sélection automatique, désambiguïsation ─────────

async def test_search_homonyms_returns_both_no_auto_selection(unity_id):
    await _ensure_test_unity(9601, parent_direction_id=None)
    await _make_person(960, unity_id=unity_id, firstname="Mamadou", name="Diallo", matricule="EDG-01872")
    await _make_person(961, unity_id=9601, firstname="Mamadou", name="Diallo", matricule="EDG-04391")

    ids = await _search_ids(_admin(), "Mamadou Diallo")
    assert {"960", "961"}.issubset(ids), "les deux homonymes doivent apparaître, sans tri privilégiant l'un"


async def test_search_homonym_disambiguated_by_matricule(unity_id):
    await _ensure_test_unity(9602, parent_direction_id=None)
    await _make_person(962, unity_id=unity_id, firstname="Mamadou", name="Diallo", matricule="EDG-01873")
    await _make_person(963, unity_id=9602, firstname="Mamadou", name="Diallo", matricule="EDG-04392")

    ids = await _search_ids(_admin(), "EDG-04392")
    assert ids == {"963"}, "la recherche par matricule doit lever toute ambiguïté entre homonymes"


# ── 9. Recherche mono-mot toujours fonctionnelle (non-régression) ─────────────

async def test_search_single_name_token_still_works(unity_id):
    await _make_person(964, unity_id=unity_id, firstname="Ousmane", name="Sylla", matricule="EDG-00964")

    assert "964" in await _search_ids(_admin(), "Ousmane")
    assert "964" in await _search_ids(_admin(), "Sylla")


# ── 10-11. Recherche combinée avec un filtre organigramme (unit_id) ───────────

async def test_search_combined_with_unit_filter_scopes_homonyms(unity_id):
    await _ensure_test_unity(9605, parent_direction_id=None)
    await _make_person(965, unity_id=unity_id, firstname="Mamadou", name="Diallo", matricule="EDG-11111")
    await _make_person(966, unity_id=9605, firstname="Mamadou", name="Diallo", matricule="EDG-22222")

    ids_scoped_to_9605 = await _search_ids(_admin(), "Mamadou Diallo", unit_id=9605)
    assert ids_scoped_to_9605 == {"966"}, "le filtre unit_id doit s'appliquer même quand une recherche texte est active"


async def test_search_combined_with_direction_filter(unity_id):
    """direction_id doit être résolu vers tous les services de cette direction
    (même mécanisme que list_by_direction), pas seulement une correspondance
    exacte sur unity_id — le service de test appartient directement à sa propre
    unity_id ici, donc filtrer par cette même unity_id en tant que "direction"
    doit au minimum inclure la personne qui y est directement rattachée."""
    await _make_person(967, unity_id=unity_id, firstname="Sekou", name="Kaba", matricule="EDG-00967")

    ids = await _search_ids(_admin(), "Sekou Kaba", direction_id=unity_id)
    assert "967" in ids
