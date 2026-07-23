# Changelog Codex

## 2026-07-23 - Alignement CDC des roles metier

Demande: aligner strictement l'application sur les six acteurs du cahier des charges et supprimer la distinction metier Directeur / Directeur General.

Module: roles, permissions, navigation, workflow, reporting.

Fichiers modifies:

- backend RBAC, dependances, routes et services directement lies aux roles;
- frontend session, permissions, navigation, vues direction/supervision/globale et communication;
- index `docs/codex/` roles, regles metier, routes, modules, fonctionnalites et API.

Correction: `dg` n'est plus un role metier attribuable ni un niveau de permission global. Les anciennes valeurs `dg` sont normalisees vers `director` pour compatibilite, tandis que la vue globale et les donnees globales restent reservees a `admin`.

Verification: recherches ciblees des anciens guards/permissions `dg`, compilation backend ciblee et build frontend.

## 2026-07-23 - Remplacement du cahier des charges

Demande: remplacer integralement `docs/cahier-des-charges.md` par le contenu fourni du cahier des charges DSI EDG.

Module: documentation projet.

Fichiers modifies:

- `docs/cahier-des-charges.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: le cahier des charges principal contient maintenant le document DSI EDG sur l'application de Ticketing / Support Informatique, structure en sections Markdown propres.

Verification: lecture ciblee du fichier remplace.

## 2026-07-23 - Clic profil vers drawer organigramme

Demande: dans l'organigramme d'une direction, le clic sur chaque profil reel doit faire apparaitre le drawer de detail employe.

Module: MOD-ADMIN / MOD-ORG.

Fichiers modifies:

- `frontend/src/components/admin/direction-org-chart.tsx`
- `frontend/src/routes/app.admin.directions.$id.tsx`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: toutes les cartes de personnes reelles dans l'organigramme et les profils subordonnes du drawer sont des boutons explicites, avec ouverture robuste du drawer et protection contre les clics parasites de l'arbre. Les emplacements vides restent non cliquables car ils ne representent aucun employe reel.

Verification: lint cible des fichiers frontend concernes.

## 2026-07-23 - Affichage du detail direction depuis l'oeil

Demande: au clic sur l'icone `oeil` dans la liste des directions, afficher le detail organigramme au lieu de rester sur la liste.

Module: MOD-ADMIN / MOD-ORG.

Fichiers modifies:

- `frontend/src/routes/app.admin.directions.tsx`
- `docs/codex/ROUTE_INDEX.md`
- `docs/codex/FILE_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: la route `/app/admin/directions/$id` existait dans `routeTree.gen.ts`, mais elle etait imbriquee sous `/app/admin/directions`; la page parent ne rendait pas d'`Outlet`, donc TanStack gardait la liste visible meme sur `/app/admin/directions/1`.

Correction: la page parent detecte les sous-routes et rend l'`Outlet` pour laisser le detail direction afficher l'organigramme dedie.

Verification: lint cible des routes/composant organisation et build frontend.

## 2026-07-23 - Representation minimale du detail direction

Demande: au clic sur `Voir` une direction, afficher au moins un format de representation meme lorsque la direction n'a pas encore d'enfants actifs.

Module: MOD-ADMIN / MOD-ORG.

Fichiers modifies:

- `frontend/src/routes/app.admin.directions.$id.tsx`
- `frontend/src/components/admin/direction-org-chart.tsx`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/FILE_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: la page detail direction utilise maintenant le composant dedie `DirectionOrgChart`. Il affiche toujours une pyramide metier multi-branches `Directeur -> Chefs de departement -> Chefs de service -> Membres` avec des emplacements clairement non renseignes quand aucun personnel n'est affecte. Les branches reelles incompletes gardent aussi une suite visuelle jusqu'aux membres. Aucune donnee fictive ni fausse photo n'est creee; les donnees reelles restent utilisees des qu'elles existent et les personnes reelles ouvrent le drawer detail employe.

Verification: lint cible du fichier route et build frontend.

## 2026-07-23 - Organigramme pyramidal interactif d'une direction

Demande: lorsqu'un administrateur clique sur `Voir/Consulter` une direction, afficher une page premium de consultation avec organigramme pyramidal et fiches employes cliquables.

Module: MOD-ADMIN / MOD-ORG.

Fichiers modifies:

- `frontend/src/routes/app.admin.directions.$id.tsx`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/FILE_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: la route existante `/app/admin/directions/$id` est conservee et affiche maintenant un organigramme pyramidal interactif base sur les vraies directions, departements, services/unites et comptes. Les cartes personnes/avatars ouvrent un drawer detail employe; la page conserve la charte EDG-SUP et ajoute recherche, zoom et mode focus.

