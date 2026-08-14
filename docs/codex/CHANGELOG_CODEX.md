# Changelog Codex

## 2026-08-13 - KPI "Transmis"/"Retransmis" sur "Mes tickets" (BR-RETRANSMIT-001)

Demande: faire parler les KPI de "Ma boîte de traitement" en fonction des actions de flux entre file d'attente, boîte de traitement, transmis, retransmis, revenu — discussion préalable demandée explicitement par l'utilisateur avant toute implémentation.

Discussion (résumé) : "revenu dans sa boîte" écarté comme KPI séparé (redondant — capturé implicitement par "retransmis") ; "retransmis" défini comme "un ticket qui revient vers moi ET que je renvoie ensuite" ; décision de remplacer 4 des 6 KPI actuels (Durée moyenne actifs, Critiques, Durée la plus longue actifs, Délai moyen résolution) par "Transmis"/"Retransmis", pour une grille finale à 4 cartes (En cours, Total résolus, Transmis, Retransmis).

Implémentation :
1. **Backend** — nouveau paramètre `retransmitted_only: bool = False` sur la route existante `GET /requests/transmitted` (pas de nouvel endpoint, réutilise BR-TRANSMIT-001) : ajoute `HAVING COUNT(*) >= 2` au `GROUP BY wf.request_id` déjà présent dans `list_transmitted_by_actor()` (`RepositoryRequest.py`). "Retransmis" = tickets où l'acteur a un événement `treatment_transmitted` au moins deux fois — transmettre deux fois implique nécessairement un retour entre les deux, donc pas besoin de modéliser "revenu" séparément.
2. **Frontend** — `fetchTransmittedByMe()` (`lib/api/requests.ts`) accepte le nouveau filtre `retransmitted_only`. `app.my-tickets.tsx` : deux nouvelles requêtes `useQuery` (`limit: 1`, ne lisent que `.total`) alimentent les cartes "Transmis" (icône `Send`) et "Retransmis" (icône `Repeat2`, mise en évidence ambre si > 0) ; les 4 KPI calculés localement retirés (`activeAssignedTickets`, `resolutionDurations`, `kpiCritical`, `kpiAvgActiveHours`, `kpiLongestActiveHours`, `kpiAvgResolution`) ainsi que les imports `ShieldAlert`/`TrendingUp` devenus inutilisés.

Fichiers modifiés: `backend/api/repositories/RepositoryRequest.py`, `backend/api/services/ServiceRequest.py`, `backend/api/routes/RouteRequest.py`, `backend/tests/api/test_transmit_treatment.py`, `frontend/src/lib/api/requests.ts`, `frontend/src/routes/app.my-tickets.tsx`, `docs/codex/BUSINESS_RULES.md` (BR-RETRANSMIT-001), `docs/codex/CHANGELOG_CODEX.md`.

Vérifications réalisées : `pytest tests/api/test_transmit_treatment.py` → 13 passés (scénario A→B→A→C existant complété avec les assertions `retransmitted_only`). `python -m py_compile` sur les 3 fichiers backend modifiés → OK. `tsc --noEmit` sur le frontend → aucune erreur dans les fichiers modifiés (erreurs pré-existantes et sans rapport dans `app.supervision.tsx`, non touché).

Modules non touchés : `app.transmitted.tsx` (page "Tickets transmis" existante, le nouveau paramètre est optionnel et absent de son appel — comportement par défaut inchangé), le reste de la grille KPI (En cours, Total résolus).

## 2026-08-13 - Correctif : messagerie active sur un ticket annulé (complément BR-MESSAGING-PARTICIPANTS-001)

Demande: sur un ticket au statut "Annulée", la zone de saisie de l'onglet "Discussions" restait active (capture d'écran à l'appui) — il faut bloquer l'envoi de message dans ce cas.

