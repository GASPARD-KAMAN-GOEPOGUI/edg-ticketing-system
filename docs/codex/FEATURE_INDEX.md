# Feature Index

Ce fichier est le premier point d'entree pour localiser un probleme fonctionnel.

## FEATURE-PERSONAL-REQUESTS

Identifiant: FEATURE-PERSONAL-REQUESTS
Nom: Mes demandes personnelles
Module: MOD-PERSONAL / MOD-REQUEST
Description: creation personnelle, liste, historique et detail des demandes creees par l'utilisateur connecte, sans export personnel. Les formulaires demandeur de creation et d'edition personnelle ne montrent pas les champs internes categorie, priorite, direction destinataire et service. `Mes demandes` contient les statuts actifs/evolutifs; `Historique` contient seulement `closed`, `cancelled`, `rejected`.
Roles concernes: user, agent, chief, director, admin.
Route frontend: `/app/requests`, `/app/requests/$id`.
Page principale: `frontend/src/routes/app.requests.index.tsx`, `frontend/src/routes/app.requests.$id.tsx`.
Composants: `new-request-form.tsx`, `workflow-timeline.tsx`, `appreciation-form.tsx`.
Service frontend: `frontend/src/lib/api/requests.ts`.
Endpoint backend: `GET /api/v1/requests`, `GET /api/v1/requests/{id}`, `POST /api/v1/requests`, `PATCH /api/v1/requests/{id}/requester-edit`.
Route backend: `backend/api/routes/RouteRequest.py`.
Service backend: `backend/api/services/ServiceRequest.py`.
Schemas: `SchemaRequest.py`.
Modeles: `ModelRequest.py`, `ModelWorkflow.py`, `ModelWorkflowDetail.py`.
Tables: `request`, `workflow`, `workflow_detail`.
Permissions: `CREATE_REQUEST`, `VIEW_OWN_REQUESTS`, `CANCEL_REQUEST`, `REOPEN_REQUEST`.
Regles metier: BR-NAV-001, BR-PERSONAL-CREATE-001, BR-PERSONAL-EDIT-001, BR-REQ-001, BR-REQ-REF-001, BR-OWN-001.
Tests: `backend/tests/api/test_requests_baseline.py`, `backend/tests/api/test_ticket_actions.py`.
Fonctionnalites dependantes: notifications, workflow, appreciation.
Chemins probables en cas de probleme: `app.requests.*`, `requests.ts`, `RouteRequest.py`, `ServiceRequest.py`.

## FEATURE-AGENT-TICKETS

Identifiant: FEATURE-AGENT-TICKETS
Nom: Mes tickets agent
Module: MOD-AGENT
Description: tickets personnellement assignes a l'intervenant, KPI dynamiques sur cette charge, actions de traitement, resolution et escalade. Depuis le 2026-08-06, pour `chief-service` et `chief-departement`, la vue inclut aussi les tickets `escalated` du perimetre operationnel autorise, en remplacement de l'ancien onglet `Repartition > Escalades`.
Roles concernes: agent-support, chief-service, chief-departement, director, admin.
Route frontend: `/app/my-tickets`, `/app/my-tickets/tickets/$id`.
Page principale: `frontend/src/routes/app.my-tickets.tsx`, `frontend/src/routes/app.my-tickets_.tickets.$id.tsx`.
Service frontend: `frontend/src/lib/api/requests.ts`.
Endpoint backend: `GET /api/v1/requests?assignee_id={actor_id}`, `GET /api/v1/requests/by-assignee/{assignee_id}`, `POST /api/v1/requests/{id}/resolve`, `POST /api/v1/requests/{id}/escalate`.
Backend: `RouteRequest.py`, `ServiceRequest.py`, `ticket_actions.py`.
Tables: `request`, `workflow_detail`, `task`.
Permissions: agent dans `ACTION_ALLOWED_ROLES`.
Regles metier: BR-ROLE-AGENT-001, BR-TICKET-001, BR-SCOPE-001.
Tests: `test_ticket_actions.py`.
Chemins probables: `app.my-tickets.tsx`, `capabilities.ts`, `ticket-navigation.ts`, `RouteRequest.py`, `ServiceRequest.py`, `ticket_actions.py`.

## FEATURE-QUEUE-QUALIFICATION