Verification: lint cible de `app.admin.directions.$id.tsx` et build frontend Vite/TanStack.

## 2026-07-23 - Attribution des roles utilisateurs selon hierarchie organisationnelle

Demande: adapter le formulaire admin d'attribution/modification de role pour afficher les champs organisationnels selon le role et valider l'affectation cote backend.

Module: MOD-ADMIN / MOD-ORG / users.

Fichiers modifies:

- `frontend/src/routes/app.admin.users.tsx`
- `frontend/src/lib/api/accounts.ts`
- `backend/api/schemas/SchemaAccount.py`
- `backend/api/routes/RouteUsers.py`
- `backend/api/services/ServiceAccount.py`
- `backend/tests/api/test_user_org_assignment.py`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/API_INDEX.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/DEPENDENCY_INDEX.md`
- `docs/codex/FILE_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: le formulaire admin distingue `Chef de departement` et `Chef de service` sans creer de role base supplementaire; les deux restent portes par le role backend `chief` avec un `unity_id` pointant vers le niveau choisi. Les champs direction/departement/service sont filtres sur les entites actives, les valeurs masquees sont videes et le backend valide le niveau organisationnel avant persistence.

Verification: compilation ciblee backend, test cible `test_user_org_assignment.py`, lint cible frontend et build Vite/TanStack.

## 2026-07-23 - Structure organisationnelle Direction / Departement / Service

Demande: ajouter le menu `Departements`, completer la hierarchie organisationnelle `Direction -> Departement -> Unite/Service`, garder la meme table et ajouter une consultation premium d'une direction.

Module: MOD-ADMIN / MOD-ORG.

Fichiers modifies:

- `backend/api/routes/RouteDirectionsUnits.py`
- `backend/api/routes/__init__.py`
- `backend/api/main.py`
- `backend/tests/api/test_directions_units_hierarchy.py`
- `frontend/src/lib/api/directions-units.ts`
- `frontend/src/components/app-layout.tsx`
- `frontend/src/routes/app.admin.directions.tsx`
- `frontend/src/routes/app.admin.directions.$id.tsx`
- `frontend/src/routes/app.admin.departments.tsx`
- `frontend/src/routes/app.admin.units.tsx`
- `frontend/src/routes/app.admin.org.tsx`
- `frontend/src/routeTree.gen.ts`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/API_INDEX.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/MODULE_INDEX.md`
- `docs/codex/DEPENDENCY_INDEX.md`
- `docs/codex/ROUTE_INDEX.md`
- `docs/codex/FILE_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: les directions, departements et services/unites restent dans `unity` et sont positionnes par `organigram.parent_id`. Les nouveaux elements portent `unity.infos.org_type` pour stabiliser leur type sans migration. Les actions de suppression admin deviennent des desactivations visibles et reversibles; une confirmation forcee desactive aussi les descendants actifs pour conserver une hierarchie coherente.

Verification: compilation ciblee backend, test cible `test_directions_units_hierarchy.py`, build frontend Vite/TanStack pour generer et verifier les nouvelles routes.

## 2026-07-23 - Seed organisation respecte les suppressions admin

Demande: identifier pourquoi les directions et services supprimes dans l'administration reapparaissent apres relance, puis corriger uniquement la cause.

Module: MOD-ADMIN / MOD-ORG.

Fichiers modifies:

- `backend/api/seed_references.py`
- `backend/tests/api/test_seed_references_org.py`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/API_INDEX.md`
- `docs/codex/DEPENDENCY_INDEX.md`
- `docs/codex/FILE_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: `seed_references.py`, execute a chaque demarrage par `main.py`, restaurait explicitement les `Unity` et `Organigram` soft-deleted en remettant `deleted_at = None`.

Correction: le seed cree toujours les donnees builtin absentes sur base neuve, mais ignore les `Unity` et `Organigram` soft-deleted et ne restaure plus automatiquement les directions/services supprimes. Les enfants dont le parent seed est absent ou supprime ne sont pas recrees/reparents par le seed.

Verification: compilation ciblee de `seed_references.py` et test cible `test_seed_references_org.py`.

## 2026-07-20 - Formulaire demandeur sans champs internes

Demande: retirer du formulaire de creation demandeur les champs `Categorie`, `Priorite`, `Direction destinataire` et `Service`.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:

