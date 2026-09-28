"""Figeage des identités organisationnelles sur un ticket (traçabilité).

Deux dimensions sont figées au moment des faits, et ne doivent JAMAIS être
recalculées ensuite :

  - le DEMANDEUR (direction / département / service / fonction / matricule),
    figé à la création de la demande ;
  - l'organisation TRAITANTE (direction / département / service), figée à la
    qualification.

Sans ce figeage, une mutation de compte ou une réorganisation de l'organigramme
réécrit rétroactivement l'historique : un incident traité en janvier afficherait
le service que la personne occupe en décembre. Ces tests mutent volontairement
les comptes et l'organigramme APRÈS coup, puis vérifient que le ticket n'a pas
bougé.

Pendant intervenant de ces règles : `test_trace_interventions.py` (BR-TRACE-001).
"""
from __future__ import annotations

from types import SimpleNamespace

from sqlalchemy import select

from tests.conftest import _TestSession

_REQUESTER = 9600
_QUALIFIER = 9601

_PAYLOAD = {
    "description": "Description de test pour le figeage des identités organisationnelles.",
    "category": "panne",
    "priority": "medium",
    "is_external": False,
    # Posé explicitement : on appelle le service directement, sans passer par la
    # route qui fixe habituellement le statut initial.
    "request_status": "new",
    "requester_name": "Demandeur Test",
    "requester_email": "demandeur.freeze@test.edg.gn",
}


async def _unity(codename: str, label: str) -> int:
    from api.models.ModelUnity import Unity

    async with _TestSession() as session:
        existing = (
            await session.execute(select(Unity).where(Unity.codename == codename))
        ).scalar_one_or_none()
        if existing is not None:
            existing.label = label
            await session.commit()
            return int(existing.id)
        unity = Unity(codename=codename, label=label, aleas=codename, status=True)
        session.add(unity)
        await session.commit()
        await session.refresh(unity)
        return int(unity.id)


async def _account(account_id: int, *, unity_id: int, role: str, job: str, matricule: str) -> None:
    from api.models.ModelAccount import Account

    async with _TestSession() as session:
        existing = await session.get(Account, account_id)
        if existing is None:
            existing = Account(
                id=account_id,
                name=f"Compte Freeze {account_id}",
                firstname="Test",
                email=f"freeze.{account_id}@test.edg.gn",
                account_status="active",
                is_edg_employee=True,
            )
            session.add(existing)
        existing.unity_id = unity_id
        existing.role = role
        existing.job = job
        existing.matricule = matricule
        existing.account_status = "active"
        await session.commit()


async def _mutate_account(account_id: int, **fields) -> None:
    """Simule une évolution de carrière : mutation de service, changement de
    fonction… postérieure aux tickets déjà enregistrés."""
    from api.models.ModelAccount import Account

    async with _TestSession() as session:
        account = await session.get(Account, account_id)
        for key, value in fields.items():
            setattr(account, key, value)
        await session.commit()


async def _rename_unity(unity_id: int, label: str) -> None:
    """Simule une réorganisation : le service est renommé après coup."""
    from api.models.ModelUnity import Unity

    async with _TestSession() as session:
        unity = await session.get(Unity, unity_id)
        unity.label = label
        await session.commit()


async def _create_ticket(unity_id: int | None, title: str, *, in_triage: bool = False) -> str:
    """`in_triage=True` + `unity_id=None` reproduit l'état réel d'un ticket en
    file d'attente : créé par un utilisateur, pas encore routé vers un service.
    C'est dans cet état que le chef de service le qualifie."""
    from api.services.ServiceRequest import RequestService

    async with _TestSession() as session:
        obj = await RequestService(session).create({
            **_PAYLOAD,
            "title": title,
            "unity_id": unity_id,
            "in_triage": in_triage,
            "requester_id": _REQUESTER,
        })
        return str(obj.id)


async def _qualify(request_id: str, qualifier_unity_id: int) -> None:
    from api.services.ServiceRequest import RequestService

    actor = SimpleNamespace(
        id=_QUALIFIER, role="chief-service", unity_id=qualifier_unity_id,
        direction_id=None, name="Qualifiant", firstname="Test",
    )
    async with _TestSession() as session:
        await RequestService(session).qualify_triage(
            request_id,
            {"category": "panne", "priority": "medium"},
            actor_id=str(_QUALIFIER),
            actor_name="Test Qualifiant",
            actor_role="chief-service",
            actor=actor,
        )
        await session.commit()


async def _reload(request_id: str):
    from api.models.ModelRequest import Request

    async with _TestSession() as session:
        return await session.get(Request, int(request_id))


# ── Demandeur ────────────────────────────────────────────────────────────────

async def test_identite_du_demandeur_figee_a_la_creation():
    """Le service, la fonction et le matricule du demandeur sont gelés."""
    unity_id = await _unity("TST-FREEZE-DEM", "Service Demandeur Origine")
    await _account(_REQUESTER, unity_id=unity_id, role="user",
                   job="Technicienne", matricule="MAT-ORIGINE")

    request_id = await _create_ticket(unity_id, "Figeage demandeur")

    obj = await _reload(request_id)
    assert obj.requester_unit_id == unity_id
    assert obj.requester_job == "Technicienne"
    assert obj.employee_matricule == "MAT-ORIGINE"
    assert obj.requester_service_label == "Service Demandeur Origine"


