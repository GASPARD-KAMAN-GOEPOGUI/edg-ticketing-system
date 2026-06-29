-- ============================================================
-- Migration : synchronisation du schéma table `request`
-- À exécuter UNE SEULE FOIS si vous voyez :
--   ❌ DB_ERROR (None) — OperationalError | GET /api/v1/requests/
-- ============================================================
-- ÉTAPE 1 : Renommer sla_deadline → sla_hours (si sla_deadline existe)
-- Commenter cette ligne si la colonne s'appelle déjà sla_hours.
-- MySQL 8.0+ seulement :
ALTER TABLE `request` RENAME COLUMN `sla_deadline` TO `sla_hours`;

-- ÉTAPE 2 : Ajouter les colonnes potentiellement absentes
-- Chaque ligne peut être commentée si la colonne existe déjà.
ALTER TABLE `request`
  ADD COLUMN IF NOT EXISTS `sla_hours`             SMALLINT     NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS `sla_elapsed`           SMALLINT     NOT NULL DEFAULT 0,
  ADD COLUMN IF NOT EXISTS `sla_response_at`       DATETIME     NULL,
  ADD COLUMN IF NOT EXISTS `submission_mode`       ENUM('personal','on_behalf_of_unit') NOT NULL DEFAULT 'personal',
  ADD COLUMN IF NOT EXISTS `on_behalf_direction_id` INT         NULL,
  ADD COLUMN IF NOT EXISTS `on_behalf_unit_id`     INT         NULL,
  ADD COLUMN IF NOT EXISTS `location_label`        TEXT         NULL,
  ADD COLUMN IF NOT EXISTS `client_ref`            VARCHAR(50)  NULL,
  ADD COLUMN IF NOT EXISTS `lat`                   DOUBLE       NULL,
  ADD COLUMN IF NOT EXISTS `lng`                   DOUBLE       NULL;

-- ÉTAPE 3 : FK pour on_behalf_direction et on_behalf_unit (si pas encore créées)
-- Ignorer l'erreur si les FK existent déjà.
ALTER TABLE `request`
  ADD CONSTRAINT `fk_req_obdir`  FOREIGN KEY (`on_behalf_direction_id`) REFERENCES `direction`(`id`),
  ADD CONSTRAINT `fk_req_obunit` FOREIGN KEY (`on_behalf_unit_id`)  REFERENCES `unit`(`id`);

-- ============================================================
-- ALTERNATIVE : Recréer complètement la base (DEV UNIQUEMENT)
-- Cela supprime toutes les données. Redémarrer le serveur ensuite
-- pour que create_all() recrée les tables avec le bon schéma.
-- ============================================================
-- DROP DATABASE edg_ticketing;
-- CREATE DATABASE edg_ticketing CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