- `frontend/src/components/new-request-form.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: le formulaire personnel affiche uniquement le titre, la description et les pieces jointes optionnelles. Le frontend conserve des valeurs techniques non visibles (`autre`, `medium`) pour satisfaire le contrat actuel de creation, sans envoyer direction ni service; la qualification reste dans les espaces metier autorises.

Verification: recherche ciblee des libelles/champs retires et lint cible du composant.

## 2026-07-20 - Ordre Grille puis Liste dans les toggles tickets

Demande: dans toutes les vues de tickets, conserver la grille par defaut et afficher l'icone Grille avant l'icone Liste.

Module: MOD-PERSONAL / MOD-AGENT / MOD-CHIEF / MOD-SUPERVISION.

Fichiers modifies:

- `frontend/src/components/layout-toggle.tsx`
- `frontend/src/routes/app.requests.index.tsx`
- `frontend/src/routes/app.requests.history.tsx`
- `frontend/src/routes/app.my-tickets.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: le composant commun `LayoutToggle` affiche maintenant le bouton Grille avant le bouton Liste. `Mes demandes`, `Historique` et `Mes tickets` n'utilisent plus la valeur de layout memorisee en session, afin de rouvrir en grille a chaque entree sur la page. `File d'attente` et `Supervision` etaient deja en etat local `grid`. Le basculement manuel reste disponible.

Verification: recherche ciblee des usages `LayoutToggle`/`LayoutMode` dans les routes frontend et lint cible des fichiers touches.

## 2026-07-20 - Separation Mes demandes et Historique

Demande: reorganiser l'affichage demandeur pour garder `resolved` dans `Mes demandes` et placer uniquement `closed`, `cancelled`, `rejected` dans `Historique`.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:

- `frontend/src/routes/app.requests.index.tsx`
- `frontend/src/routes/app.requests.history.tsx`
- `frontend/src/routes/app.index.tsx`
- `backend/api/repositories/RepositoryRequest.py`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/API_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: `Mes demandes` exclut `closed,cancelled,rejected`; `Historique` propose seulement `closed`, `cancelled`, `rejected`; `resolved` reste dans les listes actives/personnelles jusqu'a cloture ou autre statut terminal. Le repository accepte l'exclusion multi-statut et tient compte des alias de statuts historiques.

Verification: lint frontend cible et compilation backend cible.

## 2026-07-20 - Filtrage strict de A qualifier

Demande: corriger `A qualifier` pour exclure les statuts terminaux, limiter `Prendre la demande` aux statuts actifs et normaliser `cancalled`/`escaladed`.

Module: MOD-AGENT / MOD-CHIEF / MOD-REQUEST.

Fichiers modifies:

- `backend/api/core/ticket_actions.py`
- `backend/api/repositories/RepositoryRequest.py`
- `backend/api/services/ServiceRequest.py`
- `backend/tests/api/test_ticket_actions.py`
- `frontend/src/routes/app.queue.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/API_INDEX.md`
- `docs/codex/WORKFLOW_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: `/requests/triage` retourne uniquement `new`, `qualifying`, `qualified`, `reopened`; le frontend applique la meme garde avant d'afficher/activer `Prendre la demande`; `normalize_status` mappe `cancalled -> cancelled` et `escaladed -> escalated`; les tests verrouillent qu'un statut terminal ne peut pas aller vers `assigned`.

Verification: tests cibles `test_ticket_actions.py`, compilation ciblee backend et lint cible frontend.

## 2026-07-20 - Correction prise en charge A qualifier

Demande: corriger l'erreur affichee au clic sur `Prendre la demande`.

Module: MOD-AGENT / MOD-CHIEF / MOD-REQUEST.

Fichiers modifies:

- `frontend/src/routes/app.queue.tsx`
- `frontend/src/lib/api/requests.ts`
- `backend/api/routes/RouteRequest.py`
- `docs/codex/API_INDEX.md`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: le frontend pouvait envoyer une unite comme `direction_id` lors d'une prise directe depuis `A qualifier`, et l'endpoint imposait `direction_id` meme lorsque `unit_id` etait la vraie donnee utile.

Correction: `direction_id` devient optionnel pour `/requests/{id}/qualify` quand `unit_id` est fourni; `Prendre la demande` envoie prioritairement l'unite reelle de l'utilisateur et affiche le message backend exact en cas de refus.

Verification: compilation ciblee de `RouteRequest.py` et lint cible sur `app.queue.tsx`/`requests.ts`.

## 2026-07-20 - Listes de tickets en vue grille par defaut

Demande: afficher par defaut en vue grille partout ou une liste de ticket dispose deja d'une bascule liste/grille.

Module: MOD-PERSONAL / MOD-AGENT / MOD-SUPERVISION.

Fichiers modifies:

- `frontend/src/routes/app.my-tickets.tsx`
- `frontend/src/routes/app.queue.tsx`
- `frontend/src/routes/app.supervision.tsx`
- `frontend/src/routes/app.requests.history.tsx`
- `frontend/src/routes/app.chief-inbox.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: les layouts initiaux de `Mes tickets`, `File d'attente`, `Supervision` et `Historique` passent de `list` a `grid`. La `Boite chef` affiche ses cartes tickets en grille responsive. `Mes demandes` etait deja en `grid`. La vue liste reste accessible via les toggles existants lorsqu'ils existent.

