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
| `agent-support` | Agent Support | traitement quotidien | idem user | tickets assignes, file, qualification | `/app/my-tickets`, `/app/queue` | tickets personnellement assignes; tickets libres non assignes de son unite (service); triage selon regle | qualifier, s'auto-assigner, traiter, resoudre, escalader, changer son etat selon scope |
| `chief-service` | Chef de Service | responsable d'un service | idem user | service/equipe, file, supervision, SLA, rapports | `/app/chief-inbox`, `/app/queue`, `/app/supervision`, `/app/sla-center`, `/app/reports` | tickets de son service/unite uniquement | assigner a agent de son service, reassigner service dans la direction, priorite, escalade, approuver/rejeter reouverture |
| `chief-departement` | Chef Departement | validation/suivi departemental | idem user | departement (plusieurs services), supervision, SLA, rapports | `/app/department-inbox`, `/app/supervision`, `/app/sla-center`, `/app/reports` | tickets de tous les services rattaches a son departement (perimetre elargi via l'organigramme, pas juste sa propre unite) | idem chief-service, mais assignation/traitement possibles sur n'importe quel service de son departement |
| `director` | Direction DSI | pilotage/arbitrage direction | idem user | supervision direction, vue direction, SLA, rapports | `/app/supervision`, `/app/direction`, `/app/sla-center`, `/app/reports` | tickets des departements/services rattaches a sa direction | transfert direction/service selon regle, arbitrage, resoudre uniquement tickets escalades, priorite, reouverture |
| `admin` | Administrateur | administration systeme | idem user | backoffice complet et vue globale | `/app/admin/*`, `/app/dg` | toutes donnees admin | config, users, refs, SLA, routing, logs, actions globales |

Note compatibilite: l'ancien role technique `dg` est conserve uniquement comme alias legacy normalise vers `director` (voir `LEGACY_ROLE_ALIASES` dans `rbac.py`). Il ne doit plus etre propose, attribue ni utilise comme role metier. La route frontend `/app/dg` est un nom de fichier historique — elle exige desormais le role `admin` (vue globale pilotage), pas `dg`.

Note perimetre chief-departement vs chief-service: les deux roles partagent la meme matrice de permissions (`ROLE_PERMISSIONS`), la difference est une question de **perimetre organisationnel** calcule dynamiquement via l'organigramme (`_direction_unity_ids` / `_get_dir_unity_ids`, "departement + services rattaches") plutot qu'un droit supplementaire. Depuis 2026-07-27, les deux roles ont aussi chacun leur propre espace frontend nomme (`/app/chief-inbox` pour chief-service, `/app/department-inbox` pour chief-departement) — meme composant partage (`ChiefInbox` dans `app.chief-inbox.tsx`), guard de role et route distincts, perimetre de donnees adapte via detection de l'URL courante. Voir `BR-ROLE-CHIEF-DEPARTEMENT-001` dans `BUSINESS_RULES.md`.

## Permissions backend

Source: `backend/api/core/rbac.py`.

Les permissions sont cumulatives dans la hierarchie:

```text
public < user < agent-support < chief-service = chief-departement < director < admin
```

Permissions importantes:

- user: `CREATE_REQUEST`, `VIEW_OWN_REQUESTS`, `CANCEL_REQUEST`, `VIEW_NOTIFICATIONS`;
- agent-support: `VIEW_ALL_REQUESTS`, `ASSIGN_REQUEST`, `CLOSE_REQUEST`, `REOPEN_REQUEST`, `ESCALATE_REQUEST`, `VIEW_WORKFLOWS`, `VIEW_TASKS`;
- chief-service / chief-departement: `MANAGE_REQUESTS`, `MANAGE_ESCALATIONS`, `VIEW_REPORTS`, `VIEW_STATS`, `MANAGE_WORKFLOWS` (memes permissions ; perimetre organisationnel different, voir note ci-dessus);
- director: `VIEW_GLOBAL_REPORTS`;
- admin: toutes permissions.

## Actions ticket backend

Source: `backend/api/core/ticket_actions.py`.

| Action | Roles backend | Note |
| --- | --- | --- |
| `qualify` | agent-support, chief-service, chief-departement, admin | qualification/orientation |
| `assign` | agent-support, chief-service, chief-departement, admin | agent seulement auto-assignation; chief-service vers agent de son service; chief-departement vers agent de n'importe quel service de son departement |
| `resolve` | agent-support, chief-service, chief-departement, director, admin | director seulement si ticket escalade/arbitrage |
| `close` | user, agent-support, chief-service, chief-departement, director, admin | demandeur peut cloturer sa demande resolue |
| `request_reopen` | user, agent-support, chief-service, chief-departement, director, admin | seul demandeur via scope |
| `reopen`, `reject_reopen` | chief-service, chief-departement, director, admin | demande de reouverture requise |
| `cancel` | user, agent-support, chief-service, chief-departement, director, admin | scope applique |
| `reassign` | chief-service, chief-departement, director, admin | service selon perimetre (meme direction) |
| `transfer_direction` | director, admin | transfert inter-direction |
| `reject` | chief-service, chief-departement, admin | rejet demande/ticket |
| `escalate` | agent-support, chief-service, chief-departement, director, admin | agent seulement ticket assigne |
| `change_priority` | chief-service, chief-departement, director, admin | tous chefs inclus |

## Regles de navigation

- Ouverture depuis `Mes demandes`: detail personnel `/app/requests/$id`.
- Ouverture depuis un espace pro: detail dans l'espace pro correspondant.
- Le bouton retour doit revenir a la liste d'origine.
