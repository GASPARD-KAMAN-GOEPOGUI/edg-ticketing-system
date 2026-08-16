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
- `director_routing_router` → `GET|POST|PUT|DELETE /api/v1/routing-rules/by-direction/...`

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
- CTA principal : "Faire une demande" → "Ouvrir un ticket" → `/login`
- Section "Pour qui ?" : suppression carte "Citoyen/Client", 3 cartes employé (Demandeur / Agent-Chef / Directeur-DG)
- Section "Comment ça marche" : suppression "sans création de compte" → "compte EDG requis"
- Section confiance : "Créer un compte" → "Ouvrir un ticket" → `/login`
- Meta : titre et description mis à jour pour refléter le périmètre interne

#### 4. `/create-request` (`frontend/src/routes/create-request.tsx`)
- Remplacé le formulaire citoyen par une passerelle employé
- Affiche "Réservé aux employés EDG" + bouton "Se connecter" → `/login`

#### 5. Layout public (`frontend/src/components/public-layout.tsx`)
- Footer "Services" : "Nouvelle demande" → "Espace employé" (lien `/login`)
- Footer "Services" : "Base de connaissance" → `/knowledge` (lien corrigé depuis `/help`)

---

## Session 2026-08-14 — Messagerie : conversations privées par paire (BR-MESSAGING-PAIR-001)

### Problème
Le module Discussion d'un ticket était un fil unique par ticket : tout membre
du staff ayant accès RBAC au ticket (agent/chef/direction dans son périmètre,
admin) voyait l'intégralité des messages, y compris ceux échangés avec un
**ancien** intervenant après réaffectation du ticket. Remplace l'ancienne règle
`BR-MESSAGING-PARTICIPANTS-001` (accès large à tout intervenant historique).

### Nouvelle règle métier
Une conversation = paire privée **{demandeur, intervenant}**, jamais un fil
global. Un même ticket peut porter plusieurs conversations indépendantes (une
par intervenant successif). Seuls le demandeur et l'intervenant courant
(`assignee_id`) peuvent écrire — et uniquement dans la conversation courante ;
une conversation avec un ancien intervenant devient une archive lecture-seule
pour ses deux participants. L'admin conserve une vue de supervision lecture
seule sur toutes les conversations d'un ticket. Aucun autre rôle (même avec
accès RBAC large au ticket) ne voit un contenu de conversation dont il n'est
pas partie.

### Changements backend (`backend/api/routes/RouteRequest.py`)
- `_CommentBody.peer_id` (nouveau champ, requis pour un commentaire normal) —
  clé stable de la conversation : toujours le côté "intervenant" de la paire,
  jamais inversé selon qui écrit (le demandeur et l'assigné qui répond
  partagent le même `peer_id` = `assignee_id`).
- `_resolve_comment_peer()` — résout `peer_id` à la lecture pour les
  événements historiques (créés avant ce champ), sans migration de données :
  directive → `target_user_id` ; auteur=demandeur → assigné courant ;
  auteur=staff → lui-même.
- `_visible_comment_responses()` (remplace `_hide_internal_comments` /
  `_is_ticket_participant`) — filtre `comment_added` par paire : admin voit
  tout (supervision) ; demandeur voit toute conversation normale (jamais les
  directives) ; staff ne voit que sa propre conversation (peer_id == lui ou
  auteur == lui) ; directive visible seulement à son auteur (chef) et sa
  cible (agent).
- `POST /requests/{id}/comments` — écriture normale limitée à
  `{requester_id, assignee_id}` avec `body.peer_id` obligatoire et égal à
  `assignee_id` ; 422 explicite si le ticket n'a pas encore d'assigné.
- `DELETE /requests/{id}/comments/{id}` — suppression resserrée à l'auteur (ou
  admin) ; l'ancien comportement (tout membre du staff non-owner pouvait
  supprimer le message d'un autre intervenant) est supprimé, incohérent avec
  la nouvelle confidentialité par paire.
- `GET /requests/{id}/comments` — nouveau paramètre `peer_id` (remplace
  `public_only`, supprimé) pour filtrer sur une conversation précise.
- `RepositoryWorkflowDetail.list_comments_by_request()` — simplifié, ne fait
  plus de filtrage `public_only` (déplacé dans la route, dépendant du viewer).

### Changements frontend (`frontend/src/routes/app.requests.$id.tsx`, `frontend/src/lib/api/requests.ts`)
- `CreateCommentData.peer_id` / `RequestItem.comments[].peerId` propagés
  bout-en-bout (le backend résout toujours la valeur, y compris pour les
  événements historiques).
- Sélecteur de conversations (`buildConversations()`) affiché au demandeur et
  à l'admin dès qu'il existe plus d'une conversation sur le ticket ; l'agent
  courant/ancien voit directement son unique fil, sans sélecteur.
- Composeur actif uniquement sur la conversation courante
  (`isViewingCurrentConversation`) ; nouveaux messages de verrouillage :
  "pas encore d'intervenant assigné", "vue de supervision admin (lecture
  seule)", "conversation archivée avec un ancien intervenant".
- Suppression resserrée à l'auteur (+ admin), cohérent avec le backend.

