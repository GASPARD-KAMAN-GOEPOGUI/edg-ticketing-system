# Dependency Index

Ce fichier liste les dependances fonctionnelles utiles pour localiser les problemes. Il ne liste pas les imports techniques generiques.

## Demande personnelle

```text
frontend/src/routes/app.requests.index.tsx
-> frontend/src/lib/api/requests.ts
-> GET /api/v1/requests
-> backend/api/routes/RouteRequest.py
-> backend/api/services/ServiceRequest.py
-> RepositoryRequest.py
-> ModelRequest.py
-> request
```

## Detail personnel

```text
frontend/src/routes/app.requests.$id.tsx
-> workflow-timeline.tsx
-> requests.ts + workflow.ts
-> GET /api/v1/requests/{id}
-> GET /api/v1/requests/{id}/timeline
-> RouteRequest.py / RouteWorkflow.py
-> ServiceRequest.py / ServiceWorkflow.py
-> Request / WorkflowDetail
-> request / workflow_detail
```

## Detail metier contexte

```text
frontend/src/lib/ticket-navigation.ts
-> app.my-tickets_.tickets.$id.tsx / app.queue_.tickets.$id.tsx / app.supervision_.tickets.$id.tsx / app.direction_.tickets.$id.tsx / app.dg_.tickets.$id.tsx / app.admin.tickets.$id.tsx
-> app.requests.$id.tsx ou composant detail partage selon implementation
-> RouteRequest.py
-> ServiceRequest.py
-> ticket_actions.py
```

## Supervision

```text
frontend/src/routes/app.supervision.tsx
-> frontend/src/lib/api/requests.ts
-> GET /api/v1/requests avec filtres scope
-> backend/api/routes/RouteRequest.py
-> backend/api/services/ServiceRequest.py
-> Account + Unity + Request
-> account / unity / request
```

## Vue direction

```text
frontend/src/routes/app.direction.tsx
-> frontend/src/lib/api/requests.ts + reports.ts
-> GET /api/v1/requests/by-direction/{direction_id}
-> POST /api/v1/requests/{id}/transfer-direction
-> backend/api/routes/RouteRequest.py
-> backend/api/services/ServiceRequest.py
-> ticket_actions.py
-> Request + Unity + WorkflowDetail
```

## Rapports direction/service

```text
frontend/src/routes/app.reports.tsx
-> frontend/src/lib/api/reports.ts
-> GET /api/v1/reports/by-unity
-> GET /api/v1/reports/decision
-> GET /api/v1/reports/decision/export
-> backend/api/routes/RouteReports.py
-> backend/api/services/ServiceReport.py
-> Request + Account + Unity + RequestStatus + Workflow + WorkflowDetail + Attachment + Appreciation
-> request / account / unity / request_status / workflow / workflow_detail / attachment / appreciation
```

## Notifications

```text
frontend/src/components/notification-panel.tsx
-> frontend/src/lib/api/notifications.ts
-> GET /api/v1/notifications
-> backend/api/routes/RouteNotification.py
-> backend/api/services/ServiceNotification.py
-> backend/api/services/NotificationEmitter.py pour les notifications creees par les actions ticket
-> backend/api/core/mailer.py pour l'envoi SMTP optionnel
-> backend/templates/*.html pour le rendu des emails
-> ModelNotification.py
-> notification
```

## Temps reel

```text
frontend/src/providers/realtime-provider.tsx
-> frontend/src/lib/realtime/sse-client.ts
-> GET /api/v1/events
-> backend/api/routes/RouteSSE.py
-> backend/api/core/event_bus.py
-> events `notification.created` cibles par `target.user_ids`
```

## Admin configuration

```text
frontend/src/routes/app.admin.routing.tsx
-> frontend/src/lib/api/admin-config.ts
-> /api/v1/admin/routing*
-> backend/api/routes/RouteAdminConfig.py
-> ServiceRoutingRule.py / repositories refs
-> routing_rule
```

## Admin utilisateurs et roles

```text
frontend/src/routes/app.admin.users.tsx
-> frontend/src/lib/api/accounts.ts
-> frontend/src/lib/api/directions-units.ts pour directions/departements/unites actifs
-> GET/POST/PUT/DELETE /api/v1/users*
-> GET /api/v1/directions*
-> GET /api/v1/departments*
-> GET /api/v1/units*
-> backend/api/routes/RouteUsers.py
-> backend/api/services/ServiceAccount.py
-> Account + Unity + Organigram
-> account / unity / organigram
```

## Admin organisation

```text
frontend/src/routes/app.admin.directions.tsx / frontend/src/routes/app.admin.directions.$id.tsx / frontend/src/routes/app.admin.departments.tsx / frontend/src/routes/app.admin.units.tsx / frontend/src/routes/app.admin.org.tsx
-> frontend/src/lib/api/directions-units.ts
-> frontend/src/lib/api/accounts.ts pour le personnel de l'arbre direction
-> GET/POST/PUT/DELETE /api/v1/directions*
-> GET/POST/PUT/DELETE /api/v1/departments*
-> GET/POST/PUT/DELETE /api/v1/units*
-> POST /api/v1/{directions|departments|units}/{id}/activate|deactivate
-> backend/api/routes/RouteDirectionsUnits.py
-> backend/api/seed_references.py au demarrage pour les donnees builtin Unity/Organigram
-> Unity + Organigram
-> unity / organigram
```

## SLA/escalades

```text
frontend/src/routes/app.sla-center.tsx
-> frontend/src/lib/api/escalations.ts + requests.ts
-> GET /api/v1/escalations
-> backend/api/routes/RouteEscalation.py
-> backend/api/services/ServiceEscalade.py
-> workflow_detail infos + request SLA fields
```
