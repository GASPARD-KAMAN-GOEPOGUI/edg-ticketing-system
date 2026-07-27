# Business Rules

## Navigation et contextes

BR-NAV-001
Description: Un ticket ouvert depuis un espace metier doit rester dans cet espace metier.
Module: MOD-PERSONAL, MOD-SUPERVISION, MOD-AGENT, MOD-CHIEF, MOD-DIRECTION, MOD-GLOBAL, MOD-ADMIN.
Roles: tous.
Fichiers: `ticket-navigation.ts`, `app-layout.tsx`, `app.*_.tickets.$id.tsx` (dont `app.chief-inbox_.tickets.$id.tsx` et `app.department-inbox_.tickets.$id.tsx`), `app.requests.$id.tsx`.
Endpoints: `GET /requests/{id}`.
Tables: `request`.
Tests associes: `frontend/role-visual-check.mjs`.

Note implementation: les notifications doivent appeler `ticketDetailRouteForNotification` depuis `ticket-navigation.ts`; une ancienne URL backend `/app/requests/{id}` ne doit pas forcer le contexte personnel pour un role professionnel.

BR-NAV-002
Description: Les trois onglets `Accueil`, `Mes demandes`, `Historique` sont personnels pour tous les roles; les autres onglets sont professionnels.
Fichiers: `app-layout.tsx`, `ROLE_INDEX.md`.

BR-UI-TICKET-LAYOUT-001
Description: Les listes de tickets ou demandes rendues en cartes s'ouvrent en vue grille a chaque ouverture de page. Quand une bascule liste/grille existe, la vue liste reste disponible via le toggle et l'icone Grille est affichee avant l'icone Liste.
Fichiers: `layout-toggle.tsx`, `app.requests.index.tsx`, `app.requests.history.tsx`, `app.my-tickets.tsx`, `app.queue.tsx`, `app.supervision.tsx`, `app.chief-inbox.tsx`.

BR-PERSONAL-REQUESTS-001
Description: Dans l'espace personnel demandeur, `Mes demandes` affiche uniquement les demandes encore actives ou pouvant evoluer: `new`, `qualifying`, `qualified`, `assigned`, `in_progress`, `pending`, `escalated`, `resolved`, `reopened`. `Historique` affiche uniquement les demandes definitivement terminees: `closed`, `cancelled`, `rejected`. `Demandes recentes` affiche au maximum les 3 demandes actives les plus recentes.
Fichiers: `app.index.tsx`, `app.requests.index.tsx`, `app.requests.history.tsx`, `requests.ts`, `RouteRequest.py`, `ServiceRequest.py`, `RepositoryRequest.py`.
Note statut: `resolved` reste dans `Mes demandes` jusqu'a cloture demandeur ou passage vers un statut terminal.
Note implementation: l'espace personnel (`Mes demandes`, `Historique`) ne propose aucun export des propres demandes, quel que soit le role connecte. Les exports restent reserves aux espaces metier/reporting/admin.
Note acces: tout role connecte qui est `requester_id` d'une demande doit pouvoir la consulter dans `Mon espace` comme demande personnelle, sans etre bloque par son perimetre metier service/direction.
Note UI: `Mes demandes` et `Historique` suivent `BR-UI-TICKET-LAYOUT-001`.

BR-PERSONAL-CREATE-001
Description: Dans l'espace personnel, le formulaire de creation demandeur ne doit afficher que les informations necessaires au depot de la demande: titre, description detaillee et pieces jointes optionnelles. Les champs categorie, priorite, direction destinataire et service/unite sont reserves au traitement interne et ne sont pas visibles ni modifiables par le demandeur lors de la creation.
Fichiers: `new-request-form.tsx`, `requests.ts`, `RouteRequest.py`, `ServiceRequest.py`.
Note implementation: le frontend envoie une categorie technique non modifiable `autre` et une priorite technique `medium` uniquement pour satisfaire le contrat actuel de creation; aucune direction ni service n'est envoye depuis le formulaire demandeur. La qualification/orientation reste effectuee dans les espaces metier autorises.

