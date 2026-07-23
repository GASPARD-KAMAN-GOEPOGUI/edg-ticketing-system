# AGENTS.md - EDG Connect

Ce fichier est la référence officielle de comportement pour toute intervention Codex sur EDG Connect. Il doit être consulté avant `docs/codex/`, puis utilisé avec la mémoire technique locale du projet.

## 1. Identité Du Projet

EDG Connect / EDG-SUP est une application de gestion des demandes et tickets EDG.

Objectif principal :

- permettre la création et le suivi des demandes ;
- qualifier, orienter et traiter les tickets ;
- gérer les assignations, escalades, réouvertures et clôtures ;
- fournir des vues par rôle : personnel, traitement, supervision, direction, DG, administration ;
- produire des rapports, statistiques, notifications et bases de connaissances.

Architecture générale :

- frontend : React 19, TanStack Router/Start, TanStack Query, TypeScript, Vite, Tailwind CSS, Radix UI, lucide-react ;
- backend : FastAPI, SQLAlchemy async, Pydantic v1, Uvicorn/Gunicorn ;
- données : base relationnelle via SQLAlchemy ;
- temps réel : SSE ;
- exports : CSV, Excel, PDF ;
- documentation technique : `docs/codex/`.

Grands modules fonctionnels :

- authentification ;
- espace personnel ;
- demandes/tickets ;
- traitement agent ;
- chef de service ;
- supervision ;
- vue direction ;
- vue DG ;
- administration ;
- workflow/timeline/commentaires ;
- rapports ;
- notifications ;
- base de connaissances ;
- organisation ;
- SLA/escalades ;
- audit/sécurité.

Rôles métier :

- `public` : visiteur, suivi public, base de connaissances publique ;
- `user` : demandeur/employé, ses propres demandes ;
- `agent` : traitement quotidien des tickets ;
- `chief` : responsable de service ;
- `director` : pilotage, arbitrage, transfert et validation direction ;
- `dg` : pilotage global ;
- `admin` : administration système.

## 2. Philosophie De Travail

Principes obligatoires :

- préserver l'architecture existante ;
- privilégier les corrections locales ;
- éviter les modifications transversales ;
- ne jamais casser un autre module pour corriger un problème isolé ;
- respecter les règles métier documentées ;
- garder les conventions existantes ;
- réduire la surface modifiée ;
- réutiliser les structures existantes avant toute création.

Une correction réussie doit être ciblée, compréhensible, testée localement et documentée.

## 3. Source De Vérité

Ordre de priorité obligatoire :

1. `AGENTS.md`
2. `docs/codex/`
3. architecture existante
4. code source concerné
5. nouvelle implémentation seulement si aucune structure existante ne répond au besoin

Le code source ne doit jamais être considéré comme la seule source de vérité. Les règles métier, routes attendues, périmètres par rôle et workflows doivent être confirmés dans `docs/codex/` avant modification.

## 4. Utilisation Obligatoire De docs/codex

Avant toute correction, consulter la documentation pertinente dans `docs/codex/`.

Ne jamais repartir de zéro si la documentation permet déjà d'identifier :

- le module ;
- la fonctionnalité ;
- les fichiers concernés ;
- les routes ;
- les endpoints ;
- les rôles ;
- les règles métier ;
- les dépendances directes ;
- les tests ciblés.

La documentation `docs/codex/` est une mémoire vivante. Elle doit être synchronisée après chaque changement significatif.

## 5. Localisation Des Problèmes

Pour chaque demande utilisateur, identifier d'abord :

- la fonctionnalité ;
- le module ;
- le rôle concerné ;
- la page ou l'action ;
- le résultat actuel ;
- le résultat attendu ;
- la règle métier concernée ;
- les chemins probables.

Ensuite ouvrir uniquement les fichiers nécessaires et leurs dépendances fonctionnelles immédiates.

## 6. Recherche Progressive

Ordre de recherche obligatoire :