async def test_mutation_du_demandeur_ne_reecrit_pas_ses_anciens_tickets():
    """Le coeur de la règle : muter le compte APRÈS coup ne doit rien changer."""
    origine_id = await _unity("TST-FREEZE-DEM2", "Service Origine")
    ailleurs_id = await _unity("TST-FREEZE-DEM3", "Service Ailleurs")
    await _account(_REQUESTER, unity_id=origine_id, role="user",
                   job="Technicienne", matricule="MAT-AVANT")

    request_id = await _create_ticket(origine_id, "Figeage demandeur mutation")

    # La personne change de service, de fonction et de matricule.
    await _mutate_account(_REQUESTER, unity_id=ailleurs_id,
                          job="Directrice", matricule="MAT-APRES")

    obj = await _reload(request_id)
    assert obj.requester_unit_id == origine_id, "le service du demandeur a suivi la mutation"
    assert obj.requester_job == "Technicienne", "la fonction du demandeur a suivi la mutation"
    assert obj.employee_matricule == "MAT-AVANT", "le matricule a suivi la mutation"
    assert obj.requester_service_label == "Service Origine"


async def test_renommage_du_service_ne_reecrit_pas_le_libelle_demandeur():
    """Une réorganisation qui renomme un service ne doit pas toucher l'historique."""
    unity_id = await _unity("TST-FREEZE-DEM4", "Libellé Avant")
    await _account(_REQUESTER, unity_id=unity_id, role="user",
                   job="Agent", matricule="MAT-REN")

    request_id = await _create_ticket(unity_id, "Figeage libelle demandeur")
    await _rename_unity(unity_id, "Libellé Après Réorganisation")

    obj = await _reload(request_id)
    assert obj.requester_service_label == "Libellé Avant"


# ── Organisation traitante ───────────────────────────────────────────────────

async def test_organisation_traitante_figee_a_la_qualification():
    """Le service traitant vient du qualifiant, et ses libellés sont gelés."""
    demandeur_unity = await _unity("TST-FREEZE-TR1", "Service Demandeur")
    traitant_unity = await _unity("TST-FREEZE-TR2", "Service Traitant Origine")
    await _account(_REQUESTER, unity_id=demandeur_unity, role="user",
                   job="Agent", matricule="MAT-TR")
    await _account(_QUALIFIER, unity_id=traitant_unity, role="chief-service",
                   job="Chef de service", matricule="MAT-CSSHF")

    request_id = await _create_ticket(None, "Figeage traitant", in_triage=True)
    await _qualify(request_id, traitant_unity)

    obj = await _reload(request_id)
    # L'organisation traitante est celle du qualifiant, pas celle du demandeur.
    assert obj.unity_id == traitant_unity
    assert obj.handler_service_label == "Service Traitant Origine"
    # Le demandeur, lui, n'a pas bougé.
    assert obj.requester_unit_id == demandeur_unity


async def test_renommage_du_service_traitant_ne_reecrit_pas_le_ticket():
    demandeur_unity = await _unity("TST-FREEZE-TR3", "Service Demandeur 2")
    traitant_unity = await _unity("TST-FREEZE-TR4", "Traitant Avant")
    await _account(_REQUESTER, unity_id=demandeur_unity, role="user",
                   job="Agent", matricule="MAT-TR2")
    await _account(_QUALIFIER, unity_id=traitant_unity, role="chief-service",
                   job="Chef de service", matricule="MAT-CSSHF2")

    request_id = await _create_ticket(None, "Figeage traitant renomme", in_triage=True)
    await _qualify(request_id, traitant_unity)
    await _rename_unity(traitant_unity, "Traitant Après Réorganisation")

    obj = await _reload(request_id)
    assert obj.handler_service_label == "Traitant Avant"
    assert obj.direction_id is not None, "la direction traitante doit rester résolue"


# ── Non-régression sur les tickets antérieurs au figeage ─────────────────────

async def test_ticket_sans_figeage_retombe_sur_le_compte():
    """Les tickets créés avant cette règle n'ont rien dans `infos` : les
    lectures doivent continuer de fonctionner en retombant sur le compte."""
    from api.models.ModelRequest import Request

    unity_id = await _unity("TST-FREEZE-LEG", "Service Legacy")
    await _account(_REQUESTER, unity_id=unity_id, role="user",
                   job="Fonction Actuelle", matricule="MAT-LEGACY")

    request_id = await _create_ticket(unity_id, "Ticket legacy")

    # On efface le figeage pour simuler un ticket antérieur.
    async with _TestSession() as session:
        obj = await session.get(Request, int(request_id))
        obj.infos = None
        await session.commit()

    obj = await _reload(request_id)
    assert obj.requester_unit_id == unity_id
    assert obj.requester_job == "Fonction Actuelle"
    assert obj.employee_matricule == "MAT-LEGACY"
    # Aucun libellé figé disponible : le frontend les résout depuis les ids.
    assert obj.requester_service_label is None
