-- =============================================================================
-- Migration : TABLE request — remplacement des colonnes VARCHAR par FK INT
-- Prérequis : tables request_status, priority_definition, request_category,
--             request_source doivent être peuplées (seed_references)
-- =============================================================================

-- 1. Ajout des colonnes FK (nullable au départ)
ALTER TABLE `request`
    ADD COLUMN `request_status_id`      INT NULL AFTER `request_status`,
    ADD COLUMN `priority_definition_id` INT NULL AFTER `priority`,
    ADD COLUMN `request_category_id`    INT NULL AFTER `category`,
    ADD COLUMN `request_source_id`      INT NULL AFTER `source`;

-- 2. Peuplement par correspondance de code/slug
UPDATE `request` r
JOIN `request_status` rs ON rs.code = r.request_status AND rs.deleted_at IS NULL
SET r.request_status_id = rs.id;

UPDATE `request` r
JOIN `priority_definition` pd ON pd.slug = r.priority AND pd.deleted_at IS NULL
SET r.priority_definition_id = pd.id;

UPDATE `request` r
JOIN `request_category` rc ON rc.code = r.category AND rc.deleted_at IS NULL
SET r.request_category_id = rc.id;

-- source est nullable : ne mapper que les lignes non NULL
UPDATE `request` r
JOIN `request_source` rso ON rso.code = r.source AND rso.deleted_at IS NULL
SET r.request_source_id = rso.id
WHERE r.source IS NOT NULL;

-- 3. Fallback pour les non-mappés (sauf source qui reste nullable)
UPDATE `request` r,
       (SELECT id FROM `request_status` WHERE code = 'new' AND deleted_at IS NULL LIMIT 1) def
SET r.request_status_id = def.id
WHERE r.request_status_id IS NULL;

UPDATE `request` r,
       (SELECT id FROM `priority_definition` WHERE slug = 'medium' AND deleted_at IS NULL LIMIT 1) def
SET r.priority_definition_id = def.id
WHERE r.priority_definition_id IS NULL;

UPDATE `request` r,
       (SELECT id FROM `request_category` WHERE deleted_at IS NULL ORDER BY sort_order ASC LIMIT 1) def
SET r.request_category_id = def.id
WHERE r.request_category_id IS NULL;

-- 4. Passage NOT NULL (sauf request_source_id qui reste nullable)
ALTER TABLE `request`
    MODIFY COLUMN `request_status_id`      INT NOT NULL,
    MODIFY COLUMN `priority_definition_id` INT NOT NULL,
    MODIFY COLUMN `request_category_id`    INT NOT NULL,
    MODIFY COLUMN `request_source_id`      INT NULL;

-- 5. Contraintes FK
ALTER TABLE `request`
    ADD CONSTRAINT `fk_req_status_id`      FOREIGN KEY (`request_status_id`)      REFERENCES `request_status`(`id`),
    ADD CONSTRAINT `fk_req_priority_def`   FOREIGN KEY (`priority_definition_id`) REFERENCES `priority_definition`(`id`),
    ADD CONSTRAINT `fk_req_category_id`    FOREIGN KEY (`request_category_id`)    REFERENCES `request_category`(`id`),
    ADD CONSTRAINT `fk_req_source_id`      FOREIGN KEY (`request_source_id`)      REFERENCES `request_source`(`id`);

-- 6. Remplacement des indices
DROP INDEX `idx_req_rstatus`  ON `request`;
DROP INDEX `idx_req_priority` ON `request`;
DROP INDEX `idx_req_category` ON `request`;
DROP INDEX `idx_req_source`   ON `request`;

CREATE INDEX `idx_req_status_id`       ON `request`(`request_status_id`);
CREATE INDEX `idx_req_priority_def_id` ON `request`(`priority_definition_id`);
CREATE INDEX `idx_req_category_id`     ON `request`(`request_category_id`);
CREATE INDEX `idx_req_source_id`       ON `request`(`request_source_id`);

-- 7. Suppression des anciennes colonnes
ALTER TABLE `request`
    DROP COLUMN `request_status`,
    DROP COLUMN `priority`,
    DROP COLUMN `category`,
    DROP COLUMN `source`;
