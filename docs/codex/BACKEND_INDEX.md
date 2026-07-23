# Backend Index

## Entree et montage

Point d'entree: `backend/api/main.py`.

Prefix API: `/api/v1`.

Routers montes: health, auth, events, references, unity, organigram, public directions, directions, units, accounts, requests, attachments, sla policies, routing rules, workflows, tasks, notifications, activity logs, knowledge, announcements, appreciations, CSAT, communication, admin config, users, stats, reports, escalations.

## Chaines fonctionnelles principales

```text
RouteRequest.py
-> SchemaRequest.py
-> get_current_user / require_roles / ticket_actions.py
-> ServiceRequest.py
-> RepositoryRequest.py + repositories refs/workflow
-> ModelRequest.py + ModelWorkflowDetail.py
-> request + workflow_detail
-> effet metier ticket/demande
```

```text
RouteWorkflow.py
-> SchemaWorkflow.py / SchemaWorkflowDetail.py
-> require_roles
-> ServiceWorkflow.py
-> RepositoryWorkflow.py / RepositoryWorkflowDetail.py
-> ModelWorkflow.py / ModelWorkflowDetail.py
-> workflow + workflow_detail
-> circuit, commentaire, timeline
```

```text
RouteReports.py
-> ServiceReport.py
-> SQL sur request/account/unity/status/appreciation
-> rapports journaliers, mensuels, agent, unite, SLA, CSAT
```

```text
RouteAdminConfig.py
-> services refs/SLA/routing/security
-> modeles referentiels et config
-> tables refs, sla_policy, routing_rule, security_incident
```

## Routers importants

| Router | Prefix logique | Role | Services |
| --- | --- | --- | --- |
| `RouteAuth.py` | `/auth` | login, refresh, reset, register, biometric | `ServiceAccount.py`, `ServiceBiometric.py`, `ServiceSecurityIncident.py` |
| `RouteRequest.py` | `/requests` | demandes/tickets, actions, commentaires, timeline, pieces jointes | `ServiceRequest.py`, `ServiceWorkflow.py`, `ServiceAttachment.py` |
| `RouteWorkflow.py` | `/workflows`, `/requests`, `/workflow-details` | workflow et details | `ServiceWorkflow.py` |
| `RouteUsers.py` | `/users` | profil, staff, admin users | `ServiceAccount.py` |
| `RouteDirectionsUnits.py` | `/directions`, `/units`, `/public` | organisation | SQL direct + services selon endpoint |
| `RouteRoutingRule.py` | `/routing-rules`, `/director/routing-rules` probable | routage admin/directeur | `ServiceRoutingRule.py` |
| `RouteReports.py` | `/reports` | rapports | `ServiceReport.py`, `ServiceExport.py` |
| `RouteStats.py` | `/stats`, `/agent-stats` | KPIs | `ServiceStats.py` |
| `RouteEscalation.py` | `/escalations` | escalades | `ServiceEscalade.py` et workflow_detail infos |
| `RouteNotification.py` | `/notifications` | notifications | `ServiceNotification.py` |
| `RouteSSE.py` | `/events` | temps reel | event bus |
| `RouteKnowledge.py` | `/knowledge` | KB public/admin | `ServiceKnowledgeArticle.py` |
| `RouteReferences.py` | `/references` | statuts, categories, priorites refs | `ServiceReferences.py` |
| `RouteAdminConfig.py` | `/admin` | config SLA/routing/ref/security | services admin/ref |

## Authentification et permissions

- `dependencies.py`: `get_current_user`, `require_roles`, `require_permissions`, `require_admin`.
- `core/rbac.py`: matrice permission par role.
- `core/ticket_actions.py`: source backend pour actions et transitions tickets.

## Taches automatiques

- `core/scheduler.py` et `services/ServiceEscalade.py` gerent escalades SLA automatiques.
- `RouteSSE.py` + `core/event_bus.py` notifient le frontend.
