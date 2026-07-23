# Moteur De Reporting Decisionnel

Date: 2026-07-13

## Objectif

Le moteur decisionnel consolide les tickets EDG sans doublon selon la hierarchie:

EDG -> Direction -> Service / Unite -> Agent ou Responsable -> Ticket.

Il reutilise le module existant `MOD-REPORT`:

- service backend: `backend/api/services/ServiceReport.py`
- route backend: `backend/api/routes/RouteReports.py`
- API frontend: `frontend/src/lib/api/reports.ts`
- endpoint JSON: `GET /api/v1/reports/decision`
- endpoint export: `GET /api/v1/reports/decision/export`

Il ne remplace pas les rapports existants `daily`, `monthly`, `by-agent`, `by-unity`, `sla`, `csat`; il les complete pour les tableaux de bord decisionnels, les audits et les exports de pilotage.

## Trois Niveaux De Lecture

Le endpoint JSON expose `tables` avec trois vues complementaires:

1. `executive`: vue synthetique par direction, destinee DG, admin, direction generale, comite de direction.
2. `analytical`: vue detaillee regroupable par `direction`, `service`, `status`, `category`, `priority`, `assignee` ou `period`.
3. `audit`: lignes ticket par ticket, paginees, triables et exportables pour retrouver l'origine de chaque chiffre.

Chaque vue partage les memes totaux consolides afin d'eviter les ecarts entre synthese, analyse et audit.

## Perimetres Et Filtres

Filtres supportes:

- `start`, `end`: periode basee sur `request.created_at`
- `direction_id`: direction EDG
- `unity_id`: service / unite
- `assignee_id`: agent ou responsable assigne
- `status`: un ou plusieurs codes `request_status.code`, separes par virgule
- `category`: un ou plusieurs codes `request_category.code`
- `priority`: un ou plusieurs `priority_definition.slug`
- `source`: un ou plusieurs canaux `request.request_source`
- `origin`: `internal` ou `external`, base sur `request.is_external`
- `search`: recherche sur reference, titre, demandeur, unite ou agent
- `group_by`: regroupement de la vue analytique
- `inactive_days`: seuil pour tickets actifs sans activite recente
- `page`, `limit`, `sort_by`, `sort_dir`: pagination et tri de la vue audit
- `include_tickets`: inclut les feuilles tickets dans la hierarchie
- `include_audit_rows`: inclut toutes les lignes audit triees pour l'export complet

Scoping roles:

- `admin`, `dg`: vue globale ou filtre explicite.
- `director`: force sa direction.
- `chief`: force son service/unite.

Roles futurs non presents dans le modele actuel:

- auditeur;
- controle interne.

Ces roles devront etre ajoutes au modele `Account.role`, au RBAC et aux regles d'acces avant d'avoir un acces dedie.

## Methode Anti-Doublon

Le calcul charge une seule ligne par `request.id`.

La timeline `workflow_detail` est agregee dans une sous-requete par `workflow.request_id`, puis jointe au ticket. Ainsi, plusieurs commentaires, escalades ou actions sur un ticket ne creent pas plusieurs lignes de comptage.

Controle retourne:

- `data_quality.rows_loaded`
- `data_quality.unique_ticket_count`
- `data_quality.duplicate_ticket_count`

`duplicate_ticket_count` doit rester a `0`.

## Groupes De Colonnes

Les tableaux sont exposes avec `tables.column_groups` pour permettre une UI lisible avec colonnes configurables.

Vue executive:

- Perimetre: direction, service/unite
- Volumes: total, ouverts, backlog, critiques
- SLA: taux de respect, hors SLA, retard
- Performance: resolution, cloture, delai resolution
- Tendance: delta et delta pourcentage

Vue analytique:

- Perimetre: direction, service/unite, responsable de traitement
- Statuts: nouveaux, a qualifier, affectes, en cours, attente validation, resolus, fermes, escalades, reouverts
- SLA: respectes, hors SLA, taux SLA, plus vieux ticket actif
- Delais: qualification, affectation, premiere prise en charge, traitement, resolution, fermeture
- Qualite: priorite dominante, categorie dominante, satisfaction, commentaires, pieces jointes

Vue audit:

- Ticket: reference, titre, statut, priorite, categorie
- Organisation: direction, service/unite, responsable
- Origine: canal, interne/externe, demandeur, localisation
- Dates: creation, derniere activite, resolution, cloture
- SLA et delais: hors SLA, cause derivee, premiere prise en charge, resolution
- Tracabilite: motifs escalade/reouverture si traces, commentaires, interactions, pieces jointes

## KPI Et Formules