Verification: `rg` cible sur les routes documentees avec `LayoutToggle`/`LayoutMode`; les routes direction, DG, SLA et admin ciblees n'exposent pas de toggle layout local a modifier.

## 2026-07-20 - Mes demandes en vue grille par defaut

Demande: afficher `Mes demandes` en vue grille par defaut.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:

- `frontend/src/routes/app.requests.index.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: la valeur par defaut du layout personnel `req:layout` passe de `list` a `grid`, tout en conservant le toggle liste/grille.

Verification: `eslint` cible sur `app.requests.index.tsx` avec `prettier/prettier` desactive pour ignorer le bruit CRLF existant.

## 2026-07-20 - Suppression export des demandes personnelles

Demande: supprimer la partie export concernant les propres demandes, pour tous les roles.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:

- `frontend/src/routes/app.requests.index.tsx`
- `frontend/src/routes/app.requests.history.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: retrait des boutons, menus, imports et handlers d'export dans `Mes demandes` et `Historique`. Les exports metier des modules rapports, direction, DG ou admin ne sont pas touches.

Verification: `eslint` cible sur `app.requests.index.tsx` et `app.requests.history.tsx` avec `prettier/prettier` desactive pour ignorer le bruit CRLF existant.

## 2026-07-20 - Prise en charge depuis A qualifier

Demande: remplacer `Resoudre directement` par `Prendre la demande` dans l'onglet `A qualifier`, afin que l'utilisateur se l'affecte et poursuive le traitement depuis `Mes tickets`.

Module: MOD-AGENT / MOD-CHIEF / MOD-REQUEST.

Fichiers modifies:

- `frontend/src/routes/app.queue.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: l'action directe de resolution dans `A qualifier` court-circuitait le flux normal de traitement agent.

Correction: l'action `Prendre la demande` reutilise `POST /requests/{id}/qualify` avec `assignee_id` de l'utilisateur connecte; la demande sort du triage, passe en `assigned`, puis les caches `qualify`, `queue`, `requests`, `my-tickets` et `my-tickets-stats` sont invalides.

Verification: `eslint` cible sur `frontend/src/routes/app.queue.tsx` avec `prettier/prettier` desactive pour ignorer le bruit CRLF existant.

## 2026-07-20 - Separation Mes tickets et File d'attente

Demande: reorganiser `Mes tickets` et `File d'attente` pour supprimer les doublons et garantir que les tickets pris sortent de la file.

Module: MOD-AGENT / MOD-CHIEF / MOD-REQUEST.

Fichiers modifies:

- `frontend/src/routes/app.my-tickets.tsx`
- `frontend/src/routes/app.queue.tsx`
- `frontend/src/lib/api/requests.ts`
- `backend/api/routes/RouteRequest.py`
- `backend/api/services/ServiceRequest.py`
- `backend/api/repositories/RepositoryRequest.py`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/API_INDEX.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/ROLE_INDEX.md`
- `docs/codex/ROUTE_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: `File d'attente` contenait encore une sous-vue `Mes tickets` et un filtre statut redondant; `Mes tickets` calculait aussi une partie de ses KPI depuis une source non strictement limitee aux tickets affectes a l'agent connecte.

Correction: `File d'attente` conserve seulement les vues `A prendre` et `A qualifier`; la vue `A prendre` appelle `/requests/queue` avec `unassigned_only=true`; `Mes tickets` liste et calcule ses KPI depuis `/requests` filtre par `assignee_id` de l'utilisateur connecte.

Verification: `python -m compileall backend/api/routes/RouteRequest.py backend/api/services/ServiceRequest.py backend/api/repositories/RepositoryRequest.py`; `eslint` cible avec `prettier/prettier` desactive sur les fichiers frontend touches. Le lint standard reste bloque par la configuration Prettier CRLF existante.

## 2026-07-20 - Detail ticket depuis File d'attente

Demande: corriger l'ouverture d'un ticket depuis `File d'attente` pour l'agent de traitement et les roles disposant de cet onglet, sans modifier les autres modules.

Module: MOD-AGENT / MOD-CHIEF / MOD-REQUEST.

Fichiers modifies:

- `backend/api/routes/RouteRequest.py`
- `backend/api/services/ServiceRequest.py`
- `backend/api/core/ticket_actions.py`
- `backend/tests/api/test_ticket_actions.py`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: la liste `/requests/queue` utilise un perimetre `unity_id` calcule via l'organigramme, mais le detail `/requests/{id}` et le garde d'actions agent/chef restaient limites a l'unite exacte. Un ticket pouvait donc etre visible dans la file puis refuse au detail.

