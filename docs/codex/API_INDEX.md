# API Index

Base API frontend: `/api/v1` en production, `http://localhost:8000/api/v1` en dev.

## Endpoints principaux

| Methode | Endpoint | Router | Service | Modeles | Tables | Permissions | Frontend utilisateur |
| --- | --- | --- | --- | --- | --- | --- | --- |
| POST | `/auth/login` | `RouteAuth.py` | `ServiceAccount.py` | Account | `account` | public | login/admin-login |
| POST | `/auth/refresh` | `RouteAuth.py` | auth core | Account | `account` | refresh token | API client |
| GET | `/users/me` | `RouteUsers.py` | `ServiceAccount.py` | Account | `account` | authenticated | profil/layout |
| PATCH | `/users/me` | `RouteUsers.py` | `ServiceAccount.py` | Account | `account` | authenticated | profil |
| GET/POST/PATCH/DELETE | `/users/*` | `RouteUsers.py` | `ServiceAccount.py` | Account/Unity/Organigram | `account`, `unity`, `organigram` | admin pour mutations; staff (agent-support/chief-service/chief-departement/director/admin) pour lecture annuaire | admin utilisateurs & roles; `GET /users?role=agent-support&direction_id=X` (elargi via organigramme) pour le selecteur d'assignation chief-departement, `unit_id=X` (exact) pour chief-service |
| GET/POST/PATCH/DELETE | `/directions/*` | `RouteDirectionsUnits.py` | Unity/Organigram | Unity, Organigram | `unity`, `organigram` | authenticated; admin pour ecriture | admin directions + detail organigramme |
| GET/POST/PATCH/DELETE | `/departments/*` | `RouteDirectionsUnits.py` | Unity/Organigram | Unity, Organigram | `unity`, `organigram` | authenticated; admin pour ecriture | admin departements |
| GET/POST/PATCH/DELETE | `/units/*` | `RouteDirectionsUnits.py` | Unity/Organigram | Unity, Organigram | `unity`, `organigram` | authenticated; admin pour ecriture | admin services/unites |
| GET | `/requests` | `RouteRequest.py` | `ServiceRequest.py` | Request | `request` | authenticated, scoping force cote serveur (agent-support/chief-service bornes a leur unite ; chief-departement/director elargis a leur departement/direction via organigramme) ; admin peut filtrer `direction_id`; `exclude_status` optionnel et peut exclure plusieurs statuts separes par virgule | listes demandes/tickets, vue globale |
| POST | `/requests` | `RouteRequest.py` | `ServiceRequest.py` | Request | `request`, `workflow` | `CREATE_REQUEST` | nouvelle demande |
| GET | `/requests/{id}` | `RouteRequest.py` | `ServiceRequest.py` | Request | `request` | scoping; acces personnel autorise si l'acteur est `requester_id`; `include_deleted=true` admin uniquement | details tickets |
| PATCH | `/requests/{id}` | `RouteRequest.py` | `ServiceRequest.py` | Request | `request` | scoping/admin selon champs | modification |
| PATCH | `/requests/{id}/requester-edit` | `RouteRequest.py` | `ServiceRequest.py` | Request | `request` | demandeur, statut `new`, champs autorises `title`/`description` uniquement (`extra=forbid`) | detail personnel |
| GET | `/requests/queue` | `RouteRequest.py` | `ServiceRequest.py` | Request | `request` | agent-support/chief-service/chief-departement/director/admin | file d'attente; `direction_id` force cote serveur et elargi via organigramme pour chief-departement/director; `unassigned_only=true` pour la vue `A prendre` |
| GET | `/requests/triage` | `RouteRequest.py` | `ServiceRequest.py` | Request | `request` | agent-support/chief-service/chief-departement/admin | a qualifier; retourne uniquement `new`, `qualifying`, `qualified`, `reopened` |
| POST | `/requests/{id}/qualify` | `RouteRequest.py` | `ServiceRequest.py` | Request | `request`, `workflow_detail` | agent-support/chief-service/chief-departement/admin | qualification; `direction_id` optionnel si `unit_id` est fourni |
| POST | `/requests/{id}/assign` | `RouteRequest.py` | `ServiceRequest.py` | Request | `request`, `workflow_detail` | agent-support/chief-service/chief-departement/admin + regles | assignation; chief-service borne a son service, chief-departement a tous les services de son departement |
| POST | `/requests/{id}/resolve` | `RouteRequest.py` | `ServiceRequest.py` | Request | `request`, `workflow_detail` | BR-TRANSMIT-001 : reserve a l'intervenant actuel (`assignee_id == actor.id`) parmi agent-support/chief-service/chief-departement/director/admin | "Terminer le traitement" ; body `{summary, solution, work_done, recommendations?, attachment_ids?}` (3 premiers obligatoires) |
| POST | `/requests/{id}/transmit` | `RouteRequest.py` | `ServiceRequest.py` | Request | `request`, `workflow_detail` | BR-TRANSMIT-001 : reserve a l'intervenant actuel parmi agent-support/chief-service/chief-departement/director/admin | "Transmettre le traitement" ; body `{to_user_id, work_done, reason, instruction?, attachment_ids?}` (cible libre dans toute l'organisation, statut preserve) |
| POST | `/requests/{id}/close` | `RouteRequest.py` | `ServiceRequest.py` | Request | `request`, `workflow_detail` | demandeur/user+ selon regle | cloture |
| POST | `/requests/{id}/request-reopen` | `RouteRequest.py` | `ServiceRequest.py` | Request | `workflow_detail` | demandeur | demande reouverture |
| POST | `/requests/{id}/reopen` | `RouteRequest.py` | `ServiceRequest.py` | Request | `request`, `workflow_detail`, `notification` | chief-service/chief-departement/director/admin | approuver reouverture — libere l'assignee (`assignee_id=null`) et retourne en File d'attente (`in_triage=true`), BR-REOPEN-QUEUE-001 |
| POST | `/requests/{id}/reject-reopen` | `RouteRequest.py` | `ServiceRequest.py` | Request | `workflow_detail` | chief-service/chief-departement/director/admin | rejet reouverture |
| POST | `/requests/{id}/cancel` | `RouteRequest.py` | `ServiceRequest.py` | Request | `request`, `workflow_detail` | user/agent-support/chief-service/chief-departement/director/admin | annulation |
| POST | `/requests/{id}/reject` | `RouteRequest.py` | `ServiceRequest.py` | Request | `request`, `workflow_detail` | chief-service/chief-departement/admin | rejet |
| POST | `/requests/{id}/priority` | `RouteRequest.py` | `ServiceRequest.py` | Request | `request` | chief-service/chief-departement/director/admin | priorite |
| POST | `/requests/{id}/reassign` | `RouteRequest.py` | `ServiceRequest.py` | Request | `request`, `workflow_detail` | chief-service/chief-departement/director/admin | changement service (meme direction) |
| POST | `/requests/{id}/transfer-direction` | `RouteRequest.py` | `ServiceRequest.py` | Request | `request`, `workflow_detail` | director/admin | transfert direction |
| POST | `/requests/{id}/escalate` | `RouteRequest.py` | `ServiceRequest.py` | WorkflowDetail | `workflow_detail` | agent-support/chief-service/chief-departement/director/admin | escalade |
| GET/POST | `/requests/{id}/comments` | `RouteRequest.py` | `ServiceWorkflow.py` | WorkflowDetail | `workflow_detail` | scoping ticket; lecture publique seule si l'acteur est le demandeur proprietaire | commentaires; `POST` accepte `attachment_id` optionnel (piece jointe deja uploadee sur la meme demande, rattachee au commentaire) |
| GET | `/requests/{id}/timeline` | `RouteRequest.py` | `ServiceWorkflow.py` | WorkflowDetail | `workflow_detail` | scoping ticket | timeline |
| GET/POST | `/requests/{id}/attachments` | `RouteRequest.py` | `AttachmentService.py` | Attachment | `attachment` | scoping ticket/personnel | liste et ajout pieces jointes ; `POST` accepte `skip_timeline_event=true` (query) pour ne pas creer d'evenement `attachment_added` separe quand la piece jointe est immediatement rattachee a un commentaire |
| GET | `/requests/download/{path}` | `RouteRequest.py` | storage | fichier local | `uploads` | scoping ticket/personnel par `request_id` extrait du chemin | ouverture/telechargement piece jointe |
| GET | `/workflows/*` | `RouteWorkflow.py` | `ServiceWorkflow.py` | Workflow | `workflow` | agent+ selon endpoint | workflow |
| GET | `/reports/by-agent` | `RouteReports.py` | `ServiceReport.py` | Request/Account | `request`, `account` | chief-service/chief-departement/director/admin | rapports |
| GET | `/reports/by-unity` | `RouteReports.py` | `ServiceReport.py` | Request/Unity | `request`, `unity` | chief-service/chief-departement/director/admin; `direction_id` pour vue direction/admin | performance service, rapport direction |
| GET | `/reports/decision` | `RouteReports.py` | `ServiceReport.py` | Request/Workflow/Unity/Account | `request`, `workflow`, `workflow_detail`, `unity`, `account` | chief-service/chief-departement/director/admin; scoping role + filtres | moteur decisionnel |
| GET | `/reports/decision/export` | `RouteReports.py` | `ServiceReport.py` | Request/Workflow/Unity/Account | `request`, `workflow`, `workflow_detail`, `unity`, `account` | chief-service/chief-departement/director/admin; scoping role + filtres | export decisionnel |
| GET | `/reports/sla/reopen-stats` | `RouteReports.py` | `ServiceReport.py` | Request/Workflow/WorkflowDetail | `request`, `workflow`, `workflow_detail` | chief-service/chief-departement/director/admin | BR-SLA-REOPEN-001 — tickets reouverts, duree moy. 1er cycle vs post-reouverture, conformite SLA par cycle |
| GET | `/reports/interventions` | `RouteReports.py` | `ServiceReport.py` | Request/Workflow/WorkflowDetail | `request`, `workflow`, `workflow_detail` | chief-service/chief-departement/director/admin | BR-TRACE-001 — nombre d'interventions, intervenants distincts, duree moy./cumulee, transmissions/resolutions/reouvertures, temps par agent/service/departement |
| GET | `/stats/*` | `RouteStats.py` | `ServiceStats.py` | Request | `request` | role selon endpoint | dashboards |
| GET/PATCH/POST | `/notifications/*` | `RouteNotification.py` | `ServiceNotification.py` | Notification | `notification` | authenticated | panel/page notifications |
| GET/POST/PATCH | `/admin/*` | `RouteAdminConfig.py` | services config | refs/config | refs, sla, routing | admin | admin |

