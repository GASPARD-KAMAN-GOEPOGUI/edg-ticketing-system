# Role Index

## Principe

Chaque role a deux espaces:

- espace personnel: ses demandes, son historique, son profil, ses notifications;
- espace professionnel: donnees traitees, supervisees, validees ou administrees.

Ne pas melanger ces deux contextes dans la navigation ni dans les permissions.

## Roles

Nomenclature canonique alignee sur les 6 acteurs du cahier des charges DSI + `public` (extension hors CDC conservee pour le suivi/KB publics).

| Role | Acteur CDC | Objectif | Espace personnel | Espace professionnel | Pages pro | Donnees visibles | Actions autorisees principales |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `public` | *(hors CDC)* | visiteur | suivi public, knowledge public | aucun | `/track`, `/knowledge` | demande par ref + justificatif | suivre, consulter KB publique |
| `user` | Utilisateur | demandeur/employe | `/app`, `/app/requests`, `/app/requests/history`, `/app/profile` | aucun traitement ticket | aucun | ses demandes | creer, modifier si `new`, annuler, demander reouverture, cloturer apres resolution |
| `chief-service` | Agent Support | traitement quotidien | idem user | tickets assignes, file, qualification | `/app/my-tickets`, `/app/queue` | tickets personnellement assignes; tickets libres non assignes de son unite (service); triage selon regle | qualifier, s'auto-assigner, traiter, resoudre, escalader, changer son etat selon scope |
| `chief-service` | Chef de Service | responsable d'un service | idem user | Mon travail (traitement personnel) + Pilotage (service), SLA, rapports | `/app/my-tickets`, `/app/queue`, `/app/chief-inbox`, `/app/supervision`, `/app/sla-center`, `/app/reports` | tickets de son service/unite uniquement | s'auto-assigner (file d'attente), assigner a agent de son service, reassigner service dans la direction, priorite, escalade, approuver/rejeter reouverture |
| `chief-departement` | Chef Departement | validation/suivi departemental | idem user | Mon travail (traitement personnel) + Pilotage (departement), SLA, rapports | `/app/my-tickets`, `/app/queue`, `/app/department-inbox`, `/app/supervision`, `/app/sla-center`, `/app/reports` | tickets de tous les services rattaches a son departement (perimetre elargi via l'organigramme, pas juste sa propre unite) | prendre un ticket, recevoir/faire une assignation vers un role operationnel de son perimetre, traiter/transmettre/terminer s'il est intervenant courant |
| `director` | Direction DSI | pilotage/arbitrage direction | idem user | Mon travail (`/app/direction` et `/app/my-tickets`) + Pilotage direction, SLA, rapports | `/app/my-tickets`, `/app/direction`, `/app/queue`, `/app/supervision`, `/app/strategic-dashboard`, `/app/sla-center`, `/app/reports` | tickets des departements/services rattaches a sa direction | prendre un ticket, recevoir/faire une assignation vers un role operationnel de sa direction, traiter/transmettre/terminer s'il est intervenant courant, priorite, reouverture |
| `admin` | Administrateur | administration systeme | idem user | backoffice complet et vue globale | `/app/admin/*`, `/app/dg` | toutes donnees admin | config, users, refs, SLA, routing, logs, actions globales |

Note compatibilite: l'ancien role technique `dg` est conserve uniquement comme alias legacy normalise vers `director` (voir `LEGACY_ROLE_ALIASES` dans `rbac.py`). Il ne doit plus etre propose, attribue ni utilise comme role metier. La route frontend `/app/dg` est un nom de fichier historique — elle exige desormais le role `admin` (vue globale pilotage), pas `dg`.

Note perimetre chief-departement vs chief-service: les deux roles partagent la meme matrice de permissions (`ROLE_PERMISSIONS`), la difference est une question de **perimetre organisationnel** calcule dynamiquement via l'organigramme (`_direction_unity_ids` / `_get_dir_unity_ids`, "departement + services rattaches") plutot qu'un droit supplementaire. Depuis 2026-07-27, les deux roles ont aussi chacun leur propre espace frontend nomme (`/app/chief-inbox` pour chief-service, `/app/department-inbox` pour chief-departement) — meme composant partage (`ChiefInbox` dans `app.chief-inbox.tsx`), guard de role et route distincts, perimetre de donnees adapte via detection de l'URL courante. Voir `BR-ROLE-CHIEF-DEPARTEMENT-001` dans `BUSINESS_RULES.md`.

Note navigation Mon travail (2026-08-05): le raccourci menu dedie "Reouvertures" est retire. Les tickets `reopened` restent visibles dans "Ma boite de traitement" (`/app/my-tickets`) pour les roles qui traitent personnellement des tickets assignes.

## Permissions backend

Source: `backend/api/core/rbac.py`.

Les permissions sont cumulatives dans la hierarchie:

```text
public < user < chief-service < chief-service = chief-departement < director < admin
```

Permissions importantes:

- user: `CREATE_REQUEST`, `VIEW_OWN_REQUESTS`, `CANCEL_REQUEST`, `VIEW_NOTIFICATIONS`;
- chief-service: `VIEW_ALL_REQUESTS`, `ASSIGN_REQUEST`, `CLOSE_REQUEST`, `REOPEN_REQUEST`, `ESCALATE_REQUEST`, `VIEW_WORKFLOWS`, `VIEW_TASKS`;
- chief-service / chief-departement: `MANAGE_REQUESTS`, `MANAGE_ESCALATIONS`, `VIEW_REPORTS`, `VIEW_STATS`, `MANAGE_WORKFLOWS` (memes permissions ; perimetre organisationnel different, voir note ci-dessus);
- director: `VIEW_GLOBAL_REPORTS`;
- admin: toutes permissions.

## Actions ticket backend

Source: `backend/api/core/ticket_actions.py`.

| Action | Roles backend | Note |
| --- | --- | --- |
| `qualify` | chief-service, chief-service, chief-departement, director, admin (`dg` exclu) | qualification/orientation/prise depuis file |
| `assign` | chief-service, chief-service, chief-departement, director, admin (`dg` exclu) | assignation vers tout role operationnel autorise, avec controle de perimetre pour les non-admin; destinataire admin reserve a admin |
| `resolve` ("Terminer le traitement") | chief-service, chief-service, chief-departement, director, admin | BR-TRANSMIT-001 : reserve a l'intervenant actuel (`assignee_id == actor.id`), quel que soit le role parmi ceux-ci ; resume/solution/travail realise obligatoires |
| `transmit_treatment` ("Transmettre le traitement") | chief-service, chief-service, chief-departement, director, admin | BR-TRANSMIT-001 : reserve a l'intervenant actuel ; cible libre dans toute l'organisation (role traitant + actif) ; statut preserve |
| `close` | user, chief-service, chief-service, chief-departement, director, admin | demandeur peut cloturer sa demande resolue |
| `request_reopen` | user, chief-service, chief-service, chief-departement, director, admin | seul demandeur via scope |
| `reopen`, `reject_reopen` | chief-service, chief-departement, director, admin | demande de reouverture requise |
| `cancel` | user, chief-service, chief-service, chief-departement, director, admin | scope applique |
| `reassign` | chief-service, chief-departement, director, admin | service selon perimetre (meme direction) |
| `transfer_direction` | director, admin | transfert inter-direction |
| `reject` | chief-service, chief-departement, admin | rejet demande/ticket |
| `escalate` | chief-service, chief-service, chief-departement, director, admin | agent seulement ticket assigne |
| `change_priority` | chief-service, chief-departement, director, admin | tous chefs inclus |

## Regles de navigation

- Ouverture depuis `Mes demandes`: detail personnel `/app/requests/$id`.
- Ouverture depuis un espace pro: detail dans l'espace pro correspondant.
- Le bouton retour doit revenir a la liste d'origine.