### Non régression
Aucune migration de base de données (tout vit dans `workflow_detail.infos`,
déjà JSON libre). Journal d'audit, workflow, statuts, SLA, pièces jointes et
notifications non touchés. Mécanisme et autorisation d'envoi des directives
chef→agent inchangés ; seule leur visibilité en lecture est resserrée au
couple (chef auteur, agent cible) + admin.

---

## Session 2026-08-14 (suite) — Mode de développement LAN

### Besoin
Pouvoir utiliser l'application depuis un téléphone/PC sur le même réseau
Wi-Fi que le poste de développement, sans toucher manuellement une IP à
chaque fois.

### Ajouts (purement additifs — aucun fichier existant modifié)
- `scripts/dev-lan.ps1` — détecte l'IP LAN, vérifie ports/pare-feu, démarre
  backend (`backend/start-dev.ps1 -BindHost 0.0.0.0`) et frontend
  (`vite dev --host 0.0.0.0 --mode lan`) dans des fenêtres séparées, génère
  `frontend/.env.lan.local` (gitignored, régénéré à chaque lancement,
  `VITE_API_URL=http://<IP_LAN>:8000/api/v1`), affiche les URLs + QR code
  (best-effort), arrête proprement les deux processus sur CTRL+C.
- `docs/DEV-LAN.md` — documentation d'usage et dépannage.

### Pourquoi aucune modification de `main.py`/CORS/auth n'était nécessaire
`CORSMiddleware` (`backend/api/main.py`) autorise déjà `allow_origins=["*"]`
avec `allow_credentials=False` en développement — sûr car l'authentification
est 100% JWT via header `Authorization: Bearer` (`localStorage`, aucun
cookie, confirmé dans `frontend/src/lib/session.ts`/`client.ts`). Le frontend
lit déjà `VITE_API_URL` comme URL absolue (`client.ts`, `sse-client.ts`) —
seul point à rendre dynamique, résolu via `.env.lan.local` + `--mode lan`
sans toucher `.env.development` (utilisé par `npm run dev`).
`backend/start-dev.ps1` supportait déjà `-BindHost`, réutilisé tel quel.

---

## Session 2026-08-15 — Export du dossier complet d'une demande (Administration)

### Besoin
Permettre à l'administrateur d'obtenir, depuis la fiche détail admin d'un
ticket, le dossier fonctionnel complet de cette demande (identification,
demandeur, structure organisationnelle, acteurs, historique, escalades,
conversations, pièces jointes, notifications) — **sans aucune donnée SLA/délai**,
sans effet de bord métier, réservé au rôle `admin`.

### Constat d'audit préalable
Aucune table dédiée `Comment`/`Escalation`/`RequestTimeline` n'existe. Tout
l'historique fonctionnel d'un ticket est un flux unique append-only de
`WorkflowDetail` (`Request.timelines`), distingué par `event_type` et le
JSON `infos`. L'export réutilise cette seule source de vérité — aucune
nouvelle table, colonne ou relation créée.

### Backend
- **Ajouté** : `backend/api/services/ServiceRequestExport.py` —
  `RequestExportService.build_dossier(request_id)` : agrège `Request`
  (relations déjà `lazy="selectin"`, aucune requête supplémentaire pour
  l'essentiel), la chaîne organisationnelle du demandeur (`OrganigramRepository.
  get_ancestors`), les événements (`Request.timelines`), les pièces jointes et
  les notifications (`NotificationRepository.list_by_request`), puis génère un
  classeur Excel (`openpyxl`) à 7 feuilles : Synthèse, Acteurs, Historique,
  Escalades, Conversations, Pièces jointes, Notifications. Toute clé contenant
  `sla` est exclue de la construction (aucun champ délai/SLA dans l'export).
- **Ajouté** à `backend/api/routes/RouteRequest.py` :
  `GET /api/v1/requests/{id}/export` — `Depends(require_roles("admin"))`
  uniquement (même pattern que `DELETE /{id}`), lecture seule (aucun
  changement de statut, notification ou événement émis), réponse xlsx via
  `ServiceExport.build_response`.
- **Ajouté** aux barrels `backend/api/services/__init__.py`
  (`RequestExportService`).
- **Tests** : `backend/tests/api/test_request_export.py` — RBAC (403 pour
  `user`/`agent-support`/`chief-service`/`director`), ticket vide (7 feuilles
  présentes, message « Aucune donnée enregistrée »), ticket avec cycle de vie
  complet (qualification/assignation → commentaire → résolution → clôture) et
  assertion qu'aucune cellule du classeur ne contient la sous-chaîne `sla`.

### Frontend
- **Ajouté** à `frontend/src/lib/api/requests.ts` : `exportRequestDossier(id)`
  — réutilise `apiFetchBlob` (même pattern que `fetchAttachmentFile`).
- **Ajouté** à `frontend/src/routes/app.requests.$id.tsx` : bouton
  « Exporter la demande » dans l'en-tête de la fiche, visible uniquement si
  `context === "admin"` (donc uniquement via `/app/admin/tickets/$id`, jamais
  sur la route générique `/app/requests/$id`) — aucune invalidation de cache
  React Query, aucune mutation, téléchargement direct du blob xlsx.

### Non régression
`ServiceExport.py` n'a pas été modifié (rapports agrégés existants
inchangés). Aucune migration de base de données.

Fichiers créés : `scripts/dev-lan.ps1`, `docs/DEV-LAN.md`.
