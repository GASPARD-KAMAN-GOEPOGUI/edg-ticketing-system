# Changelog Codex

## 2026-07-31 - Escalade : plus de choix manuel de niveau, routage automatique vers le chef hiérarchique

Demande: "pour les escalde, on a pas besoin de faire un choix, on doit juste remplir la partie motif, puis le systeme envoie uniquement au chef hierarchie de celui qui fait le traitement uniquement" — retirer le selecteur "Niveau cible" de la modale d'escalade et faire en sorte que le systeme determine seul le destinataire (chef hierarchique de la personne qui traite le ticket), sans choix manuel.

Module: MOD-AGENT / MOD-CHIEF / MOD-DIRECTION (BR-ESCALATE-AUTO-CHIEF-001).

Fichiers modifies:
- `backend/api/routes/RouteRequest.py`
- `backend/api/services/ServiceEscalade.py`
- `frontend/src/routes/app.requests.$id.tsx`
- `frontend/src/lib/api/requests.ts`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: la modale "Escalader la demande" exigeait de choisir un "Niveau cible" (`Chef de service`/`Directeur`/`Résolution`, valeurs figées de `DEFAULT_LEVELS.slice(3, 6)`) qui n'était de toute façon jamais reliée à un vrai compte destinataire — l'API acceptait ce libellé comme simple texte et ne réassignait jamais le ticket à qui que ce soit de concret.

Correction: `EscalateBody` est réduit à `{ reason }`. La route `POST /requests/{id}/escalate` détermine désormais elle-même le destinataire : la personne qui traite le ticket (`assignee_id`, ou l'acteur lui-même si non assigné), puis remonte à son chef hiérarchique via la nouvelle fonction partagée `find_hierarchical_chief` (`ServiceEscalade.py`) — chef dans la même unité (hors le traitant lui-même, pour le cas où un chef escalade son propre ticket), sinon remontée de l'organigramme vers l'unité parente à la recherche d'un chef ou d'un directeur. Si personne n'est trouvé, 422 explicite au lieu d'une escalade dans le vide. Le ticket est réassigné au chef trouvé (même schéma que l'escalade automatique SLA) et celui-ci est notifié. `EscaladeService._find_chief` (auto-SLA) délègue maintenant à cette même fonction, ce qui corrige au passage un bug préexistant (recherche d'un role littéral `"chief"` invalide dans l'enum). Côté frontend, la modale ne demande plus que le motif ; le Select "Niveau cible", l'état `escalateLevel`, l'import `DEFAULT_LEVELS` et les imports `Select*` désormais inutilisés sont retirés.

Verification: `npx tsc --noEmit` — même baseline préexistante (12 erreurs, aucune imputable) ; `npx eslint` — même warning préexistant `unused eslint-disable directive`, zéro nouvelle erreur ; `python -m py_compile` sur les 2 fichiers backend modifiés — OK ; comparaison `git stash` des tests `TestAssignationEscaladeRoles` avant/après ce changement — mêmes 9 échecs/6 succès des deux côtés (échecs préexistants, dus à une erreur 500 sur `/assign` en environnement de test SQLite, sans lien avec cette modification).