| KPI | Definition | Formule | Source | Perimetre | Agregation |
| --- | --- | --- | --- | --- | --- |
| `total_tickets` | Tickets distincts du perimetre | `COUNT(DISTINCT request.id)` | `request.id` | periode + filtres | somme des tickets uniques |
| `new_tickets` | Tickets nouveaux | statut `new` | `request_status.code` | periode + filtres | somme |
| `qualifying_tickets` | Tickets a qualifier ou en triage | statut `qualifying` ou `request.in_triage=true` | `request_status.code`, `request.in_triage` | periode + filtres | somme |
| `assigned_tickets` | Tickets affectes | statut `assigned` | `request_status.code` | periode + filtres | somme |
| `open_tickets` | Tickets actifs non termines | statut dans `new, qualifying, qualified, assigned, in_progress, pending, pending_validation, escalated, reopened` | `request_status.code` | periode + filtres | somme |
| `in_progress_tickets` | Tickets en cours | statut `in_progress` | `request_status.code` | periode + filtres | somme |
| `pending_validation_tickets` | Tickets en attente de validation | statut `pending` ou `pending_validation` | `request_status.code` | periode + filtres | somme |
| `resolved_tickets` | Tickets resolus non clotures | statut `resolved` | `request_status.code` | periode + filtres | somme |
| `closed_tickets` | Tickets clotures | statut `closed` | `request_status.code` | periode + filtres | somme |
| `escalated_tickets` | Tickets escalades actuellement ou ayant une escalade tracee | statut `escalated` ou evenement `escalated/escalation_manual` | `request_status.code`, `workflow_detail.event_type` | periode + filtres | somme par ticket unique |
| `reopened_tickets` | Tickets reouverts actuellement ou ayant une reouverture tracee | statut `reopened` ou evenement `reopened` | `request_status.code`, `workflow_detail.event_type` | periode + filtres | somme par ticket unique |
| `backlog_tickets` | Tickets actifs hors traitement final | statut dans `new, qualifying, qualified, assigned, pending, pending_validation, escalated, reopened` | `request_status.code` | periode + filtres | somme |
| `critical_tickets` | Tickets critiques | priorite `critical` | `priority_definition.slug` | periode + filtres | somme |
| `urgent_tickets` | Tickets urgents ou hauts | priorite `urgent` ou `high` | `priority_definition.slug` | periode + filtres | somme |
| `overdue_tickets` | Tickets en retard | `request.sla_breached=true` | `request.sla_breached` | periode + filtres | somme |
| `sla_breached_tickets` | Tickets hors SLA | `request.sla_breached=true` | `request.sla_breached` | periode + filtres | somme |
| `sla_respected_tickets` | Tickets avec SLA renseigne et non depasse | `sla_hours > 0 AND sla_breached=false` | `request.sla_hours`, `request.sla_breached` | periode + filtres | somme |
| `sla_compliance_rate` | Taux de respect SLA | `sla_respected / (sla_respected + sla_breached) * 100` | KPI SLA consolides | niveau courant | recalcul sur totaux |
| `resolution_rate` | Taux de resolution | `(resolved_tickets + closed_tickets) / total_tickets * 100` | KPI consolides | niveau courant | recalcul sur totaux |
| `closure_rate` | Taux de cloture | `closed_tickets / total_tickets * 100` | KPI consolides | niveau courant | recalcul sur totaux |
| `avg_qualification_hours` | Delai moyen de qualification/orientation | moyenne `created_at -> premier qualifying/qualified/assigned` | `request.created_at`, `workflow_detail.created_at` | tickets avec evenement trace | moyenne ponderee |
| `avg_assignment_hours` | Delai moyen d'affectation | moyenne `created_at -> premier assigned/reassigned_service` | `request.created_at`, `workflow_detail.created_at` | tickets avec evenement trace | moyenne ponderee |
| `avg_first_response_hours` | Delai moyen de premiere prise en charge | moyenne `created_at -> premier assigned/in_progress` | `request.created_at`, `workflow_detail.created_at` | tickets avec evenement trace | moyenne ponderee |
| `avg_treatment_hours` | Delai moyen de traitement effectif | moyenne `premier assigned/in_progress -> resolved_at` | `workflow_detail.created_at`, `request.resolved_at` | tickets resolus et tracables | moyenne ponderee |
| `avg_resolution_hours` | Delai moyen de resolution | moyenne `created_at -> resolved_at` | `request.created_at`, `request.resolved_at` | tickets resolus | moyenne ponderee |
| `avg_closure_hours` | Delai moyen de fermeture apres resolution | moyenne `resolved_at -> closed_at` | `request.resolved_at`, `request.closed_at` | tickets clotures | moyenne ponderee |
| `avg_ticket_age_hours` | Age moyen des tickets | moyenne `created_at -> closed_at/resolved_at/NOW()` | `request.created_at`, `request.resolved_at`, `request.closed_at` | periode + filtres | moyenne ponderee |
| `oldest_active_ticket_hours` | Plus vieux ticket actif | max `created_at -> NOW()` pour statuts actifs | `request.created_at`, `request_status.code` | tickets actifs | maximum |
| `unassigned_tickets` | Tickets sans affectation | `assignee_id IS NULL` | `request.assignee_id` | periode + filtres | somme |
| `inactive_tickets` | Tickets actifs sans activite recente | `last_activity_age_hours >= inactive_days*24` | `workflow_detail.created_at`, `request.updated_at` | tickets actifs | somme |
| `internal_tickets` | Tickets internes | `is_external=false` | `request.is_external` | periode + filtres | somme |
| `external_tickets` | Tickets externes | `is_external=true` | `request.is_external` | periode + filtres | somme |
| `comment_count` | Volume de commentaires | `COUNT(workflow_detail WHERE event_type=comment_added)` | `workflow_detail.event_type` | periode + filtres | somme |
| `interaction_count` | Volume d'interactions tracees | `COUNT(workflow_detail.id)` | `workflow_detail.id` | periode + filtres | somme |
| `attachment_count` | Nombre de pieces jointes | `COUNT(attachment.id)` | `attachment.request_id` | periode + filtres | somme |
| `avg_satisfaction_rating` | Satisfaction moyenne | moyenne `appreciation.rating` | `appreciation.rating` | tickets notes | moyenne ponderee |
| `dominant_priority` | Priorite dominante | valeur la plus frequente | `priority_definition.slug` | groupe courant | recalcul |
| `dominant_category` | Categorie dominante | valeur la plus frequente | `request_category.code` | groupe courant | recalcul |
| `dominant_source` | Canal dominant | valeur la plus frequente | `request.request_source` | groupe courant | recalcul |
| `trend_total_delta` | Evolution en volume | `current_total - previous_total` | KPI courant + precedent | groupe courant | recalcul |
| `trend_total_delta_pct` | Evolution en pourcentage | `delta / previous_total * 100` | KPI courant + precedent | groupe courant | recalcul |