Correction: reutilisation du meme perimetre `unity_id` calcule pour le detail et les actions agent/chef; la correspondance par `direction_id` seule reste refusee afin de ne pas elargir artificiellement les droits.

Verification: `python -m compileall backend/api/routes/RouteRequest.py backend/api/services/ServiceRequest.py backend/api/core/ticket_actions.py`; `backend\venv\Scripts\pytest.exe backend\tests\api\test_ticket_actions.py -q` -> 57 tests passes.

## 2026-07-20 - Affichage demandeur sans demandes cloturees

Demande: corriger l'espace Demandeur afin que les demandes cloturees ne s'affichent plus dans `Demandes recentes` ni dans `Mes demandes`, et restent visibles uniquement dans `Historique`.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:

- `frontend/src/routes/app.index.tsx`
- `frontend/src/routes/app.requests.index.tsx`
- `frontend/src/lib/api/requests.ts`
- `backend/api/routes/RouteRequest.py`
- `backend/api/services/ServiceRequest.py`
- `backend/api/repositories/RepositoryRequest.py`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/API_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: `Accueil > Demandes recentes` affiche les 3 demandes personnelles actives les plus recentes. `Mes demandes` appelle le filtre existant `/requests` avec `exclude_status=closed`, masque le statut `Cloturee` du select et remet un ancien choix memorise sur `Tous les statuts`. `Historique` reste le seul onglet personnel qui charge `closed`.

Verification: `python -m compileall backend/api/routes/RouteRequest.py backend/api/services/ServiceRequest.py backend/api/repositories/RepositoryRequest.py`; ESLint cible sur les fichiers frontend avec `prettier/prettier` desactive pour ignorer le bruit CRLF existant; `git diff --check` cible OK.

## 2026-07-20 - Suppression admin Directions et Services/Unites

Demande: corriger la suppression CRUD des Directions et des Unites/Services dans l'espace Administrateur, sans modifier les autres modules.

Module: MOD-ADMIN / MOD-ORG.

Chemins consultes:

- `AGENTS.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/MODULE_INDEX.md`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/API_INDEX.md`
- `docs/codex/DEPENDENCY_INDEX.md`
- `frontend/src/lib/api/directions-units.ts`
- `frontend/src/routes/app.admin.directions.tsx`
- `frontend/src/routes/app.admin.units.tsx`
- `backend/api/routes/RouteDirectionsUnits.py`
- `backend/api/repositories/base_repository.py`
- `backend/api/repositories/RepositoryOrganigram.py`
- `backend/api/models/ModelUnity.py`
- `backend/api/models/ModelOrganigram.py`

Fichiers modifies:

- `backend/api/routes/RouteDirectionsUnits.py`
- `docs/codex/CHANGELOG_CODEX.md`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/API_INDEX.md`
- `docs/codex/DEPENDENCY_INDEX.md`

Cause: la suppression soft-delete marquait seulement `unity.deleted_at`; les listes admin etaient basees sur `organigram.deleted_at` et continuaient a retourner la direction ou le service supprime.

Correction: les endpoints `DELETE /directions/{id}` et `DELETE /units/{id}` soft-delete maintenant la `Unity` et son noeud `Organigram` actif. Les listes/details `/directions/*` et `/units/*` excluent les `Unity` soft-deleted et les services dont la direction parente est supprimee.

Verification: `python -m compileall backend\api\routes\RouteDirectionsUnits.py`.

## 2026-07-20 - Historique aligne sur les filtres de Mes demandes

Demande: prendre la barre de recherche et l'organisation des filtres de `Mes demandes` comme reference, puis appliquer le meme format a `Historique` sans supprimer les fonctionnalites utiles propres a l'historique.

Module: MOD-PERSONAL / MOD-REQUEST.

Chemins consultes:

- `AGENTS.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/BUSINESS_RULES.md`
- `frontend/src/routes/app.requests.index.tsx`
- `frontend/src/routes/app.requests.history.tsx`

Fichiers modifies:

- `frontend/src/routes/app.requests.history.tsx`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: remplacement des onglets visuels de statut historique par un select compact place dans le meme bandeau que la recherche et la periode, sur le modele de `Mes demandes`. Les statuts historiques `resolues`, `cloturees`, `rejetees`, l'export, le layout, la pagination et les dates personnalisees restent disponibles.

Verification: controle cible du diff et des imports; aucun build global lance car la modification est limitee a l'UI d'une route et le projet ne fournit pas de script typecheck dedie.

## 2026-07-20 - Notifications ciblees par prochain acteur workflow

