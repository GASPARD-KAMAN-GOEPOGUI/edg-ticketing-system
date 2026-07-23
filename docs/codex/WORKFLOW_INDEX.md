# Workflow Index

## Statuts ticket

`new`, `qualifying`, `qualified`, `assigned`, `in_progress`, `pending`, `escalated`, `resolved`, `closed`, `reopened`, `rejected`, `cancelled`.

Normalisation: les anciens codes fautifs `cancalled` et `escaladed` doivent etre interpretes comme `cancelled` et `escalated`.

## Transitions backend autorisees

Source: `backend/api/core/ticket_actions.py`.

| Statut cible | Sources autorisees |
| --- | --- |
| `qualifying` | `new`, `reopened`, `qualified`, `assigned`, `in_progress`, `pending`, `escalated` |
| `qualified` | `qualifying` |
| `assigned` | `qualified`, `qualifying`, `new`, `reopened` |
| `in_progress` | `assigned`, `qualifying`, `qualified`, `pending`, `escalated` |
| `pending` | `in_progress`, `assigned` |
| `escalated` | `in_progress`, `assigned`, `pending`, `qualifying` |
| `resolved` | `in_progress`, `assigned`, `escalated`, `pending` |
| `closed` | `resolved` |
| `reopened` | `resolved`, `rejected`, `closed` |
| `rejected` | `new`, `qualifying`, `qualified`, `assigned`, `in_progress`, `pending` |
| `cancelled` | `new`, `qualifying`, `qualified`, `assigned`, `in_progress`, `pending` |

Les statuts terminaux `cancelled`, `closed`, `resolved`, `rejected` ne peuvent pas transiter vers `assigned`.

Roles bypass transition: `admin`, `dg`.

## Etapes metier principales

| Etape | Acteur | Statut initial | Action | Statut resultant | Endpoint | Tables modifiees | Notification |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Creation | user+ ou public | aucun | creer demande | `new` ou routage initial selon service | `POST /requests` | `request`, `workflow` | oui |
| Qualification | agent/chief/admin | `new`/`reopened` | qualifier/orienter | `qualifying` puis `qualified`/`assigned` selon logique | `POST /requests/{id}/qualify` | `request`, `workflow_detail` | oui |
| Assignation | agent/chief/admin | `new`, `qualifying`, `qualified`, `reopened` | assigner | `assigned` | `POST /requests/{id}/assign` | `request`, `workflow_detail` | oui |
| Traitement | agent/chief | `assigned` | prise en charge | `in_progress` ou action service | `PATCH /requests/{id}` selon action | `request`, `workflow_detail` | oui |
| Mise en attente | agent/chief | `assigned`, `in_progress` | attente | `pending` | `PATCH /requests/{id}` | `request`, `workflow_detail` | oui |
| Escalade | agent/chief/director/admin | `qualifying`, `assigned`, `in_progress`, `pending` | escalader | `escalated` | `POST /requests/{id}/escalate` | `workflow_detail`, `request` | oui |
| Arbitrage direction | director/admin | `escalated` | resoudre ou transferer | `resolved` ou changement perimetre | `POST /resolve`, `POST /transfer-direction` | `request`, `workflow_detail` | oui |
| Resolution | agent/chief/director/admin | `assigned`, `in_progress`, `pending`, `escalated` | resoudre | `resolved` | `POST /requests/{id}/resolve` | `request`, `workflow_detail` | oui |
| Cloture | demandeur/user+ selon scope | `resolved` | cloturer | `closed` | `POST /requests/{id}/close` | `request`, `workflow_detail` | oui |
| Demande reouverture | demandeur | `resolved`, `closed`, `rejected` | demander reopen | trace pending reopen | `POST /requests/{id}/request-reopen` | `workflow_detail` | oui |
| Reouverture acceptee | chief/director/admin | `resolved`, `closed`, `rejected` | rouvrir | `reopened` | `POST /requests/{id}/reopen` | `request`, `workflow_detail` | oui |
| Reouverture rejetee | chief/director/admin | `resolved`, `closed`, `rejected` | rejeter reopen | statut conserve | `POST /requests/{id}/reject-reopen` | `workflow_detail` | oui |

## Timeline et commentaires

Les commentaires et actions doivent accompagner la demande jusqu'a cloture. Source principale: `workflow_detail`.

Endpoints:

- `GET /requests/{request_id}/comments`
- `POST /requests/{request_id}/comments`
- `GET /requests/{request_id}/timeline`
- `POST /requests/{request_id}/timeline`
- endpoints `/workflows/*` pour details/circuit.

## Reouverture

Lorsqu'un ticket est rouvert, le cycle reprend avec le premier statut `reopened` au lieu de `creation`. Les niveaux non sollicites ne doivent pas faire croire qu'ils ont traite le ticket.