## Rapports Decisionnels

Le endpoint JSON renvoie:

- `kpis`: synthese globale du perimetre filtre;
- `previous_kpis`: synthese de la periode precedente;
- `trends`: ecarts absolus et pourcentage;
- `hierarchy`: arbre EDG -> direction -> service -> agent -> ticket;
- `tables.executive`, `tables.analytical`, `tables.audit`;
- `tables.column_groups`;
- `tables.capabilities`: tri, filtres multi-criteres, recherche, pagination, colonnes configurables, regroupement, sous-totaux, totaux, export complet, impression;
- `breakdowns.direction`;
- `breakdowns.service`;
- `breakdowns.status`;
- `breakdowns.category`;
- `breakdowns.priority`;
- `breakdowns.assignee`;
- `breakdowns.period`;
- `kpi_catalog`;
- `data_quality`.

L'export supporte `group_by`:

- `global`
- `executive`
- `direction`
- `service`
- `status`
- `category`
- `priority`
- `assignee`
- `period`
- `audit`

Formats:

- `csv`
- `excel`
- `pdf`

Les exports ajoutent les metadonnees:

- `periode`
- `genere_le`
- `genere_par`
- `filtres`

Regle d'export: l'export doit reprendre le perimetre filtre complet. La vue audit paginee affiche une page, mais l'export audit utilise `include_audit_rows=true` pour exporter toutes les lignes du perimetre trie.

## Historique Et Tendances

La tendance compare la periode courante a la periode precedente de meme duree.

Exemple: si `start=2026-07-01` et `end=2026-07-10`, la periode precedente est `2026-06-21` a `2026-06-30`.

KPI compares:

- `total_tickets`
- `open_tickets`
- `resolved_tickets`
- `closed_tickets`
- `backlog_tickets`
- `sla_breached_tickets`

## Donnees Disponibles Et Limites

Donnees disponibles:

- direction, service/unite, agent/responsable: `unity`, `account`, rattachement du ticket;
- statut, categorie, priorite: tables referentielles liees a `request`;
- SLA et delais: `request.sla_*`, `request.created_at`, `request.resolved_at`, `request.closed_at`;
- timeline, commentaires, escalades, reouvertures, derniere activite: `workflow_detail`;
- canal et origine: `request.request_source`, `request.is_external`;
- localisation: `request.location_label`, `request.lat`, `request.lng`;
- satisfaction: `appreciation.rating`, `appreciation.resolved_confirmed`;
- pieces jointes: `attachment.request_id`.

Donnees partiellement disponibles:

- motifs d'escalade et de reouverture: recuperes depuis `workflow_detail.comment` ou `workflow_detail.label`, non encore normalises par referentiel;
- cause de retard: non structuree, `late_cause` est derivee en `SLA depasse` lorsque `request.sla_breached=true`;
- site/localisation: disponible en libelle et coordonnees si saisi, pas de referentiel de site dedie;
- niveau auditeur/controle interne: roles non presents dans `Account.role`.

Ameliorations futures:

- ajouter un modele d'acces dedie pour auditeurs et controle interne;
- ajouter un referentiel structure de causes de retard;
- normaliser les motifs d'escalade et de reouverture;
- ajouter des snapshots de reporting si le volume rend le recalcul a la demande trop couteux;
- rendre obligatoires certains evenements metier pour ameliorer les delais historiques.
