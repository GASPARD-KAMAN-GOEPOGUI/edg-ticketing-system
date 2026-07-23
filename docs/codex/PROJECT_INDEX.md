# Project Index

## Projet

Nom: EDG Connect / EDG-SUP.

Finalite: application de gestion des demandes/tickets EDG avec creation de demandes, qualification, orientation, traitement, supervision, escalade, reporting, administration, notifications et base de connaissances.

## Technologies

| Couche | Technologies |
| --- | --- |
| Frontend | React 19, TanStack Router/Start, TanStack Query, Vite, TypeScript, Tailwind CSS, Radix UI, lucide-react, Recharts |
| Backend | FastAPI, SQLAlchemy async, Pydantic v1, Uvicorn/Gunicorn |
| Donnees | Base SQL relationnelle via SQLAlchemy, MySQL/PyMySQL/AioMySQL probable |
| Temps reel | SSE via `backend/api/routes/RouteSSE.py` et `frontend/src/lib/realtime/sse-client.ts` |
| Auth | JWT, refresh token, blacklist Redis optionnelle, biometric/security incidents |
| Exports | CSV/Excel/PDF via `ServiceExport.py`, `xlsx` cote frontend |

## Architecture generale

```text
frontend/src/routes        Pages et routes TanStack
frontend/src/components    Layouts, formulaires, UI et composants metier
frontend/src/lib/api       Clients API frontend
frontend/src/lib           Session, permissions, navigation ticket, realtime
backend/api/main.py        Entree FastAPI et montage des routers
backend/api/routes         Routers HTTP
backend/api/services       Logique metier
backend/api/repositories   Acces donnees
backend/api/models         Modeles SQLAlchemy
backend/api/schemas        Schemas Pydantic
backend/api/core           RBAC, actions ticket, securite, exceptions, mailer, scheduler
backend/tests/api          Tests API cibles
```

## Fichiers d'entree

| Zone | Fichier |
| --- | --- |
| Frontend app | `frontend/src/router.tsx`, `frontend/src/start.ts`, `frontend/src/routes/__root.tsx`, `frontend/src/routes/app.tsx` |
| Frontend routes generees | `frontend/src/routeTree.gen.ts` |
| Backend app | `backend/api/main.py` |
| Backend dependances | `backend/api/dependencies.py` |
| Backend seed refs | `backend/api/seed_references.py` |
| Docker | `docker-compose.yml`, `docker-compose.prod.yml` |

## Conventions

| Type | Convention |
| --- | --- |
| Routes frontend | fichiers `app.*.tsx` dans `frontend/src/routes` |
| Routes detail metier | un detail ticket doit rester dans son contexte: requests, my-tickets, queue, chief-inbox, supervision, direction, dg, admin |
| Routers backend | `RouteX.py` avec `APIRouter(prefix=...)` |
| Services backend | `ServiceX.py` |
| Repositories | `RepositoryX.py` |
| Modeles | `ModelX.py`, tables en snake_case |
| Schemas | `SchemaX.py` |
| Roles | `public`, `user`, `agent`, `chief`, `director`, `dg`, `admin` |

## Configurations essentielles

| Fichier | Role |
| --- | --- |
| `.gitignore` | Ignore env, caches, logs, `.codex/` |
| `frontend/package.json` | Scripts `dev`, `build`, `preview`, `lint` |
| `backend/requirements.txt` | Dependances FastAPI/SQLAlchemy/auth/SSE/export |
| `backend/start-dev.ps1`, `backend/start-dev.cmd` | Demarrage backend local |

## Dossiers exclus des recherches

`.git/`, `.codex/`, `frontend/node_modules/`, `frontend/dist/`, `frontend/.vite/`, `backend/venv/`, `venv/`, `__pycache__/`, logs, caches, builds, profils navigateur.

## Grandes dependances entre couches

```text
Route frontend
-> service frontend dans frontend/src/lib/api
-> endpoint /api/v1
-> backend/api/routes/Route*.py
-> backend/api/services/Service*.py
-> backend/api/repositories/Repository*.py
-> backend/api/models/Model*.py
-> table SQL
```
