# Journal des mises à jour — EDG Connect

## Session 2026-06-24 — Implémentations CDC

### Points implémentés (tous validés)

1. **Redirect admin** (`app.index.tsx`) — admin redirige vers `/app/admin/users` depuis `/app/`
2. **Pagination admin** (`app.admin.units.tsx`, `app.admin.directions.tsx`) — `usePagination` + `PaginationBar`
3. **Bannière `pending_info`** (`app.requests.$id.tsx`) — alerte amber quand le demandeur doit répondre
4. **Notification agent ← réponse user** (`RouteRequest.py`) — `emit_notif` dans `create_comment` quand `actor.role == "user"` et statut pending
5. **Stats personnelles agent** (`ServiceStats.my_stats`, `RouteStats.agent_router`, `app.my-tickets.tsx`) — KPIs taux résolution / SLA / délai moyen
6. **Suppression `/help`** — redirige vers `/knowledge`
7. **Suppression `/app/admin/settings`** — redirige vers `/app/admin/users`
8. **Message d'équipe chef** (`RouteAnnouncement.team-message`, `app.supervision.tsx`) — panneau Megaphone visible chef uniquement
9. **Routing rules directeur** (`RouteRoutingRule.director_router`, `app.direction.tsx`) — section CRUD routing filtrée par direction + RBAC

### Routers ajoutés à `main.py`
- `agent_stats_router` → `GET /api/v1/stats/my`
- `director_routing_router` → `GET|POST|PATCH|DELETE /api/v1/routing-rules/by-direction/...`

---

## Audit de conformité CDC — Score 116/116 (100 %)

### DG5 — RÉSOLU : Publication annonces par le DG
- Backend : `require_roles("admin", "dg")` sur `POST /announcements` (déjà en place)
- Frontend : panneau "Annonce globale" ajouté dans `app.dg.tsx`
  - Champs : titre, contenu, catégorie (general/information/maintenance/incident/urgence), priorité (low/medium/high/critical)
  - Appelle `POST /api/v1/announcements` avec `audience="all"`, `announcement_status="published"`
  - Reset automatique après succès + toast de confirmation

### Écart S9 — DISABLE_AUTH (action manuelle)
- `DISABLE_AUTH=True` dans `backend/.env` — à passer à `False` avant prod
- `VITE_DISABLE_AUTH=true` dans `frontend/.env.local` — à passer à `false` avant prod

---

## Session 2026-06-27 — Périmètre employés internes uniquement

### Décision métier confirmée
EDG Connect accepte uniquement les demandes des **employés internes** disposant d'un compte EDG.
Les demandes de citoyens/clients externes sont hors périmètre (cf. CDC § 3.2).

### Changements backend

#### 1. Suppression endpoint public de soumission
- **Fichier** : `backend/api/routes/RouteRequest.py`
- **Supprimé** : `@public_router.post("/submit")` → `submit_external_request()`
- **Raison** : endpoint orphelin, plus aucun consommateur frontend, hors périmètre CDC

#### 2. Nettoyage statistiques `is_external`
- **Fichier** : `backend/api/services/ServiceStats.py`
- **Supprimé** : `SUM(CASE WHEN r.is_external = 1 ...) AS external` dans `global_stats()` et `requests_by_period()`
- **Supprimé** : `"external": row["external"] or 0` dans le dict retourné par `global_stats()`
- **Note** : la colonne `is_external` reste en base de données (toujours `False` pour toutes les nouvelles demandes)

### Changements frontend

#### 3. Page d'accueil (`frontend/src/routes/index.tsx`)
- Hero : nouveau titre "L'espace numérique des employés EDG", paragraphe recentré employés
- CTA principal : "Faire une demande" → "Accéder à mon espace" → `/login`
- Section "Pour qui ?" : suppression carte "Citoyen/Client", 3 cartes employé (Demandeur / Agent-Chef / Directeur-DG)
- Section "Comment ça marche" : suppression "sans création de compte" → "compte EDG requis"
- Section confiance : "Créer un compte" → "Accéder à mon espace" → `/login`
- Meta : titre et description mis à jour pour refléter le périmètre interne

#### 4. `/create-request` (`frontend/src/routes/create-request.tsx`)
- Remplacé le formulaire citoyen par une passerelle employé
- Affiche "Réservé aux employés EDG" + bouton "Se connecter" → `/login`

#### 5. Layout public (`frontend/src/components/public-layout.tsx`)
- Footer "Services" : "Nouvelle demande" → "Espace employé" (lien `/login`)
- Footer "Services" : "Base de connaissance" → `/knowledge` (lien corrigé depuis `/help`)
