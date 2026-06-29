-- Test de connexion à la base de données edg_ticketing
SELECT 1 AS connection_test;

-- Vérifier la base active
SELECT DATABASE() AS current_database;

-- Lister les tables existantes
SHOW TABLES;