## Payloads et erreurs

- Payloads ticket: schemas dans `backend/api/schemas/SchemaRequest.py`.
- Payloads workflow/commentaires: `SchemaWorkflowDetail.py`.
- Reponses: enveloppes `RequestResponse`, `RequestListItemResponse`, `WorkflowDetailResponse`, `PaginatedResponse`. Depuis 2026-07-29, `requester_unit_id` (unite d'appartenance du demandeur, via `Account.unity_id`) est expose en plus de `unity_id`/`direction_id` (unite/direction en charge du traitement) — cote frontend, la direction du demandeur se deduit de `requester_unit_id` via la liste `units` (`direction_id`), il n'existe pas de champ `requester_direction_id` cote backend.
- Erreurs metier: `ForbiddenException`, `BusinessException`, `ValidationException` dans `backend/api/core/exceptions.py`; codes dans `error_codes.py`.
- Validations action/status/scope: `backend/api/core/ticket_actions.py`.
- BR-TRANSMIT-001 : `POST /requests/{id}/transmit` et `POST /requests/{id}/resolve` renvoient 409 `TICKET_STATE_CONFLICT` (`ConflictException`) si l'affectation du ticket a change entre la lecture et l'ecriture (transmission concurrente) — le frontend doit inviter a actualiser la page plutot que reessayer silencieusement.

## Rapports decisionnels

`GET /reports/decision` accepte les filtres `start`, `end`, `direction_id`, `unity_id`, `assignee_id`, `status`, `category`, `priority`, `source`, `origin`, `search`, `group_by`, `inactive_days`, `page`, `limit`, `sort_by`, `sort_dir`, `include_tickets`, `include_audit_rows`.

`status`, `category`, `priority` et `source` peuvent contenir plusieurs valeurs separees par virgule. `origin` vaut `internal` ou `external`.

La reponse expose `kpis`, `previous_kpis`, `trends`, `hierarchy`, `breakdowns`, `kpi_catalog` et `tables` avec trois lectures: `executive`, `analytical`, `audit`.

`GET /reports/decision/export` accepte les memes filtres metier et `group_by=global|executive|direction|service|status|category|priority|assignee|period|audit`. L'export reprend toutes les colonnes du perimetre filtre, avec `periode`, `genere_le`, `genere_par` et `filtres`.

## Effets metier transversaux

Les actions tickets modifient souvent `request`, ajoutent une entree `workflow_detail`, creent une notification et publient un event SSE.

Les notifications metier sont personnelles: une ligne `notification` correspond a un `recipient_id` unique. Les endpoints `/notifications/*` retournent les notifications du destinataire authentifie, sauf consultation admin explicitement autorisee. Les publications SSE `notification.created` doivent cibler uniquement `target.user_ids=[recipient_id]` afin de respecter le prochain acteur du workflow.

L'administration organisationnelle expose la hierarchie `Direction -> Departement -> Unite/Service` via `Unity + Organigram`, sans table dediee aux departements. Les endpoints `/directions/*`, `/departments/*` et `/units/*` retournent les elements actifs et inactifs non soft-deleted. Les actions utilisateur de suppression sont des desactivations visibles et reversibles via `/deactivate` et `/activate`; les anciens `DELETE` restent compatibles et ne font pas de suppression physique. Le seed de demarrage `seed_references.py` ne restaure pas automatiquement les directions/services soft-deleted.

L'administration des utilisateurs accepte `direction_id`, `department_id` et `unit_id` comme alias de formulaire, mais persiste uniquement `account.unity_id`. Les mutations admin `/users/`, `/users/{id}` et `/users/{id}/role` valident que l'entite cible est active et que son niveau correspond au role: direction pour `director`, departement pour `chief-departement`, unite/service pour `chief-service`, unite pour `user`/`agent-support`/`admin`. Les anciens roles techniques `dg`, `agent`, `chief` sont normalises respectivement vers `director`, `agent-support`, `chief-service` pour compatibilite (voir `LEGACY_ROLE_ALIASES` dans `rbac.py`).
