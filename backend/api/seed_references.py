"""
Seed des tables de référence dynamiques et des priorités.
Idempotent : utilise get_or_create, ne réécrit jamais un enregistrement existant.
Appelé une fois au démarrage de l'application (lifespan).
"""
from __future__ import annotations

import logging

from sqlalchemy.ext.asyncio import AsyncSession

from api.configs.Environment import get_environment

from api.repositories import (
    RequestStatusRepository,
    RequestCategoryRepository,
    PriorityDefinitionRepository,
    SlaPolicyRepository,
    UnityRepository,
    OrganigramRepository,
)

logger = logging.getLogger(__name__)

# ── Données builtin par table ─────────────────────────────────────────────────

_REQUEST_STATUSES = [
    # "pending", "qualified" et "escalated" retires du workflow le 2026-09-26 :
    # plus aucune transition ne les cible. Les bases existantes conservent leurs
    # lignes (archivables depuis l'ecran Referentiels, qui refuse l'archivage
    # tant qu'un ticket les porte) ; une installation neuve ne les cree plus.
    {"code": "new",          "label": "Nouvelle",              "sort_order": 0,  "is_builtin": True},
    {"code": "qualifying",   "label": "En qualification",      "sort_order": 2,  "is_builtin": True},
    {"code": "assigned",     "label": "Assignée",              "sort_order": 4,  "is_builtin": True},
    {"code": "in_progress",  "label": "En cours",              "sort_order": 5,  "is_builtin": True},
    {"code": "resolved",     "label": "Résolue",               "sort_order": 8,  "is_builtin": True},
    {"code": "closed",       "label": "Clôturée",              "sort_order": 9,  "is_builtin": True},
    {"code": "cancelled",    "label": "Annulée",               "sort_order": 10, "is_builtin": True},
    {"code": "reopened",     "label": "Réouverte",             "sort_order": 11, "is_builtin": True},
    {"code": "rejected",     "label": "Rejeté",                "sort_order": 12, "is_builtin": True},
]

_REQUEST_CATEGORIES = [
    # ── Catégories DSI (cahier des charges §5) ────────────────────────────────
    {"code": "incident",         "label": "Incident",               "sort_order": 1,  "is_builtin": True},
    {"code": "demande_service",  "label": "Demande de service",     "sort_order": 2,  "is_builtin": True},
    {"code": "maintenance_si",   "label": "Maintenance SI",         "sort_order": 3,  "is_builtin": True},
    {"code": "reseau",           "label": "Réseau",                 "sort_order": 4,  "is_builtin": True},
    {"code": "habilitation",     "label": "Habilitation / Accès",   "sort_order": 5,  "is_builtin": True},
    {"code": "securite",         "label": "Sécurité",               "sort_order": 6,  "is_builtin": True},
    {"code": "materiel",         "label": "Matériel",               "sort_order": 7,  "is_builtin": True},
    {"code": "logiciel",         "label": "Logiciel",               "sort_order": 8,  "is_builtin": True},
    # ── Catégories EDG générales ──────────────────────────────────────────────
    {"code": "branchement",           "label": "Branchement",              "sort_order": 10, "is_builtin": True},
    {"code": "panne",                 "label": "Panne / Interruption",     "sort_order": 11, "is_builtin": True},
    {"code": "facturation",           "label": "Facturation",              "sort_order": 12, "is_builtin": True},
    {"code": "compteur",              "label": "Compteur / Relevé",        "sort_order": 13, "is_builtin": True},
    {"code": "reclamation",           "label": "Réclamation",              "sort_order": 14, "is_builtin": True},
    {"code": "information",           "label": "Demande d'information",    "sort_order": 15, "is_builtin": True},
    {"code": "acces_applicatif",      "label": "Accès applicatif",         "sort_order": 16, "is_builtin": True},
    {"code": "incident_technique",    "label": "Incident technique",       "sort_order": 17, "is_builtin": True},
    {"code": "paie",                  "label": "Paie",                     "sort_order": 18, "is_builtin": True},
    {"code": "carrieres",             "label": "Carrières",                "sort_order": 19, "is_builtin": True},
    {"code": "budget",                "label": "Budget",                   "sort_order": 20, "is_builtin": True},
    {"code": "document_administratif","label": "Document administratif",   "sort_order": 21, "is_builtin": True},
    {"code": "formation",             "label": "Formation",                "sort_order": 22, "is_builtin": True},
    {"code": "equipement",            "label": "Équipement / Matériel",    "sort_order": 23, "is_builtin": True},
    {"code": "autre",                 "label": "Autre",                    "sort_order": 99, "is_builtin": True},
]






