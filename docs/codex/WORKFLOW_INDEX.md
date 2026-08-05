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
| Transmission (BR-TRANSMIT-001) | intervenant actuel (agent-support/chief-service/chief-departement/director) | `assigned`, `in_progress`, `pending`, `escalated` | transmettre le traitement a un intervenant choisi librement | statut inchange, `assignee_id` change | `POST /requests/{id}/transmit` | `request`, `workflow_detail` | oui |
| Resolution / "Terminer le traitement" (BR-TRANSMIT-001) | intervenant actuel (agent-support/chief-service/chief-departement/director/admin) | `assigned`, `in_progress`, `pending`, `escalated` | resoudre (resume/solution/travail realise obligatoires) | `resolved` | `POST /requests/{id}/resolve` | `request`, `workflow_detail` | oui |
| Cloture | demandeur/user+ selon scope | `resolved` | cloturer | `closed` | `POST /requests/{id}/close` | `request`, `workflow_detail` | oui |
| Demande reouverture | demandeur | `resolved`, `closed`, `rejected` | demander reopen | trace pending reopen | `POST /requests/{id}/request-reopen` | `workflow_detail` | oui |
| Reouverture acceptee (BR-REOPEN-QUEUE-001) | chief/director/admin | `resolved`, `closed`, `rejected` | rouvrir | `reopened`, `assignee_id=null`, `in_triage=true` (retour File d'attente) | `POST /requests/{id}/reopen` | `request`, `workflow_detail`, `notification` | oui |
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

Retour automatique en File d'attente (BR-REOPEN-QUEUE-001, 2026-08-04) : l'approbation de reouverture (`POST /requests/{id}/reopen`) libere systematiquement l'ancien intervenant — `assignee_id=null` — et remet le ticket dans les criteres de la File d'attente (`in_triage=true`, statut `reopened` deja present dans `RepositoryRequest._QUALIFIABLE_STATUSES`). L'ancien intervenant n'est jamais reaffecte automatiquement (notification purement informative) ; un nouvel agent (ou le meme, s'il le souhaite) doit reprendre le ticket depuis `/requests/triage` comme n'importe quelle demande en attente, ce qui demarre un nouveau cycle d'intervention. Tant qu'aucun `assignee_id` n'est defini, `transmit_treatment`/`resolve` restent indisponibles (`TICKET_ACTION_STATUSES` exclut `reopened`) — voir BR-REOPEN-QUEUE-001 dans `BUSINESS_RULES.md`.

Cycle SLA independant (BR-SLA-REOPEN-001, 2026-08-04) : la meme approbation demarre aussi un nouveau cycle SLA mesure depuis la date de reouverture — le cycle SLA precedent (deja clos par la resolution qui a precede la demande de reouverture) reste fige definitivement, jamais recalcule. Voir BR-SLA-REOPEN-001 dans `BUSINESS_RULES.md`.

## Workflow collaboratif dynamique et cycles d'intervention (BR-TRANSMIT-001)

Apres la file d'attente (qualification/assignation initiale), le traitement d'un ticket n'est plus une chaine fixe d'intervenants : l'intervenant actuel (`request.assignee_id`) peut transmettre le traitement a n'importe quel autre intervenant traitant actif de l'organisation (`POST /requests/{id}/transmit`), autant de fois que necessaire, jusqu'a ce que quelqu'un termine le traitement (`POST /requests/{id}/resolve`). Un meme acteur peut revenir plusieurs fois sur le meme ticket (plusieurs cycles distincts).

- Intervenant actuel: `request.assignee_id` — un seul a la fois.
- Participants: liste synthetique dedupliquee (un acteur = une seule entree), calculee cote frontend depuis la timeline (`buildParticipants` dans `app.requests.$id.tsx`), aucune donnee/backend dediee.
- Cycle d'intervention: segment append-only dans `workflow_detail`, jamais modifie/supprime. Un nouveau cycle commence a chaque `assigned` ou `treatment_transmitted`. `cycle_number` = nombre de cycles deja clotures (`treatment_transmitted`/`treatment_completed`) + 1, reconstruit a la volee (pas de nouvelle table).
- Evenements `workflow_detail`: `treatment_transmitted` (transmission — `infos.previous_assignee_id`, `new_assignee_id`, `work_done`, `reason`, `instruction`, `attachment_ids`, `started_at`, `ended_at`, `duration_seconds`, `cycle_number`) et `treatment_completed` (terminaison — `infos.summary`, `solution`, `work_done`, `recommendations`, `attachment_ids`, memes champs de cycle).
- Autorisation: garde generique `assert_is_current_handler` (`ticket_actions.py`) — l'acteur doit etre `request.assignee_id` ET avoir un role traitant (`agent-support`, `chief-service`, `chief-departement`, `director`). Le role seul ne suffit plus pour ces deux actions.
- Concurrence: ecriture atomique conditionnelle (`_atomic_conditional_update`) — 409 `TICKET_STATE_CONFLICT` si l'affectation a change entre lecture et ecriture.
- Ne jamais reutiliser `create_circuit`/`accept_detail` (`ServiceWorkflow.py`) pour ce workflow : ce mecanisme construit une chaine predefinie complete en un seul appel, incompatible avec un parcours dynamique decouvert au fil du traitement.

## Traçabilité des interventions (BR-TRACE-001)

Une intervention est un conteneur logique (pas un simple evenement) regroupant tout le travail d'un intervenant — commentaires, pieces jointes, travail effectue — depuis qu'il devient l'intervenant courant jusqu'a sa transmission ou sa resolution. Identification explicitement enregistree (jamais recalculee) : `intervention_id`, `intervention_order` (repart a 1 a chaque nouveau cycle SLA), `intervention_cycle_number` (aligne sur `sla_cycle_number`, BR-SLA-REOPEN-001, mais suivi independamment via un compteur explicite dans `request.infos`). Identite figee de l'intervenant (matricule/direction/departement/service) gravee au moment de l'action, jamais recalculee meme si le compte change ensuite. Reconstruit sans nouvelle table depuis `workflow_detail` — voir BR-TRACE-001 dans `BUSINESS_RULES.md`.
