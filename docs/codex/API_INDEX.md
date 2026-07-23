# API Index

Base API frontend: `/api/v1` en production, `http://localhost:8000/api/v1` en dev.

## Endpoints principaux

| Methode | Endpoint | Router | Service | Modeles | Tables | Permissions | Frontend utilisateur |
| --- | --- | --- | --- | --- | --- | --- | --- |
| POST | `/auth/login` | `RouteAuth.py` | `ServiceAccount.py` | Account | `account` | public | login/admin-login |
| POST | `/auth/refresh` | `RouteAuth.py` | auth core | Account | `account` | refresh token | API client |
| GET | `/users/me` | `RouteUsers.py` | `ServiceAccount.py` | Account | `account` | authenticated | profil/layout |
| PATCH | `/users/me` | `RouteUsers.py` | `ServiceAccount.py` | Account | `account` | authenticated | profil |
| GET/POST/PATCH/DELETE | `/users/*` | `RouteUsers.py` | `ServiceAccount.py` | Account/Unity/Organigram | `account`, `unity`, `organigram` | admin pour mutations; staff pour lecture annuaire | admin utilisateurs & roles |
| GET/POST/PATCH/DELETE | `/directions/*` | `RouteDirectionsUnits.py` | Unity/Organigram | Unity, Organigram | `unity`, `organigram` | authenticated; admin pour ecriture | admin directions + detail organigramme |
| GET/POST/PATCH/DELETE | `/departments/*` | `RouteDirectionsUnits.py` | Unity/Organigram | Unity, Organigram | `unity`, `organigram` | authenticated; admin pour ecriture | admin departements |
| GET/POST/PATCH/DELETE | `/units/*` | `RouteDirectionsUnits.py` | Unity/Organigram | Unity, Organigram | `unity`, `organigram` | authenticated; admin pour ecriture | admin services/unites |
| GET | `/requests` | `RouteRequest.py` | `ServiceRequest.py` | Request | `request` | authenticated, scoping service; admin peut filtrer `direction_id`; `exclude_status` optionnel et peut exclure plusieurs statuts separes par virgule | listes demandes/tickets, vue globale |
| POST | `/requests` | `RouteRequest.py` | `ServiceRequest.py` | Request | `request`, `workflow` | `CREATE_REQUEST` | nouvelle demande |
| GET | `/requests/{id}` | `RouteRequest.py` | `ServiceRequest.py` | Request | `request` | scoping; `include_deleted=true` admin uniquement | details tickets |
| PATCH | `/requests/{id}` | `RouteRequest.py` | `ServiceRequest.py` | Request | `request` | scoping/admin selon champs | modification |
| PATCH | `/requests/{id}/requester-edit` | `RouteRequest.py` | `ServiceRequest.py` | Request | `request` | demandeur, statut `new` | detail personnel |
| GET | `/requests/queue` | `RouteRequest.py` | `ServiceRequest.py` | Request | `request` | agent/chief | file d'attente; `unassigned_only=true` pour la vue `A prendre` |
| GET | `/requests/triage` | `RouteRequest.py` | `ServiceRequest.py` | Request | `request` | agent/chief/admin | a qualifier; retourne uniquement `new`, `qualifying`, `qualified`, `reopened` |
| POST | `/requests/{id}/qualify` | `RouteRequest.py` | `ServiceRequest.py` | Request | `request`, `workflow_detail` | agent/chief/admin | qualification; `direction_id` optionnel si `unit_id` est fourni |
| POST | `/requests/{id}/assign` | `RouteRequest.py` | `ServiceRequest.py` | Request | `request`, `workflow_detail` | agent/chief/admin + regles | assignation |
| POST | `/requests/{id}/resolve` | `RouteRequest.py` | `ServiceRequest.py` | Request | `request`, `workflow_detail` | agent/chief/director/admin | resolution |
| POST | `/requests/{id}/close` | `RouteRequest.py` | `ServiceRequest.py` | Request | `request`, `workflow_detail` | demandeur/user+ selon regle | cloture |
| POST | `/requests/{id}/request-reopen` | `RouteRequest.py` | `ServiceRequest.py` | Request | `workflow_detail` | demandeur | demande reouverture |
| POST | `/requests/{id}/reopen` | `RouteRequest.py` | `ServiceRequest.py` | Request | `request`, `workflow_detail` | chief/director/admin | approuver reouverture |
| POST | `/requests/{id}/reject-reopen` | `RouteRequest.py` | `ServiceRequest.py` | Request | `workflow_detail` | chief/director/admin | rejet reouverture |
| POST | `/requests/{id}/cancel` | `RouteRequest.py` | `ServiceRequest.py` | Request | `request`, `workflow_detail` | user/agent/chief/director/admin | annulation |
| POST | `/requests/{id}/reject` | `RouteRequest.py` | `ServiceRequest.py` | Request | `request`, `workflow_detail` | chief/admin | rejet |
| POST | `/requests/{id}/priority` | `RouteRequest.py` | `ServiceRequest.py` | Request | `request` | chief/director/admin | priorite |
| POST | `/requests/{id}/reassign` | `RouteRequest.py` | `ServiceRequest.py` | Request | `request`, `workflow_detail` | chief/director/admin | changement service |
| POST | `/requests/{id}/transfer-direction` | `RouteRequest.py` | `ServiceRequest.py` | Request | `request`, `workflow_detail` | director/admin | transfert direction |
| POST | `/requests/{id}/escalate` | `RouteRequest.py` | `ServiceRequest.py` | WorkflowDetail | `workflow_detail` | agent/chief/director/admin | escalade |
| GET/POST | `/requests/{id}/comments` | `RouteRequest.py` | `ServiceWorkflow.py` | WorkflowDetail | `workflow_detail` | scoping ticket | commentaires |
| GET | `/requests/{id}/timeline` | `RouteRequest.py` | `ServiceWorkflow.py` | WorkflowDetail | `workflow_detail` | scoping ticket | timeline |
| GET | `/workflows/*` | `RouteWorkflow.py` | `ServiceWorkflow.py` | Workflow | `workflow` | agent+ selon endpoint | workflow |
| GET | `/reports/by-agent` | `RouteReports.py` | `ServiceReport.py` | Request/Account | `request`, `account` | chief/director/admin | rapports |
| GET | `/reports/by-unity` | `RouteReports.py` | `ServiceReport.py` | Request/Unity | `request`, `unity` | chief/director/admin; `direction_id` pour vue direction/admin | performance service, rapport direction |
| GET | `/reports/decision` | `RouteReports.py` | `ServiceReport.py` | Request/Workflow/Unity/Account | `request`, `workflow`, `workflow_detail`, `unity`, `account` | chief/director/admin; scoping role + filtres | moteur decisionnel |
| GET | `/reports/decision/export` | `RouteReports.py` | `ServiceReport.py` | Request/Workflow/Unity/Account | `request`, `workflow`, `workflow_detail`, `unity`, `account` | chief/director/admin; scoping role + filtres | export decisionnel |
| GET | `/stats/*` | `RouteStats.py` | `ServiceStats.py` | Request | `request` | role selon endpoint | dashboards |
| GET/PATCH/POST | `/notifications/*` | `RouteNotification.py` | `ServiceNotification.py` | Notification | `notification` | authenticated | panel/page notifications |
| GET/POST/PATCH | `/admin/*` | `RouteAdminConfig.py` | services config | refs/config | refs, sla, routing | admin | admin |