1. `docs/codex/FEATURE_INDEX.md`
2. `docs/codex/MODULE_INDEX.md`
3. `docs/codex/BUSINESS_RULES.md`
4. `docs/codex/DEPENDENCY_INDEX.md`
5. index spécialisé concerné
6. code source ciblé

Interdiction par défaut :

- scan global automatique ;
- exploration complète du dépôt ;
- lecture massive de fichiers non liés ;
- analyse de dépendances externes, caches, builds ou logs.

Élargir la recherche seulement si les chemins ciblés ne suffisent pas. Dans ce cas, expliquer le sous-dossier à examiner et pourquoi.

## 7. Architecture

Ne jamais créer sans vérification préalable :

- nouvelle route ;
- nouvelle page ;
- nouveau composant ;
- nouveau service ;
- nouveau workflow ;
- nouvelle logique métier ;
- nouveau modèle ;
- nouvel endpoint ;
- nouvelle règle de navigation.

Toujours vérifier dans cet ordre :

1. `docs/codex/`
2. fichiers directement liés ;
3. architecture existante ;
4. besoin réel d'une nouvelle structure.

Si une solution existe déjà, la réutiliser. Si aucune solution n'existe, expliquer pourquoi une nouvelle structure est nécessaire avant de l'implémenter.

## 8. Navigation

Respecter strictement les espaces fonctionnels :

- espace personnel : `Mes demandes`, `Historique`, `Profil`, `Notifications` personnelles ;
- espace métier : tickets traités par un agent ou un chef ;
- espace supervision : tickets supervisés ;
- espace direction : pilotage d'une direction ;
- espace DG : vue globale ;
- espace administration : backoffice.

Règle clé :

- un ticket ouvert depuis `Mes demandes` reste dans `/app/requests/$id` ;
- un ticket ouvert depuis un module métier reste dans sa route métier ;
- un ticket ouvert depuis administration reste dans `/app/admin/tickets/$id` ;
- les liens doivent conserver le contexte d'origine.

Source centrale :

- utiliser `frontend/src/lib/ticket-navigation.ts` pour la navigation détail ticket ;
- ne pas dupliquer le mapping des rôles ou routes dans plusieurs fichiers.

## 9. Respect Des Règles Métier

Toute correction doit respecter les règles documentées dans `docs/codex/BUSINESS_RULES.md`.

Si une règle métier est absente :

1. signaler l'absence ;
2. proposer l'ajout ;
3. mettre à jour `BUSINESS_RULES.md` si la correction l'introduit.

Règles particulièrement sensibles :

- séparation espace personnel / espace métier ;
- conflit d'intérêt sur sa propre demande ;
- périmètre agent/chef/directeur ;
- transfert inter-direction ;
- résolution directeur limitée aux tickets escaladés/arbitrés ;
- cycle de réouverture ;
- timeline/commentaires visibles jusqu'à clôture.

## 10. Dépendances

Avant de modifier une fonctionnalité, vérifier uniquement ses dépendances directes :

- page ou composant frontend ;
- service API frontend ;
- endpoint backend ;
- route backend ;
- service backend ;
- modèle ou table impliquée ;
- permissions ou règles métier ;
- test ciblé existant.

Ne pas inspecter les dépendances techniques sans utilité pour localiser le problème.

## 11. Corrections

Toujours :

- modifier le minimum de fichiers ;
- conserver les conventions existantes ;
- éviter les duplications ;
- éviter le code mort ;
- éviter les refontes non demandées ;
- préserver les signatures publiques si possible ;
- garder les changements lisibles et localisés.

Ne pas :

- renommer un fichier sans nécessité ;
- déplacer un module sans demande explicite ;
- modifier une règle métier voisine ;
- changer un workflow non concerné ;
- réécrire un composant entier pour une correction locale.

## 12. Vérifications

Exécuter seulement les vérifications ciblées liées à la modification :

- test de service ;
- test d'endpoint ;
- test de règle métier ;
- vérification TypeScript ciblée ;
- import ciblé ;
- compilation ciblée ;
- test visuel ciblé si la navigation ou l'UI est concernée.