Demande: corriger le module Notifications afin qu'un ticket qui arrive dans une direction ne notifie plus tous les utilisateurs de cette direction, mais uniquement l'acteur qui doit effectuer la prochaine action.

Module: MOD-NOTIF / dependance directe MOD-REQUEST.

Chemins consultes:

- `AGENTS.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/MODULE_INDEX.md`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/DEPENDENCY_INDEX.md`
- `backend/api/services/NotificationEmitter.py`
- `backend/api/services/ServiceRequest.py`
- `backend/api/routes/RouteNotification.py`
- `backend/api/services/ServiceNotification.py`
- `backend/api/repositories/RepositoryNotification.py`
- `backend/api/core/event_bus.py`
- `frontend/src/lib/realtime/invalidation-map.ts`

Fichiers modifies:

- `backend/api/services/NotificationEmitter.py`
- `backend/api/services/ServiceRequest.py`
- `docs/codex/CHANGELOG_CODEX.md`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/API_INDEX.md`
- `docs/codex/MODULE_INDEX.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/DEPENDENCY_INDEX.md`

Correction: `NotificationEmitter` cree une notification pour un seul `recipient_id` puis publie `notification.created` uniquement vers `target.user_ids=[recipient_id]`. Le transfert inter-direction notifie seulement le directeur designe comme prochain acteur (`workflow_detail.dest_id` / `infos.target_user_id`) au lieu de boucler sur tous les directeurs de la direction cible.

Verification: `python -m compileall backend\api\services\NotificationEmitter.py backend\api\services\ServiceRequest.py`.

## 2026-07-13 - Creation demande: succes frontend fiable

Demande: corriger le comportement de creation d'une nouvelle demande quand le backend confirme la creation mais que l'interface peut afficher un faux etat d'erreur.

Module: MOD-PERSONAL / MOD-REQUEST.

Chemins consultes:

- `AGENTS.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/DEPENDENCY_INDEX.md`
- `frontend/src/components/new-request-form.tsx`
- `frontend/src/lib/api/requests.ts`
- `frontend/src/lib/api/client.ts`
- `frontend/src/routes/app.requests.index.tsx`
- `frontend/src/routes/app.tsx`
- `backend/api/routes/RouteRequest.py`
- `backend/api/services/ServiceRequest.py`
- `backend/api/schemas/SchemaRequest.py`

Fichiers modifies:

- `frontend/src/components/new-request-form.tsx`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: validation locale par champ obligatoire, toast vert de succes des que `POST /requests/` reussit, separation stricte entre erreur de creation et erreurs post-succes comme pieces jointes ou navigation, invalidation immediate des listes `requests` et preparation du cache detail.

Resultat: une creation HTTP 201 n'est plus convertie en faux message rouge par un effet secondaire; les erreurs locales restent sous les champs concernes.

## 2026-07-13 - Tableaux decisionnels enrichis

Demande: renforcer les rapports pour obtenir des tableaux complets exploitables en pilotage, audit, controle interne et comite de direction.

Module: MOD-REPORT.

Chemins consultes:

- `AGENTS.md`
- `docs/codex/REPORTING_DECISION_ENGINE.md`
- `docs/codex/API_INDEX.md`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/FEATURE_INDEX.md`
- `backend/api/services/ServiceReport.py`
- `backend/api/routes/RouteReports.py`
- `frontend/src/lib/api/reports.ts`

Fichiers modifies:

- `backend/api/services/ServiceReport.py`
- `backend/api/routes/RouteReports.py`
- `frontend/src/lib/api/reports.ts`
- `docs/codex/REPORTING_DECISION_ENGINE.md`
- `docs/codex/API_INDEX.md`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/MODULE_INDEX.md`
- `docs/codex/DEPENDENCY_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: enrichissement du moteur decisionnel avec vues `executive`, `analytical` et `audit`, groupes de colonnes, filtres multi-criteres, recherche, tri, pagination audit, exports complets avec metadonnees, catalogue KPI detaille et indicateurs de qualite/trace disponibles.

Resultat: la logique backend et le contrat API sont prets pour des tableaux decisionnels riches sans inventer de donnees; les donnees non structurees comme la cause detaillee de retard restent documentees comme ameliorations futures.

## 2026-07-13 - Moteur de reporting decisionnel

Demande: construire la logique de pilotage/reporting qui servira aux tableaux de bord, sans modifier l'interface si non necessaire.

Module: MOD-REPORT, MOD-DG, MOD-ADMIN.

Chemins consultes:

- `AGENTS.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/MODULE_INDEX.md`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/API_INDEX.md`
- `docs/codex/DEPENDENCY_INDEX.md`
- `backend/api/services/ServiceReport.py`
- `backend/api/routes/RouteReports.py`
- `backend/api/models/ModelRequest.py`
- `backend/api/models/ModelWorkflow.py`
- `backend/api/models/ModelWorkflowDetail.py`
- `backend/api/models/ModelAccount.py`
- `backend/api/models/ModelUnity.py`
- `frontend/src/lib/api/reports.ts`