Identifiant: FEATURE-QUEUE-QUALIFICATION
Nom: File d'attente et demandes a qualifier
Module: MOD-AGENT / MOD-CHIEF / MOD-DIRECTION
Description: une seule vue — `A qualifier`, pour les demandes a orienter ou a prendre en charge par l'utilisateur connecte. L'ancien onglet `A prendre` (tickets non assignes du perimetre agent/chef, `unassigned_only=true`) a ete retire le 2026-07-29 (voir BR-ROLE-AGENT-001, note retrait onglet) pour tous les roles ayant acces a la page. Depuis le 2026-08-05, tous les roles operationnels (`agent-support`, `chief-service`, `chief-departement`, `director`, `admin`) peuvent prendre un ticket depuis la File d'attente et assigner vers un intervenant operationnel autorise (`dg` exclu ; destinataire admin reserve a admin). Le formulaire d'assignation (bouton `Assigner`) impose depuis le 2026-07-29 une hierarchie stricte Direction -> Departement -> Service -> Personne, chaque niveau filtre aux entites actives et cascade sur le parent choisi (voir BR-TICKET-QUALIFY-001, note formulaire 4 niveaux).
Roles concernes: agent-support, chief-service, chief-departement, director, admin.
Route frontend: `/app/queue`, `/app/queue/tickets/$id`.
Page principale: `frontend/src/routes/app.queue.tsx`, `frontend/src/routes/app.queue_.tickets.$id.tsx`.
Endpoint backend: `GET /api/v1/requests/triage`, `POST /api/v1/requests/{id}/qualify`.
Regles metier: BR-TICKET-QUALIFY-001, BR-SCOPE-001.
Chemins probables: `app.queue.tsx`, `requests.ts`, `RouteRequest.py`, `ServiceRequest.py`.

## FEATURE-CHIEF-INBOX

Identifiant: FEATURE-CHIEF-INBOX
Nom: Centre de repartition (chief-service) — libelle valide au chantier "File d'attente / actions par role" (2026-07-31), anciennement "Boite de traitement chef"
Module: MOD-CHIEF
Description: vue chief-service pour les tickets de son service — liste directe, sans etape d'agregation — et actions d'affectation/reaffectation d'agent, changement de priorite, resolution exceptionnelle (motif obligatoire, Lot 2.6). Depuis le Lot 2.5, chief-service n'a plus acces a "Changer de service" (retire, reserve a chief-departement/director/admin). Panneau "Charge par agent" (Lot 2.2, `GET /requests/workload-by-unit`) affichant le nombre de tickets actifs par agent du service. Depuis le 2026-08-06, l'onglet interne `Escalades` est retire; les escalades operationnelles apparaissent dans `/app/my-tickets`.
Roles concernes: chief-service.
Route frontend: `/app/chief-inbox`, `/app/chief-inbox/tickets/$id`.
Endpoint backend: `GET /api/v1/requests/by-unity/{unity_id}`, `GET /api/v1/requests/workload-by-unit`, `POST /api/v1/requests/{id}/assign`, `POST /api/v1/requests/{id}/priority`, `POST /api/v1/requests/{id}/resolve` (motif obligatoire pour ce role).
Regles metier: BR-ROLE-CHIEF-001, BR-ASSIGN-001, BR-PRIORITY-001.
Chemins probables: `app.chief-inbox.tsx`, `capabilities.ts`, `RouteRequest.py`, `ServiceRequest.py`, `ticket_actions.py`.

## FEATURE-DEPARTMENT-PILOTAGE

Identifiant: FEATURE-DEPARTMENT-PILOTAGE
Nom: Centre de pilotage (chief-departement)
Module: MOD-CHIEF
Description: ecran principal agrege par service du departement (nb tickets, tickets critiques, % SLA, escalades — `AggregatedServiceDashboard` mode `"pilotage"`, alimente par `GET /reports/decision?group_by=service` deja scope departement). Clic sur un service = drill-down vers le composant partage `ChiefInbox` (meme composant que chief-service), filtre a ce seul service. Depuis le 2026-08-06, le drill-down ne contient plus d'onglet interne `Escalades`; les escalades operationnelles apparaissent dans `/app/my-tickets`. Chief-departement ne traite jamais un ticket lui-meme : "Affecter/Reaffecter" et "Traiter/resoudre" retires (Lot 3.1/3.2). Action propre : "Escalade exceptionnelle" (`escalate_to_director`, court-circuite la hierarchie normale, cible directement le directeur, motif obligatoire).
Roles concernes: chief-departement.
Route frontend: `/app/department-inbox` (dashboard), `/app/department-inbox/tickets/$id` (drill-down puis detail).
Endpoint backend: `GET /api/v1/reports/decision`, `GET /api/v1/requests/by-unity/{unity_id}`, `POST /api/v1/requests/{id}/reassign`, `POST /api/v1/requests/{id}/escalate-to-director`, `POST /api/v1/requests/{id}/priority`.
Regles metier: BR-ROLE-CHIEF-DEPARTEMENT-001, BR-ROLE-CHIEF-DEPARTEMENT-002, BR-ESCALATE-EXCEPTIONNELLE-001, BR-REPORT-DECISION-001.
Chemins probables: `app.department-inbox.tsx`, `components/aggregated-service-dashboard.tsx`, `app.chief-inbox.tsx` (composant partage), `capabilities.ts`, `RouteRequest.py`, `ServiceEscalade.py`, `ticket_actions.py`.

