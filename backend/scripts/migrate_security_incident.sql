-- ============================================================
-- Migration : création de la table security_incident
-- Stocke les tentatives d'accès non autorisées sur l'interface admin :
-- photo capturée, métadonnées de connexion, statut de résolution.
-- À exécuter UNE SEULE FOIS.
-- ============================================================

CREATE TABLE IF NOT EXISTS `security_incident` (
  `id`               INT            NOT NULL AUTO_INCREMENT,
  `uuid`             CHAR(36)       NOT NULL,
  `status`           TINYINT(1)     NOT NULL DEFAULT 1,
  `infos`            JSON               NULL,
  `created_at`       DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP,
  `updated_at`       DATETIME       NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  `deleted_at`       DATETIME           NULL,

  `email_attempted`  VARCHAR(320)       NULL COMMENT 'Identifiant saisi lors de la tentative',
  `ip_address`       VARCHAR(45)        NULL COMMENT 'IPv4 ou IPv6',
  `user_agent`       TEXT               NULL,
  `photo_path`       VARCHAR(500)       NULL COMMENT 'Chemin relatif dans /uploads/security/',
  `occurred_at`      VARCHAR(50)        NULL COMMENT 'Horodatage ISO transmis par le frontend',

  `resolved`         TINYINT(1)     NOT NULL DEFAULT 0,
  `resolved_at`      DATETIME           NULL,
  `resolved_by`      INT                NULL,
  `notes`            TEXT               NULL,

  PRIMARY KEY (`id`),
  UNIQUE  KEY `uq_security_incident_uuid`    (`uuid`),
  INDEX   `idx_sec_inc_resolved`             (`resolved`),
  INDEX   `idx_sec_inc_email`                (`email_attempted`),
  INDEX   `idx_sec_inc_created`              (`created_at`),
  INDEX   `idx_sec_inc_status`               (`status`, `deleted_at`),
  CONSTRAINT `fk_sec_inc_resolver`
    FOREIGN KEY (`resolved_by`) REFERENCES `account` (`id`)
    ON DELETE SET NULL ON UPDATE CASCADE
) ENGINE=InnoDB
  DEFAULT CHARSET=utf8mb4
  COLLATE=utf8mb4_unicode_ci;