_PRIORITY_DEFINITIONS = [
    {"slug": "low",      "label": "Basse",    "description": "Demandes non urgentes, traitement dans les délais standards.", "color": "slate",  "sort_order": 1, "is_builtin": True, "status": True},
    {"slug": "medium",   "label": "Moyenne",  "description": "Demandes courantes nécessitant un suivi normal.",             "color": "blue",   "sort_order": 2, "is_builtin": True, "status": True},
    {"slug": "high",     "label": "Haute",    "description": "Demandes urgentes impactant plusieurs utilisateurs.",         "color": "orange", "sort_order": 3, "is_builtin": True, "status": True},
    {"slug": "critical", "label": "Critique", "description": "Incidents majeurs à traiter immédiatement.",                 "color": "red",    "sort_order": 4, "is_builtin": True, "status": True},
]

# Politiques SLA par défaut — mêmes délais pour toutes les catégories, variant
# uniquement par priorité. response_h = délai de première réponse, resolution_h =
# délai de résolution (alimente request.sla_hours), escalate_after_h = seuil
# d'escalade automatique (scheduler).
_SLA_HOURS_BY_PRIORITY: dict[str, dict[str, int]] = {
    "low":      {"response_h": 24, "resolution_h": 72, "escalate_after_h": 96},
    "medium":   {"response_h": 8,  "resolution_h": 48, "escalate_after_h": 60},
    "high":     {"response_h": 2,  "resolution_h": 24, "escalate_after_h": 30},
    "critical": {"response_h": 1,  "resolution_h": 4,  "escalate_after_h": 6},
}

# ── Structure organisationnelle EDG (Unity + Organigram) ─────────────────────
#
# Chaque unity a : codename (unique), label, aleas, description
# L'organigram lie unity_codename → parent_codename (None = racine)
#
# Niveau 0 (racines) : Directions EDG
# Niveau 1 : Départements DSI (enfants de DSI)
# Niveau 2 : Services (enfants des départements)

_UNITIES = [
    # ── Directions EDG (racines) ──────────────────────────────────────────────
    {"codename": "DG",    "label": "Direction Générale",                   "aleas": "DG",   "description": None},
    {"codename": "DC",    "label": "Direction Commerciale",                "aleas": "DC",   "description": None},
    {"codename": "DT",    "label": "Direction Technique",                  "aleas": "DT",   "description": None},
    {"codename": "DRH",   "label": "Direction des Ressources Humaines",    "aleas": "DRH",  "description": None},
    {"codename": "DF",    "label": "Direction Financière",                 "aleas": "DF",   "description": None},
    {"codename": "DSI",   "label": "Direction des Systèmes d'Information", "aleas": "DSI",  "description": None},
    {"codename": "DM",    "label": "Direction de la Maintenance",          "aleas": "DM",   "description": None},
    {"codename": "DI",    "label": "Direction des Infrastructures",        "aleas": "DI",   "description": None},
    {"codename": "DIAJ",  "label": "Direction des Affaires Juridiques",    "aleas": "DIAJ", "description": None},
    {"codename": "DQE",   "label": "Direction Qualité & Environnement",    "aleas": "DQE",  "description": None},
    # ── Secrétariat / Services d'appui DSI ───────────────────────────────────
    {"codename": "DSI-SEC",  "label": "Secrétariat DSI",     "aleas": "SEC",    "description": None},
    {"codename": "DSI-APP",  "label": "Service d'Appui DSI", "aleas": "APPUI",  "description": None},
    # ── Départements DSI (§3 CDC) ─────────────────────────────────────────────
    {"codename": "DSI-DED",  "label": "Département Étude et Développement",    "aleas": "ED",  "description": None},
    {"codename": "DSI-DEX",  "label": "Département Exploitation",              "aleas": "EXP", "description": None},
    {"codename": "DSI-DIR",  "label": "Département Infrastructure et Réseau",  "aleas": "INR", "description": None},
    # ── Services DSI (§3 CDC) ─────────────────────────────────────────────────
    {"codename": "DSI-SED",  "label": "Service Étude & Digitalisation",        "aleas": "SED",  "description": None},
    {"codename": "DSI-SMT",  "label": "Service Maintenance",                   "aleas": "SMNT", "description": None},
    {"codename": "DSI-SSP",  "label": "Service Support",                       "aleas": "SUP",  "description": None},
    {"codename": "DSI-SRC",  "label": "Service Réseau & Cybersécurité",        "aleas": "SRC",  "description": None},
    {"codename": "DSI-SSH",  "label": "Service Système & Habilitation",        "aleas": "SSH",  "description": None},
    # ── Services autres directions ────────────────────────────────────────────
    {"codename": "DC-SC",   "label": "Service Clientèle",                "aleas": "SC",  "description": None},
    {"codename": "DC-SF",   "label": "Service Facturation",              "aleas": "SF",  "description": None},
    {"codename": "DC-SR",   "label": "Service Recouvrement",             "aleas": "SR",  "description": None},
    {"codename": "DC-SCO",  "label": "Service Commercial",               "aleas": "SCO", "description": None},
    {"codename": "DT-SD",   "label": "Service Distribution",             "aleas": "SD",  "description": None},
    {"codename": "DT-ST",   "label": "Service Transport",                "aleas": "ST",  "description": None},
    {"codename": "DT-SP",   "label": "Service Production",               "aleas": "SP",  "description": None},
    {"codename": "DT-SM",   "label": "Service Métrologie",               "aleas": "SM",  "description": None},
    {"codename": "DRH-SF",  "label": "Service Formation",                "aleas": "SF",  "description": None},
    {"codename": "DRH-SAP", "label": "Service Administration du Personnel","aleas": "SAP","description": None},
    {"codename": "DRH-SRE", "label": "Service Recrutement",             "aleas": "SRE", "description": None},
    {"codename": "DF-SCO",  "label": "Service Comptabilité",             "aleas": "SCO", "description": None},
    {"codename": "DF-SBG",  "label": "Service Budget & Contrôle",        "aleas": "SBG", "description": None},
    {"codename": "DF-STR",  "label": "Service Trésorerie",               "aleas": "STR", "description": None},
    {"codename": "DM-SMR",  "label": "Service Maintenance Réseau",       "aleas": "SMR", "description": None},
    {"codename": "DM-SME",  "label": "Service Maintenance Équipements",  "aleas": "SME", "description": None},
    {"codename": "DM-SL",   "label": "Service Logistique",               "aleas": "SL",  "description": None},
    {"codename": "DI-SET",  "label": "Service Études & Travaux",         "aleas": "SET", "description": None},
    {"codename": "DI-SSU",  "label": "Service Supervision",              "aleas": "SSU", "description": None},
    {"codename": "DIAJ-SCT","label": "Service Contentieux",              "aleas": "SCT", "description": None},
    {"codename": "DIAJ-SCN","label": "Service Contrats",                 "aleas": "SCN", "description": None},
    {"codename": "DG-CAB",  "label": "Cabinet du Directeur Général",     "aleas": "CAB", "description": None},
    {"codename": "DG-COM",  "label": "Service Communication",            "aleas": "COM", "description": None},
]

