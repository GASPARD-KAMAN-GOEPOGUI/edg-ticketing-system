-- ════════════════════════════════════════════════════════════════════════
-- EDG Support — SCHÉMA SEUL (aucune donnée), MySQL 8 / utf8mb4
-- Généré depuis les modèles SQLAlchemy (api/models) — état du code actuel,
-- équivalent à la dernière migration historique (029).
-- Non destructif : CREATE TABLE IF NOT EXISTS, aucun DROP, aucun INSERT.
-- Les données de référence (statuts, priorités, catégories, SLA,
-- organigramme) sont insérées par le script d'initialisation, pas ici.
-- Régénérer : voir docs (CreateTable/CreateIndex, dialecte mysql).
-- ════════════════════════════════════════════════════════════════════════

SET NAMES utf8mb4;
SET FOREIGN_KEY_CHECKS = 0;

-- Table `app_lock`
CREATE TABLE IF NOT EXISTS app_lock (
	name VARCHAR(100) NOT NULL, 
	holder VARCHAR(200) NOT NULL, 
	acquired_at DATETIME NOT NULL, 
	expires_at DATETIME NOT NULL, 
	PRIMARY KEY (name)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_unicode_ci;

-- Table `priority_definition`
CREATE TABLE IF NOT EXISTS priority_definition (
	slug VARCHAR(50) NOT NULL, 
	label VARCHAR(100) NOT NULL, 
	description TEXT NOT NULL, 
	color ENUM('slate','blue','teal','amber','orange','red','purple') NOT NULL, 
	sort_order SMALLINT NOT NULL, 
	is_builtin BOOL NOT NULL, 
	id INTEGER NOT NULL AUTO_INCREMENT, 
	uuid VARCHAR(36) NOT NULL, 
	status BOOL NOT NULL, 
	infos JSON, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	updated_at DATETIME NOT NULL DEFAULT now(), 
	deleted_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (slug), 
	UNIQUE (uuid)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE INDEX idx_prio_order ON priority_definition (sort_order);
CREATE INDEX idx_prio_status ON priority_definition (status, deleted_at);

-- Table `rate_limit_counter`
CREATE TABLE IF NOT EXISTS rate_limit_counter (
	key_hash CHAR(64) NOT NULL, 
	count INTEGER NOT NULL, 
	expires_at DATETIME NOT NULL, 
	PRIMARY KEY (key_hash)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE INDEX idx_rate_limit_counter_expires_at ON rate_limit_counter (expires_at);

-- Table `request_category`
CREATE TABLE IF NOT EXISTS request_category (
	code VARCHAR(50) NOT NULL, 
	label VARCHAR(200) NOT NULL, 
	sort_order SMALLINT NOT NULL, 
	is_builtin BOOL NOT NULL, 
	id INTEGER NOT NULL AUTO_INCREMENT, 
	uuid VARCHAR(36) NOT NULL, 
	status BOOL NOT NULL, 
	infos JSON, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	updated_at DATETIME NOT NULL DEFAULT now(), 
	deleted_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (code), 
	UNIQUE (uuid)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE INDEX idx_rc_order ON request_category (sort_order);
CREATE INDEX idx_rc_status ON request_category (status, deleted_at);

-- Table `request_status`
CREATE TABLE IF NOT EXISTS request_status (
	code VARCHAR(50) NOT NULL, 
	label VARCHAR(200) NOT NULL, 
	sort_order SMALLINT NOT NULL, 
	is_builtin BOOL NOT NULL, 
	id INTEGER NOT NULL AUTO_INCREMENT, 
	uuid VARCHAR(36) NOT NULL, 
	status BOOL NOT NULL, 
	infos JSON, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	updated_at DATETIME NOT NULL DEFAULT now(), 
	deleted_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (code), 
	UNIQUE (uuid)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE INDEX idx_rs_order ON request_status (sort_order);
CREATE INDEX idx_rs_status ON request_status (status, deleted_at);

-- Table `revoked_token`
CREATE TABLE IF NOT EXISTS revoked_token (
	token_hash CHAR(64) NOT NULL, 
	revoked_at DATETIME NOT NULL, 
	expires_at DATETIME NOT NULL, 
	PRIMARY KEY (token_hash)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE INDEX idx_revoked_token_expires_at ON revoked_token (expires_at);

-- Table `session_binding`
CREATE TABLE IF NOT EXISTS session_binding (
	token_hash CHAR(64) NOT NULL, 
	account_id INTEGER NOT NULL, 
	version INTEGER NOT NULL, 
	expires_at DATETIME NOT NULL, 
	PRIMARY KEY (token_hash)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE INDEX idx_session_binding_expires_at ON session_binding (expires_at);

-- Table `sla_policy`
CREATE TABLE IF NOT EXISTS sla_policy (
	category VARCHAR(50) NOT NULL, 
	priority VARCHAR(50) NOT NULL, 
	response_h SMALLINT NOT NULL, 
	resolution_h SMALLINT NOT NULL, 
	escalate_after_h SMALLINT NOT NULL, 
	id INTEGER NOT NULL AUTO_INCREMENT, 
	uuid VARCHAR(36) NOT NULL, 
	status BOOL NOT NULL, 
	infos JSON, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	updated_at DATETIME NOT NULL DEFAULT now(), 
	deleted_at DATETIME, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_sla_cat_prio UNIQUE (category, priority), 
	UNIQUE (uuid)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE INDEX idx_sla_status ON sla_policy (status, deleted_at);

-- Table `unity`
CREATE TABLE IF NOT EXISTS unity (
	label VARCHAR(200) NOT NULL, 
	codename VARCHAR(50) NOT NULL, 
	aleas VARCHAR(50), 
	description TEXT, 
	parent_direction_id INTEGER, 
	id INTEGER NOT NULL AUTO_INCREMENT, 
	uuid VARCHAR(36) NOT NULL, 
	status BOOL NOT NULL, 
	infos JSON, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	updated_at DATETIME NOT NULL DEFAULT now(), 
	deleted_at DATETIME, 
	PRIMARY KEY (id), 
	UNIQUE (codename), 
	FOREIGN KEY(parent_direction_id) REFERENCES unity (id) ON DELETE SET NULL, 
	UNIQUE (uuid)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE INDEX idx_unity_codename ON unity (codename);
CREATE INDEX idx_unity_parent_dir ON unity (parent_direction_id);
CREATE INDEX idx_unity_status ON unity (status, deleted_at);

-- Table `account`
CREATE TABLE IF NOT EXISTS account (
	unity_id INTEGER, 
	central_user_id INTEGER, 
	central_user_uuid VARCHAR(64), 
	name VARCHAR(200) NOT NULL, 
	firstname VARCHAR(200), 
	email VARCHAR(320) NOT NULL, 
	phone VARCHAR(30), 
	`role` ENUM('public','user','chief-service','technicien','chef-division-support','admin') NOT NULL, 
	account_status VARCHAR(50) NOT NULL, 
	matricule VARCHAR(20), 
	job VARCHAR(200), 
	avatar_url VARCHAR(2048), 
	is_edg_employee BOOL NOT NULL, 
	email_verified BOOL NOT NULL, 
	mfa_enabled BOOL NOT NULL, 
	availability ENUM('available','busy','overload','off'), 
	notif_sla_alerts BOOL NOT NULL, 
	notif_escalations BOOL NOT NULL, 
	notif_comments BOOL NOT NULL, 
	notif_resolutions BOOL NOT NULL, 
	activated_at DATETIME, 
	consent_accepted_at DATETIME, 
	consent_version VARCHAR(50), 
	id INTEGER NOT NULL AUTO_INCREMENT, 
	uuid VARCHAR(36) NOT NULL, 
	status BOOL NOT NULL, 
	infos JSON, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	updated_at DATETIME NOT NULL DEFAULT now(), 
	deleted_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(unity_id) REFERENCES unity (id), 
	UNIQUE (central_user_id), 
	UNIQUE (central_user_uuid), 
	UNIQUE (email), 
	UNIQUE (phone), 
	UNIQUE (matricule), 
	UNIQUE (uuid)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE INDEX idx_account_central_user_id ON account (central_user_id);
CREATE INDEX idx_account_role ON account (`role`);
CREATE INDEX idx_account_status ON account (status, deleted_at);
CREATE INDEX idx_account_unity ON account (unity_id);

-- Table `organigram`
CREATE TABLE IF NOT EXISTS organigram (
	unity_id INTEGER NOT NULL, 
	parent_id INTEGER, 
	id INTEGER NOT NULL AUTO_INCREMENT, 
	uuid VARCHAR(36) NOT NULL, 
	status BOOL NOT NULL, 
	infos JSON, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	updated_at DATETIME NOT NULL DEFAULT now(), 
	deleted_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(unity_id) REFERENCES unity (id), 
	FOREIGN KEY(parent_id) REFERENCES organigram (id) ON DELETE SET NULL, 
	UNIQUE (uuid)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE INDEX idx_org_parent ON organigram (parent_id);
CREATE INDEX idx_org_status ON organigram (status, deleted_at);
CREATE INDEX idx_org_unity ON organigram (unity_id);

-- Table `routing_rule`
CREATE TABLE IF NOT EXISTS routing_rule (
	target_unity_id INTEGER, 
	name VARCHAR(200) NOT NULL, 
	condition_field ENUM('category','priority','source','keyword') NOT NULL, 
	condition_value TEXT NOT NULL, 
	auto_assign BOOL NOT NULL, 
	sort_order SMALLINT NOT NULL, 
	id INTEGER NOT NULL AUTO_INCREMENT, 
	uuid VARCHAR(36) NOT NULL, 
	status BOOL NOT NULL, 
	infos JSON, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	updated_at DATETIME NOT NULL DEFAULT now(), 
	deleted_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(target_unity_id) REFERENCES unity (id), 
	UNIQUE (uuid)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE INDEX idx_rr_order ON routing_rule (sort_order);
CREATE INDEX idx_rr_status ON routing_rule (status, deleted_at);

-- Table `activity_log`
CREATE TABLE IF NOT EXISTS activity_log (
	actor_id INTEGER, 
	actor VARCHAR(200) NOT NULL, 
	actor_role ENUM('public','user','chief-service','technicien','chef-division-support','admin') NOT NULL, 
	action VARCHAR(500) NOT NULL, 
	category VARCHAR(50) NOT NULL, 
	target VARCHAR(500) NOT NULL, 
	ip_address VARCHAR(45), 
	user_agent TEXT, 
	log_status ENUM('success','warning','error') NOT NULL, 
	id INTEGER NOT NULL AUTO_INCREMENT, 
	uuid VARCHAR(36) NOT NULL, 
	status BOOL NOT NULL, 
	infos JSON, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	updated_at DATETIME NOT NULL DEFAULT now(), 
	deleted_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(actor_id) REFERENCES account (id), 
	UNIQUE (uuid)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE INDEX idx_log_actor ON activity_log (actor_id);
CREATE INDEX idx_log_cat ON activity_log (category);
CREATE INDEX idx_log_created ON activity_log (created_at);
CREATE INDEX idx_log_logstatus ON activity_log (log_status);
CREATE INDEX idx_log_status ON activity_log (status, deleted_at);

-- Table `request`
CREATE TABLE IF NOT EXISTS request (
	request_status_id INTEGER NOT NULL, 
	priority_definition_id INTEGER NOT NULL, 
	request_category_id INTEGER NOT NULL, 
	request_source VARCHAR(50), 
	unity_id INTEGER, 
	on_behalf_unity_id INTEGER, 
	assignee_id INTEGER, 
	requester_id INTEGER, 
	distributor_id INTEGER, 
	ref VARCHAR(30) NOT NULL, 
	title VARCHAR(500) NOT NULL, 
	description TEXT NOT NULL, 
	in_triage BOOL NOT NULL, 
	is_external BOOL NOT NULL, 
	requester_type ENUM('internal','external'), 
	submission_mode ENUM('personal','on_behalf_of_unit') NOT NULL, 
	requester_name VARCHAR(200) NOT NULL, 
	requester_phone VARCHAR(30), 
	requester_email VARCHAR(320), 
	requester_address TEXT, 
	proposed_solution TEXT, 
	meter_number VARCHAR(50), 
	client_ref VARCHAR(50), 
	lat DOUBLE, 
	lng DOUBLE, 
	location_label TEXT, 
	sla_hours SMALLINT NOT NULL, 
	sla_elapsed SMALLINT NOT NULL, 
	sla_breached BOOL NOT NULL, 
	merged_into_id INTEGER, 
	sla_response_at DATETIME, 
	resolved_at DATETIME, 
	closed_at DATETIME, 
	id INTEGER NOT NULL AUTO_INCREMENT, 
	uuid VARCHAR(36) NOT NULL, 
	status BOOL NOT NULL, 
	infos JSON, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	updated_at DATETIME NOT NULL DEFAULT now(), 
	deleted_at DATETIME, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_req_ref UNIQUE (ref), 
	FOREIGN KEY(request_status_id) REFERENCES request_status (id), 
	FOREIGN KEY(priority_definition_id) REFERENCES priority_definition (id), 
	FOREIGN KEY(request_category_id) REFERENCES request_category (id), 
	FOREIGN KEY(unity_id) REFERENCES unity (id), 
	FOREIGN KEY(on_behalf_unity_id) REFERENCES unity (id), 
	FOREIGN KEY(assignee_id) REFERENCES account (id), 
	FOREIGN KEY(requester_id) REFERENCES account (id), 
	FOREIGN KEY(distributor_id) REFERENCES account (id), 
	UNIQUE (ref), 
	FOREIGN KEY(merged_into_id) REFERENCES request (id), 
	UNIQUE (uuid)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE INDEX idx_req_assignee ON request (assignee_id);
CREATE INDEX idx_req_category_id ON request (request_category_id);
CREATE INDEX idx_req_created ON request (created_at);
CREATE INDEX idx_req_merged_into ON request (merged_into_id);
CREATE INDEX idx_req_priority_def_id ON request (priority_definition_id);
CREATE INDEX idx_req_source ON request (request_source);
CREATE INDEX idx_req_status ON request (status, deleted_at);
CREATE INDEX idx_req_status_id ON request (request_status_id);
CREATE INDEX idx_req_triage ON request (in_triage);
CREATE INDEX idx_req_unity ON request (unity_id);

-- Table `appreciation`
CREATE TABLE IF NOT EXISTS appreciation (
	request_id INTEGER NOT NULL, 
	rating SMALLINT NOT NULL, 
	comment TEXT, 
	resolved_confirmed BOOL NOT NULL, 
	is_modified BOOL NOT NULL, 
	author_type ENUM('internal','external') NOT NULL, 
	id INTEGER NOT NULL AUTO_INCREMENT, 
	uuid VARCHAR(36) NOT NULL, 
	status BOOL NOT NULL, 
	infos JSON, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	updated_at DATETIME NOT NULL DEFAULT now(), 
	deleted_at DATETIME, 
	PRIMARY KEY (id), 
	CONSTRAINT uk_appr_req UNIQUE (request_id), 
	CONSTRAINT chk_rating CHECK (rating BETWEEN 1 AND 5), 
	UNIQUE (request_id), 
	FOREIGN KEY(request_id) REFERENCES request (id) ON DELETE CASCADE, 
	UNIQUE (uuid)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE INDEX idx_appr_rating ON appreciation (rating);
CREATE INDEX idx_appr_status ON appreciation (status, deleted_at);

-- Table `attachment`
CREATE TABLE IF NOT EXISTS attachment (
	request_id INTEGER NOT NULL, 
	uploader_id INTEGER, 
	filename VARCHAR(500) NOT NULL, 
	storage_path TEXT NOT NULL, 
	mime_type VARCHAR(100) NOT NULL, 
	size_bytes INTEGER NOT NULL, 
	clamav_clean BOOL, 
	scan_status ENUM('pending_scan','clean','quarantined','deleted') NOT NULL, 
	id INTEGER NOT NULL AUTO_INCREMENT, 
	uuid VARCHAR(36) NOT NULL, 
	status BOOL NOT NULL, 
	infos JSON, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	updated_at DATETIME NOT NULL DEFAULT now(), 
	deleted_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(request_id) REFERENCES request (id) ON DELETE CASCADE, 
	FOREIGN KEY(uploader_id) REFERENCES account (id), 
	UNIQUE (uuid)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE INDEX idx_att_req ON attachment (request_id);
CREATE INDEX idx_att_status ON attachment (status, deleted_at);

-- Table `notification`
CREATE TABLE IF NOT EXISTS notification (
	recipient_id INTEGER NOT NULL, 
	request_id INTEGER, 
	type ENUM('info','success','warning') NOT NULL, 
	channel ENUM('in_app','sms','email') NOT NULL, 
	title VARCHAR(200) NOT NULL, 
	body TEXT NOT NULL, 
	action_label VARCHAR(100), 
	action_url TEXT, 
	is_read BOOL NOT NULL, 
	visibility ENUM('public','admin_only') NOT NULL, 
	read_at DATETIME, 
	id INTEGER NOT NULL AUTO_INCREMENT, 
	uuid VARCHAR(36) NOT NULL, 
	status BOOL NOT NULL, 
	infos JSON, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	updated_at DATETIME NOT NULL DEFAULT now(), 
	deleted_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(recipient_id) REFERENCES account (id) ON DELETE CASCADE, 
	FOREIGN KEY(request_id) REFERENCES request (id), 
	UNIQUE (uuid)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE INDEX idx_notif_recip ON notification (recipient_id);
CREATE INDEX idx_notif_status ON notification (status, deleted_at);
CREATE INDEX idx_notif_unread ON notification (recipient_id, is_read);

-- Table `task`
CREATE TABLE IF NOT EXISTS task (
	request_id INTEGER NOT NULL, 
	from_agent_id INTEGER, 
	to_agent_id INTEGER, 
	from_unit_id INTEGER, 
	to_unit_id INTEGER, 
	task_type VARCHAR(50) NOT NULL, 
	reason TEXT, 
	task_status VARCHAR(50) NOT NULL, 
	id INTEGER NOT NULL AUTO_INCREMENT, 
	uuid VARCHAR(36) NOT NULL, 
	status BOOL NOT NULL, 
	infos JSON, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	updated_at DATETIME NOT NULL DEFAULT now(), 
	deleted_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(request_id) REFERENCES request (id), 
	FOREIGN KEY(from_agent_id) REFERENCES account (id), 
	FOREIGN KEY(to_agent_id) REFERENCES account (id), 
	FOREIGN KEY(from_unit_id) REFERENCES unity (id), 
	FOREIGN KEY(to_unit_id) REFERENCES unity (id), 
	UNIQUE (uuid)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE INDEX idx_task_req ON task (request_id);
CREATE INDEX idx_task_status ON task (status, deleted_at);
CREATE INDEX idx_task_tstatus ON task (task_status);

-- Table `workflow`
CREATE TABLE IF NOT EXISTS workflow (
	request_id INTEGER NOT NULL, 
	workflow_status VARCHAR(50) NOT NULL, 
	id INTEGER NOT NULL AUTO_INCREMENT, 
	uuid VARCHAR(36) NOT NULL, 
	status BOOL NOT NULL, 
	infos JSON, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	updated_at DATETIME NOT NULL DEFAULT now(), 
	deleted_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(request_id) REFERENCES request (id), 
	UNIQUE (uuid)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE INDEX idx_wf_req ON workflow (request_id);
CREATE INDEX idx_wf_status ON workflow (status, deleted_at);

-- Table `workflow_detail`
CREATE TABLE IF NOT EXISTS workflow_detail (
	workflow_id INTEGER, 
	unity_id INTEGER, 
	agent_id INTEGER, 
	task_id INTEGER, 
	parent_id INTEGER, 
	event_type VARCHAR(50), 
	label VARCHAR(500), 
	actor_name VARCHAR(200), 
	accepted BOOL, 
	activated BOOL NOT NULL, 
	comment TEXT, 
	id INTEGER NOT NULL AUTO_INCREMENT, 
	uuid VARCHAR(36) NOT NULL, 
	status BOOL NOT NULL, 
	infos JSON, 
	created_at DATETIME NOT NULL DEFAULT now(), 
	updated_at DATETIME NOT NULL DEFAULT now(), 
	deleted_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(workflow_id) REFERENCES workflow (id), 
	FOREIGN KEY(unity_id) REFERENCES unity (id), 
	FOREIGN KEY(agent_id) REFERENCES account (id), 
	FOREIGN KEY(task_id) REFERENCES task (id), 
	FOREIGN KEY(parent_id) REFERENCES workflow_detail (id), 
	UNIQUE (uuid)
)ENGINE=InnoDB CHARSET=utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE INDEX idx_wfd_event_type ON workflow_detail (event_type, deleted_at);
CREATE INDEX idx_wfd_status ON workflow_detail (status, deleted_at);
CREATE INDEX idx_wfd_wf ON workflow_detail (workflow_id);

SET FOREIGN_KEY_CHECKS = 1;
