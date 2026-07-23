# Feature Index

Ce fichier est le premier point d'entree pour localiser un probleme fonctionnel.

## FEATURE-PERSONAL-REQUESTS

Identifiant: FEATURE-PERSONAL-REQUESTS
Nom: Mes demandes personnelles
Module: MOD-PERSONAL / MOD-REQUEST
Description: creation personnelle, liste, historique et detail des demandes creees par l'utilisateur connecte, sans export personnel. Le formulaire de creation demandeur ne montre pas les champs internes categorie, priorite, direction destinataire et service. `Mes demandes` contient les statuts actifs/evolutifs; `Historique` contient seulement `closed`, `cancelled`, `rejected`.
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
Regles metier: BR-NAV-001, BR-PERSONAL-CREATE-001, BR-REQ-001, BR-REQ-REF-001, BR-OWN-001.
Tests: `backend/tests/api/test_requests_baseline.py`, `backend/tests/api/test_ticket_actions.py`.
Fonctionnalites dependantes: notifications, workflow, appreciation.
Chemins probables en cas de probleme: `app.requests.*`, `requests.ts`, `RouteRequest.py`, `ServiceRequest.py`.

## FEATURE-AGENT-TICKETS

Identifiant: FEATURE-AGENT-TICKETS
Nom: Mes tickets agent
Module: MOD-AGENT
Description: tickets personnellement assignes a l'agent, KPI dynamiques sur cette charge, actions de traitement, resolution et escalade.
Roles concernes: agent.
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
Module: MOD-AGENT / MOD-CHIEF
Description: deux vues seulement: `A prendre` pour les tickets non assignes disponibles dans le perimetre agent/chef, et `A qualifier` pour les demandes a orienter ou a prendre en charge par l'utilisateur connecte.
Roles concernes: agent, chief.
Route frontend: `/app/queue`, `/app/queue/tickets/$id`.
Page principale: `frontend/src/routes/app.queue.tsx`, `frontend/src/routes/app.queue_.tickets.$id.tsx`.
Endpoint backend: `GET /api/v1/requests/queue?unassigned_only=true`, `GET /api/v1/requests/triage`, `POST /api/v1/requests/{id}/qualify`.
Regles metier: BR-TICKET-QUALIFY-001, BR-SCOPE-001.
Chemins probables: `app.queue.tsx`, `requests.ts`, `RouteRequest.py`, `ServiceRequest.py`.

## FEATURE-CHIEF-INBOX

Identifiant: FEATURE-CHIEF-INBOX
Nom: Boite de traitement chef
Module: MOD-CHIEF
Description: vue chef pour les tickets de service et actions d'assignation/reassignation.
Roles concernes: chief.
Route frontend: `/app/chief-inbox`, `/app/chief-inbox/tickets/$id`.
Endpoint backend: `GET /api/v1/requests/by-unity/{unity_id}`, `POST /api/v1/requests/{id}/assign`, `POST /api/v1/requests/{id}/reassign`, `POST /api/v1/requests/{id}/priority`.
Regles metier: BR-ROLE-CHIEF-001, BR-ASSIGN-001, BR-PRIORITY-001.
Chemins probables: `app.chief-inbox.tsx`, `capabilities.ts`, `RouteRequest.py`, `ticket_actions.py`.

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
Regles metier: BR-TIMELINE-001, BR-REOPEN-001.
Chemins probables: `workflow-timeline.tsx`, `RouteRequest.py`, `RouteWorkflow.py`, `ServiceWorkflow.py`, `ModelWorkflowDetail.py`.

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
Tables: `notification`, `workflow_detail`, `request`, `account`.
Regles metier: BR-NOTIF-001, BR-NAV-001.
Chemins probables: `notification-panel.tsx`, `notifications.ts`, `NotificationEmitter.py`, `ServiceRequest.py`, `RouteNotification.py`, `RepositoryNotification.py`, `event_bus.py`.

## FEATURE-REPORTS

Identifiant: FEATURE-REPORTS
Nom: Rapports
Module: MOD-REPORT
Description: rapports journaliers, mensuels, par agent, par service/unite, SLA, CSAT et moteur decisionnel hierarchique EDG -> direction -> service -> agent -> ticket, avec vues executive, analytique et audit.
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