# (codename_unity, codename_parent_organigram_unity | None)
_ORGANIGRAM_TREE = [
    # Directions → racines (parent=None)
    ("DG",   None), ("DC",   None), ("DT",   None), ("DRH",  None),
    ("DF",   None), ("DSI",  None), ("DM",   None), ("DI",   None),
    ("DIAJ", None), ("DQE",  None),
    # DSI — secrétariat / appui
    ("DSI-SEC",  "DSI"), ("DSI-APP",  "DSI"),
    # DSI — départements
    ("DSI-DED",  "DSI"), ("DSI-DEX",  "DSI"), ("DSI-DIR",  "DSI"),
    # DSI — services (enfants des départements)
    ("DSI-SED",  "DSI-DED"),
    ("DSI-SMT",  "DSI-DEX"), ("DSI-SSP",  "DSI-DEX"),
    ("DSI-SRC",  "DSI-DIR"), ("DSI-SSH",  "DSI-DIR"),
    # DC
    ("DC-SC", "DC"), ("DC-SF", "DC"), ("DC-SR", "DC"), ("DC-SCO", "DC"),
    # DT
    ("DT-SD", "DT"), ("DT-ST", "DT"), ("DT-SP", "DT"), ("DT-SM", "DT"),
    # DRH
    ("DRH-SF", "DRH"), ("DRH-SAP", "DRH"), ("DRH-SRE", "DRH"),
    # DF
    ("DF-SCO", "DF"), ("DF-SBG", "DF"), ("DF-STR", "DF"),
    # DM
    ("DM-SMR", "DM"), ("DM-SME", "DM"), ("DM-SL", "DM"),
    # DI
    ("DI-SET", "DI"), ("DI-SSU", "DI"),
    # DIAJ
    ("DIAJ-SCT", "DIAJ"), ("DIAJ-SCN", "DIAJ"),
    # DG
    ("DG-CAB", "DG"), ("DG-COM", "DG"),
]


# ── Seed runner ───────────────────────────────────────────────────────────────