## FEATURE-STRATEGIC-DASHBOARD

Identifiant: FEATURE-STRATEGIC-DASHBOARD
Nom: Tableau de bord strategique (director)
Module: MOD-DIRECTION
Description: vue consultative agregee sur toute la direction (Lot 4) — reutilise `AggregatedServiceDashboard` en mode `"strategic"` (lecture seule, pas de drill-down, pas de bouton d'action), avec un resume executif (totaux de la direction, tires du champ `kpis` de la reponse `/reports/decision`) au-dessus des cartes par service. Additif : coexiste avec `/app/direction` et `/app/supervision` sans leur retirer aucune capacite.
Roles concernes: director.
Route frontend: `/app/strategic-dashboard`.
Endpoint backend: `GET /api/v1/reports/decision` (aucun nouvel endpoint — reutilisation totale, deja scope direction via `_apply_decision_scope`).
Regles metier: BR-ROLE-DIRECTOR-001 (note additive), BR-REPORT-DECISION-001.
Chemins probables: `app.strategic-dashboard.tsx`, `components/aggregated-service-dashboard.tsx`, `app-layout.tsx` (groupe "Pilotage").

## FEATURE-SUPERVISION

Identifiant: FEATURE-SUPERVISION
Nom: Centre de supervision
Module: MOD-SUPERVISION
Description: supervision des tickets d'equipe/service/direction selon role, sans confusion avec Mes demandes.
Roles concernes: chief, director.
Route frontend: `/app/supervision`, `/app/supervision/tickets/$id`.
Page principale: `frontend/src/routes/app.supervision.tsx`, `frontend/src/routes/app.supervision_.tickets.$id.tsx`.
Endpoint backend: principalement `GET /api/v1/requests` avec filtres, actions ticket via `RouteRequest.py`.
Regles metier: BR-NAV-001, BR-ROLE-CHIEF-001, BR-ROLE-DIRECTOR-001.
Chemins probables: `app.supervision.tsx`, `ticket-navigation.ts`, `app-layout.tsx`, `RouteRequest.py`, `ServiceRequest.py`.
Note chief-departement: la liste supervision charge le perimetre departemental avec `direction_id=<department unity_id>` pour reutiliser l'expansion backend departement + services, tandis que chief-service reste en `unit_id` exact.
Note UI (2026-08-06): la page `/app/supervision` masque les sections operationnelles `Charge & retards par agent`, `Distribution des escalades` et `Escalades en cours`; les donnees, routes et calculs backend restent inchanges.

## FEATURE-DIRECTION

Identifiant: FEATURE-DIRECTION
Nom: Vue direction
Module: MOD-DIRECTION
Description: pilotage de la direction, tickets de la direction, transfert direction/service, resolution uniquement si escalade/arbitrage.
Roles concernes: director.
Route frontend: `/app/direction`, `/app/direction/tickets/$id`.
Endpoint backend: `GET /api/v1/requests/by-direction/{direction_id}`, `POST /api/v1/requests/{id}/transfer-direction`, `POST /api/v1/requests/{id}/resolve`.
Regles metier: BR-ROLE-DIRECTOR-001, BR-TRANSFER-001, BR-DIRECTOR-RESOLVE-001.
Chemins probables: `app.direction.tsx`, `app.direction_.tickets.$id.tsx`, `RouteRequest.py`, `ticket_actions.py`.
Voir aussi: FEATURE-STRATEGIC-DASHBOARD (vue consultative additive distincte, `/app/strategic-dashboard`, aucune capacite de traitement).

## FEATURE-GLOBAL-ADMIN

Identifiant: FEATURE-GLOBAL-ADMIN
Nom: Vue globale admin
Module: MOD-GLOBAL / MOD-ADMIN
Description: pilotage global admin, suivi des escalades/SLA, consultation globale; filtre "Toutes les directions" ou direction precise avec regroupement des tickets par statut et export du rapport par service/unite.
Roles concernes: admin.
Route frontend: `/app/dg`, `/app/dg/tickets/$id`.
Endpoint backend: `GET /api/v1/requests?direction_id=...`, `GET /api/v1/stats/*`, `GET /api/v1/reports/*`, `GET /api/v1/reports/by-unity/export?direction_id=...`, `GET /api/v1/escalations`.
Regles metier: BR-ROLE-ADMIN-001, BR-ADMIN-GLOBAL-001, BR-SLA-001, BR-ROLE-LEGACY-DG-001.
Chemins probables: `app.dg.tsx`, `app.dg_.tickets.$id.tsx`, `requests.ts`, `reports.ts`, `RouteStats.py`, `RouteReports.py`, `RouteEscalation.py`.

## FEATURE-ADMIN-TICKETS

Identifiant: FEATURE-ADMIN-TICKETS
Nom: Administration ticket
Module: MOD-ADMIN / MOD-REQUEST
Description: consultation et administration d'un ticket dans le contexte admin.
Roles concernes: admin.
Route frontend: `/app/admin/tickets/$id`.
Endpoint backend: endpoints `RouteRequest.py` + config admin.
Regles metier: BR-NAV-001, BR-ROLE-ADMIN-001.
Chemins probables: `app.admin.tickets.$id.tsx`, `ticket-navigation.ts`, `RouteRequest.py`.

## FEATURE-WORKFLOW-TIMELINE

Identifiant: FEATURE-WORKFLOW-TIMELINE
Nom: Timeline, commentaires et actions
Module: MOD-WORKFLOW
Description: historique visible dans le detail du ticket, commentaires, actions, escalades, reopen.
Roles concernes: agent, chief, director, admin, demandeur selon visibilite.
Route frontend: composant detail ticket + `workflow-timeline.tsx`.
Endpoint backend: `GET/POST /api/v1/requests/{request_id}/comments`, `GET/POST /api/v1/requests/{request_id}/timeline`, `/api/v1/workflows/*`.
Regles metier: BR-TIMELINE-001, BR-REOPEN-001, BR-REOPEN-QUEUE-001.
Chemins probables: `workflow-timeline.tsx`, `RouteRequest.py`, `RouteWorkflow.py`, `ServiceWorkflow.py`, `ModelWorkflowDetail.py`.

## FEATURE-COLLABORATIVE-TREATMENT

Identifiant: FEATURE-COLLABORATIVE-TREATMENT
Nom: Workflow collaboratif dynamique post-file d'attente
Module: MOD-AGENT / MOD-CHIEF / MOD-DIRECTION / MOD-WORKFLOW
Description: apres qualification/assignation, le traitement suit un parcours dynamique — pas de chaine fixe. L'intervenant actuel (`assignee_id`) peut "Transmettre le traitement" a n'importe quel intervenant traitant actif de l'organisation (motif + travail effectue obligatoires, instruction/pieces jointes facultatives, statut preserve), ou "Terminer le traitement" (resume/solution/travail realise obligatoires) s'il est reserve a lui. Un meme acteur peut intervenir plusieurs fois (cycles distincts, tous conserves dans l'historique append-only).
Roles concernes: agent-support, chief-service, chief-departement, director (intervenants traitants) ; admin (bypass exceptionnel, jamais un traitement normal).
Route frontend: composant detail ticket partage (`RequestDetailPage`, `app.requests.$id.tsx`), boutons "Transmettre le traitement"/"Terminer le traitement" dans l'onglet Traitement.
Endpoint backend: `POST /api/v1/requests/{id}/transmit`, `POST /api/v1/requests/{id}/resolve`.
Route backend: `backend/api/routes/RouteRequest.py`.
Service backend: `backend/api/services/ServiceRequest.py` (`transmit_treatment`, `resolve`).
Modeles: `ModelRequest.py` (`assignee_id`), `ModelWorkflowDetail.py` (`treatment_transmitted`, `treatment_completed`).
Tables: `request`, `workflow`, `workflow_detail` (aucune nouvelle table).
Permissions: garde generique `assert_is_current_handler` (`ticket_actions.py`) — remplace le role seul pour ces deux actions.
Regles metier: BR-TRANSMIT-001 (remplace/assouplit BR-ROLE-CHIEF-DEPARTEMENT-001 Lot 3.2 et BR-DIRECTOR-RESOLVE-001 pour ces deux actions precises).
Tests: `backend/tests/api/test_transmit_treatment.py`.
Fonctionnalites dependantes: notifications (BR-NOTIF-001), timeline/participants (FEATURE-WORKFLOW-TIMELINE), temps reel (`request.transmitted`).
Chemins probables: `ticket_actions.py`, `ServiceRequest.py`, `RouteRequest.py`, `app.requests.$id.tsx`, `capabilities.ts`, `requests.ts`, `workflow-timeline.tsx`.

## FEATURE-REOPEN-QUEUE

Identifiant: FEATURE-REOPEN-QUEUE
Nom: Retour automatique d'un ticket reouvert dans la File d'attente
Module: MOD-AGENT / MOD-CHIEF / MOD-WORKFLOW
Description: quand une demande de reouverture est approuvee, le ticket libere systematiquement son ancien intervenant (`assignee_id=null`, jamais de reaffectation automatique) et retourne dans la File d'attente (`in_triage=true`) comme n'importe quelle demande en attente. Un nouvel agent (ou le meme, s'il le choisit) doit la reprendre depuis la File d'attente pour demarrer un nouveau cycle collaboratif dynamique (FEATURE-COLLABORATIVE-TREATMENT) — transmission/terminaison redeviennent alors disponibles pour ce nouvel intervenant. Corrige le blocage identifie par la verification du workflow dynamique (2026-08-04) : sans ce correctif, un ticket reouvert restait affecte a l'ancien intervenant mais hors des statuts autorises pour transmettre/resoudre (`reopened` volontairement exclu de `TICKET_ACTION_STATUSES.transmit_treatment`/`resolve`), bloquant definitivement le workflow.
Roles concernes: chief-service/chief-departement/director/admin (approbation) ; agent-support/chief-service/chief-departement (reprise depuis la File d'attente).
Route frontend: `app.queue.tsx` (badge `Réouverte` + encart motif/ancien intervenant/date sur la carte depliee), `app.requests.$id.tsx` (message "Ce ticket réouvert attend une nouvelle prise en charge.").
Endpoint backend: `POST /api/v1/requests/{id}/reopen` (comportement etendu, pas de nouvel endpoint).
Route backend: `backend/api/routes/RouteRequest.py`.
Service backend: `backend/api/services/ServiceRequest.py` (`reopen`).
Modeles: `ModelRequest.py` (`assignee_id`, `in_triage`, `request_status`), `ModelWorkflowDetail.py` (`reopened`), `ModelNotification.py`.
Tables: `request`, `workflow_detail`, `notification` (aucune nouvelle table).
Regles metier: BR-REOPEN-QUEUE-001 (etend BR-REOPEN-001).
Tests: `backend/tests/api/test_reopen_queue.py`.
Fonctionnalites dependantes: File d'attente (`GET /requests/triage`), notifications (BR-NOTIF-001), timeline (FEATURE-WORKFLOW-TIMELINE), workflow collaboratif dynamique (FEATURE-COLLABORATIVE-TREATMENT), temps reel (`request.reopened`, deja dans `INVALIDATION_MAP`).
Chemins probables: `ServiceRequest.py`, `RepositoryRequest.py` (`_QUALIFIABLE_STATUSES`), `RouteRequest.py`, `app.queue.tsx`, `app.requests.$id.tsx`, `capabilities.ts`.

## FEATURE-SLA-REOPEN-CYCLES

Identifiant: FEATURE-SLA-REOPEN-CYCLES
Nom: Cycles SLA independants apres reouverture
Module: MOD-WORKFLOW / MOD-CHIEF / MOD-DIRECTION / MOD-REPORT
Description: le premier cycle SLA (creation -> premiere resolution) est fige definitivement et n'est jamais recalcule ; chaque reouverture approuvee (FEATURE-REOPEN-QUEUE) ouvre un nouveau cycle SLA independant mesure depuis la date de reouverture, permettant de comparer la performance du premier traitement et de chaque traitement post-reouverture separement, y compris sur plusieurs reouvertures successives. Reconstruit entierement depuis `workflow_detail` (aucune nouvelle table/colonne).
Roles concernes: agent-support/chief-service/chief-departement/director (traitement, visible dans le detail ticket) ; chief-service/chief-departement/director/admin (KPI agreges, Centre SLA).
Route frontend: `app.requests.$id.tsx` (onglet "Activité SLA" — un bloc par cycle : motif de reouverture, debut, fin, temps de resolution, respect SLA), `app.sla-center.tsx` (rangee KPI "Réouvertures").
Endpoint backend: `GET /api/v1/reports/sla/reopen-stats` (nouveau, additif) ; donnees par ticket exposees via `GET /api/v1/requests/{id}` (`sla_cycles`, `reopen_count`).
Route backend: `backend/api/routes/RouteReports.py`, `backend/api/routes/RouteRequest.py`.
Service backend: `backend/api/services/ServiceRequest.py` (`_sla_cycle_snapshot`, appele par `resolve`), `backend/api/services/ServiceEscalade.py` (`mark_sla_breached`, ancre sur la derniere reouverture), `backend/api/services/ServiceReport.py` (`sla_reopen_stats`).
Modeles: `ModelRequest.py` (`sla_cycles`, `reopen_count`, proprietes calculees).
Tables: `request` (`sla_hours`/`sla_elapsed`/`sla_breached` restent "live"), `workflow_detail` (`treatment_completed.infos` porte l'instantane gele par cycle) — aucune nouvelle table.
Regles metier: BR-SLA-REOPEN-001.
Tests: `backend/tests/api/test_sla_reopen.py`.
Fonctionnalites dependantes: FEATURE-REOPEN-QUEUE (le nouveau cycle demarre a l'evenement `reopened`), timeline (FEATURE-WORKFLOW-TIMELINE), rapports SLA existants (non modifies, extension strictement additive).
Chemins probables: `ServiceRequest.py`, `ServiceEscalade.py`, `ModelRequest.py`, `ServiceReport.py`, `RouteReports.py`, `app.requests.$id.tsx`, `app.sla-center.tsx`.

## FEATURE-TRACE-INTERVENTIONS

Identifiant: FEATURE-TRACE-INTERVENTIONS
Nom: Traçabilité complète des interventions
Module: MOD-WORKFLOW / MOD-AGENT / MOD-CHIEF / MOD-DIRECTION / MOD-REPORT
Description: la timeline devient un journal d'interventions hierarchique (Cycle -> Intervention) plutot qu'une simple liste d'evenements. Une intervention est un conteneur logique regroupant tout le travail d'un intervenant (commentaires, pieces jointes, travail effectue) depuis qu'il devient l'intervenant courant jusqu'a sa transmission ou sa resolution — identification (`intervention_id`/`intervention_order`/`intervention_cycle_number`) et identite de l'intervenant (matricule/direction/departement/service) explicitement enregistrees et figees a l'ecriture, jamais recalculees ni dependantes d'une jointure live. Compatible avec le workflow collaboratif dynamique (FEATURE-COLLABORATIVE-TREATMENT) et les cycles SLA (FEATURE-SLA-REOPEN-CYCLES), reconstruit entierement depuis `workflow_detail` (aucune nouvelle table/colonne).
Roles concernes: agent-support/chief-service/chief-departement/director (consultation detail ticket) ; chief-service/chief-departement/director/admin (KPI agreges, Centre SLA).
Route frontend: `app.requests.$id.tsx` (onglet "Journal" — bascule "Journal des interventions" (defaut) / "Chronologie complete"), `app.sla-center.tsx` (rangee KPI "Interventions" + tableau par agent).
Endpoint backend: `GET /api/v1/reports/interventions` (nouveau, additif) ; donnees par ticket exposees via `GET /api/v1/requests/{id}` (`interventions`, incluant `actor_role`/`summary`/`solution`/`recommendations`).
Route backend: `backend/api/routes/RouteReports.py`, `backend/api/routes/RouteRequest.py`.
Service backend: `backend/api/services/ServiceRequest.py` (`_actor_identity_snapshot`, `_open_intervention`, `_current_intervention_meta`, `_intervention_meta_for_actor`), `backend/api/services/ServiceReport.py` (`intervention_stats`).
Modeles: `ModelRequest.py` (`interventions`, propriete calculee).
Tables: `request` (`infos` — pointeur "intervention courante", live), `workflow_detail` (`infos` enrichi sur `assigned`/`treatment_transmitted`/`treatment_completed`/`reopened`/`comment_added`/`attachment_added`) — aucune nouvelle table.
Regles metier: BR-TRACE-001.
Tests: `backend/tests/api/test_trace_interventions.py`.
Fonctionnalites dependantes: FEATURE-COLLABORATIVE-TREATMENT (une intervention se ferme par transmission/resolution), FEATURE-REOPEN-QUEUE (nouveau cycle a chaque reouverture), FEATURE-SLA-REOPEN-CYCLES (`intervention_cycle_number` aligne sur `sla_cycle_number`), timeline (FEATURE-WORKFLOW-TIMELINE, conservee en bascule).
Chemins probables: `ServiceRequest.py`, `ModelRequest.py`, `ServiceReport.py`, `RouteReports.py`, `RouteRequest.py`, `intervention-journal.tsx`, `intervention-filters.tsx`, `intervention-detail-body.tsx`, `intervention-details-modal.tsx`, `intervention-utils.ts`, `app.requests.$id.tsx`, `app.sla-center.tsx`.

### Sous-composants UI (Journal d'intervention premium, 2026-08-04)

- `frontend/src/components/intervention-journal.tsx` — orchestrateur (`InterventionJournal`) : resume compact (`InterventionSummary`), sections de cycle repliables (`CycleSection`), cartes d'intervention (`InterventionCard`), separateur de reouverture (`ReopenSeparator`), liaison de transmission (`TransferLink`), badge de statut (`StatusPill`). Filtrage client-side pur sur les `interventions` deja chargees (aucun nouvel appel reseau).
- `frontend/src/components/intervention-detail-body.tsx` — `InterventionDetailBody`, corps de detail partage entre la carte depliee et la fiche de consultation (une seule source de rendu — travail effectue, resultat/solution, commentaires rattaches, instruction, pieces jointes avec auteur/date/taille, transmission ancien->nouveau, SLA).
- `frontend/src/components/intervention-details-modal.tsx` — `InterventionDetailsModal`, fiche de consultation en lecture seule (`Dialog` shadcn), aucune action de modification/suppression.
- `frontend/src/components/intervention-filters.tsx` — `InterventionFilters` (popover), filtres (cycle/intervenant/service/decision/pieces jointes/SLA depasse) + recherche texte, compact.
- `frontend/src/lib/intervention-utils.ts` — helpers partages (formatage date/duree, libelle de role via `roleLabels` deja existant, statut reel d'intervention derive de `decision` — aucun statut invente).
- Reutilise sans duplication : `Avatar`/`AvatarFallback` + `initialsFor()` (deja utilises dans le fil de commentaires), `Popover`/`Dialog`/`Select`/`Checkbox`/`Input` (primitives shadcn deja presentes), `handleAttachmentFile`/`handleTimelineAttachmentOpen` (deja existants dans `app.requests.$id.tsx`).
- Export : bouton "Exporter le journal" prepare (visible, desactive) — aucun moteur d'export par ticket n'existe a ce jour (seuls les rapports agreges en ont un) ; decision utilisateur validee de ne pas construire de nouveau pipeline backend pour cette iteration.

## FEATURE-NOTIFICATIONS

Identifiant: FEATURE-NOTIFICATIONS
Nom: Notifications personnelles et workflow
Module: MOD-NOTIF
Description: page et panneau de notifications, avec destinataire unique selon le prochain acteur du workflow ticket.
Roles concernes: user, agent, chief, director, admin.
Route frontend: `/app/notifications`.
Composants: `frontend/src/components/notification-panel.tsx`.
Service frontend: `frontend/src/lib/api/notifications.ts`, `frontend/src/lib/realtime/invalidation-map.ts`.
Endpoint backend: `GET/PATCH/POST /api/v1/notifications/*`, actions ticket qui appellent `NotificationEmitter.py`.
Route backend: `backend/api/routes/RouteNotification.py`, `backend/api/routes/RouteSSE.py`.
Service backend: `backend/api/services/ServiceNotification.py`, `backend/api/services/NotificationEmitter.py`.
Email backend: `backend/api/core/mailer.py`, templates HTML dans `backend/templates/`.
Tables: `notification`, `workflow_detail`, `request`, `account`.
Regles metier: BR-NOTIF-001, BR-NAV-001.
Chemins probables: `notification-panel.tsx`, `notifications.ts`, `NotificationEmitter.py`, `ServiceRequest.py`, `RouteNotification.py`, `RepositoryNotification.py`, `event_bus.py`.

## FEATURE-REPORTS

Identifiant: FEATURE-REPORTS
Nom: Rapports
Module: MOD-REPORT
Description: rapports journaliers, mensuels, par agent, par service/unite, SLA, CSAT et moteur decisionnel hierarchique EDG -> direction -> service -> agent -> ticket, avec vues executive, analytique et audit. Depuis le 2026-08-06, pour `chief-service`, le filtre direction est masque dans `/app/reports` et les rapports par agent/service/CSAT sont forces cote backend sur le service exact de l'acteur. Depuis le 2026-08-06, le bandeau visuel `Filtres` / periode / compteur tickets est retire de la page; les valeurs par defaut continuent d'alimenter les exports et chargements existants. Depuis le 2026-08-06, l'entree sidebar `Rapports Service` est masquee pour `chief-service`; les entrees rapports des roles `chief-departement`, `director` et `admin` restent visibles.
Roles concernes: chief, director, admin.
Route frontend: `/app/reports`.
Endpoint backend: `/api/v1/reports/daily`, `/monthly`, `/by-agent`, `/by-unity`, `/decision`, `/decision/export`, `/sla`, `/csat`.
Regles metier: BR-REPORT-001, BR-REPORT-DECISION-001, BR-DIRECTION-SERVICE-001, BR-ADMIN-GLOBAL-001.
Chemins probables: `app.reports.tsx`, `reports.ts`, `RouteReports.py`, `ServiceReport.py`, `REPORTING_DECISION_ENGINE.md`.

## FEATURE-ADMIN-CONFIG

Identifiant: FEATURE-ADMIN-CONFIG
Nom: Configuration admin
Module: MOD-ADMIN
Description: utilisateurs, organisation, referentiels, routage, SLA, priorites, communication, audit.
Roles concernes: admin.
Routes frontend: `/app/admin/*`.
Endpoint backend: `/api/v1/admin/*`, `/api/v1/users/*`, `/api/v1/directions`, `/api/v1/departments`, `/api/v1/units`, `/api/v1/references/*`.
Regles metier: BR-ROLE-ADMIN-001, BR-ADMIN-USER-ORG-001, BR-ORG-HIERARCHY-001, BR-ORG-DELETE-001.
Chemins probables: `app.admin.*.tsx`, `app.admin.users.tsx`, `accounts.ts`, `admin-config.ts`, `directions-units.ts`, `RouteAdminConfig.py`, `RouteUsers.py`, `ServiceAccount.py`, `RouteDirectionsUnits.py`.

## FEATURE-ADMIN-ORG

Identifiant: FEATURE-ADMIN-ORG
Nom: Structure organisationnelle admin
Module: MOD-ADMIN / MOD-ORG
Description: gestion des directions, departements et services/unites sur la meme table `unity`, avec hierarchie `organigram.parent_id`, recherche, filtres actifs/inactifs, activation/desactivation et detail direction en organigramme pyramidal interactif. Le detail affiche toujours une representation pyramidale Directeur -> Chefs de departement -> Chefs de service -> Membres meme si aucune branche active n'existe encore.
Roles concernes: admin.
Routes frontend: `/app/admin/org`, `/app/admin/directions`, `/app/admin/directions/$id`, `/app/admin/departments`, `/app/admin/units`.
Composant frontend: `frontend/src/components/admin/direction-org-chart.tsx`.
Service frontend: `frontend/src/lib/api/directions-units.ts`, `frontend/src/lib/api/accounts.ts` pour le personnel affiche dans le detail direction.
Endpoint backend: `GET/POST/PATCH /directions/*`, `GET/POST/PATCH /departments/*`, `GET/POST/PATCH /units/*`, actions `/activate` et `/deactivate`.
Route backend: `backend/api/routes/RouteDirectionsUnits.py`.
Modeles: `ModelUnity.py`, `ModelOrganigram.py`, `ModelAccount.py`.
Tables: `unity`, `organigram`, `account`.
Regles metier: BR-ORG-HIERARCHY-001, BR-ORG-DELETE-001.
Tests: `backend/tests/api/test_directions_units_hierarchy.py`, `backend/tests/api/test_seed_references_org.py`.
Chemins probables: `app.admin.directions.tsx`, `app.admin.directions.$id.tsx`, `app.admin.departments.tsx`, `app.admin.units.tsx`, `app.admin.org.tsx`, `directions-units.ts`, `RouteDirectionsUnits.py`.
Note UI: le clic sur `Voir` dans `/app/admin/directions` ouvre `/app/admin/directions/$id`; cette page delegue le rendu au composant `DirectionOrgChart`, qui affiche les donnees reelles sous forme de pyramide Directeur -> Departement -> Service/Unite -> Collaborateurs. Si la direction n'a pas encore de directeur, chef de departement, chef de service ou collaborateur actif, la page garde une pyramide multi-branches avec emplacements explicites non renseignes et sans fausses photos. Chaque avatar/personne reel est cliquable et ouvre un drawer detail employe.