BR-PERSONAL-EDIT-001
Description: Dans le detail d'une demande personnelle, le demandeur peut modifier uniquement le titre et la description lorsque l'edition initiale est autorisee. Les champs categorie, priorite, direction destinataire et service/unite restent reserves aux espaces metier et ne doivent pas etre affiches ni envoyes par l'interface demandeur.
Fichiers: `app.requests.$id.tsx`, `requests.ts`, `RouteRequest.py`, `ServiceRequest.py`.
Note implementation: le frontend et le backend limitent l'edition demandeur a `title` et `description`; les champs internes non prevus par le schema sont refuses par l'API.

BR-ATTACHMENT-001
Description: Les pieces jointes d'une demande doivent etre visibles depuis le detail de la demande/ticket pour les acteurs autorises. Chaque fichier doit proposer une action `Voir` et une action `Telecharger` via une requete authentifiee, sans exposer un acces direct non controle.
Fichiers: `app.requests.$id.tsx`, `requests.ts`, `client.ts`, `RouteRequest.py`, `storage.py`.
Endpoints: `GET /requests/{id}/attachments`, `POST /requests/{id}/attachments`, `GET /requests/download/{path}`.
Note securite: l'acces aux fichiers reutilise le scoping de la demande; un role professionnel qui est aussi demandeur proprietaire reste autorise via la regle d'acces personnel.
Note UI/stockage: les URLs de fichiers doivent encoder le chemin de stockage et l'action `Voir` doit ouvrir la fenetre de previsualisation au moment du clic, avant la recuperation authentifiee du blob, afin d'eviter le blocage navigateur.

## Roles et perimetres

BR-OWN-001
Description: Un acteur ne traite pas sa propre demande sauf actions demandeur autorisees: cloturer, annuler, demander reouverture, edition initiale.
Fichiers: `ticket_actions.py`, `capabilities.ts`.
Tests: `test_ticket_actions.py`.

BR-SCOPE-001
Description: Agent/chef agissent dans leur unite; directeur dans sa direction; admin global.
Fichiers: `ticket_actions.py`, `ServiceRequest.py`, `ServiceWorkflow.py`.
Tables: `request`, `unity`, `account`.
Note implementation: les tickets visibles depuis `File d'attente` utilisent le meme perimetre `unity_id` calcule que le detail `/app/queue/tickets/$id` et les actions associees; un agent/chef ne doit pas etre autorise par simple correspondance `direction_id`.

BR-ROLE-AGENT-001
Description: Un agent traite uniquement les tickets qui lui sont personnellement assignes dans `Mes tickets`; la `File d'attente` sert a prendre/orienter des tickets libres dans son perimetre.
Fichiers: `ticket_actions.py`, `app.my-tickets.tsx`, `app.queue.tsx`.
Note implementation: les KPI de `Mes tickets` sont calcules depuis les tickets filtres par `assignee_id` de l'agent connecte. La vue `A prendre` de `/app/queue` exclut les tickets deja assignes via `unassigned_only=true`; apres prise/assignation, le ticket sort de la file et rejoint `Mes tickets`.

BR-ROLE-CHIEF-001
Description: Un chef supervise son service, assigne a un agent de son service, peut changer la priorite et peut reaffecter un ticket vers un autre service de la meme direction uniquement avec un motif explicite conserve dans la timeline. Le renvoi/escalade vers le directeur doit aussi etre justifie cote interface.
Fichiers: `ticket_actions.py`, `ServiceRequest.py`, `RouteRequest.py`, `app.chief-inbox.tsx`, `app.supervision.tsx`.

