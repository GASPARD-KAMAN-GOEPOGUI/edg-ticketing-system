# Memoire technique Codex

Ce dossier est la memoire technique locale de EDG Connect. Il sert a localiser vite une fonctionnalite, ses fichiers probables, ses regles metier, ses endpoints et ses tests, sans rescanner tout le depot a chaque intervention.

## Ordre de consultation

1. `FEATURE_INDEX.md` pour partir d'un probleme fonctionnel.
2. `MODULE_INDEX.md` pour retrouver le module metier.
3. `BUSINESS_RULES.md` pour verifier la regle applicable.
4. `KNOWN_ISSUES.md` pour voir si le symptome est deja connu.
5. Index specialise selon le cas: `FRONTEND_INDEX.md`, `BACKEND_INDEX.md`, `ROUTE_INDEX.md`, `API_INDEX.md`, `DATABASE_INDEX.md`, `ROLE_INDEX.md`, `WORKFLOW_INDEX.md`.

## Methode pour chaque nouvelle tache

Avant toute correction, identifier: probleme cible, module, fonctionnalite, role, regle metier, chemins courts, hypothese et perimetre exclu.

Ensuite:

1. consulter les index ci-dessus;
2. ouvrir seulement les fichiers listes et leurs dependances fonctionnelles immediates;
3. corriger localement;
4. tester la zone modifiee;
5. mettre a jour les index impactes et `CHANGELOG_CODEX.md`.

## Recherches autorisees

Une recherche elargie est autorisee seulement si les index sont insuffisants, obsoletes, ou si une reconstruction est explicitement demandee. Dans ce cas, limiter la recherche au sous-dossier concerne et documenter la raison.

## Dossiers exclus

Ne pas indexer par defaut: `node_modules/`, `.git/`, `.codex/`, `venv/`, `.venv/`, `__pycache__/`, `.pytest_cache/`, `dist/`, `build/`, `frontend/dist/`, `frontend/.vite/`, `logs/`, `tmp/`, fichiers `*.log`, `*.err`, `*.tmp`, `*.pyc`.

## Regle de mise a jour

Toute modification de route, endpoint, role, permission, workflow, table, modele, service, page ou action ticket doit mettre a jour le ou les index concernes.
