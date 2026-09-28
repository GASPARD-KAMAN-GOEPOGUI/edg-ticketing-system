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
  `user`/`chief-service`/`chief-service`/`director`), ticket vide (7 feuilles
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

---

## Session 2026-08-19 — Rattachement post-login sans compte local (auto-provisioning + consentement)

### Besoin
`resolve_central_account()` (`backend/api/dependencies.py`) rejetait
systématiquement avec 401 tout utilisateur authentifié avec succès par la
plateforme centrale `manager-user` mais sans compte local rattaché
(`central_user_id`), sans jamais distinguer :
- un utilisateur **déjà membre** d'un groupe support de cette application
  (`admin-support`/`qualify-support`/`collaborateur-support`) mais dont le
  miroir local est absent (compte créé côté central par une autre équipe, ou
  perdu localement) ;
- un utilisateur central connu mais **sans aucun groupe** de cette
  application (ex. seulement `employe-edg`, `manager-link-hub`).

Aucun mécanisme de consentement n'existait dans le code (colonnes DB,
endpoint, écran) — confirmé par audit exhaustif avant implémentation.

### Constat d'audit préalable
L'intégration centrale était déjà largement fonctionnelle et testée (login/
refresh/scopes/groupes, synchronisation de rôle dans `_ROLE_SYNC_SPACE`,
inscription entièrement câblée au central, opérations de compte via token
machine). Le changement de mot de passe self-service (`/auth/reset-password`
→ `central_auth.reset_central_password(..., new_password=...)`) et l'anti-
doublon inscription (vérifications locales + idempotence du central sur
`POST /v1/client-app-users/group-membership`) étaient déjà corrects — non
modifiés. Seul le bug ci-dessus a été traité.