BR-ROLE-CHIEF-DEPARTEMENT-001
Description: Un chief-departement (Chef Departement du CDC) partage la meme matrice de permissions qu'un chief-service, mais son perimetre organisationnel est elargi au departement entier (le departement et tous les services qui lui sont rattaches dans l'organigramme), alors qu'un chief-service reste strictement borne a son propre service. Concretement : lecture/action sur les tickets (`assert_ticket_scope`), listing (`GET /requests`, `GET /requests/{id}`, `GET /requests/by-unity/{id}`) et assignation a un agent (`assert_assignment_allowed`) acceptent tout service descendant du departement pour chief-departement, contre une correspondance exacte d'unite pour chief-service.
Fichiers: `ticket_actions.py` (`assert_ticket_scope`, `assert_assignment_allowed`), `ServiceRequest.py` (`_guard_ticket_action`, `assign`), `RouteRequest.py` (`list_requests`, `_resolve_access`, `_check_unity_access`), `app.chief-inbox.tsx` (selecteur d'agent assignable via `direction_id` pour chief-departement).
Tests: `test_ticket_actions.py` (`test_chief_departement_can_assign_across_department_scope`).

BR-ROLE-CHIEF-DEPARTEMENT-002
Description: chief-service et chief-departement ont chacun leur propre espace professionnel nomme et route dediee — `/app/chief-inbox` pour chief-service, `/app/department-inbox` pour chief-departement — au lieu de partager une seule page. Les deux routes rendent le meme composant partage (`ChiefInbox`, defini et exporte depuis `app.chief-inbox.tsx`) qui detecte dynamiquement l'espace courant via le chemin d'URL (`useRouterState`) pour adapter le libelle affiche, la cle de requete/cache et la portee de la liste d'agents assignables (`unit_id` exact pour chief-service, `direction_id` elargi via organigramme pour chief-departement). Un ticket ouvert depuis l'un des deux espaces reste dans cet espace (BR-NAV-001) via `ticketDetailRouteForList`/`ticketDetailRouteForSource` dans `ticket-navigation.ts`.
Fichiers: `app.chief-inbox.tsx`, `app.department-inbox.tsx`, `app.chief-inbox_.tickets.$id.tsx`, `app.department-inbox_.tickets.$id.tsx`, `ticket-navigation.ts`, `app.requests.$id.tsx` (contexte `departmentInbox`), `app-layout.tsx` (navigation sidebar/mobile par role).

BR-ROLE-DIRECTOR-001
Description: Un directeur pilote sa direction, arbitre et transfere; il n'est pas un agent de traitement quotidien.
Fichiers: `ticket_actions.py`, `app.direction.tsx`, `app.supervision.tsx`.

BR-DIRECTOR-RESOLVE-001
Description: Un directeur peut resoudre uniquement un ticket escalade ou en arbitrage.
Fichiers: `ticket_actions.py`, `capabilities.ts`, details tickets.
Tests: `test_ticket_actions.py`.

BR-ROLE-LEGACY-DG-001
Description: L'ancien role technique `dg` est un alias legacy normalise vers `director` pour compatibilite des donnees existantes. Il ne doit plus etre cree, attribue ni utilise dans les interfaces, permissions ou workflows metier.
Fichiers: `rbac.py`, `session.ts`, `SchemaAccount.py`, `ServiceAccount.py`, `RepositoryAccount.py`.

BR-ROLE-ADMIN-001
Description: Admin administre le systeme et possede toutes les permissions.
Fichiers: `rbac.py`, routes admin.
Note implementation: depuis un contexte admin, le detail ticket peut charger une demande soft-deleted via `GET /requests/{id}?include_deleted=true` pour conserver l'audit depuis les notifications; le frontend l'affiche en lecture seule et garde les actions metier desactivees.

BR-ADMIN-USER-ORG-001
Description: Dans l'administration des utilisateurs, les champs d'affectation organisationnelle dependent du role choisi. Un directeur est rattache a une direction active. Un chef peut etre rattache a un departement actif ou a un service/unite actif selon le choix formulaire `Chef de departement` ou `Chef de service`. Les roles `user`, `agent` et `admin` doivent etre rattaches a un service/unite actif appartenant a un departement actif.
Module: MOD-ADMIN, MOD-ORG.
Fichiers: `app.admin.users.tsx`, `accounts.ts`, `SchemaAccount.py`, `RouteUsers.py`, `ServiceAccount.py`.
Endpoints: `POST /users/`, `PATCH /users/{id}`, `PATCH /users/{id}/role`.
Tables: `account`, `unity`, `organigram`.
Regles: le frontend masque les champs non applicables, vide les anciennes selections lors d'un changement de role/direction/departement et n'envoie pas les valeurs masquees. Le backend admin normalise `direction_id`, `department_id` et `unit_id` vers `unity_id`, verifie que l'entite est active et refuse une affectation incompatible avec le role.

BR-ADMIN-GLOBAL-001
Description: Dans la vue globale admin, l'admin conserve une vue consolidee "Toutes les directions" ou filtre une direction precise; les tickets, statuts, escalades visibles et rapports doivent rester dans le contexte pilotage administratif, jamais dans `Mes demandes`.
Fichiers: `app.dg.tsx`, `requests.ts`, `reports.ts`, `RouteRequest.py`, `RouteReports.py`.
Donnees: `request.direction_id`, statuts tickets, escalades rattachees aux demandes du perimetre, export `reports/by-unity`.

## Organisation

BR-ORG-HIERARCHY-001
Description: La structure organisationnelle admin suit `Direction -> Département -> Unité/Service` sans nouvelle table ni migration. Les trois niveaux utilisent `unity` pour l'identité et `organigram.parent_id` pour le rattachement hiérarchique. Les nouvelles entités portent `unity.infos.org_type` (`direction`, `department`, `unit`) pour stabiliser la distinction de type, avec inference par position/libelle pour les donnees existantes.
Module: MOD-ADMIN, MOD-ORG.
Fichiers: `RouteDirectionsUnits.py`, `directions-units.ts`, `app.admin.directions.tsx`, `app.admin.departments.tsx`, `app.admin.units.tsx`, `app.admin.org.tsx`, `app.admin.directions.$id.tsx`.
Endpoints: `GET/POST/PATCH /directions/*`, `GET/POST/PATCH /departments/*`, `GET/POST/PATCH /units/*`.
Tables: `unity`, `organigram`.
Regles: une direction peut avoir une direction parente; un departement appartient obligatoirement a une direction; une unite/service appartient obligatoirement a un departement pour toute nouvelle creation; les anciens services directement rattaches a une direction restent lisibles comme donnees legacy.

BR-ORG-DELETE-001
Description: Dans l'administration organisationnelle, l'action utilisateur `Supprimer/Désactiver` est une desactivation logique visible et reversible, jamais un DELETE physique. L'element reste liste avec le statut `Inactif`, conserve ses informations et ses rattachements, puis peut etre reactive.
Module: MOD-ADMIN, MOD-ORG.
Fichiers: `RouteDirectionsUnits.py`, `seed_references.py`, `ModelUnity.py`, `ModelOrganigram.py`, `RepositoryUnity.py`, `RepositoryOrganigram.py`.
Endpoints: `POST /directions/{id}/deactivate`, `POST /directions/{id}/activate`, `POST /departments/{id}/deactivate`, `POST /departments/{id}/activate`, `POST /units/{id}/deactivate`, `POST /units/{id}/activate`; les anciens `DELETE /directions/{id}` et `DELETE /units/{id}` restent compatibles et declenchent une desactivation.
Tables: `unity`, `organigram`.
Note implementation: si l'element possede des enfants actifs, l'API renvoie `409` sauf confirmation `force=true`; la confirmation desactive aussi les descendants afin de garder une hierarchie coherente. Les anciennes lignes `deleted_at` restent masquees et ne sont pas restaurees.
Note seed: `seed_references.py`, execute au demarrage, ne doit jamais restaurer automatiquement une `unity` ou un `organigram` soft-deleted. Les donnees builtin absentes sont creees sur base neuve, mais les suppressions/desactivations admin persistantes sont respectees.

## Ticket et workflow

BR-TICKET-001
Description: Les transitions de statut doivent respecter `ALLOWED_TRANSITIONS`.
Fichiers: `ticket_actions.py`, `ServiceRequest.py`.
Tests: `test_ticket_actions.py`.
Note implementation: les anciens libelles fautifs `cancalled` et `escaladed` sont normalises respectivement en `cancelled` et `escalated` avant validation. Aucun statut terminal (`cancelled`, `closed`, `resolved`, `rejected`) ne peut transiter vers `assigned`.

BR-TICKET-QUALIFY-001
Description: Une demande non orientee doit etre qualifiee/orientee avant traitement normal, sauf routage automatique.
Fichiers: `ServiceRequest.py`, `RouteRequest.py`, `app.queue.tsx`.
Note implementation: `A qualifier` affiche uniquement les statuts actifs `new`, `qualifying`, `qualified`, `reopened`. Les statuts terminaux `cancelled`, `closed`, `resolved`, `rejected` sont exclus meme si `in_triage=True` est reste en base. L'action `Prendre la demande` reutilise la qualification avec `assignee_id` de l'utilisateur connecte; elle envoie l'unite reelle de l'acteur si disponible et ne fabrique pas une direction a partir d'un service. La demande quitte le triage, passe en `assigned` et apparait dans `Mes tickets`.

BR-ASSIGN-001
Description: Assignation differenciee de l'escalade; assigner donne un responsable de traitement, escalader remonte un blocage/arbitrage.
Fichiers: `ticket_actions.py`, `ServiceRequest.py`.

BR-TRANSFER-001
Description: Si la demande ne concerne aucun service de la direction, le directeur peut transferer vers la direction chargee de resoudre; le ticket suit ensuite le chemin d'entree de la nouvelle direction.
Fichiers: `ticket_actions.py`, `ServiceRequest.py`, `app.direction.tsx`.

BR-PRIORITY-001
Description: Le changement de priorite est accorde a tous les chefs, directeurs et admins.
Fichiers: `ticket_actions.py`, `capabilities.ts`.

BR-REOPEN-001
Description: En reouverture, le cycle reprend depuis `reopened`, pas depuis creation.
Fichiers: `ServiceRequest.py`, `workflow-timeline.tsx`.

BR-TIMELINE-001
Description: Tous les commentaires et actions doivent etre visibles dans le detail d'une demande jusqu'a cloture.
Fichiers: `RouteRequest.py`, `RouteWorkflow.py`, `ServiceWorkflow.py`, `workflow-timeline.tsx`.

BR-REQ-REF-001
Description: La reference demande suit la formule direction-demandeur/service-demandeur-horodatage-sequence.
Fichiers: `ServiceRequest.py`, `RepositoryRequest.py`.
Tests: `test_requests_baseline.py`.

## Notifications

BR-NOTIF-001
Description: Les notifications liees a un ticket doivent viser uniquement le prochain acteur du workflow, jamais toute une direction ou tout un service par defaut.
Module: MOD-NOTIF, MOD-REQUEST.
Roles: tous les roles authentifies selon l'etape courante.
Fichiers: `NotificationEmitter.py`, `ServiceRequest.py`, `RouteRequest.py`, `RouteNotification.py`, `RouteSSE.py`.
Endpoints: `GET /notifications/*`, actions ticket dans `POST /requests/{id}/*`.
Tables: `notification`, `workflow_detail`, `request`, `account`.
Note implementation: le destinataire attendu est le compte precis deja trace par l'action (`workflow_detail.dest_id`, `infos.target_user_id`, `request.assignee_id` ou `request.requester_id` selon le cas). Les events temps reel `notification.created` doivent etre cibles avec `target.user_ids=[recipient_id]`.

## Reporting

BR-REPORT-001
Description: Les rapports sont scopes au role: chef service, directeur direction; admin global ou filtre direction explicite.
Fichiers: `ServiceReport.py`, `app.reports.tsx`.

BR-REPORT-DECISION-001
Description: Le moteur decisionnel consolide chaque ticket une seule fois dans la hierarchie EDG -> direction -> service/unite -> agent/responsable -> ticket; les KPI des niveaux superieurs sont recalcules depuis les tickets uniques du niveau inferieur. Il doit fournir trois niveaux de lecture: executive, analytique et audit, avec colonnes groupees, filtres multi-criteres, recherche, tri, pagination audit et exports complets sur le perimetre filtre.
Fichiers: `ServiceReport.py`, `RouteReports.py`, `reports.ts`, `REPORTING_DECISION_ENGINE.md`.
Endpoints: `GET /reports/decision`, `GET /reports/decision/export`.
Tables: `request`, `request_status`, `priority_definition`, `request_category`, `unity`, `account`, `workflow`, `workflow_detail`, `attachment`, `appreciation`.
Note implementation: aucun indicateur ne doit etre invente; les donnees absentes ou non structurees sont documentees comme limites ou ameliorations futures.

BR-DIRECTION-SERVICE-001
Description: La performance par service d'un directeur doit lister uniquement les services rattaches a sa direction.
Fichiers: `ServiceReport.py`, `app.reports.tsx`, `RouteReports.py`.
