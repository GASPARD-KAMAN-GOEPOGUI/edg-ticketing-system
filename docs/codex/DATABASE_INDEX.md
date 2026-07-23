# Database Index

## Base commune

La plupart des tables heritent de `BaseColumns`:

- `id` entier auto-increment;
- `uuid`;
- `status`;
- `infos` JSON;
- `created_at`, `updated_at`, `deleted_at`.

## Tables principales

| Table | Modele | Colonnes importantes | Relations | Modules |
| --- | --- | --- | --- | --- |
| `account` | `ModelAccount.py` | `unity_id`, `email`, `phone`, `role`, `account_status`, `matricule`, `availability` | `unity`, demandes assignees/demandees | auth, roles, tickets |
| `unity` | `ModelUnity.py` | `label`, `codename`, `aleas`, `parent_direction_id` | auto-relation direction/service | organisation, scope |
| `request` | `ModelRequest.py` | `ref`, `title`, `description`, `request_status_id`, `priority_definition_id`, `request_category_id`, `unity_id`, `assignee_id`, `requester_id`, `sla_*`, `resolved_at`, `closed_at` | status, priority, category, unity, assignee, requester, workflows | demandes/tickets |
| `request_status` | `ModelRequestStatus.py` | `code`, `label`, `sort_order` | request | statuts |
| `request_category` | `ModelRequestCategory.py` | `code`, `label`, `sort_order` | request | categories |
| `priority_definition` | `ModelPriorityDefinition.py` | `slug`, `label`, `color`, `sort_order` | request | priorite/SLA |
| `workflow` | `ModelWorkflow.py` | `request_id`, `workflow_status` | request, details | workflow |
| `workflow_detail` | `ModelWorkflowDetail.py` | `workflow_id`, `unity_id`, `agent_id`, `task_id`, `parent_id`, `event_type`, `label`, `actor_name`, `accepted`, `activated`, `comment` | workflow, account, unity, task, parent/children | timeline/commentaires |
| `task` | `ModelTask.py` | `request_id`, `from_agent_id`, `to_agent_id`, `from_unit_id`, `to_unit_id`, `task_type`, `task_status` | request, account, unity | workflow/taches |
| `attachment` | `ModelAttachment.py` | `request_id`, `uploader_id`, `filename`, `storage_path`, `mime_type`, `scan_status` | request, account | pieces jointes |
| `notification` | `ModelNotification.py` | `recipient_id`, `request_id`, `type`, `channel`, `title`, `body`, `action_url`, `is_read` | account, request | notifications |
| `routing_rule` | `ModelRoutingRule.py` | `target_unity_id`, `name`, `condition_field`, `condition_value`, `auto_assign`, `sort_order` | unity | routage |
| `sla_policy` | `ModelSlaPolicy.py` | `category`, `priority`, `response_h`, `resolution_h`, `escalate_after_h` | refs categorie/priorite par code | SLA |
| `activity_log` | `ModelActivityLog.py` | `actor_id`, `actor`, `actor_role`, `action`, `category`, `target`, `ip_address`, `log_status` | account | audit |
| `appreciation` | `ModelAppreciation.py` | `request_id`, `rating`, `comment`, `resolved_confirmed`, `author_type` | request | CSAT/reouverture |
| `knowledge_article` | `ModelKnowledgeArticle.py` | `author_id`, `title`, `excerpt`, `body`, `category`, `is_published`, `is_archived` | account | KB |
| `knowledge_category` | `ModelKnowledgeCategory.py` | `code`, `label` | articles | KB refs |
| `announcement` | `ModelAnnouncement.py` | `category`, `priority`, `status`, `author_id`, `title`, `audience`, `published_at` | account + refs + target roles | annonces |
| `announcement_target_role` | `ModelAnnouncementTargetRole.py` | `announcement_id`, `role` | announcement | annonces |
| `organigram` | `ModelOrganigram.py` | `unity_id`, `parent_id` | unity, auto-relation | organisation |
| `communication_setting` | `ModelCommunicationSetting.py` | canaux email/sms/banner/whatsapp/push, sender, reply_to | account updater | communication |
| `security_incident` | `ModelSecurityIncident.py` | `email_attempted`, `ip_address`, `photo_path`, `attempt_count`, `resolved` | account resolver | securite |

## Enums/statuts connus

Roles: `public`, `user`, `agent`, `chief`, `director`, `dg`, `admin`.

Statuts demande frontend: `new`, `qualifying`, `qualified`, `assigned`, `in_progress`, `pending`, `resolved`, `closed`, `reopened`, `rejected`, `escalated`, `cancelled`.

Priorites: `low`, `medium`, `high`, `critical`.

## Services qui modifient les donnees critiques

- `ServiceRequest.py`: `request`, `workflow`, `workflow_detail`, notifications.
- `ServiceWorkflow.py`: `workflow`, `workflow_detail`.
- `ServiceTask.py`: `task`, `workflow_detail`.
- `ServiceEscalade.py`: `request.sla_breached`, `workflow_detail`, notifications.
- `ServiceAccount.py`: `account`.
- `ServiceRoutingRule.py`: `routing_rule`.
- `ServiceReferences.py`: tables de reference.
