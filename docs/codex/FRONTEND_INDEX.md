# Frontend Index

## Entrees frontend

| Fichier | Role |
| --- | --- |
| `frontend/src/router.tsx` | Creation du routeur TanStack |
| `frontend/src/routes/__root.tsx` | Racine, provider QueryClient, erreurs |
| `frontend/src/routes/app.tsx` | Layout applicatif protege |
| `frontend/src/components/app-layout.tsx` | Sidebar, groupes de navigation par role, retour contexte |
| `frontend/src/lib/session.ts` | Session utilisateur, roles, tokens |
| `frontend/src/lib/capabilities.ts` | Capacites et actions affichables par role |
| `frontend/src/lib/ticket-navigation.ts` | Mapping liste ticket -> detail ticket metier |

## Routes principales

| Route | Page | Module | Roles | Service frontend | Endpoint | Fichiers |
| --- | --- | --- | --- | --- | --- | --- |
| `/` | accueil public | public | public | homepage/knowledge | public | `index.tsx` |
| `/login` | connexion | auth | public | `auth.ts` | `/auth/login` | `login.tsx` |
| `/admin-login` | connexion admin | auth | admin | `auth.ts` | `/auth/login` | `admin-login.tsx` |
| `/forgot-password` | reset | auth | public | `auth.ts` | `/auth/*reset*` | `forgot-password.tsx` |
| `/register` | inscription | auth | public | `auth.ts` | `/auth/register` | `register.tsx` |
| `/track` | suivi public | request | public | `requests.ts` | `/requests/track` | `track.tsx` |
| `/create-request` | creation publique | request | public/user | `requests.ts` | `/requests` | `create-request.tsx` |
| `/app` | accueil personnel/pro | personal | user+ | stats/requests | plusieurs | `app.index.tsx` |
| `/app/requests` | mes demandes | personal | user+ | `requests.ts` | `/requests` | `app.requests.index.tsx` |
| `/app/requests/$id` | detail personnel | personal | user+ | `requests.ts`, `workflow.ts` | `/requests/{id}` | `app.requests.$id.tsx` |
| `/app/requests/history` | historique personnel | personal | user+ | `requests.ts` | `/requests` | `app.requests.history.tsx` |
| `/app/my-tickets` | tickets agent | agent | chief-service | `requests.ts` | `/requests/by-assignee/*` | `app.my-tickets.tsx` |
| `/app/my-tickets/tickets/$id` | detail agent | agent | chief-service | `requests.ts` | `/requests/{id}` | `app.my-tickets_.tickets.$id.tsx` |
| `/app/queue` | file/qualification | queue | chief-service, chief-service, chief-departement, director | `requests.ts` | `/requests/queue`, `/requests/triage` | `app.queue.tsx` |
| `/app/queue/tickets/$id` | detail queue | queue | chief-service, chief-service, chief-departement, director | `requests.ts` | `/requests/{id}` | `app.queue_.tickets.$id.tsx` |
| `/app/chief-inbox` | boite chef de service | chief | chief-service | `requests.ts`, `accounts.ts` | `/requests/queue`, `/users` | `app.chief-inbox.tsx` |
| `/app/chief-inbox/tickets/$id` | detail chef de service | chief | chief-service | `requests.ts` | `/requests/{id}` | `app.chief-inbox_.tickets.$id.tsx` |
| `/app/department-inbox` | boite chef de departement | chief | chief-departement | `requests.ts`, `accounts.ts` | `/requests/queue`, `/users` | `app.department-inbox.tsx` (reutilise le composant `ChiefInbox` de `app.chief-inbox.tsx`) |
| `/app/department-inbox/tickets/$id` | detail chef de departement | chief | chief-departement | `requests.ts` | `/requests/{id}` | `app.department-inbox_.tickets.$id.tsx` |
| `/app/supervision` | supervision | supervision | chief-service, chief-departement, director | `requests.ts`, `reports.ts` | `/requests`, `/stats` | `app.supervision.tsx` |
| `/app/supervision/tickets/$id` | detail supervision | supervision | chief-service, chief-departement, director | `requests.ts` | `/requests/{id}` | `app.supervision_.tickets.$id.tsx` |
| `/app/direction` | vue direction | direction | director | `requests.ts`, `reports.ts` | `/requests/by-direction/*` | `app.direction.tsx` |
| `/app/direction/tickets/$id` | detail direction | direction | director | `requests.ts` | `/requests/{id}` | `app.direction_.tickets.$id.tsx` |
| `/app/dg` | vue globale pilotage admin | admin | admin | `reports.ts`, `escalations.ts` | `/stats`, `/reports`, `/escalations` | `app.dg.tsx` |
| `/app/dg/tickets/$id` | detail vue globale admin | admin | admin | `requests.ts` | `/requests/{id}` | `app.dg_.tickets.$id.tsx` |
| `/app/sla-center` | centre SLA | sla | chief-service, chief-departement, director, admin | `requests.ts`, `escalations.ts` | `/requests/sla-breached`, `/escalations` | `app.sla-center.tsx` |
| `/app/reports` | rapports | reports | chief-service, chief-departement, director, admin | `reports.ts` | `/reports/*` | `app.reports.tsx` |
| `/app/knowledge` | base connaissance | knowledge | user+ | `knowledge.ts` | `/knowledge/*` | `app.knowledge.tsx` |
| `/app/notifications` | notifications | notif | user+ | `notifications.ts` | `/notifications/*` | `app.notifications.tsx` |
| `/app/profile` | profil | personal | user+ | `accounts.ts` | `/users/me` | `app.profile.tsx` |
| `/app/admin/*` | administration | admin | admin | `admin-config.ts`, autres | `/admin/*`, `/users/*` | `app.admin.*.tsx` |

## Affichage par role

La source principale de navigation par role est `app-layout.tsx`. Les trois premiers onglets (`Accueil`, `Mes demandes`, `Historique`) sont personnels pour tous les roles. Les autres onglets sont professionnels et ne doivent pas ramener vers `/app/requests/$id` sauf ouverture depuis `Mes demandes`.
