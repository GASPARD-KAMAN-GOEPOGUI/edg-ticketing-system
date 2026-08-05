# Known Issues

## KI-TRACE-REACT-001

Identifiant: KI-TRACE-REACT-001
Titre: Mise a jour d'etat React sur une fibre non encore montee
Date: 2026-08-05
Environnement: developpement Vite + React 19 uniquement (jamais observe/teste en build de production — voir "Build de production").
Ecran / composant: detail ticket (`frontend/src/routes/app.requests.$id.tsx`), section Journal — bascule entre les vues "Journal des interventions" et "Chronologie complete" (BR-TRACE-001). Le composant `InterventionJournal` (`frontend/src/components/intervention-journal.tsx`) est demonte/remonte integralement a chaque bascule (remplacement conditionnel `journalView === "interventions" ? <InterventionJournal/> : <WorkflowTimeline/>`, ligne ~3460 — pas un simple masquage CSS).
Frequence: intermittente, non reproductible de maniere deterministe. Observee 2 fois consecutives lors de la recette visuelle du 2026-08-04 (`journal_recette_followup.mjs`), puis 0 fois sur 4 nouvelles tentatives de reproduction cibleee le 2026-08-05 (voir "Scenarios de reproduction testes").
Impact fonctionnel observe: aucun. Aucune donnee perdue, aucun blocage d'interaction, aucune regression visuelle constatee pendant ou apres l'occurrence.
Perte de donnees: aucune — confirme par re-verification complete (toutes les interventions restent presentes et consultables apres la sequence ayant produit l'avertissement).
Build de production: reussi (`npm run build`, aucune erreur, aucun avertissement equivalent — coherent avec une cause liee au serveur de developpement Vite, absente en production).
Message console complet (capture verbatim, `followup_console.json`):
```
Can't perform a React state update on a component that hasn't mounted yet. This indicates
that you have a side-effect in your render function that asynchronously tries to update
the component. Move this work to useEffect instead.
```
Origine confirmee dans le code source (pas une supposition): `react-dom/cjs/react-dom-client.development.js`, fonction `warnAboutUpdateOnNotYetMountedFiberInDEV` (lignes ~18718-18737), appelee depuis `getRootForUpdatedFiber` (lignes ~4634-4640) — avertissement interne de React 19, declenche quand une mise a jour d'etat cible une fibre dont `alternate === null` (jamais montee) alors que la mise a jour survient hors phase de rendu (donc de maniere asynchrone). Le `console.error` de React n'imprime aucun nom de composant ni stack applicative dans son texte.
Hypothese principale: course interne d'une primitive Radix UI pendant le demontage complet du sous-arbre `InterventionJournal` au moment de la bascule — un effet asynchrone (positionnement `Popover`/`Select` via portail, ou animation de fermeture `Dialog`) declenche avant le demontage tenterait de mettre a jour une fibre jamais commitee.
Facteurs possibles: `Popover` (`intervention-filters.tsx`), `Select` (`intervention-filters.tsx`), `Dialog` (`intervention-details-modal.tsx`), portail Radix (rendu hors arbre DOM principal), compilation Vite a froid (les deux occurrences historiques etaient systematiquement precedees du meme avertissement Vite sans rapport `[tanstack-router] These exports from "app.chief-inbox.tsx" will not be code-split…`, qui n'apparait que lors d'une transformation de module a la volee — indice d'un ralentissement du tick JS au moment critique, absent une fois le cache Vite chaud).
Verifications deja effectuees:
- recherche exhaustive (`grep`) de `useEffect`/`useLayoutEffect`/`setTimeout`/`requestAnimationFrame`/`.then(` dans les 5 fichiers du Journal (`intervention-journal.tsx`, `intervention-detail-body.tsx`, `intervention-details-modal.tsx`, `intervention-filters.tsx`, `workflow-timeline.tsx`) — aucune occurrence, ecarte une cause directe dans le code applicatif BR-TRACE-001 ;
- verification des cles React (`CycleSection` par `cycleNumber`, `InterventionCard` par `iv.interventionId`) — stables et uniques, ecarte une cause par cle dupliquee/instable ;
- verification d'un pattern controle/non-controle sur `journalView` et les etats locaux `open` des accordeons — simples `useState` initialises une fois, aucun pattern `value`/`undefined` a risque ;
- recherche de `setState` appele directement dans le corps d'un composant (hors gestionnaire d'evenement/effet) dans les 5 fichiers — aucune occurrence ;
- lecture du code source React (`react-dom-client.development.js`) pour confirmer la condition de declenchement exacte plutot que de deviner a partir du texte du message.
Scenarios de reproduction testes (4, sans resultat — navigateur reel, Chromium/Playwright):
1. sequence exacte de la recette du 2026-08-04 repetee 3 fois (Journal -> Chronologie -> Journal) ;
2. 10 bascules rapides consecutives sans delai d'attente ;
3. ouverture du popover Filtres puis interaction avec le Select "Cycle" laisse ouvert, bascule immediate sans fermeture propre ;
4. fermeture de la fiche de consultation (Echap) suivie d'une bascule immediate, sans attendre la fin de l'animation de fermeture Radix (~150-200 ms).
Points ecartes explicitement (ne pas confondre avec la cause de cette entree — deja documentes separement lors de la recette du 2026-08-04, cf. `docs/codex/CHANGELOG_CODEX.md` et le rapport de recette visuelle) : les identifiants `aria-controls` partages par les deux boutons d'une meme `InterventionCard`, et la reinitialisation de l'etat deplie/replie des accordeons de cycle a chaque bascule de vue. Ni l'un ni l'autre ne transite par `warnAboutUpdateOnNotYetMountedFiberInDEV` et aucun des deux n'a ete retenu comme cause de cet avertissement. Ils ne sont pas repris ici comme des anomalies necessitant une entree KI dediee tant qu'aucune decision de correction ne les concerne.
Module: MOD-WORKFLOW / MOD-AGENT / MOD-CHIEF / MOD-DIRECTION (BR-TRACE-001, presentation uniquement).
Role concerne: tous les roles consultant le detail d'un ticket avec journal d'interventions.
Regle metier: BR-TRACE-001 (aucune regle metier affectee — anomalie de presentation/outillage dev, pas de logique de traitement).
Chemins probables: `frontend/src/routes/app.requests.$id.tsx` (point de bascule), `frontend/src/components/intervention-filters.tsx` (`Popover`/`Select`), `frontend/src/components/intervention-details-modal.tsx` (`Dialog`) — cause non confirmee au-dela de ce perimetre.
Cause: non confirmee avec certitude — hypothese documentee ci-dessus, aucune stack applicative capturee au moment de l'occurrence (le `console.error` de React ne l'imprime pas).
Correction: non appliquee et non recommandee dans l'etat actuel — voir "Recommandation".
Fichiers modifies: aucun (bug documente uniquement, aucun composant React touche).
Test: aucun test automatise pertinent (avertissement console non deterministe) — surveillance manuelle recommandee lors d'un usage prolonge en developpement.
Recommandation: surveiller avant correction. Ne pas corriger a l'aveugle un phenomene non reproduit de maniere stable ; risque de modifier un composant Radix/Journal sans agir sur la cause reelle.
Condition de reouverture du chantier: reproduction stable avec capture de la stack applicative au moment exact de l'occurrence, OU impact utilisateur confirme (aucun des deux n'est reuni a ce jour).
Statut: surveillance — non bloquant.