### Backend
- **`backend/api/core/central_auth.py`** : nouveau `get_profile(bearer_token)`
  — `GET /api/me` (endpoint confirmé par l'équipe plateforme centrale, hors
  périmètre du README d'intégration qui ne documente que `DELETE
  /v1/users/{id}`), renvoie le profil complet (nom/prénom/téléphone/uuid).
  Nouveau `parse_profile_identity(profile)` — extraction défensive
  (convention centrale observée ailleurs dans ce module : `name`=prénom,
  `last_name`=nom de famille ; ne lève jamais, champs manquants → `None`,
  complétés manuellement sur l'écran de rattachement).
- **Migration `018_add_consent_to_account.py`** + `ModelAccount.py` :
  colonnes `consent_accepted_at` (DateTime), `consent_version` (String(50)),
  nullable, sur `account`.
- **`backend/api/services/ServiceAccount.py`** : nouvelle méthode
  `provision_from_central()` — matérialise le miroir local d'une identité
  **déjà existante** côté central (pas de création centrale, contrairement à
  `create()`) ; vérifie l'unicité locale email, tolère un conflit de
  téléphone (champ secondaire, omis plutôt que bloquant).
- **`backend/api/dependencies.py`** : `resolve_central_account()` refactorisé
  (extraction de `_ensure_account_active()`/`_sync_role_from_groups()`/
  `_fetch_scopes_and_groups()`, comportement externe inchangé — toujours
  strict pour `get_current_user`/SSE). Nouvelle fonction
  `resolve_or_provision_login_account()`, réservée à `POST /auth/login` :
  auto-provisionne silencieusement si `role_from_groups(groups)` est non vide
  (utilisateur déjà dans un groupe support), sinon retourne `(None, scopes)`.
- **`backend/api/schemas/SchemaAuth.py`** : `ConsentRequiredResponse` (retour
  de login quand aucun compte n'a pu être résolu/provisionné — 200, jamais
  401) et `ConsentAcceptRequest`.
- **`backend/api/routes/RouteAuth.py`** :
  - `POST /auth/login` — `response_model=Union[TokenResponse,
    ConsentRequiredResponse]` ; appelle `get_profile()` pour pré-remplir les
    suggestions (nom/prénom/téléphone) dans les deux branches (provisioning
    silencieux ou consentement).
  - **Nouveau** `POST /auth/consent/accept` (bearer central du login, jamais
    de nouveau `central_login`) — revérifie scopes/groupes côté central
    (jamais confiance au payload), idempotent si le compte existe déjà
    (retry réseau/double clic), sinon `add_group_membership(...,
    "collaborateur-support", ...)` + `provision_from_central(role="user",
    consent_accepted_at=now(), consent_version=...)`.
- **`backend/api/main.py`** : `_RATE_LIMITS["/api/v1/auth/consent/accept"] =
  (5, 60)` — même tier que `/auth/register` (crée aussi un compte).
- **Tests** (`backend/tests/api/test_auth.py`, fixture `mock_central_auth`
  étendue avec `get_profile`, `inactive_groups`, `added_memberships`) :
  auto-provisioning silencieux (rôle mappé correctement pour les 3 groupes
  support) ; `needs_consent=true` sans groupe support, avec groupes d'autres
  applications uniquement, et avec groupe support `is_activated=false` ;
  `POST /auth/consent/accept` — succès, idempotence sur double appel, 401
  sans bearer/bearer invalide, 422 nom vide. `test_login_compte_non_rattache_
  retourne_401` renommé/réécrit en `test_login_sans_groupe_support_retourne_
  needs_consent` (le comportement attendu a changé : 200 + `needs_consent`
  au lieu de 401 sec). 32/32 tests `test_auth.py` verts ; suite complète
  `tests/api/` : mêmes 63 échecs pré-existants qu'avant ce changement
  (vérifié par comparaison stash/baseline — homepage slides, RBAC, workflow
  tickets, sans rapport avec l'authentification), aucune régression.

### Frontend
- **`frontend/src/lib/api/auth.ts`** : `loginUser()` retourne désormais
  `LoginResult` (union discriminée `needsConsent: false/true`). Nouveau
  `acceptConsent()` — passe le bearer central via un header explicite
  (`skipAuth: true` + `Authorization` manuel), le token n'étant pas encore en
  session tant que le consentement n'est pas accepté.
- **`frontend/src/lib/session.ts`** : `setPendingConsent()`/
  `getPendingConsent()`/`clearPendingConsent()` — `sessionStorage` (jamais
  `localStorage`), auto-effacé à la fermeture de l'onglet, distinct de la
  session applicative persistée.
- **Nouvelle route `frontend/src/routes/consent.tsx`** — écran de
  rattachement (email lecture seule, nom/prénom/téléphone pré-remplis mais
  modifiables, checkbox obligatoire liée à `/legal/terms`/`/legal/privacy`) ;
  `beforeLoad` redirige vers `/login` si aucun consentement en attente.
- **`frontend/src/routes/login.tsx`** — si `needsConsent`, stocke la charge
  utile via `setPendingConsent()` puis navigue vers `/consent` (jamais de
  `setTokens`/`setUser` avant acceptation).
- **`frontend/src/routes/admin-login.tsx`** — `needsConsent` traité comme un
  refus d'accès identique au cas rôle≠admin ; jamais de redirection vers
  l'écran de consentement depuis cette page (pas d'auto-élévation admin).
- **Nouvelles pages placeholder** `frontend/src/routes/legal.terms.tsx` /
  `legal.privacy.tsx` — texte générique marqué « À compléter », rien ne
  bloque en attendant le texte légal définitif.
- **`frontend/src/routes/app.profile.tsx`** — correction d'une incohérence
  détectée à l'audit : la section « Sécurité » affirmait à tort que seul un
  administrateur pouvait réinitialiser le mot de passe (contredisant le flux
  self-service `/forgot-password` déjà fonctionnel) ; texte corrigé + lien
  « Changer le mot de passe ».

### Vérification
`npx tsc --noEmit` : zéro nouvelle erreur (mêmes 55 erreurs pré-existantes,
aucune dans les fichiers touchés). Test navigateur (Playwright, dev server
local) : `/legal/terms`, `/legal/privacy`, `/login` sans erreur console ;
`/consent` avec charge de consentement simulée en `sessionStorage` — champs
pré-remplis, checkbox gate le bouton, aucune erreur console/hydratation. Un
hard-refresh direct sur `/consent` sans consentement en attente déclenche un
avertissement d'hydratation React (mismatch SSR/CSR) — **reproduit à
l'identique sur `/admin-login` existant** (non modifié), confirmé pré-
existant au framework (`ssr:false` + redirection `beforeLoad` sur
navigation complète) et hors périmètre de cette session.

### Limitation connue liée à l'API centrale
La forme exacte de la réponse `GET /api/me` (présence garantie d'un
`uuid`/`user_uuid`, noms de champs) n'a pas pu être observée en conditions
réelles dans cette session (pas d'accès à un bearer central valide) — le
parsing est défensif (`parse_profile_identity`) et dégrade proprement (champs
manquants → `None`, complétés manuellement par l'utilisateur), mais un test
en conditions réelles avec un compte central de test reste recommandé avant
mise en production, en particulier pour confirmer que `central_user_uuid`
est bien capturé (indispensable pour les opérations admin ultérieures sur un
compte auto-provisionné : activation/désactivation/reset mot de passe).

Fichiers créés : `backend/alembic/versions/018_add_consent_to_account.py`,
`frontend/src/routes/consent.tsx`, `frontend/src/routes/legal.terms.tsx`,
`frontend/src/routes/legal.privacy.tsx`.

---

## Session 2026-09-22 — Qualification : organisation traitante déduite du qualifiant

### Règle métier
Seule la Direction des Systèmes d'Information traite les incidents. Lors de la
qualification, le chef de service (CSSHF) n'a donc pas à choisir une direction,
un département ni un service : l'organisation traitante **est** son propre
rattachement, déjà renseigné par l'administrateur au back-office.

Les champs organisationnels du ticket ne sont pas supprimés pour autant — ils
sont le contrôle de la qualification. Un ticket porte deux photographies
distinctes, à ne pas confondre :

| Dimension | Champ | Source |
| --- | --- | --- |
| Organisation **traitante** | `unity_id` (colonne), `direction_id` (dérivé de `unity.parent_direction_id`) | compte du chef de service qui qualifie |
| Organisation **du demandeur** | `requester_unit_id`, `requester_job`, `employee_matricule` (dérivés) | compte du demandeur |

### Backend

`api/services/ServiceRequest.py` — `qualify_triage()` : `patch["unity_id"]` vient
désormais de `actor.unity_id`. Le repli sur `data["unit_id"]` / `data["direction_id"]`
ne s'applique plus que si l'acteur n'a aucun rattachement (cas admin). La règle
est donc appliquée **côté serveur** : un `unit_id` forgé dans un appel API direct
est ignoré, retirer les champs de l'UI n'aurait pas suffi.

`api/models/ModelRequest.py` — deux propriétés dérivées ajoutées :
`requester_job` (→ `Account.job`) et `employee_matricule` (→ `Account.matricule`).
Elles ne lisent que des colonnes simples de `self.requester`, déjà chargé en
`lazy="selectin"` — aucun chargement différé n'est déclenché (même contrainte que
`requester_unit_id` existant ; accéder à `requester.unity` aurait au contraire
provoqué un `MissingGreenlet` en contexte async).

`api/schemas/SchemaRequest.py` — `requester_job` et `employee_matricule` exposés
dans `_RequestCommonFields`. Le frontend les lisait déjà (`requests.ts`) mais
l'API ne les a jamais fournis : ils arrivaient systématiquement `undefined`.

Aucune migration : tout est dérivé, aucune colonne ajoutée.

### Frontend

`frontend/src/routes/app.queue.tsx` — retrait des trois cascades Direction →
Département → Service, du bandeau « Routage suggéré » et de son bouton
« Appliquer » (qui ne pilotaient que les champs supprimés), ainsi que des
requêtes devenues sans objet : `fetchDirections`, `fetchDepartments`,
`fetchUnits`, `fetchRoutingRules`. `TriageForm` se réduit à
`{ category, priority, personId }`, `canAssign` à `Boolean(form.personId)`.
`qualifyTriage()` n'envoie plus `direction_id` ni `unit_id`.

Le département n'a pas eu besoin d'être ajouté au ticket : une unité porte déjà
son `department_id`/`department_name` (API `/units/`), et `app.requests.$id.tsx`
reconstitue les deux triplets Direction/Département/Service depuis `serviceId`
(traitant) et `requesterServiceId` (demandeur).

### Vérification
`npx tsc --noEmit` : zéro erreur dans `app.queue.tsx` (49 erreurs pré-existantes
ailleurs, `app.admin.audit.tsx` et `app.admin.routing.tsx`, non touchées).

Tests backend `tests/api` : **égalité stricte des ensembles d'échecs**, 57 avant
et 57 après, `comm` vide dans les deux sens. Le A/B a été produit en annulant
uniquement les trois modifications de cette session, pas par `git stash` : ces
fichiers portent des modifications non commitées antérieures (BR-DISTRIBUTION-001),
qu'un stash aurait également annulées, faussant la comparaison.

### Suite — figeage des identités organisationnelles
La limitation de traçabilité identifiée ici (valeurs dérivées en direct des
comptes) a été traitée dans la foulée : voir la session ci-dessous.

---

## Session 2026-09-22 (suite) — Figeage des identités organisationnelles

### Problème
`direction_id`, `requester_unit_id`, `requester_job`, `employee_matricule` et
tous les libellés d'unité étaient **dérivés en direct** des comptes et de
l'organigramme. Conséquence : muter une personne, changer sa fonction, renommer
un service ou réorganiser l'organigramme **réécrivait rétroactivement
l'historique** — un incident traité en janvier affichait la situation de
décembre.

Une partie du problème était déjà résolue et n'a pas été refaite : les
**intervenants** sont figés depuis BR-TRACE-001 via
`_actor_identity_snapshot()` (matricule + direction/département/service gelés
dans `workflow_detail.infos` à l'ouverture de chaque intervention). Restaient le
**demandeur** (aucun figeage) et l'**organisation traitante** (service gelé comme
identifiant via `unity_id`, mais direction dérivée et libellés lus en direct).

### Principe retenu
Aucune nouvelle table, aucune nouvelle colonne, aucune migration : le figeage
réutilise le champ JSON `request.infos` et **la forme exacte** du mécanisme déjà
en place pour les intervenants. Trois snapshots, un seul résolveur
d'organigramme commun.

### Backend (`api/services/ServiceRequest.py`)

| Fonction | Rôle | Écrit quand |
| --- | --- | --- |
| `_org_labels_for_unity()` | brique commune : direction/département/service + id de direction d'une unité, résolus via l'organigramme | — |
| `_actor_identity_snapshot()` | intervenant (existant, **refactoré** pour utiliser la brique commune) | ouverture d'intervention |
| `_requester_identity_snapshot()` | demandeur (nouveau) | `create()` |
| `_handler_org_snapshot()` | organisation traitante (nouveau) | `qualify_triage()` |

Clés écrites dans `request.infos` : `requester_unit_id`, `requester_job`,
`requester_matricule`, `requester_direction_id`, `requester_direction_label`,
`requester_department_label`, `requester_service_label`, `handler_unit_id`,
`handler_direction_id`, `handler_direction_label`, `handler_department_label`,
`handler_service_label`.

**Piège corrigé au passage** — dans `update()`, l'ouverture d'intervention
repartait systématiquement des `infos` relues en base, écrasant silencieusement
un patch `infos` fourni par l'appelant. `qualify_triage()` étant précisément un
appelant qui patche `infos` **et** l'assignation, son figeage aurait été perdu.
La fusion part désormais des `infos` de l'appelant quand elles existent.

### Backend (`api/models/ModelRequest.py`)
Propriété `_frozen` (lecture défensive de `infos`), puis chaque lecture
organisationnelle applique la même règle : **valeur figée d'abord, repli sur le
compte / l'organigramme courant** pour les tickets antérieurs au figeage.
Nouvelles propriétés `requester_direction_id`, `requester_direction_label`,
`requester_department_label`, `requester_service_label`,
`handler_direction_label`, `handler_department_label`, `handler_service_label`.

`requester_direction_id` est la seule sans repli : la déduire exigerait de
remonter l'organigramme depuis `self.requester.unity`, donc un chargement
différé interdit en contexte async (`MissingGreenlet`). Le frontend la résout
comme avant depuis `requester_unit_id` pour les anciens tickets.

### Frontend
`requests.ts` : nouveaux champs bruts + mapping (`requesterDirectionLabel`,
`requesterDepartmentLabel`, `requesterServiceLabel`, `handlerDirectionLabel`,
`handlerDepartmentLabel`, `handlerServiceLabel`) ; `requester_unit_id` et
`requester_direction_id` sont désormais explicitement stringifiés (le backend
envoie des entiers, le type brut annonçait `string`).
`app.requests.$id.tsx` : les deux triplets affichés préfèrent le libellé figé et
ne retombent sur l'organigramme courant qu'à défaut.

### Vérification
Nouveau fichier `backend/tests/api/test_org_identity_freeze.py` — **6 tests, tous
au vert**. Ils mutent volontairement les comptes et renomment les unités *après*
création/qualification, puis vérifient que le ticket n'a pas bougé ; le dernier
efface `infos` pour prouver que le repli des anciens tickets fonctionne encore.

Suite `tests/api` : **égalité stricte des ensembles d'échecs**, 57 avant / 57
après, `comm` vide dans les deux sens. `npx tsc --noEmit` : aucune erreur dans
les fichiers modifiés (49 pré-existantes ailleurs, inchangées).

---

## Session 2026-09-22 (suite) — Procédure tâche 1.3 : descriptif de solution proposée

> **Référentiel** — à partir de cette session, l'alignement fonctionnel part de
> `docs/Procédure d'assistance aux utilisateurs.pdf` (réf. EDG/PS-GSI/Pro-02),
> et non plus de `docs/cahier-des-charges.md`. Les écarts sont numérotés par
> tâche du §6.2 de la procédure.

### Règle
Tâche 1.3 — « Recevoir et imputer la réquisition au chef de division support
pour traitement », **point de contrôle : descriptif de la solution proposée**.
Le chef de service décrit la piste de résolution envisagée en orientant le
ticket ; le chef de division la lit pour décider de prendre ou d'affecter, puis
le technicien la lit pour intervenir. **Jamais visible du demandeur** : c'est
une piste interne, qui peut se révéler fausse au diagnostic terrain (tâche 2.1,
« vérification de l'état réel de la requête »).

Obligatoire **uniquement à l'imputation vers un CDS** — prendre le ticket pour
soi-même n'est pas une imputation, la tâche 1.3 ne s'y applique pas.

### Migration
`025_add_proposed_solution.py` — colonne `request.proposed_solution` (TEXT,
nullable). Additive, aucun backfill : les tickets antérieurs restent à NULL.

**À ne pas confondre avec `solution`**, déjà stockée dans les `infos` de
l'événement `treatment_completed` : celle-ci est la solution *réellement
appliquée* par le technicien à la résolution. Les deux décrivent deux moments
différents, par deux acteurs différents, et coexistent.

### Confidentialité — pourquoi un endpoint dédié plutôt qu'un champ de la fiche
Le réflexe serait d'ajouter le champ à `RequestResponse` et de l'effacer pour le
demandeur. Le recensement a montré que **vingt endpoints** renvoient un
`RequestResponse`, dont **sept accessibles au demandeur** (création, édition
personnelle, clôture, réouverture, annulation, suivi public, lecture d'item).
Il aurait fallu effacer le champ à chacun, et le premier endpoint ajouté ensuite
aurait fuité.

Le champ n'est donc exposé que là où il ne peut structurellement pas atteindre
un demandeur :

| Surface | Schéma / endpoint | Garde |
| --- | --- | --- |
| File Distribution du CDS | `DistributionListItemResponse` sur `GET /requests/distribution` | `_distribution_guard` (CDS + admin) |
| Fiche détail (CSSHF, CDS, technicien…) | `GET /requests/{id}/proposed-solution` | rôles support explicites **+ refus si le lecteur est le demandeur de CE ticket** |

`RequestResponse` et `RequestListItemResponse` ne portent **pas** le champ — deux
tests verrouillent cette absence.

Second garde-fou : le champ n'est pas dans `RequestUpdate`, il ne peut donc être
écrit qu'à la qualification, jamais par un `PUT /requests/{id}`.

### Backend
- `RouteRequest.QualifyTriageBody` : champ `proposed_solution`.
- `_assert_queue_target_allowed()` retourne désormais un booléen « est-ce une
  imputation à un CDS ? », réutilisant la requête de rôle qu'elle faisait déjà
  (pas de requête supplémentaire). La route lève un 422 explicite si le
  descriptif manque dans ce cas.
- `ServiceRequest._serialize()` accepte un `schema_cls` (défaut inchangé), pour
  que `list_distribution` serve le schéma élargi sans toucher aux autres listes.

### Frontend
- `app.queue.tsx` : champ « Solution proposée » (Textarea), marqué obligatoire et
  bloquant le bouton d'orientation dès qu'un destinataire est choisi ; conservé
  s'il est renseigné lors d'une prise en charge personnelle.
- `app.distribution.tsx` : encart de lecture dans la file du CDS, là où il décide.
- `app.requests.$id.tsx` : encart sous la description. La requête n'est **même pas
  émise** si le lecteur est le demandeur ou hors des rôles support.

### Tests existants mis à jour (contrat métier changé)
`test_distribution.py` et `test_queue_target_restriction.py` qualifiaient vers un
CDS sans descriptif : 12 tests tombaient en 422. Leurs helpers renseignent
désormais `proposed_solution` — ces tests portent sur la file Distribution et sur
le ciblage, pas sur ce point de contrôle, qui a son fichier dédié.

### Vérification
`backend/tests/api/test_proposed_solution.py` — **12 tests, tous au vert**,
dont quatre de non-fuite : demandeur simple, intervenant demandeur de *son
propre* ticket, absence du champ sur la fiche détail, absence sur les listes.

Suite `tests/api` : **égalité stricte des ensembles d'échecs**, 57 / 57, `comm`
vide dans les deux sens. `npx tsc --noEmit` : aucune erreur dans les fichiers
modifiés.

### Anomalie repérée — corrigée dans la session suivante (voir ci-dessous)
Sur mobile, la barre de navigation basse libellait `/app/my-tickets`
**« Mes tickets »** pour chief-service, chef-division-support et technicien,
alors que cette route est **« Ma boîte de traitement »**.

---

## Session 2026-09-22 (suite) — Barre mobile : les menus indispensables par rôle

### Besoin
Sur mobile, la barre du bas doit porter, **pour le rôle connecté, les menus
indispensables à sa part du traitement d'un ticket** — accessibles en un appui,
sans passer par le tiroir.

**Le tiroir (hamburger) n'est pas concerné et reste exhaustif** : lui et la
sidebar se construisent tous deux depuis `navItems`
(`navItems.filter(i => i.roles.includes(role))`). La barre du bas est un jeu de
**raccourcis** distinct ; elle ne restreint rien.

### Ce qui avait dérivé
La barre était un ternaire imbriqué codé en dur, indépendant de `navItems`, et
avait accumulé trois écarts :
1. `/app/my-tickets` libellé **« Mes tickets »** pour 3 rôles, alors que c'est
   **« Ma boîte »** — l'espace personnel étant `/app/requests`. Le chef de
   département avait, lui, le bon libellé : la correction a consisté à aligner
   les autres sur l'existant.
2. **L'espace personnel `/app/requests` était absent** de la barre pour *tous*
   les rôles de traitement, alors que chaque acteur reste demandeur de ses
   propres tickets.
3. Le directeur gardait un raccourci **« Rapports »** alors que `/app/reports`
   avait été volontairement retiré de la navigation le 2026-08-16 — la barre
   contredisait donc une décision explicite. Retiré.

### Composition retenue
Geste central du rôle en position mise en avant (`primary`), puis l'espace
personnel, puis Alertes et Profil. Cinq entrées au maximum (~360 px).

| Rôle | Tâches procédure | Barre |
| --- | --- | --- |
| user | 1.1 / 3.2 | Accueil · **Créer** · Mes tickets · Alertes · Profil |
| chief-service | 1.2 / 1.3 | **File att.** · Ma boîte · Mes tickets · Alertes · Profil |
| chef-division-support | 1.4 / 3.4 | **Distrib.** · Ma boîte · Mes tickets · Alertes · Profil |
| technicien | 1.5 / 2.x / 3.1 / 3.3 | **Ma boîte** · Mes tickets · Alertes · Profil |
| chief-departement | hors procédure | Superviser · **Ma boîte** · Mes tickets · Alertes · Profil |
| director | hors procédure | Superviser · **Ma boîte** (`/app/direction`) · Mes tickets · Alertes · Profil |
| admin | hors procédure | Accueil · **Utilisateurs** · Journaux · Alertes · Profil |

### Implémentation
Nouveau module `frontend/src/components/mobile-shortcuts.ts` — les raccourcis
sortent de `app-layout.tsx` pour devenir **testables** : le runner Vitest du
projet est volontairement sans JSX (`include: ["src/**/*.test.ts"]`,
environnement node) et ne peut donc pas importer un `.tsx`. `app-layout.tsx`
n'appelle plus que `mobileShortcutsFor(role)`, qui replie sur la barre de
l'utilisateur simple pour un rôle inconnu.

`navItems` n'a **pas** été modifié : le tiroir et la sidebar sont intacts.

### Vérification
`frontend/src/components/mobile-shortcuts.test.ts` — **39 tests**, dont le
garde-fou qui empêche la confusion de revenir : aucune entrée pointant vers une
route de traitement ne peut être libellée « Mes tickets », et aucune entrée
« Mes tickets » ne peut pointer ailleurs que vers `/app/requests`. Couvre aussi
la composition (espace personnel présent, Alertes/Profil en fin, une seule
entrée mise en avant, ≤ 5 entrées, pas de doublon) et la non-réapparition de
« Rapports ».

`npx vitest run` : **124 tests au vert** (2 fichiers, dont les tests
pré-existants). `npx tsc --noEmit` : aucune erreur dans les fichiers modifiés.
`npx vite build` : build de production réussi.

---

## Session 2026-09-23 — Procédure tâche 2.1 : constat d'intervention

### Règle
Bloc 2 « Réalisation de l'intervention », tâche **2.1 — Qualifier la demande**,
point de contrôle **« vérification de l'état réel de la requête »**, livrable
« requête qualifiée ». L'intervenant confronte ce qu'il trouve à ce qui a été
décrit, **avant** d'intervenir : la tâche 2.1 précède la 2.2 (« résoudre le
problème », déjà opérationnelle).

**Deux qualifications coexistent** et ne se confondent pas :

| | 1.2 / 1.3 — CSSHF | 2.1 — Technicien |
| --- | --- | --- |
| Quand | à la réception, avant imputation | sur place, avant d'intervenir |
| Sur quoi | la fiche, sur pièce | l'état réel constaté |
| Où | File d'attente (`/qualify`) | fiche du ticket (`/field-check`) |

`POST /{id}/qualify` et sa garde stricte `_queue_manage_guard` n'ont **pas** été
touchés : le technicien reste exclu de la File d'attente.

### Portée — restreinte au technicien, et pourquoi
Première implémentation : gate sur `/resolve` pour **tout** intervenant →
**30 tests en régression** (résolutions par chef de service, chef de département,
directeur). Ce n'était pas un problème de tests mais de conception : le document
place les tâches 2.1 **et** 2.2 sous la responsabilité du **seul technicien**.
Un chef de département qui termine un traitement ne réalise pas une intervention
de terrain.

Après recentrage sur le technicien : **0 régression**. La règle est donc à la
fois plus fidèle au document et sans effet de bord.

### Backend
- `ServiceRequest._open_intervention()` pose `field_check_required` dans
  `request.infos` **uniquement** si le titulaire de l'intervention est un
  technicien (rôle lu dans `_actor_identity_snapshot`), et le retire sinon (une
  transmission technicien → autre rôle ne doit pas laisser traîner le drapeau).
  Drapeau posé à l'ouverture plutôt que déduit d'une date en dur : les
  interventions antérieures à la règle ne le portent pas et restent résolvables
  — même logique « absent = antérieur = exempté » que le figeage des identités.
- `field_check()` : validation (`conformity` ∈ {`conforme`, `ecart`}, `findings`
  non vide), garde `assert_is_current_handler` (ce n'est pas un rôle qui
  constate, c'est celui qui détient le ticket), puis événement `field_check`
  dans le `workflow_detail` — **aucune table, aucune colonne, aucune migration**.
- Le constat est rattaché à `current_intervention_id`, **pas au ticket** : après
  une transmission, le nouvel intervenant refait le sien.
- `_assert_field_check_done()` appelé dans `resolve()` : refus (400) tant que le
  constat manque.
- Écart → notification aux chefs de service de l'unité **traitante** (choix
  déterministe, plutôt que de chercher dans le journal qui a qualifié). Aucun
  chemin de retour nouveau : transmission et `pending` restent les voies
  existantes. SLA intact (`sla_hours` n'est résolu qu'à la création).

### Frontend
Les actions de traitement vivent dans l'**onglet Traitement** : la carte
« Consigner mon constat » et le rappel du dernier constat sont donc dans
`treatmentActionsPanel`, à côté de Résoudre et Transmettre — nulle part ailleurs.

La **lecture par le demandeur** ne demande aucun câblage :
`_visible_comment_responses` ne filtre que les événements `comment_added`, tout
autre événement du journal passe tel quel. Le constat apparaît donc dans
l'onglet **Journal**, qui est précisément l'onglet par défaut du demandeur.

Contrairement à `proposed_solution` (interne), le constat **est** visible du
demandeur : c'est un fait établi sur son matériel, et il nourrit la validation
qu'il donnera en tâche 3.2.

### Vérification
`backend/tests/api/test_field_check.py` — **13 tests au vert**, dont : blocage de
la résolution sans constat, passage après constat, refus d'un constat vide ou
d'une conformité invalide, refus pour un autre intervenant et pour le demandeur,
notification du CSSHF sur écart (et **silence** sur un constat conforme),
visibilité dans le journal du demandeur, non-régression des interventions
antérieures, et **reprise du constat par le suivant après transmission**.

Suite `tests/api` : **égalité stricte des ensembles d'échecs**, 57 / 57, `comm`
vide dans les deux sens. `npx tsc --noEmit` : aucune erreur dans les fichiers
modifiés. `npx vitest run` : 124 tests au vert. `npx vite build` : réussi.

---

## Session 2026-09-23 (suite) — PV d'intervention : Badge, statut d'intervenant, et fiabilisation de la suite de tests

### Le PV comme référence
Le formulaire **EDG/PS-GSI/PV-01 version 03 (02/06/2026)**, déposé dans `docs/`,
est le document de sortie de toute intervention. Sa structure est le miroir de la
procédure : Réception (1.2), Affectation (1.3/1.4), Traitement (2.x), Émargement
et Appréciations (3.2).

La quasi-totalité de ses rubriques est déjà disponible, plusieurs grâce aux blocs
1 et 2 : organisation traitante figée (1.3), constat terrain (2.1), horaires
d'intervention (BR-TRACE-001), `summary`/`solution`/`work_done` obligatoires à la
résolution.

**Signature** : le formulaire comporte trois emplacements de signature et une
ligne d'émargement, alors que la signature est hors périmètre projet. Sans
contradiction : le pied de page du PV dit « Avant utilisation d'un **document
papier** ». Le PDF sera généré avec **lignes vierges**, signées au stylo.

### Badge — renommage de libellé uniquement
« Matricule » devient « **Badge** » partout où l'utilisateur le lit (formulaire
admin, profil, fiche annuaire, journal d'intervention, champs de recherche, et
les messages d'erreur du backend).

**Aucune migration** : la colonne reste `account.matricule`. Cette table est
**partagée avec la plateforme centrale**, dont le code pourrait lire la colonne,
et le matricule sert en outre d'identifiant de connexion (`/auth/login` accepte
email **ou** matricule, résolu localement par `find_by_matricule`). Décision
explicite de l'utilisateur après alerte.

### Statut d'intervenant
`titulaire` | `prestataire` | `stagiaire` (le PV papier n'offre que les deux
premiers ; le troisième est une demande métier). Qualifie l'**intervenant**,
jamais le demandeur.

Stocké dans `account.infos` — **pas de colonne** : même raison que ci-dessus, on
ne modifie pas le schéma de la table partagée. `ServiceAccount._fold_intervenant_status()`
**fusionne** la valeur dans `infos` sans jamais le substituer, pour ne pas
effacer ce qu'il porte déjà (indicateur d'e-mail de bienvenue).