Effet de bord assumé: `app.supervision.tsx` (bouton "Transférer au Directeur" d'une escalade déjà en cours, via `escalations.ts`) appelle le même endpoint et bénéficie désormais de la même résolution automatique — il réassigne réellement le ticket au directeur trouvé (avant, cette action ne réassignait jamais personne en pratique). Comportement jugé cohérent avec l'intitulé du bouton ; aucun changement de code sur ce fichier.

## 2026-07-29 - Onglet Traitement : boutons d'action en grille 3 colonnes (au lieu de l'empilement liste)

Demande: apres le passage en liste empilee (entree precedente), retour utilisateur explicite avec capture d'ecran montrant les 5 actions visibles empilees verticalement : "je ne veut pas voir cet empilement, je veux les affichage cote a cote en trois trois" — les actions de traitement doivent s'afficher en grille de 3 colonnes plutot qu'en pile verticale.

Module: MOD-AGENT / MOD-CHIEF / MOD-DIRECTION (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: `treatmentActionsPanel` passe du `<section>` liste plein-largeur (entree precedente) a un conteneur `<div className="grid grid-cols-1 gap-2 sm:grid-cols-3">` — 1 colonne sur mobile, 3 colonnes cote a cote a partir du breakpoint `sm`. Chaque item redevient une carte independante (`rounded-xl border p-3`, sans `border-b` puisqu'il n'y a plus d'empilement lineaire) au lieu d'une ligne separee par bordure. Aucun changement de `onClick`, de mutation ou d'etat `disabled`/`isPending` — uniquement le conteneur et l'enveloppe visuelle de chaque bouton. `requestActionsPanel` (actions demandeur + message "Aucune action disponible...") n'est pas touche, conformement au perimetre de la demande (non circle sur la capture).

Verification: `npx tsc --noEmit` — meme baseline preexistante (12 erreurs, aucune imputable a ce changement) ; `npx eslint --format json` filtre hors `prettier/prettier` — uniquement le warning `unused eslint-disable directive` deja preexistant a la ligne 720, zero nouvelle erreur.

## 2026-07-29 - Onglet Traitement : boutons d'action reformates en liste (comme requestActionsPanel)

Demande: dans l'onglet `Traitement`, afficher les boutons de traitement (Demarrer traitement, Reprendre le traitement, Escalader, Ajouter une note, Marquer resolue, etc.) sous le meme format que les actions existantes (liste de lignes pleine largeur avec icone/titre/sous-titre), au lieu de boutons "pilule" en ligne.

Module: MOD-AGENT / MOD-CHIEF / MOD-DIRECTION (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: `treatmentActionsPanel` passe d'une rangee de boutons `rounded-full` en `flex-wrap` a un `<section>` unique au format identique a `requestActionsPanel` — lignes plein-largeur empilees (icone + titre en gras + sous-titre), separees par `border-b`, meme conteneur (`rounded-[16px] border border-border/35 bg-background/25`). Chaque action (Approuver/Refuser reouverture, M'assigner, Demarrer traitement, Demander des infos, Reprendre le traitement, Escalader, Reassigner, Creer circuit, Changer priorite, Rejeter, Changer service, Transferer direction, Ajouter une note, Marquer resolue) conserve exactement le meme `onClick`, la meme mutation et le meme etat `disabled`/`isPending` qu'avant — seul le conteneur visuel change, aucune logique ni permission modifiee. Couleur par action alignee sur les conventions deja utilisees ailleurs dans l'app.

Verification: `npx tsc --noEmit` sans nouvelle erreur imputable au fichier (meme baseline preexistante, 12 erreurs) ; `npx eslint` — uniquement le warning `unused eslint-disable directive` deja preexistant, zero occurrence `prettier/prettier` et zero erreur de logique.

## 2026-07-29 - Retrait de la banniere d'en-tete "L'agent vous demande des informations complementaires"

Demande: suite au retrait du bandeau P10 (voir entree precedente), retirer aussi la banniere restante dans l'en-tete du ticket (meme message, sans bouton) — confirmee redondante par capture d'ecran, le lien `Repondre` en surbrillance du fil de commentaires suffit desormais a signaler qu'une reponse est attendue.

Module: MOD-PERSONAL, MOD-REQUEST (BR-COMMENT-LOCK-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: suppression du bloc `{needsUserResponse && (...)}` dans l'en-tete du ticket ("L'agent vous demande des informations complementaires" / "Repondez via la section commentaires ci-dessous..."). `needsUserResponse` reste utilise (uniquement) pour calculer `isAwaitingReply` sur le dernier commentaire du fil (voir entree precedente) — aucune variable devenue inutilisee.

Verification: `npx tsc --noEmit` sans nouvelle erreur imputable au fichier (baseline preexistante, 12 erreurs contre 13 precedemment — une erreur `TS2322` sur `RequesterCard`/`directions` a disparu independamment de ce changement) ; `npx eslint` — uniquement du bruit `prettier/prettier` (3649 occurrences) et le warning `unused eslint-disable directive` deja preexistant, zero erreur de logique.

## 2026-07-29 - Reponse attendue : retrait du bandeau P10, mise en evidence animee sur le fil de commentaires

Demande: supprimer le bandeau "Votre retour est attendu" + bouton `Repondre` dedie ; l'action de reponse doit passer uniquement par le lien `Repondre` deja present sous chaque commentaire, avec un fond vert anime signalant qu'une reponse est attendue, et un clic qui amene directement au champ de reponse.

Module: MOD-PERSONAL, MOD-REQUEST (BR-COMMENT-LOCK-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: suppression du bloc "P10 — Bandeau PENDING" (`GlassCard` pleine largeur avec titre, texte et bouton `Repondre` dedie), redondant avec le lien `Repondre` deja present sous chaque commentaire. A la place, le dernier commentaire du fil recoit une mise en evidence conditionnelle (`isAwaitingReply = needsUserResponse && index === visibleComments.length - 1`) — fond vert anime (`animate-pulse bg-success/20 ring-1 ring-success/50`) tant que le ticket est en statut `pending` cote demandeur, puisqu'aucun commentaire du demandeur n'a encore ete poste depuis le passage en attente, donc le dernier commentaire est necessairement celui de l'agent qui attend une reponse. Le clic ajoute desormais un `scrollIntoView` avant le `focus()` deja existant, pour amener directement au champ de reponse comme le faisait l'ancien bouton dedie. Options presentees a l'utilisateur et validees avant implementation : mise en evidence sur le dernier commentaire uniquement (pas sur tous les commentaires non repondus), et action au clic = scroll+focus sur le champ existant (pas de modal dediee). La banniere discrete de l'en-tete ("L'agent vous demande des informations complementaires", sans bouton) n'est pas concernee.

Verification: `npx tsc --noEmit` sans nouvelle erreur imputable au fichier (baseline preexistante inchangee) ; `npx eslint` — uniquement du bruit `prettier/prettier` (3748 occurrences) et le warning `unused eslint-disable directive` deja preexistant, zero erreur de logique.

## 2026-07-29 - Formulaire d'assignation a 4 niveaux obligatoires (File d'attente / A qualifier)

Demande: revoir le formulaire d'assignation de la File d'attente du Support General pour respecter strictement la hierarchie Direction -> Departement -> Service -> Personne, avec filtrage actif-uniquement, cascade de reinitialisation, messages de listes vides, et bouton `Assigner` desactive tant que le formulaire est incomplet.

Module: MOD-AGENT / MOD-CHIEF (BR-TICKET-QUALIFY-001, note formulaire 4 niveaux — nouvelle regle).

Fichiers modifies:
- `frontend/src/routes/app.queue.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: le formulaire de qualification (`QualifyTab`) est reorganise en 4 champs sequentiels reutilisant des fonctions API deja existantes (aucun endpoint/service backend cree ou modifie) :
- **Direction cible** — `fetchDirections({ status: "active" })`, toujours active.
- **Departement cible** (nouveau champ) — `fetchDepartments({ directionId, status: "active" })`, desactive tant qu'aucune direction n'est choisie.
- **Service cible** — `fetchUnits({ departmentId, status: "active" })` (auparavant filtre par direction, desormais par departement), desactive tant qu'aucun departement n'est choisi.
- **Personne cible** — fusion de `fetchUsers({ role: "agent-support", unit_id })` et `fetchUsers({ role: "chief-service", unit_id })` (dedupliques par id), desactive tant qu'aucun service n'est choisi. Le filtre `only_active=True` est deja applique cote backend (`list_by_role_and_unit`, `RepositoryAccount.py`), donc les comptes inactifs/bloques sont deja exclus sans changement necessaire. L'option "— Aucune (laisser la direction gerer)" est retiree : une personne precise doit toujours etre selectionnee.

Chaque changement de champ reinitialise tous les champs enfants (`directionId` change -> reset departement/service/personne ; `departmentId` change -> reset service/personne ; `unitId` change -> reset personne), y compris via les raccourcis de suggestion de routage existants (auto-application categorie -> direction). Un message explicite apparait sous chaque select vide ("Aucune direction active disponible.", "Aucun departement actif disponible pour cette direction.", "Aucun service actif disponible.", "Aucun employe autorise a traiter dans ce service."). Le bouton, renomme `Assigner` (etait `Valider l'orientation`), reste desactive tant que les 4 champs ne sont pas tous renseignes (`canAssign`). Soumission inchangee : `qualifyTriage(id, { category, priority, direction_id, unit_id, assignee_id }, actorId)` — `department_id` reste un filtre UI intermediaire, jamais envoye au backend (aucune colonne dediee, conforme au modele Direction -> Departement -> Unite via Unity + Organigram). Le bouton independant `Prendre la demande` (auto-assignation rapide de l'agent connecte, sans passer par ce formulaire) n'est pas concerne et reste inchange.

Point signale (voir aussi note dans BUSINESS_RULES.md): CLAUDE.md documente une regle deja en place ("routage dynamique", Module 1 termine) permettant de router une demande vers une direction ou un service seul sans designer de personne. Le nouveau formulaire rend la personne obligatoire pour ce bouton specifique — aucune contradiction backend (l'API `qualify_triage` garde `assignee_id` optionnel), mais cette page n'offre plus ce raccourci. A confirmer si c'est le comportement definitivement voulu.

Verification: `npx tsc --noEmit` — zero erreur sur `app.queue.tsx` (la baseline preexistante de 7 erreurs liees au typage `fetchDirections`/`realDirections` a disparu, resolue en passant par un appel explicite `() => fetchDirections({...})` au lieu de la reference de fonction nue comme `queryFn`) ; `npx eslint` — 590 occurrences, toutes `prettier/prettier`, zero erreur de logique.

## 2026-07-29 - Retrait de l'onglet "A prendre" de la File d'attente

Demande: sur `/app/queue`, supprimer l'onglet `A prendre` (confirme applicable a tous les roles ayant acces a la page) pour ne garder que `A qualifier`.

Module: MOD-AGENT / MOD-CHIEF (FEATURE-QUEUE-QUALIFICATION, BR-ROLE-AGENT-001).

Fichiers modifies:
- `frontend/src/routes/app.queue.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: retire entierement le selecteur d'onglets `A prendre`/`A qualifier` ainsi que la fonction `QueueTab` (recherche, filtres priorite/direction, vues liste/grille, selection multiple, dialogs Assigner/Escalader — ~600 lignes) — `QueuePage` rend directement `QualifyTab` (seul choix restant, pour `agent-support`, `chief-service` et `admin`, les 3 roles ayant acces a cette route). Le parametre d'URL `?tab=` et le type `Tab` associes sont supprimes avec le composant (aucune autre page ne s'appuyait sur ce parametre). Nettoyage des imports devenus inutiles dans ce fichier (`Checkbox`, `Input`, `Dialog*`, `LayoutToggle`, `PaginationBar`, `EscalationProgressBar`, `buildRequesterStepsFromStatus`, `DEFAULT_LEVELS`, `assignRequest`, `fetchQueue`, `useRole`, `apiFetch`, `Link`, `useNavigate`, `useCallback`, `AnimatePresence`/`motion`, `StatusBadge`, `Textarea`, `useEffect`, `format`, `fetchRefTable`) — verifie qu'aucun reste utilise ailleurs dans le fichier ; les fonctions partagees (`fetchQueue`, `assignRequest`) restent utilisees telles quelles par `app.chief-inbox.tsx`/`app.index.tsx`, aucune suppression globale. Le titre de page "File d'attente" (auparavant porte par `QueueTab`) est reintroduit dans l'en-tete de `QualifyTab` pour que la page conserve un titre.

Verification: `npx tsc --noEmit` retombe sur la meme baseline preexistante (typage `fetchDirections`/`realDirections` — non liee a ce changement) ; `npx eslint` — uniquement du bruit `prettier/prettier` (56 occurrences), zero erreur de logique, zero import residuel signale.

## 2026-07-29 - Correction bug critique : suppression de commentaire possible sur ticket cloture

Demande: une fois le bandeau "Les commentaires sont desactives - ticket cloture" affiche, il ne doit plus etre possible de supprimer/modifier un commentaire existant (capture d'ecran : menu `Supprimer` encore actif sur un commentaire malgre le bandeau).

Module: MOD-REQUEST (nouvelle regle BR-COMMENT-LOCK-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `backend/api/routes/RouteRequest.py`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: `canDeleteComment` (frontend) ne verifiait que la propriete du commentaire (auteur, ou role staff non-demandeur), sans jamais tenir compte du statut de la demande — le menu `Supprimer` restait donc actif meme quand le bandeau de verrouillage etait deja affiche. Cote backend, `DELETE /requests/{id}/comments/{comment_id}` n'avait aucun controle de statut non plus : un appel direct a l'API pouvait supprimer un commentaire sur un ticket cloture/rejete/archive, contournant totalement la restriction visuelle du frontend. Aucune fonctionnalite de modification (edition du texte) n'existe dans le code actuel — seule la suppression etait exposee et donc concernee.

Correction: `canDeleteComment` retourne desormais `false` des que `isArchived || r.status === "closed" || r.status === "rejected"`, la meme condition deja utilisee par le bandeau de verrouillage et le bouton `Repondre`. Cote backend, `delete_comment` leve une erreur `422` avec message explicite si `req.deleted_at is not None or req.request_status in {"closed", "rejected"}` — l'enforcement ne repose plus uniquement sur le masquage du bouton cote UI.

Corrections annexes (bugs preexistants decouverts pendant la verification TypeScript, non lies a la demande mais bloquants pour la compilation): `c.attachmentMimeType` (n'existe pas sur le type mappe) corrige en `c.attachmentMime` ; `formatFileSize` (fonction inexistante) corrige en `formatAttachmentSize` (helper deja defini plus haut dans le fichier). Ces deux coquilles venaient de la refonte recente du panneau Commentaires (bulles/avatars) et empechaient `tsc --noEmit` de passer sans erreur nouvelle.

Verification: `python -m compileall api/routes/RouteRequest.py` OK ; `npx tsc --noEmit` retombe exactement sur la baseline preexistante connue (13 erreurs `app.requests.$id.tsx`, 5 `app.requests.index.tsx`, typage `fetchDirections`/`Direction[]`) apres correction des deux coquilles ; `npx eslint` — uniquement du bruit `prettier/prettier` et un warning `unused eslint-disable directive` deja present avant cette session.

## 2026-07-29 - Detail ticket : reproduction maquette commentaires

Demande: reproduire typiquement la maquette fournie pour l'onglet `Commentaires` d'une demande/ticket, avec avatars de profil, bulles de discussion, pieces jointes et barre de publication.

Module: MOD-REQUEST / MOD-WORKFLOW (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: le panneau `commentsPanel` affiche maintenant les commentaires sous forme de fil conversationnel: avatars via `buildAvatarUrl`, bulles compactes avec nom + role, date + `Repondre`, menu visuel, indentation de reponse et carte de piece jointe avec telechargement. La barre de saisie reprend le modele de la maquette avec avatar, champ, trombone, reaction et bouton `Publier`. Les mutations `createComment`/`uploadAttachment`, les permissions, la visibilite public/interne et les endpoints ne changent pas.

Verification: `npm run build` frontend OK (client + SSR), avec les avertissements Vite habituels sur chunks volumineux/imports externes non utilises.

## 2026-07-29 - Notifications Lot 2 : matrice workflow vers acteurs précis

Demande: démarrer uniquement le Lot 2 du module Notifications, après validation de la table statuts officiels, pour compléter la matrice événements workflow -> destinataire précis sans changement RBAC, sans suppression physique et sans migration de statuts.

Correction: `ServiceRequest.py` notifie désormais la clôture au demandeur, l'annulation au demandeur et à l'agent assigné si distinct, et la réouverture acceptée au demandeur puis au prochain traitant précis (`assignee_id`) ou au chef d'unité si aucun agent n'est assigné. Les notifications restent créées via `NotificationEmitter`, donc publiées en SSE `notification.created` vers `target.user_ids=[recipient_id]`. Aucun statut (`qualified`/`escalated`/`cancelled`), endpoint, permission ou broadcast `request.*` n'est modifié dans ce lot.

Verification: `python -m compileall backend/api/services/ServiceRequest.py` OK. `backend\venv\Scripts\pytest.exe backend\tests\api\test_requests_baseline.py -q` lancé via `cmd.exe`: 36 passed, 21 failed; les échecs observés sont bloqués par l'état existant des fixtures/roles legacy (`KeyError: 'agent'` sur l'enum `role_enum`, alors que le référentiel actuel attend `agent-support`), pas par les notifications ajoutées dans ce lot.

## 2026-07-29 - Detail ticket : indicateurs delais sur une ligne

Demande: dans l'onglet `Délais de traitement`, afficher les blocs d'activite sur une seule ligne quand l'espace desktop le permet.

Module: MOD-REQUEST / MOD-WORKFLOW (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: la grille des 4 indicateurs passe en `xl:grid-cols-4`, avec padding reduit et textes tronques pour conserver une ligne propre en desktop. Le repli reste responsive en 2 colonnes tablette puis 1 colonne mobile. Aucun changement de calcul, donnees, permissions ou couleurs.

Verification: `npm run build` frontend OK (client + SSR), avec les avertissements Vite habituels sur chunks volumineux/imports externes non utilises.

## 2026-07-29 - Detail ticket : libelle SLA explicite

Demande: rendre l'onglet `SLA` plus explicatif en francais pour ameliorer l'ergonomie.

Module: MOD-REQUEST / MOD-WORKFLOW (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: le libelle visible de l'onglet passe de `SLA` a `Délais de traitement`. La cle interne `sla`, le contenu de l'onglet, les calculs, les couleurs et les permissions restent inchanges.

Verification: `npm run build` frontend OK (client + SSR), avec les avertissements Vite habituels sur chunks volumineux/imports externes non utilises.

## 2026-07-29 - Detail ticket : actions Traitement en modales

Demande: dans l'onglet `Traitement`, faire ouvrir une boite modale pour toutes les actions au clic, y compris celles qui etaient jusque-la directes ou affichees en section.

Module: MOD-REQUEST / MOD-WORKFLOW (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: `Demander des infos`, `Ajouter une note`, `Rejeter`, `Reassigner`, `Priorite`, `Service`, `Modifier` et `Annuler` ouvrent maintenant des modales `Dialog` au lieu de deployer un bloc dans la section. Les actions simples (`M'assigner`, `Demarrer traitement`, `Reprendre le traitement`, `Marquer resolue`, `Confirmer la resolution`, `Approuver reouverture`) passent par une modale de confirmation avant d'appeler les memes mutations. Les actions deja modales (`Escalader`, `Refuser reouverture`, `Transferer direction`, `Creer circuit`, `Rouvrir la demande`, `Votre avis`) restent sur ce pattern. Aucun changement de mutation, permission, endpoint ou workflow.

Verification: `npm run build` frontend OK (client + SSR), avec les avertissements Vite habituels sur chunks volumineux/imports externes non utilises.

## 2026-07-29 - Detail ticket : actions demandeur en modales dans Traitement

Demande: deplacer les blocs demandeur `Demande cloturee` et `Votre avis` dans l'onglet `Traitement`, sous forme de boutons d'action ouvrant une modale.

Module: MOD-REQUEST / MOD-WORKFLOW (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: les deux grands blocs pleine largeur sont retires du flux principal. L'onglet `Traitement` affiche maintenant les actions demandeur correspondantes: `Rouvrir la demande`/`Demande cloturee` ouvre une modale de reouverture ou d'information, et `Votre avis` ouvre une modale reutilisant `AppreciationForm`. Les mutations, permissions, donnees et couleurs existantes restent conservees.

Verification: `npm run build` frontend OK (client + SSR), avec les avertissements Vite habituels sur chunks volumineux/imports externes non utilises.

## 2026-07-29 - Detail ticket UX Lot 4 : timeline compacte

Demande: rendre le journal des actions plus scannable avec action, acteur et date en ligne principale, sans modifier l'ordre, les donnees, la limite initiale visible, l'expansion ni les couleurs.

Module: MOD-REQUEST / MOD-WORKFLOW (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/components/workflow-timeline.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: compactage strictement visuel de `WorkflowTimeline`: icones et espacements reduits, ligne principale action/acteur/date, suppression des badges secondaires redondants visibles sous chaque evenement, commentaires et motifs gardes dans un bloc discret. Quand le libelle principal indique generiquement `un agent`, il affiche le nom reel de `targetUserName` si disponible. Le controle `Voir tout`/`Reduire`, les 3 evenements visibles par defaut, l'ordre des evenements et toutes les couleurs restent inchanges.

Verification: `npm run build` frontend OK (client + SSR), avec les avertissements Vite habituels sur chunks volumineux/imports externes non utilises.

## 2026-07-29 - Detail ticket UX Lot 3 : onglets et zone de contenu

Demande: compacter les onglets et clarifier leur hierarchie visuelle sans supprimer d'entrees ni badges, sans toucher aux couleurs, a l'etat actif ou a la logique de rendu.

Module: MOD-REQUEST / MOD-WORKFLOW (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: reduction des paddings de la barre d'onglets et des panneaux de contenu, conservation du scroll horizontal local mobile, et ajout de separations visuelles non fonctionnelles avant les groupes `Commentaires/Fichiers` et `SLA/Traitement`. Les 6 onglets, leurs badges, l'etat actif, les couleurs existantes et le contenu affiche restent inchanges.

Verification: `npm run build` frontend OK (client + SSR), avec les avertissements Vite habituels sur chunks volumineux/imports externes non utilises.

## 2026-07-29 - Detail ticket UX Lot 2 : stepper compact

Demande: compacter le stepper de progression du detail ticket, en gardant les 5 etapes lisibles sur desktop, tablette et telephone, sans toucher aux couleurs ni a la logique.

Module: MOD-REQUEST / MOD-WORKFLOW (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: reduction strictement visuelle du stepper `TicketLifecycleStepper`: cercles plus petits, connecteurs recalés, padding de carte reduit, libelles/dates plus compacts avec tailles progressives selon largeur. `buildFixedLifecycleSteps`, les dates, les etats (`done`, `active`, `warning`, `pending`) et toutes les couleurs restent inchanges.

Verification: `npm run build` frontend OK (client + SSR), avec les avertissements Vite habituels sur chunks volumineux/imports externes non utilises.

## 2026-07-29 - Detail ticket UX Lot 1 : header et grille generale

Demande: lancer le Lot 1 de la refonte UX des pages detail demande/ticket, avec contrainte explicite: aucune modification de couleur autorisee.

Module: MOD-REQUEST / MOD-WORKFLOW (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: ajustement strictement visuel de la grille generale et de la carte haute partagee par les details tickets: repartition desktop proche 68/32, gutters/espacements plus aerés, titre du ticket rendu plus dominant, bloc SLA reduit typographiquement pour ne plus concurrencer le titre. Les couleurs existantes, badges, fonds, bordures, calcul SLA, routes, appels API, permissions et conditions d'affichage restent inchanges.

Verification: `npm run build` frontend OK (client + SSR), avec les avertissements Vite habituels sur chunks volumineux/imports externes non utilises.

## 2026-07-29 - Templates HTML SMTP pour les emails ticketing

Demande: reprendre pour l'application ticketing le principe du dossier `edgrh/templates`, afin que l'affichage des contenus de mail SMTP soit gere par des templates HTML.

Module: MOD-NOTIF / backend SMTP (BR-NOTIF-001).

Fichiers modifies:
- `backend/api/core/mailer.py`
- `backend/api/services/NotificationEmitter.py`
- `backend/templates/_ticket_notification_base.html`
- `backend/templates/ticket_confirmation_creation.html`
- `backend/templates/ticket_accuse_reception.html`
- `backend/templates/ticket_affectation.html`
- `backend/templates/ticket_changement_statut.html`
- `backend/templates/ticket_validation.html`
- `backend/templates/ticket_resolution.html`
- `backend/templates/ticket_cloture.html`
- `backend/templates/ticket_reouverture.html`
- `backend/templates/ticket_transfert.html`
- `backend/templates/ticket_alerte_sla.html`
- `backend/templates/ticket_rejet_annulation.html`
- `backend/templates/ticket_recu_paiement.html`
- `backend/templates/reset_code_email.html`
- `backend/templates/notification_email.html`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/DEPENDENCY_INDEX.md`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: le HTML des emails EDG Connect etait construit directement dans `mailer.py`, ce qui rendait la presentation difficile a maintenir et moins coherente avec la structure deja presente dans `edgrh/templates`.

Correction: creation de `backend/templates/` avec une base HTML commune, 12 templates evenementiels conformes a la maquette (creation, accuse de reception, affectation, changement de statut, validation, resolution, cloture, reouverture, transfert, alerte SLA, rejet/annulation, recu de paiement) et le template de code de reinitialisation. `mailer.py` choisit automatiquement la variante selon le titre/type de notification, rend le HTML via un mini-rendeur interne avec echappement HTML, integre le logo EDG en image inline CID et conserve les fonctions publiques existantes (`send_notification_email`, `send_reset_code_email`). `NotificationEmitter.py` enrichit les emails avec les details du ticket quand `request_id` est present. L'envoi SMTP et la decision `CommunicationSetting.email_on` restent inchanges.

Verification: `python .codex/render_email_check.py` OK (`render ok`, script temporaire supprime ensuite) et `python -m compileall backend/api/core/mailer.py backend/api/services/NotificationEmitter.py` OK.

Complement responsive: `_ticket_notification_base.html` ajoute une couche mobile/tablette (`@media only screen and (max-width: 520px)`) pour empiler header/footer, transformer les details en lignes verticales et couper les libelles longs. Verification ciblee: rendu des 12 variantes dans une page HTML temporaire + assertions sur `max-width:640px`, la media query mobile et `overflow-wrap:anywhere`; `python -m compileall backend/api/core/mailer.py backend/api/services/NotificationEmitter.py` OK.

## 2026-07-29 - Modification personnelle du ticket autorisee aussi en qualification

Demande: le demandeur ne voyait plus l'option "Modifier la demande" des que son ticket passait en statut "En qualification" (`qualifying`) — seul le statut `new` l'autorisait. Nouvelle regle metier explicite du chef : la modification (titre/description) doit rester possible tant que le ticket est `new` ou `qualifying`, et se verrouiller definitivement a partir de `qualified` (et pour tous les statuts suivants, y compris apres reouverture `reopened` — un ticket reouvert reste verrouille). Toute information complementaire passe desormais uniquement par commentaires/reponses/pieces jointes.

Module: MOD-REQUEST (BR-REQUESTER-EDIT-001, nouvelle regle).

Fichiers modifies:
- `backend/api/services/ServiceRequest.py` — `requester_edit()` : la verification `req.request_status != "new"` est remplacee par `req.request_status not in self._REQUESTER_EDIT_STATUSES` avec `_REQUESTER_EDIT_STATUSES = ("new", "qualifying")`.
- `backend/api/routes/RouteRequest.py` — docstring de `PATCH /requests/{id}/requester-edit` mise a jour.
- `frontend/src/lib/capabilities.ts` — `TICKET_ACTION_STATUSES.requester_edit` passe de `["new"]` a `["new", "qualifying"]` (`canEdit` dans `app.requests.$id.tsx` en depend directement, aucun changement necessaire cote composant).
- `docs/codex/BUSINESS_RULES.md` — nouvelle regle BR-REQUESTER-EDIT-001.
- `docs/codex/CHANGELOG_CODEX.md`

Cause: la restriction initiale ("des qu'un acteur est deja intervenu") avait ete implementee au sens strict du tout premier statut, alors que la qualification est une etape de triage automatique/secretariat qui ne constitue pas encore une intervention de fond sur le contenu du ticket.

Verification: `python -c "import ast; ast.parse(open('backend/api/services/ServiceRequest.py').read())"` et idem `RouteRequest.py` (syntaxe OK). Pas de test backend/frontend existant ne reference `requester_edit`/`requester-edit` (verifie par recherche), donc aucune regression de suite de tests a corriger.

## 2026-07-29 - Cards tickets cliquables sur toute leur surface

Demande: sur les cards de tickets, pouvoir cliquer directement sur toute la card pour ouvrir le detail, au lieu de devoir cliquer uniquement sur le titre/reference.

Module: MOD-AGENT, MOD-CHIEF, MOD-SUPERVISION (BR-UI-TICKET-LAYOUT-001, BR-NAV-001).

Fichiers modifies:
- `frontend/src/routes/app.my-tickets.tsx`
- `frontend/src/routes/app.queue.tsx`
- `frontend/src/routes/app.supervision.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: certaines vues en grille rendaient la card ticket comme un simple conteneur, avec navigation seulement sur le titre/reference ou sur un bouton `Traiter`. L'ergonomie etait incoherente avec les cards deja completement cliquables (`Mes demandes`, `Boite de traitement`).

Correction: les cards grille de `Mes tickets`, `File d'attente` et les cards d'escalades de `Supervision` deviennent des surfaces cliquables avec `role="link"` et support clavier `Enter`/`Espace`, en conservant la route detail propre au contexte (`/app/my-tickets/tickets/$id`, `/app/queue/tickets/$id`, `/app/supervision/tickets/$id`). Les actions internes (`Escalader`, `Assigner`, checkbox, actions escalade) stoppent la propagation pour ne pas ouvrir le detail par erreur.

Verification: `npm run build` cote frontend OK (client + SSR), avec les avertissements Vite habituels sur chunks volumineux et imports externes non utilises.

## 2026-07-29 - Detail ticket chef de service : menu Priorite non rogne

Demande: dans l'espace chef de service, corriger le probleme d'affichage encerclé en rouge sur le menu `Priorite` du detail ticket.

Module: MOD-CHIEF / MOD-REQUEST (BR-UI-TICKET-DETAIL-001, BR-PRIORITY-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: apres le deplacement des actions staff dans l'onglet `Traitement`, le menu `Priorite` etait rendu en `absolute` dans une carte centrale `glass-strong overflow-hidden`, puis suivi par le panneau d'actions. Selon la hauteur disponible, le menu pouvait etre rogne ou visuellement recouvert.

Correction: le conteneur d'onglets du detail ticket autorise l'overflow visible, le groupe d'actions de traitement cree une couche `relative z-20`, et le menu `Priorite` est remonte en `z-50`. Aucun changement de route, permission, mutation ou endpoint.

Verification: `npm run build` cote frontend OK (client + SSR), avec les avertissements Vite habituels sur chunks volumineux et imports externes non utilises.

## 2026-07-29 - Supervision chef de departement : perimetre departement + services

Demande: dans `/app/supervision` et `/app/supervision/tickets/$id`, permettre au chef de departement de superviser son departement compose des services dont les chefs de service sont sous son autorite.

Module: MOD-SUPERVISION, MOD-CHIEF (BR-ROLE-CHIEF-DEPARTEMENT-001).

Fichiers modifies:
- `frontend/src/routes/app.supervision.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: `app.supervision.tsx` traitait tous les roles chef de la meme maniere et appelait `fetchRequests({ unit_id: sessionUser.unit_id })` / `fetchUsers({ unit_id: sessionUser.unit_id })`. Pour `chief-departement`, `sessionUser.unit_id` represente le departement, mais `unit_id` cote API est un filtre exact ; la page ne recuperait donc pas les tickets et agents des services rattaches au departement.

Correction: distinction explicite `chief-service` / `chief-departement` dans la page supervision. `chief-service` conserve le filtre exact `unit_id`. `chief-departement` utilise `direction_id=<department unity_id>` pour les agents et tickets, ce qui reutilise l'expansion backend existante `_direction_unity_ids` (departement + services descendants). Les libelles de la page deviennent dynamiques : "Supervision du departement" pour chief-departement, "Supervision du service" pour chief-service.

Verification: `npm run build` cote frontend OK (client + SSR), avec les avertissements Vite habituels sur chunks volumineux/imports externes non utilises.

## 2026-07-29 - Temps reel : 7 evenements orphelins ajoutes a l'invalidation SSE + filet de rattrapage reconnexion

Demande: ameliorer l'experience utilisateur pour que les chargements de donnees soient en temps reel.

Module: MOD-REQUEST, MOD-AGENT, MOD-CHIEF, MOD-DIRECTION (BR-REALTIME-001, nouvelle regle).

Fichiers modifies:
- `frontend/src/lib/realtime/invalidation-map.ts`
- `frontend/src/providers/realtime-provider.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Localisation: l'infrastructure temps reel (SSE + `INVALIDATION_MAP` + `RealtimeProvider`) existait deja et couvrait correctement 9 des 16 types d'evenements `request.*` reellement emis par `ServiceRequest.py`. Verification par comparaison directe des `emit_event(AppEvent(type=...))` du backend contre les cles de `INVALIDATION_MAP` : 7 evenements bien emis et recus cote client mais sans handler d'invalidation associe — `request.routed`, `request.reassigned`, `request.transferred_direction`, `request.priority_changed`, `request.rejected`, `request.reopen_requested`, `request.reopen_rejected`. Consequence concrete : une reassignation de service, un transfert de direction, un changement de priorite ou un rejet restaient invisibles en temps reel pour les autres sessions ouvertes (chef, agent, demandeur) jusqu'a un rechargement manuel de page.

Correction: les 7 evenements manquants sont ajoutes a `INVALIDATION_MAP`, avec les memes prefixes de query keys (`request`, `requests`, `queue`, `my-tickets`, `my-tickets-stats`, `stats`, etc.) que les evenements `request.*` deja geres les plus proches par nature. Comme `Object.keys(INVALIDATION_MAP)` pilote directement l'enregistrement des abonnements SSE dans `realtime-provider.tsx` (aucun autre fichier a modifier pour brancher un nouvel evenement), ces 7 ajouts suffisent a les rendre actifs.

Complement fiabilite: ajout d'un filet de rattrapage sur reconnexion SSE — `event_bus.py` etant un pub/sub en memoire sans rejeu d'historique, tout evenement emis pendant une coupure reseau etait definitivement perdu ; et depuis la desactivation du refetch automatique au focus/reconnexion (optimisation perf du 2026-07-28), plus rien ne rattrapait ces evenements manques avant un rechargement manuel. `realtime-provider.tsx` invalide desormais l'union complete des query keys de `INVALIDATION_MAP` a chaque reconnexion SSE faisant suite a une coupure detectee (pas au montage initial, via un ref `hasDroppedRef` qui distingue premiere connexion et reconnexion).

Verification: `npx tsc --noEmit` sans nouvelle erreur sur les deux fichiers touches ; `npx eslint` sur `invalidation-map.ts` — uniquement du bruit `prettier/prettier` ; sur `realtime-provider.tsx` — un warning `react-refresh/only-export-components` preexistant (export `useRealtimeStatus` deja present avant cette session, non introduit par ce changement) et une note `prettier/prettier` preexistante, aucune erreur de logique nouvelle.

## 2026-07-29 - Correction bug critique RBAC : tickets assignes invisibles hors unite courante de l'agent

Demande: "je ne vois plus les tickets dans leur espace correspondante" — signale sur File d'attente, Mes tickets, Mes demandes et Supervision/Direction/DG, role Agent Support teste.

Module: MOD-AGENT, MOD-CHIEF, MOD-PERSONAL (BR-ROLE-AGENT-001).

Fichiers modifies:
- `backend/api/routes/RouteRequest.py`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Localisation: verification en base (compte `Fatoumata Conte`, id=5, role agent-support, unity_id=16) — sur ses 21 tickets assignes (`assignee_id=5`), un seul appartient a l'unite 16 ; les 20 autres sont rattaches a d'autres unites (6, 1, 14, ou aucune). Cause identifiee dans `list_requests` (`RouteRequest.py`) : pour agent-support/chief-service, `unit_id` etait force a `actor.unity_id` **inconditionnellement**, meme quand le client demandait explicitement `assignee_id=<soi-meme>` (c'est le cas de `app.my-tickets.tsx`, qui interroge uniquement par `assignee_id` — voir `BR-ROLE-AGENT-001`). Consequence : tout ticket assigne personnellement a l'agent mais hors de son unite courante disparaissait de `Mes tickets`/`File d'attente`. De plus, `_check_request_access` (controle d'acces au detail `GET /requests/{id}`) n'avait de bypass que pour le demandeur (`requester_id`), pas pour l'assigne (`assignee_id`) — un agent pouvait donc recevoir un 403 en ouvrant un ticket qui lui etait pourtant assigne.

Correction: ajout d'un bypass symetrique a celui deja existant pour le demandeur — `is_own_assignee_view` (`assignee_id == str(actor.id)`) dans `list_requests`, qui leve le forcing `unit_id`/`direction_id` uniquement dans ce cas ; et un retour anticipe equivalent (`assignee_id == str(actor.id)`) dans `_check_request_access`. Le filtre `assignee_id` reste toujours verrouille sur l'identite de l'acteur (aucun elargissement de perimetre), seule la restriction d'unite forcee est levee quand l'agent consulte explicitement ses propres tickets assignes.

Verification: `python -m compileall api/routes/RouteRequest.py` OK. Test E2E via API non effectue (backend local intermittent non-reactif dans cet environnement, deja constate en session precedente) — a confirmer manuellement par l'utilisateur en rechargeant `Mes tickets`/`File d'attente` avec le compte Agent Support.

## 2026-07-29 - Perf : rapport decisionnel (/reports/decision) scanne toute la table workflow_detail/attachment sans tenir compte de la periode

Demande: "je veux que les chargements (donnees, pages, etc...) soient dans les 10s" — investigation ciblee sur la page la plus probable (Rapports, chef/direction/admin) apres qu'une exploration codebase (backend + frontend) ait classe les points d'impact par probabilite reelle de depasser 10s.

Module: MOD-REPORTS (rapport decisionnel).

Fichiers modifies:
- `backend/api/services/ServiceReport.py` — sous-requetes `evt` (agregation `workflow_detail`) et `att` (agregation `attachment`) dans `_decision_rows()`.
- `docs/codex/CHANGELOG_CODEX.md`

Cause: `_decision_rows(start, end, ...)` filtre la requete principale par periode (`DATE(r.created_at) BETWEEN :start AND :end`, toujours actif — `start`/`end` non optionnels), mais les deux sous-requetes `LEFT JOIN (...) evt` et `LEFT JOIN (...) att` agregeaient `workflow_detail`/`attachment` sans aucune restriction — elles scannaient et agregeaient (`GROUP BY request_id`) l'intégralite de ces deux tables, pour **toutes** les demandes de l'historique complet, quelle que soit la periode demandee, avant de faire le `LEFT JOIN` sur le sous-ensemble filtre. `decision_report()` appelle `_decision_rows()` deux fois par requete HTTP (periode courante + periode precedente pour le comparatif), doublant ce cout a chaque appel. Plus `workflow_detail`/`attachment` grossissent avec le temps, plus l'ecart entre "periode demandee" et "table entiere scannee" s'aggrave — explique une degradation progressive independante de la periode choisie par l'utilisateur.

Correction: les deux sous-requetes rejoignent desormais `request` (alias `rf`/`rf2`) avec le meme filtre `deleted_at IS NULL AND DATE(created_at) BETWEEN :start AND :end` deja utilise par la requete principale (memes parametres lies, pas de nouveau parametre) — elles n'agregent plus que les lignes appartenant a des demandes de la periode consideree. Correction purement additive au niveau du filtrage : le lien final `evt.request_id = r.id` / `att.request_id = r.id` restant strictement identique, aucun changement de resultat, uniquement une reduction du volume scanne. Index deja presents et utilises par le nouveau join : `idx_wf_req` (`workflow.request_id`), `idx_att_req` (`attachment.request_id`), `idx_req_created` (`request.created_at`).

Verification: `python -c "import ast; ast.parse(...)"` sur `ServiceReport.py` (syntaxe OK). Pas d'acces a une base MySQL locale peuplee pour mesurer le gain reel avant/apres — a confirmer en environnement avec donnees de volume realiste.

Perimetre exclu (investigue puis ecarte, cf. echanges) : plafonner `GET /requests` a moins de 1000 (cascaderait sur 6+ pages qui en dependent) ; brancher `app.reports.tsx` sur `/stats/by-direction`/`/stats/by-category` (ces endpoints `ServiceStats.py` referencent une table `direction` et des colonnes `request.direction_id`/`account.direction_id`/`account.unit_id` supprimees par la migration `011_replace_direction_unit_with_unity_organigram` — code mort casse, non appele par le frontend actuel, hors perimetre de cette session).

## 2026-07-29 - Reference demande : ajout du niveau departement (direction/departement/service)

Demande: la reference generee a la creation d'une demande doit suivre la formule "codename-direction-demandeur"-"codename-departement-demandeur"-"codename-service-demandeur" suivie de l'horodatage et de la sequence (ex: `DSI-ED-SED-0824070260729-001`), au lieu de seulement direction-service (ex: `SED-SED-0824070260729-001` — le segment direction etait meme errone car derive de la colonne plate `unity.parent_direction_id`, jamais peuplee par le seed, qui retombait donc sur le service lui-meme).

Module: MOD-REQUEST (BR-REQ-REF-001).

Fichiers modifies:
- `backend/api/services/ServiceRequest.py` — nouvelle methode `_org_chain_for_unity()` (remonte l'arbre `Organigram` feuille -> racine pour une unite donnee) ; `_requester_ref_unities()` remplacee par `_requester_ref_hierarchy()` qui retourne `(direction, departement, service)` en se basant sur cet arbre plutot que sur `unity.parent_direction_id` ; `_build_reference_base()` compose desormais 3 segments (`direction_code-departement_code-service_code`) au lieu de 2, avec repli du departement sur le code direction quand l'organigramme ne comporte pas de niveau intermediaire (cas de toutes les directions sauf DSI dans le seed actuel).
- `backend/api/repositories/RepositoryRequest.py` — docstring de `next_ref()` mise a jour (`DIR-DEPT-SVC-HHMMSSYYYMMDD-SEQ`) ; aucun changement de logique (le prefixe reste une chaine opaque).
- `docs/codex/BUSINESS_RULES.md` — BR-REQ-REF-001 mise a jour.
- `docs/codex/CHANGELOG_CODEX.md`

Cause: `_requester_ref_unities()` resolvait la "direction" via `unit.parent_direction_id`, une colonne plate sur `Unity` jamais renseignee par `seed_references.py` (seul l'arbre `Organigram`, autoportant via `parent_id`, encode la hierarchie reelle). Quand cette colonne est `NULL`, le code retombait sur `unit` lui-meme, produisant un doublon (ex: `SED-SED-...` au lieu de `DSI-SED-...`), et il n'existait de toute facon aucune notion de departement intermediaire.

Correction: la hierarchie est desormais entierement derivee de `Organigram` (le seul champ fiable) : le noeud racine (sans parent) est la direction, le noeud feuille est le service du demandeur, et le noeud intermediaire (s'il existe, ex: `DSI-DED`/`DSI-DEX`/`DSI-DIR` pour la DSI) est le departement. Pour les directions sans departement dedie dans le seed actuel (DC, DT, DRH, DF, DM, DI, DIAJ, DG), le segment departement reprend le code direction.

Verification: `python -c "import ast; ast.parse(open('backend/api/services/ServiceRequest.py').read())"` et idem sur `RepositoryRequest.py` (syntaxe OK).

## 2026-07-29 - Correction bug : agent assigne duplique dans "Intervenants" + nom complet manquant

Demande: sur `/app/requests/:id`, le panneau "Intervenants" affichait deux lignes distinctes pour le meme agent assigne — "Conte / Agent Support / Assigne" et "Fatoumata Conte / Agent Support / Ticket assigne a un agent" — meme cause racine que le doublon demandeur corrige plus tot (`String(raw.requester_id)`). Demande complementaire: garantir l'affichage du nom complet (prenom + nom) pour chaque intervenant.

Module: MOD-REQUEST (detail ticket, panneau lateral "Intervenants").

Fichiers modifies:
- `backend/api/models/ModelRequest.py` — propriete `Request.assignee_name` renvoie desormais le nom complet (`firstname + name`, meme convention que `ServiceRequest._account_display_name` deja utilisee pour `target_user_name` sur l'evenement timeline d'assignation) au lieu du seul nom de famille.
- `frontend/src/lib/api/requests.ts` — `mapRequest()` : `assigneeId` coerce en `String(raw.assignee_id)` (meme fix que `requesterId`) ; type `RawRequest.assignee_id` corrige en `number | string | null`.
- `frontend/src/components/new-request-form.tsx` — `requester_name` envoye a la creation compose desormais `[sessionUser.firstname, sessionUser.name].filter(Boolean).join(" ")` (meme pattern deja utilise dans `app.requests.$id.tsx:542`, `app.profile.tsx:284`, `app.admin.users.tsx:134`) au lieu du seul nom de famille — corrige l'affichage du demandeur pour les nouvelles demandes internes (n'affecte pas retroactivement les demandes deja creees, `requester_name` etant une colonne stockee et non calculee).
- `docs/codex/CHANGELOG_CODEX.md`

Cause: deux bugs cumules sur la meme paire d'entrees `buildParticipants()` :
1. Cle de dedoublonnage : `request.assigneeId` (nombre JSON brut, non coerce) vs `event.targetUserId` de l'evenement `assigned` (`str(assignee_id)` cote backend, donc toujours string cote frontend via `asString()`) — deux cles de types differents ⇒ deux entrees Map pour la meme personne.
2. Nom incomplet : `Request.assignee_name` ne renvoyait que `Account.name` (nom de famille seul), alors que l'evenement timeline utilise `_account_display_name` (prenom + nom) — meme une fois dedoublonne, le nom affiche aurait ete tronque selon l'ordre d'insertion dans la Map (`add()` ne met a jour ni le champ `name`, ni `role` si deja present).

Correction: alignement du type/de la coercion `assigneeId` sur le meme pattern deja applique a `requesterId`, et alignement de `assignee_name` (backend) sur `_account_display_name` pour renvoyer systematiquement le nom complet — les deux entrees fusionnent desormais en une seule, avec le nom complet de l'agent.

Verification: `python -c "import ast; ast.parse(...)"` sur `ModelRequest.py` (syntaxe OK) ; `npx tsc --noEmit` — aucune nouvelle erreur (baseline preexistante comparee via `git stash`, inchangee).

## 2026-07-29 - Uniformisation titre du ticket + alignement etoile (independant du navigateur/largeur)

Demande: uniformiser l'affichage du titre du ticket sur le format de la premiere capture (2-3 mots par ligne, etoile bien alignee) — la seconde capture montrait un mot par ligne et une etoile flottant au milieu du titre, incoherent selon la fenetre/navigateur.

Module: MOD-REQUEST (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: le titre passait a `lg:text-4xl` (36px) des 1024px de large, alors que la colonne titre partage encore l'espace avec le bloc SLA fixe (288px) jusqu'a des largeurs plus confortables — resultat un rendu "un mot par ligne" tres sensible a la largeur exacte disponible. Par ailleurs le conteneur flex titre+etoile utilisait `items-center` : des que le titre s'etalait sur plusieurs lignes, l'etoile se retrouvait centree au milieu du bloc au lieu de rester a cote de la premiere ligne.

Correction: le saut vers `text-4xl` est repousse a `xl:` (1280px) au lieu de `lg:` (1024px) — le titre reste a `text-3xl` sur toute la plage intermediaire, largeur ou 2-3 mots par ligne restent lisibles de facon deterministe. Le conteneur titre+etoile passe de `items-center` a `items-start` avec `mt-1` sur l'icone, un alignement fixe qui ne depend plus du nombre de lignes du titre ni de la largeur de fenetre/navigateur.

Verification: `npx tsc --noEmit` sans nouvelle erreur imputable au fichier (baseline preexistante inchangee) ; `npx eslint` — 3221 problemes, tous confirmes `prettier/prettier` via sortie JSON agregee, zero erreur de logique.

## 2026-07-29 - Correction bug : demandeur duplique dans "Intervenants" (detail ticket)

Demande: sur `/app/requests/:id`, le panneau "Intervenants (N)" affichait deux lignes distinctes pour le meme demandeur — "GOEPOGUI / Demandeur / Createur" et "GOEPOGUI / Demandeur / Demande creee par l'utilisateur" — alors que les deux representent le meme evenement (creation du ticket par le demandeur).

Module: MOD-REQUEST (detail ticket, panneau lateral "Intervenants").

Fichiers modifies:
- `frontend/src/lib/api/requests.ts` — `mapRequest()` : `requesterId` coerce desormais en `String(raw.requester_id)` (comme `directionId`/`serviceId`) ; type `RawRequest.requester_id` corrige en `number | string | null`.
- `docs/codex/CHANGELOG_CODEX.md`

Cause: `buildParticipants()` (`app.requests.$id.tsx`) deduplique les intervenants via une `Map` cle sur `candidate.key`. Le "createur" est ajoute avec `key: request.requesterId`, et l'evenement timeline `created` est ajoute avec `key: event.actorId` (calcule via `asString(infos.actor_id)`, donc toujours une string). Le backend renvoie `requester_id` en JSON comme nombre (`Optional[int]` dans `SchemaRequest.py`), et `mapRequest()` le recopiait tel quel (`raw.requester_id ?? ""`) sans coercion — `request.requesterId` valait donc le nombre `12` alors que `event.actorId` valait la chaine `"12"`. Deux cles de types differents dans la `Map` ⇒ deux entrees pour la meme personne au lieu d'une fusion.

Correction: alignement de `requesterId` sur la meme convention `String(...)` deja utilisee pour les autres identifiants mappes depuis l'API (`directionId`, `serviceId`), pour que la cle corresponde exactement a celle produite par `asString()` cote timeline.

Verification: `npx tsc --noEmit` — aucune nouvelle erreur (baseline preexistante comparee via `git stash`, inchangee).

## 2026-07-29 - Boutons de traitement deplaces dans l'onglet Traitement

Demande: les boutons de traitement (Demarrer traitement, Demander des infos, Escalader, etc.) doivent se trouver dans l'onglet `Traitement` plutot que dans l'en-tete du ticket.

Module: MOD-REQUEST, MOD-AGENT, MOD-CHIEF (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: extraction du bloc de boutons d'action staff (auparavant directement dans `<header>`, visible sur la capture pour `Fatoumata Conte`/Agent Support) dans une nouvelle variable `treatmentActionsPanel`, avec exactement les memes conditions `can*` et mutations qu'avant (aucun changement de permission/logique metier). Ce panneau est desormais rendu dans le contenu de l'onglet `Traitement`, au-dessus du panneau `requestActionsPanel` existant (actions demandeur). Pour eviter un doublon visuel sur `Marquer resolue` (present dans les deux panneaux via `canResolveTicket`), la branche correspondante a ete retiree de `requestActionsPanel` et de `canShowQuickActions` — ce panneau ne porte plus que les actions reservees au demandeur (`Modifier`, `Annuler`, `Demander une reouverture`, `Confirmer la resolution`). L'en-tete du ticket ne contient plus que reference/titre/badges/bloc SLA et les bannieres d'information (`needsUserResponse`, `isArchived`), ce qui reduit aussi le risque de squeeze du titre corrige precedemment (moins d'elements en concurrence dans la meme ligne flex).

Verification: `npx tsc --noEmit` sans nouvelle erreur imputable au fichier (baseline preexistante inchangee) ; `npx eslint` — 3221 problemes, tous confirmes `prettier/prettier` via sortie JSON agregee, zero erreur de logique.

## 2026-07-29 - Correction bug : bloc "Demandeur" (Direction/Departement/Service) vide sur le detail ticket

Demande: sur `/app/requests/:id`, le panneau "Details de la demande" > section "Demandeur" affichait toujours `—` pour Direction/Departement/Service (visible sur capture, encadre en rouge), alors que la section "Traitement" juste en dessous affiche correctement ces memes informations pour l'unite en charge du ticket.

Module: MOD-REQUEST (detail ticket, panneau lateral).

Fichiers modifies:
- `backend/api/models/ModelRequest.py` — ajout propriete `Request.requester_unit_id` (derivee de `self.requester.unity_id`, relation deja chargee en `lazy="selectin"`).
- `backend/api/schemas/SchemaRequest.py` — ajout champ `requester_unit_id: Optional[int]` sur `_RequestCommonFields` (expose sur `RequestResponse` et `RequestListItemResponse`).
- `frontend/src/routes/app.requests.$id.tsx` — `requesterDirectionName` derive desormais la direction via `requesterUnit?.direction_id` (meme pattern deja utilise pour `currentDirectionId`/l'unite en charge) au lieu de dependre d'un champ `requester_direction_id` qui n'a jamais existe cote backend.
- `docs/codex/API_INDEX.md`, `docs/codex/CHANGELOG_CODEX.md`

Cause: le frontend (`frontend/src/lib/api/requests.ts`) mappait deja `requesterServiceId: raw.requester_unit_id` et `requesterDirectionId: raw.requester_direction_id`, mais aucun des deux champs n'a jamais existe dans le schema Pydantic de reponse (`SchemaRequest.py`) ni dans une propriete du modele `Request` — le backend ne renvoyait donc jamais ces valeurs, contrairement a `assignee_name`/`direction_id` (unite en charge) qui suivent deja ce pattern de propriete Python exposee via `orm_mode`.

Correction: ajout de la propriete `requester_unit_id` (service d'appartenance du demandeur, via `Account.unity_id` deja charge) cote backend/schema ; cote frontend, la direction du demandeur est resolue a partir de la liste `units` deja chargee (`requesterUnit.direction_id`) exactement comme pour la section "Traitement", evitant d'avoir a exposer un second champ backend pour la direction (deduction faite via `Unity.parent_direction_id`, deja indisponible en synchrone sur `Account.unity` qui est `lazy="raise"`).

Verification: `python -c "import ast; ast.parse(...)"` sur les 2 fichiers backend modifies (syntaxe OK) ; `npx tsc --noEmit` sur `app.requests.$id.tsx` — aucune nouvelle erreur (baseline preexistante comparee via `git stash` inchangee).

## 2026-07-28 - Correction bug critique : titre du ticket ecrase lettre par lettre

Demande: mauvaise disposition constatee sur `/app/my-tickets/tickets/46` (et toutes les vues d'une demande) — le titre s'affichait avec une lettre par ligne, sur toute la hauteur de la page. Corriger pour retrouver la bonne disposition de `app.requests.$id.tsx`.

Module: MOD-REQUEST (BR-UI-TICKET-DETAIL-001) — impact transversal car composant partage `RequestDetailPage`.

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: `/app/my-tickets/tickets/:id` (`app.my-tickets_.tickets.$id.tsx`) rend `RequestDetailPage` avec `context="myTickets"` — c'est donc exactement le meme composant que `/app/requests/:id`, le bug n'est pas specifique a cette route. Dans l'en-tete (`<header>`), le bloc [titre+SLA] (`flex-1`) et la ligne de boutons d'action (`w-full lg:w-auto`) partageaient une meme ligne flex des que `lg:flex-row` s'active, sans `flex-wrap`. Si les boutons d'action (plusieurs boutons avec icone+texte) refusaient de descendre sous leur largeur naturelle, tout le budget restant — y compris en dessous de zero — etait retire du bloc titre, dont `min-w-0` autorise justement un retrecissement illimite. Le bloc SLA interne (`lg:w-72 lg:shrink-0`) aggrave l'effet en refusant lui-meme toute reduction. Resultat a certaines largeurs desktop intermediaires : le `<h1>` du titre se retrouvait ecrase a quasiment 0px de large, forcant le navigateur a placer chaque caractere sur sa propre ligne (`break-words` a l'extreme).

Correction: ajout de `flex-wrap` sur l'en-tete — la ligne de boutons d'action passe desormais a la ligne suivante si la place manque, au lieu d'ecraser le titre. Ajout de `lg:flex-wrap` sur le sous-bloc titre/SLA et `min-w-[12rem]` sur le conteneur du titre (au lieu de `min-w-0`) — le bloc SLA (288px fixe) passe lui aussi a la ligne plutot que de forcer le titre sous une largeur lisible. Comme le composant est partage, la correction s'applique automatiquement a tous les contextes (`requests`, `myTickets`, `queue`, `supervision`, `chiefInbox`, `departmentInbox`, `direction`, `dg`, `slaCenter`, `admin`).

Verification: `npx tsc --noEmit` sans nouvelle erreur imputable au fichier (baseline preexistante inchangee) ; `npx eslint` — 3234 problemes, tous confirmes `prettier/prettier` via sortie JSON agregee, zero erreur de logique.

## 2026-07-28 - Audit responsive detail ticket : garde-fou largeur des menus d'action

Demande: rendre `app.requests.$id.tsx` responsive sur desktop/tablette/telephone sans bug ni crash.

Module: MOD-REQUEST (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Constat: un audit ligne par ligne du fichier a montre qu'un travail responsive etendu avait deja ete applique (grille 70/30 -> colonne unique avant `xl`, en-tete/SLA empilable, stepper 5 colonnes sans scroll, onglets `overflow-x-auto`, listes fichiers/commentaires empilables) et documente (voir note "responsive multi-ecrans" ci-dessus). Verification `tsc --noEmit` : aucune nouvelle erreur, seulement la baseline preexistante deja connue (typage `fetchDirections`/`Direction[]`) — le fichier compile proprement apres cet important volume de changement.

Correction apportee: seul residu identifie — les 3 menus deroulants de l'en-tete (`Reassigner`, `Priorite`, `Service`) sont positionnes en `absolute right-0` avec une largeur minimale fixe et aucun plafond de largeur, un risque theorique de debordement horizontal sur tres petit ecran si leur bouton declencheur se retrouve pres du bord gauche. Ajout de `max-w-[calc(100vw-1.5rem)]` sur les trois, sans changer position, contenu ni comportement.

Verification: `npx tsc --noEmit` sans nouvelle erreur (baseline inchangee) ; `npx eslint` — 3234 problemes, tous confirmes `prettier/prettier` via sortie JSON agregee, zero erreur de logique. Test visuel navigateur multi-largeurs non effectue dans cet environnement (session authentifiee indisponible — le backend local devient intermittemment non-reactif lors des tentatives de connexion, cause non liee a ce changement) ; a verifier manuellement par l'utilisateur a 375px/768px/1440px.

## 2026-07-28 - Performance frontend : chargements plus rapides

Demande: reduire la lenteur visible avant l'affichage des pages et des donnees, notamment l'ecran logo/spinner mobile.

Module: frontend global / MOD-AUTH / MOD-PERSONAL.

Fichiers modifies:
- `frontend/src/router.tsx`
- `frontend/src/components/route-transition.tsx`
- `frontend/src/lib/api/client.ts`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: le fallback global de route etait affiche immediatement (`defaultPendingMs: 0`), les transitions remettaient un wrapper anime cle par `pathname` autour de l'application, et le client API chargeait la session par imports dynamiques repetes pendant les requetes. Le cache React Query etait aussi court par defaut et relancait des refetchs au focus/reconnexion.

Correction: cache global React Query porte a 1 minute avec conservation 10 minutes, refetch automatique au focus/reconnexion desactive, retry query desactive pour echouer vite si le backend ne repond pas, preload conserve 30 secondes, splash pending retarde a 300 ms avec duree minimale courte, transition globale remplacee par un rendu direct sans remount, imports session du client API rendus statiques. Aucun endpoint, role, permission, workflow ou donne metier n'est modifie.

Verification: `git diff --check` cible OK; `npm run build` cote frontend OK apres relance avec autorisation d'acces. L'ancien avertissement Vite sur `session.ts` importe a la fois dynamiquement et statiquement n'apparait plus; seuls les avertissements de chunks volumineux preexistants restent visibles.

## 2026-07-28 - Layout mobile : espacement bas avant navigation

Demande: sur l'accueil mobile, conserver entre la derniere section de contenu et la barre de navigation le meme espacement visuel qu'entre les sections de cartes.

Module: MOD-PERSONAL / layout applicatif.

Fichiers modifies:
- `frontend/src/components/app-layout.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: augmentation du padding bas mobile du conteneur principal avec prise en compte de `env(safe-area-inset-bottom)`, et positionnement de la barre mobile au-dessus de cette zone sure. Le contenu garde maintenant de l'air avant le menu fixe sans modifier les items, routes, roles ou donnees.

Verification: `git diff --check` cible OK; `npm run build` cote frontend OK apres relance avec autorisation d'acces. Seuls les avertissements Vite preexistants restent visibles (imports dynamiques/chunks volumineux).

## 2026-07-28 - Mes demandes : filtres visuellement distincts sur mobile

Demande: dans la zone de filtres encerclée de `Mes demandes`, chaque champ doit etre distinct a l'affichage.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `frontend/src/routes/app.requests.index.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: retrait du conteneur filtre unique en `GlassCard` et remplacement par une grille responsive ou chaque champ (recherche, statut, origine, periode, dates personnalisees, effacement) possede sa propre bordure, son fond et son espacement. Les valeurs, filtres, requetes API et comportements restent inchanges.

Verification: `git diff --check` cible OK; `npm run build` cote frontend OK apres relance avec autorisation d'acces. Seuls les avertissements Vite preexistants restent visibles (imports dynamiques/chunks volumineux).

## 2026-07-28 - Detail ticket responsive multi-ecrans

Demande: rendre `frontend/src/routes/app.requests.$id.tsx` responsive sur desktop, tablette et telephone, sans bug ni crash.

Module: MOD-REQUEST (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: ajustement UI uniquement du detail ticket: conteneur fluide avec paddings progressifs, grille principale repliee en une colonne avant `xl`, en-tete ticket/SLA vertical sur petits ecrans, titre/reference longs contenus dans la carte, stepper 5 etapes compresse sans scroll horizontal, onglets avec scroll local de secours, panneaux et listes fichiers/commentaires/actions empiles sur mobile puis horizontaux quand l'espace le permet. Aucun workflow, endpoint, role, permission ou calcul metier n'est modifie.

Verification: `npm run build` cote frontend OK apres relance avec autorisation d'acces; seuls les avertissements Vite preexistants restent visibles (imports dynamiques/chunks volumineux).

## 2026-07-28 - Stepper ticket : etape active en vert (couleur bouton) au lieu de bleu

Demande: la pastille bleue du stepper representant l'etape actuelle doit prendre la couleur verte des boutons de l'application.

Module: MOD-REQUEST (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: dans `TicketLifecycleStepper`, la classe de l'etape `active` passe de `border-sky-500 bg-sky-500 text-white shadow-sky-500/25` (bleu) a `border-primary bg-primary text-primary-foreground shadow-primary/25` (vert `--primary`, meme variable que `gradient-primary` utilisee par les boutons d'action principaux de l'app). Les etapes `done` (vert emeraude), `warning` (ambre) et `pending` (neutre) restent inchangees.

Verification: `npx tsc --noEmit` sans nouvelle erreur imputable au fichier (baseline preexistante inchangee).

## 2026-07-28 - Detail ticket : conteneur d'onglets et cartes laterales alignes sur la charte graphique

Demande: les zones entourees (conteneur d'onglets central + cartes Intervenants/Details de la demande) doivent adopter la charte graphique de l'application.

Module: MOD-REQUEST (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: le conteneur d'onglets et `sideCardClass` (Intervenants/Details de la demande/RequesterCard) utilisaient un degrade CSS bespoke (`bg-[radial-gradient(...)]` + `border`/`shadow-sm`/`backdrop-blur` manuels) different du systeme de design partage `glass`/`glass-strong` (`styles.css`), deja utilise ailleurs dans ce meme fichier via `GlassCard` (panneaux SLA depasse, priorite, rejet, reouverture, appreciation) et dans le reste de l'application.

Correction: remplacement des classes bespoke par l'utilitaire `glass-strong` (memes variables `--glass-bg-strong`/`--glass-border`/`--glass-shadow-lg` que partout ailleurs dans l'app), en conservant le rayon (`rounded-[18px]`) et les paddings existants. L'en-tete ticket (carte haute au-dessus du contenu) n'etait pas entouree dans la demande et conserve son propre style.

Verification: `npx tsc --noEmit` sans nouvelle erreur imputable au fichier (baseline preexistante inchangee) ; `npx eslint` — 3232 problemes, tous confirmes `prettier/prettier` via sortie JSON agregee, zero erreur de logique. Verification visuelle en navigateur non effectuee (pas de session authentifiee disponible dans cet environnement) — a confirmer manuellement par l'utilisateur.

## 2026-07-28 - Alignement colonnes : reduction de la limite du Journal au lieu d'etirer la colonne laterale

Demande: les deux colonnes (Journal des actions / colonne laterale) doivent se terminer au meme niveau qu'indique par une barre verte tracee juste apres le 3e evenement du journal, en respectant la position du bouton `Voir tout` — et l'espace vide cree par la precedente tentative d'etirement (`flex-1`) doit disparaitre.

Module: MOD-REQUEST (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `frontend/src/components/workflow-timeline.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: la session precedente avait etire la colonne laterale (`items-stretch` + `flex-1` sur sa derniere carte) pour rattraper la hauteur du `Journal des actions`, ce qui creait un grand vide visuel dans la carte etiree — juge pire que l'ecart initial.

Correction: approche inversee. `items-stretch` retire (retour a `items-start`), `flex-1` retire de la derniere carte laterale (`RequesterCard`/`Details de la demande`) — plus aucun etirement force. A la place, `WorkflowTimeline` reduit sa synthese par defaut de 5 a 3 evenements (`events.slice(0, 3)`, controle `Voir tout` visible des que `events.length > 3`), rapprochant naturellement la hauteur par defaut du Journal de celle de la carte `Details de la demande` repliee, sans espace vide artificiel.

Verification: `npx tsc --noEmit` sans nouvelle erreur imputable aux fichiers touches (baseline preexistante inchangee sur `app.requests.$id.tsx` ; aucune erreur sur `workflow-timeline.tsx`).

## 2026-07-28 - Detail ticket, libelles courts des onglets Journals et SLA

Demande: remplacer le libelle d'onglet `Journal des actions` par `Journals` et `Activite SLA` par `SLA`.

Module: MOD-REQUEST (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: seuls les labels visibles de `detailTabs` sont raccourcis (`Journals`, `SLA`). Les cles internes (`journal`, `sla`), le contenu des onglets, la timeline et les calculs SLA restent inchanges.

Verification: inspection ciblee des labels `Journals`/`SLA` dans `app.requests.$id.tsx` OK ; `git diff --check` OK.

## 2026-07-28 - Alignement bas de colonne entre Journal des actions et Details de la demande

Demande: les deux colonnes (contenu central / colonne laterale) doivent se terminer au meme niveau — la colonne laterale s'arretait beaucoup plus haut, laissant un grand vide sous la carte `Details de la demande`.

Module: MOD-REQUEST (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: la grille principale utilisait `items-start`, donc chaque colonne gardait sa hauteur intrinseque sans egard a l'autre. Depuis que `Details de la demande` se replie par defaut derriere `Voir tout` (session precedente), la colonne laterale est devenue nettement plus courte que le `Journal des actions`, creant un ecart visuel bas de page.

Correction: la grille passe de `items-start` a `items-stretch`. La colonne laterale (`aside > div`) recoit `h-full` pour occuper toute la hauteur disponible. La derniere carte visible de cette colonne recoit `flex-1` pour absorber l'espace restant et faire coincider son bord inferieur avec celui de la colonne centrale : `RequesterCard` (toujours en dernier quand affichee, vue non-demandeur) sinon `Details de la demande` (vue demandeur, quand `RequesterCard` est absente).

Verification: `npx tsc --noEmit` sans nouvelle erreur imputable au fichier (baseline preexistante inchangee) ; `npx eslint` — 3233 problemes, tous confirmes `prettier/prettier` via sortie JSON agregee, zero erreur de logique.

## 2026-07-28 - Ligne d'onglets du detail ticket sur une seule ligne

Demande: les onglets (`Description`, `Journal des actions`, `Commentaires`, `Fichiers`, `Activite SLA`, `Traitement`) doivent tenir sur une seule ligne — supprimer le bouton `Tous les evenements` qui forcait `Traitement` a passer a la ligne.

Module: MOD-REQUEST (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: la ligne d'onglets utilisait `flex-wrap` et partageait sa largeur avec le bouton decoratif `Tous les evenements` (affiche uniquement quand l'onglet `Journal des actions` est actif, sans `onClick` ni logique de filtrage reelle — un placeholder jamais branche). Sur les largeurs d'ecran habituelles, la somme des onglets + ce bouton depassait la largeur disponible et `Traitement` (dernier onglet) passait sur une deuxieme ligne.

Correction: suppression du bouton `Tous les evenements` (aucune fonctionnalite reelle derriere, donc rien n'est perdu). La ligne d'onglets passe de `flex-wrap` a `overflow-x-auto` (scroll horizontal de secours si la largeur venait a manquer, ex. mobile tres etroit) pour garantir que tous les onglets restent sur une seule ligne.

Verification: `npx tsc --noEmit` sans nouvelle erreur imputable au fichier (baseline preexistante inchangee) ; `npx eslint` — 3233 problemes, tous confirmes `prettier/prettier` via sortie JSON agregee, zero erreur de logique.

## 2026-07-28 - Journal des actions, libelle du controle harmonise en Voir tout

Demande: appliquer au `Journal des actions` la meme terminologie `Voir tout`/`Reduire` que les cartes `Details de la demande`/`Intervenants`, en gardant le bouton existant (pas de doublon) — alternative proposee et validee apres une premiere clarification sur la position exacte.

Module: MOD-REQUEST (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/components/workflow-timeline.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: renomme uniquement les libelles du bouton d'expansion existant dans `WorkflowTimeline` — `"Voir plus d'evenements"` -> `"Voir tout"`, `"Reduire les evenements"` -> `"Reduire"`. Position (bas de la liste, centre), limite (5 evenements par defaut), icone (`ChevronDown` rotatif) et logique (`expanded`/`setExpanded`) inchangees. Aucun bouton supplementaire ajoute en haut de la section — le controle existant est juge suffisant, seule la coherence textuelle avec les autres cartes etait demandee.

Verification: `npx tsc --noEmit` sans nouvelle erreur sur `workflow-timeline.tsx`.

## 2026-07-28 - Detail ticket, controle Voir tout sur la carte Details de la demande

Demande: ajouter sur la carte `Details de la demande` le meme controle `Voir tout` deja present sur la carte `Intervenants`.

Module: MOD-REQUEST (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: ajout d'un etat local `showAllDetails` (meme pattern que `showAllParticipants` de la carte Intervenants) et d'un bouton `Voir tout`/`Reduire` identique en style et icones (`ArrowUpRight` / `ChevronDown rotate-180`, `text-primary`) dans l'en-tete de la carte `Details de la demande`. Par defaut, seul le groupe **Demande** (Categorie, Cree le, Mise a jour, ID) reste visible ; les groupes **Demandeur**, **Traitement** et **SLA** (ajoutes dans la restructuration precedente) sont masques jusqu'au clic sur `Voir tout`. Toutes les donnees sont deja calculees au rendu — l'expansion ne declenche aucun appel reseau supplementaire.

Verification: `npx tsc --noEmit` sans nouvelle erreur imputable au fichier (baseline preexistante inchangee) ; `npx eslint` — 3243 problemes, tous confirmes `prettier/prettier` via sortie JSON agregee, zero erreur de logique.

## 2026-07-28 - Detail ticket, restructuration de la carte Details de la demande

Demande: reproduire exactement une maquette fournie pour la carte laterale `Details de la demande` — 4 groupes avec icone circulaire coloree (Demande / Demandeur / Traitement / SLA).

Module: MOD-REQUEST (BR-UI-TICKET-DETAIL-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: la carte est reorganisee en 4 groupes iconographies (icone circulaire coloree + libelle majuscule) au lieu d'une liste plate : **Demande** (emeraude) — Categorie, Cree le, Mise a jour, ID de la demande (inchange) ; **Demandeur** (bleu ciel, nouveau) — Direction/Departement/Service du demandeur lui-meme (distinct du service assigne au traitement), affiche seulement pour les demandeurs internes (`authorType === "internal"`), plus le nom du demandeur (toujours affiche) ; **Traitement** (violet, renomme) — les anciens champs `Direction`/`Service` (qui representaient deja le service assigne au ticket) sont renommes `Direction en charge`/`Service en charge` et complementes d'un nouveau champ `Departement en charge` ; `Agent en charge` conserve sa condition d'affichage existante (`isRequesterView`) ; **SLA** (ambre, nouveau) — ligne de synthese "SLA depasse"/"Dans les delais" reprenant `slaOver` deja calcule, sans reintroduire la mini-carte SLA retiree precedemment (pas de courbe/Objectif/Consomme). Departement resolu via `Unit.department_name`, deja expose par l'API directions/unites — aucun nouvel appel reseau.

Verification: `npx tsc --noEmit` sans nouvelle erreur imputable au fichier (erreurs preexistantes non liees sur le typage `fetchDirections`/`Direction[]`, y compris sur le nouvel appel `directions.find` pour le demandeur, meme categorie d'erreur preexistante) ; `npx eslint` — 3224 problemes, tous confirmes `prettier/prettier` via sortie JSON agregee, zero erreur de logique.

## 2026-07-28 - Detail ticket, stepper sans scroll horizontal

Demande: le parcours/stepper de la demande ne doit pas etre scrollable ni couper une etape; les 5 etapes doivent rester visibles dans la carte.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: retrait de `overflow-x-auto` et de `min-w-[720px]` sur `TicketLifecycleStepper`. Le stepper utilise desormais une grille fixe `grid-cols-5`, avec connecteurs positionnes entre les cellules et tailles de labels responsives, afin de garder `Ouverture`, `Qualification`, `Traitement`, `Valider`, `Fermeture` visibles ensemble.

Verification: `npm run build` cote frontend OK, avec les avertissements Vite preexistants sur imports dynamiques et chunks volumineux.

## 2026-07-28 - Fusion des noeuds journal pour un commentaire avec piece jointe

Demande: quand un commentaire est accompagne d'un fichier (envoi combine), le `Journal des actions` affichait deux noeuds separes ("Piece jointe ajoutee — X" puis "Commentaire ajoute") au lieu de montrer clairement que les deux ont ete crees ensemble — reference donnee : le rendu d'un commentaire avec photo jointe sur Facebook (un seul bloc).

Module: MOD-REQUEST (BR-ATTACHMENT-001).

Fichiers modifies:
- `backend/api/routes/RouteRequest.py`
- `frontend/src/lib/api/requests.ts`
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/API_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: `upload_attachment` cree systematiquement un evenement `attachment_added` a chaque upload, y compris lorsque l'upload fait partie du flux combine "joindre un fichier + commentaire" (`commentMut` uploade d'abord le fichier puis cree le commentaire). Le commentaire cree ensuite son propre evenement `comment_added`, deja enrichi des infos de la piece jointe (chip fichier, clic `Voir`) depuis une correction anterieure — d'ou le doublon visuel dans le journal.

Correction: ajout du parametre optionnel `skip_timeline_event` (query, defaut `false`) sur `POST /requests/{id}/attachments` — quand `true`, aucun evenement `attachment_added` n'est cree. `uploadAttachment()` (`requests.ts`) accepte desormais un 4e parametre `skipTimelineEvent` transmis en query string. Le flux d'envoi combine dans `app.requests.$id.tsx` (`commentMut`) l'appelle avec `skipTimelineEvent=true`, de sorte que seul l'evenement `comment_added` (commentaire + piece jointe rattachee, un seul noeud) apparaisse dans le journal. L'upload standalone lors de la creation d'une demande (`new-request-form.tsx`) n'est pas concerne et garde son evenement `attachment_added` propre.

Verification: `python -m compileall api/routes/RouteRequest.py` OK ; `npx tsc --noEmit` sans nouvelle erreur imputable aux fichiers touches (erreurs preexistantes non liees sur `app.requests.$id.tsx`/`app.requests.index.tsx`, typage `fetchDirections`/`Direction[]`).

## 2026-07-28 - Detail ticket, bouton Voir tout des intervenants

Demande: faire fonctionner `Voir tout` dans la carte laterale `Intervenants`, avec possibilite de reduire ensuite.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: `Voir tout` n'est plus un simple texte statique: c'est un bouton qui bascule entre la synthese courte des 4 premiers intervenants et la liste complete. En mode liste complete, le libelle devient `Reduire` pour revenir a l'affichage court. Les participants restent calcules depuis les donnees existantes du ticket/timeline.

Verification: `npm run build` cote frontend OK, avec les avertissements Vite preexistants sur imports dynamiques et chunks volumineux.

## 2026-07-28 - Correction affichage image dans la modal de previsualisation

Demande: dans la modal de previsualisation (`Voir`), l'image ne s'affichait pas correctement.

Module: MOD-REQUEST (BR-ATTACHMENT-001).

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: l'`<img>` de la modal utilisait la classe `max-w-none` (sans aucune limite de largeur), ce qui force le navigateur a l'afficher a sa taille pixel native. Pour un fichier volumineux (ex. capture d'ecran haute resolution de 1.4 Mo), la taille native depasse largement la fenetre de la modal : a 100% de zoom, seul un minuscule extrait centre de l'image restait visible, donnant l'impression d'un rendu casse/flou au lieu de l'image entiere.

Correction: remplace `max-w-none` par `max-h-[70dvh] max-w-full` sur l'`<img>`. A 100% (`previewZoom=1`), l'image est desormais mise a l'echelle pour tenir entierement dans la modal en conservant son ratio. Le zoom (`ZoomIn`/`ZoomOut`, transform CSS `scale()`) continue d'agrandir au-dela de cette taille ajustee, le conteneur restant `overflow-auto` pour permettre le defilement une fois zoome.

Verification: `npx tsc --noEmit` sans nouvelle erreur imputable au fichier (erreurs preexistantes non liees sur le typage `fetchDirections`/`Direction[]`).

## 2026-07-28 - Detail ticket, onglet Traitement et ouverture fichiers depuis le journal

Demande: deplacer les actions disponibles dans un onglet `Traitement` apres `Activite SLA`, puis permettre le clic sur une piece jointe du `Journal des actions` pour ouvrir directement l'onglet `Fichiers` et l'apercu du fichier.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `frontend/src/components/workflow-timeline.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: ajout de l'onglet `Traitement` qui rend le panneau `requestActionsPanel` existant, suppression de l'ancien rendu autonome des actions en bas du dossier, et ajout d'un callback optionnel `onOpenAttachment` a `WorkflowTimeline`. Quand un evenement porte `attachment_id` ou `filename`, son libelle/chip fichier devient cliquable ; la page active l'onglet `Fichiers` puis reutilise `handleAttachmentFile(..., "open")` pour afficher l'apercu. Aucun endpoint, permission ou workflow n'est modifie.

Verification: `npm run build` cote frontend OK, avec les avertissements Vite preexistants sur imports dynamiques et chunks volumineux.

## 2026-07-28 - Correction bug critique : storage_path des pieces jointes corrompu a chaque affichage

Demande: au clic sur `Voir`, l'utilisateur obtient "Impossible d'acceder a la piece jointe : Chemin invalide."

Module: MOD-REQUEST (pieces jointes, BR-ATTACHMENT-001).

Fichiers modifies:
- `backend/api/routes/RouteRequest.py`
- Donnees: reparation ponctuelle de la table `attachment` (5 lignes corrompues restaurees depuis les fichiers reels sur disque)
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: `list_attachments` et `upload_attachment` faisaient `item.storage_path = storage.presigned_url(item.storage_path)` directement sur l'entite SQLAlchemy renvoyee par la session (`get_by_id`/`list_by_request`/`svc.create`), au lieu de ne modifier qu'une copie de reponse. `get_db()` (`backend/api/dependencies.py`) commit la session a la fin de **chaque** requete, y compris les `GET` en lecture seule. Resultat : chaque appel a `GET /requests/{id}/attachments` (donc chaque ouverture de l'onglet Fichiers) re-presignait un `storage_path` deja presigne et persistait ce resultat en base, empilant un nouveau prefixe `/api/v1/requests/download/` a chaque fois — jusqu'a produire un chemin qui echoue au controle anti-traversal de repertoire dans `download_file` (`HTTPException 400 "Chemin invalide."`). Verifie en base : les 6 pieces jointes existantes avaient entre 1 et plus de 30 prefixes empiles.

Correction: `list_attachments` et `upload_attachment` construisent desormais une instance `AttachmentResponse.from_orm(...)` dediee et n'assignent l'URL presignee que sur cette copie ; l'entite ORM suivie par la session n'est plus jamais mutee pour de la presentation. Reparation ponctuelle des 5 lignes deja corrompues en base : `storage_path` reconstruit a `requests/{request_id}/{fichier reel}` en retrouvant le prefixe hexadecimal unique (intact malgre la corruption) dans chaque fichier present sur disque (`backend/uploads/requests/{id}/`).

Verification: `python -m compileall api/routes/RouteRequest.py` OK. Verification en base (`SELECT storage_path FROM attachment`) : les 5 chemins corrompus sont desormais identiques aux fichiers reels sur disque. Test E2E via `curl` (login admin puis `GET /attachments`) tente mais non conclu — le serveur de dev local a cesse de repondre pendant la requete de login (soupcon : hachage Argon2 bloquant potentiellement la boucle asyncio mono-processus en dev, sujet distinct hors perimetre de cette correction) ; a reverifier manuellement dans le navigateur apres redemarrage du backend si besoin.

## 2026-07-28 - Previsualisation piece jointe en modal zoomable

Demande: au clic sur `Voir` (image ou PDF), afficher le fichier dans une modal adaptee au contenu et zoomable, au lieu d'ouvrir un nouvel onglet ; s'assurer que le telechargement fonctionne.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: `handleAttachmentFile` n'ouvre plus de fenetre popup pour le mode `"open"` (source de blocages navigateur) — elle recupere le blob authentifie puis alimente un nouvel etat `previewFile` (`url`, `filename`, `mimeType`) affiche dans une modal `Dialog` dediee. Selon le `mime_type` : image → `<img>` avec zoom pilote par l'etat `previewZoom` (boutons `ZoomOut`/`ZoomIn`, 100%-300% par pas de 50%) ; `application/pdf` → `<iframe>` (viewer PDF natif du navigateur, deja zoomable/paginable) ; autre type → message "apercu non disponible" avec bouton de telechargement. La modal expose aussi un bouton `Telecharger` qui declenche le meme telechargement par ancre `download` que l'action `Telecharger` de la liste des pieces jointes (deja fonctionnelle via `fetchAttachmentFile` + blob + ancre — verifiee, sans changement necessaire cote logique de telechargement). Le blob de previsualisation est revoque via `URL.revokeObjectURL` a la fermeture de la modal (`closePreview`) et au demontage du composant. Aucun changement de route, permission ni donnee.

Verification: `npx tsc --noEmit` sans nouvelle erreur imputable au fichier (erreurs preexistantes non liees sur le typage `fetchDirections`/`Direction[]`) ; `npx eslint` sans probleme hors bruit prettier CRLF preexistant sur tout le depot (3128 occurrences, toutes `prettier/prettier`, verifie via sortie JSON agregee).

## 2026-07-28 - Detail ticket, Commentaires redevient un onglet dedie

Demande: dans l'onglet Commentaires, afficher chaque intervenant avec son commentaire et les fichiers qu'il a joints a ce commentaire — l'onglet `Commentaires` doit exister a part entiere, distinct du `Journal des actions`.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: revient sur la fusion du 2026-07-28 qui affichait les commentaires sous la timeline du `Journal des actions`. Le panneau `commentsPanel` (liste des intervenants avec commentaire + chip piece jointe/`Voir`, plus le formulaire d'envoi combine) est desormais rendu dans sa propre section gardee par `activeDetailTab === "comments"`, separee de la section `Journal des actions` qui ne contient plus que `WorkflowTimeline`. Le bouton d'onglet `Commentaires` bascule simplement `activeDetailTab` comme les autres onglets (retrait du redirect-vers-Journal + scroll automatique via `commentsPanelRef` qui n'a plus lieu d'etre). Aucun changement de route, permission, donnee ou workflow.

Verification: `npx tsc --noEmit` sans nouvelle erreur imputable au fichier (erreurs preexistantes non liees sur le typage `fetchDirections`/`Direction[]`) ; `npx eslint` sans probleme hors bruit prettier CRLF preexistant sur tout le depot.

## 2026-07-28 - Detail ticket, retrait de la carte SLA de la colonne laterale

Demande: retirer la carte `SLA` (mini-graphique + Depassement/Objectif/Consomme) de la colonne laterale, signalee redondante par capture d'ecran annotee ; Intervenants remonte a sa place.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: suppression de la section `SLA` (mini-courbe SVG, Depassement/Marge, Objectif/Consomme) de la colonne laterale. La colonne droite ne contient plus que `Intervenants` puis `Details de la demande`. La variable `slaOverageHours` (devenue inutilisee) est retiree. L'information SLA reste disponible via le bloc integre a l'en-tete du ticket (pourcentage, temps ecoule/objectif, barre de progression). Aucun changement de route, permission, donnee ou workflow.

Verification: `npx tsc --noEmit` sans nouvelle erreur imputable au fichier (erreurs preexistantes non liees sur le typage `fetchDirections`/`Direction[]`) ; `npx eslint` sans probleme hors bruit prettier CRLF preexistant sur tout le depot.

## 2026-07-28 - Commentaire et piece jointe envoyes ensemble (comme WhatsApp)

Demande: pouvoir joindre un fichier a un commentaire et envoyer les deux en un seul geste (clic sur Publier), avec une seule trace dans le journal des actions montrant qui a commente avec une piece jointe a l'appui — au lieu de deux actions/entrees separees.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `backend/api/routes/RouteRequest.py`
- `frontend/src/routes/app.requests.$id.tsx`
- `frontend/src/lib/api/requests.ts`
- `frontend/src/lib/mock-data.ts`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/API_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: le trombone du panneau Commentaires ne declenche plus un upload immediat — le fichier est "stage" en memoire (apercu avec bouton retirer, sans requete reseau). Au clic sur `Publier`, la mutation combinee uploade d'abord la piece jointe (`uploadAttachment`) puis cree le commentaire (`createComment`) en lui passant l'`attachment_id` obtenu, dans le meme geste utilisateur. Cote backend, `_CommentBody` accepte desormais un `attachment_id` optionnel ; `create_comment` verifie que la piece jointe appartient bien a la demande puis stocke `attachment_id`/`filename`/`mime_type`/`size_bytes` dans les `infos` de l'evenement `comment_added` — memes cles que l'evenement `attachment_added` existant, donc **aucune modification necessaire** de `workflow-timeline.tsx` : le Journal des actions affiche deja automatiquement un chip avec le nom du fichier sur l'entree de commentaire concernee. Le panneau Commentaires affiche en plus un lien `Voir` sur la piece jointe (reutilise `handleAttachmentFile`). Aucun changement de route, permission ni de modele/migration (reutilisation du champ `infos` JSON existant).

Verification: `python -m compileall api/routes/RouteRequest.py` OK ; `npx tsc --noEmit` sans nouvelle erreur imputable aux fichiers touches (erreurs preexistantes non liees sur `app.requests.$id.tsx`, typage `fetchDirections`/`Direction[]`) ; `npx eslint` sans probleme hors bruit prettier CRLF preexistant sur tout le depot.

## 2026-07-28 - Detail ticket, onglet Description avant Journal

Demande: ajouter dans la barre d'onglets centrale un onglet `Description` avant `Journal des actions`, sans toucher aux zones commentaires/actions annotees en rouge.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: ajout du type d'onglet `description`, insertion de l'onglet `Description` en premiere position et affichage de `request.description` dans la carte centrale. Le journal, le bouton `Voir plus d'evenements`, les commentaires et les actions ne sont pas modifies.

Verification: `npm run build` cote frontend OK, avec les avertissements Vite preexistants sur imports dynamiques et chunks volumineux.

## 2026-07-28 - Detail ticket, fusion Journal des actions et Commentaires

Demande: regrouper le Journal des actions et les Commentaires dans la meme carte au lieu de deux blocs separes.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: `commentsPanel` est deplace a l'interieur de la section de l'onglet `Journal des actions`, juste sous `WorkflowTimeline`, separe par une bordure — les deux sont donc visibles ensemble des que cet onglet est actif. Le bloc bas ne contient plus que la carte `Actions` seule (largeur reduite `sm:max-w-sm`, l'ancien conteneur partage `bottomPanelClass` devenu inutile a ete retire). Le clic sur l'onglet `Commentaires` continue de basculer vers `Journal des actions` puis de defiler jusqu'au bloc commentaires (`commentsPanelRef`), desormais coherent avec sa nouvelle position. Aucun changement de donnees, permission ou mutation.

Verification: `npx tsc --noEmit` sans nouvelle erreur imputable au fichier (erreurs preexistantes non liees sur le typage `fetchDirections`/`Direction[]`) ; `npx eslint` sans probleme hors bruit prettier CRLF preexistant sur tout le depot.

## 2026-07-28 - Detail ticket, fusion visuelle commentaires actions

Demande: rattacher visuellement la partie `Commentaires` avec les actions dans le bas du detail demande/ticket.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: le bloc bas utilise desormais un seul conteneur EDG Connect pour regrouper `Commentaires` et `Actions`. Les commentaires restent a gauche et les actions a droite sur desktop, sans modifier les permissions ni les mutations existantes.

Verification: `npm run build` cote frontend OK, avec les avertissements Vite preexistants sur imports dynamiques et chunks volumineux.

## 2026-07-28 - Detail ticket, retrait des blocs redondants Description et raccourci fichiers

Demande: retirer du detail ticket le bloc `Description` (sous l'onglet Journal) et le raccourci `Voir / telecharger les fichiers` de la carte `Actions`, signales redondants par capture d'ecran annotee.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: suppression de la section `Description` affichee sous l'onglet Journal des actions (texte de la demande, redondant a cet emplacement). Suppression du bouton `Voir / telecharger les fichiers` dans la carte `Actions` (redondant avec l'onglet `Fichiers` qui offre deja apercu/telechargement par piece jointe) ; `hasRequestActions` ne tient plus compte du nombre de pieces jointes. Aucun changement de route, permission, donnee ou workflow ; l'onglet Fichiers et son contenu restent inchanges.

Verification: `npx tsc --noEmit` sans nouvelle erreur imputable au fichier (erreurs preexistantes non liees sur le typage `fetchDirections`/`Direction[]`) ; `npx eslint` sans probleme hors bruit prettier CRLF preexistant sur tout le depot.

## 2026-07-28 - Detail ticket, bloc commentaires actions aligne maquette

Demande: reproduire la partie basse entouree de la maquette du detail demande/ticket dans `app.requests.$id.tsx`, en gardant la charte EDG Connect.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: les commentaires sont rendus dans une carte bas de dossier toujours visible sous le journal, et les actions autorisees sont deplacees dans une carte compacte a droite des commentaires sur desktop. L'ancienne carte Actions de la colonne laterale et l'ancien contenu commentaires masque dans les onglets sont retires pour eviter les doublons. Les permissions, routes, API et workflows restent inchanges.

Verification: `npm run build` cote frontend OK, avec les avertissements Vite preexistants sur imports dynamiques et chunks volumineux.

## 2026-07-28 - Detail ticket, journal des actions aligne maquette

Demande: reproduire la zone centrale entouree de la maquette du detail demande/ticket, en conservant la charte graphique EDG.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `frontend/src/components/workflow-timeline.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: la carte `Journal des actions` adopte un rendu plus proche de la maquette: conteneur sombre/vert, onglets conserves, filtre journal stylise, timeline plus aeree avec icones lisibles, ligne de connexion, badges de statut et controle `Voir plus d'evenements` / `Reduire les evenements`. Les evenements restent issus des donnees reelles du ticket. Aucun changement de route, permission, API ou workflow.

Verification: `npm run build` cote frontend OK, avec les avertissements Vite preexistants sur imports dynamiques et chunks volumineux.

## 2026-07-28 - Detail ticket, raffinement des cartes laterales

Demande: rapprocher encore la partie droite entouree sur la maquette du detail demande/ticket.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: les cartes laterales utilisent un fond plus proche du dossier ticket premium, le mini-graphe SLA affiche maintenant une courbe avec surface remplie et point final, et la carte Intervenants devient une synthese limitee aux premiers intervenants tout en conservant le compteur total. Aucun changement de donnees source, route, permission, API ou workflow.

Verification: `npm run build` cote frontend OK, avec les avertissements Vite preexistants sur imports dynamiques et chunks volumineux.

## 2026-07-28 - Detail ticket, colonne laterale alignee maquette

Demande: reproduire plus fidelement les blocs entoures a droite dans la maquette du detail demande/ticket.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: la colonne droite n'est plus rendue comme une carte globale contenant des sous-cartes. Les blocs SLA, Intervenants, Details de la demande et Actions utilisent des cartes autonomes au meme style que la carte haute. Le mini-graphe SLA est affine en courbe progressive, les lignes d'intervenants sont allegees et les details sont presentes en liste separee par lignes fines. Aucun changement de donnees, route, permission, API ou workflow.

Verification: `npm run build` cote frontend OK, avec les avertissements Vite preexistants sur imports dynamiques et chunks volumineux.

## 2026-07-28 - Detail ticket, carte haute alignee maquette

Demande: reproduire plus fidelement la zone haute entouree sur la maquette du detail demande/ticket dans `app.requests.$id.tsx`.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: la reference, le titre, les badges, le bloc SLA et le parcours fixe a 5 etapes sont maintenant regroupes dans une carte haute autonome. Le bloc SLA de l'en-tete est renforce visuellement (separateur, pourcentage, horloge, barre), le stepper adopte une disposition plus proche de la maquette et le contenu journal/commentaires/fichiers est separe sous cette carte. Aucun changement de route, permission, API ou workflow.

Verification: `npm run build` cote frontend OK, avec les avertissements Vite preexistants sur imports dynamiques et chunks volumineux ; `git diff --check` OK.

## 2026-07-27 - Detail ticket en vraie grille dossier

Demande: corriger l'ecart visuel restant avec la maquette apres comparaison capture utilisateur, notamment la colonne droite trop basse et le doublon `Avancement de votre demande`.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: suppression du second parcours `Avancement de votre demande`, retrait des imports associes, transformation du detail en vraie grille desktop 70/30 des le haut de l'ecran. La colonne gauche contient le dossier ticket compact (en-tete, parcours unique, onglets) et la colonne droite SLA/Intervenants/Details/Actions demarre au meme niveau que le dossier, dans une carte separee. Aucun changement de route, permission, API ou workflow.

Verification: `npm run build` cote frontend OK, avec les avertissements Vite preexistants sur imports dynamiques et chunks volumineux.

## 2026-07-27 - Detail ticket avec onglets actifs et actions laterales

Demande: rapprocher encore `app.requests.$id.tsx` de la maquette de reference en gardant la charte EDG, sans changer routes, API, permissions ni workflow.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: ajout d'un vrai systeme d'onglets dans `RequestDetailPage` (`Journal des actions`, `Commentaires`, `Fichiers`, `Activite SLA`), deplacement des actions personnelles dans une carte `Actions` de la colonne droite, retrait des boutons personnels redondants de l'en-tete, ajustement de la grille principale vers une lecture 70/30 et conservation des donnees reelles existantes (timeline, commentaires, pieces jointes, SLA).

Verification: `npm run build` cote frontend OK, avec les avertissements Vite preexistants sur imports dynamiques et chunks volumineux.

## 2026-07-27 - Alignement fin du detail ticket sur la maquette dossier

Demande: faire correspondre exactement `app.requests.$id.tsx` a une maquette de reference (en-tete, stepper 5 etapes numerotees, onglets, colonne laterale SLA/Intervenants/Details).

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: remplacement du stepper dynamique `TicketComplianceTrace` (etapes variables Chef de service/Directeur, acteur+date par etape) par `TicketLifecycleStepper`/`buildFixedLifecycleSteps` : cycle de vie fixe a 5 etapes numerotees (Ouverture/Qualification/Traitement/Valider/Fermeture), ligne pleine pour les etapes franchies et pointillee pour les etapes a venir, desormais visible aussi cote demandeur (retrait de la restriction `!isRequesterView`). Colonne laterale reordonnee et completee pour correspondre a la maquette : carte SLA (deja presente) en premier, Intervenants en second, Details de la demande reecrit en liste verticale (Categorie, Direction, Service, Agent en charge, Cree le, Mise a jour, ID de la demande) avec bouton de copie presse-papier sur l'identifiant (ajoute aussi a cote de la reference en en-tete) ; retrait de la banniere "SLA depasse" redondante (mal positionnee par un `order` CSS manquant et absente de la maquette). Code mort supprime : `ComplianceStep(State)`, `EscalationRoleLevel`, `STATUS_RANK`, `isEscalationTraceEvent`, `isFormalTraceAction`, `escalationRoleLevel`, `latestFormalRoleEvent`, `complianceStepClass`. Aucun changement de route, permission, action ou endpoint.

Verification: `npx tsc --noEmit` sans nouvelle erreur imputable au fichier (erreurs preexistantes non liees sur le typage `fetchDirections`/`Direction[]`) ; `npx eslint` sans probleme hors bruit prettier CRLF preexistant sur tout le depot.

## 2026-07-27 - Detail ticket en disposition dossier

Demande: rapprocher l'affichage du detail demande/ticket d'une page dossier professionnelle, sans casser la charte graphique ni creer de composant parallele.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: `RequestDetailPage` reste le composant central reutilise par les contextes existants, mais son affichage est reorganise au format dossier ticket: en-tete avec reference, titre, statut, priorite, categorie et bloc SLA; parcours/timeline sous l'en-tete; journal des actions affiche en premier avec onglets visuels; commentaires presentes en fil; panneau d'actions lateral branche sur les mutations existantes; colonne droite SLA, intervenants et details de la demande. Aucun changement de route, permission ou workflow.

Verification: `npm run build` cote frontend OK, avec les avertissements Vite preexistants sur imports dynamiques/chunks volumineux.

## 2026-07-27 - Pieces jointes visibles et telechargeables

Demande: afficher les fichiers ajoutes a une demande et permettre de les voir ou telecharger depuis le detail.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `frontend/src/lib/api/client.ts`
- `frontend/src/lib/api/requests.ts`
- `frontend/src/routes/app.requests.$id.tsx`
- `backend/api/storage.py`
- `docs/codex/API_INDEX.md`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: la page detail demande/ticket charge maintenant les pieces jointes via `GET /requests/{id}/attachments` et affiche une section dediee avec nom, type, taille, date, statut de scan, action `Voir` et action `Telecharger`. Les fichiers sont recuperes en blob via une requete authentifiee avant ouverture ou telechargement. L'URL locale generee par `storage.presigned_url` pointe maintenant vers la route existante `/api/v1/requests/download/{path}`.

Verification: `python -m compileall backend/api/storage.py backend/api/routes/RouteRequest.py` OK ; `npm run build` cote frontend OK.

## 2026-07-27 - Acces personnel Mon espace pour tous les roles

Demande: garantir que `Mon espace` affiche et ouvre correctement les demandes personnelles pour tous les roles, comme pour le role utilisateur.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:
- `backend/api/routes/RouteRequest.py`
- `docs/codex/API_INDEX.md`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: l'acces detail d'une demande verifie maintenant d'abord si l'acteur connecte est le `requester_id` de la demande. Dans ce cas, l'acces personnel est autorise quel que soit son role metier, sans appliquer le perimetre service/direction. Le detail personnel, la lecture des commentaires et la suppression de commentaires gardent le mode demandeur proprietaire: commentaires internes non publics masques, suppression limitee aux propres commentaires.

Verification: compilation ciblee de `backend/api/routes/RouteRequest.py` OK. Test pytest cible `backend/tests/api/test_requests_baseline.py -k VuePersonnelleBaseline` tente mais non execute dans l'environnement disponible (`No module named pytest` avec Python global; lancement du venv bloque par Windows error 1920).

## 2026-07-27 - Verrouillage edition personnelle demandeur

Demande: corriger la modification d'une demande personnelle pour qu'elle fonctionne sans bug et reste alignee au cahier des charges.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:

- `frontend/src/lib/api/requests.ts`
- `backend/api/routes/RouteRequest.py`
- `backend/api/services/ServiceRequest.py`
- `docs/codex/API_INDEX.md`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: l'edition personnelle via `/requests/{id}/requester-edit` est desormais limitee au titre et a la description dans le type frontend, le schema backend et le service. Les champs internes (`category`, `priority`, `direction_id`, `unit_id`, `unity_id`) ne font plus partie du contrat demandeur et sont refuses par l'API (`extra=forbid`). Le service rejette aussi une edition vide sans champ autorise.

Verification: `python -m compileall backend/api/routes/RouteRequest.py backend/api/services/ServiceRequest.py` OK ; controles `rg` cibles OK sur le schema backend, le service et l'appel frontend `requesterEditRequest`.

## 2026-07-27 - Espaces frontend dedies Chef de Service / Chef Departement

Demande: chaque role doit avoir « son espace propre » — chief-service et chief-departement partageaient jusque-la exactement la meme page `/app/chief-inbox` (aucune route ni composant distinct), la seule difference etant desormais le perimetre de donnees cote backend (voir entree precedente du meme jour).

Module: MOD-CHIEF.

Fichiers modifies/crees:

- `frontend/src/routes/app.chief-inbox.tsx` (composant `ChiefInbox` exporte, rendu route-aware)
- `frontend/src/routes/app.department-inbox.tsx` (nouveau — reutilise `ChiefInbox`)
- `frontend/src/routes/app.department-inbox_.tickets.$id.tsx` (nouveau)
- `frontend/src/lib/ticket-navigation.ts`
- `frontend/src/routes/app.requests.$id.tsx` (contexte `departmentInbox`)
- `frontend/src/components/app-layout.tsx`
- `docs/codex/ROLE_INDEX.md`, `FRONTEND_INDEX.md`, `ROUTE_INDEX.md`, `MODULE_INDEX.md`, `BUSINESS_RULES.md`, `CHANGELOG_CODEX.md`

Correction: creation de la route `/app/department-inbox` (+ detail `/app/department-inbox/tickets/$id`), reservee a `chief-departement` (et `admin`), avec guard de role, titre et back-navigation propres. `/app/chief-inbox` reste reserve a `chief-service` (deja le cas via `requireRole`, aucun changement de guard necessaire). Les deux routes rendent le meme composant `ChiefInbox` (evite la duplication d'environ 600 lignes de logique/JSX) qui detecte l'espace courant via `useRouterState` pour adapter dynamiquement : le libelle d'en-tete et les messages vides (« service » vs « departement »), la cle de requete/cache (`chief-inbox` vs `department-inbox`), le lien de navigation vers le detail ticket (`ticketDetailRouteForList`) et la portee de la liste d'agents assignables (`unit_id` exact vs `direction_id` elargi). Navigation sidebar/mobile mise a jour pour proposer a chaque role son propre lien (plus de partage de l'entree « Boite de traitement » entre les deux roles).

Verification: `npx tsc --noEmit` sans nouvelle erreur imputable aux fichiers touches (erreurs preexistantes non liees dans d'autres fichiers) ; `npx eslint` sans probleme hors bruit prettier CRLF preexistant sur tout le depot.

## 2026-07-27 - Distinction fonctionnelle Chef de Service / Chef Departement

Demande: poursuivre l'alignement CDC des roles en donnant a `chief-departement` un perimetre reellement plus large que `chief-service` (jusque-la, les deux roles etaient des clones stricts partageant exactement le meme perimetre `unity_id`).

Module: MOD-CHIEF / MOD-REQUEST.

Fichiers modifies:

- `backend/api/core/ticket_actions.py`
- `backend/api/services/ServiceRequest.py`
- `backend/api/routes/RouteRequest.py`
- `backend/tests/api/test_ticket_actions.py`
- `frontend/src/routes/app.chief-inbox.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/ROLE_INDEX.md`
- `docs/codex/FRONTEND_INDEX.md`
- `docs/codex/MODULE_INDEX.md`
- `docs/codex/ROUTE_INDEX.md`
- `docs/codex/API_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: `chief-departement` et `chief-service` avaient la meme matrice de permissions ET le meme calcul de perimetre (`actor.unity_id` seul), sans jamais utiliser le mecanisme d'elargissement par organigramme deja disponible (utilise pour `director`). Un chef de departement ne pouvait donc jamais voir ni agir sur les tickets des autres services de son propre departement — la distinction CDC entre les deux roles etait purement nominale. Le listing principal `GET /requests` forcait meme `unit_id` (correspondance exacte) pour `chief-departement`, et le selecteur d'agent assignable du frontend interrogeait `/users?unit_id=...` sur l'unite exacte du chef, qui ne contient generalement aucun agent (les agents sont rattaches aux services, pas au noeud departement) — rendant l'assignation impossible en pratique pour ce role.

Correction: `chief-departement` beneficie desormais du meme mecanisme d'elargissement d'organigramme que `director` (departement + tous ses services descendants), applique de bout en bout : lecture/action ticket (`assert_ticket_scope`, `_guard_ticket_action`), assignation a un agent de n'importe quel service du departement (`assert_assignment_allowed` avec `allowed_scope_unity_ids`), listing principal et par-unite (`list_requests`, `_resolve_access`, `_check_unity_access`), et selecteur d'agent assignable cote frontend (`fetchUsers({ direction_id })` au lieu de `unit_id` pour ce role). `chief-service` reste strictement borne a son unite. Au passage, corrige une sur-permission existante ou `agent-support`/`chief-service` recevaient a tort un perimetre elargi dans `_resolve_access` (acces detail ticket).

Verification: `backend\venv\Scripts\pytest.exe backend\tests\api\test_ticket_actions.py -q` OK avec 69 tests passes (nouveau test `test_chief_departement_can_assign_across_department_scope`). Note: `backend\tests\api\test_requests_baseline.py` presente 21 echecs preexistants non lies a cette intervention — ce fichier de tests n'a pas ete mis a jour lors du renommage de roles du 2026-07-23 et utilise encore les libelles `agent`/`chief` obsoletes ; a traiter separement.

## 2026-07-24 - Alignement Chef de Service actions tracables

Demande: poursuivre l'alignement CDC avec le module Chef de Service.

Module: MOD-CHIEF / MOD-REQUEST.

Fichiers modifies:

- `frontend/src/routes/app.chief-inbox.tsx`
- `backend/api/core/ticket_actions.py`
- `backend/api/services/ServiceRequest.py`
- `backend/tests/api/test_ticket_actions.py`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: la reaffectation service par un chef exige maintenant un motif explicite cote backend et frontend. Le motif nettoye est conserve dans la timeline et les metadonnees. Le renvoi au directeur depuis la boite chef exige aussi un motif avant envoi.

Verification: test cible `backend\\venv\\Scripts\\pytest.exe backend\\tests\\api\\test_ticket_actions.py -q` OK avec 68 tests passes.

## 2026-07-24 - Alignement Agent Support escalade

Demande: poursuivre l'alignement CDC avec le module Agent Support.

Module: MOD-AGENT / MOD-REQUEST.

Fichiers modifies:

- `backend/api/core/ticket_actions.py`
- `backend/tests/api/test_ticket_actions.py`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: la contrainte d'escalade agent utilise maintenant le role normalise `agent-support`. Un agent support ne peut escalader que les tickets qui lui sont personnellement assignes, que le libelle entrant soit l'ancien `agent` ou le role CDC `agent-support`.

Verification: test cible des regles ticket d'abord en echec sur l'escalade agent, puis `backend\\venv\\Scripts\\pytest.exe backend\\tests\\api\\test_ticket_actions.py -q` OK avec 65 tests passes.

## 2026-07-24 - Alignement detail demandeur

Demande: demarrer l'alignement du module Demandeur avec le cahier des charges et verifier creation, `Mes demandes`, `Historique`, accueil personnel et detail.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:

- `frontend/src/routes/app.requests.$id.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: la modification d'une demande personnelle ne montre plus `Categorie`, `Priorite`, `Direction destinataire` ni `Service`. L'interface demandeur envoie uniquement `title` et `description`, en coherence avec la restriction backend existante.

Verification: controle cible des listes personnelles, du formulaire de creation, du detail demandeur et des references mortes.

## 2026-07-23 - Alignement CDC des roles metier

Demande: aligner strictement l'application sur les six acteurs du cahier des charges et supprimer la distinction metier Directeur / Directeur General.

Module: roles, permissions, navigation, workflow, reporting.

Fichiers modifies:

- backend RBAC, dependances, routes et services directement lies aux roles;
- frontend session, permissions, navigation, vues direction/supervision/globale et communication;
- index `docs/codex/` roles, regles metier, routes, modules, fonctionnalites et API.

Correction: `dg` n'est plus un role metier attribuable ni un niveau de permission global. Les anciennes valeurs `dg` sont normalisees vers `director` pour compatibilite, tandis que la vue globale et les donnees globales restent reservees a `admin`.

Verification: recherches ciblees des anciens guards/permissions `dg`, compilation backend ciblee et build frontend.

## 2026-07-23 - Remplacement du cahier des charges

Demande: remplacer integralement `docs/cahier-des-charges.md` par le contenu fourni du cahier des charges DSI EDG.

Module: documentation projet.

Fichiers modifies:

- `docs/cahier-des-charges.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: le cahier des charges principal contient maintenant le document DSI EDG sur l'application de Ticketing / Support Informatique, structure en sections Markdown propres.

Verification: lecture ciblee du fichier remplace.

## 2026-07-23 - Clic profil vers drawer organigramme

Demande: dans l'organigramme d'une direction, le clic sur chaque profil reel doit faire apparaitre le drawer de detail employe.

Module: MOD-ADMIN / MOD-ORG.

Fichiers modifies:

- `frontend/src/components/admin/direction-org-chart.tsx`
- `frontend/src/routes/app.admin.directions.$id.tsx`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: toutes les cartes de personnes reelles dans l'organigramme et les profils subordonnes du drawer sont des boutons explicites, avec ouverture robuste du drawer et protection contre les clics parasites de l'arbre. Les emplacements vides restent non cliquables car ils ne representent aucun employe reel.

Verification: lint cible des fichiers frontend concernes.

## 2026-07-23 - Affichage du detail direction depuis l'oeil

Demande: au clic sur l'icone `oeil` dans la liste des directions, afficher le detail organigramme au lieu de rester sur la liste.

Module: MOD-ADMIN / MOD-ORG.

Fichiers modifies:

- `frontend/src/routes/app.admin.directions.tsx`
- `docs/codex/ROUTE_INDEX.md`
- `docs/codex/FILE_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: la route `/app/admin/directions/$id` existait dans `routeTree.gen.ts`, mais elle etait imbriquee sous `/app/admin/directions`; la page parent ne rendait pas d'`Outlet`, donc TanStack gardait la liste visible meme sur `/app/admin/directions/1`.

Correction: la page parent detecte les sous-routes et rend l'`Outlet` pour laisser le detail direction afficher l'organigramme dedie.

Verification: lint cible des routes/composant organisation et build frontend.

## 2026-07-23 - Representation minimale du detail direction

Demande: au clic sur `Voir` une direction, afficher au moins un format de representation meme lorsque la direction n'a pas encore d'enfants actifs.

Module: MOD-ADMIN / MOD-ORG.

Fichiers modifies:

- `frontend/src/routes/app.admin.directions.$id.tsx`
- `frontend/src/components/admin/direction-org-chart.tsx`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/FILE_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: la page detail direction utilise maintenant le composant dedie `DirectionOrgChart`. Il affiche toujours une pyramide metier multi-branches `Directeur -> Chefs de departement -> Chefs de service -> Membres` avec des emplacements clairement non renseignes quand aucun personnel n'est affecte. Les branches reelles incompletes gardent aussi une suite visuelle jusqu'aux membres. Aucune donnee fictive ni fausse photo n'est creee; les donnees reelles restent utilisees des qu'elles existent et les personnes reelles ouvrent le drawer detail employe.

Verification: lint cible du fichier route et build frontend.

## 2026-07-23 - Organigramme pyramidal interactif d'une direction

Demande: lorsqu'un administrateur clique sur `Voir/Consulter` une direction, afficher une page premium de consultation avec organigramme pyramidal et fiches employes cliquables.

Module: MOD-ADMIN / MOD-ORG.

Fichiers modifies:

- `frontend/src/routes/app.admin.directions.$id.tsx`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/FILE_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: la route existante `/app/admin/directions/$id` est conservee et affiche maintenant un organigramme pyramidal interactif base sur les vraies directions, departements, services/unites et comptes. Les cartes personnes/avatars ouvrent un drawer detail employe; la page conserve la charte EDG-SUP et ajoute recherche, zoom et mode focus.

Verification: lint cible de `app.admin.directions.$id.tsx` et build frontend Vite/TanStack.

## 2026-07-23 - Attribution des roles utilisateurs selon hierarchie organisationnelle

Demande: adapter le formulaire admin d'attribution/modification de role pour afficher les champs organisationnels selon le role et valider l'affectation cote backend.

Module: MOD-ADMIN / MOD-ORG / users.

Fichiers modifies:

- `frontend/src/routes/app.admin.users.tsx`
- `frontend/src/lib/api/accounts.ts`
- `backend/api/schemas/SchemaAccount.py`
- `backend/api/routes/RouteUsers.py`
- `backend/api/services/ServiceAccount.py`
- `backend/tests/api/test_user_org_assignment.py`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/API_INDEX.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/DEPENDENCY_INDEX.md`
- `docs/codex/FILE_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: le formulaire admin distingue `Chef de departement` et `Chef de service` sans creer de role base supplementaire; les deux restent portes par le role backend `chief` avec un `unity_id` pointant vers le niveau choisi. Les champs direction/departement/service sont filtres sur les entites actives, les valeurs masquees sont videes et le backend valide le niveau organisationnel avant persistence.

Verification: compilation ciblee backend, test cible `test_user_org_assignment.py`, lint cible frontend et build Vite/TanStack.

## 2026-07-24 - Normalisation RBAC Agent Support / Chief Service / Chief Département

Demande: normaliser les rôles métier canoniques sans casser le flux existant, en gardant la compatibilité backward sur les libellés historiques de persistance.

Module: MOD-RBAC / MOD-ACCOUNTS.

Fichiers modifies:

- `backend/api/core/rbac.py`
- `backend/api/core/ticket_actions.py`
- `backend/api/models/ModelAccount.py`
- `backend/api/dependencies.py`
- `backend/api/routes/RouteRequest.py`
- `backend/api/routes/RouteAttachment.py`
- `backend/api/services/ServiceAccount.py`
- `backend/tests/api/test_ticket_actions.py`

Correction: la couche technique bascule sur la nomenclature canonique `agent-support`, `chief-service` et `chief-departement`; les alias historiques (`agent`, `chief`, `chief-department`, `chief-dept`) sont remis sur la bonne normalisation sans refonte de workflow.

Verification: exécution directe Python sur `normalize_role()` / `has_role()` / `assert_action_allowed()` confirmant `agent-support -> resolve_allowed=OK` et refus explicite sur `reject`.

## 2026-07-23 - Structure organisationnelle Direction / Departement / Service

Demande: ajouter le menu `Departements`, completer la hierarchie organisationnelle `Direction -> Departement -> Unite/Service`, garder la meme table et ajouter une consultation premium d'une direction.

Module: MOD-ADMIN / MOD-ORG.

Fichiers modifies:

- `backend/api/routes/RouteDirectionsUnits.py`
- `backend/api/routes/__init__.py`
- `backend/api/main.py`
- `backend/tests/api/test_directions_units_hierarchy.py`
- `frontend/src/lib/api/directions-units.ts`
- `frontend/src/components/app-layout.tsx`
- `frontend/src/routes/app.admin.directions.tsx`
- `frontend/src/routes/app.admin.directions.$id.tsx`
- `frontend/src/routes/app.admin.departments.tsx`
- `frontend/src/routes/app.admin.units.tsx`
- `frontend/src/routes/app.admin.org.tsx`
- `frontend/src/routeTree.gen.ts`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/API_INDEX.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/MODULE_INDEX.md`
- `docs/codex/DEPENDENCY_INDEX.md`
- `docs/codex/ROUTE_INDEX.md`
- `docs/codex/FILE_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: les directions, departements et services/unites restent dans `unity` et sont positionnes par `organigram.parent_id`. Les nouveaux elements portent `unity.infos.org_type` pour stabiliser leur type sans migration. Les actions de suppression admin deviennent des desactivations visibles et reversibles; une confirmation forcee desactive aussi les descendants actifs pour conserver une hierarchie coherente.

Verification: compilation ciblee backend, test cible `test_directions_units_hierarchy.py`, build frontend Vite/TanStack pour generer et verifier les nouvelles routes.

## 2026-07-23 - Seed organisation respecte les suppressions admin

Demande: identifier pourquoi les directions et services supprimes dans l'administration reapparaissent apres relance, puis corriger uniquement la cause.

Module: MOD-ADMIN / MOD-ORG.

Fichiers modifies:

- `backend/api/seed_references.py`
- `backend/tests/api/test_seed_references_org.py`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/API_INDEX.md`
- `docs/codex/DEPENDENCY_INDEX.md`
- `docs/codex/FILE_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: `seed_references.py`, execute a chaque demarrage par `main.py`, restaurait explicitement les `Unity` et `Organigram` soft-deleted en remettant `deleted_at = None`.

Correction: le seed cree toujours les donnees builtin absentes sur base neuve, mais ignore les `Unity` et `Organigram` soft-deleted et ne restaure plus automatiquement les directions/services supprimes. Les enfants dont le parent seed est absent ou supprime ne sont pas recrees/reparents par le seed.

Verification: compilation ciblee de `seed_references.py` et test cible `test_seed_references_org.py`.

## 2026-07-20 - Formulaire demandeur sans champs internes

Demande: retirer du formulaire de creation demandeur les champs `Categorie`, `Priorite`, `Direction destinataire` et `Service`.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:

- `frontend/src/components/new-request-form.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: le formulaire personnel affiche uniquement le titre, la description et les pieces jointes optionnelles. Le frontend conserve des valeurs techniques non visibles (`autre`, `medium`) pour satisfaire le contrat actuel de creation, sans envoyer direction ni service; la qualification reste dans les espaces metier autorises.

Verification: recherche ciblee des libelles/champs retires et lint cible du composant.

## 2026-07-20 - Ordre Grille puis Liste dans les toggles tickets

Demande: dans toutes les vues de tickets, conserver la grille par defaut et afficher l'icone Grille avant l'icone Liste.

Module: MOD-PERSONAL / MOD-AGENT / MOD-CHIEF / MOD-SUPERVISION.

Fichiers modifies:

- `frontend/src/components/layout-toggle.tsx`
- `frontend/src/routes/app.requests.index.tsx`
- `frontend/src/routes/app.requests.history.tsx`
- `frontend/src/routes/app.my-tickets.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: le composant commun `LayoutToggle` affiche maintenant le bouton Grille avant le bouton Liste. `Mes demandes`, `Historique` et `Mes tickets` n'utilisent plus la valeur de layout memorisee en session, afin de rouvrir en grille a chaque entree sur la page. `File d'attente` et `Supervision` etaient deja en etat local `grid`. Le basculement manuel reste disponible.

Verification: recherche ciblee des usages `LayoutToggle`/`LayoutMode` dans les routes frontend et lint cible des fichiers touches.

## 2026-07-20 - Separation Mes demandes et Historique

Demande: reorganiser l'affichage demandeur pour garder `resolved` dans `Mes demandes` et placer uniquement `closed`, `cancelled`, `rejected` dans `Historique`.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:

- `frontend/src/routes/app.requests.index.tsx`
- `frontend/src/routes/app.requests.history.tsx`
- `frontend/src/routes/app.index.tsx`
- `backend/api/repositories/RepositoryRequest.py`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/API_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: `Mes demandes` exclut `closed,cancelled,rejected`; `Historique` propose seulement `closed`, `cancelled`, `rejected`; `resolved` reste dans les listes actives/personnelles jusqu'a cloture ou autre statut terminal. Le repository accepte l'exclusion multi-statut et tient compte des alias de statuts historiques.

Verification: lint frontend cible et compilation backend cible.

## 2026-07-20 - Filtrage strict de A qualifier

Demande: corriger `A qualifier` pour exclure les statuts terminaux, limiter `Prendre la demande` aux statuts actifs et normaliser `cancalled`/`escaladed`.

Module: MOD-AGENT / MOD-CHIEF / MOD-REQUEST.

Fichiers modifies:

- `backend/api/core/ticket_actions.py`
- `backend/api/repositories/RepositoryRequest.py`
- `backend/api/services/ServiceRequest.py`
- `backend/tests/api/test_ticket_actions.py`
- `frontend/src/routes/app.queue.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/API_INDEX.md`
- `docs/codex/WORKFLOW_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: `/requests/triage` retourne uniquement `new`, `qualifying`, `qualified`, `reopened`; le frontend applique la meme garde avant d'afficher/activer `Prendre la demande`; `normalize_status` mappe `cancalled -> cancelled` et `escaladed -> escalated`; les tests verrouillent qu'un statut terminal ne peut pas aller vers `assigned`.

Verification: tests cibles `test_ticket_actions.py`, compilation ciblee backend et lint cible frontend.

## 2026-07-20 - Correction prise en charge A qualifier

Demande: corriger l'erreur affichee au clic sur `Prendre la demande`.

Module: MOD-AGENT / MOD-CHIEF / MOD-REQUEST.

Fichiers modifies:

- `frontend/src/routes/app.queue.tsx`
- `frontend/src/lib/api/requests.ts`
- `backend/api/routes/RouteRequest.py`
- `docs/codex/API_INDEX.md`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: le frontend pouvait envoyer une unite comme `direction_id` lors d'une prise directe depuis `A qualifier`, et l'endpoint imposait `direction_id` meme lorsque `unit_id` etait la vraie donnee utile.

Correction: `direction_id` devient optionnel pour `/requests/{id}/qualify` quand `unit_id` est fourni; `Prendre la demande` envoie prioritairement l'unite reelle de l'utilisateur et affiche le message backend exact en cas de refus.

Verification: compilation ciblee de `RouteRequest.py` et lint cible sur `app.queue.tsx`/`requests.ts`.

## 2026-07-20 - Listes de tickets en vue grille par defaut

Demande: afficher par defaut en vue grille partout ou une liste de ticket dispose deja d'une bascule liste/grille.

Module: MOD-PERSONAL / MOD-AGENT / MOD-SUPERVISION.

Fichiers modifies:

- `frontend/src/routes/app.my-tickets.tsx`
- `frontend/src/routes/app.queue.tsx`
- `frontend/src/routes/app.supervision.tsx`
- `frontend/src/routes/app.requests.history.tsx`
- `frontend/src/routes/app.chief-inbox.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: les layouts initiaux de `Mes tickets`, `File d'attente`, `Supervision` et `Historique` passent de `list` a `grid`. La `Boite chef` affiche ses cartes tickets en grille responsive. `Mes demandes` etait deja en `grid`. La vue liste reste accessible via les toggles existants lorsqu'ils existent.

Verification: `rg` cible sur les routes documentees avec `LayoutToggle`/`LayoutMode`; les routes direction, DG, SLA et admin ciblees n'exposent pas de toggle layout local a modifier.

## 2026-07-20 - Mes demandes en vue grille par defaut

Demande: afficher `Mes demandes` en vue grille par defaut.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:

- `frontend/src/routes/app.requests.index.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: la valeur par defaut du layout personnel `req:layout` passe de `list` a `grid`, tout en conservant le toggle liste/grille.

Verification: `eslint` cible sur `app.requests.index.tsx` avec `prettier/prettier` desactive pour ignorer le bruit CRLF existant.

## 2026-07-20 - Suppression export des demandes personnelles

Demande: supprimer la partie export concernant les propres demandes, pour tous les roles.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:

- `frontend/src/routes/app.requests.index.tsx`
- `frontend/src/routes/app.requests.history.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: retrait des boutons, menus, imports et handlers d'export dans `Mes demandes` et `Historique`. Les exports metier des modules rapports, direction, DG ou admin ne sont pas touches.

Verification: `eslint` cible sur `app.requests.index.tsx` et `app.requests.history.tsx` avec `prettier/prettier` desactive pour ignorer le bruit CRLF existant.

## 2026-07-20 - Prise en charge depuis A qualifier

Demande: remplacer `Resoudre directement` par `Prendre la demande` dans l'onglet `A qualifier`, afin que l'utilisateur se l'affecte et poursuive le traitement depuis `Mes tickets`.

Module: MOD-AGENT / MOD-CHIEF / MOD-REQUEST.

Fichiers modifies:

- `frontend/src/routes/app.queue.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: l'action directe de resolution dans `A qualifier` court-circuitait le flux normal de traitement agent.

Correction: l'action `Prendre la demande` reutilise `POST /requests/{id}/qualify` avec `assignee_id` de l'utilisateur connecte; la demande sort du triage, passe en `assigned`, puis les caches `qualify`, `queue`, `requests`, `my-tickets` et `my-tickets-stats` sont invalides.

Verification: `eslint` cible sur `frontend/src/routes/app.queue.tsx` avec `prettier/prettier` desactive pour ignorer le bruit CRLF existant.

## 2026-07-20 - Separation Mes tickets et File d'attente

Demande: reorganiser `Mes tickets` et `File d'attente` pour supprimer les doublons et garantir que les tickets pris sortent de la file.

Module: MOD-AGENT / MOD-CHIEF / MOD-REQUEST.

Fichiers modifies:

- `frontend/src/routes/app.my-tickets.tsx`
- `frontend/src/routes/app.queue.tsx`
- `frontend/src/lib/api/requests.ts`
- `backend/api/routes/RouteRequest.py`
- `backend/api/services/ServiceRequest.py`
- `backend/api/repositories/RepositoryRequest.py`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/API_INDEX.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/ROLE_INDEX.md`
- `docs/codex/ROUTE_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: `File d'attente` contenait encore une sous-vue `Mes tickets` et un filtre statut redondant; `Mes tickets` calculait aussi une partie de ses KPI depuis une source non strictement limitee aux tickets affectes a l'agent connecte.

Correction: `File d'attente` conserve seulement les vues `A prendre` et `A qualifier`; la vue `A prendre` appelle `/requests/queue` avec `unassigned_only=true`; `Mes tickets` liste et calcule ses KPI depuis `/requests` filtre par `assignee_id` de l'utilisateur connecte.

Verification: `python -m compileall backend/api/routes/RouteRequest.py backend/api/services/ServiceRequest.py backend/api/repositories/RepositoryRequest.py`; `eslint` cible avec `prettier/prettier` desactive sur les fichiers frontend touches. Le lint standard reste bloque par la configuration Prettier CRLF existante.

## 2026-07-20 - Detail ticket depuis File d'attente

Demande: corriger l'ouverture d'un ticket depuis `File d'attente` pour l'agent de traitement et les roles disposant de cet onglet, sans modifier les autres modules.

Module: MOD-AGENT / MOD-CHIEF / MOD-REQUEST.

Fichiers modifies:

- `backend/api/routes/RouteRequest.py`
- `backend/api/services/ServiceRequest.py`
- `backend/api/core/ticket_actions.py`
- `backend/tests/api/test_ticket_actions.py`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: la liste `/requests/queue` utilise un perimetre `unity_id` calcule via l'organigramme, mais le detail `/requests/{id}` et le garde d'actions agent/chef restaient limites a l'unite exacte. Un ticket pouvait donc etre visible dans la file puis refuse au detail.

Correction: reutilisation du meme perimetre `unity_id` calcule pour le detail et les actions agent/chef; la correspondance par `direction_id` seule reste refusee afin de ne pas elargir artificiellement les droits.

Verification: `python -m compileall backend/api/routes/RouteRequest.py backend/api/services/ServiceRequest.py backend/api/core/ticket_actions.py`; `backend\venv\Scripts\pytest.exe backend\tests\api\test_ticket_actions.py -q` -> 57 tests passes.

## 2026-07-20 - Affichage demandeur sans demandes cloturees

Demande: corriger l'espace Demandeur afin que les demandes cloturees ne s'affichent plus dans `Demandes recentes` ni dans `Mes demandes`, et restent visibles uniquement dans `Historique`.

Module: MOD-PERSONAL / MOD-REQUEST.

Fichiers modifies:

- `frontend/src/routes/app.index.tsx`
- `frontend/src/routes/app.requests.index.tsx`
- `frontend/src/lib/api/requests.ts`
- `backend/api/routes/RouteRequest.py`
- `backend/api/services/ServiceRequest.py`
- `backend/api/repositories/RepositoryRequest.py`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/API_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: `Accueil > Demandes recentes` affiche les 3 demandes personnelles actives les plus recentes. `Mes demandes` appelle le filtre existant `/requests` avec `exclude_status=closed`, masque le statut `Cloturee` du select et remet un ancien choix memorise sur `Tous les statuts`. `Historique` reste le seul onglet personnel qui charge `closed`.

Verification: `python -m compileall backend/api/routes/RouteRequest.py backend/api/services/ServiceRequest.py backend/api/repositories/RepositoryRequest.py`; ESLint cible sur les fichiers frontend avec `prettier/prettier` desactive pour ignorer le bruit CRLF existant; `git diff --check` cible OK.

## 2026-07-20 - Suppression admin Directions et Services/Unites

Demande: corriger la suppression CRUD des Directions et des Unites/Services dans l'espace Administrateur, sans modifier les autres modules.

Module: MOD-ADMIN / MOD-ORG.

Chemins consultes:

- `AGENTS.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/MODULE_INDEX.md`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/API_INDEX.md`
- `docs/codex/DEPENDENCY_INDEX.md`
- `frontend/src/lib/api/directions-units.ts`
- `frontend/src/routes/app.admin.directions.tsx`
- `frontend/src/routes/app.admin.units.tsx`
- `backend/api/routes/RouteDirectionsUnits.py`
- `backend/api/repositories/base_repository.py`
- `backend/api/repositories/RepositoryOrganigram.py`
- `backend/api/models/ModelUnity.py`
- `backend/api/models/ModelOrganigram.py`

Fichiers modifies:

- `backend/api/routes/RouteDirectionsUnits.py`
- `docs/codex/CHANGELOG_CODEX.md`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/API_INDEX.md`
- `docs/codex/DEPENDENCY_INDEX.md`

Cause: la suppression soft-delete marquait seulement `unity.deleted_at`; les listes admin etaient basees sur `organigram.deleted_at` et continuaient a retourner la direction ou le service supprime.

Correction: les endpoints `DELETE /directions/{id}` et `DELETE /units/{id}` soft-delete maintenant la `Unity` et son noeud `Organigram` actif. Les listes/details `/directions/*` et `/units/*` excluent les `Unity` soft-deleted et les services dont la direction parente est supprimee.

Verification: `python -m compileall backend\api\routes\RouteDirectionsUnits.py`.

## 2026-07-20 - Historique aligne sur les filtres de Mes demandes

Demande: prendre la barre de recherche et l'organisation des filtres de `Mes demandes` comme reference, puis appliquer le meme format a `Historique` sans supprimer les fonctionnalites utiles propres a l'historique.

Module: MOD-PERSONAL / MOD-REQUEST.

Chemins consultes:

- `AGENTS.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/BUSINESS_RULES.md`
- `frontend/src/routes/app.requests.index.tsx`
- `frontend/src/routes/app.requests.history.tsx`

Fichiers modifies:

- `frontend/src/routes/app.requests.history.tsx`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: remplacement des onglets visuels de statut historique par un select compact place dans le meme bandeau que la recherche et la periode, sur le modele de `Mes demandes`. Les statuts historiques `resolues`, `cloturees`, `rejetees`, l'export, le layout, la pagination et les dates personnalisees restent disponibles.

Verification: controle cible du diff et des imports; aucun build global lance car la modification est limitee a l'UI d'une route et le projet ne fournit pas de script typecheck dedie.

## 2026-07-20 - Notifications ciblees par prochain acteur workflow

Demande: corriger le module Notifications afin qu'un ticket qui arrive dans une direction ne notifie plus tous les utilisateurs de cette direction, mais uniquement l'acteur qui doit effectuer la prochaine action.

Module: MOD-NOTIF / dependance directe MOD-REQUEST.

Chemins consultes:

- `AGENTS.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/MODULE_INDEX.md`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/DEPENDENCY_INDEX.md`
- `backend/api/services/NotificationEmitter.py`
- `backend/api/services/ServiceRequest.py`
- `backend/api/routes/RouteNotification.py`
- `backend/api/services/ServiceNotification.py`
- `backend/api/repositories/RepositoryNotification.py`
- `backend/api/core/event_bus.py`
- `frontend/src/lib/realtime/invalidation-map.ts`

Fichiers modifies:

- `backend/api/services/NotificationEmitter.py`
- `backend/api/services/ServiceRequest.py`
- `docs/codex/CHANGELOG_CODEX.md`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/API_INDEX.md`
- `docs/codex/MODULE_INDEX.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/DEPENDENCY_INDEX.md`

Correction: `NotificationEmitter` cree une notification pour un seul `recipient_id` puis publie `notification.created` uniquement vers `target.user_ids=[recipient_id]`. Le transfert inter-direction notifie seulement le directeur designe comme prochain acteur (`workflow_detail.dest_id` / `infos.target_user_id`) au lieu de boucler sur tous les directeurs de la direction cible.

Verification: `python -m compileall backend\api\services\NotificationEmitter.py backend\api\services\ServiceRequest.py`.

## 2026-07-13 - Creation demande: succes frontend fiable

Demande: corriger le comportement de creation d'une nouvelle demande quand le backend confirme la creation mais que l'interface peut afficher un faux etat d'erreur.

Module: MOD-PERSONAL / MOD-REQUEST.

Chemins consultes:

- `AGENTS.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/DEPENDENCY_INDEX.md`
- `frontend/src/components/new-request-form.tsx`
- `frontend/src/lib/api/requests.ts`
- `frontend/src/lib/api/client.ts`
- `frontend/src/routes/app.requests.index.tsx`
- `frontend/src/routes/app.tsx`
- `backend/api/routes/RouteRequest.py`
- `backend/api/services/ServiceRequest.py`
- `backend/api/schemas/SchemaRequest.py`

Fichiers modifies:

- `frontend/src/components/new-request-form.tsx`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: validation locale par champ obligatoire, toast vert de succes des que `POST /requests/` reussit, separation stricte entre erreur de creation et erreurs post-succes comme pieces jointes ou navigation, invalidation immediate des listes `requests` et preparation du cache detail.

Resultat: une creation HTTP 201 n'est plus convertie en faux message rouge par un effet secondaire; les erreurs locales restent sous les champs concernes.

## 2026-07-13 - Tableaux decisionnels enrichis

Demande: renforcer les rapports pour obtenir des tableaux complets exploitables en pilotage, audit, controle interne et comite de direction.

Module: MOD-REPORT.

Chemins consultes:

- `AGENTS.md`
- `docs/codex/REPORTING_DECISION_ENGINE.md`
- `docs/codex/API_INDEX.md`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/FEATURE_INDEX.md`
- `backend/api/services/ServiceReport.py`
- `backend/api/routes/RouteReports.py`
- `frontend/src/lib/api/reports.ts`

Fichiers modifies:

- `backend/api/services/ServiceReport.py`
- `backend/api/routes/RouteReports.py`
- `frontend/src/lib/api/reports.ts`
- `docs/codex/REPORTING_DECISION_ENGINE.md`
- `docs/codex/API_INDEX.md`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/MODULE_INDEX.md`
- `docs/codex/DEPENDENCY_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: enrichissement du moteur decisionnel avec vues `executive`, `analytical` et `audit`, groupes de colonnes, filtres multi-criteres, recherche, tri, pagination audit, exports complets avec metadonnees, catalogue KPI detaille et indicateurs de qualite/trace disponibles.

Resultat: la logique backend et le contrat API sont prets pour des tableaux decisionnels riches sans inventer de donnees; les donnees non structurees comme la cause detaillee de retard restent documentees comme ameliorations futures.

## 2026-07-13 - Moteur de reporting decisionnel

Demande: construire la logique de pilotage/reporting qui servira aux tableaux de bord, sans modifier l'interface si non necessaire.

Module: MOD-REPORT, MOD-DG, MOD-ADMIN.

Chemins consultes:

- `AGENTS.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/MODULE_INDEX.md`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/API_INDEX.md`
- `docs/codex/DEPENDENCY_INDEX.md`
- `backend/api/services/ServiceReport.py`
- `backend/api/routes/RouteReports.py`
- `backend/api/models/ModelRequest.py`
- `backend/api/models/ModelWorkflow.py`
- `backend/api/models/ModelWorkflowDetail.py`
- `backend/api/models/ModelAccount.py`
- `backend/api/models/ModelUnity.py`
- `frontend/src/lib/api/reports.ts`

Fichiers modifies:

- `backend/api/services/ServiceReport.py`
- `backend/api/routes/RouteReports.py`
- `frontend/src/lib/api/reports.ts`
- `docs/codex/REPORTING_DECISION_ENGINE.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/API_INDEX.md`
- `docs/codex/MODULE_INDEX.md`
- `docs/codex/DEPENDENCY_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: ajout de `GET /reports/decision` et `GET /reports/decision/export`, avec hierarchie EDG -> direction -> service/unite -> agent/responsable -> ticket, KPI consolides, tendances periode precedente, breakdowns par direction/service/statut/categorie/priorite/responsable/periode, et export CSV/Excel/PDF avec filtres appliques.

Resultat: le reporting dispose d'un moteur decisionnel reutilisable pour DG, admin, direction et responsables metier; les roles auditeur/controle interne restent documentes comme amelioration future car absents du modele de roles actuel.

## 2026-07-13 - Filtre direction de la vue globale admin

Demande: dans le module Administration, permettre a l'administrateur de superviser toutes les directions ou une direction precise depuis la vue globale, avec tickets regroupes par statut et rapport direction.

Module: MOD-DG, MOD-ADMIN, MOD-REPORT.

Chemins consultes:

- `AGENTS.md`
- `docs/codex/MODULE_INDEX.md`
- `docs/codex/ROUTE_INDEX.md`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/BUSINESS_RULES.md`
- `frontend/src/routes/app.dg.tsx`
- `frontend/src/lib/api/requests.ts`
- `frontend/src/lib/api/directions-units.ts`
- `frontend/src/lib/api/reports.ts`
- `frontend/src/lib/api/escalations.ts`

Fichiers modifies:

- `frontend/src/routes/app.dg.tsx`
- `docs/codex/FEATURE_INDEX.md`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/API_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Correction: ajout du perimetre "Toutes les directions" / direction precise dans `/app/dg`, application de `direction_id` a `fetchRequests`, regroupement compact des tickets par statut, filtrage des escalades visibles selon les tickets du perimetre et export via le rapport existant `reports/by-unity`.

Resultat: l'admin conserve une supervision globale ou directionnelle dans le contexte pilotage administratif, sans melange avec `Mes demandes`.

## 2026-07-13 - Detail admin des notifications vers tickets archives

Demande: corriger le cas ou un clic notification admin ouvre `/app/admin/tickets/$id` mais affiche `Demande introuvable`.

Probleme traite: la navigation etait deja dans le bon contexte admin, mais certaines notifications pointaient vers une demande soft-deleted; `GET /requests/{id}` excluait ces demandes et le detail affichait une erreur generique.

Module: MOD-NOTIF, MOD-ADMIN, MOD-PERSONAL.

Chemins consultes:

- `AGENTS.md`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/API_INDEX.md`
- `frontend/src/routes/app.admin.tickets.$id.tsx`
- `frontend/src/routes/app.requests.$id.tsx`
- `frontend/src/lib/api/requests.ts`
- `backend/api/routes/RouteRequest.py`
- `backend/api/services/ServiceRequest.py`
- `backend/api/models/ModelNotification.py`

Fichiers modifies:

- `backend/api/services/ServiceRequest.py`
- `backend/api/routes/RouteRequest.py`
- `frontend/src/lib/api/requests.ts`
- `frontend/src/routes/app.requests.$id.tsx`
- `frontend/src/lib/mock-data.ts`
- `docs/codex/API_INDEX.md`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: une notification peut rester liee a `request.id` alors que la demande est soft-deleted; le detail admin doit pouvoir l'auditer sans rebasculer dans `Mes demandes`.

Correction: ajout de `include_deleted=true` sur `GET /requests/{id}`, honore uniquement pour le role admin; `RequestDetailPage` l'utilise seulement dans le contexte `admin`, separe le cache React Query du contexte personnel, affiche un etat `Ticket archive` et desactive les actions metier.

Tests:

- `python -m compileall backend/api/services/ServiceRequest.py backend/api/routes/RouteRequest.py`
- `npm run build`
- verification MySQL ciblee: `request.id=33` correspond a `EDG-2026-0025` avec `deleted_at` renseigne.

Resultat: un ticket archive ouvert depuis une notification admin reste dans `/app/admin/tickets/$id` et devient consultable en lecture seule.

## 2026-07-13 - Creation de AGENTS.md

Demande: créer un fichier `AGENTS.md` à la racine pour standardiser définitivement le comportement Codex sur EDG Connect.

Probleme traite: les consignes de travail devaient être centralisées afin de ne plus devoir les répéter à chaque conversation.

Module: documentation projet.

Chemins consultes:

- `docs/codex/README.md`
- `docs/codex/PROJECT_INDEX.md`
- `docs/codex/MODULE_INDEX.md`
- `docs/codex/ROLE_INDEX.md`
- `docs/codex/CHANGELOG_CODEX.md`

Fichiers modifies:

- `AGENTS.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: absence d'une référence racine unique pour les règles d'intervention Codex.

Correction: ajout de `AGENTS.md` avec les sections identité projet, philosophie, sources de vérité, usage obligatoire de `docs/codex/`, recherche progressive, architecture, navigation, règles métier, dépendances, vérifications, documentation, gestion des index et règle absolue de travail.

Tests:

- vérification ciblée de présence/contenu de `AGENTS.md`.

Resultat: règle de comportement officielle disponible à la racine du dépôt.

## 2026-07-13 - Navigation des notifications vers le detail metier

Demande: corriger les liens de notifications qui ouvraient `/app/requests/$id` au lieu du detail metier adapte au role.

Probleme traite: depuis `/app/notifications` ou le panneau notifications, un admin/agent/chef/directeur/DG pouvait etre renvoye dans `Mes demandes`, puis voir `Demande introuvable`.

Module: MOD-NOTIF, MOD-PERSONAL, MOD-AGENT, MOD-CHIEF, MOD-SUPERVISION, MOD-DIRECTION, MOD-DG, MOD-ADMIN.

Chemins consultes:

- `docs/codex/ROUTE_INDEX.md`
- `docs/codex/BUSINESS_RULES.md`
- `frontend/src/lib/ticket-navigation.ts`
- `frontend/src/routes/app.notifications.tsx`
- `frontend/src/components/notification-panel.tsx`
- `frontend/src/lib/api/notifications.ts`

Fichiers modifies:

- `frontend/src/lib/ticket-navigation.ts`
- `frontend/src/routes/app.notifications.tsx`
- `frontend/src/components/notification-panel.tsx`
- `docs/codex/BUSINESS_RULES.md`
- `docs/codex/CHANGELOG_CODEX.md`

Cause: `ticketDetailRouteForSource` traitait toute URL `/app/requests/...` comme un contexte personnel, meme quand cette URL venait d'une notification recue par un role professionnel.

Correction: ajout de `ticketDetailRouteForNotification` comme helper central dans `ticket-navigation.ts`; les deux surfaces notifications l'utilisent maintenant pour router admin/agent/chef/directeur/DG vers leurs details metier existants, tout en gardant `/app/requests/$id` pour le demandeur simple.

Tests:

- verification TypeScript ciblee frontend.
- recherche ciblee des imports notifications.
- verification directe de `ticketDetailRouteForNotification`: admin, agent, chief, director, dg, user et source direction explicite.

Resultat: navigation des notifications alignee sur BR-NAV-001 sans nouvelle route ni logique parallele.

## 2026-07-13 - Creation memoire technique initiale

Demande: construire une base de connaissance persistante dans `docs/codex/`.

Probleme traite: Codex devait disposer d'index locaux pour eviter de rescanner tout le projet a chaque intervention.

Module: documentation transversale.

Chemins consultes:

- `frontend/src/routes`
- `frontend/src/lib`
- `frontend/src/components/app-layout.tsx`
- `frontend/src/lib/capabilities.ts`
- `frontend/src/lib/ticket-navigation.ts`
- `backend/api/main.py`
- `backend/api/routes`
- `backend/api/services`
- `backend/api/models`
- `backend/api/core/rbac.py`
- `backend/api/core/ticket_actions.py`
- `backend/tests/api`

Fichiers modifies:

- `.gitignore`
- `docs/codex/*.md`

Cause: absence d'une cartographie locale structuree.

Correction: ajout des index projet, modules, fonctionnalites, frontend, backend, routes, API, database, roles, workflow, regles metier, dependances, fichiers, problemes connus et changelog.

Tests:

- verification a faire apres creation: presence des 16 fichiers.
- aucune correction fonctionnelle demandee ni effectuee.

Resultat: memoire technique initiale disponible.

Documents d'index mis a jour: tous les documents initiaux.

## 2026-07-13 - Hygiene artefacts Codex

Demande: aucun fichier temporaire Codex a la racine.

Probleme traite: des logs `.codex-uvicorn*.log` etaient encore a la racine.

Module: hygiene projet.

Chemins consultes:

- `.gitignore`
- racine du projet

Fichiers modifies:

- `.gitignore`

Cause: motifs explicites `.codex-*.log` non couverts comme regle nommee, meme si `*.log` existait deja.

Correction: deplacement des logs vers `.codex/logs/` et ajout du motif `/.codex-*.log`.

Tests:

- listing cible racine.

Resultat: logs ranges sous `.codex/logs/`.
