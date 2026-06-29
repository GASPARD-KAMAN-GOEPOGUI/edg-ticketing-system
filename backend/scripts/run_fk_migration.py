"""
Exécute les migrations FK pour announcement et request.
Lance chaque statement séparément pour éviter les problèmes multi-statement.
"""
import asyncio, sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

ANNOUNCE_STMTS = [
    # 1. Ajout colonnes FK nullable
    "ALTER TABLE `announcement` ADD COLUMN `announcement_category_id` INT NULL AFTER `announcement_category`",
    "ALTER TABLE `announcement` ADD COLUMN `announcement_priority_id` INT NULL AFTER `announcement_priority`",
    "ALTER TABLE `announcement` ADD COLUMN `announcement_status_id` INT NULL AFTER `announcement_status`",
    # 2. Peuplement
    "UPDATE `announcement` a JOIN `announcement_category` ac ON ac.code = a.announcement_category AND ac.deleted_at IS NULL SET a.announcement_category_id = ac.id",
    "UPDATE `announcement` a JOIN `announcement_priority` ap ON ap.code = a.announcement_priority AND ap.deleted_at IS NULL SET a.announcement_priority_id = ap.id",
    "UPDATE `announcement` a JOIN `announcement_status` ast ON ast.code = a.announcement_status AND ast.deleted_at IS NULL SET a.announcement_status_id = ast.id",
    # 3. Fallback
    "UPDATE `announcement` a, (SELECT id FROM `announcement_category` WHERE deleted_at IS NULL ORDER BY sort_order ASC LIMIT 1) def_cat SET a.announcement_category_id = def_cat.id WHERE a.announcement_category_id IS NULL",
    "UPDATE `announcement` a, (SELECT id FROM `announcement_priority` WHERE deleted_at IS NULL ORDER BY sort_order ASC LIMIT 1) def_prio SET a.announcement_priority_id = def_prio.id WHERE a.announcement_priority_id IS NULL",
    "UPDATE `announcement` a, (SELECT id FROM `announcement_status` WHERE deleted_at IS NULL ORDER BY sort_order ASC LIMIT 1) def_status SET a.announcement_status_id = def_status.id WHERE a.announcement_status_id IS NULL",
    # 4. NOT NULL
    "ALTER TABLE `announcement` MODIFY COLUMN `announcement_category_id` INT NOT NULL",
    "ALTER TABLE `announcement` MODIFY COLUMN `announcement_priority_id` INT NOT NULL",
    "ALTER TABLE `announcement` MODIFY COLUMN `announcement_status_id` INT NOT NULL",
    # 5. FK constraints
    "ALTER TABLE `announcement` ADD CONSTRAINT `fk_ann_category_id` FOREIGN KEY (`announcement_category_id`) REFERENCES `announcement_category`(`id`)",
    "ALTER TABLE `announcement` ADD CONSTRAINT `fk_ann_priority_id` FOREIGN KEY (`announcement_priority_id`) REFERENCES `announcement_priority`(`id`)",
    "ALTER TABLE `announcement` ADD CONSTRAINT `fk_ann_status_id` FOREIGN KEY (`announcement_status_id`) REFERENCES `announcement_status`(`id`)",
    # 6. Nouveaux indices
    "CREATE INDEX `idx_ann_cat_id`    ON `announcement`(`announcement_category_id`)",
    "CREATE INDEX `idx_ann_prio_id`   ON `announcement`(`announcement_priority_id`)",
    "CREATE INDEX `idx_ann_status_id` ON `announcement`(`announcement_status_id`)",
    # 7. Suppression anciennes colonnes
    "ALTER TABLE `announcement` DROP COLUMN `announcement_category`",
    "ALTER TABLE `announcement` DROP COLUMN `announcement_priority`",
    "ALTER TABLE `announcement` DROP COLUMN `announcement_status`",
]