Distinct de `is_edg_employee`, booléen déduit de la présence d'un badge : un
stagiaire EDG peut avoir un badge sans être titulaire. Les deux coexistent.

### Figeage (comme le reste)
`_actor_identity_snapshot()` capture désormais `actor_status` en plus de
`actor_matricule` : un stagiaire devenu titulaire ne réécrit pas ses anciens PV.
Le nom complet (`intervention_actor_name`) était déjà figé — il sert de **repli
quand l'intervenant n'a pas de badge** (prestataire, stagiaire), pour que la case
du PV ne reste jamais vide sur un document destiné à être signé.

### Fiabilisation — deux tests réparés (cause réelle identifiée)
`test_directions_units_hierarchy` et `test_user_org_assignment` présupposaient
qu'une direction préexiste. Or **rien ne la crée** :
- `SEED_ORG_STRUCTURE=False` ne sème aucune structure organisationnelle ;
- `/directions/` lit la table **Organigram** et classe via `_kind_from_org`, qui
  privilégie le **préfixe du libellé** sur la règle « racine = direction » ;
- les unités créées par les autres tests sont libellées « Unité Test N » → le
  préfixe « unité » les classe en *units*, jamais en *directions*.

Ces tests ne passaient donc qu'au gré de l'ordre d'exécution. Vérifié : ils
échouaient **aussi en isolation, sur du code sans aucune modification**.

Correction : ils créent désormais la direction dont ils ont besoin
(`POST /directions/`) si aucune n'existe. Ils passent maintenant en isolation,
ce qui n'avait jamais été le cas.

**Méthode ayant permis d'exclure le code applicatif** : annulation manuelle de
chaque groupe de modifications, séparément — groupe « comptes » annulé → 59 ;
`actor_status` annulé → 59. Si l'un avait été en cause, l'annuler aurait ramené
57. Aucun ne le fait. (Une tentative par `git stash` a de nouveau donné une sonde
inexploitable — 113 échecs — ces fichiers portant des modifications non
commitées antérieures : **ne pas réessayer cette voie**.)

### Vérification
Suite `tests/api` : **57 échecs, ensemble strictement identique à la référence**,
`comm` vide dans les deux sens — et **402 tests passés contre 371** à l'origine
(les 31 nouveaux tests des blocs 1 et 2). `npx tsc --noEmit` : aucune erreur
nouvelle. `npx vitest run` : 124 au vert. `npx vite build` : réussi.

---

## Session 2026-09-23 (suite) — Tâche 3.1 : génération du PV d'intervention

### Ce qui est livré
`GET /requests/{id}/pv` produit le **PV au format officiel EDG/PS-GSI/PV-01
version 03**, en PDF paysage A4 : cartouche réglementaire (logo, processus,
réf/version/date), bandeau « RÉSERVÉE À L'INFORMATIQUE », puis les blocs
Réception, Affectation, Traitement, Émargement et Appréciations du Requérant.

Nouveau service `api/services/ServicePvIntervention.py`. Il **dérive** l'existant
(`pdf_safe_text`, `get_logo_path`, `build_response`) plutôt que d'ajouter un
second moteur d'export ; seule la mise en page du formulaire lui est propre.

### Aucune donnée nouvelle
Tout provient de ce que les blocs 1 et 2 ont figé : organisation traitante
(tâche 1.3), constat terrain (2.1), horaires et identité de l'intervenant
(BR-TRACE-001), `work_done`/`solution`/`recommendations` (2.2), appréciation CSAT
(3.2). Le PV est une **mise en forme**, pas une collecte.

| Champ du formulaire | Source |
| --- | --- |
| Mail ☐ / Téléphone ☐ | `request_source` (`email` / `telephone`) |
| Service (Réception) | `requester_service_label` figé |
| Responsable + Badge | `receiver_name` / `receiver_badge` figés à la qualification |
| N° Fiche | `ref` |
| Département / Service (Affectation) | `handler_*_label` figés |
| Lieu | `location_label` |
| Titulaire / Prestataire / Stagiaire | `actor_status` figé |
| Badge (intervenant) | `actor_matricule` figé, **à défaut le nom complet** |
| Délai d'exécution | `sla_hours` |
| Dates / heures début et fin | `interventions[].started_at` / `ended_at` |
| Traitement | constat + travail réalisé + solution + recommandations |
| Appréciations du Requérant | note CSAT + commentaire |

### Signature — zones laissées vierges
Le formulaire porte trois emplacements de signature et une ligne d'émargement,
alors qu'aucun mécanisme de signature n'existe (décision du 2026-09-22). Sans
contradiction : son pied de page dit « Avant utilisation d'un **document
papier** ». Les zones sont rendues **vides**, le PV se signe au stylo.

### Confidentialité
`proposed_solution` (tâche 1.3) n'y figure **jamais** : le PV est remis au
demandeur — c'est lui qui valide le dépannage et signe (tâche 3.2) — et cette
piste reste interne. Un test vérifie que la chaîne n'apparaît pas dans les
octets du PDF.

L'accès au PV est celui du ticket (`_resolve_access`), **demandeur inclus**.

### Défaut corrigé au passage (BR-DISTRIBUTION-001)
`_exit_distribution()` jetait silencieusement le `opening_meta` renvoyé par
`_open_intervention()` : les interventions nées d'une **distribution** — c'est-à-dire
le chemin NOMINAL de la procédure — n'avaient donc **aucune identité figée**
(ni nom, ni badge, ni statut, ni organisation), ni au journal d'interventions ni
sur le PV. La méta est désormais jointe à l'événement d'ouverture via un
paramètre `extra_infos` de `_record_distribution_event()`, comme sur les chemins
`assign()` et `transmit_treatment()`.

Découvert parce qu'un test du PV exigeait un statut d'intervenant figé et
recevait `None`.