## KI-SQL-001

Identifiant: KI-SQL-001
Date: 2026-08-01
Symptome: `GET /reports/decision` (et son export) renvoie systematiquement une erreur 500 (`DATABASE_ERROR` / `OperationalError: near "SEPARATOR": syntax error`) pour TOUT role, des qu'il est appele via une requete HTTP reelle dans la suite de tests backend (SQLite en memoire, `backend/tests/conftest.py`).
Resultat actuel: `ServiceReport._decision_rows()` (`backend/api/services/ServiceReport.py`, sous-requete workflow_detail ~lignes 391-400) utilise `GROUP_CONCAT(... SEPARATOR ' | ')` — syntaxe MySQL uniquement. SQLite exige `group_concat(expr, separateur)` (deuxieme argument positionnel, pas de mot-cle `SEPARATOR`). Aucun test existant dans toute la suite n'appelait `/reports/decision` via HTTP avant sa decouverte (chantier "File d'attente / actions par role", Lot 4.4, 2026-08-01) — la couverture reelle de cet endpoint etait donc nulle, tous roles confondus, pas seulement pour director.
Resultat attendu: `/reports/decision` executable et testable via HTTP dans la suite SQLite comme n'importe quel autre endpoint, pour permettre une verification bout-en-bout (et pas seulement une verification unitaire de la logique de scope en amont de la requete SQL).
Module: MOD-REPORT (BR-REPORT-DECISION-001), MOD-CHIEF (FEATURE-DEPARTMENT-PILOTAGE), MOD-DIRECTION (FEATURE-STRATEGIC-DASHBOARD) — tous les consommateurs de `AggregatedServiceDashboard`/`fetchDecisionReport`.
Role concerne: tous (bug independant du role — chief-departement, director, admin, tout appelant de `/reports/decision`).
Regle metier: BR-REPORT-DECISION-001.
Chemins probables: `backend/api/services/ServiceReport.py` (`_decision_rows`, lignes ~391-400), `backend/tests/conftest.py` (moteur SQLite de test).
Cause: la requete SQL brute de `/reports/decision` est ecrite pour MySQL (dialecte de production, cf. CLAUDE.md) sans portabilite vers SQLite (dialecte de test).
Correction: non appliquee — hors perimetre du chantier qui l'a decouverte (Lot 4). Piste de correctif a valider separement : soit reecrire la sous-requete avec une syntaxe portable (ex. `group_concat(expr, ' | ')` fonctionne sur MySQL ET SQLite, sans le mot-cle `SEPARATOR`), soit detecter le dialecte SQLAlchemy et adapter la clause, soit deplacer l'agregation cote Python apres une requete plus simple.
Fichiers modifies: aucun (bug documente, non corrige).
Test: `backend/tests/api/test_decision_report_director_scope.py` (2 tests ecrits et marques `pytest.mark.skip` avec la raison exacte — a reactiver des que ce correctif sera fait, ou executable des maintenant contre une vraie base MySQL).
Statut: ouvert — dette technique separee, a traiter dans un chantier dedie de portabilite SQL (confirme explicitement hors perimetre immediat par le demandeur, 2026-08-01).