Diagnostic: le verrou de messagerie existait déjà pour les statuts terminaux `closed`/`rejected`, mais `cancelled` avait été oublié à trois endroits distincts, tous porteurs de la même logique dupliquée : `isDiscussionLocked` (frontend, contrôle l'affichage de la zone de saisie), `canDeleteComment` (frontend, autorisation de suppression), et `delete_comment` (backend, même garde côté serveur). Plus grave : `create_comment` (backend, `POST /requests/{id}/comments`) ne vérifiait **aucun statut** avant ce correctif — seule l'UI empêchait la saisie, un appel API direct (Swagger, curl, token valide) pouvait donc poster un message sur un ticket clôturé, rejeté ou annulé sans aucun blocage serveur.

Correction :
1. `create_comment` (`RouteRequest.py`) — nouvelle garde 422 si `request_status in {closed, rejected, cancelled}` ou `deleted_at is not None`, avant même la vérification du workflow actif.
2. `delete_comment` (`RouteRequest.py`) — `cancelled` ajouté à l'ensemble de statuts déjà bloqués (`closed`, `rejected`).
3. `isDiscussionLocked` et `canDeleteComment` (`app.requests.$id.tsx`) — `cancelled` ajouté aux deux conditions. La zone de saisie (précédemment une condition dupliquée en dur) réutilise désormais `isDiscussionLocked` comme source unique de vérité.

Fichiers modifiés: `backend/api/routes/RouteRequest.py`, `frontend/src/routes/app.requests.$id.tsx`, `docs/codex/BUSINESS_RULES.md` (complément BR-MESSAGING-PARTICIPANTS-001), `docs/codex/CHANGELOG_CODEX.md`.

Vérifications réalisées : `python -m py_compile` sur `RouteRequest.py` → OK. Test de régression ciblé par isolation (`git stash` limité à `RouteRequest.py` seul, sans toucher au reste de l'arbre) : `pytest tests/api/test_directive_comment.py` produit exactement les 3 mêmes échecs avec et sans le correctif — confirmé pré-existants et sans rapport avec ce changement (échec sur `POST /requests/3/qualify` → 404, endpoint de qualification, aucun lien avec la messagerie). Aucun test dédié à la messagerie n'a régressé.

Modules non touchés : lecture des messages (`GET /requests/{id}/comments`), directive chef→agent (garde de rôle indépendante, déjà vérifiée avant la garde de statut ajoutée).

## 2026-08-13 - Validation stricte des numéros de téléphone (BR-PHONE-FORMAT-001)

Demande: contrôler correctement les champs de saisie téléphone — un numéro n'est valide que sous l'un des formats `+224 6XX XX XX XX`, `224 6XX XX XX XX` ou `6XX XX XX XX`.

Constat: `normalize_phone()` (`backend/api/core/phone.py`) ne faisait que reformater n'importe quelle suite de chiffres vers `+224<suite>` sans jamais vérifier le préfixe mobile (`6`) ni la longueur (9 chiffres locaux) — un numéro invalide (ex. `123456`, `+224512345678`) était accepté silencieusement. Côté frontend, les champs téléphone (`register.tsx`, `app.profile.tsx`) étaient de simples `<Input>` sans aucune validation, juste un placeholder indicatif.

Correction :
1. Nouvelle fonction `validate_guinea_phone()` (`backend/api/core/phone.py`) — normalise puis vérifie le format (`^6\d{8}$` sur la partie locale), lève `ValueError` sinon. `normalize_phone()` reste inchangée et permissive (utilisée pour la recherche/dédoublonnage, où bloquer une saisie en cours serait une régression UX).
2. Câblée en validateur Pydantic sur `AccountBase.phone`/`AccountUpdate.phone` (`SchemaAccount.py`) et `RegisterRequest.phone` (`SchemaAuth.py`) → 422 automatique sur tout numéro mal formé, sur `POST /auth/register`, `PUT /users/{id}`, `PUT /users/me`, `POST /accounts`.
3. Nouveau `frontend/src/lib/phone.ts` (regex miroir) + validation inline (message d'erreur, bouton désactivé) dans `register.tsx` et `app.profile.tsx` — les deux seuls formulaires collectant un téléphone en saisie libre (`app.admin.users.tsx` n'a pas de champ téléphone ; `track.tsx` accepte email OU téléphone comme identifiant de recherche, volontairement non contraint).

Fichiers modifiés: `backend/api/core/phone.py`, `backend/api/schemas/SchemaAccount.py`, `backend/api/schemas/SchemaAuth.py`, `backend/tests/core/test_phone.py` (nouveau), `frontend/src/lib/phone.ts` (nouveau), `frontend/src/routes/register.tsx`, `frontend/src/routes/app.profile.tsx`, `docs/codex/BUSINESS_RULES.md` (BR-PHONE-FORMAT-001), `docs/codex/CHANGELOG_CODEX.md`.

Vérifications réalisées : `pytest tests/core/test_phone.py` → 16 passés (formats acceptés/rejetés + câblage schémas). `pytest tests/api/test_auth.py` → 24 passés (aucune régression). Test d'intégration HTTP volontairement omis pour `/auth/register` : le rate-limiter (5/60s) est déjà saturé par les tests existants de la même classe — couverture assurée au niveau schéma Pydantic à la place (identique en pratique, sans dépendance d'ordonnancement fragile).

Modules non touchés : `normalize_phone()` (recherche/dédoublonnage), `RouteAccount.py::check_duplicate`, formulaire admin utilisateurs (pas de champ téléphone).

## 2026-08-13 - Correctif sécurité : comptes inactifs pouvaient s'authentifier (BR-AUTH-ACCOUNT-STATUS-001)

Demande: après autorisation du scope `user.delete` côté plateforme centrale pour la suppression de comptes (session précédente), l'utilisateur signale un problème lié à "l'authentification qui ne marche pas" et précise l'attendu : seuls les comptes actifs doivent pouvoir s'authentifier, les comptes inactifs ne doivent jamais s'authentifier.

Diagnostic: deux champs distincts existent sur `Account` — `status` (flag générique hérité de `BaseColumns`, essentiellement un indicateur de soft-delete) et `account_status` (champ métier réel, valeurs `active`/`inactive`/`suspended`/`locked` du référentiel `account_statuses`, celui affiché/filtré dans le backoffice admin `app.admin.users.tsx` et déjà utilisé comme critère d'éligibilité partout ailleurs : assignation automatique `ServiceRequest.py`, escalade `ServiceEscalade.py`, ciblage annonces `ServiceAnnouncement.py`). La porte d'authentification `resolve_central_account()` (`dependencies.py`, utilisée par `/auth/login` et par `get_current_user` pour chaque requête authentifiée) ne vérifiait que `account.status` — jamais `account.account_status`. Le bouton dédié "Activer/Désactiver" du backoffice synchronise bien les deux champs ensemble (`ServiceAccount.set_active()`), mais `account_status` reste éditable indépendamment via le formulaire général de mise à jour d'un compte (`AccountUpdate.account_status`), sans toucher `status` — un compte pouvait donc devenir `inactive` métier tout en restant capable de se connecter et d'utiliser l'application.

Correction (un seul fichier touché) :
1. `resolve_central_account()` (`backend/api/dependencies.py`) rejette désormais aussi (401) toute requête dont `account.account_status` (normalisé, insensible à la casse/espaces) n'est pas exactement `"active"`. Comme cette fonction gate à la fois le login et chaque requête authentifiée suivante, une session déjà active est également coupée dès sa prochaine requête si le compte est désactivé en cours de session — pas seulement empêchée de se reconnecter.
2. Tests de régression ajoutés dans `backend/tests/api/test_auth.py` : `test_login_compte_inactif_retourne_401` (login refusé pour `account_status="inactive"` même avec identifiants centraux valides), `test_session_active_bloquee_apres_desactivation` (session active coupée dès la requête suivant une désactivation).

Fichiers modifiés: `backend/api/dependencies.py`, `backend/tests/api/test_auth.py`, `docs/codex/BUSINESS_RULES.md` (nouvelle section "Authentification", BR-AUTH-ACCOUNT-STATUS-001), `docs/codex/CHANGELOG_CODEX.md`.

Vérifications réalisées : `pytest tests/api/test_auth.py` → 24 passés (dont les 2 nouveaux tests). Aucun test existant ne créait de compte avec `account_status` non-`"active"` avant cette correction (vérifié par recherche ciblée) — aucune régression attendue sur la suite existante.

Modules non touchés : flux central (`central_auth.central_login`), bouton Activer/Désactiver existant (déjà correct), autres services filtrant déjà sur `account_status`.

## 2026-08-11 - Masquage de tout affichage SLA/délai dans l'application (BR-NO-SLA-DISPLAY-001)

Demande: après la désactivation de l'escalade automatique (BR-NO-AUTO-ESCALATION-001), l'utilisateur a remarqué que la carte KPI "Délais dépassés" restait visible sur la page Supervision et a demandé pourquoi, alors qu'il pensait avoir demandé de désactiver "la partie délai" partout. Clarification explicite obtenue (question posée avant modification, AGENTS.md §16) : périmètre le plus large — tout badge, pourcentage, carte KPI et graphique lié au SLA/délai doit disparaître, dans tous les rôles (admin/chef/direction/DG), y compris la page Centre SLA entière.

Correction — retrait des éléments d'affichage suivants (données/endpoints backend non touchés, changement 100% frontend) :
- `app-layout.tsx` : entrée de navigation "Centre SLA" retirée.
- `app.supervision.tsx` : carte KPI "Délais dépassés", barre "Délais dépassés" du graphique, métrique "Retards" des cartes agent, colonne "Délais dépassés" du tableau agents, colonnes "Retards"/"Dép. délai" du tableau "Supervision des services".
- `app.requests.$id.tsx` : onglet "Délais de traitement" retiré de la fiche ticket.
- `app.dg.tsx` : badge "Délai dépassé +Xh" sur les cartes d'escalade, bloc entier "Carte thermique des délais par direction".
- `app.direction.tsx` : carte KPI "Hors délai", badge "+Xh délai" sur les cartes d'escalade, colonne "Délai dépassé" du tableau chefs, barre "Hors délai" du graphique par service.
- `app.reports.tsx` : cartes KPI "Taux délai (actif)" et "Délai moyen résolution".
- `app.admin.audit.tsx` : carte KPI "Délais dépassés".
- `app.index.tsx` : raccourci "Centre SLA", cartes KPI "Délais dépassés" (3 variantes selon rôle), carte thermique "Performance par direction" (heatmap SLA par direction).

Exclusions délibérées (documentées dans `BUSINESS_RULES.md`, pas un oubli) : `app.admin.sla.tsx` (page de configuration des heures SLA, pas un affichage de statut), l'option d'export "Délai" sur Rapports (fichier téléchargé à la demande, pas affiché à l'écran), le widget "Temps de traitement" de la fiche ticket (déjà reformulé en durée neutre sans jugement de conformité, sans pourcentage ni badge), le toggle "Alertes délais critiques" du Profil (préférence personnelle, déjà sans effet), et les mentions "SLA" du texte marketing de la page publique.

Fichiers modifiés: `frontend/src/components/app-layout.tsx`, `frontend/src/routes/app.supervision.tsx`, `frontend/src/routes/app.requests.$id.tsx`, `frontend/src/routes/app.dg.tsx`, `frontend/src/routes/app.direction.tsx`, `frontend/src/routes/app.reports.tsx`, `frontend/src/routes/app.admin.audit.tsx`, `frontend/src/routes/app.index.tsx`, `docs/codex/BUSINESS_RULES.md`, `docs/codex/CHANGELOG_CODEX.md`.

Vérification: `npx tsc --noEmit` → 57 erreurs à chaque étape intermédiaire vérifiée, total identique à la référence tout au long de l'intervention (aucune régression). Contexte notable : le dépôt contient en parallèle un chantier indépendant et volumineux, sans rapport avec cette demande (retrait du module biométrie/incidents sécurité, intégration d'une plateforme d'authentification centrale) — confirmé via `git stash`/`git status`, qui a aussi permis d'établir que le total de 57 erreurs est stable indépendamment de ce chantier concurrent. Variables et fonctions devenues mortes après retrait des affichages (`slaColorClass`, `slaBreached`/`slaBreachedMine` locaux, comptage `slaBreached` dans les agrégations par service) nettoyées à chaque fois plutôt que laissées en code mort.

## 2026-08-10 - Migration méthode HTTP : PATCH → PUT sur tous les endpoints de mise à jour (BR-HTTP-METHOD-PUT-001)

Demande: remplacer la méthode HTTP `PATCH` par `PUT` sur l'ensemble des endpoints de mise à jour, en conservant strictement le même comportement (mêmes payloads partiels acceptés, mêmes validations, mêmes réponses) — recommandation de standardisation, aucune logique métier concernée.

Correction (purement mécanique, aucun changement de comportement) :
1. **Backend** — tous les décorateurs `@router.patch(`, `@director_router.patch(`, `@me_router.patch(`, `@directions_router.patch(`, `@departments_router.patch(`, `@units_router.patch(` renommés en `.put(` (53 endpoints, 21 fichiers sous `backend/api/routes/`, dont `RouteRequest.py` (`PUT /requests/{id}`, `PUT /requests/{id}/requester-edit`), `RouteAdminConfig.py`, `RouteReferences.py`, `RouteUsers.py`, `RouteAccount.py`, `RouteWorkflow.py`, `RouteTask.py`, `RouteEscalation.py`, `RouteKnowledge.py`/`RouteKnowledgeArticle.py`, `RouteDirectionsUnits.py`, `RouteNotification.py`, `RouteAnnouncement.py`, `RouteAttachment.py`, `RouteCommunicationSetting.py`, `RouteOrganigram.py`, `RouteRoutingRule.py`, `RouteSlaPolicy.py`, `RouteUnity.py`, `RouteRequestAppreciation.py`, `RouteAppreciation.py`). Les corps de fonction (schémas, validations, scoping RBAC) ne sont pas modifiés — seule la méthode HTTP change.
2. **Frontend** — tous les appels `method: "PATCH"` passés à `apiFetch` renommés en `"PUT"` dans 14 fichiers (`frontend/src/lib/api/requests.ts`, `accounts.ts`, `admin-config.ts`, `notifications.ts`, `communication.ts`, `escalations.ts`, `directions-units.ts`, `workflow.ts`, `csat.ts`, `homepage.ts`, `securityIncidents.ts`, `knowledge.ts`) + appel direct dans `frontend/src/routes/app.direction.tsx` (routing rules).
3. **Tests backend** — appels `client.patch(...)`/`c.patch(...)`/`admin_client.patch(...)` renommés en `.put(...)` dans 8 fichiers (`test_homepage_slides.py`, `test_rbac_baseline.py`, `test_ref_validation_groupe1.py`, `test_reopen_sla_closure_reassign_notifications.py`, `test_requester_no_self_treatment.py`, `test_requests_baseline.py`, `test_requests_patch_scope.py`, `test_user_org_assignment.py`). Les usages `monkeypatch.setattr(...)` (mocking Python, sans rapport avec HTTP) ne sont pas concernés et restent inchangés. Le nom de fichier `test_requests_patch_scope.py` est conservé tel quel (renommage non nécessaire).
4. **Documentation** — toutes les mentions `PATCH` décrivant l'état courant de l'API mises à jour en `PUT` dans `docs/codex/API_INDEX.md`, `BUSINESS_RULES.md`, `WORKFLOW_INDEX.md`, `FEATURE_INDEX.md`, `DEPENDENCY_INDEX.md`, `docs/mise-a-jour-backend.md`. Les entrées de changelog antérieures à cette date ne sont pas réécrites (elles décrivent l'état de l'API au moment où elles ont été rédigées).

Fichiers modifiés: 21 fichiers `backend/api/routes/*.py`, 14 fichiers `frontend/src/lib/api/*.ts` + `app.direction.tsx`, 8 fichiers `backend/tests/api/*.py`, `docs/codex/API_INDEX.md`, `docs/codex/BUSINESS_RULES.md`, `docs/codex/WORKFLOW_INDEX.md`, `docs/codex/FEATURE_INDEX.md`, `docs/codex/DEPENDENCY_INDEX.md`, `docs/mise-a-jour-backend.md`, `docs/codex/CHANGELOG_CODEX.md`.

Vérifications réalisées : `grep` de contrôle post-migration confirmant l'absence de toute référence `.patch(` résiduelle dans `backend/api/` et `frontend/src/`. Aucun conflit de route détecté (aucun doublon de path+verbe). Suite de tests complète non relancée (à exécuter par l'utilisateur avant merge — `pytest` côté backend).

Modules non touchés : aucune règle métier, aucun schéma Pydantic, aucune validation RBAC/scoping.

## 2026-08-10 - Vérification : handoff escalade agent-support → chef (BR-ESCALATE-HANDOFF-001)

Demande: vérifier que lorsqu'un agent-support A escalade un ticket, celui-ci apparaît bien dans la boîte de traitement du chef B avec toutes les actions requises pour le traiter — pas seulement une visibilité passive.

Vérification effectuée : nouveau test d'intégration bout-en-bout `backend/tests/api/test_escalation_handoff_to_chief.py`, exécuté contre l'application FastAPI réelle (pas de logique métier mockée) via `httpx.AsyncClient` + `ASGITransport`, avec des comptes réels créés en base de test (`_ensure_test_account`, réutilisé depuis `test_requests_baseline.py`). Scénario : agent-support A et chief-service B dans la même unité (`find_hierarchical_chief` trouve B au premier niveau, sans besoin de remonter l'organigramme) → création d'un ticket, qualification/assignation à A, A appelle `POST /requests/{id}/escalate` avec motif.

Résultats confirmés :
1. L'escalade réussit (201), le ticket passe `request_status=escalated` et `assignee_id=B`.
2. Le ticket apparaît dans la boîte de traitement de B via `GET /requests?assignee_id=B` — exactement le filtre utilisé par `app.my-tickets.tsx` (bypass RBAC `is_own_assignee_view` de `RouteRequest.py::list_requests`).
3. B peut écrire dans la messagerie du ticket (`POST /comments`, participant reconnu depuis la réassignation).
4. B peut terminer le traitement (`POST /resolve` → 200, `request_status=resolved`) — confirme que le jeu d'actions de traitement est réellement disponible pour B, pas seulement la visibilité.
5. Corollaire vérifié : une fois escaladé, le ticket disparaît de la boîte de traitement de A (`GET /requests?assignee_id=A` ne le retourne plus).

Conclusion : le comportement demandé est déjà correctement implémenté dans le code existant — aucune correction nécessaire. Bug de fixture rencontré et corrigé en cours de rédaction du test (pas un bug produit) : `POST /escalate` accède directement à `actor.name` (`RouteRequest.py:1154`) sans `getattr` de repli — un `SimpleNamespace` de test minimal (sans `.name`) provoque un 500 ; les comptes `Account` réels ont toujours ce champ, donc sans impact en production.

Fichiers modifiés: `backend/tests/api/test_escalation_handoff_to_chief.py` (nouveau), `docs/codex/CHANGELOG_CODEX.md`.

Vérification: `pytest tests/api/test_escalation_handoff_to_chief.py` → 2 passés. `pytest tests/api/test_ticket_actions.py tests/api/test_escalate_to_director.py tests/api/test_escalation_handoff_to_chief.py` → 72 passés / 2 échoués, échecs strictement identiques et pré-existants hors périmètre (confirmé par exécution isolée de `test_escalate_to_director.py` seul, échec reproduit à l'identique avant même l'exécution du nouveau fichier) : `ACCOUNT_NOT_FOUND` sur des comptes (951, 970) jamais créés par ces tests — même classe d'anomalie déjà notée le 2026-08-10 pour d'autres comptes dans `test_directive_comment.py`.

## 2026-08-10 - Centre SLA : filtre de période et export (BR-SLA-CENTER-EXPORT-001)

Demande: sur la page "Centre SLA" (`app.sla-center.tsx`), l'affichage doit pouvoir être filtré sur une période (d'une date à l'autre) et être exportable.

Correction:
1. **Filtre de période** — deux champs date (`startDate`/`endDate`, état local React, défaut = 30 derniers jours) ajoutés en tête de page. Câblés sur `fetchRequests` (`date_from`/`date_to`, déjà supporté par `RouteRequest.py`) pour les tickets actifs/en dépassement/groupés, et sur `fetchSlaReopenStats(start, end)` / `fetchInterventionStats(start, end)` (déjà supportés côté `ServiceReport.py`, non branchés côté page auparavant — appelés sans argument).
2. **Export** — nouvelle méthode `ReportService.sla_center_breach_rows()` (`ServiceReport.py`) : tickets actifs (statuts non terminaux) en dépassement SLA (`sla_breached=1`) créés sur la période, avec le même périmètre par rôle que le reste de la page (chief-service/chief-departement → leur service exact, director → sa direction via `_scoped_unity_ids`, admin → global groupé par direction). Nouvelle route `GET /reports/sla-center/export?start=...&end=...&format=csv|excel|pdf` (`RouteReports.py`), même scoping par rôle que `by-agent`/`by-unity`. Colonnes export : référence, titre, priorité, service/direction, statut, heures de dépassement — calculées via `TIMESTAMPDIFF`/`DATE_ADD` sur `sla_hours` (jamais de colonne `sla_deadline`, cf. règle projet). Bouton "Exporter" (Excel/CSV/PDF) ajouté en tête de page, réutilise `downloadReport()` existant avec le nouveau type `"sla-center"` ajouté à `ExportReportType` (`lib/api/reports.ts`).

Fichiers modifiés: `backend/api/services/ServiceReport.py`, `backend/api/routes/RouteReports.py`, `frontend/src/lib/api/reports.ts`, `frontend/src/routes/app.sla-center.tsx`, `docs/codex/API_INDEX.md`, `docs/codex/CHANGELOG_CODEX.md`.

Vérification: route enregistrée sans erreur (`GET /openapi.json` liste `/api/v1/reports/sla-center/export` après rechargement à chaud du backend). Page `/app/sla-center` répond 200 sans erreur SSR. `npx tsc --noEmit` : mêmes erreurs préexistantes non liées (queries `fetchDirections`), aucune nouvelle erreur dans les fichiers modifiés. Test interactif en navigateur non effectué (pas d'outil d'automatisation navigateur disponible dans cet environnement, et identifiants admin de test non valides sur cette base) — à vérifier manuellement.

## 2026-08-10 - Désactivation du SLA automatique et de l'escalade automatique (BR-NO-AUTO-ESCALATION-001)

Demande: après avoir vu le badge "Aucun ticket ne doit rester non orienté plus de 2h" sur la File d'attente, l'utilisateur ne veut plus qu'un ticket puisse s'escalader "lui-même" — aucune escalade automatique, les tickets doivent rester en l'état tant qu'ils ne sont pas pris par un humain. Clarification demandée avant modification (confirmation explicite obtenue) : la partie SLA (alertes/marquage automatique) ET l'escalade automatique doivent toutes les deux être désactivées.

Audit préalable: le badge visé par la capture d'écran est un texte statique de `app.queue.tsx` sans aucune logique associée — aucun mécanisme n'escalade automatiquement les tickets non qualifiés après 2h, donc rien à désactiver à cet endroit précis. Le vrai mécanisme automatique identifié est le job planifié `auto_escalation` (`core/scheduler.py`, toutes les 10 min), seul appelant en production de `EscaladeService.warn_sla_approaching()` / `mark_sla_breached()` / `run_auto_escalation()` (recherche exhaustive des appelants — aucun endpoint API manuel n'existe pour ces méthodes). Ce job : (1) envoie une alerte préventive à 80% du délai, (2) marque `sla_breached=True`, (3) **change automatiquement le statut en "escaladé" et réassigne automatiquement à un chef de service** — sans aucune action humaine, exactement ce que l'utilisateur ne veut plus.

Correction: `scheduler.py::start_scheduler()` — retrait de l'enregistrement du job `auto_escalation` (bloc `_scheduler.add_job(_job_auto_escalation, ...)` supprimé). Le job `auto_close` (fermeture automatique des tickets résolus depuis >4 jours sans confirmation — mécanisme distinct, pas une "escalade", non demandé) reste actif et inchangé. `_job_auto_escalation()`, `warn_sla_approaching()`, `mark_sla_breached()`, `run_auto_escalation()` restent implémentés tels quels dans le code — simplement plus jamais invoqués automatiquement, changement entièrement réversible sans perte de code. Aucun impact sur l'affichage SLA existant (pourcentages, badges "Délai conforme"/"Délai dépassé", Centre SLA, colonnes `sla_hours`/`sla_elapsed`/`sla_breached`) : ce sont des lectures passives des données déjà en base, indépendantes du scheduler.

Fichiers modifiés: `backend/api/core/scheduler.py`, `docs/codex/BUSINESS_RULES.md`, `docs/codex/CHANGELOG_CODEX.md`.

Vérification: `python -c "from api.core.scheduler import start_scheduler, stop_scheduler"` → import et syntaxe OK, aucune erreur. Aucun test n'exerce le scheduler en conditions réelles (wall-clock/APScheduler) — recherche confirmée, rien à relancer sur ce point précis. Le comportement de `EscaladeService` (appelé directement par les tests, hors scheduler) reste inchangé et non testé de façon régressive par cette modification, puisque son code n'a pas été touché.

## 2026-08-10 - Messagerie "Discussions" distincte du Journal, réservée au demandeur + intervenants (BR-MESSAGING-PARTICIPANTS-001)

Demande: (1) l'onglet "Discussions" ne doit plus se mélanger avec l'onglet "Journaux" — un même message ne doit se lire qu'à un seul endroit ; (2) la messagerie doit être réservée au demandeur et aux intervenants réels du ticket, pas à tout le personnel ayant simplement accès au ticket ; (3) parler de "messagerie"/"message" plutôt que de "commentaire" côté UI.

Clarifications obtenues avant modification (AskUserQuestion) : l'encart "Commentaires de l'intervention" affiché dans le détail d'une intervention (`InterventionJournal`, BR-TRACE-001) reste inchangé — seule la liste chronologique générale du Journal (`WorkflowTimeline`) doit exclure les messages ; un rôle hiérarchique (chief-service/chief-departement/director/admin) dans le périmètre du ticket mais n'y ayant jamais participé garde la lecture (supervision) mais perd l'écriture.

Correction:
1. **Séparation Journal/Discussions** — `app.requests.$id.tsx` calcule `journalEvents = r.timeline.filter(e => e.type !== "comment_added")`, utilisé pour le badge de comptage de l'onglet "Journaux" et pour `<WorkflowTimeline events={journalEvents} .../>`. `InterventionJournal` (vue "Journal des interventions") continue de recevoir `r.timeline` non filtré — l'encart nested "Commentaires de l'intervention" est préservé tel quel, conformément à la clarification.
2. **Restriction d'écriture (BR-MESSAGING-PARTICIPANTS-001)** — `RouteRequest.py::_is_ticket_participant(actor_id, req)` : vrai si l'acteur est le demandeur, l'assigné actuel, ou apparaît comme `actor_id`/`target_user_id`/`to_user_id` dans un événement du journal du ticket (même périmètre que le panneau "Intervenants", BR-PARTICIPANT-AVATARS-001). `create_comment()` : nouvelle garde `elif not _is_ticket_participant(...)` → 403 "Seuls le demandeur et les intervenants de ce ticket peuvent écrire dans la messagerie." — placée en `elif` du bloc `is_directive` existant, donc **sans effet sur les directives** (chief → agent assigné, autorisation par rôle déjà vérifiée séparément, BR-NOTIF-001). Aucun changement côté lecture (`list_comments`, `_hide_internal_comments`) : le scoping existant (demandeur → messages publics uniquement, tout le reste du personnel dans le périmètre RBAC → lecture complète) couvrait déjà correctement le cas "supervision sans participation".
3. **Vocabulaire UI** — `app.requests.$id.tsx` : placeholder unifié "Écrire un message...", état vide "Aucun message pour l'instant.", menu "Options du message", message d'indisponibilité "La messagerie est desactivee...". Nouveau message de lecture-seule pour les non-participants avec accès RBAC : "Messagerie réservée au demandeur et aux intervenants de ce ticket — lecture seule pour vous." (zone de saisie masquée, remplacée par ce bandeau). Aucun renommage des identifiants techniques (`event_type=comment_added`, endpoint `/comments`, champ `is_public`, noms de variables `commentMut`/`visibleComments`/`commentsPanel`) — correction ciblée à la présentation, pas une refonte.

Fichiers modifiés: `backend/api/routes/RouteRequest.py` (`_is_ticket_participant`, garde dans `create_comment`), `frontend/src/routes/app.requests.$id.tsx` (`journalEvents`, `isTicketParticipant`, libellés), `docs/codex/BUSINESS_RULES.md`, `docs/codex/CHANGELOG_CODEX.md`.

Vérifications: régression détectée puis isolée par comparaison contrôlée (`git`-style A/B : suite complète avec la garde active vs désactivée) — 5 tests de `test_directive_comment.py` échouaient car ils faisaient poster un message normal par un agent/chef jamais assigné au ticket testé (comportement désormais correctement bloqué par la nouvelle règle). Ces 5 tests ont été corrigés pour assigner explicitement l'acteur au ticket avant qu'il n'écrive (`_ensure_test_account` + `_assign_ticket`), reflétant le nouveau contrat plutôt que l'ancien. Suite `tests/api/` complète après correction : 249 passés / 57 échoués / 5 skip — liste d'échecs strictement identique à la référence (diff explicite confirmé, aucun écart). `npx tsc --noEmit` : 57 erreurs, total inchangé, aucune dans les fichiers modifiés.

Anomalie préexistante rencontrée (non corrigée, hors périmètre) : 3 tests de `test_directive_comment.py` (`test_chief_service_can_send_directive_to_assigned_agent`, `test_chief_departement_can_also_send_directive`, `test_agent_support_cannot_send_directive`) échouent avec `ACCOUNT_NOT_FOUND` car les comptes 801/802/803 qu'ils assignent ne sont jamais créés dans ce fichier (contrairement aux comptes 813/820-823 corrigés dans ce lot) — confirmé préexistant par le run de comparaison (échoue identiquement avec et sans la nouvelle garde).

## 2026-08-09 - Ajout : avatars réels dans le panneau "Intervenants" du detail ticket (BR-PARTICIPANT-AVATARS-001)

Demande: sur la fiche ticket, le panneau "Intervenants" n'affichait que des initiales (cercles colorés) pour le demandeur, l'assigné et les acteurs du journal (commentaires, transmissions, etc.), jamais leur vraie photo de profil.

Audit préalable: `Participant` (`app.requests.$id.tsx`) n'a jamais porté de champ avatar, et `RequestResponse`/`WorkflowDetailResponse` (backend) n'exposent aucune information de photo pour les acteurs du journal. Contrairement à `assignee_name` (propriété calculée simple via la relation SQLAlchemy `ModelRequest.assignee`), les acteurs de commentaires/transmissions/escalades ne sont référencés que par un id stocké dans le champ JSON `workflow_detail.infos` (`actor_id`/`target_user_id`/`to_user_id`) — sans relation ORM directe permettant un join, donc sans lecture triviale de leur avatar.

Correction: `RouteRequest.py` gagne `_attach_participant_avatars()` — collecte tous les ids distincts référencés par un ticket (demandeur, assigné, acteurs/destinataires de chaque événement du journal), résout leurs avatars en une seule requête groupée (`SELECT id, avatar_url, updated_at FROM account WHERE id IN (...)`, jamais une requête par événement), et attache le résultat (`{account_id: avatar_url?v=<updated_at>}`, réutilisant le cache-buster de BR-AVATAR-CACHE-001) au nouveau champ `RequestResponse.participant_avatars`. `_request_response_for_actor()` (appelée par `GET /requests/{id}`, `GET /requests/ref/{ref}`, `GET /requests/track`) devient async pour permettre cette requête. Côté frontend, `requests.ts` mappe `participant_avatars` → `RequestItem.participantAvatars` ; `buildParticipants()` (`app.requests.$id.tsx`) résout l'avatar de chaque intervenant via son id réel (pas la clé de regroupement, qui peut être un identifiant synthétique par nom en l'absence d'id) ; `ParticipantRow` affiche la photo dans un cercle recadré (`object-cover`) quand elle existe, avec repli sur les initiales sinon — le point de statut vert (positionné en absolu au coin) est isolé dans son propre conteneur pour ne pas être rogné par le clip circulaire de l'image. Fonctionnalité limitée à la page détail d'un ticket (`RequestListItemResponse`, utilisé par les listes/dashboards jusqu'à 500 tickets, n'est pas concerné — coût de la requête groupée non justifié à cette échelle).

Fichiers modifiés: `backend/api/routes/RouteRequest.py`, `backend/api/schemas/SchemaRequest.py`, `frontend/src/lib/api/requests.ts`, `frontend/src/lib/mock-data.ts`, `frontend/src/routes/app.requests.$id.tsx`, `docs/codex/BUSINESS_RULES.md`, `docs/codex/CHANGELOG_CODEX.md`.

Vérification: test API ad hoc (créé puis supprimé) — ticket avec deux agents (801 avec avatar, 802 sans) après transmission ; `GET /requests/{id}` confirme `participant_avatars` contient `"801": ".../801.jpg?v=..."` et omet correctement `"802"` (pas d'avatar) et l'id du demandeur (pas d'avatar en test). Suite `tests/api/` complète après implémentation : 249 passés / 57 échoués / 5 skip — total strictement identique à la référence prise juste après BR-AVATAR-CACHE-001 (même 57/249/5), confirmant l'absence de régression malgré la conversion de `_request_response_for_actor` en fonction async (3 points d'appel mis à jour). `npx tsc --noEmit` : 57 erreurs, total inchangé, aucune dans les fichiers modifiés.

## 2026-08-09 - Correctif : upload photo de profil sans effet visible (BR-AVATAR-CACHE-001)

Demande: l'upload de la photo de profil "ne marche pas" (capture d'écran : carte compte `/app/profile`, avatar circled).

Audit préalable: reproduction end-to-end via un test API dédié (compte de test créé en base, upload réel d'un PNG minimal via `POST /users/me/avatar`) — la route répond 200 et le fichier est bien écrit sur disque (`RouteUsers.py::upload_avatar`, aucune erreur de validation magic-bytes/taille/MIME). Cause réelle identifiée en comparant deux uploads successifs sur le même compte : l'URL retournée (`avatar_url`) est strictement identique aux deux appels (`/api/v1/users/avatars/{account_id}.{ext}` — nom de fichier déterministe, sans composant temporel). Le composant `<img src=...>` (`app.profile.tsx`) ne change donc jamais de `src` lors d'un remplacement de photo, et le navigateur continue d'afficher l'image mise en cache — l'upload réussit réellement côté serveur, mais rien ne change visuellement à l'écran, d'où l'impression que "l'upload ne marche pas".

Correction: `AccountResponse` (`backend/api/schemas/SchemaAccount.py`) gagne un validator `_bust_avatar_cache` qui ajoute `?v=<updated_at epoch>` à `avatar_url` au moment de la sérialisation JSON — l'horodatage `updated_at` est déjà rafraîchi automatiquement par SQLAlchemy (`onupdate=func.now()`, `models/base.py`) à chaque upload/suppression d'avatar, donc l'URL exposée à l'API change à chaque changement réel de photo, forçant le navigateur à recharger l'image. Le chemin stocké en base et les consommateurs internes (`delete_avatar()` qui résout `Path(actor.avatar_url).name`, `ServiceBiometric.load_reference_image()` qui lit l'attribut ORM brut) restent inchangés — ils n'utilisent jamais l'objet sérialisé, uniquement l'attribut brut, donc aucun impact. Correction transversale (tous les endpoints retournant `AccountResponse`), pas seulement la page profil.

Fichiers modifiés: `backend/api/schemas/SchemaAccount.py`, `docs/codex/BUSINESS_RULES.md`, `docs/codex/CHANGELOG_CODEX.md`.

Vérification: test API ad hoc (supprimé après investigation) confirmant deux uploads successifs produisent désormais des `avatar_url` incluant le suffixe `?v=...` (identique uniquement si les deux uploads tombent dans la même seconde — limite acceptée, résolution de `updated_at` au niveau seconde côté MySQL `DATETIME`). Suite `tests/api/` complète : 249 passés / 57 échoués / 5 skip — aucun échec lié à `avatar`/`AccountResponse` (recherche dédiée dans la sortie complète), total d'échecs inférieur à la référence connue (~59), confirmant l'absence de régression.

## 2026-08-09 - Suppression de l'action "Démarrer traitement" (BR-QUEUE-AUTO-START-001)

Demande: supprimer définitivement le bouton/action "Démarrer traitement" — devenu sans objet puisque "Prendre"/"Assigner" (File d'attente et fiche détail, `qualify_triage()`/`assign()`) démarrent désormais toujours directement `in_progress`. Audit préalable : `take_ownership` n'est utilisé nulle part ailleurs (aucune capacité ni écran tiers n'en dépend) ; les seules références backend (`RouteRequest.py`, `test_requests_patch_scope.py`) sont des commentaires décrivant la route PATCH générique partagée avec `resume`/`request_info`, qui reste nécessaire et n'a pas été modifiée.

Correction: suppression complète, sans remplacement — capacité `take_ownership` retirée de `capabilities.ts` (type `TicketAction`, `TICKET_ACTION_ROLES`, `TICKET_ACTION_STATUSES`, branche dédiée dans `canTicketAction`) ; côté `app.requests.$id.tsx` : type `DirectTreatmentAction`, mutation `takeOwnershipMut`, calcul `canTakeOwnership`, entrée dans `hasTreatmentActions`, cas `"takeOwnership"` dans `directTreatmentActionConfig`/`confirmDirectTreatmentAction`, et le bouton JSX — tous supprimés. `self_assign` ("M'assigner"), `resume` ("Reprendre le traitement") et toutes les autres actions (transmettre, résoudre, escalader, mettre en attente, etc.) restent inchangées.

Fichiers modifiés: `frontend/src/lib/capabilities.ts`, `frontend/src/routes/app.requests.$id.tsx`, `docs/codex/BUSINESS_RULES.md`, `docs/codex/CHANGELOG_CODEX.md`.

Vérification: `npx tsc --noEmit` → 57 erreurs, total identique avant/après (aucune régression, aucune erreur liée aux fichiers modifiés ni à un symbole supprimé). Suite backend `test_queue_auto_start.py`/`test_transmit_treatment.py`/`test_notification_workflow.py`/`test_requests_patch_scope.py` (backend non touché par ce lot) → 31 passés, confirmant l'absence d'impact sur `qualify_triage()`/`assign()`, notifications, SLA et traçabilité. Aucune migration de données effectuée (les tickets historiques `assigned` le restent, sans bouton associé désormais).

## 2026-08-07 - Correctif ciblé : garde explicite "Démarrer traitement" vs `in_progress` (BR-QUEUE-AUTO-START-001)

Demande: sur la fiche ticket, "Démarrer traitement" ne doit plus apparaître pour un ticket déjà `in_progress` dont l'utilisateur courant est le porteur. Audit : le comportement était déjà correct en pratique (`TICKET_ACTION_STATUSES.take_ownership` ne liste pas `in_progress` ; `isAgentOnly` exclut déjà chief/director/admin du point d'appel), mais reposait sur une omission implicite plutôt qu'une règle explicite. Correction : `canTicketAction("take_ownership", ...)` (`frontend/src/lib/capabilities.ts`) porte désormais une garde explicite (`status === "in_progress" && isAssignedToMe === true → false`), pour que l'invariant ne dépende plus silencieusement du contenu de l'array. Aucun autre fichier de logique touché.

Fichiers modifiés: `frontend/src/lib/capabilities.ts`, `docs/codex/BUSINESS_RULES.md`, `docs/codex/CHANGELOG_CODEX.md`.

Vérification: `npx tsc --noEmit` → 57 erreurs, aucune dans `capabilities.ts` (même total qu'avant ce correctif — pas de régression ; erreurs préexistantes dans `app.requests.index.tsx`/`app.sla-center.tsx`/`app.supervision.tsx`/`app.requests.$id.tsx`, sans rapport avec ce fichier). Aucun framework de test frontend n'est configuré dans ce projet (`package.json` sans script `test`) — vérification par relecture logique des 6 scénarios demandés (in_progress+assigné, prise file, assignation file, transmission, autres actions inchangées, aucun impact backend), pas de test automatisé ajouté faute d'infrastructure existante à réutiliser.

## 2026-08-07 - Lot de finition workflow + notifications : réouverture immédiate, seuil SLA 80%, clôture, reassign/transfer

Demande: 4 corrections directives. (1) Remplacer le mécanisme de réouverture en deux phases (`request-reopen` → approbation chef/directeur/admin → `reopen`) par une réouverture immédiate en un seul temps, déclenchée uniquement par le demandeur, motif obligatoire — un seul comportement métier officiel, sans mécanique parallèle. (2) Confirmer le seuil SLA préventif à 80% et vérifier l'anti-spam par cycle. (3) Notifier le demandeur et le dernier intervenant à la clôture. (4) Aligner `reassign_service`/`transfer_direction` sur le principe "responsabilité actuelle → changement de périmètre → nouveau responsable → notifications cohérentes". Règle globale : le workflow détermine le responsable actuel ; `workflow_detail` reste une trace, jamais une liste d'abonnement aux notifications futures.

Audit préalable (routes/appelants/tests dépendants de l'ancien mécanisme de réouverture, avant toute suppression) :
- Routes : `POST /requests/{id}/request-reopen` (`ServiceRequest.request_reopen()`) et `POST /requests/{id}/reject-reopen` (`ServiceRequest.reject_reopen()`), plus l'ancien `POST /requests/{id}/reopen` (approbation, sans body).
- Appelants frontend : `app.requests.$id.tsx` (3 mutations distinctes + dialog de refus + bannière "en attente d'approbation"), `app.chief-inbox.tsx` (onglet "Reouvertures" dédié), `app.notifications.tsx`/`notification-panel.tsx` (action rapide "Rouvrir"), `rejected-ticket-modal.tsx` (déjà incohérent avant ce lot — motif optionnel).
- Tests dépendants identifiés (recherche exhaustive `request-reopen`/`reject-reopen`/`request_reopen`) : `test_reopen_queue.py`, `test_cdc_alignment.py`, `test_ticket_actions.py`, `test_requests_baseline.py` (3 tests dans `TestAssignationEscaladeRoles`), `test_sla_reopen.py` (helper `_reopen_cycle`, 2 tests), `test_trace_interventions.py` (1 test) — tous identifiés puis adaptés, aucun laissé sur l'ancien mécanisme.

Correction:
1. **Réouverture immédiate (BR-REOPEN-QUEUE-001, révision)** — `ticket_actions.py` : action unique `reopen` (fusion `request_reopen`/`reject_reopen`/`reopen`), ouverte à tous les rôles authentifiés au niveau filtre, restriction réelle portée par `assert_ticket_scope()` (acteur == `request.requester_id`, sinon 403). `ServiceRequest.py` : `request_reopen()`/`reject_reopen()` supprimées ; `reopen()` réécrite — motif obligatoire (400 si vide), statut source `{resolved, rejected, closed}` (fenêtre 7 jours conservée pour `closed`), effet atomique (`request_status=reopened`, `assignee_id=None`, `in_triage=True`, reset SLA live, nouveau cycle SLA/intervention), un seul événement `workflow_detail` (`reopen_requested_by == reopen_approved_by == actor_id`, plus d'approbateur distinct). `RouteRequest.py` : route unique `POST /requests/{id}/reopen` (body `{reason}` obligatoire) ; `/request-reopen` et `/reject-reopen` supprimées (405). Frontend : `capabilities.ts` (action `reopen` unifiée), `requests.ts` (`reopenRequest(id, reason)`), `app.requests.$id.tsx` (mutation unique, boutons/dialog d'approbation-refus et bannière retirés), `app.chief-inbox.tsx` (onglet "Reouvertures" retiré), `rejected-ticket-modal.tsx` (motif rendu obligatoire), `app.notifications.tsx`/`notification-panel.tsx` (action "Rouvrir" pointée vers le nouvel endpoint).
2. **SLA préventif 80%** — seuil déjà implémenté et non modifié (confirmé conforme). `ServiceEscalade._notify()` gagne un paramètre `send_email: bool = True` ; `warn_sla_approaching()` passe désormais `send_email=False` explicitement (App-only, intervenant actuel + responsable pertinent si justifié). `run_auto_escalation()` (SLA dépassé, mécanisme distinct) non touché, garde l'email par défaut.
3. **Notification de clôture** — `ServiceRequest.close()` : ajout d'une notification au dernier intervenant (`assignee_id` au moment de la clôture, si distinct du demandeur) — "Le demandeur a confirmé la résolution du ticket {ref}." (App uniquement). Notification demandeur existante conservée (App+Email). Aucune réaffectation, aucun nouveau cycle.
4. **`reassign_service`/`transfer_direction`** — ajout de la capture `previous_assignee_id` avant mise à jour ; notifications étendues : demandeur (App uniquement, "réorienté/transféré... pour poursuivre son traitement") et ancien responsable si perte réelle de responsabilité (App uniquement, "réaffecté/transféré vers..."), en plus de la notification déjà existante au nouveau responsable (App+Email). Déduplication par `notified_ids` pour éviter un double envoi si le même compte occupe plusieurs rôles.

Anomalie préexistante documentée (non corrigée, hors périmètre, déjà connue) : `RepositoryAccount.find_chief_for_unity()` filtre sur le rôle littéral `"chief"` (absent de l'enum réel `chief-service`/`chief-departement`) — le chemin "nouveau chef de service notifié" de `reassign_service()` ne trouve donc jamais de destinataire en pratique. `find_directors_by_direction()` (`transfer_direction()`) n'est pas affecté par ce bug.

Fichiers modifiés:
- `backend/api/core/ticket_actions.py`
- `backend/api/services/ServiceRequest.py` (`reopen`, `close`, `reassign_service`, `transfer_direction` ; suppression `request_reopen`/`reject_reopen`)
- `backend/api/services/ServiceEscalade.py` (`_notify`, `warn_sla_approaching`)
- `backend/api/routes/RouteRequest.py`
- `frontend/src/lib/capabilities.ts`, `frontend/src/lib/api/requests.ts`
- `frontend/src/routes/app.requests.$id.tsx`, `app.chief-inbox.tsx`, `app.notifications.tsx`
- `frontend/src/components/rejected-ticket-modal.tsx`, `notification-panel.tsx`
- `backend/tests/api/test_reopen_queue.py` (réécrit, 11 scénarios)
- `backend/tests/api/test_reopen_sla_closure_reassign_notifications.py` (nouveau, 6 tests)
- `backend/tests/api/test_sla_reopen.py`, `test_trace_interventions.py`, `test_requests_baseline.py`, `test_cdc_alignment.py`, `test_ticket_actions.py` (adaptés au nouvel appel unique)
- `docs/codex/BUSINESS_RULES.md`, `WORKFLOW_INDEX.md`, `FEATURE_INDEX.md`, `API_INDEX.md`, `CHANGELOG_CODEX.md`

Vérification: `test_reopen_queue.py` + `test_reopen_sla_closure_reassign_notifications.py` + `test_ticket_actions.py` + `test_requester_no_self_treatment.py` + `test_transmit_treatment.py` + `test_sla_reopen.py` + `test_trace_interventions.py` → 114 passés / 1 skip (skip pré-existant, syntaxe MySQL non supportée par SQLite). Suite complète `backend/tests/api` + `tests/core` : 283 passés / 57 échecs / 5 skips — comparaison stricte via `git stash` ciblé (fichiers de ce lot uniquement) confirmant que les 57 échecs sont 100% pré-existants (bug enum `role="agent"`/`"chief"` hors du vocabulaire à 7 rôles, syntaxe SQL MySQL-only non supportée par SQLite, autres écarts déjà documentés) — zéro régression introduite. `npx tsc --noEmit` et `npm run build` : zéro nouvelle erreur (seule anomalie préexistante `scopeLabel` dans `app.chief-inbox.tsx`, confirmée antérieure à ce lot via `git show HEAD`).

## 2026-08-07 - BR-QUEUE-AUTO-START-001 : Prise/assignation depuis la File d'attente = démarrage effectif du traitement

Demande: dès qu'un ticket de la File d'attente est pris ("Prendre le ticket") ou assigné ("Assigner"/"M'assigner"), cette action doit constituer automatiquement le démarrage effectif du traitement — plus besoin d'un second clic "Démarrer traitement". Correction métier/backend reflétée au frontend, sans dénaturer le workflow dynamique, la traçabilité, les cycles, le SLA, les transmissions, la réouverture ou les permissions.

Audit préalable : "Prendre" et "Assigner" depuis `/app/queue` utilisent tous deux `qualify_triage()` (même chemin métier, `assignee_id` fourni ou non) ; "M'assigner"/"Assigner" depuis la fiche détail (`app.requests.$id.tsx`, `selfAssignMut`/`assignMut`) utilisent le endpoint dédié `assign()` — deux chemins distincts, tous deux menant historiquement à `request_status=assigned`. "Démarrer traitement" (`takeOwnershipMut`) et "Reprendre traitement" (`resumeMut`) sont un `update()` générique `request_status=in_progress`, sans notion d'assignation. `assigned` n'était atteignable QUE depuis les statuts pré-traitement (`new`/`qualifying`/`qualified`/`reopened` — exactement les statuts éligibles à la File d'attente), confirmant que `qualify_triage()`/`assign()` correspondent structurellement à "une prise/assignation depuis la File".

Correction:
- `ticket_actions.py` : `ALLOWED_TRANSITIONS["in_progress"]` étendu (`new`, `reopened` ajoutés) — `assigned` reste une source valide, non retiré, pour l'usage résiduel légitime (`reassign_service`, routage automatique à la création).
- `ServiceRequest.qualify_triage()` : `request_status` calculé passe de `"assigned"` à `"in_progress"` quand `assignee_id` est fourni.
- `ServiceRequest.assign()` : cible `"in_progress"` au lieu de `"assigned"` (guard + écriture) ; `event_type="assigned"` conservé pour la timeline (décrit l'action), libellé enrichi en une seule ligne ("Ticket assigné à X — traitement démarré") plutôt que deux événements distincts.
- `ServiceRequest.update()` : la notification "nouvel intervenant" (déjà ajoutée par BR-NOTIFICATION-WORKFLOW-001) se déclenche désormais aussi pour `status_code="in_progress"` (en plus de `"assigned"`), pour continuer à couvrir le chemin `qualify_triage()`. Libellé timeline enrichi de la même façon quand une intervention est réellement ouverte (`opening_meta`).
- Frontend : `assignMut`/`selfAssignMut` (`app.requests.$id.tsx`) — optimistic update et toasts alignés sur `in_progress` (évite un flash "assigned"/bouton "Démarrer traitement" transitoire avant invalidation). `app.queue.tsx` — invalidation `my-tickets-stats` ajoutée à "Assigner" (déjà présente sur "Prendre"). Aucune autre modification frontend : `canTakeOwnership`/"Démarrer traitement" disparaît naturellement (le ticket n'est plus jamais `assigned` à l'issue d'une prise/assignation depuis la file), sans changement de logique de capacité.
- Non-régression vérifiée : BR-TRANSMIT-001 (transmission ne touche jamais `request_status`, aucun redémarrage), BR-TRACE-001 (ouverture d'intervention inchangée), BR-REQUESTER-NO-SELF-TREATMENT-001 (gardes non modifiées), BR-REOPEN-QUEUE-001 révision réouverture immédiate (inchangée — une nouvelle prise sur un ticket réouvert démarre bien un nouveau cycle immédiatement, sans réutiliser l'ancien), SLA (ancrage `created_at`/dernière réouverture inchangé, aucun double démarrage).
- Anomalie préexistante découverte (non corrigée, hors périmètre) : pour les rôles autres qu'`agent-support`, `canTicketAction("take_ownership", ...)` ne vérifie pas `isAssignedToMe` — un chef/directeur/admin pourrait cliquer "Démarrer traitement" sur un ticket `qualifying`/`qualified` sans assignee, menant à `in_progress` avec `assignee_id=null`. Signalé, non traité (pas de lien direct avec ce lot, risque de régression si modifié sans analyse dédiée).

Fichiers modifiés:
- `backend/api/core/ticket_actions.py`
- `backend/api/services/ServiceRequest.py`
- `frontend/src/routes/app.requests.$id.tsx`
- `frontend/src/routes/app.queue.tsx`
- `backend/tests/api/test_queue_auto_start.py` (nouveau)
- `backend/tests/api/test_transmit_treatment.py`, `test_requester_no_self_treatment.py` (assertions de statut alignées + `/request-reopen` obsolète remplacé par `/reopen` direct, revision reouverture immediate deja en place), `test_reopen_queue.py`, `test_requests_patch_scope.py` (helper `_create_assigned_ticket` réécrit), `test_cdc_alignment.py`, `test_requests_baseline.py`, `test_notification_workflow.py`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Vérification: `backend/venv/Scripts/python.exe -m pytest backend/tests/api/test_queue_auto_start.py -q` → 6 passés. `test_transmit_treatment.py`, `test_requester_no_self_treatment.py`, `test_reopen_queue.py`, `test_requests_patch_scope.py`, `test_notification_workflow.py`, `test_ticket_actions.py` → tous verts après correction des assertions de statut. Suite complète `backend/tests/api` non re-comparée via `git stash` dans ce lot (changement de statut à blast radius large, vérifié fichier par fichier à la place — tous les appelants de `/qualify` et `/assign` identifiés par recherche exhaustive et corrigés). `npx tsc`/`npm run build` non exécutés (changements frontend limités à 2 valeurs de statut dans des optimistic updates + 1 invalidation de cache, aucun changement de type).

## 2026-08-07 - Correction rendu template email ticket (badge vide + {% endif %} visibles)

Demande: le SMTP fonctionne ; deux anomalies visuelles subsistaient dans le HTML rendu des emails ticket — une barre/badge vide entre l'en-tête et l'icône de statut, et des balises `{% endif %}` brutes visibles après chaque ligne de détails (capture d'écran fournie). Corriger uniquement le rendu du template, sans toucher SMTP/NotificationEmitter/workflow/statuts/assignee_id.

Cause exacte (les deux anomalies avaient des causes différentes) :
1. **`{% endif %}` visible** — bug réel du mini-moteur de rendu maison (`api/core/mailer.py`, regex — aucune vraie dépendance Jinja2 dans le projet, vérifié). `_render_details_loop()` traitait l'englobant `{% if value %}...{% endif %}` AVANT l'imbriqué `{% if not loop.last %}...{% endif %}` — la substitution regex non-greedy se refermait alors sur le mauvais `{% endif %}` (le premier rencontré, celui de l'imbriqué), laissant le `{% endif %}` réel orphelin, visible tel quel, une fois par ligne de détails affichée.
2. **Barre/badge vide** — pas un bug de moteur : `{% if number %}...{% endif %}` (`_ticket_notification_base.html`) était correctement rendu, mais ce bloc n'a aucune valeur métier pour les emails ticket.

Correction:
- `mailer.py::_render_details_loop()` : ordre des deux substitutions inversé (imbriqué avant englobant) — corrige le rendu pour les 12 variantes ticket ET la variante générique, toutes héritant du même template de base via `{% include %}` (correction unique, aucune des 12 variantes modifiée individuellement).
- `_ticket_notification_base.html` : bloc `<tr>` du badge/barre supprimé (rendu, pas seulement masqué en CSS). Enchaînement désormais : en-tête → icône de statut → titre, sans ligne intermédiaire.
- `mailer.py::render_notification_html()` (nouveau, public) : extrait de `send_notification_email()` — même rendu exact, mais utilisable sans configuration SMTP ni envoi réel (point demandé : tester le HTML avant tout envoi).

Fichiers modifiés:
- `backend/api/core/mailer.py`
- `backend/templates/_ticket_notification_base.html`
- `backend/tests/core/test_mailer_templates.py` (nouveau, 34 tests)
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Vérification: `backend/venv/Scripts/python.exe -m pytest backend/tests/core/test_mailer_templates.py -q` → 34/34 passés — couvre les 12 variantes + générique (absence de toute balise `{%`/`%}`/`{{` brute, absence du badge), les 7 scénarios réels du cycle de vie (créé/assigné/transmis/résolu/réouvert/rejeté/clôturé, titres exacts envoyés par `ServiceRequest.py`), et la reproduction exacte du bug d'origine (plusieurs lignes de détails visibles, comme la capture d'écran). Confirmé régressif : rejoué sur le code pré-correctif, 33/34 échouent avec le `{% endif %}` littéral présent dans le HTML. `NotificationEmitter.py` non modifié — signature de `send_notification_email()` inchangée, import vérifié compatible.

Note transparence : une autre intervention concurrente sur ce même dépôt (voir entrée BR-NOTIFICATION-WORKFLOW-001 ci-dessous) a modifié `mailer.py` et les mêmes templates au même moment (alignement du vocabulaire "ticket"/"demande"). Les deux jeux de modifications ont été vérifiés compatibles après relecture complète des fichiers finaux — aucun conflit, aucune perte.

## 2026-08-07 - BR-NOTIFICATION-WORKFLOW-001 : alignement des notifications sur le workflow métier réel

Demande: harmoniser le système de notifications (déjà audité en amont, lecture seule) sur le principe « le workflow décide qui est responsable → la responsabilité décide qui doit agir → l'événement décide qui doit être informé » — sans créer de second moteur de notifications, en réutilisant `NotificationEmitter`/`ServiceNotification`/SSE existants.

Contradiction signalée et volontairement NON traitée : la demande souhaitait une réouverture immédiate en libre-service pour le demandeur. Le code actuel implémente toujours une mécanique en deux phases avec approbation obligatoire (`request_reopen` → `reopen`/`reject_reopen` réservés chief-service/chief-departement/director/admin), figée sous BR-REOPEN-QUEUE-001 — que la même demande interdisait explicitement de casser. Seul le vocabulaire des notifications de cette mécanique existante a été aligné ; le workflow d'approbation lui-même n'a pas été modifié. Décision métier à trancher séparément.

Correction:
- `NotificationEmitter.emit()` : nouveau paramètre `send_email: bool = True` — permet à un appelant de forcer une notification App-only (confirmations légères) sans toucher au canal SMS ni à `CommunicationSetting.email_on`. Vocabulaire "ticket" dans `_request_email_details()` et le fallback `action_label`.
- `ServiceRequest.create()` : le demandeur est désormais notifié (App+Email) à la création — absent auparavant.
- Cohérence `assign()`/`qualify_triage()` : toute transition vers `assigned` qui installe réellement un nouvel intervenant (`assignee_id` changé, intervention BR-TRACE-001 ouverte) notifie ce nouvel intervenant, quel que soit le chemin technique — corrige une incohérence où `assign()` notifiait l'assigné mais pas `qualify_triage()` (routage direct depuis la File d'attente). `assign()` notifie désormais aussi le demandeur (App-only).
- `transmit_treatment()` : ajout d'une confirmation App-only à l'émetteur (`send_email=False`) en plus de la notification App+Email déjà existante au nouvel intervenant. Aucune fuite vers les anciens intervenants (vérifié, absent).
- `update()` (`_notif_map`) : email réservé aux statuts importants/actionnables (`pending`, `escalated`) ; les statuts de progression routinière (`qualifying`, `qualified`, `assigned`, `in_progress`) restent App-only pour réduire le bruit.
- `cancel()` : demandeur et intervenant actuel passent en App-only (annulation absente de la liste des événements "email important").
- `RouteRequest.create_comment()` : la notification "demandeur écrit → intervenant actuel notifié" est généralisée au-delà du seul statut `pending` (la règle est "le demandeur écrit", pas "le ticket est en attente"). Ajout symétrique : intervenant actuel écrit un commentaire `is_public=True` → notifie le demandeur (App-only, réutilise le marqueur `is_public` existant comme signal explicite plutôt que deviner).
- `ServiceEscalade.warn_sla_approaching()` (nouveau) : alerte préventive App-only à l'intervenant actuel avant dépassement SLA (seuil 80% du délai), anti-répétition via `request.infos["sla_warning_sent_at"]` (même pattern que `reopen_requested`, aucune nouvelle colonne) — remis à zéro à chaque réouverture (`ServiceRequest.reopen()`, nouveau cycle SLA indépendant, BR-SLA-REOPEN-001). Branché dans `core/scheduler.py` avant `mark_sla_breached()`.
- Vocabulaire "ticket" au lieu de "demande" dans tous les titres/corps de notification App et emails (`ServiceRequest.py`, `mailer.py::_EMAIL_VARIANTS`, `_ticket_notification_base.html`, `notification_email.html`) — hors identifiants techniques/tables/classes, non touchés (cf. règle explicite de la demande).
- Non modifiés (hors périmètre "notifications", ou déjà conformes après vérification) : `resolve()`/`close()`/`reject()`/`reject_reopen()`/`reopen()` (déjà conformes, vocabulaire seul ajusté), `reassign_service()`/`transfer_direction()` (déjà ciblés sur le seul responsable concerné), escalade manuelle (déjà nominative, double notification demandeur+cible volontaire et distincte), `ServiceTask`/`ServiceAnnouncement` (hors périmètre de cette demande), pièce jointe seule (déjà sans notification, conforme à la demande).

Fichiers modifiés:
- `backend/api/services/NotificationEmitter.py`
- `backend/api/services/ServiceRequest.py`
- `backend/api/services/ServiceEscalade.py`
- `backend/api/core/scheduler.py`
- `backend/api/core/mailer.py`
- `backend/api/routes/RouteRequest.py`
- `backend/templates/_ticket_notification_base.html`
- `backend/templates/notification_email.html`
- `backend/tests/api/test_notification_workflow.py` (nouveau, 7 tests)
- `backend/tests/api/test_transmit_treatment.py` (2 assertions de titre alignées sur le nouveau vocabulaire + 1 nouvelle assertion couvrant la confirmation App-only à l'émetteur)
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Vérification: `backend/venv/Scripts/python.exe -m pytest backend/tests/api/test_notification_workflow.py backend/tests/api/test_transmit_treatment.py -q` → 20 passés. Suite complète `backend/tests/api` → 59 échecs (exactement le même total déjà documenté comme préexistant dans l'entrée du 2026-08-07 précédente, ci-dessous — aucune régression nette), 234 passés / 5 skip. Échecs vérifiés individuellement en isolation (`test_creation_auto_route_auto_assign_agent_disponible`, `test_cdc_alignment.py`, `test_directive_comment.py`, `test_escalate_to_director.py`) : tous reproduisent le bug préexistant documenté (`LookupError: 'agent' is not among the defined enum values`, rôle littéral absent de l'enum réel à 7 rôles) ou une dépendance d'ordre d'exécution entre fichiers de test (comptes créés par un autre fichier), aucun lien avec ce lot. `warn_sla_approaching()` non testé en intégration (SQLite ne supporte pas `TIMESTAMPDIFF`, même limitation déjà documentée pour `mark_sla_breached()`/`run_auto_escalation()`, KI-SQL-001) ; le reset du flag anti-répétition à la réouverture (pur Python) est couvert par la relecture de `reopen()`. `npx tsc`/`npm run build` non exécutés — aucun fichier frontend touché par ce lot.

Décisions restant à trancher (signalées, non tranchées ici) :
- Réouverture immédiate en libre-service (section 18 de la demande) vs BR-REOPEN-QUEUE-001 (approbation chef/directeur) — contradiction à arbitrer avant toute implémentation.
- SLA préventif : seuil 80% choisi par défaut (aucun seuil fourni par la demande) ; notification du responsable en plus de l'intervenant actuel volontairement omise (marquée "éventuellement" dans la demande) — à confirmer.
- `close()` : notification "éventuelle" au dernier intervenant (mentionnée comme optionnelle dans la demande) non ajoutée, pour limiter la surface modifiée — à confirmer si souhaitée.
- `reassign_service()`/`transfer_direction()` : ni le demandeur ni l'ancien intervenant ne sont notifiés (uniquement le nouveau responsable) — non couvert explicitement par la demande, laissé inchangé.
- Environnement de test : SMTP semble réellement configuré (emails transactionnels effectivement envoyés pendant `pytest`, observé via logs `mailer.py`) — préexistant, hors périmètre de cette demande, signalé pour information.

## 2026-08-07 - Sélecteur @mention pour "Transmettre le traitement" + recherche annuaire tokenisée

Demande: transformer le champ "Recherche" de la modale "Transmettre le traitement" en sélecteur @mention (recherche par prénom/nom dans les deux ordres, matricule, téléphone tolérant au formatage), avec auto-remplissage fiable de Direction/Département/Service à la sélection, gestion des homonymes (aucune sélection automatique), et combinaison possible avec les filtres organigramme existants — sans jamais transformer le workflow collaboratif dynamique en circuit fixe, ni modifier `assignee_id` avant le clic sur "Transmettre".

Audit préalable (tour précédent) : la cascade Direction/Département/Service, la recherche libre et l'auto-remplissage existaient déjà partiellement, mais deux défauts de fond bloquaient le besoin — (1) la recherche annuaire ne supportait qu'un seul mot par requête (aucun résultat pour "Prénom Nom") ; (2) l'auto-remplissage Direction/Département était déjà cassé en silence pour tout compte non-directeur (champs absents de la réponse compte).

Correction:
- `AccountRepository._apply_search()` (surcharge locale, `base_repository.py` partagé par les autres repositories non touché) : tokenise le terme (chaque mot doit matcher name/firstname/email/matricule/phone — ET entre mots, OU entre colonnes) ; normalise les termes numériques via `core/phone.py` déjà existant (tolère espaces/tirets/indicatif).
- `AccountRepository.search()` / `ServiceAccount.search()` / `RouteUsers.py::list_users` : `direction_id`/`unit_id` combinables avec `search` au lieu d'être ignorés.
- `app.requests.$id.tsx` : résolution Direction/Département via `GET /units/{id}` (déjà existant) à partir du `unit_id` réel de la personne sélectionnée, au lieu de champs jamais peuplés côté compte — corrige un bug latent déjà présent avant cette demande.
- Champ "Recherche" migré vers `components/ui/command.tsx` (cmdk, déjà dans le repo mais jamais utilisé) : navigation clavier haut/bas/entrée/échap native, debounce 400ms (`use-debounce.ts`, réutilisé), matricule affiché dans chaque suggestion et dans la personne sélectionnée pour désambiguïser les homonymes.
- Aucun nouvel endpoint. Aucune modification de `transmit_treatment()`, `assignee_id`, du workflow dynamique, de BR-TRANSMIT-001/BR-TRACE-001/BR-REQUESTER-NO-SELF-TREATMENT-001/BR-REOPEN-QUEUE-001/BR-SLA-REOPEN-001 — la sélection dans le picker prépare seulement `to_user_id` localement, la transmission réelle reste déclenchée uniquement par le bouton "Transmettre".

Fichiers modifiés:
- `backend/api/repositories/RepositoryAccount.py`
- `backend/api/services/ServiceAccount.py`
- `backend/api/routes/RouteUsers.py`
- `backend/tests/api/test_directory_search.py` (nouveau)
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`
- `docs/codex/API_INDEX.md`

Vérification: `backend/venv/Scripts/python.exe -m pytest backend/tests/api/test_directory_search.py -q` → 9 tests passés. Suite complète `backend/tests/api` (avant/après comparés via `git stash`, untracked exclus) → même ensemble de 59 échecs préexistants des deux côtés (aucune régression), 227→236 tests passés (+9, les nouveaux). `npx tsc --noEmit` → même jeu d'erreurs préexistantes qu'avant (aucune nouvelle). `npm run build` → succès. Vérification visuelle en navigateur non effectuée (pas d'outil d'automatisation navigateur disponible dans cet environnement ; nécessiterait la stack complète MySQL + session authentifiée + données de test avec matricule/téléphone) — signalé explicitement, non simulé.

## 2026-08-07 - Le demandeur ne peut jamais devenir intervenant de son propre ticket (BR-REQUESTER-NO-SELF-TREATMENT-001)

Demande: `requester_id != assignee_id` pour tout ticket, quel que soit le role professionnel du demandeur — ni en s'auto-assignant, ni via une assignation/qualification/transmission/reassignation/escalade faite par un tiers, y compris apres reouverture. Le role professionnel d'un utilisateur ne doit jamais transformer son propre ticket en ticket de traitement pour lui-meme : pour son propre ticket il reste `requester`, jamais `handler` — meme dans "Ma boite de traitement" en lecture.

Analyse prealable : une garde de conflit d'interet existait deja (`assert_ticket_scope`, bloque l'ACTEUR quand `acteur == demandeur`) mais ne verifiait jamais la CIBLE d'une affectation — un tiers pouvait donc transmettre/assigner un ticket au demandeur sans etre bloque. "Ma boite de traitement" et les boutons de traitement de la fiche detail etaient deja corrects (pilotes par `assignee_id`/`isAssignedToMe` + `!iAmRequester`), seule l'ecriture d'`assignee_id` n'etait jamais verifiee cote cible.

Correction:
- nouvelle garde centralisee `assert_requester_is_not_handler()` (`ticket_actions.py`) + code erreur `REQUESTER_CANNOT_TREAT_OWN_TICKET`, appelee dans `transmit_treatment()`, `assign()`, `qualify_triage()` et le PATCH generique admin.
- `_select_auto_assignee()` et `_apply_routing()` : exclusion du demandeur de l'auto-assignation a la creation.
- `reassign_service()` : un chef de service cible qui serait le demandeur est traite comme "aucun chef trouve" (repli existant vers non-assigne).
- `find_hierarchical_chief()` (escalade manuelle + auto SLA) : nouveau parametre `exclude_requester_id`, applique aux deux niveaux de recherche hierarchique.
- defense en profondeur cote lecture : `GET /requests?assignee_id=<soi-meme>` ("Ma boite de traitement") exclut aussi les tickets dont l'acteur est le demandeur — scope limite a cette vue precise (`is_own_assignee_view`), sans impact sur les autres usages du filtre `assignee_id` (rapports, charge par agent).
- frontend : le demandeur du ticket est exclu des selecteurs d'intervenant (`app.requests.$id.tsx` modale transmission, `app.queue.tsx` "Personne cible"), en plus de l'acteur connecte deja exclu.
- aucune modification du workflow collaboratif dynamique, de `workflow_detail`, des cycles SLA, ni du cas `reject()` (marqueur terminal volontaire, hors perimetre).

Limitation documentee (bug preexistant, non corrige — hors perimetre) : `RepositoryAccount.find_chief_for_unity()` et `_select_auto_assignee()` filtrent sur les roles litteraux `"chief"`/`"agent"` absents de l'enum reel, rendant ces deux chemins actuellement sans effet en pratique (meme sans mon changement) — le repli ajoute ici est correct par relecture de code mais pas verifiable par un test passant tant que ce bug distinct n'est pas corrige.

Fichiers modifies:
- `backend/api/core/error_codes.py`
- `backend/api/core/ticket_actions.py`
- `backend/api/services/ServiceRequest.py`
- `backend/api/services/ServiceEscalade.py`
- `backend/api/routes/RouteRequest.py`
- `backend/api/repositories/RepositoryRequest.py`
- `backend/tests/api/test_requester_no_self_treatment.py` (nouveau)
- `frontend/src/routes/app.requests.$id.tsx`
- `frontend/src/routes/app.queue.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`
- `docs/codex/API_INDEX.md`

Verification: `backend/venv/Scripts/python.exe -m pytest backend/tests/api/test_requester_no_self_treatment.py -q` -> 6 tests passes. Suite de regression `test_transmit_treatment.py` + `test_ticket_actions.py` + `test_reopen_queue.py` + `test_sla_reopen.py` + `test_trace_interventions.py` + `test_requester_no_self_treatment.py` -> 107 passes, 1 skip deja documente, aucune regression. `test_requests_baseline.py` + `test_reopen_queue.py` (isolement croise connu, deja preexistant) -> 30 echecs/35 succes, compte identique avant/apres (verifie par `git stash` lors d'une session precedente), sans lien avec ce changement.

## 2026-08-07 - "Tickets transmis" suit la responsabilite actuelle, plus seulement l'historique

Demande: quand un ticket deja transmis par un utilisateur (visible dans "Tickets transmis") lui revient via une nouvelle transmission d'un tiers, il doit disparaitre de "Tickets transmis" et reapparaitre dans "Ma boite de traitement" avec les actions de traitement disponibles, sans jamais toucher au workflow collaboratif dynamique ni a la tracabilite historique (`workflow_detail`).

Analyse: "Ma boite de traitement" (`app.my-tickets.tsx`, filtre `assignee_id`) et les actions de traitement (`app.requests.$id.tsx`, `isAssignedToMe`) etaient deja pilotees par `assignee_id` courant — deja conformes. Seule `list_transmitted_by_actor()` (BR-TRANSMIT-001) restait purement historique ("independamment du porteur actuel"), en contradiction directe avec la nouvelle regle des lors qu'un ticket revenait a un ancien transmetteur.

Correction:
- ajout de `AND (r.assignee_id IS NULL OR r.assignee_id != :actor_id)` aux deux requetes SQL de `list_transmitted_by_actor()` (comptage + selection) — exclut les tickets dont l'acteur est redevenu l'intervenant actuel.
- aucune modification de `transmit_treatment()`, du routage dynamique, de `workflow_detail`, ni d'aucune autre regle metier.
- docstrings `RepositoryRequest.list_transmitted_by_actor` et `RouteRequest.list_transmitted_by_me` mises a jour pour refleter la nouvelle semantique.

Fichiers modifies:
- `backend/api/repositories/RepositoryRequest.py`
- `backend/api/routes/RouteRequest.py`
- `backend/tests/api/test_transmit_treatment.py` (nouveau test `test_transmitted_view_flips_back_to_my_tickets_when_ticket_returns`, scenario A -> B -> A -> C)
- `backend/tests/conftest.py` (shim test-only `JSON_UNQUOTE` pour SQLite — necessaire pour executer `GET /requests/transmitted`, jusqu'ici jamais teste sous SQLite ; aucun SQL metier modifie)
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Verification: `backend/venv/Scripts/python.exe -m pytest backend/tests/api/test_transmit_treatment.py -q` -> 13 tests passes (dont le nouveau scenario A->B->A->C). Comparaison `git stash` avant/apres sur `test_requests_baseline.py` + `test_reopen_queue.py` -> 30 echecs/35 succes identiques des deux cotes (echecs preexistants, `KeyError: 'agent'` sans lien avec ce changement, hors perimetre de cette demande).

## 2026-08-06 - Rapports interventions : scope backend obligatoire

Demande: étape 1 de la mise en œuvre des tableaux professionnels/exportables — sécuriser en priorité `GET /reports/interventions` avant toute modification UI.

Correction:
- ajout d'un helper de scope backend dédié aux statistiques d'interventions.
- `chief-service` est limité à son service exact.
- `chief-departement` et `director` utilisent le périmètre organigramme via `_scoped_unity_ids`.
- `admin` conserve le périmètre global explicitement autorisé.
- absence de rattachement organisationnel = réponse vide, jamais repli global.

Fichiers modifies:
- `backend/api/routes/RouteReports.py`
- `backend/api/services/ServiceReport.py`
- `backend/tests/api/test_trace_interventions.py`
- `docs/codex/API_INDEX.md`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Verification: `backend\venv\Scripts\pytest.exe backend\tests\api\test_trace_interventions.py -q` -> 8 tests passes, 1 warning tiers `python_multipart`.

## 2026-08-06 - Centre SLA : masquage SLA par service pour chef de service

Demande: masquer la section `SLA Par Service` dans le Centre SLA pour un chef de service.

Correction:
- masquage conditionnel du tableau `SLA par ...` pour le role `chief-service`.
- conservation de la section pour `chief-departement`, `director` et `admin`.
- aucun changement backend, calcul SLA ou liste des tickets en depassement.

Fichiers modifies:
- `frontend/src/routes/app.sla-center.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Verification: `npm run build` dans `frontend/` OK. Warnings Vite/Rollup habituels sur taille de chunks/imports externes inutilises.

## 2026-08-06 - Sidebar : retrait de Rapports Service pour chef de service

Demande: masquer le bouton/menu `Rapports Service` pour un chef de service.

Correction:
- retrait de l'entree sidebar `Rapports Service` pour `chief-service`.
- la route `/app/reports` et les rapports des autres roles restent inchanges.

Fichiers modifies:
- `frontend/src/components/app-layout.tsx`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Verification: `npm run build` dans `frontend/` OK. Warnings Vite/Rollup habituels sur taille de chunks/imports externes inutilises.

## 2026-08-06 - Rapports Service : retrait du bandeau filtres

Demande: supprimer dans `Rapports & Analyses` le bandeau de filtres situe entre l'en-tete et les KPI.

Correction:
- retrait du rendu du bandeau `Filtres` / `Annee en cours` / compteur de tickets dans `/app/reports`.
- conservation du filtrage interne par defaut pour les chargements et exports existants.
- aucun changement backend ni modification des KPI/graphes.

Fichiers modifies:
- `frontend/src/routes/app.reports.tsx`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Verification: `npm run build` dans `frontend/` OK. Warnings Vite/Rollup habituels sur taille de chunks/imports externes inutilises.

## 2026-08-06 - Supervision : masquage des sections agents et escalades

Demande: masquer dans la page `Supervision` les blocs `Charge & retards par agent`, `Distribution des escalades` et `Escalades en cours`.

Correction:
- masquage UI local des trois sections dans `/app/supervision`.
- aucun changement de route, de donnees, de calcul statistique ou de workflow.

Fichiers modifies:
- `frontend/src/routes/app.supervision.tsx`
- `docs/codex/CHANGELOG_CODEX.md`

Verification: `npm run build` dans `frontend/` OK. Warnings Vite/Rollup habituels sur taille de chunks/imports externes inutilises.

## 2026-08-06 - Navigation : retrait du menu Mon equipe

Demande: masquer l'onglet/menu `Mon equipe` pour le chef de service.

Correction:
- retrait de l'entree sidebar `Mon equipe` (`/app/supervision?section=equipe`) pour `chief-service`.
- la page `/app/supervision` reste disponible via le menu `Supervision`; aucun changement de donnees ni de route.

Fichiers modifies:
- `frontend/src/components/app-layout.tsx`
- `docs/codex/CHANGELOG_CODEX.md`

Verification: `npm run build` dans `frontend/` OK.

## 2026-08-06 - Rapports Service : scope exact chef de service

Demande: dans `Rapports Service`, retirer le filtre `Toutes les directions` pour un chef de service et garantir que les donnees affichees correspondent exactement a son service.

Correction:
- frontend: le selecteur direction est masque pour `chief-service`; les rapports services restent chargeables/exportables sans selection de direction.
- backend: `/reports/by-agent`, `/reports/by-unity` et `/reports/csat` forcent `unity_id=actor.unity_id` pour `chief-service`, y compris pour les exports correspondants.
- frontend: le bloc CSAT de `/app/reports` utilise maintenant `/reports/csat` au lieu des stats globales `/stats/csat`, afin de respecter le perimetre service.

Fichiers modifies:
- `frontend/src/routes/app.reports.tsx`
- `frontend/src/lib/api/reports.ts`
- `backend/api/routes/RouteReports.py`
- `backend/api/services/ServiceReport.py`
- `docs/codex/API_INDEX.md`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Verification: `python -m compileall backend/api/routes/RouteReports.py backend/api/services/ServiceReport.py` OK ; `npm run build` dans `frontend/` OK. Warnings Vite/Rollup habituels sur taille de chunks/imports externes inutilises.

## 2026-08-06 - Navigation : retrait du menu Centre de repartition

Demande: enlever le menu `Centre de repartition`.

Correction:
- retrait de l'entree sidebar `Centre de repartition` pour `chief-service`.
- remplacement du raccourci mobile `Repartition` par `Ma boite`, afin de garder un acces direct au traitement.
- la route `/app/chief-inbox` reste disponible techniquement pour compatibilite des liens profonds.

Fichiers modifies:
- `frontend/src/components/app-layout.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/ROUTE_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Verification: `npm run build` dans `frontend/` OK.

## 2026-08-06 - Escalades : retrait de l'onglet Repartition et reprise dans Ma boite

Demande: supprimer `Repartition > Escalades` et faire apparaitre les tickets escalades dans `Ma boite de traitement`.

Correction:
- retrait de l'onglet interne `Escalades` dans `app.chief-inbox.tsx` et des deep-links `?tab=escalated`.
- suppression des raccourcis menu `Escalades` chief-service/chief-departement qui pointaient vers le centre de repartition/pilotage.
- `Ma boite de traitement` fusionne maintenant les tickets assignes a l'utilisateur avec les tickets `escalated` de son perimetre operationnel pour `chief-service` et `chief-departement`.

Fichiers modifies:
- `frontend/src/routes/app.chief-inbox.tsx`
- `frontend/src/routes/app.my-tickets.tsx`
- `frontend/src/components/app-layout.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/ROUTE_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Verification: `npm run build` dans `frontend/` OK. Warnings Vite/Rollup habituels sur taille de chunks/imports externes inutilises.

## 2026-08-06 - Navigation : detail depuis Tickets transmis conserve son contexte

Demande: depuis `/app/transmitted`, ouvrir le detail d'un ticket sans selectionner `Supervision` par defaut ; rester dans l'onglet/menu `Tickets transmis`.

Correction:
- ajout d'une route detail dediee `/app/transmitted/tickets/$id` qui reutilise `RequestDetailPage` avec le contexte `transmitted`.
- `ticket-navigation.ts` mappe maintenant `/app/transmitted` vers cette route detail.
- `RequestDetailPage` connait le contexte `Tickets transmis` et son bouton retour pointe vers `/app/transmitted`.
- `app-layout.tsx` reconnait `/app/transmitted/tickets/...` pour garder l'item `Tickets transmis` actif.

Fichiers modifiés:
- `frontend/src/lib/ticket-navigation.ts`
- `frontend/src/routes/app.transmitted.tsx`
- `frontend/src/routes/app.transmitted_.tickets.$id.tsx`
- `frontend/src/routes/app.requests.$id.tsx`
- `frontend/src/components/app-layout.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/FILE_INDEX.md`
- `docs/codex/ROUTE_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Verification: `npm run build` dans `frontend/` OK. La route detail dediee est prise en compte dans les chunks generes (`app.transmitted_.tickets._id`). Warnings Vite/Rollup habituels sur taille de chunks/imports externes inutilises.

## 2026-08-06 - Tickets transmis : grille, recherche et pagination

Demande: sur `/app/transmitted`, appliquer l'affichage en grille, ajouter une zone de recherche et conserver une pagination.

Correction:
- frontend: la page `Tickets transmis` s'ouvre en grille par defaut, garde le toggle liste/grille, affiche une recherche dans l'en-tete et utilise une pagination a 12 elements par page.
- backend/API: `GET /requests/transmitted` accepte un parametre additif `search` qui filtre les tickets transmis dans le scope de l'acteur courant (ref, titre, description, demandeur, email, compteur), sans changer le workflow ni les permissions.

Fichiers modifiés:
- `backend/api/repositories/RepositoryRequest.py`
- `backend/api/services/ServiceRequest.py`
- `backend/api/routes/RouteRequest.py`
- `frontend/src/lib/api/requests.ts`
- `frontend/src/routes/app.transmitted.tsx`
- `docs/codex/API_INDEX.md`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/ROUTE_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Verification: `python -m compileall backend/api/repositories/RepositoryRequest.py backend/api/services/ServiceRequest.py backend/api/routes/RouteRequest.py` OK ; `npm run build` dans `frontend/` OK. Warnings Vite/Rollup habituels sur taille de chunks/imports externes inutilises.

## 2026-08-06 - Correctif UI : actions de traitement sans panneau vide

Demande: dans l'onglet `Traitement` du detail ticket, supprimer la zone "Aucune action disponible dans l'etat actuel du ticket" et rattacher les actions qui pouvaient s'y afficher a la grille de boutons situee au-dessus.

Correction: `RequestDetailPage` fusionne les actions demandeur (`Modifier`, `Annuler`, `Demander une reouverture`, `Confirmer la resolution`, `Votre avis`) dans la meme grille que les actions de traitement staff, conserve les conditions d'affichage existantes et ne rend plus le panneau vide quand aucune action demandeur n'est disponible.

Fichiers modifiés:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/CHANGELOG_CODEX.md`

Verification: `npm run build` dans `frontend/` OK. Premier passage interrompu par timeout local a 120 s, second passage OK avec les warnings Vite/Rollup habituels sur taille de chunks/imports externes inutilises.

## 2026-08-05 - Correctif affichage : noms de services dans Centre SLA

Demande: dans `/app/sla-center`, afficher les noms des services plutot que les valeurs/id bruts dans "SLA par service" et "Tickets en depassement SLA".

Correction: `app.sla-center.tsx` resout les libelles de services via `/units`, complete les unites manquantes par `GET /units/{id}` si necessaire, et utilise le libelle service aussi pour `chief-service`/`chief-departement` dans le tableau des tickets en depassement.

Fichiers modifiés:
- `frontend/src/routes/app.sla-center.tsx`
- `docs/codex/CHANGELOG_CODEX.md`

Verification: `npm run build` dans `frontend/` OK. Warnings Vite/Rollup habituels sur taille de chunks/imports externes inutilises, sans echec de build.

## 2026-08-05 - Mise en conformite : File d'attente collaborative

Demande: aligner la File d'attente avec la philosophie de traitement collaboratif : tous les roles operationnels peuvent prendre un ticket, etre destinataires d'une assignation et devenir intervenant courant.

Module: MOD-AGENT / MOD-CHIEF / MOD-DIRECTION — File d'attente (`/app/queue`) et Ma boite de traitement (`/app/my-tickets`).

Correction:
- backend: `qualify` et `assign` autorisent desormais `agent-support`, `chief-service`, `chief-departement`, `director`, `admin`.
- backend: l'assignation valide que le destinataire porte un role operationnel et reste dans le perimetre organisationnel de l'acteur non-admin ; `dg` reste explicitement exclu et un destinataire `admin` ne peut etre choisi que par un `admin`.
- frontend: le Directeur n'est plus en lecture seule dans la File d'attente ; le bouton "Prendre le ticket" et le formulaire "Assigner" sont disponibles pour les roles operationnels.
- frontend: la liste "Personne cible" inclut les roles operationnels de la direction selectionnee.

Fichiers modifiés:
- `backend/api/core/ticket_actions.py`
- `backend/api/routes/RouteRequest.py`
- `backend/api/services/ServiceRequest.py`
- `frontend/src/routes/app.queue.tsx`
- `frontend/src/lib/capabilities.ts`
- `docs/codex/API_INDEX.md`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/ROLE_INDEX.md`
- `docs/codex/ROUTE_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Verification: `python -m compileall backend\api\core\ticket_actions.py backend\api\routes\RouteRequest.py backend\api\services\ServiceRequest.py` OK ; `backend\venv\Scripts\pytest.exe backend\tests\api\test_ticket_actions.py backend\tests\api\test_qualify_narrowing.py backend\tests\api\test_lot3_narrowing.py -q` OK (79 passed, 1 warning Starlette/python_multipart) ; `npm run build` dans `frontend/` OK.

## 2026-08-05 - Correctif : Ma boite limitee aux tickets assignes a l'utilisateur courant

Demande: `Ma boite de traitement` doit afficher uniquement les tickets que l'utilisateur connecte a pris depuis la File d'attente ou qui lui ont ete assignes/transmis.

Module: MOD-AGENT / MOD-CHIEF — Ma boite de traitement (`/app/my-tickets`).

Correction: la requete principale et les KPI envoient explicitement `assignee_id=<utilisateur courant>` et excluent les statuts terminaux (`resolved`, `closed`, `cancelled`, `rejected`). Une garde d'affichage cote frontend filtre aussi les lignes dont `assigneeId` ne correspond pas a l'utilisateur courant, afin d'eviter tout affichage par simple perimetre service/departement/direction.

Fichiers modifiés:
- `frontend/src/routes/app.my-tickets.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Verification: `npm run build` dans `frontend/` reussi. Warnings Vite/Rollup habituels sur taille de chunks/imports externes inutilises, sans echec de build.

## 2026-08-05 - Correctif : Ma boite masque les tickets pris apres retrait de "Reouvertures"

Demande: apres avoir pris un ticket depuis la File d'attente, il n'apparaissait pas dans "Ma boite de traitement" pour poursuivre le traitement.

Module: MOD-AGENT / MOD-CHIEF — Ma boite de traitement (`/app/my-tickets`).

Cause: l'ancien raccourci menu "Reouvertures" ouvrait `/app/my-tickets?status=reopened` et persistait ce filtre dans `sessionStorage` (`mt:status`). Apres suppression du menu, une session utilisateur pouvait conserver `mt:status="reopened"` ; Ma boite chargeait alors uniquement les tickets reouverts et masquait le ticket fraichement pris, qui passe normalement en `assigned`.

Correction: au chargement normal de `/app/my-tickets` sans parametre `status`, un nettoyage de compatibilite remet une seule fois le filtre legacy `reopened` a `all`. Les tickets `reopened` restent dans la liste principale quand le filtre est `all`, et le filtre manuel par statut reste disponible ensuite.

Fichiers modifiés:
- `frontend/src/routes/app.my-tickets.tsx`
- `docs/codex/CHANGELOG_CODEX.md`

Verification: `npm run build` dans `frontend/` reussi. Warnings Vite/Rollup habituels sur taille de chunks/imports externes inutilises, sans echec de build.

## 2026-08-05 - Navigation : suppression du raccourci "Reouvertures"

Demande: supprimer l'entree de menu "Reouvertures" tout en conservant les tickets au statut `reopened` dans "Ma boite de traitement".

Module: navigation transverse (`app-layout.tsx`) / MOD-AGENT-MOD-CHIEF.

Correction: retrait des trois items de navigation "Reouvertures" (`/app/my-tickets?status=reopened`, `/app/chief-inbox?tab=reopen`, `/app/department-inbox?tab=reopen`). Aucun filtre de donnees n'est modifie: `/app/my-tickets` conserve deja `reopened` dans ses statuts actifs et continue donc d'afficher ces tickets dans la boite principale.

Fichiers modifiés:
- `frontend/src/components/app-layout.tsx`
- `docs/codex/ROUTE_INDEX.md`
- `docs/codex/ROLE_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Verification: `rg "Réouvertures|Reouvertures|RotateCcw" frontend/src/components/app-layout.tsx` ne retourne plus d'occurrence ; `npm run build` dans `frontend/` — succès. Warnings Vite/Rollup existants sur taille de chunks/imports externes inutilisés, sans échec de build.

## 2026-08-05 - Correctif : prise de ticket vers Ma boîte de traitement

Demande: quand un utilisateur prend un ticket depuis la File d'attente, le ticket doit sortir du triage et apparaître dans "Ma boîte de traitement" (`/app/my-tickets`) pour pouvoir être traité.

Module: MOD-AGENT / MOD-CHIEF — File d'attente et boîte de traitement personnelle.

Cause: côté frontend, le bouton "Prendre le ticket" construisait la payload seulement si une direction ou un service était déjà disponible sur la carte (`takeDirectionId || takeUnitId`). Or un ticket en triage peut légitimement ne pas porter encore cette orientation complète ; dans ce cas l'auto-prise restait bloquée côté UI alors que le backend sait qualifier avec `assignee_id` seul, sortir le ticket du triage et le rendre visible via `/requests?assignee_id=<moi>`.

Correction: `app.queue.tsx` autorise l'auto-prise dès que l'utilisateur est connecté et que le statut est qualifiable, avec fallback catégorie `autre` si la carte n'a pas de catégorie. Les champs `direction_id`/`unit_id` restent envoyés quand ils existent, mais ne bloquent plus la prise en charge.

Fichiers modifiés:
- `frontend/src/routes/app.queue.tsx`
- `docs/codex/CHANGELOG_CODEX.md`

Vérification: `npm run build` dans `frontend/` — succès. Warnings Vite/Rollup existants sur taille de chunks/imports externes inutilisés, sans échec de build.

## 2026-08-05 - Fonctionnalité "Tickets transmis" (BR-TRANSMIT-001)

Demande: rendre fonctionnel l'item de menu "Tickets transmis" (jusqu'ici préparé mais désactivé) — une liste personnelle de tous les tickets que l'utilisateur connecté a lui-même transmis à quelqu'un d'autre à un moment de leur historique, peu importe qui les détient aujourd'hui ou leur statut actuel.

Module: MOD-WORKFLOW / MOD-AGENT / MOD-CHIEF / MOD-DIRECTION (lecture seule, complète BR-TRANSMIT-001 sans le reconstruire).

Cause/analyse préalable: quand `transmit_treatment()` écrit l'événement `workflow_detail` (`event_type="treatment_transmitted"`), `RepositoryWorkflowDetail.create_event()` réaffecte la colonne réelle `agent_id` au **destinataire** (`dest_id`), jamais à l'émetteur — l'identité de l'émetteur ne vit que dans le JSON `infos.actor_id`, sans colonne dédiée ni index. Aucune méthode de requête existante ne filtrait sur ce champ pour une liste (seul précédent : requêtes SQL brutes `JSON_EXTRACT`/`JSON_UNQUOTE` dans `ServiceStats.py`, pour des agrégats).

Correctif: requête SQL brute (même précédent que `ServiceStats.py`) trouvant les `request_id` distincts ayant un événement `treatment_transmitted` avec `infos.actor_id = <moi>`, dédupliqués par ticket (un ticket transmis plusieurs fois par la même personne à travers différents cycles n'apparaît qu'une fois, triée par transmission la plus récente), puis hydratation via le pipeline standard existant (`RequestRepository.list(filters={"id": [...]})`) — aucun nouveau schéma de réponse, réutilise `RequestListItemResponse` tel quel.

Fichiers modifiés:
- `backend/api/repositories/RepositoryRequest.py` (`list_transmitted_by_actor`, import `text`)
- `backend/api/services/ServiceRequest.py` (`list_transmitted_by_me`)
- `backend/api/routes/RouteRequest.py` (`GET /requests/transmitted`, inséré avant le catch-all `/{id}`, scope `agent-support/chief-service/chief-departement/director/admin`)
- `frontend/src/lib/api/requests.ts` (`fetchTransmittedByMe`)
- `frontend/src/routes/app.transmitted.tsx` (nouvelle page dédiée — pas un 4e onglet greffé sur `app.my-tickets.tsx`, dont le garde de rôle est plus étroit et les KPI sémantiquement liés à "assigné à moi", disjoint de "j'ai transmis")
- `frontend/src/components/app-layout.tsx` (item de nav "Tickets transmis" activé, `disabled` retiré, pointe vers `/app/transmitted`)

Verification: `npx tsc --noEmit` et `npm run build` — 0 nouvelle erreur. Test manuel réel sur le backend en cours d'exécution : `GET /requests/transmitted` authentifié en tant que Fatoumata Conté (agent-support ayant transmis plusieurs tickets lors de recettes précédentes) → 8 tickets retournés correctement, pagination vérifiée (page 2/limit 3 → bon offset, bon total/pages). Aucune migration Alembic, aucun fichier `ticket_actions.py`/RBAC touché.

Point signalé (non bloquant, chantier séparé) : requête `JSON_EXTRACT` non indexée sur `workflow_detail` (même style que l'existant `ServiceStats.py`, pas de nouveau risque introduit) — un index composite `(event_type, deleted_at)` accélérerait cette requête et les agrégats existants si le volume le justifie un jour. Risque de 403 au clic sur un ticket dont l'unité a changé depuis la transmission — limitation préexistante de `_check_request_access`, non introduite ni aggravée par cette fonctionnalité.

## 2026-08-05 - Refonte de la navigation par rôle — "Mon travail" (philosophie du traitement collaboratif)

Demande: faire évoluer l'organisation des menus pour refléter la philosophie "le traitement d'un ticket n'est plus l'apanage d'un rôle hiérarchique — tous les rôles opérationnels sont des intervenants potentiels ; ce qui les différencie est leur niveau de responsabilité en supervision/pilotage/analyse/administration, pas leur capacité à traiter." Le groupe de menu "Traitement" devient "Mon travail" avec un socle commun (Ma boîte de traitement, File d'attente, Réouvertures, Tickets transmis) pour agent-support, chief-service, chief-departement, director et admin.

Module: navigation transverse (`app-layout.tsx`) + pages de traitement (`app.queue.tsx`, `app.my-tickets.tsx`, `app.chief-inbox.tsx`/`app.department-inbox.tsx`, `app.direction.tsx`, `app.supervision.tsx`).

Analyse préalable (3 agents d'exploration en parallèle, cf. plan approuvé avant implémentation) : deux décisions produit ont été prises AVANT tout codage — (1) le Directeur ne reçoit aucune nouvelle capacité RBAC : les règles backend `BR-TRANSMIT-001` (`ticket_actions.py`) qui l'excluent aujourd'hui de `qualify`/`assign` restent inchangées ; (2) on réorganise l'existant en priorité — aucune nouvelle page n'est construite pour les éléments sans équivalent actuel ("Tickets transmis", "Activité du service/département", accès Directions/Départements/Services pour le Directeur, scission Statistiques/Rapports).

Correctif:
- **Ré-étiquetage et recatégorisation** (`app-layout.tsx`) : groupe "Traitement" → "Mon travail" ; "Centre de répartition"/"Centre de pilotage" reclassés vers "Pilotage" (ce sont des outils de répartition/supervision, pas du traitement personnel) ; "Rapports" reclassé vers un nouveau groupe "Analyse" (4 entrées distinctes "Rapports Service/Département/Direction"/"Rapports" remplaçant l'ancien ternaire de libellé conditionnel) ; "Vue direction" → "Ma boîte de traitement" (c'est déjà l'outil de traitement du directeur) ; "Tableau de bord stratégique" → "Tableau de bord DSI" ; "Vue globale" → "Supervision globale".
- **Correctif d'accès frontend** (même classe de bug que celui corrigé plus tôt le 2026-08-05 pour chief-service/`/app/my-tickets`) : `chief-departement` gagne l'accès à `/app/my-tickets` et `/app/queue` — le backend autorisait déjà ce rôle sur l'action `qualify` et le bypass de périmètre triage (`ticket_actions.py`), seul le garde-fou frontend (`beforeLoad`) l'excluait artificiellement.
- **Accès lecture seule pour `director`** : `/app/queue` lui est désormais ouvert (le backend autorise déjà `GET /requests/queue` pour ce rôle), mais les actions "Prendre le ticket"/"Assigner" sont masquées spécifiquement pour lui (`canTakeRole`, `canUseAssignForm` dans `app.queue.tsx`) — le backend les bloque de toute façon (`qualify`/`assign` n'incluent pas `director` dans `ACTION_ALLOWED_ROLES`) ; masquer évite une erreur 403 confuse sans accorder de nouvelle capacité.
- **Deep-links additifs vers des filtres/onglets déjà existants** (aucune nouvelle vue de données) : "Réouvertures" → `/app/my-tickets?status=reopened` (agent-support/admin) ou `/app/chief-inbox?tab=reopen` / `/app/department-inbox?tab=reopen` (chief-service/chief-departement, onglet déjà existant) ; "Escalades" → même mécanisme `?tab=escalated`, ou ancre `?section=escalades-l3` vers la section déjà existante de `/app/direction` (director) ; "Mon équipe" → ancre `?section=equipe` vers la section "Charge par agent" déjà existante de `/app/supervision`. Lecture des paramètres via `URLSearchParams(window.location.search)` dans un `useEffect` au montage (aucun `validateSearch` TanStack Router préexistant dans le projet — cohérent avec le style déjà utilisé ailleurs, ex. `public-layout.tsx`).
- **"Tickets transmis"** : préparé mais désactivé (item grisé, non cliquable, tooltip "bientôt disponible") — même traitement que le bouton "Exporter le journal" du Journal d'intervention (précédent déjà validé) ; aucune vue "tickets que j'ai personnellement transmis" n'existe côté données, différé à un chantier séparé.

Fichiers modifiés:
- `frontend/src/components/app-layout.tsx` (navItems, menu mobile, rendu des items désactivés/deep-link)
- `frontend/src/routes/app.queue.tsx`, `app.queue_.tickets.$id.tsx` (rôles + lecture seule director)
- `frontend/src/routes/app.my-tickets.tsx`, `app.my-tickets_.tickets.$id.tsx` (rôles + deep-link `?status=`)
- `frontend/src/routes/app.chief-inbox.tsx` (deep-link `?tab=`, couvre aussi `app.department-inbox.tsx` qui réutilise ce composant)
- `frontend/src/routes/app.direction.tsx` (ancre `escalades-l3`)
- `frontend/src/routes/app.supervision.tsx` (ancre `equipe`)
- `docs/codex/ROLE_INDEX.md` (pages pro par rôle mises à jour)

Verification: `npx tsc --noEmit` et `npm run build` — 0 nouvelle erreur sur les 9 fichiers modifiés (les erreurs pré-existantes dans `app.supervision.tsx`/`app.requests.index.tsx`/`app.sla-center.tsx` restent identiques en nombre, non liées à ce chantier). `git diff --stat backend/` vide — aucune règle de sécurité/RBAC backend modifiée, conformément à la décision produit.

Éléments différés (chantier séparé, non construits) : "Tickets transmis" (nécessite une vraie requête backend), "Activité du service/département" (aucune page ne correspond), accès Directions/Départements/Services pour le Directeur (pages admin-only, décision de permissions séparée), scission Statistiques/Rapports en deux pages distinctes, "Réouvertures"/"Escalades" pour le Directeur (aucune vue filtrée n'existe, non créée pour rester cohérent avec la décision RBAC).

## 2026-08-05 - Uniformisation terminologique "Demande" → "Ticket" (UI/UX + documentation utilisateur)

Demande: uniformiser le vocabulaire métier principal de l'application sur le terme ITSM standard "Ticket", en remplaçant "Demande" partout où ce mot désigne l'objet principal traité par le système (menus, titres, boutons, pages, modales, notifications, messages de succès/erreur, infobulles, libellés de formulaires, breadcrumbs, exports, base de connaissance) — à l'exclusion des routes API, tables SQL, modèles backend, colonnes, endpoints, DTO et migrations (non renommés), et à l'exclusion des usages où "demande"/"demandeur" désigne une catégorie métier distincte ("Demande de service", "Demande de réouverture", "Demande d'informations") ou le rôle de la personne (le "demandeur").

Module: présentation transverse (MOD-WORKFLOW / MOD-AGENT / MOD-CHIEF / MOD-DIRECTION / MOD-DG / MOD-ADMIN / pages publiques) — aucune règle métier modifiée, uniquement du texte affiché.

Fichiers modifiés (45 fichiers frontend, ~180 occurrences renommées):
- `frontend/src/components/` : `app-layout.tsx`, `appreciation-form.tsx`, `intervention-journal.tsx`, `metadata-fields.tsx`, `new-request-form.tsx`, `notification-panel.tsx`, `public-layout.tsx`, `rejected-ticket-modal.tsx`, `workflow-timeline.tsx`
- `frontend/src/lib/` : `api/admin-config.ts`, `export.ts`, `homepage-config.ts`, `mock-data.ts`
- `frontend/src/routes/` : `admin-login.tsx` (aucune occurrence renommée, vérifié), `app.admin.audit.tsx`, `app.admin.priorities.tsx`, `app.admin.routing.tsx`, `app.admin.sla.tsx`, `app.chief-inbox.tsx` (aucune occurrence renommée), `app.dg.tsx`, `app.direction.tsx`, `app.index.tsx`, `app.new.tsx`, `app.notifications.tsx`, `app.profile.tsx`, `app.queue.tsx`, `app.reports.tsx`, `app.requests.$id.tsx` (~55 occurrences), `app.requests.history.tsx`, `app.requests.index.tsx`, `app.supervision.tsx`, `app.tsx`, `create-request.tsx`, `index.tsx`, `track.tsx`

Occurrences volontairement conservées (catégorie métier ou hors périmètre UI/UX):
- rôle "Demandeur"/"demandeur" (personne, jamais l'objet) — partout dans l'app ;
- "Demande de réouverture" / "Demande d'informations" (actions/sous-workflows nommés, distincts du ticket lui-même) — `app.chief-inbox.tsx`, `app.requests.$id.tsx` ;
- "Demande de service" et motifs similaires ("demandes de raccordement") — catégories métier, non affectées ;
- titres de tickets simulés en texte libre dans `mock-data.ts` (ex. "Demande de congé exceptionnel") — représentent du texte saisi par un utilisateur fictif, pas le vocabulaire de l'app ;
- usages verbaux du verbe "demander" (ex. "le navigateur le demande", "Demander une réouverture") — non concernés par le remplacement du nom "Demande" ;
- `notification-panel.tsx`/`app.notifications.tsx` : correspondance de texte (`target.includes("demande à qualifier")`) couplée au contenu généré côté backend — non modifiée pour ne pas casser la classification des notifications sans changement backend correspondant (signalé pour validation métier) ;
- `lib/api/notifications.ts` (`nature?: "annonce" | "demande"`) : paramètre de requête transmis tel quel au backend, non un texte d'affichage — non modifié (signalé pour validation métier) ;
- clés de données internes non affichées (`dataKey="demandes"` dans les graphiques Recharts d'`app.reports.tsx` — seul le `name` visible en légende a été renommé) ;
- commentaires de code (hors périmètre "affiché à l'utilisateur").

Points signalés pour validation métier:
- Les pages publiques/citoyennes (`index.tsx`, `create-request.tsx`, `track.tsx`) ont été renommées par cohérence avec la consigne globale, mais "Ticket" est un terme plus technique/ITSM que "Demande" pour un public de citoyens non-initiés — à confirmer côté produit.
- `CLAUDE.md` référence encore certains libellés d'origine ("Nouvelle demande", "Prendre la demande", "Résoudre directement") dans sa description du workflow dynamique — non mis à jour (fichier de gouvernance projet, hors périmètre "documentation utilisateur" de cette tâche), à resynchroniser séparément si souhaité.
- Le commentaire de code `app.queue.tsx:460` référence encore le libellé de bouton d'origine entre guillemets ("Prendre la demande") — non modifié (commentaire, hors périmètre), mais désormais désynchronisé du bouton réel ("Prendre le ticket").

Verification: recherche exhaustive (`grep -rni "demande"`) avant/après sur `frontend/src` (43 fichiers identifiés initialement, 2 occurrences supplémentaires découvertes lors de l'audit final et corrigées) ; toutes les occurrences résiduelles auditées une à une et classées (renommées vs. volontairement conservées). `npx tsc --noEmit` : les erreurs présentes sont pré-existantes et sans rapport (imports manquants, générique React Query, fichiers non touchés par cette tâche comme `app.sla-center.tsx`). `npm run build` : succès. `eslint` : dette `prettier/prettier` pré-existante massive sur plusieurs fichiers (déjà présente avant cette tâche, cf. entrée précédente du changelog sur le même constat) — non corrigée, hors périmètre d'un changement de terminologie ciblé.

Fichiers modifiés (documentation): `docs/codex/CHANGELOG_CODEX.md`.

Point signalé (honnêteté de vérification): aucune vérification visuelle live en navigateur n'a été effectuée pour ce lot — la vérification s'appuie sur la recherche exhaustive de texte, le typage strict et le build de production.

## 2026-08-05 - Correctif : commentaires/pièces jointes invisibles dans le Journal d'intervention (BR-TRACE-001)

Demande: corriger uniquement le bug d'affichage détecté lors de la recette visuelle du 2026-08-04 (Journal d'intervention premium) — les commentaires et pièces jointes rattachés à une intervention n'apparaissaient jamais dans la carte dépliée ni dans la fiche de consultation, malgré des compteurs corrects.

Module: MOD-WORKFLOW / MOD-AGENT (UI, complète BR-TRACE-001 sans le reconstruire).

Cause confirmée par la recette du 2026-08-04 : dans `intervention-journal.tsx`, `eventsById` était construit avec `event.id` brut (nombre côté runtime, l'API renvoie `timelines[].id` en entier) alors que `interventions[].event_ids[]` est sérialisé en chaînes par Pydantic v1 (`InterventionResponse.event_ids: list[str]`). `Map.get()` exige une correspondance exacte de type — `"338" !== 338` — donc chaque correspondance échouait silencieusement, produisant une liste d'événements vide pour chaque intervention sans jamais lever d'erreur.

Correctif (frontend uniquement, aucune donnée ni endpoint modifié) : normalisation des identifiants en chaîne des deux côtés de la correspondance dans `frontend/src/components/intervention-journal.tsx` — `new Map(events.map((e) => [String(e.id), e]))` à la construction, `eventsById.get(String(id))` à la lecture des `eventIds` de chaque intervention.

Fichiers modifiés:
- `frontend/src/components/intervention-journal.tsx` (normalisation `String()` de `eventsById`/`eventsByIntervention`, 2 lignes)

Verification: vérification automatisée ciblée (Node `--test`, aucune dépendance ajoutée — le frontend n'a pas de framework de test) reproduisant le cas exact rapporté (`timeline id=12` nombre, `event_ids=["12"]` chaîne) + 4 scénarios complémentaires (plusieurs événements sur une même intervention, aucun mélange entre interventions/cycles distincts, commentaire du demandeur non rattaché correctement exclu, id référencé mais absent filtré sans erreur) — 5/5 passed. `npx tsc --noEmit` : aucune erreur sur le fichier modifié. `eslint intervention-journal.tsx` : les 21 erreurs `prettier/prettier` déjà présentes dans ce fichier restent identiques et sont toutes situées en dehors des lignes modifiées (résidu de formatage du lot du 2026-08-04, hors périmètre de ce correctif ciblé). `npm run build` : succès, aucune nouvelle erreur.

Point signalé : ce correctif ne modifie ni le backend, ni un endpoint, ni une règle de traçabilité — uniquement la lecture côté client d'une correspondance déjà correcte côté données.

## 2026-08-04 - Journal d'intervention premium — refonte UI/UX (BR-TRACE-001)

Demande: améliorer uniquement l'affichage, la hiérarchie visuelle et l'expérience utilisateur du journal d'interventions déjà fonctionnel (BR-TRACE-001) — sans reconstruire le moteur de traçabilité. Un utilisateur doit comprendre en un coup d'œil combien de cycles/interventions/intervenants un ticket a connus, ce que chacun a réalisé, pourquoi et à qui il a transmis, quelles réouvertures ont eu lieu, quel SLA a été respecté — même avec 20 intervenants et 50 événements.

Module: MOD-WORKFLOW / MOD-AGENT / MOD-CHIEF / MOD-DIRECTION (UI/UX, complète BR-TRACE-001 sans le reconstruire).

Analyse préalable (Étape 1-2, validée avant codage) : le composant `InterventionJournal` existant regroupait déjà les événements par Cycle → Intervention avec le détail complet, mais en liste plate sans hiérarchie visuelle, résumé, filtres, ni consultation dédiée. Inventaire des éléments réutilisables (`Avatar`/`initialsFor`, primitives `Dialog`/`Popover`/`Select`/`Checkbox` shadcn, `handleAttachmentFile` existant) effectué avant toute décision de composant nouveau. Deux données manquantes identifiées et confirmées absentes (pas des inventions) : le rôle de l'intervenant et `summary`/`solution`/`recommendations` n'étaient pas recopiés sur le conteneur `Intervention` bien que déjà présents dans `workflow_detail.infos` — complétés de façon additive (aucune donnée historique modifiée). Aucun statut "Interrompue"/"En attente" n'existe dans le modèle : seuls les 3 états réels (En cours/Transmise/Traitement terminé) sont utilisés, aucun n'a été inventé. Aucun système d'export par ticket n'existant, le bouton "Exporter le journal" est préparé (visible, désactivé) plutôt que de construire un nouveau pipeline backend — validé explicitement avec l'utilisateur.

Correctif: `ModelRequest.interventions` et `InterventionResponse` enrichis de `actor_role`/`summary`/`solution`/`recommendations` (lecture pure de données déjà écrites). Le composant `InterventionJournal` est découpé en 5 fichiers : orchestrateur + résumé + cycles + cartes (`intervention-journal.tsx`), corps de détail partagé entre la carte dépliée et la fiche de consultation (`intervention-detail-body.tsx`), fiche de consultation lecture seule (`intervention-details-modal.tsx`), filtres/recherche (`intervention-filters.tsx`), helpers partagés (`intervention-utils.ts`, évite tout import circulaire entre les composants). Hiérarchie visuelle : en-tête résumé compact (badges), cycles repliables (actif + dernier clos ouverts par défaut, anciens repliés), cartes d'intervention (avatar/initiales, matricule, rôle, service, statut réel, résumé replié / détail complet déplié en 7 sous-sections), liaison visuelle légère entre interventions transmises, séparateur de réouverture distinct (motif/demandeur/approbateur/date), badge "Intervenant actuel" sur le cycle actif. Accessibilité : `aria-expanded`/`aria-controls` sur tous les accordéons, boutons natifs (clavier natif), labels explicites. Responsive : badges en `flex-wrap`, aucune table horizontale, colonnes réduites sur mobile.

Fichiers modifiés:
- `backend/api/models/ModelRequest.py` (`interventions` — `actor_role`, `summary`, `solution`, `recommendations`)
- `backend/api/services/ServiceRequest.py` (`_actor_identity_snapshot` — `intervention_actor_role`)
- `backend/api/schemas/SchemaRequest.py` (`InterventionResponse` — champs additifs)
- `frontend/src/lib/mock-data.ts`, `frontend/src/lib/api/requests.ts` (types/mapping additifs)
- `frontend/src/lib/intervention-utils.ts` (nouveau)
- `frontend/src/components/intervention-journal.tsx` (réécrit), `intervention-detail-body.tsx` (nouveau), `intervention-details-modal.tsx` (nouveau), `intervention-filters.tsx` (nouveau)
- `frontend/src/routes/app.requests.$id.tsx` (libellés de vue "Journal des interventions"/"Chronologie complète", bouton Exporter préparé, props `currentAssigneeId`/`requestRef`)
- `docs/codex/BUSINESS_RULES.md`, `FEATURE_INDEX.md`

Verification: `pytest tests/api/test_trace_interventions.py` → 7/7 passed (les deux champs additifs n'affectent aucune assertion existante). `pytest tests/api` (suite complète) → 217 passed / 52 échecs préexistants, aucune régression. `npx tsc --noEmit`, `eslint` (hors bruit `prettier/prettier` préexistant) et `npm run build` : 0 nouvelle erreur, succès. Revue de code ciblée des 18 scénarios demandés (cycle unique, cycles multiples, réouvertures multiples, même intervenant sur plusieurs cycles, identité figée, ordre, rattachement commentaires/pièces jointes, transmission entre interventions, résolution en dernière intervention, cycle actif identifiable, filtres, recherche, accordéons accessibles, responsive, données anciennes sans nouveaux champs avec fallback, chronologie complète toujours accessible, aucune intervention modifiable) — tous satisfaits par traçage du code contre les données déjà validées par la suite backend.

Point signalé (honnêteté de vérification) : aucune vérification visuelle live en navigateur n'a été effectuée pour ce lot (pas de framework de test frontend dans ce projet ; l'utilisateur pilote habituellement le démarrage backend/frontend/base de données lui-même dans cette session). La correction est vérifiée par typage strict, lint, build de production et traçage logique du code contre des données déjà prouvées correctes côté backend — une recette visuelle en navigateur reste recommandée avant mise en production si une garantie supplémentaire est souhaitée.

## 2026-08-04 - Traçabilité complète des interventions — journal hiérarchique (BR-TRACE-001)

Demande: faire évoluer la traçabilité vers un niveau professionnel (ITSM) — qu'un responsable ouvrant un ticket des années plus tard comprenne immédiatement qui est intervenu, combien de fois, dans quel ordre, pendant combien de temps, pourquoi, et avec quel résultat. La timeline doit afficher des INTERVENTIONS (conteneurs logiques du travail complet d'un intervenant — commentaires, pièces jointes, travail effectué, décision) plutôt qu'une simple liste d'événements, avec trois principes obligatoires : aucune intervention jamais perdue, une intervention validée est figée (jamais modifiée/écrasée/remplacée), chaque action crée un nouvel enregistrement (jamais de mise à jour destructrice).

Module: MOD-WORKFLOW / MOD-AGENT / MOD-CHIEF / MOD-DIRECTION / MOD-REPORT (BR-TRACE-001, complète BR-TRANSMIT-001/BR-REOPEN-QUEUE-001/BR-SLA-REOPEN-001 — ne les reconstruit pas).

Cause: `workflow_detail` (append-only) portait déjà l'essentiel du contenu métier d'une intervention (travail effectué, motif, destinataire, durée, cycle SLA) mais trois informations manquaient pour en faire un véritable conteneur consultable : (1) le regroupement par cycle de réouverture n'existait que sur l'événement de résolution, pas sur les transmissions ni les événements secondaires ; (2) aucune identité figée de l'intervenant (matricule, direction, département, service) n'était jamais enregistrée — seule une jointure live vers le compte était possible, en contradiction avec le principe "une intervention est figée" si le compte change ensuite d'unité ; (3) aucun identifiant de conteneur explicite ne reliait un commentaire ou une pièce jointe à l'intervention pendant laquelle ils avaient été créés.

Analyse préalable (conforme à la démarche demandée) : aucune nouvelle table ni colonne nécessaire. Complété dans `request.infos` (pointeur "intervention courante" — JSON déjà existant, même mécanisme que le flag `reopen_requested`) et dans `infos` de chaque événement `workflow_detail` concerné (jamais recalculé après coup, conformément à la consigne explicite de ne pas dériver le cycle par comptage).

Correctif: `ServiceRequest._actor_identity_snapshot()` (nouveau) fige matricule + direction/département/service (réutilise `_org_chain_for_unity`, déjà utilisé pour les références de tickets) au moment de l'action. `_open_intervention()`/`_current_intervention_meta()` (nouveaux) calculent et enregistrent explicitement `intervention_id` (déterministe), `intervention_order` (repart à 1 à chaque nouveau cycle SLA) et `intervention_cycle_number` (compteur explicite dans `request.infos`, incrémenté uniquement par `reopen()` — nommé ainsi et non `cycle_number` pour ne jamais entrer en collision avec le `cycle_number` déjà existant de BR-TRANSMIT-001, sémantique différente). Câblés dans `assign()`, `update()` (self-assign/take-ownership/qualify_triage), `transmit_treatment()` (ferme l'intervention de l'émetteur, ouvre celle du destinataire) et `resolve()`. Commentaires et pièces jointes sont rattachés à l'intervention ouverte de leur auteur uniquement s'il est l'intervenant courant du ticket (sinon restent visibles dans l'historique, hors conteneur — ex. message du demandeur). `ModelRequest.interventions` (nouvelle propriété) reconstruit la liste des interventions en lisant exclusivement ces métadonnées explicites, sans aucun recalcul.

Fichiers modifiés:
- `backend/api/services/ServiceRequest.py` (`_actor_identity_snapshot`, `_open_intervention`, `_current_intervention_meta`, `_intervention_meta_for_actor`, câblage `assign`/`update`/`transmit_treatment`/`resolve`/`reopen`)
- `backend/api/routes/RouteRequest.py` (rattachement `comment_added`/`attachment_added`)
- `backend/api/models/ModelRequest.py` (`interventions`)
- `backend/api/schemas/SchemaRequest.py` (`InterventionResponse`, `RequestResponse.interventions`)
- `backend/api/services/ServiceReport.py` (`intervention_stats`, additif ; `noload(assignee/requester)` ajouté aussi à `sla_reopen_stats` — voir note ci-dessous)
- `backend/api/routes/RouteReports.py` (`GET /reports/interventions`)
- `frontend/src/lib/mock-data.ts` (`Intervention`), `frontend/src/lib/api/requests.ts` (`RawIntervention`, `mapIntervention`), `frontend/src/lib/api/reports.ts` (`fetchInterventionStats`)
- `frontend/src/components/intervention-journal.tsx` (nouveau — journal hiérarchique Cycle → Intervention, dépliable)
- `frontend/src/routes/app.requests.$id.tsx` (bascule "Interventions" / "Tous les événements" dans l'onglet Journal)
- `frontend/src/routes/app.sla-center.tsx` (rangée KPI "Interventions" + tableau par agent)
- `backend/tests/api/test_trace_interventions.py` (nouveau, 7 tests)
- `docs/codex/BUSINESS_RULES.md`, `WORKFLOW_INDEX.md`, `API_INDEX.md`, `FEATURE_INDEX.md`

Verification: `pytest tests/api/test_trace_interventions.py` → 7/7 passed. `pytest tests/api` (suite complète) → 217 passed / 52 échecs préexistants, mêmes échecs que la baseline documentée (aucune régression). `npx tsc --noEmit`, `eslint` (hors bruit `prettier/prettier` préexistant) et `npm run build` : 0 nouvelle erreur, succès.

Bug détecté et corrigé en cours de route (hors périmètre initial, découvert en testant à pleine charge) : `intervention_stats()`/`sla_reopen_stats()` chargent les demandes via l'ORM sans restriction, déclenchant le chargement automatique (`lazy="selectin"`) des comptes `assignee`/`requester` — un compte de test préexistant ailleurs dans la suite avec `role="agent"` (valeur héritée, hors du vocabulaire actuel à 7 rôles, présente dans plusieurs fichiers de tests non liés à ce lot) faisait échouer ce chargement (`KeyError` SQLAlchemy sur l'Enum du rôle), uniquement visible en exécutant la suite complète (jamais en isolation). Corrigé par `noload(RequestModel.assignee)`/`noload(RequestModel.requester)` sur les deux requêtes (relations non utilisées par ces rapports) — contournement ciblé et minimal ; le bug de fixture lui-même (`role="agent"` litéral dans les tests) reste hors périmètre, pré-existant, de la même famille que le bug ENUM `activity_log.actor_role` déjà documenté.

Point signalé (best-effort, non bloquant, hérité de BR-SLA-REOPEN-001) : `sla_response_hours` reste une approximation ; le temps de résolution/transmission, seule mesure exploitée par le scénario métier de traçabilité fourni, reste totalement fiable.

## 2026-08-04 - Gestion du SLA lors d'une réouverture — cycles indépendants (BR-SLA-REOPEN-001)

Demande: définir officiellement la gestion du SLA lors d'une réouverture — conserver l'historique complet du premier SLA tout en démarrant une nouvelle période SLA à la réouverture, pour mesurer indépendamment la performance du premier traitement et celle de chaque traitement après réouverture, y compris sur plusieurs réouvertures successives, sans jamais perdre ni recalculer rétroactivement les données historiques.

Module: MOD-WORKFLOW / MOD-CHIEF / MOD-DIRECTION / MOD-REPORT (BR-SLA-REOPEN-001, étend BR-REOPEN-QUEUE-001).

Cause: `request.sla_hours`/`sla_elapsed`/`sla_breached` sont des compteurs plats, uniques par ticket, recalculés en continu par le scheduler (`EscaladeService.mark_sla_breached`, `TIMESTAMPDIFF(HOUR, r.created_at, NOW())`) — aucune notion de "cycle" n'existait avant ce lot : une réouverture ne faisait que repasser le statut à `reopened`, sans jamais réinitialiser ni recalculer ces compteurs depuis la date de réouverture, ce qui aurait cumulé le temps du premier traitement avec celui du second dans une seule mesure, sans distinction possible.

Analyse préalable (conforme à la démarche demandée) : le modèle actuel ne permet de représenter qu'un seul cycle "live" à la fois, mais `workflow_detail` (append-only, déjà le mécanisme central de BR-TRANSMIT-001/BR-REOPEN-QUEUE-001) permet de reconstruire l'historique complet de tous les cycles clos sans aucune nouvelle table ni colonne — chaque résolution (`treatment_completed`) peut geler un instantané SLA du cycle qu'elle clôture, définitivement, dans ses `infos`. Solution retenue : extension minimale de la structure existante, aucune nouvelle table.

Correctif: `ServiceRequest._sla_cycle_snapshot()` (nouveau) calcule et fige, à chaque `resolve()`, un instantané du cycle qui se termine (`sla_cycle_number`, `sla_cycle_started_at` — date de la dernière réouverture ou de création si jamais réouvert —, `sla_hours_target`, `sla_elapsed_hours`, `sla_response_hours` best-effort, `sla_breached`, `sla_reopen_reason`), écrit dans l'événement `treatment_completed` et plus jamais modifié ensuite. `ServiceRequest.reopen()` réinitialise les compteurs "live" (`sla_breached=False`, `sla_elapsed=0`) dans la même écriture atomique que le retour en file d'attente (BR-REOPEN-QUEUE-001), pour éviter qu'un ticket déjà hors-délai avant réouverture ne déclenche une escalade automatique immédiate sur son nouveau cycle. `EscaladeService.mark_sla_breached()` ancre désormais son calcul sur la dernière réouverture du ticket (sous-requête sur `workflow_detail`/`workflow`, `COALESCE(dernier 'reopened', created_at)`) plutôt que systématiquement sur `created_at`. `ModelRequest.sla_cycles`/`reopen_count` (nouvelles propriétés) reconstruisent la liste complète des cycles (clos = lecture pure de l'instantané gelé, jamais recalculé ; cycle courant = calcul en direct) et sont exposées sur `RequestResponse` (détail ticket uniquement). `ServiceReport.sla_reopen_stats()` (nouveau, `GET /reports/sla/reopen-stats`) fournit les KPI agrégés (tickets réouverts, taux de réouverture, durée moyenne 1er cycle vs post-réouverture, conformité SLA par type de cycle) sans toucher à aucun rapport existant.

Fichiers modifiés:
- `backend/api/services/ServiceRequest.py` (`_sla_cycle_snapshot` nouveau, `resolve` enrichi, `reopen` reset live)
- `backend/api/services/ServiceEscalade.py` (`mark_sla_breached` — ancre sur la dernière réouverture)
- `backend/api/models/ModelRequest.py` (`sla_cycles`, `reopen_count`)
- `backend/api/schemas/SchemaRequest.py` (`SlaCycleResponse`, `RequestResponse.sla_cycles`/`reopen_count`)
- `backend/api/services/ServiceReport.py` (`sla_reopen_stats`, additif)
- `backend/api/routes/RouteReports.py` (`GET /reports/sla/reopen-stats`, additif)
- `frontend/src/lib/mock-data.ts` (`SlaCycle`, `RequestItem.slaCycles`/`reopenCount`)
- `frontend/src/lib/api/requests.ts` (`RawSlaCycle`, `mapSlaCycle`)
- `frontend/src/lib/api/reports.ts` (`SlaReopenStats`, `fetchSlaReopenStats`)
- `frontend/src/routes/app.requests.$id.tsx` (blocs cycles SLA dans l'onglet "Activité SLA")
- `frontend/src/routes/app.sla-center.tsx` (rangée KPI "Réouvertures")
- `backend/tests/api/test_sla_reopen.py` (nouveau, 2 tests exécutés + 1 skip documenté)
- `docs/codex/BUSINESS_RULES.md`, `API_INDEX.md`, `FEATURE_INDEX.md`

Verification: `pytest tests/api/test_sla_reopen.py` → 2 passed, 1 skipped (raison documentée : `mark_sla_breached()` utilise une syntaxe `UPDATE...JOIN` MySQL non supportée par SQLite, déjà jamais couverte par aucun test avant ce lot — précédent identique déjà établi dans `test_decision_report_director_scope.py`). Scénario testé : 3 cycles SLA successifs (2 réouvertures), avec changement de la cible SLA (`sla_hours`) entre le 2e et le 3e cycle — vérifie explicitement que les cycles 1 et 2 déjà clos restent bit-à-bit identiques après coup, malgré le changement de cible et les réouvertures ultérieures. `pytest tests/api` (suite complète) → 210 passed / 52 échecs / 5 skipped, mêmes échecs préexistants que la baseline documentée (aucune régression). `npx tsc --noEmit` et `eslint` (hors bruit `prettier/prettier` préexistant) : 0 nouvelle erreur sur les fichiers touchés. `npm run build` : succès.

Point signalé (best-effort, non bloquant) : `sla_response_hours` ("temps de réponse") est approximé par le premier événement `assigné`/`en cours`/`transmis` après le début du cycle — aucune donnée dédiée "première réponse" n'existe dans le modèle (`sla_response_at` présent en base mais jamais alimenté par aucun code avant ce lot). Le temps de résolution, seule mesure exploitée par le scénario métier fourni, reste lui totalement fiable et ne dépend d'aucune approximation.

## 2026-08-04 - Retour automatique d'un ticket réouvert dans la File d'attente (BR-REOPEN-QUEUE-001)

Demande: corriger le blocage identifié par la vérification fonctionnelle du workflow dynamique (2026-08-04, conclusion "workflow partiellement dynamique") — après approbation d'une demande de réouverture, le ticket restait affecté à l'ancien intervenant (`assignee_id` inchangé) et hors File d'attente (`in_triage` inchangé), alors que `reopened` est volontairement exclu des statuts autorisant `transmit_treatment`/`resolve`. Plus personne ne pouvait transmettre, résoudre, ni reprendre le ticket — il restait bloqué indéfiniment.

Module: MOD-AGENT / MOD-CHIEF / MOD-WORKFLOW (BR-REOPEN-QUEUE-001, étend BR-REOPEN-001).

Cause: `ServiceRequest.reopen()` faisait uniquement passer `request_status` à `reopened` et nettoyait le flag `infos.reopen_requested` — sans jamais toucher `assignee_id` ni `in_triage`. La File d'attente (`RepositoryRequest.list_pending_triage`, `_QUALIFIABLE_STATUSES` incluant déjà `reopened`) et les capacités frontend (`capabilities.ts`, `self_assign`/`take_ownership` incluant déjà `reopened`) étaient déjà prêtes à accueillir un ticket réouvert non affecté — seul le service backend ne produisait jamais cet état.

Correctif: `ServiceRequest.reopen()` fixe désormais explicitement `assignee_id=None` et `in_triage=True` en plus du passage à `reopened`, dans la même mise à jour atomique. Un unique nouvel événement `workflow_detail` (`event_type="reopened"`) est ajouté — table append-only, aucun événement antérieur modifié ou supprimé — avec des `infos` enrichis (`previous_assignee_id`, `new_assignee_id`, `previous_status`, `reopen_reason` (dupliqué dans `comment` pour l'affichage direct dans la timeline), `reopen_requested_by`, `reopen_approved_by`, `reopened_at`, `previous_cycle_number`/`next_cycle_number`). Notifications nominatives (BR-NOTIF-001) : demandeur informé de l'approbation, ancien intervenant informé de la réouverture (jamais réaffecté), chef d'unité informé si distinct. Aucune réaffectation automatique nulle part — le ticket redevient une demande libre en attente, comme n'importe quel ticket non traité.

Fichiers modifiés:
- `backend/api/services/ServiceRequest.py` (`reopen` réécrit)
- `frontend/src/routes/app.queue.tsx` (badge `Réouverte` remplaçant "Non orientée" pour ce statut ; encart motif/ancien intervenant/date sur la carte dépliée, chargé à la demande via `fetchRequest`)
- `frontend/src/routes/app.requests.$id.tsx` (message "Ce ticket réouvert attend une nouvelle prise en charge." dans le panneau d'actions de traitement tant que `assignee_id` est null)
- `backend/tests/api/test_reopen_queue.py` (nouveau, 8 tests)
- `docs/codex/BUSINESS_RULES.md`, `WORKFLOW_INDEX.md`, `API_INDEX.md`, `FEATURE_INDEX.md`

Verification: `pytest tests/api/test_reopen_queue.py` → 8/8 passed. `pytest tests/api` (suite complète) → 208 passed / 52 échecs, tous identiques à la baseline préexistante documentée (aucune régression — mêmes échecs qu'avant ce changement). `npx tsc --noEmit` : 0 nouvelle erreur sur les fichiers touchés (erreurs préexistantes inchangées, même famille `fetchDirections`/`queryFn` déjà documentée, répandue sur des fichiers non liés à ce chantier). `eslint` (hors règle `prettier/prettier`, bruit CRLF préexistant sur tout le fichier) : 0 erreur, 1 warning préexistant sans rapport.

Point non tranché (signalé, non implémenté) : aucune règle SLA officielle ne documente le comportement attendu de `sla_hours`/`sla_elapsed`/`sla_response_at` lors du retour en file d'attente après réouverture. Non inventé, non modifié — option recommandée documentée dans BR-REOPEN-QUEUE-001 (`BUSINESS_RULES.md`), en attente de validation avant toute implémentation.

## 2026-08-03 - Workflow collaboratif dynamique post-file d'attente (BR-TRANSMIT-001) : "Transmettre le traitement" et "Terminer le traitement"

Demande: après la file d'attente, permettre un traitement collaboratif dynamique — nombre, ordre et rôles des intervenants inconnus à l'avance, choisis progressivement selon le besoin réel découvert pendant le traitement, sans jamais imposer une chaîne fixe ni un passage obligatoire par un chef de service.

Module: MOD-AGENT / MOD-CHIEF / MOD-DIRECTION / MOD-WORKFLOW (BR-TRANSMIT-001, remplace/assouplit Lot 2.6, Lot 3.2 et BR-DIRECTOR-RESOLVE-001 pour les deux actions concernées).

Cause: le système existant ne permettait pas de transmettre librement le traitement à un autre intervenant — seules des actions rigides existaient (`assign` self/chef-vers-agent, `reassign` changement de service, `escalate` auto-routage vers un chef hiérarchique). La résolution (`resolve`) était par ailleurs restreinte par rôle (chief-departement totalement exclu depuis le Lot 3.2, directeur limité aux tickets escaladés) plutôt que par la question "l'acteur est-il l'intervenant actuel ?", et le motif obligatoire n'existait que pour chief-service (Lot 2.6). Le mécanisme `create_circuit`/`accept_detail` existant (pattern edgrh) construit une chaîne d'étapes prédéfinie complète en un seul appel — incompatible avec un parcours découvert dynamiquement, volontairement non réutilisé.

Correctif: nouvelle garde générique `assert_is_current_handler` (`ticket_actions.py`) — la règle principale devient `request.assignee_id == actor.id` (le rôle n'est plus qu'un filtre parmi `agent-support`/`chief-service`/`chief-departement`/`director`, admin bénéficiant d'un bypass exceptionnel). Nouvelle action `transmit_treatment` (`POST /requests/{id}/transmit`) : transmission libre dans toute l'organisation (annuaire complet, aucune restriction de direction/service), motif + travail effectué obligatoires, statut du ticket toujours préservé (jamais forcé à `assigned`). Action `resolve` existante étendue plutôt que dupliquée : résumé/solution/travail réalisé désormais obligatoires pour tous les rôles traitants (remplace le motif "exceptionnel" réservé à chief-service), plus aucune restriction de rôle additionnelle (chief-departement et directeur peuvent terminer un traitement dès lors qu'ils sont l'intervenant actuel). Cycles d'intervention reconstruits uniquement depuis `workflow_detail` (append-only, aucune nouvelle table) : `cycle_number`, `started_at`/`ended_at`/`duration_seconds` calculés à la volée. Écriture atomique conditionnelle (`_atomic_conditional_update`, `UPDATE ... WHERE assignee_id=<attendu>`) pour refuser (409 `TICKET_STATE_CONFLICT`) toute transmission/résolution basée sur un état obsolète (transmission concurrente).

Fichiers modifiés:
- `backend/api/core/ticket_actions.py` (`TREATING_ROLES`, `COLLABORATIVE_STATUSES`, `assert_is_current_handler`, `resolve` rouvert à chief-departement, contrainte director-escaladé-only retirée, `assert_exceptional_resolve_reason` supprimée)
- `backend/api/core/error_codes.py` (`TICKET_STATE_CONFLICT`)
- `backend/api/services/ServiceRequest.py` (`resolve` réécrit, nouvelle méthode `transmit_treatment`, helpers `_atomic_conditional_update`/`_next_treatment_cycle`)
- `backend/api/routes/RouteRequest.py` (`POST /requests/{id}/resolve` body étendu, nouveau `POST /requests/{id}/transmit`, validation des pièces jointes factorisée)
- `frontend/src/lib/api/requests.ts` (`resolveRequest` signature étendue, nouveau `transmitTreatment`)
- `frontend/src/lib/capabilities.ts` (`transmit_treatment`, `resolve` requiert `isAssignedToMe`, `chief-departement` rétabli sur `resolve`)
- `frontend/src/routes/app.requests.$id.tsx` (boutons "Transmettre le traitement"/"Terminer le traitement", modales dédiées avec annuaire cascadé Direction→Département→Service→Recherche, suppression de l'ancien flux "Marquer résolue")
- `frontend/src/routes/app.direction.tsx` (modale de résolution alignée sur les nouveaux champs obligatoires, restriction "escaladé uniquement" retirée)
- `frontend/src/components/workflow-timeline.tsx` (icônes/couleurs `treatment_transmitted`/`treatment_completed`, affichage travail effectué + durée du cycle)
- `frontend/src/lib/realtime/invalidation-map.ts` (`request.transmitted`)
- `backend/tests/api/test_transmit_treatment.py` (nouveau, 12 tests)
- `backend/tests/api/test_ticket_actions.py`, `test_lot3_narrowing.py`, `test_cdc_alignment.py`, `test_resolve_exceptional_reason.py` (adaptés à la nouvelle règle)
- `docs/codex/BUSINESS_RULES.md`, `WORKFLOW_INDEX.md`, `API_INDEX.md`, `ROLE_INDEX.md`, `FEATURE_INDEX.md`

Verification: `pytest tests/api` → 200 passed (+18 par rapport à l'état de départ), 52 échecs tous confirmés préexistants et sans rapport (bug SQLite documenté sur `/assign`, bug enum `role="agent"` dans un helper de fixture, module homepage-slides déjà cassé — KI-HOMEPAGE-001, etc. — vérifiés un par un, aucune régression sur `assign`/`reassign`/`escalate`/`create_circuit`). `npx tsc --noEmit` : 0 nouvelle erreur dans les fichiers touchés (erreurs préexistantes inchangées, même famille que celle déjà documentée dans l'entrée du 2026-08-03 ci-dessous, répandue sur 11 fichiers non liés à ce chantier). `npm run build` : succès. Bug détecté et corrigé en cours de route : l'écriture atomique anti-concurrence utilisait un `UPDATE` SQL brut puis un nouveau `SELECT`, renvoyant l'objet ORM encore en cache (non rafraîchi) — corrigé via `session.refresh()` sur l'objet déjà chargé.

Points non traités (hors périmètre, signalés) : pas de framework de tests unitaires/e2e frontend dans ce projet (aucun `vitest`/`jest`/`playwright` configuré) — vérification frontend limitée à `tsc --noEmit`, `eslint` et `npm run build` réussis, sans exécution manuelle en navigateur ni tests automatisés des 12 scénarios frontend demandés. Le bug préexistant `queryFn: fetchDirections` (référence directe incompatible avec la signature `QueryFunctionContext` de TanStack Query, ~11 fichiers) n'a pas été corrigé — hors périmètre de cette demande, déjà présent avant cette session.

## 2026-08-03 - Fil "Discussions" (ex-"Commentaires") : réponse ciblée réelle, alignement viewer-relatif, badge bidirectionnel

Demande: renommer l'onglet "Commentaires" en "Discussions" et le bouton de traitement associé ("Demander des infos" → "Ouvrir une discussion"), puis corriger trois défauts du fil : le bouton "Répondre" ne faisait que préfixer `@nom` sans lien réel vers le message ciblé ; l'indentation gauche/droite était un raccourci à 3 états incohérent au-delà de 2 échanges ; le badge "réponse attendue" n'existait que côté demandeur et seulement en statut `pending`.

Module: MOD-REQUEST-DETAIL (BR-COMMENT-LOCK-001).

Cause: les commentaires ne sont pas une table dédiée mais des lignes `workflow_detail` (`event_type='comment_added'`). Le champ `workflow_detail.parent_id` existe déjà mais sert exclusivement au chaînage d'audit du workflow entier et à la hiérarchie des étapes de traitement (`list_root_nodes`/`list_children`/`get_current_step`) — impropre à réutiliser pour un lien de réponse sans collision. L'ancienne indentation (`commentDepth`, 3 états sur la parité de l'index) et le badge (`isRequesterView && r.status === "pending"`) étaient des heuristiques approximatives, non fiables au-delà du cas d'usage initial (une seule relance agent → réponse demandeur).

Correctif: nouveau champ `infos.reply_to_id` sur l'événement `comment_added` (même pattern que `is_directive`/`attachment_id` déjà stockés dans `infos`, colonne JSON passthrough — aucune migration nécessaire), validé côté backend via la nouvelle méthode `WorkflowDetailRepository.get_comment_by_id_for_request` (422 si la cible n'existe pas, n'est pas un commentaire, ou appartient à une autre demande). Alignement des bulles rendu viewer-relatif (`isMine = isRequester(c.authorId, sessionUser?.id)`, réutilise le helper déjà utilisé par `canDeleteComment`) : chaque utilisateur voit ses propres messages à droite, ceux des autres à gauche, quel que soit son rôle. Badge "réponse attendue" recalculé par camp (demandeur vs personnel) plutôt qu'individuellement, sans condition de statut — seule la garde d'existence du fil (non archivé/clôturé/rejeté) est conservée. Détail complet de la logique dans `docs/codex/BUSINESS_RULES.md` (BR-COMMENT-LOCK-001).

Fichiers modifiés:
- `backend/api/routes/RouteRequest.py` (`_CommentBody.reply_to_id`, `create_comment`)
- `backend/api/repositories/RepositoryWorkflowDetail.py` (`get_comment_by_id_for_request`)
- `frontend/src/lib/api/requests.ts` (`mapRequest`, `mapComment`, `CreateCommentData`, `createComment`)
- `frontend/src/lib/mock-data.ts` (`RequestItem.comments.replyToId`)
- `frontend/src/routes/app.requests.$id.tsx` (état `replyToId`, alignement, `needsUserResponse`, libellés "Discussions"/"Ouvrir une discussion")
- `backend/tests/api/test_directive_comment.py` (4 tests ajoutés)
- `docs/codex/BUSINESS_RULES.md`

Verification: `pytest tests/api/test_directive_comment.py` → 9 passed (5 existants + 4 nouveaux : round-trip `reply_to_id`, réponse vers une autre demande rejetée, réponse vers un id inexistant rejetée, réponse vers un événement non-commentaire rejetée). `python -m compileall` sur les 2 fichiers backend touchés. `npx tsc --noEmit` : 0 nouvelle erreur dans les fichiers touchés (13 erreurs pré-existantes inchangées dans `app.requests.$id.tsx`, aucune dans `requests.ts`/`mock-data.ts`). Grep de cohérence `reply_to_id`/`replyToId` (lecture/écriture alignées) et `parent_id` (aucun nouvel usage sur `WorkflowDetail`, confirmant l'absence de collision avec le chaînage d'audit existant).

Effet de bord assumé: le connecteur d'angle et la ligne verticale du fil (liés à l'ancien indice de profondeur à 3 états) sont retirés — sans équivalent cohérent dans une mise en page à deux colonnes symétrique. Hors périmètre (observé, non corrigé) : le mapper inline `mapRequest()` n'inclut pas les champs de pièce jointe (`attachmentId`/`attachmentName`/`attachmentMime`/`attachmentSize`) alors que le rendu du fil les lit sur chaque commentaire — possible régression préexistante, sans rapport avec cette demande, signalée mais non traitée.

## 2026-08-01 - Fix : erreur rouge incohérente après clôture/résolution d'un ticket alors que l'action avait bien fonctionné

Demande: signalement utilisateur — en cliquant sur "Confirmer" dans la modale de clôture (`app.requests.$id.tsx`), un message d'erreur rouge apparaissait alors que le ticket était en réalité bien clôturé en base.

Module: MOD-REQUEST-DETAIL (actions `resolve`/`close`/toute action passant par `NotificationEmitter.emit`).

Cause: `NotificationEmitter.emit()` (`backend/api/services/NotificationEmitter.py`) envoyait l'email de notification automatique via `await send_notification_email(...)`, **dans le chemin critique** de la requête HTTP (close/resolve/assign/escalade/...). L'envoi SMTP réel (Gmail, `aiosmtplib`) prend 9 à 13s en conditions normales sur ce poste — dangereusement proche, voire au-delà, du timeout client de 15s (`REQUEST_TIMEOUT_MS` dans `frontend/src/lib/api/client.ts`). Quand le client abandonnait la requête (timeout), le backend continuait et committait quand même la mutation (déjà faite avant l'envoi d'email) — d'où l'incohérence : ticket réellement clôturé/résolu en base, mais toast rouge générique côté frontend (`closeMut`/`resolveMut` affichent un message fixe qui ignore la vraie cause de l'erreur). Reproduit et confirmé via appel direct du service (`RequestService.resolve/close`) et de l'endpoint HTTP réel (`httpx.ASGITransport`) sur des tickets de test, avec chronométrage avant/après correctif.

Correctif: l'envoi d'email devient fire-and-forget (`asyncio.create_task`, référence forte conservée dans `_background_email_tasks` pour éviter la garbage-collection prématurée) au lieu d'être attendu (`await`) dans le chemin de réponse. Aucun changement de comportement pour l'email lui-même (toujours envoyé, toujours best-effort/silencieux en cas d'échec — le `try/except` existant dans `send_notification_email` gère déjà ça) ; seul le blocage de la réponse HTTP est supprimé. Correctif unique, localisé à `NotificationEmitter.emit()` — bénéficie automatiquement à toutes les actions qui notifient (close, resolve, assign, escalade, changement de priorité, etc.), sans toucher aux routes/services appelants.

Fichiers modifiés:
- `backend/api/services/NotificationEmitter.py`

Verification: `pytest tests/api/test_ticket_actions.py` → 70 passed. Reproduction chronométrée avant correctif (`/resolve` 9218ms, `/close` 12596ms, tous deux < 15s mais dangereusement proches) vs après correctif (`/resolve` 458ms, `/close` 249ms), sur les mêmes tickets de test, statuts restaurés après coup. Pas de test automatisé dédié ajouté (fire-and-forget difficile à tester unitairement sans mock SMTP — hors périmètre de cette correction ciblée).

Effet de bord assumé: aucun — l'email reste envoyé (juste en arrière-plan) ; en cas d'échec SMTP il est toujours silencieusement journalisé (`logger.warning`), comme avant.

## 2026-08-01 - Chantier "File d'attente / actions par rôle" (Lots 1 à 5) — vues et actions différenciées par rôle

Demande: faire évoluer la vue "liste des tickets" et ses actions selon le rôle connecté (Agent Support, Chef de Service, Chef de Département, Direction DSI), sans dupliquer les composants — architecture commune paramétrée. Réalisé en 5 lots validés séparément, avec arrêt explicite avant chaque retrait de capacité RBAC.

Module: MOD-CHIEF, MOD-DIRECTION, MOD-REPORT (BR-ROLE-CHIEF-001, BR-ROLE-CHIEF-DEPARTEMENT-001/002, BR-ESCALATE-EXCEPTIONNELLE-001, BR-DIRECTIVE-001, BR-ROLE-DIRECTOR-001, BR-REPORT-DECISION-001).

**Lot 1 — Fondations backend**
- Correctif de périmètre `_apply_decision_scope` (`RouteReports.py`) : chief-departement était borné à sa seule unité dans `/reports/decision`, alors qu'il doit voir tout son département (réutilisation de `ServiceReport._scoped_unity_ids()`, déjà existante). `_decision_conditions` accepte désormais `unity_id` en liste (`IN (...)`).
- Nouvel endpoint `GET /requests/workload-by-unit` (charge active par agent, statuts non terminaux).

**Lot 2 — Chef de Service ("Centre de répartition")**
- Verrou sécurité sur `PATCH /requests/{id}` : absence totale de contrôle de périmètre avant ce lot (uniquement `require_roles`) — tout staff pouvait modifier n'importe quel ticket hors de son unité. Ajout de `_resolve_access` + restriction des champs acceptés pour le staff non-admin à `{request_status, status_reason}` (seul usage front réel identifié).
- Panneau "Charge par agent" dans `ChiefInbox`. Correctif `isToAssign()` (gardait à tort les tickets déjà assignés visibles).
- Narrowing : agent-support perd l'accès au routage vers un tiers dans `/app/queue` (`qualify_triage` + UI) — ne garde que l'auto-assignation.
- Narrowing : chief-service perd l'accès à "Changer de service" (`reassign`/`change_service`).
- Nouveau concept : résolution "exceptionnelle" pour chief-service — motif obligatoire (`assert_exceptional_resolve_reason`).
- Nouveau concept : "Directive" — commentaire dédié chef → agent assigné, notification nominative, badge visuel distinct (BR-DIRECTIVE-001).

**Lot 3 — Chef de Département ("Centre de pilotage")**
- Narrowing : chief-departement perd l'accès à "Affecter/Réaffecter" (`assign`) et "Traiter/résoudre" (`resolve`) — ne traite plus jamais un ticket lui-même.
- Nouveau concept : "Escalade exceptionnelle" — action `escalate_to_director` (nouvelle route `POST /{id}/escalate-to-director`, nouvelle fonction `find_director_for_department`), court-circuite `find_hierarchical_chief`, cible directement le directeur, motif obligatoire. **Attention collision de nom** avec l'alias local `escalateToDirector` déjà existant dans `app.supervision.tsx` (import renommé de `escalateRequest` depuis `escalations.ts`, comportement différent) — voir note détaillée dans BR-ESCALATE-EXCEPTIONNELLE-001.
- Nouveau composant partagé `components/aggregated-service-dashboard.tsx` (mode `"pilotage"`), consommant `GET /reports/decision?group_by=service` déjà entièrement câblé côté frontend — aucun nouveau code API. Devient l'écran principal de `/app/department-inbox` ; drill-down vers `ChiefInbox` (nouvelle prop optionnelle `filterUnitId`/`onBackToOverview`, comportement de `/app/chief-inbox` strictement inchangé).

**Lot 4 — Direction DSI ("Tableau de bord stratégique")**
- Nouvelle route additive `/app/strategic-dashboard` (guard `director` uniquement), réutilise `AggregatedServiceDashboard` en mode `"strategic"` (lecture seule) + résumé exécutif (`data.kpis`, déjà présent dans la même réponse). Aucun retrait de capacité à director (`/app/direction`, `/app/supervision` inchangés).
- Entrée de navigation ajoutée au groupe "Pilotage" (sidebar desktop + tiroir hamburger mobile) ; barre de navigation mobile basse à 5 icônes non modifiée (choix explicite pour ne retirer aucun raccourci existant).
- **Découverte** (voir KI-SQL-001 dans `KNOWN_ISSUES.md`) : `GET /reports/decision` est inexécutable via HTTP dans la suite de tests SQLite (`GROUP_CONCAT(...SEPARATOR...)`, syntaxe MySQL uniquement) — bug pré-existant, sans lien avec ce chantier, jamais couvert par un test HTTP avant ce lot. Non corrigé (hors périmètre, dette technique séparée à traiter dans un chantier dédié de portabilité SQL).

**Lot 5 — Renommage des libellés + documentation**
- Libellés alignés sur la terminologie validée : "Centre de répartition" (chief-service), "Centre de pilotage" (chief-departement), "Tableau de bord stratégique" (director, Lot 4). Mis à jour : `app-layout.tsx` (sidebar, tiroir hamburger, barre mobile), `app.chief-inbox.tsx` (titre d'onglet + H1), `app.requests.$id.tsx` (eyebrow/backLabel de contexte), `app.index.tsx` (liens rapides d'accueil par rôle — ajout au passage du lien manquant vers `/app/strategic-dashboard` pour director, oubli du Lot 4).
- Correction mineure trouvée en cours : `ROUTE_INDEX.md` listait `director` parmi les rôles de `/app/queue`, alors que le guard réel (`requireRole("agent-support", "chief-service", "admin")`) ne l'a jamais inclus — corrigé.
- `docs/codex/` mis à jour : `FEATURE_INDEX.md` (FEATURE-CHIEF-INBOX scindée, nouvelles FEATURE-DEPARTMENT-PILOTAGE et FEATURE-STRATEGIC-DASHBOARD), `MODULE_INDEX.md` (MOD-CHIEF, MOD-DIRECTION), `ROUTE_INDEX.md`, `BUSINESS_RULES.md` (BR-ROLE-CHIEF-001/CHIEF-DEPARTEMENT-001/002 réécrites pour refléter les narrowings, nouvelles BR-ESCALATE-EXCEPTIONNELLE-001, BR-DIRECTIVE-001, note scope chief-departement sur BR-REPORT-DECISION-001), `KNOWN_ISSUES.md` (KI-SQL-001).

Fichiers modifiés (cumul des 5 lots — liste non exhaustive, voir BUSINESS_RULES.md par règle) :
- Backend : `ticket_actions.py`, `RouteRequest.py`, `RouteReports.py`, `ServiceRequest.py`, `ServiceReport.py`, `ServiceEscalade.py`, `RepositoryRequest.py`.
- Frontend : `capabilities.ts`, `requests.ts`, `reports.ts` (inchangé, déjà complet), `app.queue.tsx`, `app.chief-inbox.tsx`, `app.department-inbox.tsx`, `app.requests.$id.tsx`, `app-layout.tsx`, `app.index.tsx`, `mock-data.ts`, nouveaux `components/aggregated-service-dashboard.tsx` et `routes/app.strategic-dashboard.tsx`.
- Tests (nouveaux, 100+ cas) : `test_reports_decision_scope.py`, `test_requests_workload.py`, `test_requests_patch_scope.py`, `test_qualify_narrowing.py`, `test_resolve_exceptional_reason.py`, `test_directive_comment.py`, `test_lot3_narrowing.py`, `test_escalate_to_director.py`, `test_decision_report_director_scope.py` (2 tests skip documentés, voir KI-SQL-001), extensions `test_ticket_actions.py`.

Verification: suite backend ciblée systématiquement verte à chaque lot ; suite complète comparée en isolé avant/après chaque lot — total d'échecs stable (52, tous pré-existants et non liés à ce chantier, vérifiés un par un par exécution isolée par fichier) du Lot 2 au Lot 4 inclus. `npx tsc --noEmit` propre sur tous les fichiers frontend touchés à chaque lot. Build production (`npm run build`) réussi après le Lot 4. Pas de vérification navigateur interactive (session non interactive, pas de serveur+données de seed disponible) — recommandé avant mise en production.

Effet de bord assumé: aucun — chaque narrowing RBAC a fait l'objet d'une confirmation explicite séparée avant application (diffs présentés à l'avance), et chaque ajout (Directive, Escalade exceptionnelle, Tableau de bord stratégique) est additif, sans retrait de capacité non validé.

## 2026-07-31 - Escalade : plus de choix manuel de niveau, routage automatique vers le chef hiérarchique

Demande: "pour les escalde, on a pas besoin de faire un choix, on doit juste remplir la partie motif, puis le systeme envoie uniquement au chef hierarchie de celui qui fait le traitement uniquement" — retirer le selecteur "Niveau cible" de la modale d'escalade et faire en sorte que le systeme determine seul le destinataire (chef hierarchique de la personne qui traite le ticket), sans choix manuel.

Module: MOD-AGENT / MOD-CHIEF / MOD-DIRECTION (BR-ESCALATE-AUTO-CHIEF-001).

Fichiers modifies:
- `backend/api/routes/RouteRequest.py`
- `backend/api/services/ServiceEscalade.py`
- `frontend/src/routes/app.requests.$id.tsx`
- `frontend/src/lib/api/requests.ts`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: la modale "Escalader la demande" exigeait de choisir un "Niveau cible" (`Chef de service`/`Directeur`/`Résolution`, valeurs figées de `DEFAULT_LEVELS.slice(3, 6)`) qui n'était de toute façon jamais reliée à un vrai compte destinataire — l'API acceptait ce libellé comme simple texte et ne réassignait jamais le ticket à qui que ce soit de concret.

Correction: `EscalateBody` est réduit à `{ reason }`. La route `POST /requests/{id}/escalate` détermine désormais elle-même le destinataire : la personne qui traite le ticket (`assignee_id`, ou l'acteur lui-même si non assigné), puis remonte à son chef hiérarchique via la nouvelle fonction partagée `find_hierarchical_chief` (`ServiceEscalade.py`) — chef dans la même unité (hors le traitant lui-même, pour le cas où un chef escalade son propre ticket), sinon remontée de l'organigramme vers l'unité parente à la recherche d'un chef ou d'un directeur. Si personne n'est trouvé, 422 explicite au lieu d'une escalade dans le vide. Le ticket est réassigné au chef trouvé (même schéma que l'escalade automatique SLA) et celui-ci est notifié. `EscaladeService._find_chief` (auto-SLA) délègue maintenant à cette même fonction, ce qui corrige au passage un bug préexistant (recherche d'un role littéral `"chief"` invalide dans l'enum). Côté frontend, la modale ne demande plus que le motif ; le Select "Niveau cible", l'état `escalateLevel`, l'import `DEFAULT_LEVELS` et les imports `Select*` désormais inutilisés sont retirés.

Verification: `npx tsc --noEmit` — même baseline préexistante (12 erreurs, aucune imputable) ; `npx eslint` — même warning préexistant `unused eslint-disable directive`, zéro nouvelle erreur ; `python -m py_compile` sur les 2 fichiers backend modifiés — OK ; comparaison `git stash` des tests `TestAssignationEscaladeRoles` avant/après ce changement — mêmes 9 échecs/6 succès des deux côtés (échecs préexistants, dus à une erreur 500 sur `/assign` en environnement de test SQLite, sans lien avec cette modification).

Effet de bord assumé: `app.supervision.tsx` (bouton "Transférer au Directeur" d'une escalade déjà en cours, via `escalations.ts`) appelle le même endpoint et bénéficie désormais de la même résolution automatique — il réassigne réellement le ticket au directeur trouvé (avant, cette action ne réassignait jamais personne en pratique). Comportement jugé cohérent avec l'intitulé du bouton ; aucun changement de code sur ce fichier.

## 2026-07-29 - Onglet Traitement : boutons d'action en grille 3 colonnes (au lieu de l'empilement liste)

Demande: apres le passage en liste empilee (entree precedente), retour utilisateur explicite avec capture d'ecran montrant les 5 actions visibles empilees verticalement : "je ne veut pas voir cet empilement, je veux les affichage cote a cote en trois trois" — les actions de traitement doivent s'afficher en grille de 3 colonnes plutot qu'en pile verticale.

Module: MOD-AGENT / MOD-CHIEF / MOD-DIRECTION (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: `treatmentActionsPanel` passe du `<section>` liste plein-largeur (entree precedente) a un conteneur `<div className="grid grid-cols-1 gap-2 sm:grid-cols-3">` — 1 colonne sur mobile, 3 colonnes cote a cote a partir du breakpoint `sm`. Chaque item redevient une carte independante (`rounded-xl border p-3`, sans `border-b` puisqu'il n'y a plus d'empilement lineaire) au lieu d'une ligne separee par bordure. Aucun changement de `onClick`, de mutation ou d'etat `disabled`/`isPending` — uniquement le conteneur et l'enveloppe visuelle de chaque bouton. `requestActionsPanel` (actions demandeur + message "Aucune action disponible...") n'est pas touche, conformement au perimetre de la demande (non circle sur la capture).

Verification: `npx tsc --noEmit` — meme baseline preexistante (12 erreurs, aucune imputable a ce changement) ; `npx eslint --format json` filtre hors `prettier/prettier` — uniquement le warning `unused eslint-disable directive` deja preexistant a la ligne 720, zero nouvelle erreur.

## 2026-07-29 - Onglet Traitement : boutons d'action reformates en liste (comme requestActionsPanel)

Demande: dans l'onglet `Traitement`, afficher les boutons de traitement (Demarrer traitement, Reprendre le traitement, Escalader, Ajouter une note, Marquer resolue, etc.) sous le meme format que les actions existantes (liste de lignes pleine largeur avec icone/titre/sous-titre), au lieu de boutons "pilule" en ligne.

Module: MOD-AGENT / MOD-CHIEF / MOD-DIRECTION (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: `treatmentActionsPanel` passe d'une rangee de boutons `rounded-full` en `flex-wrap` a un `<section>` unique au format identique a `requestActionsPanel` — lignes plein-largeur empilees (icone + titre en gras + sous-titre), separees par `border-b`, meme conteneur (`rounded-[16px] border border-border/35 bg-background/25`). Chaque action (Approuver/Refuser reouverture, M'assigner, Demarrer traitement, Demander des infos, Reprendre le traitement, Escalader, Reassigner, Creer circuit, Changer priorite, Rejeter, Changer service, Transferer direction, Ajouter une note, Marquer resolue) conserve exactement le meme `onClick`, la meme mutation et le meme etat `disabled`/`isPending` qu'avant — seul le conteneur visuel change, aucune logique ni permission modifiee. Couleur par action alignee sur les conventions deja utilisees ailleurs dans l'app.

Verification: `npx tsc --noEmit` sans nouvelle erreur imputable au fichier (meme baseline preexistante, 12 erreurs) ; `npx eslint` — uniquement le warning `unused eslint-disable directive` deja preexistant, zero occurrence `prettier/prettier` et zero erreur de logique.

## 2026-07-29 - Retrait de la banniere d'en-tete "L'agent vous demande des informations complementaires"

Demande: suite au retrait du bandeau P10 (voir entree precedente), retirer aussi la banniere restante dans l'en-tete du ticket (meme message, sans bouton) — confirmee redondante par capture d'ecran, le lien `Repondre` en surbrillance du fil de commentaires suffit desormais a signaler qu'une reponse est attendue.

Module: MOD-PERSONAL, MOD-REQUEST (BR-COMMENT-LOCK-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: suppression du bloc `{needsUserResponse && (...)}` dans l'en-tete du ticket ("L'agent vous demande des informations complementaires" / "Repondez via la section commentaires ci-dessous..."). `needsUserResponse` reste utilise (uniquement) pour calculer `isAwaitingReply` sur le dernier commentaire du fil (voir entree precedente) — aucune variable devenue inutilisee.

Verification: `npx tsc --noEmit` sans nouvelle erreur imputable au fichier (baseline preexistante, 12 erreurs contre 13 precedemment — une erreur `TS2322` sur `RequesterCard`/`directions` a disparu independamment de ce changement) ; `npx eslint` — uniquement du bruit `prettier/prettier` (3649 occurrences) et le warning `unused eslint-disable directive` deja preexistant, zero erreur de logique.

## 2026-07-29 - Reponse attendue : retrait du bandeau P10, mise en evidence animee sur le fil de commentaires

Demande: supprimer le bandeau "Votre retour est attendu" + bouton `Repondre` dedie ; l'action de reponse doit passer uniquement par le lien `Repondre` deja present sous chaque commentaire, avec un fond vert anime signalant qu'une reponse est attendue, et un clic qui amene directement au champ de reponse.

Module: MOD-PERSONAL, MOD-REQUEST (BR-COMMENT-LOCK-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: suppression du bloc "P10 — Bandeau PENDING" (`GlassCard` pleine largeur avec titre, texte et bouton `Repondre` dedie), redondant avec le lien `Repondre` deja present sous chaque commentaire. A la place, le dernier commentaire du fil recoit une mise en evidence conditionnelle (`isAwaitingReply = needsUserResponse && index === visibleComments.length - 1`) — fond vert anime (`animate-pulse bg-success/20 ring-1 ring-success/50`) tant que le ticket est en statut `pending` cote demandeur, puisqu'aucun commentaire du demandeur n'a encore ete poste depuis le passage en attente, donc le dernier commentaire est necessairement celui de l'agent qui attend une reponse. Le clic ajoute desormais un `scrollIntoView` avant le `focus()` deja existant, pour amener directement au champ de reponse comme le faisait l'ancien bouton dedie. Options presentees a l'utilisateur et validees avant implementation : mise en evidence sur le dernier commentaire uniquement (pas sur tous les commentaires non repondus), et action au clic = scroll+focus sur le champ existant (pas de modal dediee). La banniere discrete de l'en-tete ("L'agent vous demande des informations complementaires", sans bouton) n'est pas concernee.

Verification: `npx tsc --noEmit` sans nouvelle erreur imputable au fichier (baseline preexistante inchangee) ; `npx eslint` — uniquement du bruit `prettier/prettier` (3748 occurrences) et le warning `unused eslint-disable directive` deja preexistant, zero erreur de logique.

## 2026-07-29 - Formulaire d'assignation a 4 niveaux obligatoires (File d'attente / A qualifier)

Demande: revoir le formulaire d'assignation de la File d'attente du Support General pour respecter strictement la hierarchie Direction -> Departement -> Service -> Personne, avec filtrage actif-uniquement, cascade de reinitialisation, messages de listes vides, et bouton `Assigner` desactive tant que le formulaire est incomplet.

Module: MOD-AGENT / MOD-CHIEF (BR-TICKET-QUALIFY-001, note formulaire 4 niveaux — nouvelle regle).

Fichiers modifies:
- `frontend/src/routes/app.queue.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: le formulaire de qualification (`QualifyTab`) est reorganise en 4 champs sequentiels reutilisant des fonctions API deja existantes (aucun endpoint/service backend cree ou modifie) :
- **Direction cible** — `fetchDirections({ status: "active" })`, toujours active.
- **Departement cible** (nouveau champ) — `fetchDepartments({ directionId, status: "active" })`, desactive tant qu'aucune direction n'est choisie.
- **Service cible** — `fetchUnits({ departmentId, status: "active" })` (auparavant filtre par direction, desormais par departement), desactive tant qu'aucun departement n'est choisi.
- **Personne cible** — fusion de `fetchUsers({ role: "agent-support", unit_id })` et `fetchUsers({ role: "chief-service", unit_id })` (dedupliques par id), desactive tant qu'aucun service n'est choisi. Le filtre `only_active=True` est deja applique cote backend (`list_by_role_and_unit`, `RepositoryAccount.py`), donc les comptes inactifs/bloques sont deja exclus sans changement necessaire. L'option "— Aucune (laisser la direction gerer)" est retiree : une personne precise doit toujours etre selectionnee.

Chaque changement de champ reinitialise tous les champs enfants (`directionId` change -> reset departement/service/personne ; `departmentId` change -> reset service/personne ; `unitId` change -> reset personne), y compris via les raccourcis de suggestion de routage existants (auto-application categorie -> direction). Un message explicite apparait sous chaque select vide ("Aucune direction active disponible.", "Aucun departement actif disponible pour cette direction.", "Aucun service actif disponible.", "Aucun employe autorise a traiter dans ce service."). Le bouton, renomme `Assigner` (etait `Valider l'orientation`), reste desactive tant que les 4 champs ne sont pas tous renseignes (`canAssign`). Soumission inchangee : `qualifyTriage(id, { category, priority, direction_id, unit_id, assignee_id }, actorId)` — `department_id` reste un filtre UI intermediaire, jamais envoye au backend (aucune colonne dediee, conforme au modele Direction -> Departement -> Unite via Unity + Organigram). Le bouton independant `Prendre la demande` (auto-assignation rapide de l'agent connecte, sans passer par ce formulaire) n'est pas concerne et reste inchange.

Point signale (voir aussi note dans BUSINESS_RULES.md): CLAUDE.md documente une regle deja en place ("routage dynamique", Module 1 termine) permettant de router une demande vers une direction ou un service seul sans designer de personne. Le nouveau formulaire rend la personne obligatoire pour ce bouton specifique — aucune contradiction backend (l'API `qualify_triage` garde `assignee_id` optionnel), mais cette page n'offre plus ce raccourci. A confirmer si c'est le comportement definitivement voulu.

Verification: `npx tsc --noEmit` — zero erreur sur `app.queue.tsx` (la baseline preexistante de 7 erreurs liees au typage `fetchDirections`/`realDirections` a disparu, resolue en passant par un appel explicite `() => fetchDirections({...})` au lieu de la reference de fonction nue comme `queryFn`) ; `npx eslint` — 590 occurrences, toutes `prettier/prettier`, zero erreur de logique.

## 2026-07-29 - Retrait de l'onglet "A prendre" de la File d'attente

Demande: sur `/app/queue`, supprimer l'onglet `A prendre` (confirme applicable a tous les roles ayant acces a la page) pour ne garder que `A qualifier`.

Module: MOD-AGENT / MOD-CHIEF (FEATURE-QUEUE-QUALIFICATION, BR-ROLE-AGENT-001).

Fichiers modifies:
- `frontend/src/routes/app.queue.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: retire entierement le selecteur d'onglets `A prendre`/`A qualifier` ainsi que la fonction `QueueTab` (recherche, filtres priorite/direction, vues liste/grille, selection multiple, dialogs Assigner/Escalader — ~600 lignes) — `QueuePage` rend directement `QualifyTab` (seul choix restant, pour `agent-support`, `chief-service` et `admin`, les 3 roles ayant acces a cette route). Le parametre d'URL `?tab=` et le type `Tab` associes sont supprimes avec le composant (aucune autre page ne s'appuyait sur ce parametre). Nettoyage des imports devenus inutiles dans ce fichier (`Checkbox`, `Input`, `Dialog*`, `LayoutToggle`, `PaginationBar`, `EscalationProgressBar`, `buildRequesterStepsFromStatus`, `DEFAULT_LEVELS`, `assignRequest`, `fetchQueue`, `useRole`, `apiFetch`, `Link`, `useNavigate`, `useCallback`, `AnimatePresence`/`motion`, `StatusBadge`, `Textarea`, `useEffect`, `format`, `fetchRefTable`) — verifie qu'aucun reste utilise ailleurs dans le fichier ; les fonctions partagees (`fetchQueue`, `assignRequest`) restent utilisees telles quelles par `app.chief-inbox.tsx`/`app.index.tsx`, aucune suppression globale. Le titre de page "File d'attente" (auparavant porte par `QueueTab`) est reintroduit dans l'en-tete de `QualifyTab` pour que la page conserve un titre.

Verification: `npx tsc --noEmit` retombe sur la meme baseline preexistante (typage `fetchDirections`/`realDirections` — non liee a ce changement) ; `npx eslint` — uniquement du bruit `prettier/prettier` (56 occurrences), zero erreur de logique, zero import residuel signale.

## 2026-07-29 - Correction bug critique : suppression de commentaire possible sur ticket cloture

Demande: une fois le bandeau "Les commentaires sont desactives - ticket cloture" affiche, il ne doit plus etre possible de supprimer/modifier un commentaire existant (capture d'ecran : menu `Supprimer` encore actif sur un commentaire malgre le bandeau).

Module: MOD-REQUEST (nouvelle regle BR-COMMENT-LOCK-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `backend/api/routes/RouteRequest.py`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: `canDeleteComment` (frontend) ne verifiait que la propriete du commentaire (auteur, ou role staff non-demandeur), sans jamais tenir compte du statut de la demande — le menu `Supprimer` restait donc actif meme quand le bandeau de verrouillage etait deja affiche. Cote backend, `DELETE /requests/{id}/comments/{comment_id}` n'avait aucun controle de statut non plus : un appel direct a l'API pouvait supprimer un commentaire sur un ticket cloture/rejete/archive, contournant totalement la restriction visuelle du frontend. Aucune fonctionnalite de modification (edition du texte) n'existe dans le code actuel — seule la suppression etait exposee et donc concernee.

Correction: `canDeleteComment` retourne desormais `false` des que `isArchived || r.status === "closed" || r.status === "rejected"`, la meme condition deja utilisee par le bandeau de verrouillage et le bouton `Repondre`. Cote backend, `delete_comment` leve une erreur `422` avec message explicite si `req.deleted_at is not None or req.request_status in {"closed", "rejected"}` — l'enforcement ne repose plus uniquement sur le masquage du bouton cote UI.

Corrections annexes (bugs preexistants decouverts pendant la verification TypeScript, non lies a la demande mais bloquants pour la compilation): `c.attachmentMimeType` (n'existe pas sur le type mappe) corrige en `c.attachmentMime` ; `formatFileSize` (fonction inexistante) corrige en `formatAttachmentSize` (helper deja defini plus haut dans le fichier). Ces deux coquilles venaient de la refonte recente du panneau Commentaires (bulles/avatars) et empechaient `tsc --noEmit` de passer sans erreur nouvelle.

Verification: `python -m compileall api/routes/RouteRequest.py` OK ; `npx tsc --noEmit` retombe exactement sur la baseline preexistante connue (13 erreurs `app.requests.$id.tsx`, 5 `app.requests.index.tsx`, typage `fetchDirections`/`Direction[]`) apres correction des deux coquilles ; `npx eslint` — uniquement du bruit `prettier/prettier` et un warning `unused eslint-disable directive` deja present avant cette session.

## 2026-07-29 - Detail ticket : reproduction maquette commentaires

Demande: reproduire typiquement la maquette fournie pour l'onglet `Commentaires` d'une demande/ticket, avec avatars de profil, bulles de discussion, pieces jointes et barre de publication.

Module: MOD-REQUEST / MOD-WORKFLOW (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: le panneau `commentsPanel` affiche maintenant les commentaires sous forme de fil conversationnel: avatars via `buildAvatarUrl`, bulles compactes avec nom + role, date + `Repondre`, menu visuel, indentation de reponse et carte de piece jointe avec telechargement. La barre de saisie reprend le modele de la maquette avec avatar, champ, trombone, reaction et bouton `Publier`. Les mutations `createComment`/`uploadAttachment`, les permissions, la visibilite public/interne et les endpoints ne changent pas.

Verification: `npm run build` frontend OK (client + SSR), avec les avertissements Vite habituels sur chunks volumineux/imports externes non utilises.

## 2026-07-29 - Notifications Lot 2 : matrice workflow vers acteurs précis

Demande: démarrer uniquement le Lot 2 du module Notifications, après validation de la table statuts officiels, pour compléter la matrice événements workflow -> destinataire précis sans changement RBAC, sans suppression physique et sans migration de statuts.

Correction: `ServiceRequest.py` notifie désormais la clôture au demandeur, l'annulation au demandeur et à l'agent assigné si distinct, et la réouverture acceptée au demandeur puis au prochain traitant précis (`assignee_id`) ou au chef d'unité si aucun agent n'est assigné. Les notifications restent créées via `NotificationEmitter`, donc publiées en SSE `notification.created` vers `target.user_ids=[recipient_id]`. Aucun statut (`qualified`/`escalated`/`cancelled`), endpoint, permission ou broadcast `request.*` n'est modifié dans ce lot.

Verification: `python -m compileall backend/api/services/ServiceRequest.py` OK. `backend\venv\Scripts\pytest.exe backend\tests\api\test_requests_baseline.py -q` lancé via `cmd.exe`: 36 passed, 21 failed; les échecs observés sont bloqués par l'état existant des fixtures/roles legacy (`KeyError: 'agent'` sur l'enum `role_enum`, alors que le référentiel actuel attend `agent-support`), pas par les notifications ajoutées dans ce lot.

## 2026-07-29 - Detail ticket : indicateurs delais sur une ligne

Demande: dans l'onglet `Délais de traitement`, afficher les blocs d'activite sur une seule ligne quand l'espace desktop le permet.

Module: MOD-REQUEST / MOD-WORKFLOW (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: la grille des 4 indicateurs passe en `xl:grid-cols-4`, avec padding reduit et textes tronques pour conserver une ligne propre en desktop. Le repli reste responsive en 2 colonnes tablette puis 1 colonne mobile. Aucun changement de calcul, donnees, permissions ou couleurs.

Verification: `npm run build` frontend OK (client + SSR), avec les avertissements Vite habituels sur chunks volumineux/imports externes non utilises.

## 2026-07-29 - Detail ticket : libelle SLA explicite

Demande: rendre l'onglet `SLA` plus explicatif en francais pour ameliorer l'ergonomie.

Module: MOD-REQUEST / MOD-WORKFLOW (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: le libelle visible de l'onglet passe de `SLA` a `Délais de traitement`. La cle interne `sla`, le contenu de l'onglet, les calculs, les couleurs et les permissions restent inchanges.

Verification: `npm run build` frontend OK (client + SSR), avec les avertissements Vite habituels sur chunks volumineux/imports externes non utilises.

## 2026-07-29 - Detail ticket : actions Traitement en modales

Demande: dans l'onglet `Traitement`, faire ouvrir une boite modale pour toutes les actions au clic, y compris celles qui etaient jusque-la directes ou affichees en section.

Module: MOD-REQUEST / MOD-WORKFLOW (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: `Demander des infos`, `Ajouter une note`, `Rejeter`, `Reassigner`, `Priorite`, `Service`, `Modifier` et `Annuler` ouvrent maintenant des modales `Dialog` au lieu de deployer un bloc dans la section. Les actions simples (`M'assigner`, `Demarrer traitement`, `Reprendre le traitement`, `Marquer resolue`, `Confirmer la resolution`, `Approuver reouverture`) passent par une modale de confirmation avant d'appeler les memes mutations. Les actions deja modales (`Escalader`, `Refuser reouverture`, `Transferer direction`, `Creer circuit`, `Rouvrir la demande`, `Votre avis`) restent sur ce pattern. Aucun changement de mutation, permission, endpoint ou workflow.

Verification: `npm run build` frontend OK (client + SSR), avec les avertissements Vite habituels sur chunks volumineux/imports externes non utilises.

## 2026-07-29 - Detail ticket : actions demandeur en modales dans Traitement

Demande: deplacer les blocs demandeur `Demande cloturee` et `Votre avis` dans l'onglet `Traitement`, sous forme de boutons d'action ouvrant une modale.

Module: MOD-REQUEST / MOD-WORKFLOW (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: les deux grands blocs pleine largeur sont retires du flux principal. L'onglet `Traitement` affiche maintenant les actions demandeur correspondantes: `Rouvrir la demande`/`Demande cloturee` ouvre une modale de reouverture ou d'information, et `Votre avis` ouvre une modale reutilisant `AppreciationForm`. Les mutations, permissions, donnees et couleurs existantes restent conservees.

Verification: `npm run build` frontend OK (client + SSR), avec les avertissements Vite habituels sur chunks volumineux/imports externes non utilises.

## 2026-07-29 - Detail ticket UX Lot 4 : timeline compacte

Demande: rendre le journal des actions plus scannable avec action, acteur et date en ligne principale, sans modifier l'ordre, les donnees, la limite initiale visible, l'expansion ni les couleurs.

Module: MOD-REQUEST / MOD-WORKFLOW (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/components/workflow-timeline.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: compactage strictement visuel de `WorkflowTimeline`: icones et espacements reduits, ligne principale action/acteur/date, suppression des badges secondaires redondants visibles sous chaque evenement, commentaires et motifs gardes dans un bloc discret. Quand le libelle principal indique generiquement `un agent`, il affiche le nom reel de `targetUserName` si disponible. Le controle `Voir tout`/`Reduire`, les 3 evenements visibles par defaut, l'ordre des evenements et toutes les couleurs restent inchanges.

Verification: `npm run build` frontend OK (client + SSR), avec les avertissements Vite habituels sur chunks volumineux/imports externes non utilises.

## 2026-07-29 - Detail ticket UX Lot 3 : onglets et zone de contenu

Demande: compacter les onglets et clarifier leur hierarchie visuelle sans supprimer d'entrees ni badges, sans toucher aux couleurs, a l'etat actif ou a la logique de rendu.

Module: MOD-REQUEST / MOD-WORKFLOW (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: reduction des paddings de la barre d'onglets et des panneaux de contenu, conservation du scroll horizontal local mobile, et ajout de separations visuelles non fonctionnelles avant les groupes `Commentaires/Fichiers` et `SLA/Traitement`. Les 6 onglets, leurs badges, l'etat actif, les couleurs existantes et le contenu affiche restent inchanges.

Verification: `npm run build` frontend OK (client + SSR), avec les avertissements Vite habituels sur chunks volumineux/imports externes non utilises.

## 2026-07-29 - Detail ticket UX Lot 2 : stepper compact

Demande: compacter le stepper de progression du detail ticket, en gardant les 5 etapes lisibles sur desktop, tablette et telephone, sans toucher aux couleurs ni a la logique.

Module: MOD-REQUEST / MOD-WORKFLOW (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: reduction strictement visuelle du stepper `TicketLifecycleStepper`: cercles plus petits, connecteurs recalés, padding de carte reduit, libelles/dates plus compacts avec tailles progressives selon largeur. `buildFixedLifecycleSteps`, les dates, les etats (`done`, `active`, `warning`, `pending`) et toutes les couleurs restent inchanges.

Verification: `npm run build` frontend OK (client + SSR), avec les avertissements Vite habituels sur chunks volumineux/imports externes non utilises.

## 2026-07-29 - Detail ticket UX Lot 1 : header et grille generale

Demande: lancer le Lot 1 de la refonte UX des pages detail demande/ticket, avec contrainte explicite: aucune modification de couleur autorisee.

Module: MOD-REQUEST / MOD-WORKFLOW (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: ajustement strictement visuel de la grille generale et de la carte haute partagee par les details tickets: repartition desktop proche 68/32, gutters/espacements plus aerés, titre du ticket rendu plus dominant, bloc SLA reduit typographiquement pour ne plus concurrencer le titre. Les couleurs existantes, badges, fonds, bordures, calcul SLA, routes, appels API, permissions et conditions d'affichage restent inchanges.

Verification: `npm run build` frontend OK (client + SSR), avec les avertissements Vite habituels sur chunks volumineux/imports externes non utilises.

## 2026-07-29 - Templates HTML SMTP pour les emails ticketing

Demande: reprendre pour l'application ticketing le principe du dossier `edgrh/templates`, afin que l'affichage des contenus de mail SMTP soit gere par des templates HTML.

Module: MOD-NOTIF / backend SMTP (BR-NOTIF-001).

Fichiers modifies:
- `backend/api/core/mailer.py`
- `backend/api/services/NotificationEmitter.py`
- `backend/templates/_ticket_notification_base.html`
- `backend/templates/ticket_confirmation_creation.html`
- `backend/templates/ticket_accuse_reception.html`
- `backend/templates/ticket_affectation.html`
- `backend/templates/ticket_changement_statut.html`
- `backend/templates/ticket_validation.html`
- `backend/templates/ticket_resolution.html`
- `backend/templates/ticket_cloture.html`
- `backend/templates/ticket_reouverture.html`
- `backend/templates/ticket_transfert.html`
- `backend/templates/ticket_alerte_sla.html`
- `backend/templates/ticket_rejet_annulation.html`
- `backend/templates/ticket_recu_paiement.html`
- `backend/templates/reset_code_email.html`
- `backend/templates/notification_email.html`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/DEPENDENCY_INDEX.md`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: le HTML des emails EDG Connect etait construit directement dans `mailer.py`, ce qui rendait la presentation difficile a maintenir et moins coherente avec la structure deja presente dans `edgrh/templates`.

Correction: creation de `backend/templates/` avec une base HTML commune, 12 templates evenementiels conformes a la maquette (creation, accuse de reception, affectation, changement de statut, validation, resolution, cloture, reouverture, transfert, alerte SLA, rejet/annulation, recu de paiement) et le template de code de reinitialisation. `mailer.py` choisit automatiquement la variante selon le titre/type de notification, rend le HTML via un mini-rendeur interne avec echappement HTML, integre le logo EDG en image inline CID et conserve les fonctions publiques existantes (`send_notification_email`, `send_reset_code_email`). `NotificationEmitter.py` enrichit les emails avec les details du ticket quand `request_id` est present. L'envoi SMTP et la decision `CommunicationSetting.email_on` restent inchanges.

Verification: `python .codex/render_email_check.py` OK (`render ok`, script temporaire supprime ensuite) et `python -m compileall backend/api/core/mailer.py backend/api/services/NotificationEmitter.py` OK.

Complement responsive: `_ticket_notification_base.html` ajoute une couche mobile/tablette (`@media only screen and (max-width: 520px)`) pour empiler header/footer, transformer les details en lignes verticales et couper les libelles longs. Verification ciblee: rendu des 12 variantes dans une page HTML temporaire + assertions sur `max-width:640px`, la media query mobile et `overflow-wrap:anywhere`; `python -m compileall backend/api/core/mailer.py backend/api/services/NotificationEmitter.py` OK.

## 2026-07-29 - Modification personnelle du ticket autorisee aussi en qualification

Demande: le demandeur ne voyait plus l'option "Modifier la demande" des que son ticket passait en statut "En qualification" (`qualifying`) — seul le statut `new` l'autorisait. Nouvelle regle metier explicite du chef : la modification (titre/description) doit rester possible tant que le ticket est `new` ou `qualifying`, et se verrouiller definitivement a partir de `qualified` (et pour tous les statuts suivants, y compris apres reouverture `reopened` — un ticket reouvert reste verrouille). Toute information complementaire passe desormais uniquement par commentaires/reponses/pieces jointes.

Module: MOD-REQUEST (BR-REQUESTER-EDIT-001, nouvelle regle).

Fichiers modifies:
- `backend/api/services/ServiceRequest.py` — `requester_edit()` : la verification `req.request_status != "new"` est remplacee par `req.request_status not in self._REQUESTER_EDIT_STATUSES` avec `_REQUESTER_EDIT_STATUSES = ("new", "qualifying")`.
- `backend/api/routes/RouteRequest.py` — docstring de `PATCH /requests/{id}/requester-edit` mise a jour.
- `frontend/src/lib/capabilities.ts` — `TICKET_ACTION_STATUSES.requester_edit` passe de `["new"]` a `["new", "qualifying"]` (`canEdit` dans `app.requests.$id.tsx` en depend directement, aucun changement necessaire cote composant).
- `docs/codex/BUSINESS_RULES.md` — nouvelle regle BR-REQUESTER-EDIT-001.
- `docs/codex/CHANGELOG_CODEX.md`

Cause: la restriction initiale ("des qu'un acteur est deja intervenu") avait ete implementee au sens strict du tout premier statut, alors que la qualification est une etape de triage automatique/secretariat qui ne constitue pas encore une intervention de fond sur le contenu du ticket.

Verification: `python -c "import ast; ast.parse(open('backend/api/services/ServiceRequest.py').read())"` et idem `RouteRequest.py` (syntaxe OK). Pas de test backend/frontend existant ne reference `requester_edit`/`requester-edit` (verifie par recherche), donc aucune regression de suite de tests a corriger.

## 2026-07-29 - Cards tickets cliquables sur toute leur surface

Demande: sur les cards de tickets, pouvoir cliquer directement sur toute la card pour ouvrir le detail, au lieu de devoir cliquer uniquement sur le titre/reference.

Module: MOD-AGENT, MOD-CHIEF, MOD-SUPERVISION (BR-UI-TICKET-LAYOUT-001, BR-NAV-001).

Fichiers modifies:
- `frontend/src/routes/app.my-tickets.tsx`
- `frontend/src/routes/app.queue.tsx`
- `frontend/src/routes/app.supervision.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: certaines vues en grille rendaient la card ticket comme un simple conteneur, avec navigation seulement sur le titre/reference ou sur un bouton `Traiter`. L'ergonomie etait incoherente avec les cards deja completement cliquables (`Mes demandes`, `Boite de traitement`).

Correction: les cards grille de `Mes tickets`, `File d'attente` et les cards d'escalades de `Supervision` deviennent des surfaces cliquables avec `role="link"` et support clavier `Enter`/`Espace`, en conservant la route detail propre au contexte (`/app/my-tickets/tickets/$id`, `/app/queue/tickets/$id`, `/app/supervision/tickets/$id`). Les actions internes (`Escalader`, `Assigner`, checkbox, actions escalade) stoppent la propagation pour ne pas ouvrir le detail par erreur.

Verification: `npm run build` cote frontend OK (client + SSR), avec les avertissements Vite habituels sur chunks volumineux et imports externes non utilises.

## 2026-07-29 - Detail ticket chef de service : menu Priorite non rogne

Demande: dans l'espace chef de service, corriger le probleme d'affichage encerclé en rouge sur le menu `Priorite` du detail ticket.

Module: MOD-CHIEF / MOD-REQUEST (BR-UI-TICKET-DETAIL-001, BR-PRIORITY-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: apres le deplacement des actions staff dans l'onglet `Traitement`, le menu `Priorite` etait rendu en `absolute` dans une carte centrale `glass-strong overflow-hidden`, puis suivi par le panneau d'actions. Selon la hauteur disponible, le menu pouvait etre rogne ou visuellement recouvert.

Correction: le conteneur d'onglets du detail ticket autorise l'overflow visible, le groupe d'actions de traitement cree une couche `relative z-20`, et le menu `Priorite` est remonte en `z-50`. Aucun changement de route, permission, mutation ou endpoint.

Verification: `npm run build` cote frontend OK (client + SSR), avec les avertissements Vite habituels sur chunks volumineux et imports externes non utilises.

## 2026-07-29 - Supervision chef de departement : perimetre departement + services

Demande: dans `/app/supervision` et `/app/supervision/tickets/$id`, permettre au chef de departement de superviser son departement compose des services dont les chefs de service sont sous son autorite.

Module: MOD-SUPERVISION, MOD-CHIEF (BR-ROLE-CHIEF-DEPARTEMENT-001).

Fichiers modifies:
- `frontend/src/routes/app.supervision.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: `app.supervision.tsx` traitait tous les roles chef de la meme maniere et appelait `fetchRequests({ unit_id: sessionUser.unit_id })` / `fetchUsers({ unit_id: sessionUser.unit_id })`. Pour `chief-departement`, `sessionUser.unit_id` represente le departement, mais `unit_id` cote API est un filtre exact ; la page ne recuperait donc pas les tickets et agents des services rattaches au departement.

Correction: distinction explicite `chief-service` / `chief-departement` dans la page supervision. `chief-service` conserve le filtre exact `unit_id`. `chief-departement` utilise `direction_id=<department unity_id>` pour les agents et tickets, ce qui reutilise l'expansion backend existante `_direction_unity_ids` (departement + services descendants). Les libelles de la page deviennent dynamiques : "Supervision du departement" pour chief-departement, "Supervision du service" pour chief-service.

Verification: `npm run build` cote frontend OK (client + SSR), avec les avertissements Vite habituels sur chunks volumineux/imports externes non utilises.

## 2026-07-29 - Temps reel : 7 evenements orphelins ajoutes a l'invalidation SSE + filet de rattrapage reconnexion

Demande: ameliorer l'experience utilisateur pour que les chargements de donnees soient en temps reel.

Module: MOD-REQUEST, MOD-AGENT, MOD-CHIEF, MOD-DIRECTION (BR-REALTIME-001, nouvelle regle).

Fichiers modifies:
- `frontend/src/lib/realtime/invalidation-map.ts`
- `frontend/src/providers/realtime-provider.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Localisation: l'infrastructure temps reel (SSE + `INVALIDATION_MAP` + `RealtimeProvider`) existait deja et couvrait correctement 9 des 16 types d'evenements `request.*` reellement emis par `ServiceRequest.py`. Verification par comparaison directe des `emit_event(AppEvent(type=...))` du backend contre les cles de `INVALIDATION_MAP` : 7 evenements bien emis et recus cote client mais sans handler d'invalidation associe — `request.routed`, `request.reassigned`, `request.transferred_direction`, `request.priority_changed`, `request.rejected`, `request.reopen_requested`, `request.reopen_rejected`. Consequence concrete : une reassignation de service, un transfert de direction, un changement de priorite ou un rejet restaient invisibles en temps reel pour les autres sessions ouvertes (chef, agent, demandeur) jusqu'a un rechargement manuel de page.

Correction: les 7 evenements manquants sont ajoutes a `INVALIDATION_MAP`, avec les memes prefixes de query keys (`request`, `requests`, `queue`, `my-tickets`, `my-tickets-stats`, `stats`, etc.) que les evenements `request.*` deja geres les plus proches par nature. Comme `Object.keys(INVALIDATION_MAP)` pilote directement l'enregistrement des abonnements SSE dans `realtime-provider.tsx` (aucun autre fichier a modifier pour brancher un nouvel evenement), ces 7 ajouts suffisent a les rendre actifs.

Complement fiabilite: ajout d'un filet de rattrapage sur reconnexion SSE — `event_bus.py` etant un pub/sub en memoire sans rejeu d'historique, tout evenement emis pendant une coupure reseau etait definitivement perdu ; et depuis la desactivation du refetch automatique au focus/reconnexion (optimisation perf du 2026-07-28), plus rien ne rattrapait ces evenements manques avant un rechargement manuel. `realtime-provider.tsx` invalide desormais l'union complete des query keys de `INVALIDATION_MAP` a chaque reconnexion SSE faisant suite a une coupure detectee (pas au montage initial, via un ref `hasDroppedRef` qui distingue premiere connexion et reconnexion).

Verification: `npx tsc --noEmit` sans nouvelle erreur sur les deux fichiers touches ; `npx eslint` sur `invalidation-map.ts` — uniquement du bruit `prettier/prettier` ; sur `realtime-provider.tsx` — un warning `react-refresh/only-export-components` preexistant (export `useRealtimeStatus` deja present avant cette session, non introduit par ce changement) et une note `prettier/prettier` preexistante, aucune erreur de logique nouvelle.

## 2026-07-29 - Correction bug critique RBAC : tickets assignes invisibles hors unite courante de l'agent

Demande: "je ne vois plus les tickets dans leur espace correspondante" — signale sur File d'attente, Mes tickets, Mes demandes et Supervision/Direction/DG, role Agent Support teste.

Module: MOD-AGENT, MOD-CHIEF, MOD-PERSONAL (BR-ROLE-AGENT-001).

Fichiers modifies:
- `backend/api/routes/RouteRequest.py`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Localisation: verification en base (compte `Fatoumata Conte`, id=5, role agent-support, unity_id=16) — sur ses 21 tickets assignes (`assignee_id=5`), un seul appartient a l'unite 16 ; les 20 autres sont rattaches a d'autres unites (6, 1, 14, ou aucune). Cause identifiee dans `list_requests` (`RouteRequest.py`) : pour agent-support/chief-service, `unit_id` etait force a `actor.unity_id` **inconditionnellement**, meme quand le client demandait explicitement `assignee_id=<soi-meme>` (c'est le cas de `app.my-tickets.tsx`, qui interroge uniquement par `assignee_id` — voir `BR-ROLE-AGENT-001`). Consequence : tout ticket assigne personnellement a l'agent mais hors de son unite courante disparaissait de `Mes tickets`/`File d'attente`. De plus, `_check_request_access` (controle d'acces au detail `GET /requests/{id}`) n'avait de bypass que pour le demandeur (`requester_id`), pas pour l'assigne (`assignee_id`) — un agent pouvait donc recevoir un 403 en ouvrant un ticket qui lui etait pourtant assigne.

Correction: ajout d'un bypass symetrique a celui deja existant pour le demandeur — `is_own_assignee_view` (`assignee_id == str(actor.id)`) dans `list_requests`, qui leve le forcing `unit_id`/`direction_id` uniquement dans ce cas ; et un retour anticipe equivalent (`assignee_id == str(actor.id)`) dans `_check_request_access`. Le filtre `assignee_id` reste toujours verrouille sur l'identite de l'acteur (aucun elargissement de perimetre), seule la restriction d'unite forcee est levee quand l'agent consulte explicitement ses propres tickets assignes.

Verification: `python -m compileall api/routes/RouteRequest.py` OK. Test E2E via API non effectue (backend local intermittent non-reactif dans cet environnement, deja constate en session precedente) — a confirmer manuellement par l'utilisateur en rechargeant `Mes tickets`/`File d'attente` avec le compte Agent Support.

## 2026-07-29 - Perf : rapport decisionnel (/reports/decision) scanne toute la table workflow_detail/attachment sans tenir compte de la periode

Demande: "je veux que les chargements (donnees, pages, etc...) soient dans les 10s" — investigation ciblee sur la page la plus probable (Rapports, chef/direction/admin) apres qu'une exploration codebase (backend + frontend) ait classe les points d'impact par probabilite reelle de depasser 10s.

Module: MOD-REPORTS (rapport decisionnel).

Fichiers modifies:
- `backend/api/services/ServiceReport.py` — sous-requetes `evt` (agregation `workflow_detail`) et `att` (agregation `attachment`) dans `_decision_rows()`.
- `docs/codex/CHANGELOG_CODEX.md`

Cause: `_decision_rows(start, end, ...)` filtre la requete principale par periode (`DATE(r.created_at) BETWEEN :start AND :end`, toujours actif — `start`/`end` non optionnels), mais les deux sous-requetes `LEFT JOIN (...) evt` et `LEFT JOIN (...) att` agregeaient `workflow_detail`/`attachment` sans aucune restriction — elles scannaient et agregeaient (`GROUP BY request_id`) l'intégralite de ces deux tables, pour **toutes** les demandes de l'historique complet, quelle que soit la periode demandee, avant de faire le `LEFT JOIN` sur le sous-ensemble filtre. `decision_report()` appelle `_decision_rows()` deux fois par requete HTTP (periode courante + periode precedente pour le comparatif), doublant ce cout a chaque appel. Plus `workflow_detail`/`attachment` grossissent avec le temps, plus l'ecart entre "periode demandee" et "table entiere scannee" s'aggrave — explique une degradation progressive independante de la periode choisie par l'utilisateur.

Correction: les deux sous-requetes rejoignent desormais `request` (alias `rf`/`rf2`) avec le meme filtre `deleted_at IS NULL AND DATE(created_at) BETWEEN :start AND :end` deja utilise par la requete principale (memes parametres lies, pas de nouveau parametre) — elles n'agregent plus que les lignes appartenant a des demandes de la periode consideree. Correction purement additive au niveau du filtrage : le lien final `evt.request_id = r.id` / `att.request_id = r.id` restant strictement identique, aucun changement de resultat, uniquement une reduction du volume scanne. Index deja presents et utilises par le nouveau join : `idx_wf_req` (`workflow.request_id`), `idx_att_req` (`attachment.request_id`), `idx_req_created` (`request.created_at`).

Verification: `python -c "import ast; ast.parse(...)"` sur `ServiceReport.py` (syntaxe OK). Pas d'acces a une base MySQL locale peuplee pour mesurer le gain reel avant/apres — a confirmer en environnement avec donnees de volume realiste.

Perimetre exclu (investigue puis ecarte, cf. echanges) : plafonner `GET /requests` a moins de 1000 (cascaderait sur 6+ pages qui en dependent) ; brancher `app.reports.tsx` sur `/stats/by-direction`/`/stats/by-category` (ces endpoints `ServiceStats.py` referencent une table `direction` et des colonnes `request.direction_id`/`account.direction_id`/`account.unit_id` supprimees par la migration `011_replace_direction_unit_with_unity_organigram` — code mort casse, non appele par le frontend actuel, hors perimetre de cette session).

## 2026-07-29 - Reference demande : ajout du niveau departement (direction/departement/service)

Demande: la reference generee a la creation d'une demande doit suivre la formule "codename-direction-demandeur"-"codename-departement-demandeur"-"codename-service-demandeur" suivie de l'horodatage et de la sequence (ex: `DSI-ED-SED-0824070260729-001`), au lieu de seulement direction-service (ex: `SED-SED-0824070260729-001` — le segment direction etait meme errone car derive de la colonne plate `unity.parent_direction_id`, jamais peuplee par le seed, qui retombait donc sur le service lui-meme).

Module: MOD-REQUEST (BR-REQ-REF-001).

Fichiers modifies:
- `backend/api/services/ServiceRequest.py` — nouvelle methode `_org_chain_for_unity()` (remonte l'arbre `Organigram` feuille -> racine pour une unite donnee) ; `_requester_ref_unities()` remplacee par `_requester_ref_hierarchy()` qui retourne `(direction, departement, service)` en se basant sur cet arbre plutot que sur `unity.parent_direction_id` ; `_build_reference_base()` compose desormais 3 segments (`direction_code-departement_code-service_code`) au lieu de 2, avec repli du departement sur le code direction quand l'organigramme ne comporte pas de niveau intermediaire (cas de toutes les directions sauf DSI dans le seed actuel).
- `backend/api/repositories/RepositoryRequest.py` — docstring de `next_ref()` mise a jour (`DIR-DEPT-SVC-HHMMSSYYYMMDD-SEQ`) ; aucun changement de logique (le prefixe reste une chaine opaque).
- `docs/codex/BUSINESS_RULES.md` — BR-REQ-REF-001 mise a jour.
- `docs/codex/CHANGELOG_CODEX.md`

Cause: `_requester_ref_unities()` resolvait la "direction" via `unit.parent_direction_id`, une colonne plate sur `Unity` jamais renseignee par `seed_references.py` (seul l'arbre `Organigram`, autoportant via `parent_id`, encode la hierarchie reelle). Quand cette colonne est `NULL`, le code retombait sur `unit` lui-meme, produisant un doublon (ex: `SED-SED-...` au lieu de `DSI-SED-...`), et il n'existait de toute facon aucune notion de departement intermediaire.

Correction: la hierarchie est desormais entierement derivee de `Organigram` (le seul champ fiable) : le noeud racine (sans parent) est la direction, le noeud feuille est le service du demandeur, et le noeud intermediaire (s'il existe, ex: `DSI-DED`/`DSI-DEX`/`DSI-DIR` pour la DSI) est le departement. Pour les directions sans departement dedie dans le seed actuel (DC, DT, DRH, DF, DM, DI, DIAJ, DG), le segment departement reprend le code direction.

Verification: `python -c "import ast; ast.parse(open('backend/api/services/ServiceRequest.py').read())"` et idem sur `RepositoryRequest.py` (syntaxe OK).

## 2026-07-29 - Correction bug : agent assigne duplique dans "Intervenants" + nom complet manquant

Demande: sur `/app/requests/:id`, le panneau "Intervenants" affichait deux lignes distinctes pour le meme agent assigne — "Conte / Agent Support / Assigne" et "Fatoumata Conte / Agent Support / Ticket assigne a un agent" — meme cause racine que le doublon demandeur corrige plus tot (`String(raw.requester_id)`). Demande complementaire: garantir l'affichage du nom complet (prenom + nom) pour chaque intervenant.

Module: MOD-REQUEST (detail ticket, panneau lateral "Intervenants").

Fichiers modifies:
- `backend/api/models/ModelRequest.py` — propriete `Request.assignee_name` renvoie desormais le nom complet (`firstname + name`, meme convention que `ServiceRequest._account_display_name` deja utilisee pour `target_user_name` sur l'evenement timeline d'assignation) au lieu du seul nom de famille.
- `frontend/src/lib/api/requests.ts` — `mapRequest()` : `assigneeId` coerce en `String(raw.assignee_id)` (meme fix que `requesterId`) ; type `RawRequest.assignee_id` corrige en `number | string | null`.
- `frontend/src/components/new-request-form.tsx` — `requester_name` envoye a la creation compose desormais `[sessionUser.firstname, sessionUser.name].filter(Boolean).join(" ")` (meme pattern deja utilise dans `app.requests.$id.tsx:542`, `app.profile.tsx:284`, `app.admin.users.tsx:134`) au lieu du seul nom de famille — corrige l'affichage du demandeur pour les nouvelles demandes internes (n'affecte pas retroactivement les demandes deja creees, `requester_name` etant une colonne stockee et non calculee).
- `docs/codex/CHANGELOG_CODEX.md`

Cause: deux bugs cumules sur la meme paire d'entrees `buildParticipants()` :
1. Cle de dedoublonnage : `request.assigneeId` (nombre JSON brut, non coerce) vs `event.targetUserId` de l'evenement `assigned` (`str(assignee_id)` cote backend, donc toujours string cote frontend via `asString()`) — deux cles de types differents ⇒ deux entrees Map pour la meme personne.
2. Nom incomplet : `Request.assignee_name` ne renvoyait que `Account.name` (nom de famille seul), alors que l'evenement timeline utilise `_account_display_name` (prenom + nom) — meme une fois dedoublonne, le nom affiche aurait ete tronque selon l'ordre d'insertion dans la Map (`add()` ne met a jour ni le champ `name`, ni `role` si deja present).

Correction: alignement du type/de la coercion `assigneeId` sur le meme pattern deja applique a `requesterId`, et alignement de `assignee_name` (backend) sur `_account_display_name` pour renvoyer systematiquement le nom complet — les deux entrees fusionnent desormais en une seule, avec le nom complet de l'agent.

Verification: `python -c "import ast; ast.parse(...)"` sur `ModelRequest.py` (syntaxe OK) ; `npx tsc --noEmit` — aucune nouvelle erreur (baseline preexistante comparee via `git stash`, inchangee).

## 2026-07-29 - Uniformisation titre du ticket + alignement etoile (independant du navigateur/largeur)

Demande: uniformiser l'affichage du titre du ticket sur le format de la premiere capture (2-3 mots par ligne, etoile bien alignee) — la seconde capture montrait un mot par ligne et une etoile flottant au milieu du titre, incoherent selon la fenetre/navigateur.

Module: MOD-REQUEST (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: le titre passait a `lg:text-4xl` (36px) des 1024px de large, alors que la colonne titre partage encore l'espace avec le bloc SLA fixe (288px) jusqu'a des largeurs plus confortables — resultat un rendu "un mot par ligne" tres sensible a la largeur exacte disponible. Par ailleurs le conteneur flex titre+etoile utilisait `items-center` : des que le titre s'etalait sur plusieurs lignes, l'etoile se retrouvait centree au milieu du bloc au lieu de rester a cote de la premiere ligne.

Correction: le saut vers `text-4xl` est repousse a `xl:` (1280px) au lieu de `lg:` (1024px) — le titre reste a `text-3xl` sur toute la plage intermediaire, largeur ou 2-3 mots par ligne restent lisibles de facon deterministe. Le conteneur titre+etoile passe de `items-center` a `items-start` avec `mt-1` sur l'icone, un alignement fixe qui ne depend plus du nombre de lignes du titre ni de la largeur de fenetre/navigateur.

Verification: `npx tsc --noEmit` sans nouvelle erreur imputable au fichier (baseline preexistante inchangee) ; `npx eslint` — 3221 problemes, tous confirmes `prettier/prettier` via sortie JSON agregee, zero erreur de logique.

## 2026-07-29 - Correction bug : demandeur duplique dans "Intervenants" (detail ticket)

Demande: sur `/app/requests/:id`, le panneau "Intervenants (N)" affichait deux lignes distinctes pour le meme demandeur — "GOEPOGUI / Demandeur / Createur" et "GOEPOGUI / Demandeur / Demande creee par l'utilisateur" — alors que les deux representent le meme evenement (creation du ticket par le demandeur).

Module: MOD-REQUEST (detail ticket, panneau lateral "Intervenants").

Fichiers modifies:
- `frontend/src/lib/api/requests.ts` — `mapRequest()` : `requesterId` coerce desormais en `String(raw.requester_id)` (comme `directionId`/`serviceId`) ; type `RawRequest.requester_id` corrige en `number | string | null`.
- `docs/codex/CHANGELOG_CODEX.md`

Cause: `buildParticipants()` (`app.requests.$id.tsx`) deduplique les intervenants via une `Map` cle sur `candidate.key`. Le "createur" est ajoute avec `key: request.requesterId`, et l'evenement timeline `created` est ajoute avec `key: event.actorId` (calcule via `asString(infos.actor_id)`, donc toujours une string). Le backend renvoie `requester_id` en JSON comme nombre (`Optional[int]` dans `SchemaRequest.py`), et `mapRequest()` le recopiait tel quel (`raw.requester_id ?? ""`) sans coercion — `request.requesterId` valait donc le nombre `12` alors que `event.actorId` valait la chaine `"12"`. Deux cles de types differents dans la `Map` ⇒ deux entrees pour la meme personne au lieu d'une fusion.

Correction: alignement de `requesterId` sur la meme convention `String(...)` deja utilisee pour les autres identifiants mappes depuis l'API (`directionId`, `serviceId`), pour que la cle corresponde exactement a celle produite par `asString()` cote timeline.

Verification: `npx tsc --noEmit` — aucune nouvelle erreur (baseline preexistante comparee via `git stash`, inchangee).

## 2026-07-29 - Boutons de traitement deplaces dans l'onglet Traitement

Demande: les boutons de traitement (Demarrer traitement, Demander des infos, Escalader, etc.) doivent se trouver dans l'onglet `Traitement` plutot que dans l'en-tete du ticket.

Module: MOD-REQUEST, MOD-AGENT, MOD-CHIEF (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: extraction du bloc de boutons d'action staff (auparavant directement dans `<header>`, visible sur la capture pour `Fatoumata Conte`/Agent Support) dans une nouvelle variable `treatmentActionsPanel`, avec exactement les memes conditions `can*` et mutations qu'avant (aucun changement de permission/logique metier). Ce panneau est desormais rendu dans le contenu de l'onglet `Traitement`, au-dessus du panneau `requestActionsPanel` existant (actions demandeur). Pour eviter un doublon visuel sur `Marquer resolue` (present dans les deux panneaux via `canResolveTicket`), la branche correspondante a ete retiree de `requestActionsPanel` et de `canShowQuickActions` — ce panneau ne porte plus que les actions reservees au demandeur (`Modifier`, `Annuler`, `Demander une reouverture`, `Confirmer la resolution`). L'en-tete du ticket ne contient plus que reference/titre/badges/bloc SLA et les bannieres d'information (`needsUserResponse`, `isArchived`), ce qui reduit aussi le risque de squeeze du titre corrige precedemment (moins d'elements en concurrence dans la meme ligne flex).

Verification: `npx tsc --noEmit` sans nouvelle erreur imputable au fichier (baseline preexistante inchangee) ; `npx eslint` — 3221 problemes, tous confirmes `prettier/prettier` via sortie JSON agregee, zero erreur de logique.

## 2026-07-29 - Correction bug : bloc "Demandeur" (Direction/Departement/Service) vide sur le detail ticket

Demande: sur `/app/requests/:id`, le panneau "Details de la demande" > section "Demandeur" affichait toujours `—` pour Direction/Departement/Service (visible sur capture, encadre en rouge), alors que la section "Traitement" juste en dessous affiche correctement ces memes informations pour l'unite en charge du ticket.

Module: MOD-REQUEST (detail ticket, panneau lateral).

Fichiers modifies:
- `backend/api/models/ModelRequest.py` — ajout propriete `Request.requester_unit_id` (derivee de `self.requester.unity_id`, relation deja chargee en `lazy="selectin"`).
- `backend/api/schemas/SchemaRequest.py` — ajout champ `requester_unit_id: Optional[int]` sur `_RequestCommonFields` (expose sur `RequestResponse` et `RequestListItemResponse`).
- `frontend/src/routes/app.requests.$id.tsx` — `requesterDirectionName` derive desormais la direction via `requesterUnit?.direction_id` (meme pattern deja utilise pour `currentDirectionId`/l'unite en charge) au lieu de dependre d'un champ `requester_direction_id` qui n'a jamais existe cote backend.
- `docs/codex/API_INDEX.md`, `docs/codex/CHANGELOG_CODEX.md`

Cause: le frontend (`frontend/src/lib/api/requests.ts`) mappait deja `requesterServiceId: raw.requester_unit_id` et `requesterDirectionId: raw.requester_direction_id`, mais aucun des deux champs n'a jamais existe dans le schema Pydantic de reponse (`SchemaRequest.py`) ni dans une propriete du modele `Request` — le backend ne renvoyait donc jamais ces valeurs, contrairement a `assignee_name`/`direction_id` (unite en charge) qui suivent deja ce pattern de propriete Python exposee via `orm_mode`.

Correction: ajout de la propriete `requester_unit_id` (service d'appartenance du demandeur, via `Account.unity_id` deja charge) cote backend/schema ; cote frontend, la direction du demandeur est resolue a partir de la liste `units` deja chargee (`requesterUnit.direction_id`) exactement comme pour la section "Traitement", evitant d'avoir a exposer un second champ backend pour la direction (deduction faite via `Unity.parent_direction_id`, deja indisponible en synchrone sur `Account.unity` qui est `lazy="raise"`).

Verification: `python -c "import ast; ast.parse(...)"` sur les 2 fichiers backend modifies (syntaxe OK) ; `npx tsc --noEmit` sur `app.requests.$id.tsx` — aucune nouvelle erreur (baseline preexistante comparee via `git stash` inchangee).

## 2026-07-28 - Correction bug critique : titre du ticket ecrase lettre par lettre

Demande: mauvaise disposition constatee sur `/app/my-tickets/tickets/46` (et toutes les vues d'une demande) — le titre s'affichait avec une lettre par ligne, sur toute la hauteur de la page. Corriger pour retrouver la bonne disposition de `app.requests.$id.tsx`.

Module: MOD-REQUEST (BR-UI-TICKET-DETAIL-001) — impact transversal car composant partage `RequestDetailPage`.

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: `/app/my-tickets/tickets/:id` (`app.my-tickets_.tickets.$id.tsx`) rend `RequestDetailPage` avec `context="myTickets"` — c'est donc exactement le meme composant que `/app/requests/:id`, le bug n'est pas specifique a cette route. Dans l'en-tete (`<header>`), le bloc [titre+SLA] (`flex-1`) et la ligne de boutons d'action (`w-full lg:w-auto`) partageaient une meme ligne flex des que `lg:flex-row` s'active, sans `flex-wrap`. Si les boutons d'action (plusieurs boutons avec icone+texte) refusaient de descendre sous leur largeur naturelle, tout le budget restant — y compris en dessous de zero — etait retire du bloc titre, dont `min-w-0` autorise justement un retrecissement illimite. Le bloc SLA interne (`lg:w-72 lg:shrink-0`) aggrave l'effet en refusant lui-meme toute reduction. Resultat a certaines largeurs desktop intermediaires : le `<h1>` du titre se retrouvait ecrase a quasiment 0px de large, forcant le navigateur a placer chaque caractere sur sa propre ligne (`break-words` a l'extreme).

Correction: ajout de `flex-wrap` sur l'en-tete — la ligne de boutons d'action passe desormais a la ligne suivante si la place manque, au lieu d'ecraser le titre. Ajout de `lg:flex-wrap` sur le sous-bloc titre/SLA et `min-w-[12rem]` sur le conteneur du titre (au lieu de `min-w-0`) — le bloc SLA (288px fixe) passe lui aussi a la ligne plutot que de forcer le titre sous une largeur lisible. Comme le composant est partage, la correction s'applique automatiquement a tous les contextes (`requests`, `myTickets`, `queue`, `supervision`, `chiefInbox`, `departmentInbox`, `direction`, `dg`, `slaCenter`, `admin`).

Verification: `npx tsc --noEmit` sans nouvelle erreur imputable au fichier (baseline preexistante inchangee) ; `npx eslint` — 3234 problemes, tous confirmes `prettier/prettier` via sortie JSON agregee, zero erreur de logique.

## 2026-07-28 - Audit responsive detail ticket : garde-fou largeur des menus d'action

Demande: rendre `app.requests.$id.tsx` responsive sur desktop/tablette/telephone sans bug ni crash.

Module: MOD-REQUEST (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Constat: un audit ligne par ligne du fichier a montre qu'un travail responsive etendu avait deja ete applique (grille 70/30 -> colonne unique avant `xl`, en-tete/SLA empilable, stepper 5 colonnes sans scroll, onglets `overflow-x-auto`, listes fichiers/commentaires empilables) et documente (voir note "responsive multi-ecrans" ci-dessus). Verification `tsc --noEmit` : aucune nouvelle erreur, seulement la baseline preexistante deja connue (typage `fetchDirections`/`Direction[]`) — le fichier compile proprement apres cet important volume de changement.

Correction apportee: seul residu identifie — les 3 menus deroulants de l'en-tete (`Reassigner`, `Priorite`, `Service`) sont positionnes en `absolute right-0` avec une largeur minimale fixe et aucun plafond de largeur, un risque theorique de debordement horizontal sur tres petit ecran si leur bouton declencheur se retrouve pres du bord gauche. Ajout de `max-w-[calc(100vw-1.5rem)]` sur les trois, sans changer position, contenu ni comportement.

Verification: `npx tsc --noEmit` sans nouvelle erreur (baseline inchangee) ; `npx eslint` — 3234 problemes, tous confirmes `prettier/prettier` via sortie JSON agregee, zero erreur de logique. Test visuel navigateur multi-largeurs non effectue dans cet environnement (session authentifiee indisponible — le backend local devient intermittemment non-reactif lors des tentatives de connexion, cause non liee a ce changement) ; a verifier manuellement par l'utilisateur a 375px/768px/1440px.

## 2026-07-28 - Performance frontend : chargements plus rapides

Demande: reduire la lenteur visible avant l'affichage des pages et des donnees, notamment l'ecran logo/spinner mobile.

Module: frontend global / MOD-AUTH / MOD-PERSONAL.

Fichiers modifies:
- `frontend/src/router.tsx`
- `frontend/src/components/route-transition.tsx`
- `frontend/src/lib/api/client.ts`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: le fallback global de route etait affiche immediatement (`defaultPendingMs: 0`), les transitions remettaient un wrapper anime cle par `pathname` autour de l'application, et le client API chargeait la session par imports dynamiques repetes pendant les requetes. Le cache React Query etait aussi court par defaut et relancait des refetchs au focus/reconnexion.

Correction: cache global React Query porte a 1 minute avec conservation 10 minutes, refetch automatique au focus/reconnexion desactive, retry query desactive pour echouer vite si le backend ne repond pas, preload conserve 30 secondes, splash pending retarde a 300 ms avec duree minimale courte, transition globale remplacee par un rendu direct sans remount, imports session du client API rendus statiques. Aucun endpoint, role, permission, workflow ou donne metier n'est modifie.

Verification: `git diff --check` cible OK; `npm run build` cote frontend OK apres relance avec autorisation d'acces. L'ancien avertissement Vite sur `session.ts` importe a la fois dynamiquement et statiquement n'apparait plus; seuls les avertissements de chunks volumineux preexistants restent visibles.

## 2026-07-28 - Layout mobile : espacement bas avant navigation

Demande: sur l'accueil mobile, conserver entre la derniere section de contenu et la barre de navigation le meme espacement visuel qu'entre les sections de cartes.

Module: MOD-PERSONAL / layout applicatif.

Fichiers modifies:
- `frontend/src/components/app-layout.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: augmentation du padding bas mobile du conteneur principal avec prise en compte de `env(safe-area-inset-bottom)`, et positionnement de la barre mobile au-dessus de cette zone sure. Le contenu garde maintenant de l'air avant le menu fixe sans modifier les items, routes, roles ou donnees.

Verification: `git diff --check` cible OK; `npm run build` cote frontend OK apres relance avec autorisation d'acces. Seuls les avertissements Vite preexistants restent visibles (imports dynamiques/chunks volumineux).

## 2026-07-28 - Mes demandes : filtres visuellement distincts sur mobile

Demande: dans la zone de filtres encerclée de `Mes demandes`, chaque champ doit etre distinct a l'affichage.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `frontend/src/routes/app.requests.index.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: retrait du conteneur filtre unique en `GlassCard` et remplacement par une grille responsive ou chaque champ (recherche, statut, origine, periode, dates personnalisees, effacement) possede sa propre bordure, son fond et son espacement. Les valeurs, filtres, requetes API et comportements restent inchanges.

Verification: `git diff --check` cible OK; `npm run build` cote frontend OK apres relance avec autorisation d'acces. Seuls les avertissements Vite preexistants restent visibles (imports dynamiques/chunks volumineux).

## 2026-07-28 - Detail ticket responsive multi-ecrans

Demande: rendre `frontend/src/routes/app.requests.$id.tsx` responsive sur desktop, tablette et telephone, sans bug ni crash.

Module: MOD-REQUEST (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: ajustement UI uniquement du detail ticket: conteneur fluide avec paddings progressifs, grille principale repliee en une colonne avant `xl`, en-tete ticket/SLA vertical sur petits ecrans, titre/reference longs contenus dans la carte, stepper 5 etapes compresse sans scroll horizontal, onglets avec scroll local de secours, panneaux et listes fichiers/commentaires/actions empiles sur mobile puis horizontaux quand l'espace le permet. Aucun workflow, endpoint, role, permission ou calcul metier n'est modifie.

Verification: `npm run build` cote frontend OK apres relance avec autorisation d'acces; seuls les avertissements Vite preexistants restent visibles (imports dynamiques/chunks volumineux).

## 2026-07-28 - Stepper ticket : etape active en vert (couleur bouton) au lieu de bleu

Demande: la pastille bleue du stepper representant l'etape actuelle doit prendre la couleur verte des boutons de l'application.

Module: MOD-REQUEST (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: dans `TicketLifecycleStepper`, la classe de l'etape `active` passe de `border-sky-500 bg-sky-500 text-white shadow-sky-500/25` (bleu) a `border-primary bg-primary text-primary-foreground shadow-primary/25` (vert `--primary`, meme variable que `gradient-primary` utilisee par les boutons d'action principaux de l'app). Les etapes `done` (vert emeraude), `warning` (ambre) et `pending` (neutre) restent inchangees.

Verification: `npx tsc --noEmit` sans nouvelle erreur imputable au fichier (baseline preexistante inchangee).

## 2026-07-28 - Detail ticket : conteneur d'onglets et cartes laterales alignes sur la charte graphique

Demande: les zones entourees (conteneur d'onglets central + cartes Intervenants/Details de la demande) doivent adopter la charte graphique de l'application.

Module: MOD-REQUEST (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: le conteneur d'onglets et `sideCardClass` (Intervenants/Details de la demande/RequesterCard) utilisaient un degrade CSS bespoke (`bg-[radial-gradient(...)]` + `border`/`shadow-sm`/`backdrop-blur` manuels) different du systeme de design partage `glass`/`glass-strong` (`styles.css`), deja utilise ailleurs dans ce meme fichier via `GlassCard` (panneaux SLA depasse, priorite, rejet, reouverture, appreciation) et dans le reste de l'application.

Correction: remplacement des classes bespoke par l'utilitaire `glass-strong` (memes variables `--glass-bg-strong`/`--glass-border`/`--glass-shadow-lg` que partout ailleurs dans l'app), en conservant le rayon (`rounded-[18px]`) et les paddings existants. L'en-tete ticket (carte haute au-dessus du contenu) n'etait pas entouree dans la demande et conserve son propre style.

Verification: `npx tsc --noEmit` sans nouvelle erreur imputable au fichier (baseline preexistante inchangee) ; `npx eslint` — 3232 problemes, tous confirmes `prettier/prettier` via sortie JSON agregee, zero erreur de logique. Verification visuelle en navigateur non effectuee (pas de session authentifiee disponible dans cet environnement) — a confirmer manuellement par l'utilisateur.

## 2026-07-28 - Alignement colonnes : reduction de la limite du Journal au lieu d'etirer la colonne laterale

Demande: les deux colonnes (Journal des actions / colonne laterale) doivent se terminer au meme niveau qu'indique par une barre verte tracee juste apres le 3e evenement du journal, en respectant la position du bouton `Voir tout` — et l'espace vide cree par la precedente tentative d'etirement (`flex-1`) doit disparaitre.

Module: MOD-REQUEST (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `frontend/src/components/workflow-timeline.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: la session precedente avait etire la colonne laterale (`items-stretch` + `flex-1` sur sa derniere carte) pour rattraper la hauteur du `Journal des actions`, ce qui creait un grand vide visuel dans la carte etiree — juge pire que l'ecart initial.

Correction: approche inversee. `items-stretch` retire (retour a `items-start`), `flex-1` retire de la derniere carte laterale (`RequesterCard`/`Details de la demande`) — plus aucun etirement force. A la place, `WorkflowTimeline` reduit sa synthese par defaut de 5 a 3 evenements (`events.slice(0, 3)`, controle `Voir tout` visible des que `events.length > 3`), rapprochant naturellement la hauteur par defaut du Journal de celle de la carte `Details de la demande` repliee, sans espace vide artificiel.

Verification: `npx tsc --noEmit` sans nouvelle erreur imputable aux fichiers touches (baseline preexistante inchangee sur `app.requests.$id.tsx` ; aucune erreur sur `workflow-timeline.tsx`).

## 2026-07-28 - Detail ticket, libelles courts des onglets Journals et SLA

Demande: remplacer le libelle d'onglet `Journal des actions` par `Journals` et `Activite SLA` par `SLA`.

Module: MOD-REQUEST (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: seuls les labels visibles de `detailTabs` sont raccourcis (`Journals`, `SLA`). Les cles internes (`journal`, `sla`), le contenu des onglets, la timeline et les calculs SLA restent inchanges.

Verification: inspection ciblee des labels `Journals`/`SLA` dans `app.requests.$id.tsx` OK ; `git diff --check` OK.

## 2026-07-28 - Alignement bas de colonne entre Journal des actions et Details de la demande

Demande: les deux colonnes (contenu central / colonne laterale) doivent se terminer au meme niveau — la colonne laterale s'arretait beaucoup plus haut, laissant un grand vide sous la carte `Details de la demande`.

Module: MOD-REQUEST (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: la grille principale utilisait `items-start`, donc chaque colonne gardait sa hauteur intrinseque sans egard a l'autre. Depuis que `Details de la demande` se replie par defaut derriere `Voir tout` (session precedente), la colonne laterale est devenue nettement plus courte que le `Journal des actions`, creant un ecart visuel bas de page.

Correction: la grille passe de `items-start` a `items-stretch`. La colonne laterale (`aside > div`) recoit `h-full` pour occuper toute la hauteur disponible. La derniere carte visible de cette colonne recoit `flex-1` pour absorber l'espace restant et faire coincider son bord inferieur avec celui de la colonne centrale : `RequesterCard` (toujours en dernier quand affichee, vue non-demandeur) sinon `Details de la demande` (vue demandeur, quand `RequesterCard` est absente).

Verification: `npx tsc --noEmit` sans nouvelle erreur imputable au fichier (baseline preexistante inchangee) ; `npx eslint` — 3233 problemes, tous confirmes `prettier/prettier` via sortie JSON agregee, zero erreur de logique.

## 2026-07-28 - Ligne d'onglets du detail ticket sur une seule ligne

Demande: les onglets (`Description`, `Journal des actions`, `Commentaires`, `Fichiers`, `Activite SLA`, `Traitement`) doivent tenir sur une seule ligne — supprimer le bouton `Tous les evenements` qui forcait `Traitement` a passer a la ligne.

Module: MOD-REQUEST (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: la ligne d'onglets utilisait `flex-wrap` et partageait sa largeur avec le bouton decoratif `Tous les evenements` (affiche uniquement quand l'onglet `Journal des actions` est actif, sans `onClick` ni logique de filtrage reelle — un placeholder jamais branche). Sur les largeurs d'ecran habituelles, la somme des onglets + ce bouton depassait la largeur disponible et `Traitement` (dernier onglet) passait sur une deuxieme ligne.

Correction: suppression du bouton `Tous les evenements` (aucune fonctionnalite reelle derriere, donc rien n'est perdu). La ligne d'onglets passe de `flex-wrap` a `overflow-x-auto` (scroll horizontal de secours si la largeur venait a manquer, ex. mobile tres etroit) pour garantir que tous les onglets restent sur une seule ligne.

Verification: `npx tsc --noEmit` sans nouvelle erreur imputable au fichier (baseline preexistante inchangee) ; `npx eslint` — 3233 problemes, tous confirmes `prettier/prettier` via sortie JSON agregee, zero erreur de logique.

## 2026-07-28 - Journal des actions, libelle du controle harmonise en Voir tout

Demande: appliquer au `Journal des actions` la meme terminologie `Voir tout`/`Reduire` que les cartes `Details de la demande`/`Intervenants`, en gardant le bouton existant (pas de doublon) — alternative proposee et validee apres une premiere clarification sur la position exacte.

Module: MOD-REQUEST (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/components/workflow-timeline.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: renomme uniquement les libelles du bouton d'expansion existant dans `WorkflowTimeline` — `"Voir plus d'evenements"` -> `"Voir tout"`, `"Reduire les evenements"` -> `"Reduire"`. Position (bas de la liste, centre), limite (5 evenements par defaut), icone (`ChevronDown` rotatif) et logique (`expanded`/`setExpanded`) inchangees. Aucun bouton supplementaire ajoute en haut de la section — le controle existant est juge suffisant, seule la coherence textuelle avec les autres cartes etait demandee.

Verification: `npx tsc --noEmit` sans nouvelle erreur sur `workflow-timeline.tsx`.

## 2026-07-28 - Detail ticket, controle Voir tout sur la carte Details de la demande

Demande: ajouter sur la carte `Details de la demande` le meme controle `Voir tout` deja present sur la carte `Intervenants`.

Module: MOD-REQUEST (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: ajout d'un etat local `showAllDetails` (meme pattern que `showAllParticipants` de la carte Intervenants) et d'un bouton `Voir tout`/`Reduire` identique en style et icones (`ArrowUpRight` / `ChevronDown rotate-180`, `text-primary`) dans l'en-tete de la carte `Details de la demande`. Par defaut, seul le groupe **Demande** (Categorie, Cree le, Mise a jour, ID) reste visible ; les groupes **Demandeur**, **Traitement** et **SLA** (ajoutes dans la restructuration precedente) sont masques jusqu'au clic sur `Voir tout`. Toutes les donnees sont deja calculees au rendu — l'expansion ne declenche aucun appel reseau supplementaire.

Verification: `npx tsc --noEmit` sans nouvelle erreur imputable au fichier (baseline preexistante inchangee) ; `npx eslint` — 3243 problemes, tous confirmes `prettier/prettier` via sortie JSON agregee, zero erreur de logique.

## 2026-07-28 - Detail ticket, restructuration de la carte Details de la demande

Demande: reproduire exactement une maquette fournie pour la carte laterale `Details de la demande` — 4 groupes avec icone circulaire coloree (Demande / Demandeur / Traitement / SLA).

Module: MOD-REQUEST (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: la carte est reorganisee en 4 groupes iconographies (icone circulaire coloree + libelle majuscule) au lieu d'une liste plate : **Demande** (emeraude) — Categorie, Cree le, Mise a jour, ID de la demande (inchange) ; **Demandeur** (bleu ciel, nouveau) — Direction/Departement/Service du demandeur lui-meme (distinct du service assigne au traitement), affiche seulement pour les demandeurs internes (`authorType === "internal"`), plus le nom du demandeur (toujours affiche) ; **Traitement** (violet, renomme) — les anciens champs `Direction`/`Service` (qui representaient deja le service assigne au ticket) sont renommes `Direction en charge`/`Service en charge` et complementes d'un nouveau champ `Departement en charge` ; `Agent en charge` conserve sa condition d'affichage existante (`isRequesterView`) ; **SLA** (ambre, nouveau) — ligne de synthese "SLA depasse"/"Dans les delais" reprenant `slaOver` deja calcule, sans reintroduire la mini-carte SLA retiree precedemment (pas de courbe/Objectif/Consomme). Departement resolu via `Unit.department_name`, deja expose par l'API directions/unites — aucun nouvel appel reseau.

Verification: `npx tsc --noEmit` sans nouvelle erreur imputable au fichier (erreurs preexistantes non liees sur le typage `fetchDirections`/`Direction[]`, y compris sur le nouvel appel `directions.find` pour le demandeur, meme categorie d'erreur preexistante) ; `npx eslint` — 3224 problemes, tous confirmes `prettier/prettier` via sortie JSON agregee, zero erreur de logique.

## 2026-07-28 - Detail ticket, stepper sans scroll horizontal

Demande: le parcours/stepper de la demande ne doit pas etre scrollable ni couper une etape; les 5 etapes doivent rester visibles dans la carte.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: retrait de `overflow-x-auto` et de `min-w-[720px]` sur `TicketLifecycleStepper`. Le stepper utilise desormais une grille fixe `grid-cols-5`, avec connecteurs positionnes entre les cellules et tailles de labels responsives, afin de garder `Ouverture`, `Qualification`, `Traitement`, `Valider`, `Fermeture` visibles ensemble.

Verification: `npm run build` cote frontend OK, avec les avertissements Vite preexistants sur imports dynamiques et chunks volumineux.

## 2026-07-28 - Fusion des noeuds journal pour un commentaire avec piece jointe

Demande: quand un commentaire est accompagne d'un fichier (envoi combine), le `Journal des actions` affichait deux noeuds separes ("Piece jointe ajoutee — X" puis "Commentaire ajoute") au lieu de montrer clairement que les deux ont ete crees ensemble — reference donnee : le rendu d'un commentaire avec photo jointe sur Facebook (un seul bloc).

Module: MOD-REQUEST (BR-ATTACHMENT-001).

Fichiers modifies:
- `backend/api/routes/RouteRequest.py`
- `frontend/src/lib/api/requests.ts`
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/API_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: `upload_attachment` cree systematiquement un evenement `attachment_added` a chaque upload, y compris lorsque l'upload fait partie du flux combine "joindre un fichier + commentaire" (`commentMut` uploade d'abord le fichier puis cree le commentaire). Le commentaire cree ensuite son propre evenement `comment_added`, deja enrichi des infos de la piece jointe (chip fichier, clic `Voir`) depuis une correction anterieure — d'ou le doublon visuel dans le journal.

Correction: ajout du parametre optionnel `skip_timeline_event` (query, defaut `false`) sur `POST /requests/{id}/attachments` — quand `true`, aucun evenement `attachment_added` n'est cree. `uploadAttachment()` (`requests.ts`) accepte desormais un 4e parametre `skipTimelineEvent` transmis en query string. Le flux d'envoi combine dans `app.requests.$id.tsx` (`commentMut`) l'appelle avec `skipTimelineEvent=true`, de sorte que seul l'evenement `comment_added` (commentaire + piece jointe rattachee, un seul noeud) apparaisse dans le journal. L'upload standalone lors de la creation d'une demande (`new-request-form.tsx`) n'est pas concerne et garde son evenement `attachment_added` propre.

Verification: `python -m compileall api/routes/RouteRequest.py` OK ; `npx tsc --noEmit` sans nouvelle erreur imputable aux fichiers touches (erreurs preexistantes non liees sur `app.requests.$id.tsx`/`app.requests.index.tsx`, typage `fetchDirections`/`Direction[]`).

## 2026-07-28 - Detail ticket, bouton Voir tout des intervenants

Demande: faire fonctionner `Voir tout` dans la carte laterale `Intervenants`, avec possibilite de reduire ensuite.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: `Voir tout` n'est plus un simple texte statique: c'est un bouton qui bascule entre la synthese courte des 4 premiers intervenants et la liste complete. En mode liste complete, le libelle devient `Reduire` pour revenir a l'affichage court. Les participants restent calcules depuis les donnees existantes du ticket/timeline.

Verification: `npm run build` cote frontend OK, avec les avertissements Vite preexistants sur imports dynamiques et chunks volumineux.

## 2026-07-28 - Correction affichage image dans la modal de previsualisation

Demande: dans la modal de previsualisation (`Voir`), l'image ne s'affichait pas correctement.

Module: MOD-REQUEST (BR-ATTACHMENT-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: l'`<img>` de la modal utilisait la classe `max-w-none` (sans aucune limite de largeur), ce qui force le navigateur a l'afficher a sa taille pixel native. Pour un fichier volumineux (ex. capture d'ecran haute resolution de 1.4 Mo), la taille native depasse largement la fenetre de la modal : a 100% de zoom, seul un minuscule extrait centre de l'image restait visible, donnant l'impression d'un rendu casse/flou au lieu de l'image entiere.

Correction: remplace `max-w-none` par `max-h-[70dvh] max-w-full` sur l'`<img>`. A 100% (`previewZoom=1`), l'image est desormais mise a l'echelle pour tenir entierement dans la modal en conservant son ratio. Le zoom (`ZoomIn`/`ZoomOut`, transform CSS `scale()`) continue d'agrandir au-dela de cette taille ajustee, le conteneur restant `overflow-auto` pour permettre le defilement une fois zoome.

Verification: `npx tsc --noEmit` sans nouvelle erreur imputable au fichier (erreurs preexistantes non liees sur le typage `fetchDirections`/`Direction[]`).

## 2026-07-28 - Detail ticket, onglet Traitement et ouverture fichiers depuis le journal

Demande: deplacer les actions disponibles dans un onglet `Traitement` apres `Activite SLA`, puis permettre le clic sur une piece jointe du `Journal des actions` pour ouvrir directement l'onglet `Fichiers` et l'apercu du fichier.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `frontend/src/components/workflow-timeline.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: ajout de l'onglet `Traitement` qui rend le panneau `requestActionsPanel` existant, suppression de l'ancien rendu autonome des actions en bas du dossier, et ajout d'un callback optionnel `onOpenAttachment` a `WorkflowTimeline`. Quand un evenement porte `attachment_id` ou `filename`, son libelle/chip fichier devient cliquable ; la page active l'onglet `Fichiers` puis reutilise `handleAttachmentFile(..., "open")` pour afficher l'apercu. Aucun endpoint, permission ou workflow n'est modifie.

Verification: `npm run build` cote frontend OK, avec les avertissements Vite preexistants sur imports dynamiques et chunks volumineux.

## 2026-07-28 - Correction bug critique : storage_path des pieces jointes corrompu a chaque affichage

Demande: au clic sur `Voir`, l'utilisateur obtient "Impossible d'acceder a la piece jointe : Chemin invalide."

Module: MOD-REQUEST (pieces jointes, BR-ATTACHMENT-001).

Fichiers modifies:
- `backend/api/routes/RouteRequest.py`
- Donnees: reparation ponctuelle de la table `attachment` (5 lignes corrompues restaurees depuis les fichiers reels sur disque)
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: `list_attachments` et `upload_attachment` faisaient `item.storage_path = storage.presigned_url(item.storage_path)` directement sur l'entite SQLAlchemy renvoyee par la session (`get_by_id`/`list_by_request`/`svc.create`), au lieu de ne modifier qu'une copie de reponse. `get_db()` (`backend/api/dependencies.py`) commit la session a la fin de **chaque** requete, y compris les `GET` en lecture seule. Resultat : chaque appel a `GET /requests/{id}/attachments` (donc chaque ouverture de l'onglet Fichiers) re-presignait un `storage_path` deja presigne et persistait ce resultat en base, empilant un nouveau prefixe `/api/v1/requests/download/` a chaque fois — jusqu'a produire un chemin qui echoue au controle anti-traversal de repertoire dans `download_file` (`HTTPException 400 "Chemin invalide."`). Verifie en base : les 6 pieces jointes existantes avaient entre 1 et plus de 30 prefixes empiles.

Correction: `list_attachments` et `upload_attachment` construisent desormais une instance `AttachmentResponse.from_orm(...)` dediee et n'assignent l'URL presignee que sur cette copie ; l'entite ORM suivie par la session n'est plus jamais mutee pour de la presentation. Reparation ponctuelle des 5 lignes deja corrompues en base : `storage_path` reconstruit a `requests/{request_id}/{fichier reel}` en retrouvant le prefixe hexadecimal unique (intact malgre la corruption) dans chaque fichier present sur disque (`backend/uploads/requests/{id}/`).

Verification: `python -m compileall api/routes/RouteRequest.py` OK. Verification en base (`SELECT storage_path FROM attachment`) : les 5 chemins corrompus sont desormais identiques aux fichiers reels sur disque. Test E2E via `curl` (login admin puis `GET /attachments`) tente mais non conclu — le serveur de dev local a cesse de repondre pendant la requete de login (soupcon : hachage Argon2 bloquant potentiellement la boucle asyncio mono-processus en dev, sujet distinct hors perimetre de cette correction) ; a reverifier manuellement dans le navigateur apres redemarrage du backend si besoin.

## 2026-07-28 - Previsualisation piece jointe en modal zoomable

Demande: au clic sur `Voir` (image ou PDF), afficher le fichier dans une modal adaptee au contenu et zoomable, au lieu d'ouvrir un nouvel onglet ; s'assurer que le telechargement fonctionne.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: `handleAttachmentFile` n'ouvre plus de fenetre popup pour le mode `"open"` (source de blocages navigateur) — elle recupere le blob authentifie puis alimente un nouvel etat `previewFile` (`url`, `filename`, `mimeType`) affiche dans une modal `Dialog` dediee. Selon le `mime_type` : image → `<img>` avec zoom pilote par l'etat `previewZoom` (boutons `ZoomOut`/`ZoomIn`, 100%-300% par pas de 50%) ; `application/pdf` → `<iframe>` (viewer PDF natif du navigateur, deja zoomable/paginable) ; autre type → message "apercu non disponible" avec bouton de telechargement. La modal expose aussi un bouton `Telecharger` qui declenche le meme telechargement par ancre `download` que l'action `Telecharger` de la liste des pieces jointes (deja fonctionnelle via `fetchAttachmentFile` + blob + ancre — verifiee, sans changement necessaire cote logique de telechargement). Le blob de previsualisation est revoque via `URL.revokeObjectURL` a la fermeture de la modal (`closePreview`) et au demontage du composant. Aucun changement de route, permission ni donnee.

Verification: `npx tsc --noEmit` sans nouvelle erreur imputable au fichier (erreurs preexistantes non liees sur le typage `fetchDirections`/`Direction[]`) ; `npx eslint` sans probleme hors bruit prettier CRLF preexistant sur tout le depot (3128 occurrences, toutes `prettier/prettier`, verifie via sortie JSON agregee).

## 2026-07-28 - Detail ticket, Commentaires redevient un onglet dedie

Demande: dans l'onglet Commentaires, afficher chaque intervenant avec son commentaire et les fichiers qu'il a joints a ce commentaire — l'onglet `Commentaires` doit exister a part entiere, distinct du `Journal des actions`.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: revient sur la fusion du 2026-07-28 qui affichait les commentaires sous la timeline du `Journal des actions`. Le panneau `commentsPanel` (liste des intervenants avec commentaire + chip piece jointe/`Voir`, plus le formulaire d'envoi combine) est desormais rendu dans sa propre section gardee par `activeDetailTab === "comments"`, separee de la section `Journal des actions` qui ne contient plus que `WorkflowTimeline`. Le bouton d'onglet `Commentaires` bascule simplement `activeDetailTab` comme les autres onglets (retrait du redirect-vers-Journal + scroll automatique via `commentsPanelRef` qui n'a plus lieu d'etre). Aucun changement de route, permission, donnee ou workflow.

Verification: `npx tsc --noEmit` sans nouvelle erreur imputable au fichier (erreurs preexistantes non liees sur le typage `fetchDirections`/`Direction[]`) ; `npx eslint` sans probleme hors bruit prettier CRLF preexistant sur tout le depot.

## 2026-07-28 - Detail ticket, retrait de la carte SLA de la colonne laterale

Demande: retirer la carte `SLA` (mini-graphique + Depassement/Objectif/Consomme) de la colonne laterale, signalee redondante par capture d'ecran annotee ; Intervenants remonte a sa place.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: suppression de la section `SLA` (mini-courbe SVG, Depassement/Marge, Objectif/Consomme) de la colonne laterale. La colonne droite ne contient plus que `Intervenants` puis `Details de la demande`. La variable `slaOverageHours` (devenue inutilisee) est retiree. L'information SLA reste disponible via le bloc integre a l'en-tete du ticket (pourcentage, temps ecoule/objectif, barre de progression). Aucun changement de route, permission, donnee ou workflow.

Verification: `npx tsc --noEmit` sans nouvelle erreur imputable au fichier (erreurs preexistantes non liees sur le typage `fetchDirections`/`Direction[]`) ; `npx eslint` sans probleme hors bruit prettier CRLF preexistant sur tout le depot.

## 2026-07-28 - Commentaire et piece jointe envoyes ensemble (comme WhatsApp)

Demande: pouvoir joindre un fichier a un commentaire et envoyer les deux en un seul geste (clic sur Publier), avec une seule trace dans le journal des actions montrant qui a commente avec une piece jointe a l'appui — au lieu de deux actions/entrees separees.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `backend/api/routes/RouteRequest.py`
- `frontend/src/routes/app.requests.$id.tsx`
- `frontend/src/lib/api/requests.ts`
- `frontend/src/lib/mock-data.ts`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/API_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: le trombone du panneau Commentaires ne declenche plus un upload immediat — le fichier est "stage" en memoire (apercu avec bouton retirer, sans requete reseau). Au clic sur `Publier`, la mutation combinee uploade d'abord la piece jointe (`uploadAttachment`) puis cree le commentaire (`createComment`) en lui passant l'`attachment_id` obtenu, dans le meme geste utilisateur. Cote backend, `_CommentBody` accepte desormais un `attachment_id` optionnel ; `create_comment` verifie que la piece jointe appartient bien a la demande puis stocke `attachment_id`/`filename`/`mime_type`/`size_bytes` dans les `infos` de l'evenement `comment_added` — memes cles que l'evenement `attachment_added` existant, donc **aucune modification necessaire** de `workflow-timeline.tsx` : le Journal des actions affiche deja automatiquement un chip avec le nom du fichier sur l'entree de commentaire concernee. Le panneau Commentaires affiche en plus un lien `Voir` sur la piece jointe (reutilise `handleAttachmentFile`). Aucun changement de route, permission ni de modele/migration (reutilisation du champ `infos` JSON existant).

Verification: `python -m compileall api/routes/RouteRequest.py` OK ; `npx tsc --noEmit` sans nouvelle erreur imputable aux fichiers touches (erreurs preexistantes non liees sur `app.requests.$id.tsx`, typage `fetchDirections`/`Direction[]`) ; `npx eslint` sans probleme hors bruit prettier CRLF preexistant sur tout le depot.

## 2026-07-28 - Detail ticket, onglet Description avant Journal

Demande: ajouter dans la barre d'onglets centrale un onglet `Description` avant `Journal des actions`, sans toucher aux zones commentaires/actions annotees en rouge.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: ajout du type d'onglet `description`, insertion de l'onglet `Description` en premiere position et affichage de `request.description` dans la carte centrale. Le journal, le bouton `Voir plus d'evenements`, les commentaires et les actions ne sont pas modifies.

Verification: `npm run build` cote frontend OK, avec les avertissements Vite preexistants sur imports dynamiques et chunks volumineux.

## 2026-07-28 - Detail ticket, fusion Journal des actions et Commentaires

Demande: regrouper le Journal des actions et les Commentaires dans la meme carte au lieu de deux blocs separes.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: `commentsPanel` est deplace a l'interieur de la section de l'onglet `Journal des actions`, juste sous `WorkflowTimeline`, separe par une bordure — les deux sont donc visibles ensemble des que cet onglet est actif. Le bloc bas ne contient plus que la carte `Actions` seule (largeur reduite `sm:max-w-sm`, l'ancien conteneur partage `bottomPanelClass` devenu inutile a ete retire). Le clic sur l'onglet `Commentaires` continue de basculer vers `Journal des actions` puis de defiler jusqu'au bloc commentaires (`commentsPanelRef`), desormais coherent avec sa nouvelle position. Aucun changement de donnees, permission ou mutation.

Verification: `npx tsc --noEmit` sans nouvelle erreur imputable au fichier (erreurs preexistantes non liees sur le typage `fetchDirections`/`Direction[]`) ; `npx eslint` sans probleme hors bruit prettier CRLF preexistant sur tout le depot.

## 2026-07-28 - Detail ticket, fusion visuelle commentaires actions

Demande: rattacher visuellement la partie `Commentaires` avec les actions dans le bas du detail demande/ticket.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: le bloc bas utilise desormais un seul conteneur EDG Connect pour regrouper `Commentaires` et `Actions`. Les commentaires restent a gauche et les actions a droite sur desktop, sans modifier les permissions ni les mutations existantes.

Verification: `npm run build` cote frontend OK, avec les avertissements Vite preexistants sur imports dynamiques et chunks volumineux.

## 2026-07-28 - Detail ticket, retrait des blocs redondants Description et raccourci fichiers

Demande: retirer du detail ticket le bloc `Description` (sous l'onglet Journal) et le raccourci `Voir / telecharger les fichiers` de la carte `Actions`, signales redondants par capture d'ecran annotee.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: suppression de la section `Description` affichee sous l'onglet Journal des actions (texte de la demande, redondant a cet emplacement). Suppression du bouton `Voir / telecharger les fichiers` dans la carte `Actions` (redondant avec l'onglet `Fichiers` qui offre deja apercu/telechargement par piece jointe) ; `hasRequestActions` ne tient plus compte du nombre de pieces jointes. Aucun changement de route, permission, donnee ou workflow ; l'onglet Fichiers et son contenu restent inchanges.

Verification: `npx tsc --noEmit` sans nouvelle erreur imputable au fichier (erreurs preexistantes non liees sur le typage `fetchDirections`/`Direction[]`) ; `npx eslint` sans probleme hors bruit prettier CRLF preexistant sur tout le depot.

## 2026-07-28 - Detail ticket, bloc commentaires actions aligne maquette

Demande: reproduire la partie basse entouree de la maquette du detail demande/ticket dans `app.requests.$id.tsx`, en gardant la charte EDG Connect.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: les commentaires sont rendus dans une carte bas de dossier toujours visible sous le journal, et les actions autorisees sont deplacees dans une carte compacte a droite des commentaires sur desktop. L'ancienne carte Actions de la colonne laterale et l'ancien contenu commentaires masque dans les onglets sont retires pour eviter les doublons. Les permissions, routes, API et workflows restent inchanges.

Verification: `npm run build` cote frontend OK, avec les avertissements Vite preexistants sur imports dynamiques et chunks volumineux.

## 2026-07-28 - Detail ticket, journal des actions aligne maquette

Demande: reproduire la zone centrale entouree de la maquette du detail demande/ticket, en conservant la charte graphique EDG.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `frontend/src/components/workflow-timeline.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: la carte `Journal des actions` adopte un rendu plus proche de la maquette: conteneur sombre/vert, onglets conserves, filtre journal stylise, timeline plus aeree avec icones lisibles, ligne de connexion, badges de statut et controle `Voir plus d'evenements` / `Reduire les evenements`. Les evenements restent issus des donnees reelles du ticket. Aucun changement de route, permission, API ou workflow.

Verification: `npm run build` cote frontend OK, avec les avertissements Vite preexistants sur imports dynamiques et chunks volumineux.

## 2026-07-28 - Detail ticket, raffinement des cartes laterales

Demande: rapprocher encore la partie droite entouree sur la maquette du detail demande/ticket.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: les cartes laterales utilisent un fond plus proche du dossier ticket premium, le mini-graphe SLA affiche maintenant une courbe avec surface remplie et point final, et la carte Intervenants devient une synthese limitee aux premiers intervenants tout en conservant le compteur total. Aucun changement de donnees source, route, permission, API ou workflow.

Verification: `npm run build` cote frontend OK, avec les avertissements Vite preexistants sur imports dynamiques et chunks volumineux.

## 2026-07-28 - Detail ticket, colonne laterale alignee maquette

Demande: reproduire plus fidelement les blocs entoures a droite dans la maquette du detail demande/ticket.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: la colonne droite n'est plus rendue comme une carte globale contenant des sous-cartes. Les blocs SLA, Intervenants, Details de la demande et Actions utilisent des cartes autonomes au meme style que la carte haute. Le mini-graphe SLA est affine en courbe progressive, les lignes d'intervenants sont allegees et les details sont presentes en liste separee par lignes fines. Aucun changement de donnees, route, permission, API ou workflow.

Verification: `npm run build` cote frontend OK, avec les avertissements Vite preexistants sur imports dynamiques et chunks volumineux.

## 2026-07-28 - Detail ticket, carte haute alignee maquette

Demande: reproduire plus fidelement la zone haute entouree sur la maquette du detail demande/ticket dans `app.requests.$id.tsx`.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: la reference, le titre, les badges, le bloc SLA et le parcours fixe a 5 etapes sont maintenant regroupes dans une carte haute autonome. Le bloc SLA de l'en-tete est renforce visuellement (separateur, pourcentage, horloge, barre), le stepper adopte une disposition plus proche de la maquette et le contenu journal/commentaires/fichiers est separe sous cette carte. Aucun changement de route, permission, API ou workflow.

Verification: `npm run build` cote frontend OK, avec les avertissements Vite preexistants sur imports dynamiques et chunks volumineux ; `git diff --check` OK.

## 2026-07-27 - Detail ticket en vraie grille dossier

Demande: corriger l'ecart visuel restant avec la maquette apres comparaison capture utilisateur, notamment la colonne droite trop basse et le doublon `Avancement de votre demande`.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: suppression du second parcours `Avancement de votre demande`, retrait des imports associes, transformation du detail en vraie grille desktop 70/30 des le haut de l'ecran. La colonne gauche contient le dossier ticket compact (en-tete, parcours unique, onglets) et la colonne droite SLA/Intervenants/Details/Actions demarre au meme niveau que le dossier, dans une carte separee. Aucun changement de route, permission, API ou workflow.

Verification: `npm run build` cote frontend OK, avec les avertissements Vite preexistants sur imports dynamiques et chunks volumineux.

## 2026-07-27 - Detail ticket avec onglets actifs et actions laterales

Demande: rapprocher encore `app.requests.$id.tsx` de la maquette de reference en gardant la charte EDG, sans changer routes, API, permissions ni workflow.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: ajout d'un vrai systeme d'onglets dans `RequestDetailPage` (`Journal des actions`, `Commentaires`, `Fichiers`, `Activite SLA`), deplacement des actions personnelles dans une carte `Actions` de la colonne droite, retrait des boutons personnels redondants de l'en-tete, ajustement de la grille principale vers une lecture 70/30 et conservation des donnees reelles existantes (timeline, commentaires, pieces jointes, SLA).

Verification: `npm run build` cote frontend OK, avec les avertissements Vite preexistants sur imports dynamiques et chunks volumineux.

## 2026-07-27 - Alignement fin du detail ticket sur la maquette dossier

Demande: faire correspondre exactement `app.requests.$id.tsx` a une maquette de reference (en-tete, stepper 5 etapes numerotees, onglets, colonne laterale SLA/Intervenants/Details).

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: remplacement du stepper dynamique `TicketComplianceTrace` (etapes variables Chef de service/Directeur, acteur+date par etape) par `TicketLifecycleStepper`/`buildFixedLifecycleSteps` : cycle de vie fixe a 5 etapes numerotees (Ouverture/Qualification/Traitement/Valider/Fermeture), ligne pleine pour les etapes franchies et pointillee pour les etapes a venir, desormais visible aussi cote demandeur (retrait de la restriction `!isRequesterView`). Colonne laterale reordonnee et completee pour correspondre a la maquette : carte SLA (deja presente) en premier, Intervenants en second, Details de la demande reecrit en liste verticale (Categorie, Direction, Service, Agent en charge, Cree le, Mise a jour, ID de la demande) avec bouton de copie presse-papier sur l'identifiant (ajoute aussi a cote de la reference en en-tete) ; retrait de la banniere "SLA depasse" redondante (mal positionnee par un `order` CSS manquant et absente de la maquette). Code mort supprime : `ComplianceStep(State)`, `EscalationRoleLevel`, `STATUS_RANK`, `isEscalationTraceEvent`, `isFormalTraceAction`, `escalationRoleLevel`, `latestFormalRoleEvent`, `complianceStepClass`. Aucun changement de route, permission, action ou endpoint.

Verification: `npx tsc --noEmit` sans nouvelle erreur imputable au fichier (erreurs preexistantes non liees sur le typage `fetchDirections`/`Direction[]`) ; `npx eslint` sans probleme hors bruit prettier CRLF preexistant sur tout le depot.

## 2026-07-27 - Detail ticket en disposition dossier

Demande: rapprocher l'affichage du detail demande/ticket d'une page dossier professionnelle, sans casser la charte graphique ni creer de composant parallele.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: `RequestDetailPage` reste le composant central reutilise par les contextes existants, mais son affichage est reorganise au format dossier ticket: en-tete avec reference, titre, statut, priorite, categorie et bloc SLA; parcours/timeline sous l'en-tete; journal des actions affiche en premier avec onglets visuels; commentaires presentes en fil; panneau d'actions lateral branche sur les mutations existantes; colonne droite SLA, intervenants et details de la demande. Aucun changement de route, permission ou workflow.

Verification: `npm run build` cote frontend OK, avec les avertissements Vite preexistants sur imports dynamiques/chunks volumineux.

## 2026-07-27 - Pieces jointes visibles et telechargeables

Demande: afficher les fichiers ajoutes a une demande et permettre de les voir ou telecharger depuis le detail.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `frontend/src/lib/api/client.ts`
- `frontend/src/lib/api/requests.ts`
- `frontend/src/routes/app.requests.$id.tsx`
- `backend/api/storage.py`
- `docs/codex/API_INDEX.md`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: la page detail demande/ticket charge maintenant les pieces jointes via `GET /requests/{id}/attachments` et affiche une section dediee avec nom, type, taille, date, statut de scan, action `Voir` et action `Telecharger`. Les fichiers sont recuperes en blob via une requete authentifiee avant ouverture ou telechargement. L'URL locale generee par `storage.presigned_url` pointe maintenant vers la route existante `/api/v1/requests/download/{path}`.

Verification: `python -m compileall backend/api/storage.py backend/api/routes/RouteRequest.py` OK ; `npm run build` cote frontend OK.

## 2026-07-27 - Acces personnel Mon espace pour tous les roles

Demande: garantir que `Mon espace` affiche et ouvre correctement les demandes personnelles pour tous les roles, comme pour le role utilisateur.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `backend/api/routes/RouteRequest.py`
- `docs/codex/API_INDEX.md`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: l'acces detail d'une demande verifie maintenant d'abord si l'acteur connecte est le `requester_id` de la demande. Dans ce cas, l'acces personnel est autorise quel que soit son role metier, sans appliquer le perimetre service/direction. Le detail personnel, la lecture des commentaires et la suppression de commentaires gardent le mode demandeur proprietaire: commentaires internes non publics masques, suppression limitee aux propres commentaires.

Verification: compilation ciblee de `backend/api/routes/RouteRequest.py` OK. Test pytest cible `backend/tests/api/test_requests_baseline.py -k VuePersonnelleBaseline` tente mais non execute dans l'environnement disponible (`No module named pytest` avec Python global; lancement du venv bloque par Windows error 1920).

## 2026-07-27 - Verrouillage edition personnelle demandeur

Demande: corriger la modification d'une demande personnelle pour qu'elle fonctionne sans bug et reste alignee au cahier des charges.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:

- `frontend/src/lib/api/requests.ts`
- `backend/api/routes/RouteRequest.py`
- `backend/api/services/ServiceRequest.py`
- `docs/codex/API_INDEX.md`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: l'edition personnelle via `/requests/{id}/requester-edit` est desormais limitee au titre et a la description dans le type frontend, le schema backend et le service. Les champs internes (`category`, `priority`, `direction_id`, `unit_id`, `unity_id`) ne font plus partie du contrat demandeur et sont refuses par l'API (`extra=forbid`). Le service rejette aussi une edition vide sans champ autorise.

Verification: `python -m compileall backend/api/routes/RouteRequest.py backend/api/services/ServiceRequest.py` OK ; controles `rg` cibles OK sur le schema backend, le service et l'appel frontend `requesterEditRequest`.

## 2026-07-27 - Espaces frontend dedies Chef de Service / Chef Departement

Demande: chaque role doit avoir « son espace propre » — chief-service et chief-departement partageaient jusque-la exactement la meme page `/app/chief-inbox` (aucune route ni composant distinct), la seule difference etant desormais le perimetre de donnees cote backend (voir entree precedente du meme jour).

Module: MOD-CHIEF.

Fichiers modifies/crees:

- `frontend/src/routes/app.chief-inbox.tsx` (composant `ChiefInbox` exporte, rendu route-aware)
- `frontend/src/routes/app.department-inbox.tsx` (nouveau — reutilise `ChiefInbox`)
- `frontend/src/routes/app.department-inbox_.tickets.$id.tsx` (nouveau)
- `frontend/src/lib/ticket-navigation.ts`
- `frontend/src/routes/app.requests.$id.tsx` (contexte `departmentInbox`)
- `frontend/src/components/app-layout.tsx`
- `docs/codex/ROLE_INDEX.md`, `FRONTEND_INDEX.md`, `ROUTE_INDEX.md`, `MODULE_INDEX.md`, `BUSINESS_RULES.md`, `CHANGELOG_CODEX.md`

Correction: creation de la route `/app/department-inbox` (+ detail `/app/department-inbox/tickets/$id`), reservee a `chief-departement` (et `admin`), avec guard de role, titre et back-navigation propres. `/app/chief-inbox` reste reserve a `chief-service` (deja le cas via `requireRole`, aucun changement de guard necessaire). Les deux routes rendent le meme composant `ChiefInbox` (evite la duplication d'environ 600 lignes de logique/JSX) qui detecte l'espace courant via `useRouterState` pour adapter dynamiquement : le libelle d'en-tete et les messages vides (« service » vs « departement »), la cle de requete/cache (`chief-inbox` vs `department-inbox`), le lien de navigation vers le detail ticket (`ticketDetailRouteForList`) et la portee de la liste d'agents assignables (`unit_id` exact vs `direction_id` elargi). Navigation sidebar/mobile mise a jour pour proposer a chaque role son propre lien (plus de partage de l'entree « Boite de traitement » entre les deux roles).

Verification: `npx tsc --noEmit` sans nouvelle erreur imputable aux fichiers touches (erreurs preexistantes non liees dans d'autres fichiers) ; `npx eslint` sans probleme hors bruit prettier CRLF preexistant sur tout le depot.

## 2026-07-27 - Distinction fonctionnelle Chef de Service / Chef Departement

Demande: poursuivre l'alignement CDC des roles en donnant a `chief-departement` un perimetre reellement plus large que `chief-service` (jusque-la, les deux roles etaient des clones stricts partageant exactement le meme perimetre `unity_id`).

Module: MOD-CHIEF / MOD-REQUEST.

Fichiers modifies:

- `backend/api/core/ticket_actions.py`
- `backend/api/services/ServiceRequest.py`
- `backend/api/routes/RouteRequest.py`
- `backend/tests/api/test_ticket_actions.py`
- `frontend/src/routes/app.chief-inbox.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/ROLE_INDEX.md`
- `docs/codex/FRONTEND_INDEX.md`
- `docs/codex/MODULE_INDEX.md`
- `docs/codex/ROUTE_INDEX.md`
- `docs/codex/API_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: `chief-departement` et `chief-service` avaient la meme matrice de permissions ET le meme calcul de perimetre (`actor.unity_id` seul), sans jamais utiliser le mecanisme d'elargissement par organigramme deja disponible (utilise pour `director`). Un chef de departement ne pouvait donc jamais voir ni agir sur les tickets des autres services de son propre departement — la distinction CDC entre les deux roles etait purement nominale. Le listing principal `GET /requests` forcait meme `unit_id` (correspondance exacte) pour `chief-departement`, et le selecteur d'agent assignable du frontend interrogeait `/users?unit_id=...` sur l'unite exacte du chef, qui ne contient generalement aucun agent (les agents sont rattaches aux services, pas au noeud departement) — rendant l'assignation impossible en pratique pour ce role.

Correction: `chief-departement` beneficie desormais du meme mecanisme d'elargissement d'organigramme que `director` (departement + tous ses services descendants), applique de bout en bout : lecture/action ticket (`assert_ticket_scope`, `_guard_ticket_action`), assignation a un agent de n'importe quel service du departement (`assert_assignment_allowed` avec `allowed_scope_unity_ids`), listing principal et par-unite (`list_requests`, `_resolve_access`, `_check_unity_access`), et selecteur d'agent assignable cote frontend (`fetchUsers({ direction_id })` au lieu de `unit_id` pour ce role). `chief-service` reste strictement borne a son unite. Au passage, corrige une sur-permission existante ou `agent-support`/`chief-service` recevaient a tort un perimetre elargi dans `_resolve_access` (acces detail ticket).

Verification: `backend\venv\Scripts\pytest.exe backend\tests\api\test_ticket_actions.py -q` OK avec 69 tests passes (nouveau test `test_chief_departement_can_assign_across_department_scope`). Note: `backend\tests\api\test_requests_baseline.py` presente 21 echecs preexistants non lies a cette intervention — ce fichier de tests n'a pas ete mis a jour lors du renommage de roles du 2026-07-23 et utilise encore les libelles `agent`/`chief` obsoletes ; a traiter separement.

## 2026-07-24 - Alignement Chef de Service actions tracables

Demande: poursuivre l'alignement CDC avec le module Chef de Service.

Module: MOD-CHIEF / MOD-REQUEST.

Fichiers modifies:

- `frontend/src/routes/app.chief-inbox.tsx`
- `backend/api/core/ticket_actions.py`
- `backend/api/services/ServiceRequest.py`
- `backend/tests/api/test_ticket_actions.py`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: la reaffectation service par un chef exige maintenant un motif explicite cote backend et frontend. Le motif nettoye est conserve dans la timeline et les metadonnees. Le renvoi au directeur depuis la boite chef exige aussi un motif avant envoi.

Verification: test cible `backend\\venv\\Scripts\\pytest.exe backend\\tests\\api\\test_ticket_actions.py -q` OK avec 68 tests passes.

## 2026-07-24 - Alignement Agent Support escalade

Demande: poursuivre l'alignement CDC avec le module Agent Support.

Module: MOD-AGENT / MOD-REQUEST.

Fichiers modifies:

- `backend/api/core/ticket_actions.py`
- `backend/tests/api/test_ticket_actions.py`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: la contrainte d'escalade agent utilise maintenant le role normalise `agent-support`. Un agent support ne peut escalader que les tickets qui lui sont personnellement assignes, que le libelle entrant soit l'ancien `agent` ou le role CDC `agent-support`.

Verification: test cible des regles ticket d'abord en echec sur l'escalade agent, puis `backend\\venv\\Scripts\\pytest.exe backend\\tests\\api\\test_ticket_actions.py -q` OK avec 65 tests passes.

## 2026-07-24 - Alignement detail demandeur

Demande: demarrer l'alignement du module Demandeur avec le cahier des charges et verifier creation, `Mes demandes`, `Historique`, accueil personnel et detail.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:

- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: la modification d'une demande personnelle ne montre plus `Categorie`, `Priorite`, `Direction destinataire` ni `Service`. L'interface demandeur envoie uniquement `title` et `description`, en coherence avec la restriction backend existante.

Verification: controle cible des listes personnelles, du formulaire de creation, du detail demandeur et des references mortes.

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

## 2026-07-24 - Normalisation RBAC Agent Support / Chief Service / Chief Département

Demande: normaliser les rôles métier canoniques sans casser le flux existant, en gardant la compatibilité backward sur les libellés historiques de persistance.

Module: MOD-RBAC / MOD-ACCOUNTS.

Fichiers modifies:

- `backend/api/core/rbac.py`
- `backend/api/core/ticket_actions.py`
- `backend/api/models/ModelAccount.py`
- `backend/api/dependencies.py`
- `backend/api/routes/RouteRequest.py`
- `backend/api/routes/RouteAttachment.py`
- `backend/api/services/ServiceAccount.py`
- `backend/tests/api/test_ticket_actions.py`

Correction: la couche technique bascule sur la nomenclature canonique `agent-support`, `chief-service` et `chief-departement`; les alias historiques (`agent`, `chief`, `chief-department`, `chief-dept`) sont remis sur la bonne normalisation sans refonte de workflow.

Verification: exécution directe Python sur `normalize_role()` / `has_role()` / `assert_action_allowed()` confirmant `agent-support -> resolve_allowed=OK` et refus explicite sur `reject`.

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