### Frontend
Bouton « PV d'intervention » dans l'**onglet Traitement** (règle : les actions de
traitement s'y trouvent). Disponible aussi sur un ticket **terminé** — c'est
justement après la résolution que le PV s'imprime — et au **demandeur** une fois
le ticket résolu, pour la tâche 3.2.

### Vérification
`backend/tests/api/test_pv_intervention.py` — **8 tests au vert** : PDF valide,
nom de fichier porteur de la référence, PV disponible avant résolution (vierge
mais exploitable), **absence de la solution proposée dans les octets du PDF**,
accès du demandeur, refus d'un tiers sans accès au ticket, statut d'intervenant
figé malgré une mutation du compte, responsable de réception figé.

Rendu **contrôlé visuellement** sur un exemplaire de démonstration (un
chevauchement de libellé dans la case « Appréciations du Requérant » a été
corrigé).

Suite `tests/api` : **57 / 57, ensembles identiques**, `comm` vide dans les deux
sens. `npx tsc --noEmit` : aucune erreur nouvelle. `npx vitest run` : 124 au
vert. `npx vite build` : réussi.

---

## Session 2026-09-23 (suite) — Tâches 3.3 et 3.4 : circuit du PV et TSI

### 3.3 — Soumettre le PV au chef de division
`POST /requests/{id}/pv/submit`. **Le destinataire n'est pas choisi** : c'est le
chef de division qui a réparti le ticket (`distributor_id`, posé à la tâche 1.4).

Gardes : l'intervenant qui a traité (`assignee_id`), et traitement terminé
(`resolved`/`closed`) — la tâche 3.3 suit la 2.2. `assert_is_current_handler`
**ne convenait pas** ici : sa liste de statuts autorisés est
`COLLABORATIVE_STATUSES`, or le PV se soumet sur un statut terminal. D'où
`_assert_is_last_handler()`, même règle de fond (c'est l'intervenant, pas un
rôle), statuts différents.

Pièces jointes facultatives : le **PV signé et scanné**, la signature étant
manuscrite — c'est ainsi qu'elle entre dans le système.

### 3.4 — Enregistrer et archiver le PV
`POST /requests/{id}/pv/archive`, réservé au chef de division **qui a réparti ce
ticket** (l'admin garde son bypass). Refus si le PV n'a pas été soumis : la 3.3
précède la 3.4.

### TSI — Tableau de Suivi des Interventions
`GET /requests/pv-tracking` + page `/app/pv-tracking` (menu « Suivi des
interventions », chef de division et admin).

**À ne pas confondre avec `GET /reports/interventions`**, qui agrège des
statistiques : le TSI est un suivi **ligne à ligne** — réf, objet, intervenant
et badge, statut du ticket, dates de soumission et d'archivage, étape du PV
(*En cours* → *À archiver* → *Archivé*).

Périmètre : `distributor_id` **sans** la condition `assignee_id IS NULL`, à la
différence de la file Distribution. Le TSI suit donc le ticket **après** sa
sortie de la file, jusqu'à l'archivage — un test le vérifie explicitement.

### Deux pièges rencontrés
**Ordre de déclaration des routes.** `GET /requests/pv-tracking` était déclaré
après `GET /requests/{id}` : FastAPI résout dans l'ordre, l'URL était donc
capturée comme un identifiant. La route a été déplacée avant, près de
`/distribution`.

**Relations volontairement non chargées.** La requête du TSI utilise
`_SKIP_UNUSED_RELS` (performance), donc `interventions` n'y est pas reconstruit
et le tableau ne pouvait nommer personne. Le nom et le badge de l'intervenant
courant sont désormais recopiés dans `request.infos` à l'ouverture de
l'intervention — même patron que le pointeur `current_intervention_id` déjà en
place.

### État du PV
Stocké dans `request.infos` (`pv_submitted_at/by`, `pv_archived_at/by`) et
journalisé par deux événements `workflow_detail` : `pv_submitted`, `pv_archived`.
**Aucune table, aucune colonne, aucune migration** — le PV est un document
dérivé du ticket, seul son circuit est suivi.

### Vérification
`test_pv_intervention.py` passe à **16 tests**, dont : soumission refusée avant
résolution, refus pour un autre intervenant, archivage refusé sans soumission
préalable, refus pour un **autre** chef de division, TSI refusé au technicien, et
le ticket présent au TSI mais **absent** de la file Distribution.

Suite `tests/api` : **57 / 57, ensembles identiques**. `npx tsc --noEmit` :
aucune erreur nouvelle. `npx vitest run` : 124 au vert. `npx vite build` :
réussi.


---

## Session 2026-09-23 (fin) — Tâche 3.2 rattachée au circuit du PV

### Ce qui change
La tâche 3.2 (« valider le dépannage », par le demandeur) existait
fonctionnellement — confirmation de résolution + CSAT — mais **hors du circuit du
PV**. Elle y est désormais une étape à part entière :

`3.1 établir → 3.2 valider (demandeur) → 3.3 soumettre (technicien) → 3.4 archiver (CDS)`

### Pas de seconde validation
La validation n'est **pas** un nouveau geste : c'est la confirmation de résolution
que le demandeur donne déjà avec son appréciation. `ServiceAppreciation` appelle
`RequestService.record_pv_validation()` à la création **et** à la mise à jour de
l'appréciation. Créer un second mécanisme aurait produit deux validations
concurrentes pour le même fait.

### Contestation = réinitialisation
`resolved_confirmed=False` rouvre déjà le ticket. Le circuit du PV est alors
**entièrement effacé** (`pv_validated_at`, `pv_submitted_at`, `pv_archived_at`) :
le PV de l'intervention contestée ne vaut plus, et l'intervention suivante devra
produire le sien.

### Séquencement appliqué
`pv_submit()` refuse désormais tant que `pv_validated_at` est absent : on ne
soumet pas au chef de division un PV que le demandeur n'a pas validé. Côté
écran, le bouton « Soumettre le PV » est remplacé par un message d'attente
explicite, et le TSI gagne une colonne « Validé » et une étape « À soumettre ».

### Vérification
`test_pv_intervention.py` passe à **21 tests**, dont : la validation alimente le
circuit, la soumission est refusée sans elle puis acceptée après, la contestation
réinitialise le circuit, et **les cinq étapes du parcours apparaissent au
journal** (`field_check`, `treatment_completed`, `pv_validated`, `pv_submitted`,
`pv_archived`).

Quatre tests de 3.3/3.4 écrits juste avant ont dû être mis à jour : ils
soumettaient sans validation, ce que la règle refuse maintenant. C'est le
contrat métier qui a changé.

Suite `tests/api` : **57 / 57, ensembles identiques**. `npx tsc --noEmit` :
aucune erreur nouvelle. `npx vitest run` : 124 au vert. `npx vite build` :
réussi.

### État du bloc 3
| Tâche | État |
| --- | --- |
| 3.1 Établir le PV | ✅ |
| 3.2 Valider le dépannage | ✅ |
| 3.3 Soumettre au chef de division | ✅ |
| 3.4 Enregistrer, archiver, TSI | ✅ |

---

## Session 2026-09-24 — Retrait des Annonces, de la Base de connaissances et du référentiel Statuts de compte

Décision produit : trois éléments sortent du périmètre de l'application. Le
déclencheur est le panneau **Référentiels** de l'espace admin, dont cinq entrées
sur sept devaient disparaître ; l'analyse a montré que deux d'entre elles ne
pouvaient pas être retirées sans démonter les fonctionnalités qu'elles
alimentaient.

### Périmètre exact

| Élément retiré | Nature |
| --- | --- |
| Annonces institutionnelles | Fonctionnalité complète (front + back + SSE) |
| Base de connaissances | Fonctionnalité complète (front + back) |
| Référentiel *Statuts de compte* | Table de référence seule |

**La colonne `account.account_status` est CONSERVÉE.** C'est un `VARCHAR(50)`
libre, alimenté par le code (`active`, `inactive`…), et non une clé étrangère.
Seule disparaît la validation référentielle qui vérifiait ces valeurs
(`check_ref_code` dans `ServiceAccount.create()` et `update()`).

### Base de données — migration `026_remove_announcements_knowledge`

Huit tables supprimées, dans cet ordre (des porteuses vers les référentiels,
`announcement` portant trois clés étrangères et `announcement_target_role`
référençant `announcement`) :

```
announcement_target_role · announcement · announcement_category
announcement_priority · announcement_status
knowledge_article · knowledge_category
account_status
```

**Aucune donnée métier perdue** : `announcement` et `knowledge_article` étaient
vides ; les six autres tables ne contenaient que des lignes de référence semées
au démarrage. `downgrade()` recrée la structure mais évidemment pas le contenu.

La migration `025` (ajout de `request.proposed_solution`), restée en attente,
a été appliquée au passage — la base était à `024` alors que `ModelRequest`
déclarait déjà la colonne, ce qui aurait fait échouer toute requête ORM sur
`request` dès qu'un ticket aurait existé.

### Backend — 29 fichiers supprimés

- **Modèles (8)** : `ModelAccountStatus`, `ModelKnowledgeCategory`,
  `ModelKnowledgeArticle`, `ModelAnnouncement`, `ModelAnnouncementCategory`,
  `ModelAnnouncementPriority`, `ModelAnnouncementStatus`,
  `ModelAnnouncementTargetRole`
- **Repositories (8)**, **Schémas (8)** : symétriques des modèles
- **Services (2)** : `ServiceAnnouncement`, `ServiceKnowledgeArticle`
- **Routes (3)** : `RouteAnnouncement`, `RouteKnowledge`, `RouteKnowledgeArticle`

### Backend — fichiers modifiés

| Fichier | Modification |
| --- | --- |
| `main.py` | Désenregistrement de 4 routeurs |
| `routes/__init__.py`, `models/`, `repositories/`, `schemas/`, `services/` | Barrel exports nettoyés |
| `RouteReferences.py` | 5 sections d'endpoints CRUD supprimées (`/account-statuses`, `/knowledge-categories`, `/announcement-*`) + entrées du chargement global |
| `RouteAdminConfig.py` | `_REF_SERVICE_MAP` passe de 7 à 2 entrées |
| `ServiceReferences.py` | 5 classes de service supprimées |
| `ServiceAccount.py` | Validation référentielle `account_status` retirée (2 appels) |
| `seed_references.py` | 5 blocs de données + 5 appels `_seed()` retirés |
| `core/rbac.py` | Permissions `view/manage_knowledge` et `view/manage_announcements` supprimées. **`_PUBLIC` devient un ensemble vide** — c'étaient ses deux seules permissions |
| `core/error_codes.py` | `ANNOUNCEMENT_NOT_FOUND` retiré |
| `core/middleware.py`, `repositories/base_repository.py` | Entrées de libellés retirées |
| `RouteNotification.py`, `RepositoryNotification.py` | Filtre `nature` : valeur `annonce` renommée `systeme`. **Le critère est inchangé** (`request_id IS NULL`), seul le vocabulaire suit le retrait |

### Frontend — 5 fichiers supprimés

`routes/app.knowledge.tsx`, `routes/app.admin.knowledge.tsx`,
`routes/knowledge.tsx` (public), `routes/help.tsx`, `lib/api/knowledge.ts`.

`/help` n'était qu'une redirection vers `/knowledge` : sans cible, la route n'a
plus d'objet. Ses trois liens dans le pied de page public (Aide, FAQ, Support)
sont retirés avec elle.

### Frontend — fichiers modifiés

| Fichier | Modification |
| --- | --- |
| `lib/api/admin-config.ts` | `REF_TABLES` passe de 7 à 2 entrées — c'est le panneau Référentiels visible par l'admin |
| `routes/app.admin.communication.tsx` | **Réécrit : 877 → 154 lignes.** Ne conserve que les réglages de canaux et d'expéditeur |
| `lib/api/communication.ts` | **292 → 69 lignes.** Annonces retirées, `communication_setting` conservé |
| `lib/mock-data.ts` | **2038 → 1638 lignes.** 20 exports retirés |
| `components/notification-panel.tsx` | **676 → 549 lignes.** Onglet « Annonces » et blocs d'alertes retirés |
| `routes/app.notifications.tsx` | Onglet et filtre par source retirés (une seule source restante) |
| `routes/app.dg.tsx` | Panneau « Annonce globale » retiré (106 lignes) |
| `routes/index.tsx` | `AnnouncementsCarousel` et ses tables de style retirés (déjà décâblé le 2026-09-22) |
| `lib/realtime/invalidation-map.ts` | 5 événements SSE `announcement.*` retirés |
| `lib/permissions.ts` | Miroir de `core/rbac.py` ; `_PUBLIC` devient vide |
| `components/app-layout.tsx`, `components/public-layout.tsx` | Entrées de navigation retirées |
| `lib/api/notifications.ts` | `source: "request" \| "announcement"` → `"request" \| "system"` |

### Vocabulaire : « annonce » → « système »

Les notifications non rattachées à un ticket étaient étiquetées « Annonce ».
Elles subsistent (elles ne venaient pas de la table `announcement` : le critère
a toujours été `request_id IS NULL`) et sont désormais étiquetées « Système ».
Renommage cohérent front et back, sans changement de comportement.

### Tests

Classes de tests des fonctionnalités retirées supprimées dans
`tests/schema_validation/` : `TestAccountStatus`, `TestAnnouncementCategory`,
`TestAnnouncementPriority`, `TestAnnouncementStatus`, `TestKnowledgeArticle`,
`TestAnnouncement`, `TestAnnouncementTargetRole`, plus 7 entrées de la liste
paramétrée de `test_01_imports.py`.

`test_total_schema_count` : seuil abaissé de 18 à 17 classes `Response`, cinq
des huit schémas supprimés en portant une.

### Écart CDC rouvert

**DG5** était enregistré comme corrigé (panneau « Annonce globale » de
`/app/dg`, vérifié le 2026-07-04). Le retrait des annonces le rouvre. Ce n'est
pas une régression subie mais une décision produit : le CDC §11.4 acte le
retrait.


---

## Session 2026-09-24 — Référentiels : édition du code et suppression logique

### Besoin
Sur `/app/admin/references`, pouvoir modifier **tout** à l'édition et disposer
d'une **suppression logique**. En pratique aucune des deux n'était accessible :
le champ `code` était verrouillé en modification, et l'archivage comme la
désactivation étaient masqués pour les valeurs « Intégré » — or elles le sont
toutes.

### Le risque mesuré, et l'arbitrage
Les **codes de statut apparaissent 101 fois comme littéraux** dans le backend
(matrice de transitions, `COLLABORATIVE_STATUSES`, `TERMINAL_STATUSES`, table
des événements, circuit du PV). Les **politiques SLA** retrouvent par ailleurs
catégories et priorités par le **texte** de leur code
(`find_policy(category, priority)`).

Renommer le code d'une valeur intégrée casserait donc le workflow **sans lever
la moindre erreur** au moment du renommage. Arbitrage retenu (option (a) de
l'utilisateur) :

| | Règle |
| --- | --- |
| **Libellé** | modifiable partout, valeurs intégrées comprises — ce n'est que de l'affichage |
| **Code d'une valeur créée** | modifiable |
| **Code d'une valeur intégrée** | **immuable**, refus explicite côté serveur |

### Le vrai changement : la protection porte sur l'USAGE
L'ancienne garde (`is_builtin` → suppression interdite) protégeait la mauvaise
chose. Un référentiel intégré que plus aucun ticket ne porte est inoffensif ;
une valeur créée à la main mais portée par des centaines de tickets ne doit pas
disparaître.

`_ReferenceGuardMixin._assert_not_in_use()` compte donc les tickets qui pointent
sur la valeur (`request_status_id`, `request_category_id`,
`priority_definition_id`) et refuse l'archivage en **disant combien**, tout en
rappelant que la **désactivation** retire la valeur des formulaires sans toucher
à l'historique.

La suppression reste **logique** (`deleted_at`), jamais physique, et la
restauration existait déjà.

### Conséquence assumée
La **désactivation** s'ouvre aussi aux valeurs intégrées : il aurait été
incohérent de pouvoir archiver une valeur intégrée sans pouvoir simplement la
désactiver, alors que la désactivation est précisément l'issue proposée quand
l'archivage est refusé.

### Implémentation
- `ServiceReferences._ReferenceGuardMixin` — une seule place pour les deux
  règles, partagée par les trois services (statuts, catégories, priorités) via
  `_USAGE_COLUMN` / `_CODE_FIELD`.
- Réécrire le **même** code n'est pas un changement (cas d'un formulaire qui
  poste tous ses champs) : le refus ne porte que sur une valeur réellement
  différente.
- Frontend : champ `code` verrouillé **uniquement** si `is_builtin`, avec une
  explication à l'écran plutôt qu'un champ grisé sans raison ; le code n'est pas
  renvoyé pour une valeur intégrée ; l'erreur du backend est affichée telle
  quelle (elle porte le décompte et la solution de repli).

### Vérification
`backend/tests/api/test_reference_edition.py` — **9 tests au vert** : libellé
modifiable sur intégrée comme sur créée, code refusé sur intégrée, accepté sur
créée, réécriture du même code tolérée, même règle pour les catégories,
archivage d'une valeur intégrée **inutilisée** accepté, archivage d'une valeur
**utilisée** refusé avec le bon décompte et la mention de la désactivation,
restauration.

Suite `tests/api` : **57 / 57, ensembles identiques**. `npx tsc --noEmit` :
aucune erreur nouvelle. `npx vitest run` : 124 au vert. `npx vite build` :
réussi.

---

## Session 2026-09-24 (suite) — Retrait de `communication_setting`

Décision produit, prise après analyse des inconvénients. **`activity_log` a été
explicitement conservée** : elle est le seul mécanisme de journalisation des
connexions de toute la base (`ActiveSession` et `security_incident` n'existent
plus), et le CDC l'exige aux §10.5 et §13.

### Pourquoi cette table pesait peu

Singleton (une ligne max), **vide au moment du retrait**. Sur ses neuf colonnes
métier, trois seulement étaient lues par le code :

| Colonne | Consommée | Où |
| --- | --- | --- |
| `email_on` | oui | `NotificationEmitter` (2 gardes) |
| `sms_on` | oui | `ServiceSMS` |
| `sender_sms` | oui | `ServiceSMS`, avec repli sur `SMS_SENDER` |
| `sender_email`, `reply_to` | **non** | l'expéditeur vient de `SMTP_USER` (`.env`) |
| `internal_notif_on`, `banner_on` | **non** | togglables dans l'UI, sans effet |
| `whatsapp_on`, `push_mobile_on` | **non** | marqués « Bientôt disponible » |

### Comportement d'envoi : inchangé

Les deux gardes retirées étaient en *fail-open* :

```python
cs = cs_row.scalar_one_or_none()
if cs is None or cs.email_on:      # table vide -> on envoie
```

Le bloc d'envoi a été **déroulé** (désindenté de 4 espaces) et non supprimé :
les mails et SMS partent exactement comme avant. Même logique dans `ServiceSMS`,
où le repli `env.SMS_SENDER` existait déjà.

⚠️ **Conséquence assumée** : il n'y a plus de coupe-circuit en base. Couper les
envois passe désormais par `.env` — `SMTP_HOST` vide pour les mails,
`SMS_GATEWAY_URL` vide pour les SMS — donc par un redémarrage. En production
(4 workers Gunicorn), c'est un redéploiement et non un clic.

### Migration `027_remove_communication_setting`

Une table supprimée, base passée de 18 à **17 tables**. Aucune donnée perdue.
`downgrade()` recrée la structure. Aucune clé étrangère entrante : la table
pointait vers `account` (`updated_by`), rien ne pointait vers elle.

### Backend — 5 fichiers supprimés

`ModelCommunicationSetting`, `RepositoryCommunicationSetting`,
`SchemaCommunicationSetting`, `ServiceCommunicationSetting`,
`RouteCommunicationSetting`.

### Backend — fichiers modifiés

| Fichier | Modification |
| --- | --- |
| `NotificationEmitter.py` | 2 gardes `email_on` déroulées, envoi préservé |
| `ServiceSMS.py` | Garde `sms_on` et surcharge `sender_sms` retirées. **Signature changée** : `send_sms(session, *, to, message)` → `send_sms(*, to, message)` — `session` ne servait qu'à lire le réglage. Un seul appelant, mis à jour |
| `main.py`, les 5 `__init__.py` | Routeur désenregistré, barrels nettoyés |
| `core/rbac.py` | Permission `MANAGE_COMMUNICATION` retirée |
| `core/middleware.py`, `base_repository.py` | Libellés retirés |
| `configs/Environment.py` | Commentaire de `SMS_SENDER` corrigé (ne surcharge plus rien) |

Routes : 317 → **315**.

### Frontend — 2 fichiers supprimés

`routes/app.admin.communication.tsx` (154 lignes) et `lib/api/communication.ts`
(69 lignes). L'écran n'était lié à aucun menu : ni barre latérale, ni tuile
d'accueil. Sa suppression ne casse aucun lien.

`lib/mock-data.ts` perd 3 exports (`CommunicationChannelSettings`,
`CommunicationSettings`, `defaultCommunicationSettings`) ; `lib/permissions.ts`
perd `manage_communication`.

### Tests

- `TestCommunicationSetting` supprimée de `test_07_transversal_and_communication.py`
- Tuple `SchemaCommunicationSetting` retiré de `test_01_imports.py`
- `test_total_schema_count` : seuil 17 → **16** (`CommunicationSettingResponse` disparaît)

Contrôle de non-régression sur `schema_validation` : **0 nouvel échec**
(33 → 26, les 7 disparus étant les tests des entités retirées).

---

## Session 2026-09-25 — Démarrage bloqué par le seed, et cache des scopes centraux

### 1. Seed des références vs archivage admin (démarrage impossible)

Le démarrage échouait sur `IntegrityError 1062` : trois catégories archivées par
l'admin (`facturation`, `compteur`, `paie`) occupaient toujours leur `code` dans
l'index unique — lequel ignore `deleted_at` — alors que `get_or_create` les
cherchait avec le filtre `deleted_at IS NULL`, ne les trouvait pas, et lançait un
INSERT. `Application startup failed. Exiting.` à chaque reload.

| Fichier | Modification |
| --- | --- |
| `repositories/base_repository.py` | `get_or_create(..., include_deleted=False)` — nouveau paramètre, défaut inchangé donc aucun appel existant n'est affecté |
| `seed_references.py` | `_seed()` et la boucle des politiques SLA passent `include_deleted=True`. Une référence archivée est reconnue comme existante et **laissée archivée** : l'archivage reste une décision admin |
| `services/ServiceReferences.py` | `_ReferenceGuardMixin._create_or_revive()`, branché sur les `create()` des 3 référentiels. Recréer une valeur archivée la **restaure** et lui applique les données soumises, au lieu d'échouer en 1062 sur une ligne invisible dans l'UI. Un code porté par une valeur active reste un conflit explicite |

`uk_sla_cat_prio` (unique composite `category`+`priority`) portait le même piège,
traité en même temps bien qu'aucune ligne n'y soit archivée aujourd'hui.

### 2. Cache des scopes/groupes centraux

Chaque requête protégée validait le bearer token par **deux appels HTTP** à la
plateforme centrale (`get_scopes` + `get_groups`), sans cache — mesuré à ~1,5 s
par appel, ~12 s à froid après un redémarrage. Un écran comme la création
d'utilisateur, qui émet 5 requêtes (dont les listes en cascade direction →
département → service), payait **10 allers-retours** et pouvait dépasser le
timeout de 15 s d'`apiFetch` : les listes revenaient vides, sans message.

| Fichier | Modification |
| --- | --- |
| `configs/Environment.py` | `CENTRAL_AUTH_CACHE_TTL: int = 45` (secondes ; 0 désactive et restaure le comportement historique) |
| `dependencies.py` | Cache mémoire par processus, clé = SHA-256 du token (jamais conservé en clair) ; verrou par token contre le stampede ; `asyncio.gather` sur les deux appels ; sweep des entrées expirées + garde-fou à 512 entrées ; `invalidate_central_auth_cache(token=None)` |
| `routes/RouteAuth.py` | `logout` purge l'entrée du token — sinon il resterait accepté jusqu'à expiration de son entrée |

Seuls les succès sont mis en cache : ni une erreur d'auth ni une panne du central
ne sont figées. Le **rôle local et le compte restent relus en DB à chaque
requête** (`find_by_central_user_id`) — le cache ne fige que la validation du
token et les groupes centraux, la règle « le rôle vient toujours de la DB » est
intacte.

Mesure sur double instrumenté (latence centrale simulée à 0,5 s/appel) :

| Scénario | Avant | Après |
| --- | --- | --- |
| 5 requêtes parallèles, cache froid | 10 appels, ~5 s | **2 appels, 0,54 s** |
| Requête suivante, cache chaud | 2 appels | **0 appel, 0,000 s** |
| Après `logout` | — | nouvel appel (invalidation vérifiée) |
| `CENTRAL_AUTH_CACHE_TTL=0` | — | 2 appels par requête (historique) |

Contrepartie assumée : une révocation ou un changement de groupe côté central met
jusqu'à `CENTRAL_AUTH_CACHE_TTL` secondes à être vu, d'où une valeur basse. En
production (4 workers gunicorn) chaque worker a son cache : au pire un appel par
worker et par TTL. Un cache partagé passerait par Redis, comme la blacklist.

### Défaut connu, non corrigé

La plateforme centrale répond **422** sur `/v1/auth/login` quand le mot de passe
est trop court. Cette réponse n'est pas traduite : `HTTPStatusError` remonte
jusqu'au `ResponseWrapperMiddleware` et l'utilisateur reçoit une **500** au lieu
d'un message de validation. À traiter dans `central_auth.central_login()`.

---

## Session 2026-09-25 (suite) — Connexions centrales : cause des 503 intermittents

### Symptôme rapporté

« Les comptes créés depuis le back-office ne peuvent pas se connecter. »

### Diagnostic

La chaîne création → connexion est **saine**. Vérifié en créant un compte de test
via `AccountService.create()` puis en tentant immédiatement la connexion :
compte créé (central_user_id attribué) et **login réussi du premier coup**.

Les comptes existants ont bien été créés côté central — le central répond `403
"Invalid email or password"` pour eux, contre `404 "User not found"` pour un
email inexistant. Ils existent donc, avec un mot de passe qui n'est pas celui
essayé.

La vraie cause des échecs est ailleurs : **chaque appel ouvrait son propre
`httpx.AsyncClient`**, donc sa propre connexion TLS. 17 sites d'appel, aucune
réutilisation. Sur une liaison lente, la poignée de main TLS se paie jusqu'à 5 s,
et un simple login en enchaîne quatre (source-token, login, scopes, groupes) :
la séquence frôlait puis dépassait `HTTP_TIMEOUT_MS` (20 s), retombant par
intermittence en `503 Service d'authentification central indisponible` — alors
que le central répondait parfaitement.

### Correctif

| Fichier | Modification |
| --- | --- |
| `core/central_auth.py` | Client `httpx.AsyncClient` **partagé** (keep-alive, 10 connexions persistantes, `keepalive_expiry=60s`), créé paresseusement sous verrou. Les 17 `async with httpx.AsyncClient(**_client_kwargs())` deviennent `async with _client()` — un context manager qui prête le client sans le fermer, donc aucune structure d'appel modifiée. `close_central_client()` pour l'arrêt |
| `main.py` | `await central_auth.close_central_client()` dans le lifespan |

### Mesures (liaison lente, même instant, même endpoint)

| Séquence de 4 appels enchaînés | Total |
| --- | --- |
| Avant — un client neuf par appel | 10,44 + 6,23 + 3,92 + 5,34 = **25,93 s** |
| Après — connexion partagée | 2,12 + 1,07 + 0,63 + 1,21 = **5,03 s** |

**Gain : 20,9 s, soit 81 %.** Sur la route complète `POST /auth/login` : 11,3 s au
premier appel (TLS à froid) puis **~2,0-2,5 s**, sans aucun 503 sur 4 tentatives
consécutives. Se cumule avec le cache des scopes/groupes de la session
précédente.

### Cohérence back-office ↔ plateforme centrale — audit

Déjà complète, aucune correction nécessaire :

| Action admin | Propagation centrale |
| --- | --- |
| Création | `create_central_account()` **avant** l'écriture locale + `activate_central_account()` si le central ne l'active pas — invariant : aucun compte local sans identité centrale |
| Modification identité | `update_central_account()` (email, téléphone, nom, prénom) |
| Changement de rôle | `add_group_membership()` + `remove_group_membership()` |
| Activation / Désactivation | `activate_central_account()` / `deactivate_central_account()` + événement SSE `account.deactivated` |
| Suppression | `delete_central_account()` puis soft-delete local |
| Réinitialisation mot de passe | `reset_central_password()` → renvoie le mot de passe par défaut à l'admin |

Les actions purement locales (disponibilité, vérification d'email, rattachement
organisationnel, matricule, poste) n'ont pas d'équivalent central : rien à
propager.

### Reste à traiter

- Le central répond **422** sur mot de passe trop court ; non traduit, remonte en
  **500**. À traiter dans `central_login()`.

---

## Session 2026-09-26 — Retrait de l'onglet « Journals » du détail d'un ticket

Demande produit : supprimer la partie journal sur un ticket. **Frontend
uniquement — aucune route, table ni donnée backend touchée.** Les événements de
timeline et les interventions continuent d'être produits et stockés ; seule leur
restitution dans cet écran disparaît.

### `frontend/src/routes/app.requests.$id.tsx`

| Modification | Détail |
| --- | --- |
| Onglets | `journal` retiré du type `DetailTab` et de `detailTabs`. Il reste **Description, Fichiers, Traitement** |
| Section supprimée | La section entière (bascule « Journal des interventions » / « Chronologie complète », bouton d'export désactivé, rendu `InterventionJournal` / `WorkflowTimeline`) |
| Onglet par défaut | Le contexte personnel ouvrait sur `journal` : bascule sur `description`. Sans ça la page s'ouvrait sans onglet actif |
| Nettoyage | États `journalView`, dérivée `journalEvents`, handler `handleTimelineAttachmentOpen` (ne servait qu'au journal), imports `WorkflowTimeline`, `InterventionJournal` et icône `GitBranch` |
| Libellé | Carte Escalade : « Escalade tracée dans le journal. » → « Ce ticket a été escaladé. » — la phrase renvoyait à un onglet désormais absent |

`components/intervention-journal.tsx` et `components/workflow-timeline.tsx` sont
**conservés** mais ne sont plus référencés nulle part (la demande portait sur
l'écran ticket, pas sur la suppression de composants).

### Vérification

- `tsc --noEmit` : **45 erreurs, identiques avant/après** — aucune ajoutée (les 10
  du fichier concernent un `queryFn` mal typé préexistant, `directions` en
  `unknown`).
- `npm run build` : **succès** en 1 min 3 s.

### Conséquence à connaître

Le détail d'un ticket n'expose plus la traçabilité (déroulé des interventions,
chronologie événementielle) — c'était le seul écran à le faire côté utilisateur.
Le journal d'audit administrateur (`/app/admin/logs`, `activity_log`) reste
intact, mais il est réservé aux admins et n'est pas organisé par ticket. À
rapprocher de `BR-TRACE-001` et du CDC §10.5/§13 si une exigence de restitution
par ticket est réaffirmée.

---

## Session 2026-09-26 — Historique des notifications : persistance et non-effaçabilité

### Symptômes rapportés

1. « Après déconnexion puis reconnexion, les historiques de notifications
   (toutes, non lues, archivées) ne reviennent pas. »
2. « Je ne vois pas les notifications dans la partie Alertes. »
3. « La notification de création d'une demande doit toujours rester — aucune
   perte après actualisation de la page. »

### Diagnostic

**(1) Collision de `queryKey` React Query.** Le badge de la cloche
(`app-layout.tsx`) et le panneau de notifications (`notification-panel.tsx`)
utilisaient la **même clé** `["notifications", meId]` pour deux requêtes
différentes — `unread=true&limit=1` pour le badge, liste complète `limit=50`
pour le panneau. React Query identifiant une requête par sa clé et non par sa
`queryFn`, le cache partagé était écrasé par le résultat tronqué du badge, qui
se monte en premier après reconnexion. Le panneau affichait alors 1 seul
élément au lieu de l'historique.

**(2) Onglet « Alertes » invisible.** L'onglet n'était ajouté au tableau `TABS`
que si `alertTabCount > 0` : il disparaissait entièrement dès qu'il n'y avait
aucune alerte, au lieu d'afficher un état vide.

**(3) Notification de création effaçable.** Elle est bien **persistée en base**
(`ServiceRequest.create` → `emit_notif`, titre « Ticket créé »), donc ce n'était
pas un défaut de persistance. Mais le panneau exposait un bouton « archiver »
applicable à n'importe quelle notification, y compris celle-là. L'archivage est
un soft-delete (`deleted_at`) qui masque la ligne de la vue active : le compte
concerné ne la retrouvait plus après rechargement.

### Correctifs

| Fichier | Modification |
| --- | --- |
| `frontend/src/components/app-layout.tsx` | Clé du badge → `["notifications", id, "badge"]` |
| `frontend/src/components/notification-panel.tsx` | Clé du panneau → `["notifications", id, "panel"]` ; onglet « Alertes » renommé **« Notifs »** et toujours affiché ; bouton d'archivage retiré |
| `frontend/src/routes/app.notifications.tsx` | Boutons d'archivage retirés (vues liste et grille) ; bouton **Restaurer** conservé dans la vue Archivés |
| `frontend/src/lib/api/notifications.ts` | `deleteNotification()` supprimée (plus aucun appelant) |
| `backend/api/routes/RouteNotification.py` | Endpoint `DELETE /notifications/{id}` **supprimé** — un DELETE sur ce chemin renvoie désormais 405 |
| `backend/api/services/ServiceNotification.py` | Méthode `delete()` supprimée (devenue inutilisée) |

L'invalidation SSE reste fonctionnelle : `invalidateQueries({ queryKey:
["notifications"] })` invalide par **préfixe**, donc couvre les nouvelles clés.

### Migration `029_restore_archived_creation_notifications`

Remet `deleted_at = NULL` sur les notifications « Ticket créé » archivées —
strictement l'équivalent de `BaseRepository.restore()`. Appliquée le
2026-09-26 : **0 ligne restaurée**, la base ne contenant aucune notification
archivée à cette date. La migration reste utile sur un environnement qui en
aurait. `downgrade()` est volontairement sans effet : la date d'archivage
d'origine est perdue, et re-archiver en masse masquerait des notifications
légitimes.

### Décision produit

L'historique des notifications d'un compte n'est **plus réductible** :
« marquer comme lu » subsiste, l'archivage disparaît de l'interface **et** du
serveur. L'onglet « Archivés » reste affiché et conserve son bouton
**Restaurer**, pour récupérer les notifications archivées avant cette décision.

---

## Session 2026-09-26 (suite) — File d'attente : notifier les chefs de service à la création

### Demande

« Dans la file d'attente, tous les rôles qui ont le menu File d'attente doivent
être notifiés directement pour leur faire savoir qu'une demande a été créée. »

### Diagnostic

Les rôles porteurs du menu « File d'attente » sont **`chief-service` et `admin`** :
déclaration frontend (`app-layout.tsx`, `roles: ["chief-service", "admin"]`) et
garde backend `_queue_manage_guard` (`RouteRequest.py`) concordent exactement.

Or à la création, `ServiceRequest.create()` n'émettait vers eux qu'un **évènement
SSE** `request.created` — éphémère, sans aucune ligne en base. Il ne sert qu'à
rafraîchir les écrans déjà ouverts. Seul le demandeur recevait une notification
persistée (« Ticket créé »). Conséquence : un chef de service déconnecté au
moment de la création n'apprenait **jamais** qu'une demande attendait sa
qualification.

### Correctif

| Fichier | Modification |
| --- | --- |
| `api/services/ServiceRequest.py` | Dans `create()`, après la notification au demandeur : `list_by_role("chief-service")` puis un seul `emit_bulk()` — titre « Nouvelle demande à qualifier », `action_url="/app/queue?tab=qualify"` (déjà reconnu par `isQualificationNotification()` côté frontend, qui redirige vers la file) |
| `api/services/NotificationEmitter.py` | `emit_bulk()` reçoit un paramètre `commit: bool = True`, symétrique de celui que `emit()` possédait déjà |
| `api/repositories/base_repository.py` | `bulk_create()` reçoit `commit: bool = True` (flush au lieu de commit), même schéma que `create()` |

**Décisions produit :** destinataires limités aux `chief-service` (l'admin voit la
file mais ne qualifie pas) ; canal **in-app + email** ; le demandeur est exclu du
fan-out s'il est lui-même chef de service, pour éviter une double notification
sur son propre ticket.

**Pourquoi le paramètre `commit`** : `emit_bulk` commitait via `bulk_create`,
alors que `create()` orchestre volontairement **un seul commit** en fin de
requête HTTP et protège le routage par un SAVEPOINT (`begin_nested()`).
L'appeler tel quel aurait commité trop tôt et changé la sémantique de rollback.
Le défaut `True` laisse tout autre appelant inchangé. `emit_bulk` n'avait
d'ailleurs aucun consommateur avant ce lot.

### Tests

4 tests ajoutés à `tests/api/test_notification_workflow.py` : le chef de service
est notifié, l'admin ne l'est pas, le demandeur chef de service n'est pas notifié
deux fois, et l'email part bien (ce dernier verrouille un chemin dont le
`try/except` avale les erreurs, donc où une panne serait invisible).

**Une régression introduite puis corrigée :**
`test_transmit_treatment.py::test_transmit_then_terminate_notifies_and_tracks_cycles`
affirmait `len(new_handler_notifs) == 1`. Le nouvel intervenant étant
`chief-service`, il reçoit désormais aussi l'alerte de création → 2 notifications.
Corrigé en filtrant par titre avant de compter, l'idiome déjà utilisé quelques
lignes plus bas pour l'émetteur. L'intention du test (exactement une notification
« Ticket transmis ») est préservée, pas affaiblie.

Échecs restants sur le périmètre touché, **tous antérieurs** : `test_queue_auto_start`
(attend 400, reçoit 405), et `test_queue_access_restriction` /
`test_queue_target_restriction` / `test_transfer_direction_notifies_new_director…`
qui portent sur les rôles `director` et `chief-departement` **supprimés le
2026-09-25** (migration 028).

---

## Session 2026-09-26 (suite) — BR-REQUESTER-NEVER-LOSES-001 : aucun compte ne perd sa demande

### Constat

Un ticket peut être invisible pour un compte qui le concerne. Testé sur
`EDG-26-00001` (demandeur id 5, assigné id 3, encore en triage) :

| Vue | Résultat avant |
| --- | --- |
| Ma boîte du chef de division (assigné) | ✅ 1 ticket |
| Ma boîte des autres comptes | ⭕ 0 — **normal**, « Ma boîte » = ce qui m'est assigné |
| Mes demandes de fatoumata (demandeur, rôle `user`) | ✅ 1 ticket |
| **Périmètre de l'unité 3** (celle de l'assigné) | ❌ **0 ticket** |

Deux mécanismes se combinaient :

1. `request.unity_id` est **NULL pendant le triage** — et c'est voulu :
   l'organisation traitante n'est figée qu'à la qualification (BR-QUALIF-ORG-001).
   Le filtrage par périmètre portant sur cette colonne, le ticket n'appartient
   alors à aucune unité.
2. Le périmètre des rôles staff est **forcé sur leur seule unité**
   (`RouteRequest.py`). Un membre du staff qui dépose une demande ne la
   retrouvait donc ni dans l'historique (scopé unité), ni dans Ma boîte — qui
   exclut volontairement les tickets dont on est le demandeur
   (BR-REQUESTER-NO-SELF-TREATMENT-001).

### Correctif — périmètre élargi

| Fichier | Modification |
| --- | --- |
| `repositories/RepositoryRequest.py` | Filtre `scope_actor_id` : le périmètre devient `unity_id IN (...) OR requester_id = moi OR assignee_id = moi` |
| `services/ServiceRequest.py` | `list_filtered(scope_actor_id=...)`, propagé aux deux branches (liste et recherche) |
| `routes/RouteRequest.py` | Les rôles `chief-service`, `technicien`, `chef-division-support` passent `scope_actor_id = actor.id` en plus de leur unité forcée |

**Aucun élargissement de droits** : demandeur et assigné sont déjà autorisés à
voir leur propre ticket. Vérifié — un compte de la même unité qui n'est ni
demandeur ni assigné continue de ne rien voir quand le ticket n'a pas d'unité :

| Compte (unité 3) | Après |
| --- | --- |
| chief-service id 2 (ni demandeur ni assigné) | 0 ticket |
| chef-division id 3 (assigné) | **1 ticket** |
| technicien id 4 (non concerné) | 0 ticket |

### Correctif — unité traitante à l'assignation directe

`assign()` chargeait déjà l'unité de l'assigné pour ses contrôles mais ne la
reportait jamais sur le ticket : une assignation directe (routage dynamique vers
un agent, sans passer par la file de qualification) laissait `unity_id` vide
durablement. Elle est désormais renseignée **uniquement si elle est encore
vide**, pour ne pas réécrire l'organisation figée à la qualification.

Le routage automatique à la création (`_apply_routing`) posait déjà `unity_id`
correctement ; la branche de repli « aucune règle → support général » laisse
volontairement la colonne vide, le ticket étant encore en triage.

### Non fait, et pourquoi

- **Le ticket `EDG-26-00001` n'a pas été corrigé rétroactivement.** Son
  `unity_id` NULL n'est pas une anomalie : il est en triage, l'unité sera
  renseignée à sa qualification. Le forcer contredirait BR-QUALIF-ORG-001.
- **L'historique (frontend) n'a pas été modifié.** Lui faire envoyer
  `requester_id` pour tous les rôles aurait été contre-productif : le backend
  bascule alors en « vue personnelle » (`is_own_view`) et court-circuite le
  scoping, si bien qu'un chef aurait **perdu** la vue de son unité. Le correctif
  backend couvre déjà le besoin sans cet effet de bord.

### Vérification

Suite complète : **60 échecs / 453 réussis**, contre 60 échecs / 449 réussis
avant — ensemble d'échecs inchangé. Les échecs examinés portent sur des rôles
supprimés et des règles d'autorisation (403/422), aucun sur le périmètre de
liste.

---

## Session 2026-09-26 (suite) — BR-NO-AUTO-HANDOVER-001 : aucune attribution sans action d'envoi

### Règle posée

Aucun niveau ne reçoit un ticket à traiter tant qu'une **action d'envoi
explicite** ne le lui a pas adressé. Seule exception : le **chef de service**
voit les tickets dans la **file d'attente**, pour les qualifier et les router.

### Ce qui violait la règle

**1. Le repli « support général ».** Faute de règle de routage correspondante,
`_apply_routing()` assignait le ticket à `AccountRepository.find_support_agent()`,
qui retourne **le premier agent actif par ordre alphabétique**, indifféremment
parmi `chief-service`, `technicien` et `chef-division-support` :

```python
filters={"role": ["chief-service", "technicien", "chef-division-support"]},
only_active=True, order_by="name", limit=1
```

C'est ainsi que le chef de division avait hérité de `EDG-26-00001`. Avec **0
règle de routage en base**, *toute* demande créée passait par ce repli.

**2. Le routage automatique par règle.** Une règle `auto_assign` assignait
directement un agent de l'unité cible (ou son chef), sans action humaine.

### Correctif — `services/ServiceRequest.py`

| Chemin | Avant | Après |
| --- | --- | --- |
| Règle de routage correspondante | `assignee_id` = agent auto ou chef d'unité, `in_triage=False`, statut `assigned` | **Oriente vers l'unité** (`unity_id`), aucun assigné, `in_triage=True`, statut `qualifying` |
| Repli (aucune règle / conflit d'intérêt) | `assignee_id` = premier agent alphabétique | `assignee_id = None`, `in_triage=True`, statut `qualifying` |
| Notification | à l'agent tiré au sort | `_notify_queue_managers()` → tous les `chief-service` + `admin`, action « Ouvrir la file d'attente » |

`matched.auto_assign` reste stocké et tracé dans l'événement de workflow, mais
n'assigne plus personne. `find_support_agent()` n'est plus appelé (conservé, non
supprimé). `_auto_assign()` / `_select_auto_assignee()` étaient déjà du code mort
avant cette session.

La création ne permet aucun contournement : `RequestCreate` / `RequestBase`
n'exposent **ni `assignee_id` ni `unity_id`**, un client ne peut donc pas
pré-assigner un ticket.

### Vérification fonctionnelle

Demande créée avec `auto_route=True`, état en base après commit :

| Champ | Valeur |
| --- | --- |
| `assignee_id` | **NULL** — aucun niveau ne l'a reçue |
| `in_triage` | 1 — elle est dans la file d'attente |
| statut | `qualifying` |

Notifications émises : `admin` et `chief-service` (« Nouveau ticket à
qualifier »). À comparer au ticket créé avant le correctif, qui notifiait — et
assignait — le `chef-division-support`.

Visibilité vérifiée après correctif :

| Vue | Résultat |
| --- | --- |
| File d'attente (chef de service + admin) | ✅ le ticket, `assignee=None` |
| Ma boîte chief-service / chef-division / technicien | ⭕ 0 ticket chacun |
| Mes demandes du demandeur | ✅ le ticket |

La file d'attente affiche bien un ticket **sans assigné** — ce cas n'avait jamais
été exercé, `list_pending_triage` ne filtrant que sur `in_triage` et les statuts
qualifiables, il fonctionne tel quel.

### Donnée corrigée

`EDG-26-00001`, attribué au chef de division sans action d'envoi : `assignee_id`
remis à NULL, `in_triage=1`. La raison est tracée dans `request.infos`
(`handover_reverted`, avec l'assigné précédent). Le ticket de diagnostic
`EDG-26-00002` a été archivé (soft-delete).

### Vérification technique

Suite lancée **fichier par fichier** (le run groupé plante désormais sur le bug
d'environnement `INTERNALERROR: AST constructor recursion depth mismatch`) :
**397 réussis / 62 échecs**. Non directement comparable aux 60 du run groupé —
ces tests dépendent de l'ordre d'exécution. Les échecs ouverts viennent tous de
causes préexistantes, aucune liée à ce changement :

- `KeyError: 'chief-departement'`, `KeyError: 'director'` → rôles supprimés
- `405 METHOD_NOT_ALLOWED` → endpoints désalignés avec les tests
- `test_homepage_slides` (14), `test_ref_validation_groupe1` (7) → modules retirés

Les fichiers couvrant la file d'attente et la qualification passent intégralement :
`test_distribution` (22), `test_reopen_queue` (11), `test_notification_workflow`
(11), `test_transmit_treatment` (13), `test_requester_no_self_treatment` (6),
`test_qualify_narrowing` (4), `test_org_identity_freeze` (6).

---

## Session 2026-09-26 (suite 2) — Sélecteur de rôle strict, onglet « Notifs », et qualification bloquante

### A. Deux correctifs sur la notification de file d'attente

**A1 — `list_by_role()` élargit silencieusement au groupe d'alias.**
`RepositoryAccount._role_filter()` transforme `chief-service` en
`{chief-service, technicien, chef-division-support}`. Le fan-out introduit plus
tôt dans la journée notifiait donc les trois rôles, alors que la décision produit
était « chefs de service seulement ». Les tests ne l'avaient pas vu : ils
vérifiaient l'inclusion du chef de service et l'exclusion de l'admin, or l'admin
est hors du groupe — angle mort exact.

Ajout de `list_by_role_strict()`, qui filtre sur le rôle **exact** sans passer par
`_role_filter`. Utilisé par le fan-out et par `find_support_agent()`. Un test
vérifie désormais explicitement que technicien et chef de division ne sont pas
notifiés.

**A2 — `find_support_agent()` désignait un traitant incapable de qualifier.**
Elle retournait le premier compte actif **par ordre alphabétique** parmi les trois
rôles du groupe. Sur les données réelles, `'CDD'` (chef de division) passait avant
`'CDS'` (chef de service) : le ticket en triage était imputé à quelqu'un qui n'a
pas accès à la File d'attente (garde `_queue_manage_guard`), donc incapable de le
qualifier — ticket bloqué. Désormais strictement `chief-service`.

**Diagnostic d'un faux positif au passage.** Une demande créée pendant la session
n'avait aucune notification, pas même celle du demandeur. Cause : le serveur de
développement était figé en plein rechargement (piège `__pycache__` documenté dans
`CLAUDE.md`). Ses écritures de notifications étaient perdues, tandis que les
événements de workflow, qui commitent indépendamment, survivaient — d'où une
demande en base sans notification. Le code n'était pas en cause : vérifié en
appelant `emit`, `emit_bulk` puis `create()` complet sur le MySQL réel.

### B. Onglet « Notifs » — filtre élargi

Le filtre ne retenait que `type === "warning"`, SLA, escalades et résolutions. Or
« Nouvelle demande à qualifier » et « Ticket à qualifier » sont de type `info` :
elles n'apparaissaient jamais dans l'onglet. Ajout du critère `qualifier`.

**Bug de navigation corrigé** : dans cet onglet, le clic sur la ligne gérait la
redirection vers la file, mais le bouton « Voir » appelait directement
`openTicketFromNotification()` — mauvaise destination pour une notification de
qualification. La logique correcte existait dans `handleClick()`, que l'onglet
dupliquait en ligne ; c'est cette duplication qui avait divergé. Doublon supprimé,
et le libellé devient « Qualifier » pour ces notifications.

⚠️ Ce filtre repose sur une **correspondance de texte dans le titre**, mécanisme
préexistant et fragile : un libellé modifié côté backend fait disparaître la
notification de l'onglet sans erreur. Le robuste serait une colonne de type
d'événement sur `notification` — chantier distinct, non engagé.

### C. Qualification bloquante dans la File d'attente

| Champ | Avant — « Assigner » | Avant — « Prendre » | Après (les deux) |
| --- | --- | --- | --- |
| Catégorie | envoyée même vide | repli muet sur `"autre"` | **obligatoire** |
| Priorité | repli sur défaut | repli sur défaut | **obligatoire** |
| Solution proposée | obligatoire | facultative | **obligatoire** |
| Chef de division | obligatoire | sans objet | obligatoire pour « Assigner » seul |

Modifications dans `frontend/src/routes/app.queue.tsx` :

- `category` et `priority` s'initialisent **vides** (type `Priority | ""`) — plus
  de reprise depuis le ticket, qui rendait le contrôle vide de sens.
- Les deux replis muets (`|| "autre"`, `|| req.priority`) sont supprimés : le
  bouton reste bloqué au lieu d'inventer une valeur.
- `queueTargetLabel()` produit `nom complet.badge`, avec repli sur le nom complet
  seul quand le matricule est absent ou ne contient que des espaces.

**Badge = matricule, libellé uniquement.** La colonne `account.matricule` n'est pas
renommée : la table `account` est partagée avec la plateforme centrale et le
matricule sert d'identifiant de connexion.

Tests : `frontend/src/routes/app.queue.test.ts` (4, vitest) sur le format
d'affichage et ses replis.

⚠️ **Ces contrôles sont côté client uniquement.** Ils bloquent l'interface, pas un
appel direct à l'API : `qualify_triage()` accepte toujours une qualification sans
catégorie ni solution proposée. En faire un invariant métier suppose de le refuser
aussi côté serveur — non demandé à ce stade.

---

## Session 2026-09-26 (suite) — BR-NO-ORPHAN-TICKET-001 : plus de ticket hors file

### Symptôme

« Les chefs de service et de division ne parviennent pas à prendre un ticket pour
le traiter. »

### Diagnostic — deux causes distinctes, une seule est un défaut

**1. `EDG-26-00001` était en distribution — refus volontaire.** Le ticket avait
été imputé au chef de division (`distributor_id=3`), donc le chef de service ne
peut plus le reprendre : c'est `BR-DISTRIBUTION-001`, et le message le dit
explicitement (« Ce ticket est en cours de répartition par le chef de division
support »). Vérifié : le chef de division, lui, le prend sans problème via
`POST /{id}/distribution/take`.

**2. `EDG-26-00003` était un ticket ORPHELIN — le vrai défaut.** État en base :
`in_triage=0`, statut `new`, `assignee_id=NULL`, `unity_id=NULL`. Un tel ticket
est invisible **partout** : absent de la file d'attente (qui exige `in_triage`),
absent de toute boîte de traitement (aucun assigné), absent des vues scopées par
unité. Personne ne peut le prendre.

Cause : `in_triage` vaut **False par défaut** (`ModelRequest`), et seul
`_apply_routing()` — appelé *après* l'insertion — le passait à True. Or ce
routage est volontairement « best effort » : en cas d'échec il journalise et
poursuit. Tout échec du routage produisait donc un ticket définitivement
inaccessible.

> Transparence : ce ticket-là a été créé pendant une fenêtre d'édition de cette
> session (`_apply_routing` référençait `_notify_queue_managers` quelques minutes
> avant que la méthode soit écrite ; le serveur a rechargé entre les deux et le
> routage a levé). Le défaut de robustesse, lui, était réel et antérieur.

### Correctif — `services/ServiceRequest.py::create()`

```python
data.setdefault("in_triage", True)
```

L'état par défaut devient l'état sûr : toute demande naît **dans la file
d'attente**, et le routage ne fait plus que l'affiner. `submit_external()` posait
déjà ce défaut ; la création interne ne l'avait pas.

Vérifié en sabotant volontairement le routage (`_apply_routing` remplacé par une
exception) : le ticket ressort `in_triage=True`, statut `new` — donc visible dans
la file d'attente, `new` faisant partie des statuts qualifiables.

### Vérifications

| Scénario | Résultat |
| --- | --- |
| Chef de service prend un ticket de la file pour lui | ✅ `assignee=2`, `in_progress` |
| Chef de division prend un ticket qui lui est distribué | ✅ `assignee=3`, `in_progress` |
| Chef de service tente de reprendre un ticket en distribution | ⛔ refus explicite (voulu) |
| File d'attente | ✅ `EDG-26-00003` |
| File Distribution du chef de division | ✅ `EDG-26-00001` |

Tests : `test_distribution`, `test_reopen_queue`, `test_qualify_narrowing`,
`test_requester_no_self_treatment`, `test_queue_auto_start` → **47 réussis, 2
échecs**, les deux préexistants (`405 METHOD_NOT_ALLOWED`, désalignement
test/route constaté avant ce changement).

### Données remises en état

`EDG-26-00003` remis en file d'attente ; `EDG-26-00001` remis dans la file
Distribution du chef de division (état d'avant les tests) ; les tickets de
diagnostic `EDG-26-00002`, `EDG-26-00004`, `EDG-26-00005` archivés (soft-delete).

### Au passage — traces des erreurs 500

`core/middleware.py` : les deux journalisations d'erreur interne reçoivent
`exc_info`, donc la pile complète. La réponse HTTP reste strictement identique
(message générique, aucun détail technique). Le handler générique affichait déjà
la trace en DEBUG mais ne la voyait jamais : le middleware interceptait
l'exception avant lui.

Ce correctif a immédiatement livré la cause d'un `KeyError` cherché en vain :
`RouteRequest.py:645` (`_assert_queue_target_allowed`) → SQLAlchemy refuse de
**relire** un rôle absent de `role_enum` (`LookupError`). À noter : l'ORM
**accepte** l'écriture d'une telle valeur mais refuse sa relecture — toute valeur
de rôle non prévue en base rend donc le compte illisible.

---

## Session 2026-09-26 (suite) — BR-TRANSMIT-SCOPE-TECH-001 : périmètre de transmission du technicien

### Règle

Dans la modale « Transmettre le traitement », un **technicien** ne choisit plus
librement dans l'organisation :

- les sélecteurs **Direction, Département, Service** disparaissent ;
- la **recherche libre** devient une **liste fermée** : ses collègues techniciens
  du **même service**, plus le **responsable qui lui a confié le ticket**
  (`distributor_id` — le chef de division dans le circuit de distribution) ;
- chaque entrée s'affiche **nom · matricule · rôle** (« badge » = matricule) ;
- le **chef de service n'est pas une cible** : pour remonter, le technicien passe
  par le responsable qui lui a distribué le ticket.

Les autres rôles traitants (chef de service, chef de division, admin) gardent
l'annuaire libre et les filtres : `restricted=false`, comportement inchangé.

### Backend

| Fichier | Modification |
| --- | --- |
| `services/ServiceRequest.py` | `list_transmit_targets(id, actor)` — calcule les cibles autorisées ; renvoie `{restricted, items[]}` avec `id`, `name`, `matricule`, `role`, `is_distributor` (responsable trié en tête) |
| `services/ServiceRequest.py` | `_assert_transmit_target_in_scope()` appelée dans `transmit_treatment()` : **403** si un technicien vise hors périmètre |
| `routes/RouteRequest.py` | `GET /requests/{id}/transmit-targets` |

**Une seule source de vérité** : la même méthode alimente la liste affichée et le
contrôle serveur. Masquer des champs côté client ne protégeait rien — l'API
restait appelable directement, ce que la règle exigeait de verrouiller.

### Frontend — `routes/app.requests.$id.tsx`, `lib/api/requests.ts`

`fetchTransmitTargets()` + type `TransmitTarget`. Quand `restricted` est vrai :
les trois requêtes d'organigramme et la recherche de personnes sont désactivées
(`enabled: … && !transmitRestricted`), les blocs correspondants masqués, et un
`<select>` unique les remplace, avec un libellé d'aide et un message explicite
quand aucune cible n'est disponible.

### Vérification

Sonde HTTP temporaire (supprimée après usage), parcours réel — imputation au chef
de division puis assignation au technicien :

| Appel | Résultat |
| --- | --- |
| `GET /transmit-targets` (technicien) | `200`, `restricted: true`, liste = pair + distributeur |
| `GET /transmit-targets` (chef de service) | `200`, `restricted: false`, `items: []` |
| technicien → **chef de service** | **403** message explicite |
| technicien → technicien d'un **autre service** | **403** |
| technicien → collègue technicien du même service | `200` |
| technicien → son distributeur (chef de division) | `200` |

Au premier passage, les refus sortaient en **500** : `self.forbidden()` n'accepte
pas `error_code` (seulement `detail` et `hint`). Corrigé — et c'est la trace
d'exception ajoutée plus tôt dans cette session qui a permis de le voir
immédiatement.

Tests : `test_transmit_treatment`, `test_distribution`,
`test_requester_no_self_treatment`, `test_lot3_narrowing` → **46 réussis, 0
échec**. Frontend : `tsc` **45 erreurs, identiques avant/après** ; `npm run build`
**succès**.

---

## Session 2026-09-26 (suite 3) — Constat d'intervention : catégorie et priorité observées

### Demande

Sur le formulaire « Constat d'intervention », les champs **Catégorie observée** et
**Priorité observée** doivent être des listes déroulantes, et **obligatoires**.

### Avant

Deux `<Input>` en texte libre, placeholder « Facultatif », visibles uniquement
lorsque le technicien déclare un **écart**. Le technicien tapait ce qu'il voulait
(« urgent », « Urgent », « tres haute »), sans normalisation. Seules les
observations (`findings`) bloquaient l'enregistrement.

### Après — `frontend/src/routes/app.requests.$id.tsx`

- Les deux champs deviennent des `<Select>`. Catégories issues de
  `fetchRequestCategories()`, **le même référentiel que la qualification** du chef
  de service : l'intérêt du constat étant de comparer les deux, le vocabulaire
  doit être commun. Priorités : les quatre libellés de `priorityLabels`.
- **Le libellé lisible est stocké** (« Incident », « Haute »), pas le code : ces
  valeurs sont destinées à être lues par un humain, et le backend les conserve en
  texte libre sans les interpréter.
- Les deux deviennent **obligatoires** : astérisque, placeholder « Choisir », et
  le bouton « Enregistrer le constat » se bloque via `canSubmitFieldCheck`, qui
  remplace la condition portant sur les seules observations.
- **Correction au passage** : les valeurs n'étaient envoyées qu'au filtre
  `.trim() || undefined`. Un technicien qui les remplissait puis repassait en
  « conforme » les envoyait quand même, alors que les champs avaient disparu de
  l'écran — le constat transmis contredisait ce qu'il voyait. L'envoi est
  désormais borné à `conformity === "ecart"`.
- **Import mort supprimé** : `fetchRefTable` était importé sans aucun usage ; il
  cède la place à `fetchRequestCategories`.

### Portée

**Aucune modification backend.** `observed_category` et `observed_priority` sont
des `Optional[str]` stockés tels quels dans `workflow_detail.infos`
(`ServiceRequest.field_check`), sans validation ni clé étrangère.

Les champs restent affichés **uniquement en cas d'écart** : un constat conforme
n'a rien à caractériser. L'obligation ne vaut donc que dans ce cas.

⚠️ Comme pour la file d'attente, **le contrôle est côté client uniquement** :
`POST /requests/{id}/field-check` accepte toujours un constat sans ces champs.

⚠️ **Ces deux valeurs ne sont affichées nulle part** — ni dans le rappel du
constat, qui ne montre que la conformité et les observations, ni dans la
notification « Écart constaté sur le terrain » envoyée au chef de service, qui ne
transporte que `findings`. Les rendre sélectionnables améliore la qualité de la
donnée mais ne la rend pas visible. Signalé à l'utilisateur, non traité à sa
demande — chantier distinct.

---

## Session 2026-09-27 — Constat d'intervention : affichage dans l'onglet Description

### Demande

L'onglet **Description** doit présenter, dans cet ordre : la description laissée
par le demandeur, la solution proposée du chef de service, puis **le constat du
traitant actuel**. Et le bouton du constat doit disparaître une fois celui-ci
soumis.

### Correctif — `frontend/src/routes/app.requests.$id.tsx`

| Bloc de l'onglet Description | Source | Visibilité |
| --- | --- | --- |
| Description du ticket | le demandeur | tout le monde — déjà en place |
| Solution proposée | le chef de service | **support uniquement** — inchangé |
| Constat d'intervention | le traitant actuel | **tout le monde, demandeur inclus** — ajouté |

Le bloc du constat affiche la conformité (vert si conforme, ambre si écart), les
observations, la catégorie et la priorité observées lorsqu'elles existent, l'auteur
et l'horodatage.

**La solution proposée reste masquée au demandeur.** Ce n'est pas un choix
d'interface : l'endpoint dédié répond **403** au demandeur. Point signalé
explicitement à l'utilisateur, qui n'a pas demandé de changer cette règle.

### Le point délicat — rattachement à l'intervention

`lastFieldCheck` prenait le **dernier** constat du ticket, toutes interventions
confondues. Masquer le bouton sur cette base aurait bloqué l'intervenant suivant
après une transmission : son intervention n'a pas encore de constat, mais celui du
précédent aurait suffi à faire disparaître son bouton — et le backend lui aurait
ensuite refusé la résolution, sans qu'il comprenne pourquoi.

`lastFieldCheck` cible désormais le constat de l'**intervention en cours**, celle
qui n'a pas de date de fin, en rapprochant `infos.intervention_id`. Une seule
notion, partagée par le bandeau de rappel, le bouton et le nouveau bloc — ils ne
peuvent plus diverger.

**Repli assumé** : `ServiceRequest.field_check` lit `intervention_id` depuis
`request.infos["current_intervention_id"]`, qui peut être absent sur les tickets
antérieurs au suivi par intervention. Dans ce cas on retombe sur le dernier
constat, ce qui reste juste tant qu'il n'y a qu'une intervention.

### Bouton

`canFieldCheck && !lastFieldCheck` : le bouton disparaît dès le constat de
l'intervention en cours consigné, et réapparaît pour l'intervenant suivant. Le
libellé conditionnel « Revoir mon constat » disparaît avec lui — il n'a plus
d'objet. Le bandeau de rappel en haut de page est conservé : le technicien doit
savoir qu'il lui manque son constat **avant** de tenter une résolution.

### Vérification

Typage : 45 erreurs, strictement le même ensemble et les mêmes 9 fichiers qu'avant
(famille `fetchDirections` préexistante). Une régression a été introduite puis
corrigée en cours de route — `{(a || b) && …}` sur un `Record<string, unknown>`
produit un `unknown` non rendable par React, d'où un `Boolean(...)` explicite.
Tests : 113 au vert, avec l'unique échec préexistant du rôle `director`.

---

## Session 2026-09-27 — BR-FIELD-CHECK-REQUALIFY-001 : le constat requalifie le ticket

### Symptôme

« Quand le chef de service et le technicien qualifient le ticket (la catégorie,
la priorité) pendant le traitement, le ticket ne se met pas à jour. »

### Deux causes, une par couche

**1. Backend — les valeurs constatées n'étaient jamais appliquées.**
`ServiceRequest.field_check()` consignait `observed_category` et
`observed_priority` **uniquement dans l'événement `workflow_detail`**, sans
jamais toucher `request.category` / `request.priority`. C'était un choix
d'origine assumé (« Aucune table ni colonne : un événement du workflow_detail »),
mais il laissait la demande porter la qualification faite sur pièce : l'écart
relevé sur le terrain n'apparaissait ni dans les listes, ni dans les filtres, ni
dans les statistiques, ni dans le **calcul du SLA**, qui dépend de la priorité.

**2. Frontend — l'événement temps réel n'invalidait rien.**
`request.field_checked` était **absent** de `INVALIDATION_MAP`. Même une fois le
backend corrigé, l'écran aurait gardé les anciennes valeurs jusqu'à un
rechargement manuel.

### Correctifs

| Fichier | Modification |
| --- | --- |
| `services/ServiceRequest.py` | `field_check()` applique désormais les valeurs constatées au ticket via `_translate_codes()` (résolution des FK catégorie/priorité), **seulement si elles diffèrent** de l'existant |
| `services/ServiceRequest.py` | L'événement de workflow garde `requalified`, `previous_category`, `previous_priority` — on sait ce que le terrain a corrigé, et depuis quoi |
| `services/ServiceRequest.py` | L'événement SSE `request.field_checked` porte `requalified` + les nouvelles valeurs |
| `lib/realtime/invalidation-map.ts` | Entrée `request.field_checked` — même surface que `priority_changed` (la priorité pilote le SLA), plus `my-tickets` |

La notification au chef de service en cas d'écart (`_notify_handling_chiefs`) est
conservée : la requalification vient du terrain, il doit l'apprendre.

### Vérification

Sonde HTTP temporaire (supprimée après usage) :

| Scénario | Avant constat | Après constat | Relecture |
| --- | --- | --- | --- |
| Chef de service, écart | `panne` / `medium` | `compteur` / `critical` | ✅ persistant |
| Technicien, écart | `panne` / `low` | `incident_technique` / `high` | ✅ persistant |
| Constat **conforme**, sans valeurs | `panne` / `medium` | `panne` / `medium` | ✅ inchangé |

Le troisième cas est le garde-fou : un constat conforme ne requalifie rien, le
frontend n'envoyant ces champs qu'en cas d'écart (où il les rend obligatoires).

Tests : `test_field_check`, `test_pv_intervention`, `test_proposed_solution`,
`test_notification_workflow` → **57 réussis, 0 échec**. Frontend : `tsc` **45
erreurs, identiques avant/après** ; `npm run build` **succès**.

---

## Session 2026-09-27 (suite) — Workflow progressif du traitement (BR-TRAITEMENT-PROGRESSIF-001)

### Décision produit

Les actions de traitement ne sont plus toutes visibles en même temps. Elles
apparaissent **une par une**, dérivées du statut renvoyé par le backend :

```
Constat d'intervention  ->  Démarrer le traitement  ->  Terminer le traitement
```

« Transmettre le traitement » reste **indépendant** et visible à chaque étape :
son code, ses permissions et son comportement sont inchangés.

### BR-QUEUE-AUTO-START-001 est retirée

Une prise ou une assignation depuis la File d'attente **ne démarre plus** le
traitement : elle désigne un intervenant, et le ticket s'arrête à `assigned`.
Le traitement démarre au geste explicite du traitant, seul capable d'horodater
le vrai début et d'enregistrer le lieu.

Trois sites basculés de `in_progress` vers `assigned` dans `ServiceRequest` :
`qualify_triage`, `assign` et `_exit_distribution` (sortie de Distribution).

**Matrice de transitions élargie** : `assigned` reprend les sources que ciblait
`in_progress` (`in_progress`, `pending`, `escalated`, et `assigned` lui-même),
faute de quoi toute réassignation d'un ticket déjà en cours aurait été refusée.

### Nouveau geste — `POST /requests/{id}/start-treatment`

Corps : `{ location }` **uniquement**. La date et l'heure de début sont prises
**côté serveur**, jamais reçues du navigateur.

Gardes, dans l'ordre : lieu non vide · intervenant actuel
(`assert_is_current_handler`) · refus si déjà démarré · refus si le statut n'est
pas `assigned` · refus sans constat — via `_assert_field_check_done`, la garde
déjà utilisée par `resolve()`, réutilisée plutôt que réécrite : elle porte la
règle exacte (exigé seulement si l'intervention porte `field_check_required`,
donc du technicien) et retrouve le constat de l'intervention **en cours**.

Écritures : `location_label` (le champ que le PV imprime déjà en `place` — pas
de second champ créé), `infos.treatment_started_at`, `infos.treatment_location`,
statut `in_progress`, événement `treatment_started`.

**`resolve()` refuse désormais un ticket en `assigned`** : pas de terminaison
sans démarrage. Seul `assigned` traduit un traitement jamais démarré — un ticket
en attente ou escaladé reste résoluble, comme avant.

### Soumission automatique du PV

La soumission au chef de division est extraite dans `_record_pv_submission()`,
**partagée** par la soumission manuelle (`pv_submit`) et la soumission
automatique. Un seul endroit produit une soumission : les deux chemins ne peuvent
pas diverger.

`record_pv_validation()` l'appelle dès que le demandeur valide le dépannage.
**La tâche 3.2 de la procédure est donc préservée** : le PV n'est pas soumis
avant la validation du demandeur, contrairement à ce que demandait la
spécification initiale — point signalé et arbitré avec l'utilisateur.

Destinataire : `distributor_id`, posé à la tâche 1.4. Aucun utilisateur codé en
dur. Idempotence : on ne soumet que si `pv_submitted_at` est absent, donc un
double clic ou une validation répétée ne produit ni seconde soumission, ni
seconde notification.

Le bouton manuel « Soumettre le PV » est **conservé** : sa condition
(`pvValidated && !pvSubmitted`) le rend invisible dans le cas nominal, il ne
subsiste que comme filet de sécurité si l'automatisme échouait.

### Frontend

`app.requests.$id.tsx` dérive l'étape du statut backend — jamais d'un état local :

| Statut | Action progressive unique |
| --- | --- |
| `assigned` sans constat (technicien) | Constat d'intervention |
| `assigned` constat fait | Démarrer le traitement |
| `in_progress` · `pending` · `escalated` | Terminer le traitement |
| `resolved` · `closed` | aucune |

Les traitants non techniciens passent directement au démarrage, le constat ne
leur étant pas exigé — sans quoi ils resteraient bloqués.

Modal de démarrage : date et heure affichées **à titre indicatif seulement**
(l'horodatage fait foi côté serveur), lieu obligatoire.

Le formulaire de création n'expose **aucun champ de lieu** — vérifié :
`location_label` n'apparaît que dans les types d'API. Le demandeur ne peut donc
pas le saisir, conformément à la décision.

---

## Session 2026-09-27 (suite) — Cycle de validation par le demandeur

Après résolution, le demandeur valide ou rouvre. Son silence ne doit plus bloquer
le circuit du PV.

### État de départ

| Volet | État |
| --- | --- |
| Soumission automatique du PV à la validation | ✅ **déjà en place** (`BR-TRAITEMENT-PROGRESSIF-001`) — vérifié, non refait |
| Notification du demandeur à la résolution | ✅ déjà en place, mail **et** in-app (`NotificationEmitter.emit` envoie les deux) |
| Réouverture vers le chef de division | ❌ le ticket repartait en file d'attente |
| Validation d'office après délai | ❌ inexistante |

### BR-REOPEN-TO-DISTRIBUTOR-001 — `services/ServiceAppreciation.py`

`_reopen_request()` ne changeait que le statut. Le ticket repart désormais chez
le **chef de division qui l'avait réparti** (`distributor_id`), sans traitant
(`assignee_id=None`, `in_triage=False`) : il réapparaît dans sa file Distribution,
exactement comme à la première répartition, et c'est lui qui arbitre la suite.

Repli conservé : un ticket jamais passé par la distribution (traité directement
par le chef de service) n'a pas de distributeur — il repart alors en file
d'attente, comportement historique.

### BR-AUTO-VALIDATION-001 — `core/scheduler.py`, `services/ServiceRequest.py`

| Élément | Détail |
| --- | --- |
| `AUTO_VALIDATION_DAYS = 3` | jours **calendaires**, week-end compris |
| `_job_auto_validation()` | toutes les 6 h ; cible les tickets `resolved` depuis > 3 jours |
| `record_pv_validation(..., automatic=True)` | **même chemin** que la validation humaine — donc le PV part au chef de division exactement pareil |
| Traçabilité | `pv_validated_automatically` dans `infos`, `auto_validated` dans l'événement, `actor_role="system"` |
| Notification | message de résolution enrichi : le demandeur sait **dès la résolution** que son silence vaudra acceptation sous 3 jours |

Aucune note de satisfaction n'est créée : le système ne peut pas inventer un
ressenti, et une note fictive fausserait le CSAT. `record_pv_validation` retourne
désormais un booléen, ce qui rend le job idempotent (un ticket déjà validé n'est
pas recompté).

**Enchaînement avec l'existant** : validation d'office à J+3 (le PV part), puis
fermeture automatique à J+4 (`AUTO_CLOSE_DAYS`, inchangé). Un ticket n'est donc
jamais fermé avant que son PV ait été soumis.

### Vérification

Sonde HTTP temporaire (supprimée), parcours complet création → qualification →
distribution → constat → démarrage → résolution :

| Scénario | Résultat |
| --- | --- |
| Demandeur valide (appréciation, `resolved_confirmed=true`) | `201` → **`pv_submitted_at` présent** |
| Demandeur rouvre (`resolved_confirmed=false`) | statut `reopened`, `assignee=None`, `distributor` conservé, **ticket présent dans la file Distribution du chef de division** |
| Validation d'office | `pv_validated_at` + `pv_validated_automatically` + **`pv_submitted_at`** |

Tests : `test_pv_intervention`, `test_reopen_queue`, `test_sla_reopen`,
`test_distribution`, `test_notification_workflow`, `test_field_check` → **80
réussis, 0 échec**.

### Incidents de parcours, à connaître

1. **La sonde a d'abord appelé `_job_auto_validation()` directement.** Le job
   ouvre sa **propre session sur la base applicative** : il a donc tourné sur la
   vraie base, hors périmètre de test. Vérification faite immédiatement — aucun
   ticket réel touché (tous `in_progress`, sans `resolved_at`). Les tests d'un job
   planifié doivent passer par la logique métier, pas par le job lui-même.
2. **`start_treatment` exige que le constat soit DÉJÀ fait** (`_assert_field_check_done`),
   mais réutilise la garde de `resolve()` : le refus affiche alors
   « Démarrez le traitement avant de le terminer », message incohérent quand on
   essaie précisément de démarrer. L'ordre réel est **constat → démarrage →
   résolution**. Message à corriger (non fait ici, hors périmètre).

---

## Session 2026-09-27 (suite) — BR-TRANSMIT-HANDOVER-001 : assigner, c'est transmettre

### Règle

Un chef qui confie un ticket à quelqu'un d'autre s'en dessaisit : c'est une
transmission, et elle doit figurer dans **son** menu « Tickets transmis ».

| Qui | Depuis | Vers | Événement |
| --- | --- | --- | --- |
| Chef de service | file d'attente | chef de division | `distributed_to_division` |
| Chef de division | file Distribution | technicien | `distribution_assigned` |

### Correctif — `repositories/RepositoryRequest.py`

`list_transmitted_by_actor()` ne reconnaissait que `treatment_transmitted`. Un
chef de service ayant imputé dix tickets voyait donc un menu **vide**. Les deux
sous-requêtes (comptage et liste) filtrent désormais sur les **trois** types.

`distribution_taken` est volontairement exclu : le chef de division se l'assigne
à lui-même, il ne transmet rien.

Aucune migration : la requête lit `workflow_detail`, qui porte déjà ces
événements — le menu se remplit **rétroactivement**. `infos.actor_id` est bien
renseigné sur les deux (vérifié : `create_event()` le recopie depuis `actor_id`).

### Vérification

Sonde HTTP temporaire (supprimée) :

| Étape | chef de service | chef de division | technicien | tiers |
| --- | --- | --- | --- | --- |
| Avant | 0 | 0 | — | — |
| Après imputation au chef de division | **1** | 0 | — | — |
| Après répartition au technicien | 1 | **1** | 0 | 0 |

Chacun voit ses propres envois, et seulement les siens. Le détenteur actuel ne
voit rien (filtre `assignee_id != actor_id`, conservé).

### Effet de bord corrigé — BR-TRANSMIT-SCOPE-TECH-001

Le test `test_transmission_dynamique_reste_libre_apres_la_file_d_attente` a
révélé un **trou dans la règle posée plus tôt** : un technicien qui reçoit un
ticket par **transmission directe** (sans passer par la file Distribution) n'a
pas de `distributor_id` — il se retrouvait donc sans aucune cible hiérarchique et
ne pouvait plus faire remonter le ticket.

`list_transmit_targets()` applique désormais un repli : à défaut de distributeur,
les **chefs de division de son service**. L'intention reste la même — la sortie
vers le haut d'un technicien est le chef de division, jamais le chef de service.

### Tests

`test_transmit_treatment`, `test_distribution`, `test_queue_target_restriction`,
`test_pv_intervention`, `test_reopen_queue`, `test_field_check` → **87 réussis,
2 échecs**, tous deux préexistants (`chief-departement`, `director` : rôles
supprimés, `KeyError` sur relecture de l'enum — voir session précédente).

Note : le titre de la notification de résolution a été **rétabli** à
« Ticket résolu » — l'enrichissement sur le délai de validation reste dans le
corps du message. Le modifier cassait un test existant sans bénéfice.

---

## Session 2026-09-27 (fin) — PV d'intervention : champs vides et cases à cocher

### 1. Dates et heures vides — la cause

`_date()` et `_time()` ne formataient que des objets `datetime` :

```python
return value.strftime("%d/%m/%Y") if isinstance(value, datetime) else ""
```

Or les horodatages du PV viennent de **deux natures différentes** : des colonnes
SQL (`resolved_at` → `datetime`) et les métadonnées d'intervention reconstruites
depuis le journal (`started_at` / `ended_at` → **chaînes ISO**, un JSON ne
portant pas de type date). Le test `isinstance` échouait donc sur toute la partie
intervention, qui ressortait vide **alors que la donnée existait**.

Vérifié sur un ticket réel avant correction — `started_at='2026-09-26T19:42:02'`
en base, `start_date=''` sur le PV.

Correctif : `_as_datetime()` accepte les deux formes (`datetime.fromisoformat`,
suffixe `Z` géré), `_date()`/`_time()` s'appuient dessus.

### 2. Lieu vide — mauvaise source

Le PV lisait `req.location_label`. Depuis la décision produit du 2026-09-27, le
lieu est saisi par le **traitant au démarrage du traitement** et stocké dans
`infos.treatment_location` ; `location_label` n'est plus renseigné par personne.
Le PV lit désormais `treatment_location`, avec repli sur `location_label` pour
les tickets antérieurs.

### 3. Cases parasites devant Département et Service

`[X] Departement : …` / `[X] Service : …` — la case était cochée dès que la
valeur existait, ce qui n'a aucun sens : ce sont des informations, pas des
options. Cases retirées, les libellés restent.

### 4. Titulaire / Prestataire / Stagiaire

La mécanique était déjà correcte : le statut est figé à l'intervention
(`actor_status`, issu de `account.infos.intervenant_status`) — un stagiaire devenu
titulaire ne réécrit pas ses anciens PV. Aucune correction de code nécessaire.

**Décision produit** : si le traitant n'a aucun statut renseigné, les trois cases
restent **vides** — on ne présume pas d'un statut sur un document signé.

### Vérification

Sonde HTTP temporaire (supprimée), parcours complet avec technicien marqué
`stagiaire` et lieu saisi au démarrage :

| Champ | Avant | Après |
| --- | --- | --- |
| `place` | `''` | `Siege EDG, Kaloum` |
| `start_date` / `start_time` | `''` / `''` | `27/09/2026` / `21:35` |
| `end_date` / `end_time` | `''` / `''` | `27/09/2026` / `21:35` |
| `assignment_date` | `''` | `27/09/2026` |
| `is_stagiaire` | `False` | **`True`** (case cochée) |
| `is_titulaire` / `is_prestataire` | `False` | `False` |

Tests : `test_pv_intervention` (21), `test_field_check`, `test_trace_interventions`
→ **39 réussis, 1 échec** préexistant (rapport d'interventions réservé à l'admin,
403 attendu par le test, sans rapport avec le PV).

### Constat à traiter séparément

Sur le ticket réel `EDG-26-00006`, le lieu reste vide **même après correction** :
son journal ne contient aucun démarrage de traitement (`field_check` →
`treatment_completed` directement), donc `treatment_location` n'a jamais été
écrit. Les tickets déjà traités sans cette étape garderont un lieu vide — la
correction n'agit que sur les traitements à venir. À examiner : comment ce ticket
a pu être résolu sans passer par « Démarrer le traitement », que `resolve()` exige
pourtant.

---

## Session 2026-09-27 (fin) — PV : délai d'intervention réel

### Avant

`Delai d'execution : 48 h` — c'était le **SLA contractuel** (`request.sla_hours`),
le temps *accordé*, pas le temps *passé*. Deux tickets traités l'un en 20 minutes
et l'autre en trois jours affichaient la même valeur.

### Après

Le champ porte la **durée réelle de l'intervention** : l'écart entre la date et
l'heure de début et celles de fin, prises sur l'intervention documentée par le PV.

Unité choisie selon l'ordre de grandeur, pour rester lisible sur un document
imprimé :

| Durée | Affichage |
| --- | --- |
| moins d'une heure | `45 min` |
| heures rondes | `3 h` |
| heures et minutes | `3 h 20` |
| une journée pile | `1 j` |
| au-delà | `3 j 4 h` |

Cas dégradés : horodatage manquant ou fin antérieure au début → champ vide
(pointillés), jamais une durée négative ou fantaisiste.

Les deux horodatages peuvent venir de sources aux fuseaux différents (colonne SQL
vs chaîne ISO du journal) : ils sont ramenés au même référentiel avant
soustraction, sinon Python refuse l'opération.

`sla_hours` reste disponible dans les données collectées mais n'est plus imprimé
à cet emplacement.

### Vérification

Huit cas de formatage contrôlés, du quart d'heure aux journées multiples, plus
les deux cas dégradés. Sur le ticket réel `EDG-26-00006` :

```
Date Debut : 26/09/2026   Heure Debut : 19:42
Date Fin   : 27/09/2026   Heure Fin   : 19:44
Delai d'execution : 1 j          (SLA contractuel : 48 h)
```

Tests : `test_pv_intervention` (21), `test_trace_interventions` → **26 réussis, 1
échec** préexistant (rapport d'interventions réservé à l'admin).

---

## Session 2026-09-27 (fin) — PV : émargement électronique

### Règle

La validation faite dans l'application tient lieu de signature : un **✓** est
imprimé dans la ligne « Émargement » du PV.

| Colonne | Condition du ✓ |
| --- | --- |
| **Responsable IT** | le traitement est terminé (`resolved_at`) — même fait que la date déjà imprimée dans cette colonne |
| **Requérant** | il a validé le dépannage (`pv_validated_at`) |
| Requérant, validation **d'office** | ✓ suivi de la mention *(automatique)* |
| Sans validation | **case vide** — une case vierge reste une case à signer au stylo |

Un ticket rouvert efface la validation : la case du requérant redevient vide,
ce qui est cohérent — l'accord a été retiré.

La mention *(automatique)* distingue une validation **subie** (silence du
demandeur pendant 3 jours, `BR-AUTO-VALIDATION-001`) d'une validation **donnée**.
Sans elle, le document laisserait croire à un accord explicite du requérant sur
une pièce susceptible de servir de preuve.

### Rendu du ✓ — `services/ServicePvIntervention.py`

Le glyphe vient de **ZapfDingbats** (code `3` = U+2713), police standard du
format PDF : **aucun fichier à embarquer**. Helvetica, utilisée partout ailleurs
dans ce document, est limitée au Latin-1 et aurait rendu un « ? ».

Deux polices ne pouvant coexister dans un même `cell()`, la marque est
**surimprimée** après le tracé des cellules : ✓ en ZapfDingbats vert, mention en
Helvetica italique grise.

### Piège rencontré

Première version : les ✓ s'imprimaient dans la ligne **Date** au lieu de
**Émargement**. Cause — la surimpression laissait le curseur déplacé, or la
boucle lit `pdf.get_y()` pour positionner la ligne suivante : tout le tableau se
décalait. `_sign_mark()` restaure désormais la position du curseur en sortie.

Détecté en **rendant le PDF en image** et en le regardant, pas en lisant le code :
une vérification qui se serait limitée à « le PDF se génère » aurait laissé
passer le défaut.

### Vérification

PV réel (`EDG-26-00006`) régénéré et inspecté visuellement : ✓ verts alignés dans
la ligne Émargement des deux colonnes, dates intactes en dessous. Les trois cas
(validation humaine, validation automatique, absence de validation) rendus et
contrôlés à l'image.

Tests : `test_pv_intervention` (21), `test_field_check` → **34 réussis, 0 échec**.

---

## Session 2026-09-27 (fin) — PV : signature du traitant

Complément à l'émargement électronique : la ligne **Signature** du bloc
Affectation (celle du traitant, sous Badge) porte désormais le même **✓** dès
que l'intervention est terminée.

| État | Rendu |
| --- | --- |
| Traitement terminé | `Signature : ✓` |
| Pas encore terminé | `Signature : ______________________` (à signer au stylo) |

Même technique que l'émargement : le libellé reste en Helvetica, le ✓ est
surimprimé en ZapfDingbats. Sa position est calculée avec
`pdf.get_string_width()` sur le texte réellement écrit, plutôt qu'estimée — un
décalage codé en dur se serait désaligné au moindre changement de libellé.

### Vérification

PV réel régénéré et **inspecté à l'image** : `Signature : ✓` aligné sous
`Badge : 3333`, le reste du bloc intact (Département, Service, cases de statut,
Lieu, dates et heures, délai réel).

Tests : `test_pv_intervention` (21), `test_field_check`, `test_trace_interventions`
→ **39 réussis, 1 échec** préexistant (rapport réservé à l'admin).

### Conséquence documentaire

Le module indiquait « Ces zones sont rendues **vierges**, destinées à être signées
au stylo » (décision du 2026-09-22). Ce n'est plus vrai pour deux d'entre elles :
la signature du traitant et l'émargement portent maintenant la marque
électronique. Seule la zone du requérant reste vierge tant qu'il n'a pas validé.
Le PV n'atteste donc plus « signature à apposer » mais « validation effectuée
dans l'application » — **à confirmer côté métier** si ce document a une valeur
probante.

---

## Session 2026-09-28 — Suppression des statuts `qualified`, `pending` et `escalated`

### Contrôle préalable

| Statut | Tickets porteurs | Atteignable |
| --- | --- | --- |
| `qualified` | 0 | non (retiré du workflow le 2026-09-26) |
| `pending` | 0 | non |
| `escalated` | 0 | non |

Aucun ticket concerné : la précaution qui les gardait comme *sources* dans la
matrice de transitions n'avait plus d'objet.

### Backend

| Fichier | Modification |
| --- | --- |
| `core/ticket_actions.py` | Retirés de `ALLOWED_TRANSITIONS` (cibles **et** sources), de `COLLABORATIVE_STATUSES`, de `QUALIFIABLE_STATUSES` ; alias `escaladed` supprimé |
| `repositories/RepositoryRequest.py` | `_ACTIVE_STATUSES`, `_QUALIFIABLE_STATUSES` |
| `services/ServiceRequest.py` | Entrées mortes de `_STATUS_EVENT_MAP`, `_STATUS_LABEL_MAP` et du tableau de notifications par statut |
| `services/ServiceReport.py` | `ACTIVE_STATUS_CODES`, `BACKLOG_STATUS_CODES`, listes SQL `IN (...)`, compteurs |
| `tests/api/test_ticket_actions.py` | Les 3 statuts passent des transitions **valides** aux transitions **refusées** ; assertion sur l'alias supprimée |

`pending` a été **conservé partout où il désigne une tâche** (`TaskStatusEnum`,
`ModelTask`, `RepositoryTask`) et `pending_validation`, statut distinct, est
intact. Les compteurs d'agrégat des rapports (`escalated_total`, `pending_total`)
sont laissés en place : les retirer impose de modifier les schémas de réponse et
les écrans qui les affichent — ils renvoient désormais 0.

### Frontend

| Fichier | Modification |
| --- | --- |
| `lib/mock-data.ts` | Type `RequestStatus`, `statusOrder`, `statusLabels` ; données de démonstration réaffectées (`pending`/`escalated` → `in_progress`, `qualified` → `assigned`) |
| `lib/capabilities.ts` | `TICKET_ACTION_STATUSES` ; **action `resume` supprimée** — elle ne s'appliquait qu'à `pending`, elle était devenue inatteignable |
| `routes/app.requests.$id.tsx` | Mutation, drapeau, branches et bouton « Reprendre le traitement » |
| `routes/app.index.tsx` | Listes de statuts actifs, tuiles « En attente » |
| `routes/app.supervision.tsx` | Champ `pending` de `AgentStats`, colonne et carte « En attente » |
| `routes/app.dg.tsx` | Onglet « En validation », compteur |
| `app.my-tickets`, `app.sla-center`, `app.requests.index`, `status-badge` | Listes et libellés |

Le retrait du type TypeScript a servi de **filet** : le compilateur a listé les
45 usages restants, aucun n'a pu être oublié.

Non touché — faux positifs de recherche : `escalation-progress-bar.tsx`, dont le
`"pending"` désigne une **étape de progression** et non un statut de ticket (le
composant reste utilisé par `app.requests.index` et `track`).

### Base

Les trois lignes de `request_status` sont **archivées** (soft-delete), après
contrôle programmatique qu'aucun ticket ne les portait. Le seed ne les créait
déjà plus depuis le 2026-09-26.

### Vérification

- `tsc` : **45 erreurs, exactement le niveau d'origine** — aucune ajoutée. Passé
  par un pic à 90 (les usages révélés), ramené à 45.
- `npm run build` : succès.
- Tests : `test_ticket_actions`, `test_transmit_treatment`, `test_distribution`,
  `test_reopen_queue`, `test_pv_intervention`, `test_field_check`,
  `test_qualify_narrowing` → **146 réussis, 0 échec**. `test_ticket_actions`
  passe de 57 à **62 réussis** : l'échec préexistant `[in_progress-pending]` est
  réglé par la suppression elle-même.
- Application vérifiée après archivage : file d'attente et listes répondent
  normalement.
