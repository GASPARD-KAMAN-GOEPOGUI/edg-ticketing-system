-- Migration v2 : ajout des colonnes enrichissement metadata
-- À exécuter sur la base edg_ticketing si la table security_incident
-- a été créée avant l'ajout de ces colonnes au modèle SQLAlchemy.
--
-- Vérifier les colonnes existantes avant d'exécuter :
--   SHOW COLUMNS FROM security_incident;
--
-- Puis exécuter uniquement les ALTER TABLE correspondant aux colonnes manquantes.

ALTER TABLE `security_incident`
    ADD COLUMN `browser`          VARCHAR(100)  NULL AFTER `user_agent`,
    ADD COLUMN `os_info`          VARCHAR(100)  NULL AFTER `browser`,
    ADD COLUMN `device_type`      VARCHAR(50)   NULL AFTER `os_info`,
    ADD COLUMN `location_approx`  VARCHAR(200)  NULL AFTER `device_type`,
    ADD COLUMN `attempt_count`    INT           NOT NULL DEFAULT 1 AFTER `occurred_at`;
