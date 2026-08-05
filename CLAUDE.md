
# EDG Connect — Contexte projet

Plateforme de gestion des requêtes/incidents pour **Électricité de Guinée (EDG)**. Portail de service basé sur les rôles gérant les requêtes internes (employés EDG, priorité métier) et, de façon secondaire, les requêtes externes (citoyens/clients).

**Langue de l'app:** Français (locale `fr`, `date-fns/locale/fr`)
**Statut:** Frontend React 19 + TanStack Start pleinement connecté au backend FastAPI (MySQL, Argon2, JWT, SSE)
**Documentation source de vérité:** `docs/cahier-des-charges.md` (spécifications fonctionnelles) et `docs/mise-a-jour-backend.md` (prompt backend). À mettre à jour à chaque évolution du frontend (nouveaux champs, statuts, routes, entités) — incrémenter la version et ajouter une entrée changelog.

---

## Domaine métier

**7 rôles utilisateur:**
- `public` – non authentifié (accès public limité : accueil, suivi de requête, aide)
- `user` – employé EDG (utilisateur principal du système)
- `agent` – personnel de support
- `chief` – chef d'équipe/superviseur
- `director` – chef de département
- `dg` – directeur général
- `admin` – administrateur système

**Statuts requête (machine d'état):**
`new → qualifying → qualified → assigned → in_progress → pending → resolved → closed`
Branches : `rejected`, `escalated`, `reopened`

**Priorités:** `low | medium | high | critical`
**Niveaux escalade:** `L1 → L2 → L3 → DG`

**Workflow de routage — DYNAMIQUE (pas de cascade obligatoire) :**
Après qualification par le secrétaire/agent (triage), le ticket peut être routé directement vers :
1. Une **direction** (le directeur prend la main)
2. Un **service/unité** précis (le chef prend la main)
3. Un **agent spécifique** directement (bypass chef et directeur)

Le secrétaire a l'autorité complète de routage vers n'importe quel niveau — le chemin direction → chef → agent n'est pas obligatoire. Implémenté dans `app.queue.tsx` (champ "Personne cible", bouton "Résoudre directement") + `requests.ts` (`qualifyTriage()` passe `assignee_id`) + `ServiceRequest.py` (`qualify_triage`).

---

## Stack technique

| Aspect | Frontend | Backend |
|--------|----------|---------|
| Framework | React 19.2 + TanStack Router 1.168 / Start 1.167 (SSR-capable) | FastAPI 0.99.1 (dernière version native pydantic v1) + SQLAlchemy 2.x async |
| DB | N/A | MySQL 8+ (`edg_ticketing`, user `root`, mdp vide en dev) via aiomysql |
| Auth | JWT (localStorage) + auto-refresh | JWT HS256 (Argon2) + biométrie admin optionnelle |
| State | TanStack React Query 5.83 | Pattern Service → Repository → Model |
| Build | Vite 7.3 + Nitro 3.0 | Uvicorn (dev) / Gunicorn + UvicornWorker (prod, `gunicorn_conf.py`, 4 workers) |
| Langage | TypeScript 5.8.3 (strict) | Python 3.10+ / Pydantic v1.10 |
| UI | Radix UI (40+) + shadcn/ui (60+, new-york style, slate base) + Tailwind 4.2 (OKLch) | Swagger `/docs` + ReDoc `/redoc` |
| Validation | Zod 3.24 + React Hook Form 7.71 | Pydantic v1 validators |
| Temps réel | SSE client (`sse-client.ts`) | SSE endpoint + event bus asyncio |
| Sécurité | CORS, JWT refresh, rôle décodé du JWT (UX only) | RBAC re-vérifié en DB, soft-delete, magic bytes, ClamAV, blacklist Redis, rate limiting |

**Frontend — libs additionnelles:** Lucide React (icônes), Recharts 2.15 (graphiques), Framer Motion 12 (animations), Sonner (toasts), Vaul (drawer mobile), Embla Carousel, xlsx (exports Excel)

**Backend — dépendances clés (`backend/requirements.txt`):**
`fastapi==0.99.1`, `starlette==0.27.0`, `sqlalchemy[asyncio]>=2.0`, `aiomysql`, `pymysql`, `alembic` (migrations), `pydantic<2.0`, `python-jose[cryptography]` + `passlib[argon2]` + `argon2-cffi` (auth), `redis[hiredis]` (blacklist/rate-limit optionnel), `sse-starlette<2.0` (SSE), `insightface` + `onnxruntime` + `opencv-python-headless` (biométrie ArcFace), `apscheduler` (escalade auto SLA), `openpyxl` + `fpdf2` (exports rapports Excel/PDF), `cryptography` (Fernet AES-128 champs sensibles), `httpx` (passerelle SMS), `aiosmtplib` (mail)

**Commandes dev:**
- Frontend (`frontend/`) : `npm run dev` (Vite), `npm run build`, `npm run lint`, `npm run format`
- Backend (`backend/`) : `uvicorn api.main:app --reload --port 8000` ; prod : `gunicorn api.main:app -c gunicorn_conf.py`

---

## Architecture Frontend (`frontend/src/`)

**Routing:** File-based dans `routes/`. Convention : `app.requests.$id.tsx` → `/app/requests/:id`
**Alias:** `@/*` → `./src/*`

**Routes publiques:** `/`, `/login`, `/register`, `/admin-login`, `/forgot-password`, `/help`, `/track`, `/create-request`, `/knowledge`
**Routes app protégée:** `/app`, `/app/requests`, `/app/requests/:id`, `/app/requests/history`, `/app/new`, `/app/queue`, `/app/triage`, `/app/my-tickets`, `/app/supervision`, `/app/direction`, `/app/dg`, `/app/chief-inbox`, `/app/reports`, `/app/sla-center`, `/app/notifications`, `/app/knowledge`, `/app/profile`
**Routes admin (`/app/admin/*`):** users, security, directions, directions/$id, departments, units, org, priorities, references, sla, routing, knowledge, communication, logs, audit, homepage (pas de route `settings` dédiée — réglages répartis entre communication, references, priorities, sla, routing, homepage)

**Session/Auth:** `src/lib/session.ts` — `getRole()` décode le JWT access token en priorité (rôle local = UX only, le vrai rôle vient toujours du JWT signé serveur / re-vérifié en DB côté backend)

**Composants custom clés (`src/components/`):**
- `app-layout.tsx` — layout principal : sidebar collapsible desktop, hamburger + bottom nav mobile, indicateur SSE (dot vert/ambre/gris via `useRealtimeStatus()`)
- `new-request-form.tsx` — formulaire création demande (sélecteur direction visible pour tous les rôles)
- `notification-panel.tsx` — panneau notifications SSE temps réel
- `appreciation-form.tsx` — formulaire CSAT (1-5 étoiles)
- `escalation-progress-bar.tsx` — stepper escalade (Création→Chief→Directeur→DG→Résolution→Clôture)
- `workflow-timeline.tsx` — timeline du workflow de traitement
- `glass-card.tsx` — carte glassmorphique (design system de l'app)
- `async-states.tsx` — `AsyncSwap` : machine d'état loading/empty/error/ready animée
- `status-badge.tsx`, `pagination-bar.tsx`, `metadata-fields.tsx`

**Librairie API (`src/lib/api/`):**
`client.ts` (fetch + JWT auto-refresh + désencapsulation `{success, message, data}`), `auth.ts`, `requests.ts`, `accounts.ts`, `directions-units.ts`, `attachments.ts`, `comments.ts`, `escalations.ts`, `knowledge.ts`, `announcements.ts`, `activityLogs.ts`, `csat.ts`, `communication.ts`, `homepage.ts`, `workflow.ts`, `notifications.ts`, `admin-config.ts`, `securityIncidents.ts`, `biometric.ts`

**Realtime (`src/lib/realtime/`):**
- `sse-client.ts` — `SSEClient` singleton, `connect(getToken)`, backoff exponentiel 1s→30s, `on(eventType, handler)`
- `invalidation-map.ts` — `INVALIDATION_MAP` mappant chaque événement SSE sur les prefixes queryKey TanStack Query à invalider (`request.*`, `escalation.*`, `task.*`, `notification.*`, `announcement.*`, `user.*`, `reference.*`)
- `src/providers/realtime-provider.tsx` — monté uniquement dans `/app` (après auth guard), connecte/déconnecte SSE, invalide le cache React Query, expose `useRealtimeStatus()`

**Mock data restante (`src/lib/mock-data.ts`):** directions/services (8), utilisateurs exemples (23), listes statuts/priorités/catégories pour formulaires — pas de logique métier réelle dedans ; objectif à terme : supprimer ces dépendances au profit du backend.

---

## Architecture Backend (`backend/api/`)

**Entry point:** `main.py` → `uvicorn api.main:app`
**Couches:** `routes/ → services/ → repositories/ → models/` (+ `schemas/` pour la validation Pydantic)
**Préfixe global routes:** `/api/v1` (sauf `health_router`)

### Middlewares (ordre d'exécution inverse de l'ordre d'ajout dans `main.py`)
1. `CORSMiddleware` — dev : toutes origines, credentials off ; prod : origines de `CORS_ORIGINS`, credentials on
2. `ResponseWrapperMiddleware` — enveloppe `{success, message, data}` (exclut `/api/v1/events` — SSE)
3. `RequestLoggingMiddleware`
4. `RateLimitMiddleware` — Redis distribué (INCR+EXPIRE) ou fallback en mémoire (fenêtre glissante, dev/monoprocessus) ; limites : `/auth/login` 10/60s, `/auth/register` 5/60s, `/auth/forgot-password` et `/auth/reset-password` 3/60s

### Gardes de démarrage (`dependencies.py` / `Environment.py`)
- `DISABLE_AUTH=True` interdit en production
- `SECRET_KEY` placeholder/court interdit en production (≥32 chars, sans "changeme")
- `REDIS_URL` vide interdit en production (sinon blacklist JWT + rate-limiter non partagés entre workers)

### Lifespan (`main.py`)
Au démarrage : création des tables (`Base.metadata.create_all`), `seed_references()`, `seed_admin()`, démarrage du scheduler (`start_scheduler(interval_minutes=10)` — escalade auto SLA via `core/scheduler.py`). À l'arrêt : `stop_scheduler()`.

### Modèles clés (SQLAlchemy, `models/`)
Tous héritent de `BaseColumns` : `id`, `uuid`, `status`, `infos` (JSON), `created_at`, `updated_at`, `deleted_at` (soft-delete).

- `ModelAccount` — rôle, direction_id, unit_id, matricule, job, disponibilité, avatar_url
- `ModelRequest` — ref (unique), request_status (FK), priority (FK), category (FK), `sla_hours`, `sla_elapsed`, `sla_response_at`, `sla_breached` (⚠️ **pas de colonne `sla_deadline`** — toujours calculer via `TIMESTAMPDIFF`/`DATE_ADD` sur `sla_hours`), assignee_id, requester_id, in_triage, is_external
- Escalation — from/to agent, level (L1/L2/L3/DG), reason, snapshot immutable
- `ModelTask` — sous-tâches, assignee, due_date (pas de colonne `workflow_id` — lien via `WorkflowDetail`/`Workflow`)
- `ModelWorkflow` / `ModelWorkflowDetail` — pipeline de traitement et ses étapes
- Comment — `is_public` (staff interne vs visible citoyen), author_id
- `ModelAttachment` — storage_path, mime_type, scan_status (ClamAV)
- RequestTimeline — événements horodatés
- `ModelAppreciation` — CSAT rating 1-5
- `ModelSlaPolicy` — response_hours, resolution_hours par priorité
- `ModelRoutingRule` — category+priority → direction+unit
- `ModelNotification`, `ModelActivityLog`, SmsLog, `ModelAnnouncement`, `ModelKnowledgeArticle`
- ActiveSession — sessions actives (DB-backed, multi-worker safe)
- `ModelSecurityIncident` — incidents biométriques/auth

### Routes (`routes/`, ~30 routeurs enregistrés dans `main.py`)
`health`, `RouteAuth`, `RouteSSE`, `RouteReferences`, `RouteUnity`, `RouteOrganigram`, `RouteDirectionsUnits` (+ public), `RouteAccount`, `RouteRequest` (+ `public_request_router` pour `GET /requests/track` et `POST /requests/submit`, sans auth), `RouteAttachment`, `RouteSlaPolicy` (+ read), `RouteRoutingRule` (+ director), `RouteWorkflow` (+ request/detail), `RouteTask`, `RouteNotification`, `RouteActivityLog`, `RouteKnowledgeArticle`, `RouteAnnouncement`, `RouteAppreciation` (+ request), `RouteCsatStats`, `RouteCommunicationSetting`, `RouteAdminConfig`, `RouteUsers` (+ me + avatars), `RouteKnowledge` (+ public), `RouteStats` (+ agent), `RouteReports`, `RouteEscalation`

Toutes les routes protégées passent par `get_current_user()` → recharge l'`Account` depuis la DB (**le rôle vient toujours de la DB, jamais du payload JWT côté client**).
Scoping RBAC : `user` → self only · `agent`/`chief` → unit/direction · `director` → direction · `dg`/`admin` → global.

### Fichiers de configuration/core clés
- `configs/Environment.py` — `BaseSettings` pydantic v1, lit `.env` (voir variables ci-dessous)
- `configs/Database.py` — `create_async_engine` (aiomysql)
- `core/security.py` — JWT HS256 + Argon2
- `core/token_blacklist.py` — Redis-backed + fallback mémoire
- `core/event_bus.py` — bus d'événements SSE asyncio (pub/sub en mémoire, mono-process ; multi-process → Redis Pub/Sub à prévoir)
- `core/file_validator.py` — magic bytes anti-spoofing pour les pièces jointes
- `core/scheduler.py` — APScheduler, escalade automatique SLA (interval 10 min)
- `core/rbac.py`, `core/middleware.py`, `core/exceptions.py`, `core/exception_handlers.py`, `core/error_codes.py`, `core/logger.py`, `core/phone.py`, `core/ref_validation.py`
- `services/ServiceClamAV.py`, `services/ServiceBiometric.py` — scan antivirus et biométrie
- `gunicorn_conf.py` — 4 workers UvicornWorker (prod)

### Variables d'environnement (`.env`, lues par `Environment.py`)
`APP_NAME`, `APP_VERSION`, `APP_ENV`, `DEBUG_MODE`, `PORT` · `DATABASE_DIALECT`, `DATABASE_HOSTNAME`, `DATABASE_PORT`, `DATABASE_NAME`, `DATABASE_USERNAME`, `DATABASE_PASSWORD` · `SECRET_KEY`, `ALGORITHM`, `ACCESS_TOKEN_EXPIRE_MINUTES`, `REFRESH_TOKEN_EXPIRE_DAYS` · `REDIS_URL` · `CLAMAV_HOST`, `CLAMAV_PORT`, `CLAMAV_TIMEOUT`, `CLAMAV_ENABLED` · `DISABLE_AUTH` · `CORS_ORIGINS` · `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD` · `SMS_GATEWAY_URL`, `SMS_API_KEY`, `SMS_SENDER` · `ENCRYPTION_KEY` (Fernet, chiffrement champs sensibles — vide = désactivé)

---

## Temps réel (SSE)

Choisi plutôt que WebSocket — communication unidirectionnelle serveur→client suffisante. Implémenté juin 2026.

- **Endpoint:** `GET /api/v1/events?token=<jwt>` (token en query param — limitation d'`EventSource`), keepalive ping toutes les 25s, fan-out filtré par rôle. `DISABLE_AUTH=True` → mock admin.
- **Event bus:** `AppEvent(type, payload, target)`, `target: {"roles": "all"|[...], "user_ids": [...]}`, singleton `event_bus`, helper `emit()` fire-and-forget (n'exceptionne jamais).
- **Services émetteurs** (`emit_event` après chaque mutation) : `ServiceRequest` (created, status_changed, assigned, closed, resolved, reopened, cancelled), `ServiceNotification` (created, ciblage user_id), `ServiceEscalation` (created, resolved), `ServiceTask` (created, completed), `ServiceAnnouncement` (created, published, closed).

---

## Authentification biométrique admin

Déclenchement via compteur `sessionStorage` (`edg.admin.fail_count`) : 1ère erreur → message standard ; 2ème erreur et suivantes → trigger caméra + capture métadonnées (browser/OS/device/location) ; succès → reset du compteur.

- **Modèle:** InsightFace/ArcFace (ONNX) — `insightface>=1.0.0` + `onnxruntime` + `opencv-python-headless`, modèle `buffalo_l` (~360 Mo, téléchargé auto dans `~/.insightface/models/buffalo_l/`), compatible Python 3.10+.
- **Seuil:** `BIOMETRIC_THRESHOLD=40.0` (env var) — confidence = cosine_similarity × 100. ≥40% → MATCH (session+tokens créés) ; <40% → NO_MATCH (incident créé).
- **Anti-spoofing:** heuristique Laplacian variance (`BIOMETRIC_SPOOF_LAPLACIAN_UPPER=3000`), désactivable via `BIOMETRIC_ANTI_SPOOFING=false`.
- **Fichiers:** `backend/api/services/ServiceBiometric.py` (init lazy InsightFace, `verify_faces()`, `load_reference_image()`, `SpoofDetectedError`), `backend/api/routes/RouteAuth.py` (`POST /auth/biometric-verify`), `frontend/src/routes/admin-login.tsx` (`securityMetaRef`, `triggerSecurity()`), `frontend/src/lib/api/biometric.ts` (`reportSecurityIncident`).
- **Pré-requis:** l'admin doit avoir un `avatar_url` défini, sinon `match=false` + erreur `no_reference_photo`.
- **Incidents sécurité:** tout `no_match`/`error` → `POST /auth/security-incident` (photo + metadata stockés), déduplication 15 min (même identifiant → `attempt_count` incrémenté au lieu d'un nouvel incident), notifiés aux admins via SSE + in-app.

---

## Modules en suspens (état d'avancement)

- **Module 1 — Routage dynamique triage** ✅ TERMINÉ (voir section Workflow ci-dessus)
- **Module 2 — `task_id` dans `workflow_detail`** ⏳ EN ATTENTE CHEF : doit-il pointer vers la table `task` existante (objet de travail concret) ou vers une nouvelle table de types d'étapes ? Ne rien coder tant que la réponse n'est pas donnée.
- **Module 3 — `accepted` dans `workflow_detail`** ⏳ EN ATTENTE CHEF : champ `accepted` (1=accepté, 0=refusé) souhaité, mais intention exacte floue ("l'idée du chef est loin de ça" sur une interprétation déjà proposée). Ne rien coder tant que le cas d'usage exact n'est pas précisé.

**Écarts CDC connus (dernier audit 2026-06-24, score 112/116 = 96,6%):**
- DG5 : ✅ corrigé (vérifié 2026-07-04) — `/app/dg` dispose d'un panneau "Annonce globale" fonctionnel (titre/corps/catégorie/priorité + publication)
- S9 : ✅ corrigé (vérifié 2026-08-01, audit espace administrateur) — `backend/.env` a désormais `DISABLE_AUTH=False`

---

## Règles de travail à respecter

1. **Conformité CDC:** après chaque session de correction ou d'ajout de fonctionnalité (backend ou frontend), lancer un audit de conformité vs `docs/cahier-des-charges.md` (§5 fonctionnalités par rôle, §6 règles métier SLA/routage/notifications/escalade/CSAT/KB/annonces, §7 sécurité JWT/biométrie/RBAC/rate limiting/CORS/audit trail) avant de déclarer la session terminée. Produire un tableau ✅/⚠️/❌ avec score global et signaler les écarts (priorité + effort).
2. **Docs à jour:** à chaque évolution du frontend (nouveaux champs `mock-data.ts`, nouveaux statuts, nouvelles routes/entités), mettre à jour `docs/cahier-des-charges.md` et `docs/mise-a-jour-backend.md` (incrémenter version, ajouter entrée changelog).
3. **RBAC:** ne jamais faire confiance au rôle décodé côté client pour des décisions de sécurité — toujours re-vérifier via la DB côté backend.
4. **SLA:** ne jamais utiliser une colonne `sla_deadline` (elle n'existe pas) — toujours dériver via `sla_hours` + `TIMESTAMPDIFF`/`DATE_ADD`.
5. **Pydantic:** ne pas mélanger v1 et v2 — le backend est figé sur pydantic v1 (contrainte FastAPI 0.99.1).
