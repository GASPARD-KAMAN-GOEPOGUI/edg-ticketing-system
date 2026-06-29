-- =============================================================================
-- Migration : TABLE announcement — remplacement des colonnes VARCHAR par FK INT
-- Prérequis : tables announcement_category, announcement_priority,
--             announcement_status doivent être peuplées (seed_references)
-- =============================================================================

-- 1. Ajout des colonnes FK (nullable au départ pour permettre le peuplement)
ALTER TABLE `announcement`
    ADD COLUMN `announcement_category_id` INT NULL AFTER `announcement_category`,
    ADD COLUMN `announcement_priority_id` INT NULL AFTER `announcement_priority`,
    ADD COLUMN `announcement_status_id`   INT NULL AFTER `announcement_status`;

-- 2. Peuplement par correspondance de code
UPDATE `announcement` a
JOIN `announcement_category` ac ON ac.code = a.announcement_category AND ac.deleted_at IS NULL
SET a.announcement_category_id = ac.id;

UPDATE `announcement` a
JOIN `announcement_priority` ap ON ap.code = a.announcement_priority AND ap.deleted_at IS NULL
SET a.announcement_priority_id = ap.id;

UPDATE `announcement` a
JOIN `announcement_status` ast ON ast.code = a.announcement_status AND ast.deleted_at IS NULL
SET a.announcement_status_id = ast.id;

-- 3. Fallback : lignes non mappées → premier enregistrement actif (par sort_order)
UPDATE `announcement` a,
       (SELECT id FROM `announcement_category` WHERE deleted_at IS NULL ORDER BY sort_order ASC LIMIT 1) def_cat
SET a.announcement_category_id = def_cat.id
WHERE a.announcement_category_id IS NULL;

UPDATE `announcement` a,
       (SELECT id FROM `announcement_priority` WHERE deleted_at IS NULL ORDER BY sort_order ASC LIMIT 1) def_prio
SET a.announcement_priority_id = def_prio.id
WHERE a.announcement_priority_id IS NULL;

UPDATE `announcement` a,
       (SELECT id FROM `announcement_status` WHERE deleted_at IS NULL ORDER BY sort_order ASC LIMIT 1) def_status
SET a.announcement_status_id = def_status.id
WHERE a.announcement_status_id IS NULL;

-- 4. Passage NOT NULL (toutes les lignes sont maintenant peuplées)
ALTER TABLE `announcement`
    MODIFY COLUMN `announcement_category_id` INT NOT NULL,
    MODIFY COLUMN `announcement_priority_id` INT NOT NULL,
    MODIFY COLUMN `announcement_status_id`   INT NOT NULL;

-- 5. Contraintes FK
ALTER TABLE `announcement`
    ADD CONSTRAINT `fk_ann_category_id` FOREIGN KEY (`announcement_category_id`) REFERENCES `announcement_category`(`id`),
    ADD CONSTRAINT `fk_ann_priority_id` FOREIGN KEY (`announcement_priority_id`) REFERENCES `announcement_priority`(`id`),
    ADD CONSTRAINT `fk_ann_status_id`   FOREIGN KEY (`announcement_status_id`)   REFERENCES `announcement_status`(`id`);

-- 6. Remplacement des indices (anciens indices sur colonnes VARCHAR supprimés)
DROP INDEX `idx_ann_astatus` ON `announcement`;
DROP INDEX `idx_ann_prio`    ON `announcement`;

CREATE INDEX `idx_ann_cat_id`    ON `announcement`(`announcement_category_id`);
CREATE INDEX `idx_ann_prio_id`   ON `announcement`(`announcement_priority_id`);
CREATE INDEX `idx_ann_status_id` ON `announcement`(`announcement_status_id`);

-- 7. Suppression des anciennes colonnes VARCHAR
ALTER TABLE `announcement`
    DROP COLUMN `announcement_category`,
    DROP COLUMN `announcement_priority`,
    DROP COLUMN `announcement_status`;
