# File Index

| Fichier | Couche | Module | Fonction | Dependances importantes | Fonctionnalites |
| --- | --- | --- | --- | --- | --- |
| `frontend/src/components/app-layout.tsx` | frontend | navigation | sidebar, groupes par role, bouton retour | `session.ts`, `notifications.ts`, `ticket-navigation.ts` indirect | separation espaces |
| `frontend/src/lib/capabilities.ts` | frontend | roles/tickets | actions visibles selon role/status | `mock-data.ts` | actions ticket |
| `frontend/src/lib/ticket-navigation.ts` | frontend | navigation ticket | route detail selon source | route files detail | BR-NAV-001 |
| `frontend/src/lib/api/requests.ts` | frontend | request | appels API demandes/tickets | `client.ts` | listes/actions ticket |
| `frontend/src/lib/api/reports.ts` | frontend | reports | appels rapports | fetch direct/API base | reporting |
| `frontend/src/lib/api/notifications.ts` | frontend | notif | appels notifications | `client.ts` | panel/page notifications |
| `frontend/src/routes/app.requests.$id.tsx` | frontend | personal/request | detail personnel | `requests.ts`, timeline | mes demandes |
| `frontend/src/routes/app.requests.index.tsx` | frontend | personal/request | liste mes demandes | `requests.ts` | demandes perso |
| `frontend/src/routes/app.my-tickets.tsx` | frontend | agent | liste tickets agent | `requests.ts` | traitement agent |
| `frontend/src/routes/app.transmitted.tsx` | frontend | agent/workflow | liste des tickets transmis par l'acteur courant | `requests.ts`, `ticket-navigation.ts` | tickets transmis |
| `frontend/src/routes/app.transmitted_.tickets.$id.tsx` | frontend | agent/workflow | detail ticket dans le contexte Tickets transmis | `app.requests.$id.tsx` | tickets transmis, BR-NAV-001 |
| `frontend/src/routes/app.queue.tsx` | frontend | queue | file, a qualifier | `requests.ts` | qualification |
| `frontend/src/routes/app.chief-inbox.tsx` | frontend | chief | boite traitement chef | `requests.ts`, `accounts.ts` | assignation |
| `frontend/src/routes/app.supervision.tsx` | frontend | supervision | centre supervision | `requests.ts`, stats | supervision |
| `frontend/src/routes/app.direction.tsx` | frontend | direction | pilotage direction | `requests.ts`, reports | direction |
| `frontend/src/routes/app.dg.tsx` | frontend | dg | vue globale | reports/stats/escalations | DG |
| `frontend/src/routes/app.reports.tsx` | frontend | reports | rapports | `reports.ts` | performance |
| `frontend/src/routes/app.admin.*.tsx` | frontend | admin | backoffice | `admin-config.ts`, autres services | admin |
| `frontend/src/routes/app.admin.users.tsx` | frontend | admin/users | utilisateurs, roles et affectation organisationnelle dynamique | `accounts.ts`, `directions-units.ts` | admin users |
| `frontend/src/routes/app.admin.directions.tsx` | frontend | org/admin | liste et gestion logique des directions; rend l'Outlet pour le detail `/app/admin/directions/$id` | `directions-units.ts`, `app.admin.directions.$id.tsx` | organisation |
| `frontend/src/routes/app.admin.directions.$id.tsx` | frontend | org/admin | detail direction, chargement donnees et drawer employe | `directions-units.ts`, `accounts.ts`, `direction-org-chart.tsx` | organisation |
| `frontend/src/components/admin/direction-org-chart.tsx` | frontend | org/admin | composant organigramme direction pyramidal avec fallback multi-branches sans fausses photos | `directions-units.ts`, `accounts.ts`, `glass-card.tsx` | organisation |
| `frontend/src/routes/app.admin.departments.tsx` | frontend | org/admin | liste et gestion logique des departements | `directions-units.ts` | organisation |
| `frontend/src/routes/app.admin.units.tsx` | frontend | org/admin | liste et gestion logique des services/unites | `directions-units.ts` | organisation |
| `frontend/src/routes/app.admin.org.tsx` | frontend | org/admin | organigramme synthetique EDG | `directions-units.ts` | organisation |
| `frontend/src/lib/api/directions-units.ts` | frontend | org/admin | client API directions, departements, unites/services | API `/directions`, `/departments`, `/units` | organisation |
| `frontend/src/lib/api/accounts.ts` | frontend | users | client API comptes et alias organisationnels | `client.ts` | users/admin |
| `frontend/src/components/workflow-timeline.tsx` | frontend | workflow | timeline detail | workflow details | historique actions |
| `backend/api/main.py` | backend | app | creation FastAPI, routers | routes | entree backend |
| `backend/api/dependencies.py` | backend | auth/rbac | current user, guards | `rbac.py`, repositories | auth routes |
| `backend/api/core/rbac.py` | backend | roles | permissions cumulatives | enum Permission | RBAC |
| `backend/api/core/ticket_actions.py` | backend | tickets | actions, transitions, scope | exceptions/error codes | regles ticket |
| `backend/api/routes/RouteRequest.py` | backend | request | endpoints demandes/tickets/actions | `ServiceRequest.py`, schemas | tickets |
| `backend/api/services/ServiceRequest.py` | backend | request | logique ticket, ref, routage, actions | repositories, `ticket_actions.py` | tickets |
| `backend/api/repositories/RepositoryRequest.py` | backend | request | requetes request, refs | SQLAlchemy | persistence tickets |
| `backend/api/routes/RouteWorkflow.py` | backend | workflow | endpoints workflows/details | `ServiceWorkflow.py` | timeline/circuit |
| `backend/api/services/ServiceWorkflow.py` | backend | workflow | details, acceptation, circuits | repos workflow | workflow |
| `backend/api/routes/RouteReports.py` | backend | reports | endpoints rapports/export | `ServiceReport.py` | rapports |
| `backend/api/services/ServiceReport.py` | backend | reports | SQL rapports scopes | Request/Account/Unity | performance |
| `backend/api/routes/RouteUsers.py` | backend | users | profil/staff/admin users | `ServiceAccount.py` | users |
| `backend/api/services/ServiceAccount.py` | backend | users/auth | comptes, auth, roles | Account repo/security | users |
| `backend/api/routes/RouteAdminConfig.py` | backend | admin | config SLA/routing/ref/security | services refs/config | admin |
| `backend/api/routes/RouteDirectionsUnits.py` | backend | org/admin | endpoints directions, departements, services/unites sur Unity + Organigram | `ModelUnity.py`, `ModelOrganigram.py` | organisation |
| `backend/api/seed_references.py` | backend | references/org | seed demarrage references et organisation builtin | repositories refs, Unity, Organigram | refs, organisation |
| `backend/api/models/ModelRequest.py` | backend | database | modele request | refs/account/unity/workflow | tickets |
| `backend/api/models/ModelWorkflowDetail.py` | backend | database | modele timeline/commentaires | workflow/account/unity/task | timeline |
| `backend/tests/api/test_ticket_actions.py` | tests | tickets | tests regles action | `ticket_actions.py` | permissions |
| `backend/tests/api/test_requests_baseline.py` | tests | request | tests creation demande | `ServiceRequest.py` | creation/ref |
| `backend/tests/api/test_seed_references_org.py` | tests | organisation | seed respecte les suppressions soft-delete | `seed_references.py`, Unity, Organigram | admin org |
| `backend/tests/api/test_directions_units_hierarchy.py` | tests | organisation | hierarchie direction/departement/service et activation/desactivation | `RouteDirectionsUnits.py` | admin org |
| `backend/tests/api/test_user_org_assignment.py` | tests | users/org | validation des affectations role -> direction/departement/unite | `RouteUsers.py`, `ServiceAccount.py` | admin users |
| `frontend/role-visual-check.mjs` | test outil | visual/routes | test visuel role par role | Chrome CDP, API login | navigation metier |