Fichiers modifies:

- `backend/api/services/ServiceReport.py`
- `backend/api/routes/RouteReports.py`
- `frontend/src/lib/api/reports.ts`
- `docs/codex/REPORTING_DECISION_ENGINE.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/API_INDEX.md`
- `docs/codex/MODULE_INDEX.md`
- `docs/codex/DEPENDENCY_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: ajout de `GET /reports/decision` et `GET /reports/decision/export`, avec hierarchie EDG -> direction -> service/unite -> agent/responsable -> ticket, KPI consolides, tendances periode precedente, breakdowns par direction/service/statut/categorie/priorite/responsable/periode, et export CSV/Excel/PDF avec filtres appliques.

Resultat: le reporting dispose d'un moteur decisionnel reutilisable pour DG, admin, direction et responsables metier; les roles auditeur/controle interne restent documentes comme amelioration future car absents du modele de roles actuel.

## 2026-07-13 - Filtre direction de la vue globale admin

Demande: dans le module Administration, permettre a l'administrateur de superviser toutes les directions ou une direction precise depuis la vue globale, avec tickets regroupes par statut et rapport direction.

Module: MOD-DG, MOD-ADMIN, MOD-REPORT.

Chemins consultes:

- `AGENTS.md`
- `docs/codex/MODULE_INDEX.md`
- `docs/codex/ROUTE_INDEX.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/BUSINESS_RULES.md`
- `frontend/src/routes/app.dg.tsx`
- `frontend/src/lib/api/requests.ts`
- `frontend/src/lib/api/directions-units.ts`
- `frontend/src/lib/api/reports.ts`
- `frontend/src/lib/api/escalations.ts`

Fichiers modifies:

- `frontend/src/routes/app.dg.tsx`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/API_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: ajout du perimetre "Toutes les directions" / direction precise dans `/app/dg`, application de `direction_id` a `fetchRequests`, regroupement compact des tickets par statut, filtrage des escalades visibles selon les tickets du perimetre et export via le rapport existant `reports/by-unity`.

Resultat: l'admin conserve une supervision globale ou directionnelle dans le contexte pilotage administratif, sans melange avec `Mes demandes`.

## 2026-07-13 - Detail admin des notifications vers tickets archives

Demande: corriger le cas ou un clic notification admin ouvre `/app/admin/tickets/$id` mais affiche `Demande introuvable`.

Probleme traite: la navigation etait deja dans le bon contexte admin, mais certaines notifications pointaient vers une demande soft-deleted; `GET /requests/{id}` excluait ces demandes et le detail affichait une erreur generique.

Module: MOD-NOTIF, MOD-ADMIN, MOD-PERSONAL.

Chemins consultes:

- `AGENTS.md`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/API_INDEX.md`
- `frontend/src/routes/app.admin.tickets.$id.tsx`
- `frontend/src/routes/app.requests.$id.tsx`
- `frontend/src/lib/api/requests.ts`
- `backend/api/routes/RouteRequest.py`
- `backend/api/services/ServiceRequest.py`
- `backend/api/models/ModelNotification.py`

Fichiers modifies:

- `backend/api/services/ServiceRequest.py`
- `backend/api/routes/RouteRequest.py`
- `frontend/src/lib/api/requests.ts`
- `frontend/src/routes/app.requests.$id.tsx`
- `frontend/src/lib/mock-data.ts`
- `docs/codex/API_INDEX.md`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: une notification peut rester liee a `request.id` alors que la demande est soft-deleted; le detail admin doit pouvoir l'auditer sans rebasculer dans `Mes demandes`.

Correction: ajout de `include_deleted=true` sur `GET /requests/{id}`, honore uniquement pour le role admin; `RequestDetailPage` l'utilise seulement dans le contexte `admin`, separe le cache React Query du contexte personnel, affiche un etat `Ticket archive` et desactive les actions metier.

Tests:

- `python -m compileall backend/api/services/ServiceRequest.py backend/api/routes/RouteRequest.py`
- `npm run build`
- verification MySQL ciblee: `request.id=33` correspond a `EDG-2026-0025` avec `deleted_at` renseigne.

Resultat: un ticket archive ouvert depuis une notification admin reste dans `/app/admin/tickets/$id` et devient consultable en lecture seule.

## 2026-07-13 - Creation de AGENTS.md

Demande: créer un fichier `AGENTS.md` à la racine pour standardiser définitivement le comportement Codex sur EDG Connect.

