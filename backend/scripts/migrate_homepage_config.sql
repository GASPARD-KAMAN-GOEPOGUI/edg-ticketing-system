-- ============================================================
-- Migration : ajout des colonnes de personnalisation à homepage_config
-- À exécuter UNE SEULE FOIS pour activer la fonctionnalité
-- "supprimer / modifier / ajouter / mettre un délais" sur la page d'accueil.
-- ============================================================

ALTER TABLE `homepage_config`
  ADD COLUMN `title`      VARCHAR(200) NULL    AFTER `mission_text`,
  ADD COLUMN `content`    TEXT         NULL    AFTER `title`,
  ADD COLUMN `expires_at` DATETIME     NULL    AFTER `content`,
  ADD COLUMN `is_custom`  TINYINT(1)   NOT NULL DEFAULT 0 AFTER `expires_at`;