REQUEST_STMTS = [
    # 1. Ajout colonnes FK nullable
    "ALTER TABLE `request` ADD COLUMN `request_status_id` INT NULL AFTER `request_status`",
    "ALTER TABLE `request` ADD COLUMN `priority_definition_id` INT NULL AFTER `priority`",
    "ALTER TABLE `request` ADD COLUMN `request_category_id` INT NULL AFTER `category`",
    "ALTER TABLE `request` ADD COLUMN `request_source_id` INT NULL AFTER `source`",
    # 2. Peuplement
    "UPDATE `request` r JOIN `request_status` rs ON rs.code = r.request_status AND rs.deleted_at IS NULL SET r.request_status_id = rs.id",
    "UPDATE `request` r JOIN `priority_definition` pd ON pd.slug = r.priority AND pd.deleted_at IS NULL SET r.priority_definition_id = pd.id",
    "UPDATE `request` r JOIN `request_category` rc ON rc.code = r.category AND rc.deleted_at IS NULL SET r.request_category_id = rc.id",
    "UPDATE `request` r JOIN `request_source` rso ON rso.code = r.source AND rso.deleted_at IS NULL SET r.request_source_id = rso.id WHERE r.source IS NOT NULL",
    # 3. Fallback
    "UPDATE `request` r, (SELECT id FROM `request_status` WHERE code = 'new' AND deleted_at IS NULL LIMIT 1) def SET r.request_status_id = def.id WHERE r.request_status_id IS NULL",
    "UPDATE `request` r, (SELECT id FROM `priority_definition` WHERE slug = 'medium' AND deleted_at IS NULL LIMIT 1) def SET r.priority_definition_id = def.id WHERE r.priority_definition_id IS NULL",
    "UPDATE `request` r, (SELECT id FROM `request_category` WHERE deleted_at IS NULL ORDER BY sort_order ASC LIMIT 1) def SET r.request_category_id = def.id WHERE r.request_category_id IS NULL",
    # 4. NOT NULL (source reste nullable)
    "ALTER TABLE `request` MODIFY COLUMN `request_status_id` INT NOT NULL",
    "ALTER TABLE `request` MODIFY COLUMN `priority_definition_id` INT NOT NULL",
    "ALTER TABLE `request` MODIFY COLUMN `request_category_id` INT NOT NULL",
    # 5. FK constraints
    "ALTER TABLE `request` ADD CONSTRAINT `fk_req_status_id`    FOREIGN KEY (`request_status_id`)      REFERENCES `request_status`(`id`)",
    "ALTER TABLE `request` ADD CONSTRAINT `fk_req_priority_def` FOREIGN KEY (`priority_definition_id`) REFERENCES `priority_definition`(`id`)",
    "ALTER TABLE `request` ADD CONSTRAINT `fk_req_category_id`  FOREIGN KEY (`request_category_id`)    REFERENCES `request_category`(`id`)",
    "ALTER TABLE `request` ADD CONSTRAINT `fk_req_source_id`    FOREIGN KEY (`request_source_id`)      REFERENCES `request_source`(`id`)",
    # 6. Nouveaux indices
    "CREATE INDEX `idx_req_status_id`       ON `request`(`request_status_id`)",
    "CREATE INDEX `idx_req_priority_def_id` ON `request`(`priority_definition_id`)",
    "CREATE INDEX `idx_req_category_id`     ON `request`(`request_category_id`)",
    "CREATE INDEX `idx_req_source_id`       ON `request`(`request_source_id`)",
    # 7. Suppression anciennes colonnes
    "ALTER TABLE `request` DROP COLUMN `request_status`",
    "ALTER TABLE `request` DROP COLUMN `priority`",
    "ALTER TABLE `request` DROP COLUMN `category`",
    "ALTER TABLE `request` DROP COLUMN `source`",
]


async def run_stmts(session, stmts: list[str], label: str):
    from sqlalchemy import text
    print(f"\n=== {label} ===")
    for sql in stmts:
        short = sql[:80].replace('\n', ' ')
        try:
            await session.execute(text(sql))
            await session.commit()
            print(f"  OK  {short}")
        except Exception as e:
            err = str(e)
            # Colonnes déjà existantes ou indices déjà créés → ignorer
            if "Duplicate column" in err or "already exists" in err or "Duplicate key name" in err:
                print(f"  SKIP (already exists)  {short}")
            elif "Can't DROP" in err and "check that column/key exists" in err:
                print(f"  SKIP (not found)  {short}")
            else:
                print(f"  ERR  {short}")
                print(f"       {err[:200]}")
                raise


async def main():
    from api.configs.Database import engine
    from sqlalchemy.ext.asyncio import AsyncSession
    async with AsyncSession(engine) as s:
        await run_stmts(s, ANNOUNCE_STMTS, "announcement FK migration")
        await run_stmts(s, REQUEST_STMTS, "request FK migration")
    print("\nMigration terminée.")

asyncio.run(main())