Probleme traite: les consignes de travail devaient être centralisées afin de ne plus devoir les répéter à chaque conversation.

Module: documentation projet.

Chemins consultes:

- `docs/codex/README.md`
- `docs/codex/PROJECT_INDEX.md`
- `docs/codex/MODULE_INDEX.md`
- `docs/codex/ROLE_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Fichiers modifies:

- `AGENTS.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: absence d'une référence racine unique pour les règles d'intervention Codex.

Correction: ajout de `AGENTS.md` avec les sections identité projet, philosophie, sources de vérité, usage obligatoire de `docs/codex/`, recherche progressive, architecture, navigation, règles métier, dépendances, vérifications, documentation, gestion des index et règle absolue de travail.

Tests:

- vérification ciblée de présence/contenu de `AGENTS.md`.

Resultat: règle de comportement officielle disponible à la racine du dépôt.

## 2026-07-13 - Navigation des notifications vers le detail metier

Demande: corriger les liens de notifications qui ouvraient `/app/requests/$id` au lieu du detail metier adapte au role.

Probleme traite: depuis `/app/notifications` ou le panneau notifications, un admin/agent/chef/directeur/DG pouvait etre renvoye dans `Mes demandes`, puis voir `Demande introuvable`.

Module: MOD-NOTIF, MOD-PERSONAL, MOD-AGENT, MOD-CHIEF, MOD-SUPERVISION, MOD-DIRECTION, MOD-DG, MOD-ADMIN.

Chemins consultes:

- `docs/codex/ROUTE_INDEX.md`
- `docs/codex/BUSINESS_RULES.md`
- `frontend/src/lib/ticket-navigation.ts`
- `frontend/src/routes/app.notifications.tsx`
- `frontend/src/components/notification-panel.tsx`
- `frontend/src/lib/api/notifications.ts`

Fichiers modifies:

- `frontend/src/lib/ticket-navigation.ts`
- `frontend/src/routes/app.notifications.tsx`
- `frontend/src/components/notification-panel.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: `ticketDetailRouteForSource` traitait toute URL `/app/requests/...` comme un contexte personnel, meme quand cette URL venait d'une notification recue par un role professionnel.

Correction: ajout de `ticketDetailRouteForNotification` comme helper central dans `ticket-navigation.ts`; les deux surfaces notifications l'utilisent maintenant pour router admin/agent/chef/directeur/DG vers leurs details metier existants, tout en gardant `/app/requests/$id` pour le demandeur simple.

Tests:

- verification TypeScript ciblee frontend.
- recherche ciblee des imports notifications.
- verification directe de `ticketDetailRouteForNotification`: admin, agent, chief, director, dg, user et source direction explicite.

Resultat: navigation des notifications alignee sur BR-NAV-001 sans nouvelle route ni logique parallele.

## 2026-07-13 - Creation memoire technique initiale

Demande: construire une base de connaissance persistante dans `docs/codex/`.

Probleme traite: Codex devait disposer d'index locaux pour eviter de rescanner tout le projet a chaque intervention.

Module: documentation transversale.

Chemins consultes:

- `frontend/src/routes`
- `frontend/src/lib`
- `frontend/src/components/app-layout.tsx`
- `frontend/src/lib/capabilities.ts`
- `frontend/src/lib/ticket-navigation.ts`
- `backend/api/main.py`
- `backend/api/routes`
- `backend/api/services`
- `backend/api/models`
- `backend/api/core/rbac.py`
- `backend/api/core/ticket_actions.py`
- `backend/tests/api`

Fichiers modifies:

- `.gitignore`
- `docs/codex/*.md`

Cause: absence d'une cartographie locale structuree.

Correction: ajout des index projet, modules, fonctionnalites, frontend, backend, routes, API, database, roles, workflow, regles metier, dependances, fichiers, problemes connus et changelog.

Tests:

- verification a faire apres creation: presence des 16 fichiers.
- aucune correction fonctionnelle demandee ni effectuee.

Resultat: memoire technique initiale disponible.

Documents d'index mis a jour: tous les documents initiaux.

## 2026-07-13 - Hygiene artefacts Codex

Demande: aucun fichier temporaire Codex a la racine.

Probleme traite: des logs `.codex-uvicorn*.log` etaient encore a la racine.

Module: hygiene projet.

Chemins consultes:

- `.gitignore`
- racine du projet

Fichiers modifies:

- `.gitignore`

Cause: motifs explicites `.codex-*.log` non couverts comme regle nommee, meme si `*.log` existait deja.

Correction: deplacement des logs vers `.codex/logs/` et ajout du motif `/.codex-*.log`.

Tests:

- listing cible racine.

Resultat: logs ranges sous `.codex/logs/`.