async def seed_references(session: AsyncSession) -> None:
    """Seed idempotent de toutes les tables de référence."""
    seeded = 0

    async def _seed(repo, items: list[dict], key: str = "code") -> int:
        nonlocal seeded
        count = 0
        for item in items:
            # include_deleted=True : une référence archivée par l'admin occupe
            # toujours sa valeur dans l'index unique (code/slug). Sans ça le seed
            # tenterait un INSERT et planterait le démarrage en doublon (1062).
            # On ne la ressuscite pas — l'archivage reste une décision admin.
            _, created = await repo.get_or_create(
                filters={key: item[key]},
                defaults=item,
                include_deleted=True,
            )
            if created:
                count += 1
        seeded += count
        return count

    await _seed(RequestStatusRepository(session),       _REQUEST_STATUSES)
    await _seed(RequestCategoryRepository(session),     _REQUEST_CATEGORIES)
    await _seed(PriorityDefinitionRepository(session),  _PRIORITY_DEFINITIONS, key="slug")

    # ── Politiques SLA (catégorie × priorité) ────────────────────────────────
    sla_repo = SlaPolicyRepository(session)
    for cat in _REQUEST_CATEGORIES:
        for prio_slug, hours in _SLA_HOURS_BY_PRIORITY.items():
            # Même raison que dans _seed : uk_sla_cat_prio ignore deleted_at.
            _, created = await sla_repo.get_or_create(
                filters={"category": cat["code"], "priority": prio_slug},
                defaults={"category": cat["code"], "priority": prio_slug, **hours},
                include_deleted=True,
            )
            if created:
                seeded += 1

    # ── Unity + Organigram (dépendance : organigram.unity_id = unity.id) ────
    # SEED_ORG_STRUCTURE=False : la structure organisationnelle est laissée
    # entièrement à la main de l'admin (créations depuis le back-office). On
    # sort avant d'y toucher — les références au-dessus (statuts, priorités,
    # catégories, SLA) restent semées, ce sont des enums techniques dont les
    # clés étrangères conditionnent le fonctionnement de l'application.
    if not get_environment().SEED_ORG_STRUCTURE:
        logger.info(
            "seed_references: structure organisationnelle ignorée "
            "(SEED_ORG_STRUCTURE=False) — unity/organigram laissés à l'admin."
        )
        if seeded:
            logger.info("seed_references: %d enregistrements insérés", seeded)
        return

    unity_repo = UnityRepository(session)
    org_repo   = OrganigramRepository(session)

    codename_to_unity_id: dict[str, int] = {}
    for u in _UNITIES:
        # Respecter les suppressions admin : une unity soft-deleted ne doit jamais
        # être restaurée automatiquement au démarrage.
        existing = await unity_repo.get_one({"codename": u["codename"]}, include_deleted=True)
        if existing is not None:
            if existing.deleted_at is None:
                codename_to_unity_id[u["codename"]] = existing.id
            else:
                logger.debug(
                    "seed_references: unity %s ignoree car soft-deleted",
                    u["codename"],
                )
            continue
        else:
            obj = (await unity_repo.get_or_create(
                filters={"codename": u["codename"]},
                defaults={**u, "status": True},
            ))[0]
            codename_to_unity_id[u["codename"]] = obj.id
            seeded += 1

    codename_to_org_id: dict[str, int] = {}
    for (unity_codename, parent_codename) in _ORGANIGRAM_TREE:
        unity_id = codename_to_unity_id.get(unity_codename)
        if unity_id is None:
            logger.warning("seed_references: unity_codename=%s introuvable", unity_codename)
            continue

        parent_org_id = codename_to_org_id.get(parent_codename) if parent_codename else None
        if parent_codename and parent_org_id is None:
            logger.debug(
                "seed_references: organigram %s ignore car parent %s absent ou supprime",
                unity_codename,
                parent_codename,
            )
            continue

        existing_org = await org_repo.get_one({"unity_id": unity_id}, include_deleted=True)
        if existing_org is not None:
            if existing_org.deleted_at is None:
                codename_to_org_id[unity_codename] = existing_org.id
            else:
                logger.debug(
                    "seed_references: organigram %s ignore car soft-deleted",
                    unity_codename,
                )
            continue
        else:
            obj = (await org_repo.get_or_create(
                filters={"unity_id": unity_id},
                defaults={
                    "unity_id": unity_id,
                    "parent_id": parent_org_id,
                    "status": True,
                },
            ))[0]
            codename_to_org_id[unity_codename] = obj.id
            seeded += 1

    if seeded:
        logger.info("seed_references: %d enregistrements insérés", seeded)
    else:
        logger.debug("seed_references: rien à insérer (déjà présent)")
