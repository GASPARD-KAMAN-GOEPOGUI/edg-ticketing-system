# Route Index

## Principe central

Un ticket doit rester dans le contexte depuis lequel il a ete ouvert.

| Contexte | Liste | Detail attendu | Sens metier |
| --- | --- | --- | --- |
| Personnel | `/app/requests` | `/app/requests/$id` | Mes propres demandes |
| Agent | `/app/my-tickets` | `/app/my-tickets/tickets/$id` | Tickets assignes a moi |
| File/qualification | `/app/queue` | `/app/queue/tickets/$id` | Tickets libres a prendre et demandes a qualifier |
| Chef de service | `/app/chief-inbox` | `/app/chief-inbox/tickets/$id` | Tickets du service du chef-service |
| Chef de departement | `/app/department-inbox` | `/app/department-inbox/tickets/$id` | Tickets de tous les services du departement du chef-departement |
| Supervision | `/app/supervision` | `/app/supervision/tickets/$id` | Tickets supervises |
| Direction | `/app/direction` | `/app/direction/tickets/$id` | Tickets de la direction |
| Vue globale admin | `/app/dg` | `/app/dg/tickets/$id` | Pilotage global admin |
| SLA | `/app/sla-center` | `/app/sla-center/tickets/$id` | Tickets SLA/escalades |
| Admin | `/app/admin/users` ou admin | `/app/admin/tickets/$id` | Administration ticket |

## Routes frontend par role

| Route frontend | Page | Contexte | Module | Roles | Destination detail | Fichiers |
| --- | --- | --- | --- | --- | --- | --- |
| `/app` | Accueil | personnel + resume pro | MOD-PERSONAL | user+ | selon cartes | `app.index.tsx` |
| `/app/requests` | Mes demandes | personnel | MOD-PERSONAL | user+ | `/app/requests/$id` | `app.requests.index.tsx` |
| `/app/requests/history` | Historique | personnel | MOD-PERSONAL | user+ | `/app/requests/$id` | `app.requests.history.tsx` |
| `/app/my-tickets` | Ma boite de traitement | Mon travail | MOD-AGENT/MOD-CHIEF/MOD-DIRECTION | chief-service, chief-service, chief-departement, director, admin | `/app/my-tickets/tickets/$id` | `app.my-tickets.tsx` (2026-08-05 : inclut les tickets `reopened` dans la liste principale ; 2026-08-06 : affiche les tickets dont l'utilisateur courant est `assignee_id` et, pour chief-service/chief-departement, les tickets `escalated` du perimetre operationnel depuis le retrait de `Repartition > Escalades`) |
| `/app/transmitted` | Tickets transmis | Mon travail | MOD-AGENT/MOD-CHIEF/MOD-DIRECTION | chief-service, chief-service, chief-departement, director, admin | detail dedie `/app/transmitted/tickets/$id`, retour vers `/app/transmitted` | `app.transmitted.tsx`, `app.transmitted_.tickets.$id.tsx` — lecture seule, affichage grille par defaut avec toggle liste/grille, recherche et pagination, scope = acteur courant via `GET /requests/transmitted` |
| `/app/queue` | File d'attente | Mon travail | MOD-AGENT/MOD-CHIEF/MOD-DIRECTION | chief-service, chief-service, chief-departement, director, admin (`dg` exclu) | `/app/queue/tickets/$id` | `app.queue.tsx` (2026-08-05 : tous les roles operationnels peuvent prendre un ticket et assigner vers un role operationnel autorise ; destinataire admin reserve a admin ; `qualify`/`assign` alignes cote backend) |
| `/app/chief-inbox` | Centre de repartition | Route technique non exposee au menu chief-service depuis le 2026-08-06 | MOD-CHIEF | chief-service | `/app/chief-inbox/tickets/$id` | `app.chief-inbox.tsx` (support `?tab=reopen` deep-link ; onglet `Escalades` retire le 2026-08-06 au profit de `/app/my-tickets`) |
| `/app/department-inbox` | Centre de pilotage | Pilotage (recategorise depuis "Traitement" le 2026-08-05) | MOD-CHIEF | chief-departement | `/app/department-inbox/tickets/$id` (via drill-down depuis le dashboard) | `app.department-inbox.tsx` (dashboard `AggregatedServiceDashboard` + drill-down composant partage `app.chief-inbox.tsx`, deep-link `?tab=reopen` propage via le composant partage ; escalades traitees dans `/app/my-tickets`) |
| `/app/supervision` | Supervision | supervision | MOD-SUPERVISION | chief-service, chief-departement, director | `/app/supervision/tickets/$id` | `app.supervision.tsx` |
| `/app/direction` | Vue direction | pilotage | MOD-DIRECTION | director | `/app/direction/tickets/$id` | `app.direction.tsx` |
| `/app/strategic-dashboard` | Tableau de bord strategique | pilotage consultatif (additif) | MOD-DIRECTION | director | aucun (lecture seule, pas de drill-down) | `app.strategic-dashboard.tsx` (reutilise `components/aggregated-service-dashboard.tsx`) |
| `/app/dg` | Vue globale | pilotage global admin | MOD-ADMIN | admin | `/app/dg/tickets/$id` | `app.dg.tsx` |
| `/app/sla-center` | Centre SLA | pilotage SLA | MOD-SLA | chief-service, chief-departement, director, admin | `/app/sla-center/tickets/$id` | `app.sla-center.tsx` |
| `/app/reports` | Rapports | pilotage | MOD-REPORT | chief-service, chief-departement, director, admin | detail non central | `app.reports.tsx` |
| `/app/admin/*` | Admin | administration | MOD-ADMIN | admin | `/app/admin/tickets/$id` pour tickets | `app.admin.*.tsx` |

## Routes organisation admin

| Route frontend | Page | Sens metier | Backend principal |
| --- | --- | --- | --- |
| `/app/admin/org` | Organigramme | Vue synthétique Direction -> Departement -> Service/Unite | `/directions`, `/departments`, `/units` |
| `/app/admin/directions` | Directions | CRUD logique directions, parent direction optionnel, activation/desactivation | `/directions/*` |
| `/app/admin/directions/$id` | Detail direction | Organigramme reel de la direction avec personnel disponible; rendu via l'Outlet de la route parent `/app/admin/directions` | `/directions/{id}`, `/departments/by-direction/{id}`, `/units/by-direction/{id}`, `/users` |
| `/app/admin/departments` | Departements | CRUD logique departements rattaches obligatoirement a une direction | `/departments/*` |
| `/app/admin/units` | Services & Unites | CRUD logique services/unites rattaches obligatoirement a un departement pour les nouvelles creations | `/units/*` |

## Fichiers de navigation

- `frontend/src/lib/ticket-navigation.ts`: mapping des routes de liste vers details.
- `frontend/src/components/app-layout.tsx`: bouton retour et navigation visible.
- Les fichiers `app.*_.tickets.$id.tsx` doivent etre verifies via `routeTree.gen.ts` si un detail ne s'ouvre pas dans l'URL attendue.
