# Module Index

## Modules metier principaux

| ID | Nom | Objectif | Roles | Pages frontend | Backend principal | Tables |
| --- | --- | --- | --- | --- | --- | --- |
| MOD-AUTH | Authentification | Connexion, refresh, reset, session, biometric/security | tous | `/login`, `/admin-login`, `/forgot-password`, `/register` | `RouteAuth.py`, `ServiceAccount.py`, `ServiceBiometric.py`, `ServiceSecurityIncident.py` | `account`, `security_incident` |
| MOD-PERSONAL | Espace personnel | Accueil personnel, mes demandes, historique, profil, notifications | user+ | `/app`, `/app/requests`, `/app/requests/history`, `/app/profile`, `/app/notifications` | `RouteRequest.py`, `RouteUsers.py`, `RouteNotification.py` | `request`, `account`, `notification` |
| MOD-REQUEST | Demandes/Tickets | Creation, consultation, edition demandeur, suivi public | tous authentifies, public pour tracking | `/create-request`, `/track`, `/app/new`, `/app/requests/$id` | `RouteRequest.py`, `ServiceRequest.py` | `request`, `request_status`, `request_category`, `priority_definition` |
| MOD-AGENT | Traitement agent | Mes tickets, file, auto-assignation, resolution, escalade agent | agent | `/app/my-tickets`, `/app/queue` | `RouteRequest.py`, `ServiceRequest.py`, `ticket_actions.py` | `request`, `workflow`, `workflow_detail`, `task` |
| MOD-CHIEF | Chef de service | Boite de traitement, supervision equipe/service, assignation, priorite, reassignation service | chief | `/app/chief-inbox`, `/app/queue`, `/app/supervision` | `RouteRequest.py`, `RouteWorkflow.py`, `ServiceRequest.py` | `request`, `unity`, `account`, `workflow_detail` |
| MOD-SUPERVISION | Supervision | Centre de supervision des tickets dans le perimetre chef/directeur | chief, director | `/app/supervision`, `/app/supervision/tickets/$id` | `RouteRequest.py`, `RouteStats.py`, `ServiceRequest.py`, `ServiceStats.py` | `request`, `unity`, `workflow_detail` |
| MOD-DIRECTION | Vue direction | Pilotage direction, transfert inter/intra-direction, rapports direction | director | `/app/direction`, `/app/direction/tickets/$id`, `/app/reports` | `RouteRequest.py`, `RouteReports.py`, `RouteRoutingRule.py` | `request`, `unity`, `routing_rule` |
| MOD-GLOBAL | Vue globale admin | Pilotage global admin, SLA global | admin | `/app/dg`, `/app/dg/tickets/$id` | `RouteStats.py`, `RouteReports.py`, `RouteEscalation.py` | `request`, `workflow_detail`, `activity_log` |
| MOD-ADMIN | Administration | Utilisateurs, organisation, referentiels, routage, SLA, priorites, audit, communication | admin | `/app/admin/*` | `RouteAdminConfig.py`, `RouteUsers.py`, `RouteDirectionsUnits.py`, `RouteReferences.py` | toutes tables de config/ref |
| MOD-WORKFLOW | Workflow/Timeline | Circuit, commentaires, historique d'actions, acceptation et reouverture | agent+ selon action | composants detail ticket, `workflow-timeline.tsx` | `RouteWorkflow.py`, `RouteRequest.py`, `ServiceWorkflow.py` | `workflow`, `workflow_detail`, `task` |
| MOD-REPORT | Rapports | Journaliers, mensuels, agents, services/unites, decisionnel executive/analytique/audit, SLA, CSAT | chief, director, admin | `/app/reports`, `/api/v1/reports/decision` | `RouteReports.py`, `ServiceReport.py` | `request`, `account`, `unity`, `workflow_detail`, `attachment`, `appreciation` |
| MOD-NOTIF | Notifications | Panel, page notifications, events realtime cibles par destinataire workflow | tous authentifies | `NotificationPanel`, `/app/notifications` | `RouteNotification.py`, `RouteSSE.py`, `NotificationEmitter.py` | `notification` |
| MOD-KNOWLEDGE | Base de connaissances | Articles publics/internes/admin | public, user+, admin | `/knowledge`, `/app/knowledge`, `/app/admin/knowledge` | `RouteKnowledge.py`, `RouteKnowledgeArticle.py` | `knowledge_article`, `knowledge_category` |
| MOD-ORG | Organisation | Directions, departements, services/unites, organigramme | admin, lecture publique partielle | `/app/admin/directions`, `/app/admin/directions/$id`, `/app/admin/departments`, `/app/admin/units`, `/app/admin/org` | `RouteDirectionsUnits.py`, `RouteUnity.py`, `RouteOrganigram.py` | `unity`, `organigram` |
| MOD-SLA | SLA/Escalades | Politiques SLA, escalades auto/manuelles, centre SLA | chief, director, admin | `/app/sla-center`, `/app/admin/sla`, `/app/admin/priorities` | `RouteSlaPolicy.py`, `RouteEscalation.py`, `ServiceEscalade.py` | `sla_policy`, `priority_definition`, `workflow_detail` |
| MOD-AUDIT | Audit/Securite | Journaux activite et incidents securite | admin | `/app/admin/logs`, `/app/admin/security`, `/app/admin/audit` | `RouteActivityLog.py`, `RouteAdminConfig.py` | `activity_log`, `security_incident` |

## Dependances transversales

- `backend/api/core/rbac.py` definit les permissions cumulatives.
- `backend/api/core/ticket_actions.py` est la source backend des actions autorisees sur ticket.
- `frontend/src/lib/capabilities.ts` est la source frontend des capacites et actions affichables.
- `frontend/src/lib/ticket-navigation.ts` maintient la separation des routes detail selon le contexte.
- `frontend/src/components/app-layout.tsx` controle la navigation visible par role.