## KI-HOMEPAGE-001

Identifiant: KI-HOMEPAGE-001
Date: 2026-08-01
Symptome: la page admin `/app/admin/homepage` (gestion du contenu de la page d'accueil publique et du carrousel de slides) ne peut rien lire ni sauvegarder : tous ses appels API echouent.
Resultat actuel: `frontend/src/lib/api/homepage.ts` appelle `/homepage-config/`, `/admin/homepage-config`, `/admin/homepage-config/sections/*`, `/homepage/slides/`, `/admin/homepage/slides/*`. Aucune de ces routes n'existe cote backend (`main.py` ne contient aucune reference a "homepage", confirme par recherche exhaustive dans `backend/api/`). Cause racine : la migration Alembic `012_drop_obsolete_tables.py` (2026-06-22) a supprime les tables `homepage_config` et `homepage_slide` avec la justification explicite "frontend statique, pas de config DB" — une decision d'architecture (accueil statique cote frontend) qui n'a jamais ete repercutee sur la page admin, restee une UI CRUD complete pointant vers un backend qui n'existe plus. Aucune migration posterieure (013/014/015) ne recree ces tables. La lecture publique (`fetchHomepageConfig`, `fetchSlides`) est encapsulee dans un `try/catch` qui retombe silencieusement sur `DEFAULT_CONFIG`/liste vide (aucune erreur visible), mais les mutations admin (`saveHomepageConfigApi`, `createSectionApi`, `updateSectionByIdApi`, `deleteSectionApi`, `fetchAdminSlides`, `createSlideApi`, `updateSlideApi`, `deleteSlideApi`) n'ont pas ce filet et echoueront visiblement (404) des qu'un admin tente d'utiliser cette page.
Resultat attendu: soit (a) reimplementer les tables/routes/service backend homepage-config et homepage-slide si l'edition admin du contenu d'accueil doit rester une fonctionnalite active, soit (b) retirer/desactiver `app.admin.homepage.tsx` et son entree de navigation si l'accueil doit rester definitivement statique cote frontend (conformement a la decision deja actee dans la migration 012) — decision produit a trancher, hors perimetre de cet audit.
Module: MOD-ADMIN.
Role concerne: admin.
Regle metier: aucune regle BUSINESS_RULES.md ne couvre ce module (absent de l'index).
Chemins probables: `frontend/src/routes/app.admin.homepage.tsx`, `frontend/src/lib/api/homepage.ts`, `backend/alembic/versions/012_drop_obsolete_tables.py`, `backend/api/main.py`.
Cause: decommission backend (migration 012, 2026-06-22) non repercutee sur le frontend admin.
Correction: non appliquee — decision produit requise avant toute action (voir "Resultat attendu").
Fichiers modifies: aucun (bug documente, non corrige).
Test: `backend/tests/api/test_homepage_slides.py` confirme le bug empiriquement — les 14 tests (public + admin CRUD) echouent tous (`pytest tests/api/test_homepage_slides.py -q` → `14 failed`), aucun `pytest.mark.skip`, execution normale en suite.
Statut: ouvert — decouvert lors de l'audit espace administrateur du 2026-08-01.

## KI-ROUTE-001

Identifiant: KI-ROUTE-001
Date: 2026-07-13
Symptome: confusion possible entre route detail personnelle `/app/requests/$id` et routes detail metier.
Resultat actuel: des corrections recentes ont introduit des routes detail dediees, mais les fichiers `app.*_.tickets.$id.tsx` doivent etre verifies si une URL detail ne correspond pas au contexte attendu.
Resultat attendu: un ticket ouvert depuis Supervision reste dans Supervision; depuis Traitement reste dans Traitement; depuis Administration reste dans Administration.
Module: MOD-SUPERVISION, MOD-AGENT, MOD-CHIEF, MOD-DIRECTION, MOD-DG, MOD-ADMIN.
Role concerne: tous les roles professionnels.
Regle metier: BR-NAV-001.
Chemins probables: `ticket-navigation.ts`, `app-layout.tsx`, `app.*_.tickets.$id.tsx`, `routeTree.gen.ts`.
Cause: a confirmer seulement si le symptome reapparait.
Correction: non applicable dans cette mission; ne pas modifier sans demande explicite.
Fichiers modifies: aucun.
Test: utiliser `frontend/role-visual-check.mjs`.
Statut: surveillance.

## KI-DOC-001

Identifiant: KI-DOC-001
Date: 2026-07-13
Symptome: cette base de connaissance est une premiere cartographie; certains endpoints secondaires restent resumes.
Resultat attendu: chaque prochaine intervention doit enrichir l'index concerne avec les details exacts decouverts.
Module: documentation.
Role concerne: Codex.
Regle metier: mise a jour automatique des index.
Chemins probables: `docs/codex/*.md`.
Cause: cartographie initiale volontairement synthetique pour rester exploitable.
Correction: completer au fil des corrections ciblees.
Fichiers modifies: `docs/codex/*`.
Test: verification presence docs.
Statut: ouvert.

## KI-TEMP-001

Identifiant: KI-TEMP-001
Date: 2026-07-13
Symptome: fichiers temporaires Codex visibles a la racine.
Resultat actuel: artefacts connus de type `.codex-build-*`, profils navigateur, `.codex-visual-tests`, `.codex-uvicorn*.log` ranges dans `.codex/`.
Resultat attendu: aucun fichier temporaire Codex a la racine.
Module: hygiene projet.
Role concerne: Codex.
Regle metier: fichiers temporaires dans `.codex/`.
Chemins probables: `.gitignore`, scripts de test visuel, commandes locales.
Cause: anciens scripts/outils ecrivaient a la racine.
Correction: `.gitignore` ignore `.codex/` et motifs `.codex-*`; `role-visual-check.mjs` ecrit sous `.codex/`.
Fichiers modifies: `.gitignore`, `frontend/role-visual-check.mjs`.
Test: listing racine cible.
Statut: corrige/surveillance.