Ne jamais lancer automatiquement :

- audit global ;
- tous les tests ;
- tous les builds ;
- scan complet du dépôt.

Si une vérification ne peut pas être exécutée, le dire clairement.

## 13. Documentation

Après chaque modification importante, mettre à jour les documents concernés dans `docs/codex/`.

Mettre à jour au minimum :

- `CHANGELOG_CODEX.md` pour toute intervention ;
- `BUSINESS_RULES.md` si une règle change ou est ajoutée ;
- `ROUTE_INDEX.md` si une route/navigation change ;
- `API_INDEX.md` si un endpoint change ;
- `ROLE_INDEX.md` si un rôle ou une permission change ;
- `WORKFLOW_INDEX.md` si un workflow change ;
- `FEATURE_INDEX.md` ou `MODULE_INDEX.md` si une fonctionnalité évolue ;
- `FILE_INDEX.md` si un fichier clé est ajouté, déplacé ou renommé.

La documentation et le code doivent rester synchronisés.

## 14. Consommation De Contexte

Optimiser systématiquement le contexte et les tokens :

- limiter le nombre de fichiers ouverts ;
- limiter les recherches ;
- éviter les scans globaux ;
- éviter les réponses inutilement longues ;
- éviter de relire des fichiers déjà connus ;
- citer seulement les extraits utiles ;
- résumer les résultats au lieu de recopier les fichiers.

## 15. Dossiers À Ignorer

Ignorer systématiquement :

- `node_modules/`
- `dist/`
- `build/`
- `coverage/`
- `logs/`
- `tmp/`
- `temp/`
- `.cache/`
- `.git/`
- `.venv/`
- `venv/`
- `env/`
- `__pycache__/`
- `.pytest_cache/`
- `.mypy_cache/`
- `.ruff_cache/`
- `.codex/`
- profils navigateur temporaires

Ignorer aussi :

- `*.log`
- `*.tmp`
- `*.err`
- `*.cache`
- `*.pyc`

Les fichiers temporaires Codex doivent rester dans `.codex/`, jamais à la racine.

## 16. Format De Travail

Avant toute modification, indiquer brièvement :

```text
Module concerné :
Fonctionnalité :
Fichiers ciblés :
Hypothèse :
Périmètre exclu :
```

Après toute modification, indiquer :

```text
Fichiers modifiés :
Cause :
Correction :
Vérifications réalisées :
Documents mis à jour :
Modules non touchés :
```

Le compte rendu doit rester court et directement utile.

## 17. Gestion Des Index

Les documents de `docs/codex/` sont une mémoire vivante.

Lorsqu'un fichier est déplacé, renommé ou lorsqu'une fonctionnalité change :

- mettre à jour l'index concerné immédiatement ;
- corriger les chemins obsolètes ;
- ajouter la règle métier si elle manquait ;
- tracer l'intervention dans `CHANGELOG_CODEX.md`.

Ne jamais laisser le code et les index se contredire volontairement.

## 18. Reconstruction

Ne reconstruire la cartographie complète du projet que si :

- l'utilisateur le demande explicitement ;
- la documentation est devenue incohérente ;
- un incident transversal ne peut pas être isolé malgré les index ;
- une refonte globale est explicitement demandée.

Sinon, utiliser uniquement les index existants et les fichiers directement liés.

## 19. Règle Absolue

Le comportement attendu est toujours :

```text
Comprendre le problème
-> Identifier le module
-> Consulter docs/codex
-> Identifier les fichiers
-> Lire uniquement les fichiers utiles
-> Corriger localement
-> Tester localement
-> Mettre à jour docs/codex
-> Terminer
```

Cette règle s'applique à toutes les futures interventions sur EDG Connect.

## Rappel Final

L'architecture existante est la référence. Ne jamais inventer une solution parallèle lorsqu'une structure existe déjà. Réutiliser, corriger localement, tester ciblé, documenter.