## Payloads et erreurs

- Payloads ticket: schemas dans `backend/api/schemas/SchemaRequest.py`.
- Payloads workflow/commentaires: `SchemaWorkflowDetail.py`.
- Reponses: enveloppes `RequestResponse`, `RequestListItemResponse`, `WorkflowDetailResponse`, `PaginatedResponse`.
- Erreurs metier: `ForbiddenException`, `BusinessException`, `ValidationException` dans `backend/api/core/exceptions.py`; codes dans `error_codes.py`.
- Validations action/status/scope: `backend/api/core/ticket_actions.py`.

## Rapports decisionnels

`GET /reports/decision` accepte les filtres `start`, `end`, `direction_id`, `unity_id`, `assignee_id`, `status`, `category`, `priority`, `source`, `origin`, `search`, `group_by`, `inactive_days`, `page`, `limit`, `sort_by`, `sort_dir`, `include_tickets`, `include_audit_rows`.

`status`, `category`, `priority` et `source` peuvent contenir plusieurs valeurs separees par virgule. `origin` vaut `internal` ou `external`.

La reponse expose `kpis`, `previous_kpis`, `trends`, `hierarchy`, `breakdowns`, `kpi_catalog` et `tables` avec trois lectures: `executive`, `analytical`, `audit`.

`GET /reports/decision/export` accepte les memes filtres metier et `group_by=global|executive|direction|service|status|category|priority|assignee|period|audit`. L'export reprend toutes les colonnes du perimetre filtre, avec `periode`, `genere_le`, `genere_par` et `filtres`.

## Effets metier transversaux

Les actions tickets modifient souvent `request`, ajoutent une entree `workflow_detail`, creent une notification et publient un event SSE.

Les notifications metier sont personnelles: une ligne `notification` correspond a un `recipient_id` unique. Les endpoints `/notifications/*` retournent les notifications du destinataire authentifie, sauf consultation admin explicitement autorisee. Les publications SSE `notification.created` doivent cibler uniquement `target.user_ids=[recipient_id]` afin de respecter le prochain acteur du workflow.

L'administration organisationnelle expose la hierarchie `Direction -> Departement -> Unite/Service` via `Unity + Organigram`, sans table dediee aux departements. Les endpoints `/directions/*`, `/departments/*` et `/units/*` retournent les elements actifs et inactifs non soft-deleted. Les actions utilisateur de suppression sont des desactivations visibles et reversibles via `/deactivate` et `/activate`; les anciens `DELETE` restent compatibles et ne font pas de suppression physique. Le seed de demarrage `seed_references.py` ne restaure pas automatiquement les directions/services soft-deleted.

L'administration des utilisateurs accepte `direction_id`, `department_id` et `unit_id` comme alias de formulaire, mais persiste uniquement `account.unity_id`. Les mutations admin `/users/`, `/users/{id}` et `/users/{id}/role` valident que l'entite cible est active et que son niveau correspond au role: direction pour `director`, departement ou unite pour `chief`, unite pour `user`/`agent`/`admin`. L'ancien role technique `dg` est normalise vers `director` pour compatibilite.
