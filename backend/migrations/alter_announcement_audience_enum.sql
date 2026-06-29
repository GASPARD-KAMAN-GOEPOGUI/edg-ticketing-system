-- Migration : ajout de la valeur 'unit' dans l'enum announcement.audience
-- À exécuter UNE SEULE FOIS sur la base de données edg_ticketing existante.
-- MySQL ne permet pas d'ajouter une valeur à un ENUM sans recréer la colonne.

ALTER TABLE announcement
  MODIFY COLUMN audience ENUM('internal','external','all','unit')
  NOT NULL DEFAULT 'internal';
