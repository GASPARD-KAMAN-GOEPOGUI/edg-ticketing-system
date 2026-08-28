-- phpMyAdmin SQL Dump
-- version 5.2.3
-- https://www.phpmyadmin.net/
--
-- Hôte : 127.0.0.1:3306
-- Généré le : ven. 28 août 2026 à 16:32
-- Version du serveur : 8.4.7
-- Version de PHP : 8.3.28

SET SQL_MODE = "NO_AUTO_VALUE_ON_ZERO";
START TRANSACTION;
SET time_zone = "+00:00";


/*!40101 SET @OLD_CHARACTER_SET_CLIENT=@@CHARACTER_SET_CLIENT */;
/*!40101 SET @OLD_CHARACTER_SET_RESULTS=@@CHARACTER_SET_RESULTS */;
/*!40101 SET @OLD_COLLATION_CONNECTION=@@COLLATION_CONNECTION */;
/*!40101 SET NAMES utf8mb4 */;

--
-- Base de données : `edg_ticketing`
--

-- --------------------------------------------------------

--
-- Structure de la table `account`
--

DROP TABLE IF EXISTS `account`;
CREATE TABLE IF NOT EXISTS `account` (
  `unity_id` int DEFAULT NULL,
  `name` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `firstname` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `email` varchar(320) COLLATE utf8mb4_unicode_ci NOT NULL,
  `phone` varchar(30) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `role` enum('public','user','agent-support','chief-service','chief-departement','director','admin') COLLATE utf8mb4_unicode_ci NOT NULL,
  `account_status` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `matricule` varchar(20) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `job` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `avatar_url` varchar(2048) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `is_edg_employee` tinyint(1) NOT NULL,
  `email_verified` tinyint(1) NOT NULL,
  `mfa_enabled` tinyint(1) NOT NULL,
  `availability` enum('available','busy','overload','off') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `notif_sla_alerts` tinyint(1) NOT NULL,
  `notif_escalations` tinyint(1) NOT NULL,
  `notif_comments` tinyint(1) NOT NULL,
  `notif_resolutions` tinyint(1) NOT NULL,
  `activated_at` datetime DEFAULT NULL,
  `id` int NOT NULL AUTO_INCREMENT,
  `uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` tinyint(1) NOT NULL,
  `infos` json DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  `deleted_at` datetime DEFAULT NULL,
  `central_user_id` int DEFAULT NULL,
  `central_user_uuid` varchar(64) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `consent_accepted_at` datetime DEFAULT NULL,
  `consent_version` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `email` (`email`),
  UNIQUE KEY `uuid` (`uuid`),
  UNIQUE KEY `phone` (`phone`),
  UNIQUE KEY `matricule` (`matricule`),
  UNIQUE KEY `uq_account_central_user_id` (`central_user_id`),
  UNIQUE KEY `uq_account_central_user_uuid` (`central_user_uuid`),
  KEY `idx_account_role` (`role`),
  KEY `idx_account_unity` (`unity_id`),
  KEY `idx_account_status` (`status`,`deleted_at`),
  KEY `idx_account_central_user_id` (`central_user_id`)
) ENGINE=InnoDB AUTO_INCREMENT=40 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Déchargement des données de la table `account`
--

INSERT INTO `account` (`unity_id`, `name`, `firstname`, `email`, `phone`, `role`, `account_status`, `matricule`, `job`, `avatar_url`, `is_edg_employee`, `email_verified`, `mfa_enabled`, `availability`, `notif_sla_alerts`, `notif_escalations`, `notif_comments`, `notif_resolutions`, `activated_at`, `id`, `uuid`, `status`, `infos`, `created_at`, `updated_at`, `deleted_at`, `central_user_id`, `central_user_uuid`, `consent_accepted_at`, `consent_version`) VALUES
(NULL, 'Administrateur EDG', NULL, 'admin@edg.gn', NULL, 'admin', 'active', NULL, NULL, NULL, 1, 1, 0, NULL, 1, 1, 1, 1, NULL, 1, 'bf9a0b7d-7e94-4c2f-a9f1-311f5ac16d38', 1, NULL, '2026-08-11 14:02:56', '2026-08-11 14:02:56', NULL, NULL, NULL, NULL, NULL),
(16, 'GOEPOGUI', 'GASPARD', 'gaspard@edg.com.gn', NULL, 'admin', 'active', NULL, NULL, NULL, 1, 0, 0, NULL, 1, 1, 1, 1, NULL, 2, '78db3f6f-c968-4706-9428-68be2758899e', 1, '{\"reset_code_hash\": null, \"reset_code_attempts\": 0, \"reset_code_expires_at\": null}', '2026-08-11 15:02:57', '2026-08-12 17:44:27', NULL, 1467, '33de571e94cd11f1b1070afd1ed01c67', NULL, NULL),
(16, 'Agent 1', 'Test', 'agent1@gmail.com', NULL, 'agent-support', 'active', NULL, NULL, NULL, 0, 0, 0, NULL, 1, 1, 1, 1, NULL, 3, '40a446b0-c15a-493b-a7d8-16f075b58345', 1, NULL, '2026-08-11 16:02:23', '2026-08-13 08:59:32', '2026-08-13 08:59:32', 1468, '0b1a8cae959e11f1824d0afd1ed01c67', NULL, NULL),
(16, 'agent2', 'Test', 'agent2@gmail.com', NULL, 'agent-support', 'active', NULL, NULL, NULL, 0, 0, 0, NULL, 1, 1, 1, 1, NULL, 4, 'cf5a5281-2005-4fe7-a550-c489f6295579', 1, NULL, '2026-08-11 16:03:16', '2026-08-13 08:59:19', '2026-08-13 08:59:20', 1469, '2ae33ae0959e11f1824d0afd1ed01c67', NULL, NULL),
(NULL, 'GOEPOGUI', 'GASPARD KAMAN', 'gaspardkamangoepogui96@gmail.com', '+224624211919', 'user', 'active', NULL, NULL, NULL, 0, 0, 0, NULL, 1, 1, 1, 1, NULL, 5, '62f46d8d-5de5-4018-82da-f453bd86e358', 1, '{\"reset_code_hash\": \"f4b1f5ecc8c408396170140e5902a2915d5712b116abc84db3f30cb96d53b79c\", \"reset_code_attempts\": 0, \"reset_code_expires_at\": \"2026-08-14T12:42:29.057015\"}', '2026-08-11 16:06:08', '2026-08-14 12:27:29', NULL, 1447, '866ab2f03ce611f1ae520afd1ed01c67', NULL, NULL),
(16, 'TOURE', 'AMADOU', 'toure@gmail.com', '+224612121212', 'agent-support', 'active', NULL, NULL, NULL, 0, 0, 0, NULL, 1, 1, 1, 1, NULL, 6, '92120037-b130-4868-8cc3-5a2d002e40ad', 1, NULL, '2026-08-11 16:40:28', '2026-08-12 12:52:35', NULL, 1470, '5dbef69895a311f1b0920afd1ed01c67', NULL, NULL),
(16, 'GOEPOGUI', 'GASPARD KAMUS', 'goepoguigaspardkaman5@gmail.com', NULL, 'agent-support', 'active', NULL, NULL, NULL, 1, 0, 0, NULL, 1, 1, 1, 1, NULL, 7, '775f549e-1c77-4b4e-98ec-0dca60d252d0', 1, 'null', '2026-08-12 11:34:35', '2026-08-17 09:56:43', NULL, 1471, 'cb5b5720964111f1abab0afd1ed01c67', NULL, NULL),
(16, 'ONIVOGUI', 'PAULETTE', 'onivoguipaulette5@gmail.com', NULL, 'agent-support', 'active', NULL, NULL, NULL, 1, 0, 0, NULL, 1, 1, 1, 1, NULL, 8, 'fcde1fd8-0a5c-486f-a996-3f7a9df2ce1d', 1, 'null', '2026-08-15 12:02:49', '2026-08-15 12:07:14', NULL, 1472, '3c43edce98a111f1990d0afd1ed01c67', NULL, NULL),
(16, 'KAHN', 'IBRAHIMA', 'ibrahimakahn@edg.com.gn', '+224621666024', 'user', 'active', NULL, NULL, NULL, 0, 0, 0, NULL, 1, 1, 1, 1, NULL, 9, '3c5784b8-097a-4504-83ba-946e64de8afc', 1, NULL, '2026-08-19 09:50:43', '2026-08-19 09:59:06', NULL, 1173, '4ebe0c05036011f1a190dc4546c60ae2', NULL, NULL),
(NULL, 'GOEPOGUI', 'ALPHONSE', 'alphonse@gmail.com', '+224628481106', 'user', 'active', NULL, NULL, NULL, 0, 0, 0, NULL, 1, 1, 1, 1, NULL, 10, '578d906a-d982-4eba-9ad3-380f3a6cb890', 1, NULL, '2026-08-19 10:46:40', '2026-08-19 10:46:40', NULL, 1474, '45807f8e9bbb11f1bdd90afd1ed01c67', NULL, NULL),
(NULL, 'DEVINFO 01', 'DIATAS', 'diatasdev01@gmail.com', '+224620114545', 'user', 'active', NULL, NULL, NULL, 0, 0, 0, NULL, 1, 1, 1, 1, NULL, 11, '9996b1c7-35b8-4bef-89c0-b41e4a87d768', 1, NULL, '2026-08-19 10:57:21', '2026-08-19 10:57:21', NULL, 1475, 'c338546e9bbc11f199500afd1ed01c67', NULL, NULL),
(NULL, 'DEV 03', 'DIATAS', 'diatasdevinfo03@gmail.com', '+224666000011', 'user', 'active', NULL, NULL, NULL, 0, 0, 0, NULL, 1, 1, 1, 1, NULL, 12, '0c519f1e-79be-4353-b49c-6c8c8693f402', 1, NULL, '2026-08-19 11:08:11', '2026-08-19 11:08:11', NULL, 1477, '46f17ac89bbe11f1a79d0afd1ed01c67', NULL, NULL),
(NULL, 'DEV 04', 'DIATAS', 'diatasdevinfo04@gmail.com', '+224666090909', 'user', 'active', NULL, NULL, NULL, 0, 0, 0, NULL, 1, 1, 1, 1, NULL, 13, '9f455b38-5575-42b7-9ea3-ba23d23d0f8b', 1, '{\"account_created_email_sent_at\": \"2026-08-28T07:54:09.736804\"}', '2026-08-19 11:09:43', '2026-08-28 07:54:09', NULL, 1424, '0b824383379c11f1afe3dc4546c60ae2', NULL, NULL),
(NULL, 'DEV 05', 'DIATAS', 'diatasdevinfo05@gmail.com', '+224666232323', 'user', 'active', NULL, NULL, NULL, 0, 0, 0, NULL, 1, 1, 1, 1, NULL, 14, 'dab3ea49-00b3-46a7-8773-85d1a2b02fef', 1, NULL, '2026-08-19 11:10:37', '2026-08-19 11:10:37', NULL, 1427, 'e709b99d37f711f19876dc4546c60ae2', NULL, NULL),
(NULL, 'DEV 06', 'DIATAS', 'mohamed-tassilimy.diaby@edg.com.gn', '+224666898989', 'user', 'active', NULL, NULL, NULL, 0, 0, 0, NULL, 1, 1, 1, 1, NULL, 15, 'db1f12b1-6bc3-4a4d-b5e8-e5df4b562d2f', 1, NULL, '2026-08-19 11:13:16', '2026-08-19 11:13:16', NULL, 1387, '8c68f800036011f18eefdc4546c60ae2', NULL, NULL),
(NULL, 'DEV 07', 'DIATAS', 'diatasdev07@gmail.com', '+224666909090', 'user', 'active', NULL, NULL, NULL, 0, 0, 0, NULL, 1, 1, 1, 1, NULL, 16, '819c17d1-0148-4a8a-b161-36be0485d286', 1, '{\"app_associated_email_sent_at\": \"2026-08-28T07:54:10.543673\"}', '2026-08-19 11:14:58', '2026-08-28 07:54:10', NULL, 1440, '3898ae343af511f1875edc4546c60ae2', NULL, NULL),
(NULL, 'DEV 08', 'DIATAS', 'diatasdev08@gmail.com', '+224625356177', 'user', 'active', NULL, NULL, NULL, 0, 0, 0, NULL, 1, 1, 1, 1, NULL, 20, 'a337ddd2-2892-4f3d-9798-7968e3dfc267', 1, NULL, '2026-08-19 11:18:38', '2026-08-19 11:18:38', NULL, 1478, 'bc81ce189bbf11f1a79d0afd1ed01c67', NULL, NULL),
(NULL, 'DEVINFO 09', 'DIATAS', 'diatas@edg.com.gn', '+224612000000', 'user', 'active', NULL, NULL, NULL, 0, 0, 0, NULL, 1, 1, 1, 1, NULL, 21, '531aabfb-9169-45ab-a70b-c959df72ab66', 1, NULL, '2026-08-19 11:27:15', '2026-08-19 11:27:15', NULL, 1398, '7ba633f22df811f19e5ddc4546c60ae2', NULL, NULL),
(NULL, 'DEVINFO 10', 'DIATAS', 'diatasdev10@gmail.com', '+224620000001', 'user', 'active', NULL, NULL, NULL, 0, 0, 0, NULL, 1, 1, 1, 1, NULL, 22, '26b48662-622c-4ef9-9054-72c2456df6b2', 1, NULL, '2026-08-19 11:36:20', '2026-08-19 11:36:20', NULL, 1473, '8fd46ec29bb811f18df00afd1ed01c67', NULL, NULL),
(NULL, 'DIATAS', 'MOHAMED', 'gaspard-dev02@edg.com.gn', '+224600010101', 'user', 'active', NULL, NULL, NULL, 0, 0, 0, NULL, 1, 1, 1, 1, NULL, 23, 'e2829eda-4b9b-4f39-907e-924fefd06027', 1, NULL, '2026-08-19 11:45:44', '2026-08-19 11:45:44', NULL, 1479, '13643a109bc311f19b000afd1ed01c67', NULL, NULL),
(NULL, 'DIABY', 'TASLIM', 'gaspard-dev03@edg.com.gn', '+224662010100', 'user', 'active', NULL, NULL, NULL, 0, 0, 0, NULL, 1, 1, 1, 1, NULL, 24, 'aa3b6445-c5b2-498b-9bcb-d9c748877010', 1, NULL, '2026-08-19 11:55:23', '2026-08-19 11:55:23', NULL, 1480, '3360b8249bc411f184190afd1ed01c67', NULL, NULL),
(NULL, 'Toure', 'Jamsato 2', 'jamsato2@edg.com.gn', '+224626678798', 'user', 'active', NULL, NULL, NULL, 0, 0, 0, NULL, 1, 1, 1, 1, '2026-08-21 20:55:43', 25, 'cb91d232-a0f2-4221-84b2-70abcaea923c', 1, NULL, '2026-08-21 20:55:43', '2026-08-21 20:55:43', NULL, 1461, '62e28b4885e611f192c10afd1ed01c67', '2026-08-21 20:55:43', '1.0'),
(NULL, 'TOURE', 'JAM', 'jamsato@edg.com.gn', '+224623515962', 'user', 'active', NULL, NULL, NULL, 0, 0, 0, NULL, 1, 1, 1, 1, '2026-08-24 08:51:14', 26, '016c3994-5c4d-4b4e-a727-fceb5ce7053e', 1, '{\"app_associated_email_sent_at\": \"2026-08-24T08:51:19.436449\"}', '2026-08-24 08:51:14', '2026-08-24 08:51:19', NULL, 1457, 'dd24a0467a3611f18cde0afd1ed01c67', '2026-08-24 08:51:14', '1.0'),
(NULL, 'DIALBY', 'LAMINE', 'lamine-diatas@edg.com.gn', '+224610222222', 'user', 'active', NULL, NULL, NULL, 0, 0, 0, NULL, 1, 1, 1, 1, NULL, 27, 'e80e79ea-6b1a-4191-82bb-dc12c377e210', 1, '{\"account_created_email_sent_at\": \"2026-08-24T10:29:25.814173\"}', '2026-08-24 10:29:19', '2026-08-24 10:29:25', NULL, 1484, 'aa0c97009fa611f1b2c40afd1ed01c67', NULL, NULL),
(NULL, 'SIDIBE', 'LASSOU', 'lamine-diatas12@edg.com.gn', '+224612090909', 'user', 'active', NULL, NULL, NULL, 0, 0, 0, NULL, 1, 1, 1, 1, NULL, 28, 'a4548424-a1c4-4b39-b274-3b58df1bce72', 1, '{\"account_created_email_sent_at\": \"2026-08-24T10:31:42.167753\"}', '2026-08-24 10:31:36', '2026-08-24 10:31:42', NULL, 1485, 'fb821df89fa611f188b90afd1ed01c67', NULL, NULL),
(NULL, 'DEV', 'NALO DIATAS', 'nalo-diatas.diaby@edg.com.gn', '+224612330033', 'user', 'active', NULL, NULL, NULL, 0, 0, 0, NULL, 1, 1, 1, 1, '2026-08-24 10:37:29', 29, '84787fd5-3f0e-4711-ac9f-049285513b15', 1, '{\"app_associated_email_sent_at\": \"2026-08-24T10:37:36.755624\"}', '2026-08-24 10:37:29', '2026-08-24 10:37:36', NULL, 1486, '771fa20a9fa711f188b90afd1ed01c67', '2026-08-24 10:37:29', '1.0'),
(NULL, 'GASPAR', 'TASLIM', 'nalo-diatas.diabyaaaa@edg.com.gn', '+224612330031', 'user', 'active', NULL, NULL, NULL, 0, 0, 0, NULL, 1, 1, 1, 1, NULL, 30, '2792e7bb-09da-45c2-a15b-0f79eae41f02', 1, '{\"account_created_email_sent_at\": \"2026-08-24T11:16:07.133547\"}', '2026-08-24 11:15:54', '2026-08-24 11:16:07', NULL, 1487, '2b9069189fad11f189290afd1ed01c67', NULL, NULL),
(NULL, 'Diallo', 'aminata', 'aminata@gmail.com', '+224611111111', 'user', 'active', NULL, NULL, NULL, 0, 0, 0, NULL, 1, 1, 1, 1, NULL, 31, '1a9c9b71-6e8b-4d46-8941-c23727925149', 1, '{\"account_created_email_sent_at\": \"2026-08-27T11:41:07.688963\"}', '2026-08-27 11:40:57', '2026-08-27 11:41:07', NULL, 1489, '2b49bdfea20c11f1ba570afd1ed01c67', NULL, NULL),
(NULL, 'Diaby', 'Mohamed Tassilimy', 'mohamed-tassilimy.diaby11@edg.com.gn', '+224620202020', 'user', 'active', NULL, NULL, NULL, 0, 0, 0, NULL, 1, 1, 1, 1, NULL, 32, 'da0b6a22-3f92-4143-abef-e61229ce3d6e', 1, '{\"account_created_email_sent_at\": \"2026-08-27T11:42:55.538305\"}', '2026-08-27 11:42:49', '2026-08-27 11:42:55', NULL, 1490, '6dbaa022a20c11f1ba570afd1ed01c67', NULL, NULL),
(NULL, 'Diaby', 'Mohamed Tassilimy', 'diatas02@edg.com.gn', '+224611000090', 'user', 'active', NULL, NULL, NULL, 0, 0, 0, NULL, 1, 1, 1, 1, NULL, 33, '7fc2a11e-e430-409e-8362-897427471571', 1, '{\"account_created_email_sent_at\": \"2026-08-27T11:48:40.409803\"}', '2026-08-27 11:48:32', '2026-08-27 11:48:40', NULL, 1491, '39fc5428a20d11f1ba570afd1ed01c67', NULL, NULL),
(NULL, 'Diaby', 'Mohamed Tassilimy', 'diatas2@gmail.com', '+224611000091', 'user', 'active', NULL, NULL, NULL, 0, 0, 0, NULL, 1, 1, 1, 1, NULL, 34, 'c69d7231-9f46-4a19-9750-5dc49da2213d', 1, '{\"account_created_email_sent_at\": \"2026-08-27T11:49:52.153864\"}', '2026-08-27 11:49:47', '2026-08-27 11:49:52', NULL, 1492, '67122faaa20d11f1ba570afd1ed01c67', NULL, NULL),
(NULL, 'KABA', 'OUMOU', 'oumou.kaba@edg.com.gn', '+224622405240', 'user', 'active', NULL, NULL, NULL, 0, 0, 0, NULL, 1, 1, 1, 1, '2026-08-27 11:53:11', 35, '19db3016-9c16-4fd0-bdc5-26f595ba1d86', 1, '{\"app_associated_email_sent_at\": \"2026-08-27T11:53:16.055397\"}', '2026-08-27 11:53:10', '2026-08-27 11:53:16', NULL, 1, '02cb518f035f11f18811dc4546c60ae2', '2026-08-27 11:53:11', '1.0'),
(NULL, 'GOEPOGUI', 'Gaspard kaman', 'admin@gmail.com', '+224624212121', 'admin', 'active', NULL, NULL, NULL, 0, 0, 0, NULL, 1, 1, 1, 1, NULL, 36, '6b17d23f-4362-4919-83e4-a37fb513f8b1', 1, NULL, '2026-08-27 12:14:41', '2026-08-28 11:29:58', NULL, 1493, 'e134b714a21011f1a6d50afd1ed01c67', NULL, NULL),
(NULL, 'Testing', 'Testing1', 'testing1@gmail.com', '+224601010101', 'user', 'active', NULL, NULL, NULL, 0, 0, 0, NULL, 1, 1, 1, 1, NULL, 37, 'c7eae970-7663-4bbc-9cfe-08a55e1c2608', 1, '{\"account_created_email_sent_at\": \"2026-08-27T12:31:56.727494\"}', '2026-08-27 12:31:51', '2026-08-27 12:31:56', NULL, 1494, '476472c0a21311f1b1360afd1ed01c67', NULL, NULL),
(NULL, 'Testing', 'Testing2', 'testing2@gmail.com', '+224602020202', 'user', 'active', NULL, NULL, NULL, 0, 0, 0, NULL, 1, 1, 1, 1, NULL, 38, 'ea8fd879-ca74-4104-a536-0760f12dd24f', 1, '{\"account_created_email_sent_at\": \"2026-08-27T12:32:59.667159\"}', '2026-08-27 12:32:54', '2026-08-27 12:32:59', NULL, 1495, '6cc43fb4a21311f1b1360afd1ed01c67', NULL, NULL),
(NULL, 'Testing', 'Testing3', 'testing3@gmail.com', '+224603030303', 'user', 'active', NULL, NULL, NULL, 0, 0, 0, NULL, 1, 1, 1, 1, NULL, 39, 'd40260f9-1fb6-4260-81fd-90430aff401b', 1, '{\"account_created_email_sent_at\": \"2026-08-27T12:33:54.398760\"}', '2026-08-27 12:33:49', '2026-08-27 12:33:54', NULL, 1496, '8dcad524a21311f1b1360afd1ed01c67', NULL, NULL);

-- --------------------------------------------------------

--
-- Structure de la table `account_status`
--

DROP TABLE IF EXISTS `account_status`;
CREATE TABLE IF NOT EXISTS `account_status` (
  `code` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `label` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `sort_order` smallint NOT NULL,
  `is_builtin` tinyint(1) NOT NULL,
  `id` int NOT NULL AUTO_INCREMENT,
  `uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` tinyint(1) NOT NULL,
  `infos` json DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `code` (`code`),
  UNIQUE KEY `uuid` (`uuid`),
  KEY `idx_ast_status` (`status`,`deleted_at`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Déchargement des données de la table `account_status`
--

INSERT INTO `account_status` (`code`, `label`, `sort_order`, `is_builtin`, `id`, `uuid`, `status`, `infos`, `created_at`, `updated_at`, `deleted_at`) VALUES
('active', 'Actif', 1, 1, 1, '9ec3d857-ac89-447d-9798-aa7bb7eeef72', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('inactive', 'Inactif', 2, 1, 2, 'd91a516e-7890-4af1-8e5a-307cf6cd37f3', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('suspended', 'Suspendu', 3, 1, 3, 'cae6d85b-d41d-4335-8fba-c8df3edc09d4', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('locked', 'Verrouillé', 4, 1, 4, '392971ba-894d-4698-9bdd-8c61743e519e', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL);

-- --------------------------------------------------------

--
-- Structure de la table `activity_log`
--

DROP TABLE IF EXISTS `activity_log`;
CREATE TABLE IF NOT EXISTS `activity_log` (
  `actor_id` int DEFAULT NULL,
  `actor` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `actor_role` enum('public','user','agent','chief','director','dg','admin','agent-support','chief-service','chief-departement','unknown') COLLATE utf8mb4_unicode_ci NOT NULL,
  `action` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL,
  `category` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `target` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL,
  `ip_address` varchar(45) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `user_agent` text COLLATE utf8mb4_unicode_ci,
  `log_status` enum('success','warning','error') COLLATE utf8mb4_unicode_ci NOT NULL,
  `id` int NOT NULL AUTO_INCREMENT,
  `uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` tinyint(1) NOT NULL,
  `infos` json DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uuid` (`uuid`),
  KEY `idx_log_actor` (`actor_id`),
  KEY `idx_log_created` (`created_at`),
  KEY `idx_log_logstatus` (`log_status`),
  KEY `idx_log_status` (`status`,`deleted_at`),
  KEY `idx_log_cat` (`category`)
) ENGINE=InnoDB AUTO_INCREMENT=205 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Déchargement des données de la table `activity_log`
--

INSERT INTO `activity_log` (`actor_id`, `actor`, `actor_role`, `action`, `category`, `target`, `ip_address`, `user_agent`, `log_status`, `id`, `uuid`, `status`, `infos`, `created_at`, `updated_at`, `deleted_at`) VALUES
(6, 'toure@gmail.com', 'user', 'logout', 'auth', 'account:6', '127.0.0.1', NULL, 'success', 1, '7afa4f06-478f-4476-a751-3276ca44ca0d', 1, NULL, '2026-08-12 08:44:53', '2026-08-12 08:44:53', NULL),
(6, 'toure@gmail.com', 'user', 'logout', 'auth', 'account:6', '127.0.0.1', NULL, 'success', 2, '4c761bf6-fd6c-47a7-a7a0-516cd1986b24', 1, NULL, '2026-08-12 08:44:57', '2026-08-12 08:44:57', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 3, '0fa26b78-a158-4e69-8fd2-a22bbd5a5619', 1, NULL, '2026-08-12 08:45:27', '2026-08-12 08:45:27', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 4, '9cb2022a-777b-40f8-9901-45a3f3a4cf09', 1, NULL, '2026-08-12 10:58:00', '2026-08-12 10:58:00', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'logout', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 5, '8a239381-5d4d-4c4f-96e7-902389938130', 1, NULL, '2026-08-12 11:01:33', '2026-08-12 11:01:33', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 6, '8d89e01e-4d91-4540-992a-1228be63b527', 1, NULL, '2026-08-12 11:22:56', '2026-08-12 11:22:56', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'logout', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 7, '0bcaf0c6-0241-407f-a422-fe33ac329540', 1, NULL, '2026-08-12 11:34:56', '2026-08-12 11:34:56', NULL),
(7, 'jamasatou1@gmail.com', 'agent-support', 'login', 'auth', 'account:7', '127.0.0.1', NULL, 'success', 8, '2096984e-a4a1-4234-a035-4c32996d8642', 1, NULL, '2026-08-12 11:35:19', '2026-08-12 11:35:19', NULL),
(7, 'jamasatou1@gmail.com', 'agent-support', 'logout', 'auth', 'account:7', '127.0.0.1', NULL, 'success', 9, 'ccf09d19-6597-4665-996c-e5b4ca5fe085', 1, NULL, '2026-08-12 11:50:04', '2026-08-12 11:50:04', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 10, '4f7f7b57-280c-46ef-bb1c-ff49ac6bbf44', 1, NULL, '2026-08-12 11:50:45', '2026-08-12 11:50:45', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 11, '82198508-ea80-4ef5-81f1-edfcfe95909b', 1, NULL, '2026-08-12 12:03:01', '2026-08-12 12:03:01', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 12, '8b6f0f41-aa9d-4e15-a358-77fbb1802baf', 1, NULL, '2026-08-12 12:11:33', '2026-08-12 12:11:33', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 13, 'efd3368b-b353-48a1-b7c5-eda72b5c418b', 1, NULL, '2026-08-12 12:21:15', '2026-08-12 12:21:15', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 14, 'cfb4abad-52dc-4099-b82d-6b04a7dd1e17', 1, NULL, '2026-08-12 12:21:31', '2026-08-12 12:21:31', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 15, '4564c23a-e391-4011-8a69-fbfbda6e791f', 1, NULL, '2026-08-12 12:21:49', '2026-08-12 12:21:49', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'logout', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 16, 'd3b734cc-ba14-47a7-942f-0c30637355a2', 1, NULL, '2026-08-12 12:53:18', '2026-08-12 12:53:18', NULL),
(7, 'jamasatou1@gmail.com', 'agent-support', 'login', 'auth', 'account:7', '127.0.0.1', NULL, 'success', 17, '9b040ba2-56bb-454f-8e1b-e755f11d1676', 1, NULL, '2026-08-12 12:53:41', '2026-08-12 12:53:41', NULL),
(7, 'jamasatou1@gmail.com', 'agent-support', 'logout', 'auth', 'account:7', '127.0.0.1', NULL, 'success', 18, 'eb0e6233-256e-48c5-ad96-32e860da9846', 1, NULL, '2026-08-12 12:58:45', '2026-08-12 12:58:45', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 19, '5faac8c1-d5be-47e9-8f2d-a826ae99175f', 1, NULL, '2026-08-12 12:59:51', '2026-08-12 12:59:51', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'logout', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 20, '9813cb42-9332-4233-b0af-24aec07cc5f2', 1, NULL, '2026-08-12 13:00:46', '2026-08-12 13:00:46', NULL),
(6, 'toure@gmail.com', 'agent-support', 'login', 'auth', 'account:6', '127.0.0.1', NULL, 'success', 21, '776b40bd-9e0e-4d39-adf5-6d0770c03efc', 1, NULL, '2026-08-12 13:01:16', '2026-08-12 13:01:16', NULL),
(NULL, 'agent1@gmail.com', 'unknown', 'login_failed', 'auth', 'auth', '127.0.0.1', NULL, 'error', 22, '3edd96b2-0478-4e1f-825e-41c57997f80e', 1, NULL, '2026-08-12 15:28:53', '2026-08-12 15:28:53', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 23, 'd2e52575-ace5-4641-b2d1-0c7ae0be69aa', 1, NULL, '2026-08-12 15:29:08', '2026-08-12 15:29:08', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 24, '819901bb-bf28-480b-96c0-5b4f5bf5b61e', 1, NULL, '2026-08-12 15:50:12', '2026-08-12 15:50:12', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 25, '198e14dd-0b27-462a-acfa-4faa68d1b6ce', 1, NULL, '2026-08-12 15:51:12', '2026-08-12 15:51:12', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 26, '5c9292cf-2531-4224-be88-7e9f8845d763', 1, NULL, '2026-08-12 15:52:17', '2026-08-12 15:52:17', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 27, '4804a30e-094f-42e9-9b96-64350b85e4bb', 1, NULL, '2026-08-12 15:53:19', '2026-08-12 15:53:19', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 28, '811f471e-c828-4db3-af6d-c8167d625375', 1, NULL, '2026-08-12 15:54:17', '2026-08-12 15:54:17', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 29, 'd1354b6d-c8b5-4d86-b7d6-1bb061011977', 1, NULL, '2026-08-12 15:55:21', '2026-08-12 15:55:21', NULL),
(6, 'toure@gmail.com', 'agent-support', 'logout', 'auth', 'account:6', '127.0.0.1', NULL, 'success', 30, '3ecfd7e4-fceb-4ff9-b578-01d078061c83', 1, NULL, '2026-08-12 16:07:23', '2026-08-12 16:07:23', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'reset_password', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 31, 'd04dc84f-b331-489a-8a3f-8b9c21f93175', 1, NULL, '2026-08-12 16:23:55', '2026-08-12 16:23:55', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 32, '52726a44-dd70-4728-99a8-89987d32a3a3', 1, NULL, '2026-08-12 16:24:12', '2026-08-12 16:24:12', NULL),
(NULL, 'gaspard@edg.com.gn', 'unknown', 'login_failed', 'auth', 'auth', '127.0.0.1', NULL, 'error', 33, '49f95517-a375-4e9f-9cc7-b83bf1ecfb2f', 1, NULL, '2026-08-12 16:24:16', '2026-08-12 16:24:16', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'reset_password', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 34, 'f1d53184-4b76-408c-89b4-98c234bf055b', 1, NULL, '2026-08-12 16:24:36', '2026-08-12 16:24:36', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 35, 'f3402045-a8b4-4676-9051-a1e956df412e', 1, NULL, '2026-08-12 16:24:47', '2026-08-12 16:24:47', NULL),
(NULL, 'gaspardKamangoepogui96@gmail.com', 'unknown', 'login_failed', 'auth', 'auth', '127.0.0.1', NULL, 'error', 36, 'df97f41f-f02a-450c-8fd4-0da62750554d', 1, NULL, '2026-08-12 16:37:41', '2026-08-12 16:37:41', NULL),
(5, 'gaspardkamangoepogui96@gmail.com', 'user', 'reset_password', 'auth', 'account:5', '127.0.0.1', NULL, 'success', 37, '128c755f-4ea6-4f68-98e0-29f931b10679', 1, NULL, '2026-08-12 17:18:16', '2026-08-12 17:18:16', NULL),
(5, 'gaspardkamangoepogui96@gmail.com', 'user', 'login', 'auth', 'account:5', '127.0.0.1', NULL, 'success', 38, 'dd297de2-2431-4eae-9b7e-142fd1337fca', 1, NULL, '2026-08-12 17:18:31', '2026-08-12 17:18:31', NULL),
(5, 'gaspardkamangoepogui96@gmail.com', 'user', 'logout', 'auth', 'account:5', '127.0.0.1', NULL, 'success', 39, '121b7992-718a-4bac-be64-367b7f070c0e', 1, NULL, '2026-08-12 17:26:45', '2026-08-12 17:26:45', NULL),
(5, 'gaspardkamangoepogui96@gmail.com', 'user', 'reset_password', 'auth', 'account:5', '127.0.0.1', NULL, 'success', 40, '9c7681c0-23ac-4ba2-a1ba-c73f606eb547', 1, NULL, '2026-08-12 17:28:24', '2026-08-12 17:28:24', NULL),
(5, 'gaspardkamangoepogui96@gmail.com', 'user', 'login', 'auth', 'account:5', '127.0.0.1', NULL, 'success', 41, '5a33d40e-9ec0-4f9e-b8ae-c7c49e224b35', 1, NULL, '2026-08-12 17:28:55', '2026-08-12 17:28:55', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'reset_password', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 42, '0b901af3-1ec4-45f3-a9aa-7d603f2bd3a4', 1, NULL, '2026-08-12 17:43:40', '2026-08-12 17:43:40', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 43, 'd880bb8b-d59b-4843-88fb-595309afcb70', 1, NULL, '2026-08-12 17:44:04', '2026-08-12 17:44:04', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'reset_password', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 44, 'c68b2e51-6341-497c-bc67-183923b1b0e4', 1, NULL, '2026-08-12 17:44:27', '2026-08-12 17:44:27', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 45, '23a30962-fb59-4c42-869d-77dad6cfeda5', 1, NULL, '2026-08-12 17:44:31', '2026-08-12 17:44:31', NULL),
(5, 'gaspardkamangoepogui96@gmail.com', 'user', 'logout', 'auth', 'account:5', '127.0.0.1', NULL, 'success', 46, '133e5f8a-2228-4422-96b4-09fb66e3b1dd', 1, NULL, '2026-08-12 22:02:23', '2026-08-12 22:02:23', NULL),
(5, 'gaspardkamangoepogui96@gmail.com', 'user', 'logout', 'auth', 'account:5', '127.0.0.1', NULL, 'success', 47, '62555d2f-2fb4-403d-aabc-d4ba12c51c69', 1, NULL, '2026-08-12 22:02:36', '2026-08-12 22:02:36', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 48, 'c098018a-5102-4857-80f5-b4e69747de25', 1, NULL, '2026-08-12 22:03:44', '2026-08-12 22:03:44', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 49, 'ceeac702-a7db-4ce6-91f9-97de8a9f6c64', 1, NULL, '2026-08-12 22:04:07', '2026-08-12 22:04:07', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 50, '025e3ea6-4c99-4c21-b6aa-213c2baa2883', 1, NULL, '2026-08-13 08:56:39', '2026-08-13 08:56:39', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'logout', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 51, 'd2b8c480-fa87-493d-bef6-a30dcbbb80ab', 1, NULL, '2026-08-13 09:08:57', '2026-08-13 09:08:57', NULL),
(5, 'gaspardkamangoepogui96@gmail.com', 'user', 'login', 'auth', 'account:5', '127.0.0.1', NULL, 'success', 52, '0fe19367-41a4-498d-b4dc-3e04e95a6c6f', 1, NULL, '2026-08-13 09:30:45', '2026-08-13 09:30:45', NULL),
(5, 'gaspardkamangoepogui96@gmail.com', 'user', 'logout', 'auth', 'account:5', '127.0.0.1', NULL, 'success', 53, '56303435-7fec-4673-bd51-e38b2f89bf66', 1, NULL, '2026-08-13 10:20:25', '2026-08-13 10:20:25', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 54, 'abedc80e-b8fe-4f14-aefa-4960984ba783', 1, NULL, '2026-08-13 10:20:38', '2026-08-13 10:20:38', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 55, '5eeac822-97d1-4e68-9712-01f0ed2b9d37', 1, NULL, '2026-08-13 10:23:34', '2026-08-13 10:23:34', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 56, 'b7de28b7-1457-4ab5-90dd-2cb285faad47', 1, NULL, '2026-08-13 10:25:11', '2026-08-13 10:25:11', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'logout', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 57, '986e58e8-e763-4f97-9a40-5daf655509bd', 1, NULL, '2026-08-13 11:04:53', '2026-08-13 11:04:53', NULL),
(7, 'jamasatou1@gmail.com', 'agent-support', 'login', 'auth', 'account:7', '127.0.0.1', NULL, 'success', 58, '092bdc54-95ac-409f-92a1-e5c7f6f013e2', 1, NULL, '2026-08-13 11:05:18', '2026-08-13 11:05:18', NULL),
(7, 'jamasatou1@gmail.com', 'agent-support', 'logout', 'auth', 'account:7', '127.0.0.1', NULL, 'success', 59, '510574e6-7f73-4d02-b1df-09456ca99c3a', 1, NULL, '2026-08-13 16:11:10', '2026-08-13 16:11:10', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 60, 'cf25776b-9d18-4209-a1f5-41c5139c03a6', 1, NULL, '2026-08-13 16:11:35', '2026-08-13 16:11:35', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'logout', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 61, 'fa6e5df3-56b3-42c1-a732-7e714c8f7619', 1, NULL, '2026-08-13 16:13:11', '2026-08-13 16:13:11', NULL),
(7, 'jamasatou1@gmail.com', 'agent-support', 'login', 'auth', 'account:7', '127.0.0.1', NULL, 'success', 62, 'dc749627-7934-4639-aacf-123bf0d56728', 1, NULL, '2026-08-13 16:13:45', '2026-08-13 16:13:45', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 63, '85e3ecfd-d340-46cf-9e0e-5df1b82c55eb', 1, NULL, '2026-08-14 10:00:36', '2026-08-14 10:00:36', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 64, 'f318fdfa-c876-4d84-ac55-9b7df0806bcb', 1, NULL, '2026-08-14 11:15:34', '2026-08-14 11:15:34', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 65, 'c86c2fdd-b085-4775-868a-976fb447160f', 1, NULL, '2026-08-14 11:20:40', '2026-08-14 11:20:40', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 66, 'd25f17b2-60f0-4f34-b777-3d38d18524dc', 1, NULL, '2026-08-15 11:42:28', '2026-08-15 11:42:28', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'logout', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 67, '8803f579-e77b-48ac-bef6-95ace26a4e0a', 1, NULL, '2026-08-15 12:03:20', '2026-08-15 12:03:20', NULL),
(8, 'pauletteonivogui2024@gmail.com', 'agent-support', 'login', 'auth', 'account:8', '127.0.0.1', NULL, 'success', 68, 'a9cdbda7-6da9-4a23-b512-6d126987aac6', 1, NULL, '2026-08-15 12:03:39', '2026-08-15 12:03:39', NULL),
(8, 'onivoguipaulette5@gmail.com', 'agent-support', 'logout', 'auth', 'account:8', '127.0.0.1', NULL, 'success', 69, 'f4fb2b61-3077-4faa-a1aa-54a40a9c96f9', 1, NULL, '2026-08-15 14:47:07', '2026-08-15 14:47:07', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 70, '6700c912-3f8d-44d1-883c-246b25d183b2', 1, NULL, '2026-08-15 14:47:18', '2026-08-15 14:47:18', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'logout', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 71, '9891c752-7f9b-447d-9505-42340cc820d3', 1, NULL, '2026-08-15 15:37:42', '2026-08-15 15:37:42', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 72, 'bf0342f6-d5a7-4814-ba17-78b6a6b1820b', 1, NULL, '2026-08-15 15:38:17', '2026-08-15 15:38:17', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 73, 'c45e624e-69c1-404d-8cbc-d7d9652fc98f', 1, NULL, '2026-08-15 15:38:36', '2026-08-15 15:38:36', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 74, 'f0d0fad0-9172-4f6a-bd5d-dfc170037e3e', 1, NULL, '2026-08-15 15:39:05', '2026-08-15 15:39:05', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 75, '2cbd27b1-6d45-418a-8475-179dbe100811', 1, NULL, '2026-08-15 16:32:17', '2026-08-15 16:32:17', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 76, '1100d5b0-e561-48d9-afaa-9e37cc85d179', 1, NULL, '2026-08-15 16:33:28', '2026-08-15 16:33:28', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 77, '4958824e-9f54-41ce-b6f9-e63395d6c692', 1, NULL, '2026-08-15 16:34:36', '2026-08-15 16:34:36', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 78, '01502b30-4873-43f8-97ec-5c7732f86564', 1, NULL, '2026-08-15 16:36:38', '2026-08-15 16:36:38', NULL),
(5, 'gaspardkamangoepogui96@gmail.com', 'user', 'login', 'auth', 'account:5', '127.0.0.1', NULL, 'success', 79, '2a204c91-22b0-40bc-9620-ff70c36991f7', 1, NULL, '2026-08-17 09:51:55', '2026-08-17 09:51:55', NULL),
(5, 'gaspardkamangoepogui96@gmail.com', 'user', 'logout', 'auth', 'account:5', '127.0.0.1', NULL, 'success', 80, '969a6341-724a-4259-80a9-6b4404717a14', 1, NULL, '2026-08-17 09:52:56', '2026-08-17 09:52:56', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 81, '1c3eb6be-f910-4511-ba64-cfa357306f7f', 1, NULL, '2026-08-17 09:54:56', '2026-08-17 09:54:56', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'logout', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 82, '34fb3bb9-7b8a-4c65-acf3-796a7a67d922', 1, NULL, '2026-08-17 09:56:58', '2026-08-17 09:56:58', NULL),
(7, 'goepoguigaspardkaman5@gmail.com', 'agent-support', 'login', 'auth', 'account:7', '127.0.0.1', NULL, 'success', 83, '3c78d50d-9f62-4ab1-9aba-2b52261d1791', 1, NULL, '2026-08-17 09:57:33', '2026-08-17 09:57:33', NULL),
(NULL, 'goepoguigaspardkaman5@gmail.com', 'unknown', 'login_failed', 'auth', 'auth', '127.0.0.1', NULL, 'error', 84, '3e0354a6-6cd0-4e85-9f4d-7bfe0ff8c3fb', 1, NULL, '2026-08-17 10:02:46', '2026-08-17 10:02:46', NULL),
(7, 'goepoguigaspardkaman5@gmail.com', 'agent-support', 'login', 'auth', 'account:7', '127.0.0.1', NULL, 'success', 85, 'aa260cf1-6025-442c-9875-2f03c00926fb', 1, NULL, '2026-08-17 10:03:26', '2026-08-17 10:03:26', NULL),
(5, 'gaspardkamangoepogui96@gmail.com', 'user', 'login', 'auth', 'account:5', '127.0.0.1', NULL, 'success', 86, '3d5aced1-b526-4696-bd81-417986e1c9f6', 1, NULL, '2026-08-17 10:04:00', '2026-08-17 10:04:00', NULL),
(7, 'goepoguigaspardkaman5@gmail.com', 'agent-support', 'logout', 'auth', 'account:7', '127.0.0.1', NULL, 'success', 87, '688e3e8a-8f8f-431d-9023-5ff78c0a529f', 1, NULL, '2026-08-17 11:55:03', '2026-08-17 11:55:03', NULL),
(7, 'goepoguigaspardkaman5@gmail.com', 'agent-support', 'logout', 'auth', 'account:7', '127.0.0.1', NULL, 'success', 88, '3c777065-e3f5-4543-badd-e711388ccc6b', 1, NULL, '2026-08-17 11:55:04', '2026-08-17 11:55:04', NULL),
(7, 'goepoguigaspardkaman5@gmail.com', 'agent-support', 'login', 'auth', 'account:7', '127.0.0.1', NULL, 'success', 89, 'e33538c4-8990-41f3-bbb1-efd1888bdf69', 1, NULL, '2026-08-17 16:12:34', '2026-08-17 16:12:34', NULL),
(7, 'goepoguigaspardkaman5@gmail.com', 'agent-support', 'login', 'auth', 'account:7', '127.0.0.1', NULL, 'success', 90, 'da1601b3-ad6c-4fd4-b5e9-d421aa16f4d9', 1, NULL, '2026-08-17 16:12:43', '2026-08-17 16:12:43', NULL),
(7, 'goepoguigaspardkaman5@gmail.com', 'agent-support', 'login', 'auth', 'account:7', '127.0.0.1', NULL, 'success', 91, '89f9a909-1827-4334-adf5-60b0dd244d64', 1, NULL, '2026-08-19 09:37:42', '2026-08-19 09:37:42', NULL),
(7, 'goepoguigaspardkaman5@gmail.com', 'agent-support', 'logout', 'auth', 'account:7', '127.0.0.1', NULL, 'success', 92, 'c279f24c-3bcb-4800-9b92-06af991950e9', 1, NULL, '2026-08-19 09:39:32', '2026-08-19 09:39:32', NULL),
(7, 'goepoguigaspardkaman5@gmail.com', 'agent-support', 'login', 'auth', 'account:7', '127.0.0.1', NULL, 'success', 93, 'e2201bd1-cc60-4001-a771-9952c5c1f96e', 1, NULL, '2026-08-19 09:40:26', '2026-08-19 09:40:26', NULL),
(7, 'goepoguigaspardkaman5@gmail.com', 'agent-support', 'logout', 'auth', 'account:7', '127.0.0.1', NULL, 'success', 94, '98ccdde3-339d-4121-bc0d-937fc5aefa6f', 1, NULL, '2026-08-19 09:48:50', '2026-08-19 09:48:50', NULL),
(9, 'ibrahimakahn@edg.com.gn', 'user', 'register', 'auth', 'account:9', '127.0.0.1', NULL, 'success', 95, 'd1990657-c6e1-482c-9941-096a29af78cb', 1, NULL, '2026-08-19 09:50:43', '2026-08-19 09:50:43', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 96, '649277e1-2b24-4cb1-b025-7d3a95ff11e6', 1, NULL, '2026-08-19 09:56:53', '2026-08-19 09:56:53', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'logout', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 97, 'a9f06e95-1204-49c0-bdfd-1e2545d990c7', 1, NULL, '2026-08-19 09:59:16', '2026-08-19 09:59:16', NULL),
(NULL, 'ibrahimakahn@edg.com.gn', 'unknown', 'login_failed', 'auth', 'auth', '127.0.0.1', NULL, 'error', 98, '6b8b04fb-84be-40b9-98f0-99888f1f4e7f', 1, NULL, '2026-08-19 09:59:28', '2026-08-19 09:59:28', NULL),
(NULL, 'ibrahimakahn@edg.com.gn', 'unknown', 'login_failed', 'auth', 'auth', '127.0.0.1', NULL, 'error', 99, 'ad96b056-9f8f-4045-9fa1-075e25f8ead0', 1, NULL, '2026-08-19 10:00:47', '2026-08-19 10:00:47', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 100, '627a1951-ce3b-41b5-803c-3c74a76abf91', 1, NULL, '2026-08-19 10:01:02', '2026-08-19 10:01:02', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'logout', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 101, '91c998ab-0ed4-452f-b04a-70709fbe3ff4', 1, NULL, '2026-08-19 10:14:58', '2026-08-19 10:14:58', NULL),
(6, 'toure@gmail.com', 'agent-support', 'login', 'auth', 'account:6', '127.0.0.1', NULL, 'success', 102, '648ce6de-df7e-472e-8f9f-20c14e7ad81c', 1, NULL, '2026-08-19 10:15:16', '2026-08-19 10:15:16', NULL),
(6, 'toure@gmail.com', 'agent-support', 'logout', 'auth', 'account:6', '127.0.0.1', NULL, 'success', 103, '9bab1615-9ea5-43ab-a3c9-2ff4c62642cd', 1, NULL, '2026-08-19 10:23:24', '2026-08-19 10:23:24', NULL),
(NULL, 'ibrahimakahn@edg.com.gn', 'unknown', 'login_failed', 'auth', 'auth', '127.0.0.1', NULL, 'error', 104, '15081253-5f6d-491f-96bc-0977cec65a30', 1, NULL, '2026-08-19 10:23:35', '2026-08-19 10:23:35', NULL),
(NULL, 'ibrahimakahn@edg.com.gn', 'unknown', 'login_failed', 'auth', 'auth', '127.0.0.1', NULL, 'error', 105, '3781ad08-3ef6-421d-822c-1b2ea7b693a6', 1, NULL, '2026-08-19 10:32:29', '2026-08-19 10:32:29', NULL),
(NULL, 'ibrahimakahn@edg.com.gn', 'unknown', 'login_failed', 'auth', 'auth', '127.0.0.1', NULL, 'error', 106, 'ddc4c99d-b1e5-4d28-9fab-be2281395b34', 1, NULL, '2026-08-19 10:39:52', '2026-08-19 10:39:52', NULL),
(7, 'goepoguigaspardkaman5@gmail.com', 'agent-support', 'login', 'auth', 'account:7', '127.0.0.1', NULL, 'success', 107, 'e151e8bc-ec97-4ec0-9015-72a1ae38b04b', 1, NULL, '2026-08-19 10:41:06', '2026-08-19 10:41:06', NULL),
(7, 'goepoguigaspardkaman5@gmail.com', 'agent-support', 'logout', 'auth', 'account:7', '127.0.0.1', NULL, 'success', 108, '673abf43-3f1a-44d9-bc24-73f81f6db798', 1, NULL, '2026-08-19 10:41:37', '2026-08-19 10:41:37', NULL),
(5, 'gaspardkamangoepogui96@gmail.com', 'user', 'login', 'auth', 'account:5', '127.0.0.1', NULL, 'success', 109, '83d6eb18-4087-4d08-966a-aa535e03af07', 1, NULL, '2026-08-19 10:42:02', '2026-08-19 10:42:02', NULL),
(5, 'gaspardkamangoepogui96@gmail.com', 'user', 'logout', 'auth', 'account:5', '127.0.0.1', NULL, 'success', 110, '5972d3d2-b748-4508-b088-68df40b7f70d', 1, NULL, '2026-08-19 10:42:15', '2026-08-19 10:42:15', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 111, '8d64b64f-9021-4746-8ddb-134af3e55600', 1, NULL, '2026-08-19 10:42:39', '2026-08-19 10:42:39', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'logout', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 112, '7e8a0f67-3527-4f6a-b878-77d7d43c7c09', 1, NULL, '2026-08-19 10:43:24', '2026-08-19 10:43:24', NULL),
(9, 'ibrahimakahn@edg.com.gn', 'user', 'login', 'auth', 'account:9', '127.0.0.1', NULL, 'success', 113, '22c2d4ed-048f-4dd3-b885-12b9b3ce5032', 1, NULL, '2026-08-19 10:43:48', '2026-08-19 10:43:48', NULL),
(9, 'ibrahimakahn@edg.com.gn', 'user', 'logout', 'auth', 'account:9', '127.0.0.1', NULL, 'success', 114, '8818c0b8-b62c-4f9a-9b25-e0bc22dba28e', 1, NULL, '2026-08-19 10:44:42', '2026-08-19 10:44:42', NULL),
(10, 'alphonse@gmail.com', 'user', 'register', 'auth', 'account:10', '127.0.0.1', NULL, 'success', 115, 'b8e6120c-6d7f-4e23-aaa7-36752ef19278', 1, NULL, '2026-08-19 10:46:40', '2026-08-19 10:46:40', NULL),
(10, 'alphonse@gmail.com', 'user', 'login', 'auth', 'account:10', '127.0.0.1', NULL, 'success', 116, 'ac0a9e09-1adc-4d35-bbfe-8220360f0509', 1, NULL, '2026-08-19 10:47:22', '2026-08-19 10:47:22', NULL),
(10, 'alphonse@gmail.com', 'user', 'logout', 'auth', 'account:10', '127.0.0.1', NULL, 'success', 117, 'f93963db-f5bb-4cef-afe4-24520b350a9f', 1, NULL, '2026-08-19 10:51:48', '2026-08-19 10:51:48', NULL),
(2, 'gaspard@edg.com.gn', 'admin', 'login', 'auth', 'account:2', '127.0.0.1', NULL, 'success', 118, '89c56d7e-761a-4cc8-ad68-322dbc95908c', 1, NULL, '2026-08-19 10:52:14', '2026-08-19 10:52:14', NULL),
(11, 'diatasdev01@gmail.com', 'user', 'register', 'auth', 'account:11', '127.0.0.1', NULL, 'success', 119, '6f8c0c23-1fc1-4a04-96cc-7ca3b717aa42', 1, NULL, '2026-08-19 10:57:21', '2026-08-19 10:57:21', NULL),
(11, 'diatasdev01@gmail.com', 'user', 'login', 'auth', 'account:11', '127.0.0.1', NULL, 'success', 120, 'f24a3f23-0258-4317-893a-f31229f28615', 1, NULL, '2026-08-19 11:01:53', '2026-08-19 11:01:53', NULL),
(11, 'diatasdev01@gmail.com', 'user', 'logout', 'auth', 'account:11', '127.0.0.1', NULL, 'success', 121, 'd714782e-8bd9-4305-b6a9-5c43225cc276', 1, NULL, '2026-08-19 11:06:55', '2026-08-19 11:06:55', NULL),
(12, 'diatasdevinfo03@gmail.com', 'user', 'register', 'auth', 'account:12', '127.0.0.1', NULL, 'success', 122, 'ca661137-de7c-4f42-adef-fd637c8e2bdf', 1, NULL, '2026-08-19 11:08:11', '2026-08-19 11:08:11', NULL),
(13, 'diatasdevinfo04@gmail.com', 'user', 'register', 'auth', 'account:13', '127.0.0.1', NULL, 'success', 123, 'a4f8bac1-6e27-4858-abed-6823ecb30344', 1, NULL, '2026-08-19 11:09:43', '2026-08-19 11:09:43', NULL),
(14, 'diatasdevinfo05@gmail.com', 'user', 'register', 'auth', 'account:14', '127.0.0.1', NULL, 'success', 124, '9951c64f-bdba-4fd4-8e33-ed8dca059a62', 1, NULL, '2026-08-19 11:10:37', '2026-08-19 11:10:37', NULL),
(11, 'diatasdev01@gmail.com', 'user', 'login', 'auth', 'account:11', '127.0.0.1', NULL, 'success', 125, 'c4244998-bf14-4397-8844-16f2864d4417', 1, NULL, '2026-08-19 11:11:19', '2026-08-19 11:11:19', NULL),
(11, 'diatasdev01@gmail.com', 'user', 'logout', 'auth', 'account:11', '127.0.0.1', NULL, 'success', 126, '5a50c4bc-2ceb-4c1f-8966-44d909fefba1', 1, NULL, '2026-08-19 11:11:35', '2026-08-19 11:11:35', NULL),
(15, 'mohamed-tassilimy.diaby@edg.com.gn', 'user', 'register', 'auth', 'account:15', '127.0.0.1', NULL, 'success', 127, 'a7ada9f0-15e9-4f80-bb02-ac9a558c06fd', 1, NULL, '2026-08-19 11:13:16', '2026-08-19 11:13:16', NULL),
(16, 'diatasdev07@gmail.com', 'user', 'register', 'auth', 'account:16', '127.0.0.1', NULL, 'success', 128, '9b0c02d7-310e-4cf3-acdf-5d31a2f68d97', 1, NULL, '2026-08-19 11:14:59', '2026-08-19 11:14:59', NULL),
(20, 'diatasdev08@gmail.com', 'user', 'register', 'auth', 'account:20', '127.0.0.1', NULL, 'success', 129, '72180842-3b0b-463a-b856-f3c3a71773d5', 1, NULL, '2026-08-19 11:18:38', '2026-08-19 11:18:38', NULL),
(21, 'diatas@edg.com.gn', 'user', 'register', 'auth', 'account:21', '127.0.0.1', NULL, 'success', 130, '35aab1b1-871c-4142-b81a-40e8c06fb1b9', 1, NULL, '2026-08-19 11:27:15', '2026-08-19 11:27:15', NULL),
(22, 'diatasdev10@gmail.com', 'user', 'register', 'auth', 'account:22', '127.0.0.1', NULL, 'success', 131, '4f676897-c26f-466d-ae0d-bed2b9225367', 1, NULL, '2026-08-19 11:36:20', '2026-08-19 11:36:20', NULL),
(23, 'gaspard-dev02@edg.com.gn', 'user', 'register', 'auth', 'account:23', '127.0.0.1', NULL, 'success', 132, '8b03ee24-3977-4f6e-b7ef-b77424be6925', 1, NULL, '2026-08-19 11:45:44', '2026-08-19 11:45:44', NULL),
(NULL, 'gaspard-dev01@edg.com.gn', 'unknown', 'login_failed', 'auth', 'auth', '127.0.0.1', NULL, 'error', 133, 'e04c263c-df81-4975-b727-4191da89c571', 1, NULL, '2026-08-19 11:46:51', '2026-08-19 11:46:51', NULL),
(23, 'gaspard-dev02@edg.com.gn', 'user', 'login', 'auth', 'account:23', '127.0.0.1', NULL, 'success', 134, '643087ee-5e2f-46a7-b656-c0d5d68b67da', 1, NULL, '2026-08-19 11:47:03', '2026-08-19 11:47:03', NULL),
(23, 'gaspard-dev02@edg.com.gn', 'user', 'logout', 'auth', 'account:23', '127.0.0.1', NULL, 'success', 135, '5be142c6-8976-4e8c-b220-fdcb3394ddb2', 1, NULL, '2026-08-19 11:51:47', '2026-08-19 11:51:47', NULL),
(24, 'gaspard-dev03@edg.com.gn', 'user', 'register', 'auth', 'account:24', '127.0.0.1', NULL, 'success', 136, '21be0f87-78d2-4cae-8962-a3c4e06fd161', 1, NULL, '2026-08-19 11:55:23', '2026-08-19 11:55:23', NULL),
(24, 'gaspard-dev03@edg.com.gn', 'user', 'login', 'auth', 'account:24', '127.0.0.1', NULL, 'success', 137, '4b03fd26-cd96-4f68-8049-deba1e5770ca', 1, NULL, '2026-08-19 11:58:55', '2026-08-19 11:58:55', NULL),
(24, 'gaspard-dev03@edg.com.gn', 'user', 'logout', 'auth', 'account:24', '127.0.0.1', NULL, 'success', 138, 'e882700e-bfdf-4bd5-afe1-ac93712d1d63', 1, NULL, '2026-08-19 12:05:52', '2026-08-19 12:05:52', NULL),
(23, 'gaspard-dev02@edg.com.gn', 'user', 'login', 'auth', 'account:23', '127.0.0.1', NULL, 'success', 139, '645b5561-508b-4fc1-9f9c-65cdd035f792', 1, NULL, '2026-08-19 23:37:47', '2026-08-19 23:37:47', NULL),
(11, 'diatasdev01@gmail.com', 'user', 'login', 'auth', 'account:11', '127.0.0.1', NULL, 'success', 140, '68c0396e-d939-40c7-9fcc-8fe381e35b95', 1, NULL, '2026-08-19 23:39:49', '2026-08-19 23:39:49', NULL),
(11, 'diatasdev01@gmail.com', 'user', 'login', 'auth', 'account:11', '127.0.0.1', NULL, 'success', 141, 'f1bb1a6d-1ec2-4a40-880b-ebafdf81192e', 1, NULL, '2026-08-21 18:59:05', '2026-08-21 18:59:05', NULL),
(11, 'diatasdev01@gmail.com', 'user', 'login', 'auth', 'account:11', '127.0.0.1', NULL, 'success', 142, '873583b5-d648-4a34-af21-001b8fca391d', 1, NULL, '2026-08-21 18:59:32', '2026-08-21 18:59:32', NULL),
(11, 'diatasdev01@gmail.com', 'user', 'login', 'auth', 'account:11', '127.0.0.1', NULL, 'success', 143, '5a765689-e758-43ca-a57d-2d55647db39d', 1, NULL, '2026-08-21 19:14:00', '2026-08-21 19:14:00', NULL),
(NULL, 'jamsato2@edg.com.gn', 'unknown', 'login_needs_consent', 'auth', 'auth', '127.0.0.1', NULL, 'success', 144, '152cdd9b-1cea-4806-a98b-4ee3b9b91680', 1, NULL, '2026-08-21 20:54:27', '2026-08-21 20:54:27', NULL),
(25, 'jamsato2@edg.com.gn', 'user', 'consent_accept', 'auth', 'account:25', '127.0.0.1', NULL, 'success', 145, 'b6a8820b-8558-4346-8917-da153441c44c', 1, NULL, '2026-08-21 20:55:44', '2026-08-21 20:55:44', NULL),
(25, 'jamsato2@edg.com.gn', 'user', 'login', 'auth', 'account:25', '127.0.0.1', NULL, 'success', 146, '16278cd9-1650-442e-8518-f7412b182b0b', 1, NULL, '2026-08-24 08:28:24', '2026-08-24 08:28:24', NULL),
(25, 'jamsato2@edg.com.gn', 'user', 'logout', 'auth', 'account:25', '127.0.0.1', NULL, 'success', 147, '843963e5-d320-41bb-8158-f40d5c381c34', 1, NULL, '2026-08-24 08:50:17', '2026-08-24 08:50:17', NULL),
(NULL, 'jamsato@edg.com.gn', 'unknown', 'login_needs_consent', 'auth', 'auth', '127.0.0.1', NULL, 'success', 148, 'a5be5bee-869d-4a2c-b549-4194ad0ecd39', 1, NULL, '2026-08-24 08:50:44', '2026-08-24 08:50:44', NULL),
(26, 'jamsato@edg.com.gn', 'user', 'consent_accept', 'auth', 'account:26', '127.0.0.1', NULL, 'success', 149, 'dff34441-c058-4c52-828c-8875f1807e2d', 1, NULL, '2026-08-24 08:51:15', '2026-08-24 08:51:15', NULL),
(26, 'jamsato@edg.com.gn', 'user', 'logout', 'auth', 'account:26', '127.0.0.1', NULL, 'success', 150, 'ebaa8abc-fab8-4034-81af-c607b2fe877a', 1, NULL, '2026-08-24 10:27:52', '2026-08-24 10:27:52', NULL),
(27, 'lamine-diatas@edg.com.gn', 'user', 'register', 'auth', 'account:27', '127.0.0.1', NULL, 'success', 151, 'acba96b4-2255-4c27-a787-7a4dfbf1027e', 1, NULL, '2026-08-24 10:29:19', '2026-08-24 10:29:19', NULL),
(27, 'lamine-diatas@edg.com.gn', 'user', 'login', 'auth', 'account:27', '127.0.0.1', NULL, 'success', 152, '1d1fff3c-d170-44d8-a5b8-47b7749e455d', 1, NULL, '2026-08-24 10:29:43', '2026-08-24 10:29:43', NULL),
(27, 'lamine-diatas@edg.com.gn', 'user', 'logout', 'auth', 'account:27', '127.0.0.1', NULL, 'success', 153, '5af819b8-85e7-4a22-a907-89d5bf2a76fa', 1, NULL, '2026-08-24 10:30:23', '2026-08-24 10:30:23', NULL),
(28, 'lamine-diatas12@edg.com.gn', 'user', 'register', 'auth', 'account:28', '127.0.0.1', NULL, 'success', 154, '0208d241-ad79-465c-baaf-b89663da877c', 1, NULL, '2026-08-24 10:31:36', '2026-08-24 10:31:36', NULL),
(27, 'lamine-diatas@edg.com.gn', 'user', 'login', 'auth', 'account:27', '127.0.0.1', NULL, 'success', 155, '715dddb6-f849-4ce0-b61a-c519f2bb63bc', 1, NULL, '2026-08-24 10:31:55', '2026-08-24 10:31:55', NULL),
(27, 'lamine-diatas@edg.com.gn', 'user', 'logout', 'auth', 'account:27', '127.0.0.1', NULL, 'success', 156, '986b410d-c3f5-4367-ba6c-d33edab3c417', 1, NULL, '2026-08-24 10:32:16', '2026-08-24 10:32:16', NULL),
(NULL, 'nalo-diatas.diaby@edg.com.gn', 'unknown', 'login_needs_consent', 'auth', 'auth', '127.0.0.1', NULL, 'success', 157, '459ca51a-d6ae-491e-9f59-d9b9901c0c52', 1, NULL, '2026-08-24 10:36:09', '2026-08-24 10:36:09', NULL),
(NULL, 'nalo-diatas.diaby@edg.com.gn', 'unknown', 'login_needs_consent', 'auth', 'auth', '127.0.0.1', NULL, 'success', 158, '76a1c565-f3ba-4993-88e7-d6b6cba3a6f1', 1, NULL, '2026-08-24 10:36:26', '2026-08-24 10:36:26', NULL),
(29, 'nalo-diatas.diaby@edg.com.gn', 'user', 'consent_accept', 'auth', 'account:29', '127.0.0.1', NULL, 'success', 159, '07acb8c3-8000-4bab-ac2b-74bed0d0d37a', 1, NULL, '2026-08-24 10:37:30', '2026-08-24 10:37:30', NULL),
(29, 'nalo-diatas.diaby@edg.com.gn', 'user', 'logout', 'auth', 'account:29', '127.0.0.1', NULL, 'success', 160, '8b977c80-b3bf-40e0-8d41-b37a894b7944', 1, NULL, '2026-08-24 11:13:22', '2026-08-24 11:13:22', NULL),
(29, 'nalo-diatas.diaby@edg.com.gn', 'user', 'logout', 'auth', 'account:29', '127.0.0.1', NULL, 'success', 161, '8bd6a138-df4e-48aa-9f16-488c44749871', 1, NULL, '2026-08-24 11:13:29', '2026-08-24 11:13:29', NULL),
(30, 'nalo-diatas.diabyaaaa@edg.com.gn', 'user', 'register', 'auth', 'account:30', '127.0.0.1', NULL, 'success', 162, '56cb5c07-3b3c-4f3d-b372-b523df2bc9d9', 1, NULL, '2026-08-24 11:15:54', '2026-08-24 11:15:54', NULL),
(29, 'nalo-diatas.diaby@edg.com.gn', 'user', 'login', 'auth', 'account:29', '127.0.0.1', NULL, 'success', 163, '4767c7e9-66aa-40ce-9e18-f7d316915d42', 1, NULL, '2026-08-24 11:16:21', '2026-08-24 11:16:21', NULL),
(29, 'nalo-diatas.diaby@edg.com.gn', 'user', 'logout', 'auth', 'account:29', '127.0.0.1', NULL, 'success', 164, 'a0398ef4-5e17-4cb4-a1e3-f3b8af048c7a', 1, NULL, '2026-08-24 11:16:32', '2026-08-24 11:16:32', NULL),
(31, 'aminata@gmail.com', 'user', 'register', 'auth', 'account:31', '127.0.0.1', NULL, 'success', 165, '3aefae3f-8ab5-4127-819a-ae00c51b343b', 1, NULL, '2026-08-27 11:40:58', '2026-08-27 11:40:58', NULL),
(32, 'mohamed-tassilimy.diaby11@edg.com.gn', 'user', 'register', 'auth', 'account:32', '127.0.0.1', NULL, 'success', 166, 'b1145b1b-dd8e-4de0-bebb-f52141e4e630', 1, NULL, '2026-08-27 11:42:49', '2026-08-27 11:42:49', NULL),
(32, 'mohamed-tassilimy.diaby11@edg.com.gn', 'user', 'login', 'auth', 'account:32', '127.0.0.1', NULL, 'success', 167, '020768db-61a4-4c71-bb10-c99a0dfc6c51', 1, NULL, '2026-08-27 11:42:55', '2026-08-27 11:42:55', NULL),
(32, 'mohamed-tassilimy.diaby11@edg.com.gn', 'user', 'logout', 'auth', 'account:32', '127.0.0.1', NULL, 'success', 168, '61678869-deaf-4421-8546-0ae11333b274', 1, NULL, '2026-08-27 11:46:36', '2026-08-27 11:46:36', NULL),
(33, 'diatas02@edg.com.gn', 'user', 'register', 'auth', 'account:33', '127.0.0.1', NULL, 'success', 169, '2d2a8578-9c63-4c06-984d-0231ce6846c5', 1, NULL, '2026-08-27 11:48:32', '2026-08-27 11:48:32', NULL),
(33, 'diatas02@edg.com.gn', 'user', 'login', 'auth', 'account:33', '127.0.0.1', NULL, 'success', 170, '1319a8f7-c79d-4c3b-ab3a-6ea8bb3b070a', 1, NULL, '2026-08-27 11:48:36', '2026-08-27 11:48:36', NULL),
(33, 'diatas02@edg.com.gn', 'user', 'logout', 'auth', 'account:33', '127.0.0.1', NULL, 'success', 171, '3f1df4fd-1c1c-457e-bb42-e3d29d4fd0f0', 1, NULL, '2026-08-27 11:49:05', '2026-08-27 11:49:05', NULL),
(34, 'diatas2@gmail.com', 'user', 'register', 'auth', 'account:34', '127.0.0.1', NULL, 'success', 172, 'c080bc47-f13b-42ea-ad83-f155e3a481e9', 1, NULL, '2026-08-27 11:49:47', '2026-08-27 11:49:47', NULL),
(34, 'diatas2@gmail.com', 'user', 'login', 'auth', 'account:34', '127.0.0.1', NULL, 'success', 173, '0ce3b613-a256-4c73-b4a8-ab18159b6186', 1, NULL, '2026-08-27 11:49:52', '2026-08-27 11:49:52', NULL),
(34, 'diatas2@gmail.com', 'user', 'logout', 'auth', 'account:34', '127.0.0.1', NULL, 'success', 174, '25bb4b08-5f0d-463a-a1ba-3d6271c28d55', 1, NULL, '2026-08-27 11:50:46', '2026-08-27 11:50:46', NULL),
(NULL, 'oumou.kaba@edg.com.gn', 'unknown', 'login_failed', 'auth', 'auth', '127.0.0.1', NULL, 'error', 175, '51414e04-d5b9-459c-95a0-230aa8ed0eed', 1, NULL, '2026-08-27 11:51:13', '2026-08-27 11:51:13', NULL),
(NULL, 'oumou.kaba@edg.com.gn', 'unknown', 'login_failed', 'auth', 'auth', '127.0.0.1', NULL, 'error', 176, 'd77cdbc6-7045-4f38-928d-afa4832b23fa', 1, NULL, '2026-08-27 11:51:29', '2026-08-27 11:51:29', NULL),
(NULL, 'oumou.kaba@edg.com.gn', 'unknown', 'login_needs_consent', 'auth', 'auth', '127.0.0.1', NULL, 'success', 177, 'b02f7b7a-567d-4f03-ab7e-34842b5a862a', 1, NULL, '2026-08-27 11:52:52', '2026-08-27 11:52:52', NULL),
(35, 'oumou.kaba@edg.com.gn', 'user', 'consent_accept', 'auth', 'account:35', '127.0.0.1', NULL, 'success', 178, '7726dac2-53b9-44fd-b82b-8d0731781cb0', 1, NULL, '2026-08-27 11:53:11', '2026-08-27 11:53:11', NULL),
(35, 'oumou.kaba@edg.com.gn', 'user', 'logout', 'auth', 'account:35', '127.0.0.1', NULL, 'success', 179, '510c68f1-9446-44ab-bd36-ace0661b2364', 1, NULL, '2026-08-27 11:53:33', '2026-08-27 11:53:33', NULL),
(NULL, 'diatas2@gmail.com', 'unknown', 'login_failed', 'auth', 'auth', '127.0.0.1', NULL, 'error', 180, '7b542389-8a45-4c5b-a431-72e1ba465728', 1, NULL, '2026-08-27 11:53:59', '2026-08-27 11:53:59', NULL),
(34, 'diatas2@gmail.com', 'user', 'login', 'auth', 'account:34', '127.0.0.1', NULL, 'success', 181, 'a238c902-ff54-43e8-a671-bf1c31d24111', 1, NULL, '2026-08-27 11:54:20', '2026-08-27 11:54:20', NULL),
(34, 'diatas2@gmail.com', 'user', 'logout', 'auth', 'account:34', '127.0.0.1', NULL, 'success', 182, '989bddf4-b805-4e0b-a411-b89924b497af', 1, NULL, '2026-08-27 12:08:13', '2026-08-27 12:08:13', NULL),
(5, 'gaspardkamangoepogui96@gmail.com', 'user', 'login', 'auth', 'account:5', '127.0.0.1', NULL, 'success', 183, '9e820272-b712-45f0-8447-e1ec7bd73f25', 1, NULL, '2026-08-27 12:09:29', '2026-08-27 12:09:29', NULL),
(5, 'gaspardkamangoepogui96@gmail.com', 'user', 'logout', 'auth', 'account:5', '127.0.0.1', NULL, 'success', 184, '5f7a4f79-c8a7-4df8-8778-713aca08e3b7', 1, NULL, '2026-08-27 12:09:47', '2026-08-27 12:09:47', NULL),
(36, 'admin@gmail.com', 'admin', 'login', 'auth', 'account:36', '127.0.0.1', NULL, 'success', 185, '9b0bd877-afce-4bb7-a324-e810398130ee', 1, NULL, '2026-08-27 12:17:14', '2026-08-27 12:17:14', NULL),
(36, 'admin@gmail.com', 'admin', 'logout', 'auth', 'account:36', '127.0.0.1', NULL, 'success', 186, '686dee86-79de-4683-b3e1-c244e5a6f652', 1, NULL, '2026-08-27 12:18:38', '2026-08-27 12:18:38', NULL),
(34, 'diatas2@gmail.com', 'user', 'login', 'auth', 'account:34', '127.0.0.1', NULL, 'success', 187, '9a926e2f-55f2-4ad6-8ee6-884fa8612bb8', 1, NULL, '2026-08-27 12:19:35', '2026-08-27 12:19:35', NULL),
(34, 'diatas2@gmail.com', 'user', 'logout', 'auth', 'account:34', '127.0.0.1', NULL, 'success', 188, '96345764-8443-43b5-9f38-80e722daefbc', 1, NULL, '2026-08-27 12:23:12', '2026-08-27 12:23:12', NULL),
(36, 'admin@gmail.com', 'admin', 'login', 'auth', 'account:36', '127.0.0.1', NULL, 'success', 189, 'a7b54ffe-db21-4a2a-9dde-4a2d01c33544', 1, NULL, '2026-08-27 12:23:28', '2026-08-27 12:23:28', NULL),
(36, 'admin@gmail.com', 'admin', 'logout', 'auth', 'account:36', '127.0.0.1', NULL, 'success', 190, '933174cb-4b27-4605-9ca6-39164ce9cd8d', 1, NULL, '2026-08-27 12:30:05', '2026-08-27 12:30:05', NULL),
(37, 'testing1@gmail.com', 'user', 'register', 'auth', 'account:37', '127.0.0.1', NULL, 'success', 191, 'c81c1291-dd05-4b07-986c-d40d2804c3b8', 1, NULL, '2026-08-27 12:31:51', '2026-08-27 12:31:51', NULL),
(37, 'testing1@gmail.com', 'user', 'login', 'auth', 'account:37', '127.0.0.1', NULL, 'success', 192, 'aefb39d8-e241-422f-ba63-cd2bccff6ec7', 1, NULL, '2026-08-27 12:31:56', '2026-08-27 12:31:56', NULL),
(37, 'testing1@gmail.com', 'user', 'logout', 'auth', 'account:37', '127.0.0.1', NULL, 'success', 193, '6ab91b0b-f247-41ad-9120-75b8e089edcc', 1, NULL, '2026-08-27 12:32:07', '2026-08-27 12:32:07', NULL),
(38, 'testing2@gmail.com', 'user', 'register', 'auth', 'account:38', '127.0.0.1', NULL, 'success', 194, 'b301cb93-43c9-48ee-96ab-d32d8a07c39a', 1, NULL, '2026-08-27 12:32:54', '2026-08-27 12:32:54', NULL),
(38, 'testing2@gmail.com', 'user', 'login', 'auth', 'account:38', '127.0.0.1', NULL, 'success', 195, '86b81960-f858-4a70-b91c-0e4066c5e4c5', 1, NULL, '2026-08-27 12:32:59', '2026-08-27 12:32:59', NULL),
(38, 'testing2@gmail.com', 'user', 'logout', 'auth', 'account:38', '127.0.0.1', NULL, 'success', 196, '5230dabd-772a-451e-bf0f-9e1e94f7b7b1', 1, NULL, '2026-08-27 12:33:06', '2026-08-27 12:33:06', NULL),
(39, 'testing3@gmail.com', 'user', 'register', 'auth', 'account:39', '127.0.0.1', NULL, 'success', 197, '4dc51280-2522-4972-8e92-3dbbd85f02da', 1, NULL, '2026-08-27 12:33:49', '2026-08-27 12:33:49', NULL),
(39, 'testing3@gmail.com', 'user', 'login', 'auth', 'account:39', '127.0.0.1', NULL, 'success', 198, 'b4d9c097-9663-4245-87ee-23d5e6a05ca2', 1, NULL, '2026-08-27 12:33:54', '2026-08-27 12:33:54', NULL),
(39, 'testing3@gmail.com', 'user', 'logout', 'auth', 'account:39', '127.0.0.1', NULL, 'success', 199, 'b5f1738b-d756-489b-84db-d3fc250ad02d', 1, NULL, '2026-08-27 12:34:12', '2026-08-27 12:34:12', NULL),
(34, 'diatas2@gmail.com', 'user', 'login', 'auth', 'account:34', '127.0.0.1', NULL, 'success', 200, 'd0fa4636-cde9-4bac-9c0a-78b53d354573', 1, NULL, '2026-08-27 15:09:22', '2026-08-27 15:09:22', NULL),
(34, 'diatas2@gmail.com', 'user', 'logout', 'auth', 'account:34', '127.0.0.1', NULL, 'success', 201, '3eb1b74c-4f18-441e-a5e4-09fb587e870c', 1, NULL, '2026-08-27 15:37:03', '2026-08-27 15:37:03', NULL),
(34, 'diatas2@gmail.com', 'user', 'login', 'auth', 'account:34', '127.0.0.1', NULL, 'success', 202, 'e816d3ea-f1ca-4831-a200-7ea9f707cbb9', 1, NULL, '2026-08-27 15:37:26', '2026-08-27 15:37:26', NULL),
(34, 'diatas2@gmail.com', 'user', 'logout', 'auth', 'account:34', '127.0.0.1', NULL, 'success', 203, 'ea9edf85-06ec-4917-ba3d-6a9ef5af0256', 1, NULL, '2026-08-28 11:01:42', '2026-08-28 11:01:42', NULL),
(36, 'admin@gmail.com', 'admin', 'login', 'auth', 'account:36', '127.0.0.1', NULL, 'success', 204, '88364400-cc09-4349-97d5-097ba9ca786d', 1, NULL, '2026-08-28 11:04:34', '2026-08-28 11:04:34', NULL);

-- --------------------------------------------------------

--
-- Structure de la table `alembic_version`
--

DROP TABLE IF EXISTS `alembic_version`;
CREATE TABLE IF NOT EXISTS `alembic_version` (
  `version_num` varchar(32) COLLATE utf8mb4_unicode_ci NOT NULL,
  PRIMARY KEY (`version_num`)
) ENGINE=MyISAM DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Déchargement des données de la table `alembic_version`
--

INSERT INTO `alembic_version` (`version_num`) VALUES
('018');

-- --------------------------------------------------------

--
-- Structure de la table `announcement`
--

DROP TABLE IF EXISTS `announcement`;
CREATE TABLE IF NOT EXISTS `announcement` (
  `announcement_category_id` int NOT NULL,
  `announcement_priority_id` int NOT NULL,
  `announcement_status_id` int NOT NULL,
  `author_id` int NOT NULL,
  `title` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `audience` enum('internal','external','all','unit') COLLATE utf8mb4_unicode_ci NOT NULL DEFAULT 'internal',
  `attachment_name` varchar(255) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `visibility` enum('public','admin_only') COLLATE utf8mb4_unicode_ci NOT NULL,
  `published_at` datetime NOT NULL DEFAULT (now()),
  `expires_at` datetime DEFAULT NULL,
  `closed_at` datetime DEFAULT NULL,
  `id` int NOT NULL AUTO_INCREMENT,
  `uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` tinyint(1) NOT NULL,
  `infos` json DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uuid` (`uuid`),
  KEY `author_id` (`author_id`),
  KEY `idx_ann_prio_id` (`announcement_priority_id`),
  KEY `idx_ann_status` (`status`,`deleted_at`),
  KEY `idx_ann_cat_id` (`announcement_category_id`),
  KEY `idx_ann_status_id` (`announcement_status_id`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Structure de la table `announcement_category`
--

DROP TABLE IF EXISTS `announcement_category`;
CREATE TABLE IF NOT EXISTS `announcement_category` (
  `code` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `label` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `sort_order` smallint NOT NULL,
  `is_builtin` tinyint(1) NOT NULL,
  `id` int NOT NULL AUTO_INCREMENT,
  `uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` tinyint(1) NOT NULL,
  `infos` json DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `code` (`code`),
  UNIQUE KEY `uuid` (`uuid`),
  KEY `idx_ac_status` (`status`,`deleted_at`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Déchargement des données de la table `announcement_category`
--

INSERT INTO `announcement_category` (`code`, `label`, `sort_order`, `is_builtin`, `id`, `uuid`, `status`, `infos`, `created_at`, `updated_at`, `deleted_at`) VALUES
('general', 'Général', 1, 1, 1, 'db2aa753-824f-4e4a-9a53-874403a15094', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('maintenance', 'Maintenance', 2, 1, 2, '07a19379-db95-4f40-a80c-b407b84039fb', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('incident', 'Incident', 3, 1, 3, '0c762b7e-79e6-4316-8586-d4591f6e354a', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('information', 'Information', 4, 1, 4, 'fb4da972-e591-4b6e-ae8b-900570a98a33', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('urgence', 'Urgence', 5, 1, 5, '0441123d-e16d-41ae-891c-f3ddd451250d', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL);

-- --------------------------------------------------------

--
-- Structure de la table `announcement_priority`
--

DROP TABLE IF EXISTS `announcement_priority`;
CREATE TABLE IF NOT EXISTS `announcement_priority` (
  `code` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `label` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `sort_order` smallint NOT NULL,
  `is_builtin` tinyint(1) NOT NULL,
  `id` int NOT NULL AUTO_INCREMENT,
  `uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` tinyint(1) NOT NULL,
  `infos` json DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `code` (`code`),
  UNIQUE KEY `uuid` (`uuid`),
  KEY `idx_ap_order` (`sort_order`),
  KEY `idx_ap_status` (`status`,`deleted_at`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Déchargement des données de la table `announcement_priority`
--

INSERT INTO `announcement_priority` (`code`, `label`, `sort_order`, `is_builtin`, `id`, `uuid`, `status`, `infos`, `created_at`, `updated_at`, `deleted_at`) VALUES
('low', 'Basse', 1, 1, 1, 'a7602bf2-1a17-4a3c-a80a-9b2f075f4d14', 1, NULL, '2026-06-25 19:11:44', '2026-08-15 15:03:55', NULL),
('medium', 'Moyenne', 2, 1, 2, '0a6d2341-5769-45d9-bdba-9100863f4c2b', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('high', 'Haute', 3, 1, 3, '75ae1970-cf5d-4bef-82c9-3b976b1711d5', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('critical', 'Critique', 4, 1, 4, '752263d3-6d31-4a3a-8cad-0b62583b704c', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL);

-- --------------------------------------------------------

--
-- Structure de la table `announcement_status`
--

DROP TABLE IF EXISTS `announcement_status`;
CREATE TABLE IF NOT EXISTS `announcement_status` (
  `code` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `label` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `sort_order` smallint NOT NULL,
  `is_builtin` tinyint(1) NOT NULL,
  `id` int NOT NULL AUTO_INCREMENT,
  `uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` tinyint(1) NOT NULL,
  `infos` json DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `code` (`code`),
  UNIQUE KEY `uuid` (`uuid`),
  KEY `idx_anst_status` (`status`,`deleted_at`)
) ENGINE=InnoDB AUTO_INCREMENT=8 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Déchargement des données de la table `announcement_status`
--

INSERT INTO `announcement_status` (`code`, `label`, `sort_order`, `is_builtin`, `id`, `uuid`, `status`, `infos`, `created_at`, `updated_at`, `deleted_at`) VALUES
('draft', 'Brouillon', 1, 1, 1, '70b7ee71-db53-469e-9c20-27b4f8870456', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('scheduled', 'Planifiée', 2, 1, 2, '8c97933c-5c67-4cdf-bdb9-b15febdb215a', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('published', 'Publiée', 3, 1, 3, 'c90a4fcb-50b3-4f4d-b50a-7fbf0e0df81e', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('expired', 'Expirée', 4, 1, 4, '141065ee-b21b-45d2-8747-07e6af88fa71', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('closed', 'Clôturée', 5, 1, 5, '12560ba1-d51b-4924-9698-8ec05b380c58', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('cancelled', 'Annulée', 6, 1, 6, '986fc13e-b4f5-4a65-98ab-19a61092cae3', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL);

-- --------------------------------------------------------

--
-- Structure de la table `announcement_target_role`
--

DROP TABLE IF EXISTS `announcement_target_role`;
CREATE TABLE IF NOT EXISTS `announcement_target_role` (
  `announcement_id` int NOT NULL,
  `role` enum('public','user','agent','chief','director','dg','admin') COLLATE utf8mb4_unicode_ci NOT NULL,
  `id` int NOT NULL AUTO_INCREMENT,
  `uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` tinyint(1) NOT NULL,
  `infos` json DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_atrole_ann_role` (`announcement_id`,`role`),
  UNIQUE KEY `uuid` (`uuid`),
  KEY `idx_atrole_status` (`status`,`deleted_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Structure de la table `appreciation`
--

DROP TABLE IF EXISTS `appreciation`;
CREATE TABLE IF NOT EXISTS `appreciation` (
  `request_id` int NOT NULL,
  `rating` smallint NOT NULL,
  `comment` text COLLATE utf8mb4_unicode_ci,
  `resolved_confirmed` int NOT NULL,
  `is_modified` int NOT NULL,
  `author_type` enum('internal','external') COLLATE utf8mb4_unicode_ci NOT NULL,
  `id` int NOT NULL AUTO_INCREMENT,
  `uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` tinyint(1) NOT NULL,
  `infos` json DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_appr_req` (`request_id`),
  UNIQUE KEY `request_id` (`request_id`),
  UNIQUE KEY `uuid` (`uuid`),
  KEY `idx_appr_status` (`status`,`deleted_at`),
  KEY `idx_appr_rating` (`rating`)
) ;

-- --------------------------------------------------------

--
-- Structure de la table `attachment`
--

DROP TABLE IF EXISTS `attachment`;
CREATE TABLE IF NOT EXISTS `attachment` (
  `request_id` int NOT NULL,
  `uploader_id` int DEFAULT NULL,
  `filename` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL,
  `storage_path` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `mime_type` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `size_bytes` int NOT NULL,
  `clamav_clean` tinyint(1) DEFAULT NULL,
  `scan_status` enum('pending_scan','clean','quarantined','deleted') COLLATE utf8mb4_unicode_ci NOT NULL,
  `id` int NOT NULL AUTO_INCREMENT,
  `uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` tinyint(1) NOT NULL,
  `infos` json DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uuid` (`uuid`),
  KEY `uploader_id` (`uploader_id`),
  KEY `idx_att_status` (`status`,`deleted_at`),
  KEY `idx_att_req` (`request_id`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Déchargement des données de la table `attachment`
--

INSERT INTO `attachment` (`request_id`, `uploader_id`, `filename`, `storage_path`, `mime_type`, `size_bytes`, `clamav_clean`, `scan_status`, `id`, `uuid`, `status`, `infos`, `created_at`, `updated_at`, `deleted_at`) VALUES
(3, 2, 'edg recrutement.jpg', 'requests/3/fab522b4_edg_recrutement.jpg', 'image/jpeg', 66482, NULL, 'clean', 1, 'ac57ec60-9b81-4e0f-a1e7-11a70c23f766', 1, NULL, '2026-08-13 11:03:43', '2026-08-13 11:03:43', NULL),
(5, 7, 'WhatsApp Image 2026-08-07 at 1.46.51 PM.jpeg', 'requests/5/96ccbae6_WhatsApp_Image_2026-08-07_at_1.46.51_PM.jpeg', 'image/jpeg', 65439, NULL, 'clean', 2, '6d0fc16e-251f-4539-87ae-f7fa5cc1a79d', 1, NULL, '2026-08-14 11:43:30', '2026-08-14 11:43:30', NULL),
(9, 7, 'edg recrutement.jpg', 'requests/9/975e2876_edg_recrutement.jpg', 'image/jpeg', 66482, NULL, 'clean', 3, '8f2cdc49-5c8a-4a8e-9a94-88f674565d61', 1, NULL, '2026-08-19 09:41:14', '2026-08-19 09:41:14', NULL),
(10, 34, 'Facture Master BS.pdf', 'requests/10/46f00d3e_Facture_Master_BS.pdf', 'application/pdf', 664407, NULL, 'clean', 4, '6323e633-8b4b-4535-8780-48e5cc7fd396', 1, NULL, '2026-08-27 12:05:20', '2026-08-27 12:05:20', NULL),
(11, 34, 'edg recrutement.jpg', 'requests/11/7c451265_edg_recrutement.jpg', 'image/jpeg', 66482, NULL, 'clean', 5, '5d774991-127d-4871-8edb-89aadf06d7fe', 1, NULL, '2026-08-27 15:10:34', '2026-08-27 15:10:34', NULL);

-- --------------------------------------------------------

--
-- Structure de la table `communication_setting`
--

DROP TABLE IF EXISTS `communication_setting`;
CREATE TABLE IF NOT EXISTS `communication_setting` (
  `updated_by` int DEFAULT NULL,
  `internal_notif_on` tinyint(1) NOT NULL,
  `email_on` tinyint(1) NOT NULL,
  `sms_on` tinyint(1) NOT NULL,
  `banner_on` tinyint(1) NOT NULL,
  `whatsapp_on` tinyint(1) NOT NULL,
  `push_mobile_on` tinyint(1) NOT NULL,
  `sender_email` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `sender_sms` varchar(11) COLLATE utf8mb4_unicode_ci NOT NULL,
  `reply_to` varchar(255) COLLATE utf8mb4_unicode_ci NOT NULL,
  `id` int NOT NULL AUTO_INCREMENT,
  `uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` tinyint(1) NOT NULL,
  `infos` json DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uuid` (`uuid`),
  KEY `updated_by` (`updated_by`),
  KEY `idx_comms_status` (`status`,`deleted_at`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Déchargement des données de la table `communication_setting`
--

INSERT INTO `communication_setting` (`updated_by`, `internal_notif_on`, `email_on`, `sms_on`, `banner_on`, `whatsapp_on`, `push_mobile_on`, `sender_email`, `sender_sms`, `reply_to`, `id`, `uuid`, `status`, `infos`, `created_at`, `updated_at`, `deleted_at`) VALUES
(NULL, 1, 1, 1, 1, 0, 0, 'noreply@edg.gn', 'EDG', 'support@edg.gn', 1, '69481a6f-e2c3-4395-82dd-9398bb224241', 1, NULL, '2026-08-12 08:54:29', '2026-08-12 08:54:29', NULL);

-- --------------------------------------------------------

--
-- Structure de la table `knowledge_article`
--

DROP TABLE IF EXISTS `knowledge_article`;
CREATE TABLE IF NOT EXISTS `knowledge_article` (
  `author_id` int DEFAULT NULL,
  `title` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL,
  `excerpt` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `body` longtext COLLATE utf8mb4_unicode_ci NOT NULL,
  `category` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `read_time` smallint NOT NULL,
  `author` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `is_published` tinyint(1) NOT NULL,
  `is_archived` tinyint(1) NOT NULL,
  `tags` json DEFAULT NULL,
  `published_at` datetime DEFAULT NULL,
  `id` int NOT NULL AUTO_INCREMENT,
  `uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` tinyint(1) NOT NULL,
  `infos` json DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uuid` (`uuid`),
  KEY `author_id` (`author_id`),
  KEY `idx_kb_status` (`status`,`deleted_at`),
  KEY `idx_kb_cat` (`category`),
  KEY `idx_kb_pub` (`is_published`)
) ENGINE=InnoDB AUTO_INCREMENT=2 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Déchargement des données de la table `knowledge_article`
--

INSERT INTO `knowledge_article` (`author_id`, `title`, `excerpt`, `body`, `category`, `read_time`, `author`, `is_published`, `is_archived`, `tags`, `published_at`, `id`, `uuid`, `status`, `infos`, `created_at`, `updated_at`, `deleted_at`) VALUES
(NULL, 'T1', ' KJFKDJFKDJFKJ KJFKDJFKDJFKJ KJFKDJFKDJFKJ KJFKDJFKDJFKJ KJFKDJFKDJFKJ KJFKDJFKDJFKJKJFKDJFKDJFKJKJFKDJFKDJFKJV VKJFKDJFKDJFKJKJFKDJFKDJFKJ', 'Lorme Fais maintenant une vérification fonctionnelle finale de l\'export Admin sans modifier l\'architecture actuelle. Génère réellement des exports .xlsx à partir de plusieurs demandes représentatives et inspecte leur contenu feuille par feuille. Vérifie particulièrement que la Synthèse contient toutes les informations essentielles de la demande, que les Acteurs affichent clairement identité + rôle + actions, que l\'Historique restitue fidèlement le parcours chronologique, que les Conversations contiennent auteur + visibilité + message + date, que les Affectations/Transmissions sont correctement représentées, et que les informations d\'annulation, résolution, fermeture et escalade apparaissent lorsqu\'elles existent. Vérifie également qu\'aucune donnée SLA/délai n\'est présente, qu\'aucune donnée d\'une autre demande ne fuit dans l\'export et qu\'un export ne provoque aucun effet métier. Ne modifie le code que si tu identifies un véritable problème fonctionnel. À la fin, donne-moi un rapport précis des vérifications effectuées et des éventuelles corrections.', 'pannes', 1, 'GASPARD KAMAN', 0, 0, '[\"T1\", \"T2\"]', '2026-08-28 11:10:41', 1, '1408095f-b9e5-497c-a05c-0698f0babaaa', 1, 'null', '2026-08-15 15:37:09', '2026-08-28 11:11:04', NULL);

-- --------------------------------------------------------

--
-- Structure de la table `knowledge_category`
--

DROP TABLE IF EXISTS `knowledge_category`;
CREATE TABLE IF NOT EXISTS `knowledge_category` (
  `code` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `label` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `sort_order` smallint NOT NULL,
  `is_builtin` tinyint(1) NOT NULL,
  `id` int NOT NULL AUTO_INCREMENT,
  `uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` tinyint(1) NOT NULL,
  `infos` json DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `code` (`code`),
  UNIQUE KEY `uuid` (`uuid`),
  KEY `idx_kc_status` (`status`,`deleted_at`),
  KEY `idx_kc_order` (`sort_order`)
) ENGINE=InnoDB AUTO_INCREMENT=7 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Déchargement des données de la table `knowledge_category`
--

INSERT INTO `knowledge_category` (`code`, `label`, `sort_order`, `is_builtin`, `id`, `uuid`, `status`, `infos`, `created_at`, `updated_at`, `deleted_at`) VALUES
('faq', 'FAQ', 1, 1, 1, 'ac35e655-4b58-4fc3-95fa-e87d06e5f752', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('procedure', 'Procédures internes', 2, 1, 2, 'f280c05f-9f13-44c2-9a49-0747b449ae53', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('technique', 'Documentation technique', 3, 1, 3, '36f2f1e1-f55f-4a42-b305-b94ab8daa429', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('reglementation', 'Réglementation', 4, 1, 4, '06a2c60c-fa1c-4d35-b02b-67b980f0112c', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('formation', 'Formation', 5, 1, 5, '9610ee81-bcc9-42a8-87ca-cdc83a074e91', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL);

-- --------------------------------------------------------

--
-- Structure de la table `notification`
--

DROP TABLE IF EXISTS `notification`;
CREATE TABLE IF NOT EXISTS `notification` (
  `recipient_id` int NOT NULL,
  `request_id` int DEFAULT NULL,
  `type` enum('info','success','warning') COLLATE utf8mb4_unicode_ci NOT NULL,
  `channel` enum('in_app','sms','email') COLLATE utf8mb4_unicode_ci NOT NULL,
  `title` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `body` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `action_label` varchar(100) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `action_url` text COLLATE utf8mb4_unicode_ci,
  `is_read` tinyint(1) NOT NULL,
  `visibility` enum('public','admin_only') COLLATE utf8mb4_unicode_ci NOT NULL,
  `read_at` datetime DEFAULT NULL,
  `id` int NOT NULL AUTO_INCREMENT,
  `uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` tinyint(1) NOT NULL,
  `infos` json DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uuid` (`uuid`),
  KEY `request_id` (`request_id`),
  KEY `idx_notif_recip` (`recipient_id`),
  KEY `idx_notif_status` (`status`,`deleted_at`),
  KEY `idx_notif_unread` (`recipient_id`,`is_read`)
) ENGINE=InnoDB AUTO_INCREMENT=38 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Déchargement des données de la table `notification`
--

INSERT INTO `notification` (`recipient_id`, `request_id`, `type`, `channel`, `title`, `body`, `action_label`, `action_url`, `is_read`, `visibility`, `read_at`, `id`, `uuid`, `status`, `infos`, `created_at`, `updated_at`, `deleted_at`) VALUES
(2, 1, 'success', 'in_app', 'Ticket créé', 'Votre ticket DSI-EDX-SED-1007490260812-001 a été créé avec succès et placé dans la File d\'attente.', 'Voir le ticket', '/app/requests/1', 1, 'public', '2026-08-12 10:30:36', 1, '59c1b749-885f-4a4e-b3c4-97e1c69d9531', 1, NULL, '2026-08-12 10:07:50', '2026-08-12 10:30:36', NULL),
(2, 1, 'info', 'in_app', 'Ticket en cours de traitement', 'Votre ticket DSI-EDX-SED-1007490260812-001 est maintenant en cours de traitement.', 'Voir le ticket', '/app/requests/1', 1, 'public', '2026-08-13 10:20:52', 2, '0e6877bd-b689-4e64-b8e5-4c1e6e36e782', 1, NULL, '2026-08-12 11:35:42', '2026-08-13 10:20:52', NULL),
(7, 1, 'info', 'in_app', 'Ticket assigné', 'Le ticket DSI-EDX-SED-1007490260812-001 vous a été attribué. Vous pouvez commencer votre intervention.', 'Voir le ticket', '/app/requests/1', 1, 'public', '2026-08-12 11:49:33', 3, '857af46b-55c0-4546-a70f-6a745e753188', 1, NULL, '2026-08-12 11:35:42', '2026-08-14 12:02:23', '2026-08-14 12:02:23'),
(6, 1, 'info', 'in_app', 'Ticket transmis', 'Jams jamsatou1 vous a transmis le ticket DSI-EDX-SED-1007490260812-001. Consultez le travail déjà effectué et poursuivez le traitement. Motif : ttttttttttttttttteee', 'Voir le ticket', '/app/requests/1', 0, 'public', NULL, 4, 'b7215e48-3f14-4f43-96fe-97d91abefbea', 1, NULL, '2026-08-12 12:56:29', '2026-08-12 12:56:29', NULL),
(7, 1, 'info', 'in_app', 'Ticket transmis', 'Ticket DSI-EDX-SED-1007490260812-001 transmis à AMADOU TOURE.', 'Voir le ticket', '/app/requests/1', 1, 'public', '2026-08-13 11:05:43', 5, 'c0406b41-c02e-4512-aa9c-57dcb43cf9a9', 1, NULL, '2026-08-12 12:56:29', '2026-08-14 12:02:15', '2026-08-14 12:02:16'),
(5, 2, 'success', 'in_app', 'Ticket créé', 'Votre ticket GEN-GEN-UNK-1737030260812-001 a été créé avec succès et placé dans la File d\'attente.', 'Voir le ticket', '/app/requests/2', 1, 'public', '2026-08-13 09:49:45', 6, '59dba8b6-26a0-4bb1-93ad-dc55b3e6b4bf', 1, NULL, '2026-08-12 17:37:03', '2026-08-13 09:49:44', NULL),
(5, 2, 'warning', 'in_app', 'Ticket annulé', 'Votre ticket GEN-GEN-UNK-1737030260812-001 a été annulé : mon problème est resolue correctement', 'Voir le ticket', '/app/requests/2', 1, 'public', '2026-08-13 09:49:53', 7, 'b846b392-4174-44a5-aded-338315ec6808', 1, NULL, '2026-08-13 09:49:01', '2026-08-13 09:49:52', NULL),
(2, 1, 'warning', 'in_app', 'Ticket annulé', 'Votre ticket DSI-EDX-SED-1007490260812-001 a été annulé : mon problème est resolut', 'Voir le ticket', '/app/requests/1', 1, 'public', '2026-08-13 10:22:34', 8, '18f02b1d-4a13-435d-a600-f924e2489e4d', 1, NULL, '2026-08-13 10:22:17', '2026-08-13 10:22:33', NULL),
(6, 1, 'warning', 'in_app', 'Ticket annulé', 'Le ticket DSI-EDX-SED-1007490260812-001 qui vous était assigné a été annulé : mon problème est resolut. Vous ne devez plus poursuivre le traitement.', 'Voir le ticket', '/app/requests/1', 0, 'public', NULL, 9, '25a54015-dd4f-4047-b194-0aaca7d4e312', 1, NULL, '2026-08-13 10:22:17', '2026-08-13 10:22:17', NULL),
(2, 3, 'success', 'in_app', 'Ticket créé', 'Votre ticket DSI-EDX-SED-1103350260813-001 a été créé avec succès et placé dans la File d\'attente.', 'Voir le ticket', '/app/requests/3', 0, 'public', NULL, 10, '55f53bd5-6bbd-4511-b4c3-50b850f0a49d', 1, NULL, '2026-08-13 11:03:36', '2026-08-13 11:03:36', NULL),
(2, 3, 'info', 'in_app', 'Ticket en cours de traitement', 'Votre ticket DSI-EDX-SED-1103350260813-001 est maintenant en cours de traitement.', 'Voir le ticket', '/app/requests/3', 0, 'public', NULL, 11, 'bcbe8231-e271-4ffe-8f52-38ff1a3522d6', 1, NULL, '2026-08-13 11:06:55', '2026-08-13 11:06:55', NULL),
(7, 3, 'info', 'in_app', 'Ticket assigné', 'Le ticket DSI-EDX-SED-1103350260813-001 vous a été attribué. Vous pouvez commencer votre intervention.', 'Voir le ticket', '/app/requests/3', 1, 'public', '2026-08-14 11:11:28', 12, '30d04d5b-64ea-42e2-9c68-cc2faf33e05f', 1, NULL, '2026-08-13 11:06:55', '2026-08-14 12:02:17', '2026-08-14 12:02:17'),
(7, NULL, 'info', 'in_app', 'TEST unread bug', 'test', NULL, NULL, 1, 'public', '2026-08-14 11:07:00', 13, 'e17920c7-ed0f-493e-8f58-3c447e646c9b', 1, NULL, '2026-08-13 11:51:13', '2026-08-14 11:07:02', '2026-08-14 11:07:03'),
(2, 3, 'info', 'in_app', 'Nouveau message sur votre ticket', 'L\'intervenant a ajouté un message sur votre ticket DSI-EDX-SED-1103350260813-001.', 'Voir le ticket', '/app/requests/3', 0, 'public', NULL, 14, '58b23b3d-2bfe-4128-9a44-36bd167919f9', 1, NULL, '2026-08-13 12:29:18', '2026-08-13 12:29:18', NULL),
(2, 3, 'warning', 'in_app', 'Information complémentaire requise', 'Un agent attend votre retour sur le ticket DSI-EDX-SED-1103350260813-001.', 'Voir le ticket', '/app/requests/3', 0, 'public', NULL, 15, '6a9af31b-7df2-4109-8f64-a09ea8ae9704', 1, NULL, '2026-08-13 12:29:23', '2026-08-13 12:29:23', NULL),
(2, 3, 'info', 'in_app', 'Ticket en cours de traitement', 'Votre ticket DSI-EDX-SED-1103350260813-001 est maintenant en cours de traitement.', 'Voir le ticket', '/app/requests/3', 0, 'public', NULL, 16, '230e6784-6d59-4010-bc16-bab5bf2cb933', 1, NULL, '2026-08-13 12:31:02', '2026-08-13 12:31:02', NULL),
(2, 3, 'info', 'in_app', 'Nouveau message sur votre ticket', 'L\'intervenant a ajouté un message sur votre ticket DSI-EDX-SED-1103350260813-001.', 'Voir le ticket', '/app/requests/3', 1, 'public', '2026-08-13 16:12:01', 17, 'd275f953-a60e-4fdd-93cf-7504f65e2531', 1, NULL, '2026-08-13 16:10:01', '2026-08-13 16:12:00', NULL),
(7, 4, 'success', 'in_app', 'Ticket créé', 'Votre ticket DSI-EDX-SED-1105440260814-001 a été créé avec succès et placé dans la File d\'attente.', 'Voir le ticket', '/app/requests/4', 1, 'public', '2026-08-14 11:10:36', 18, '3caf8dee-1095-46b8-b34e-9ed81fd8c618', 1, NULL, '2026-08-14 11:05:44', '2026-08-14 12:02:18', '2026-08-14 12:02:19'),
(7, 4, 'warning', 'in_app', 'Ticket annulé', 'Votre ticket DSI-EDX-SED-1105440260814-001 a été annulé : je suis deja satisfait', 'Voir le ticket', '/app/requests/4', 1, 'public', '2026-08-14 11:41:20', 19, 'dc26534a-2f46-48b0-bfc4-f44e95c7b7c5', 1, NULL, '2026-08-14 11:13:33', '2026-08-14 12:02:11', '2026-08-14 12:02:11'),
(5, NULL, 'info', 'in_app', 'Test verification email a jour', 'Ceci est un test pour verifier que la notification part bien vers le nouvel email.', NULL, NULL, 0, 'public', NULL, 20, '9b8a23c9-c0d8-4711-860c-5ba207eabbaf', 1, NULL, '2026-08-14 11:18:07', '2026-08-14 11:18:07', NULL),
(5, NULL, 'info', 'in_app', 'Test verification email a jour', 'Verification que la notification part vers le nouvel email.', NULL, NULL, 0, 'public', NULL, 21, '0106c8a7-9b0a-4eee-86c0-d6d6bd582737', 1, NULL, '2026-08-14 11:19:32', '2026-08-14 11:19:32', NULL),
(7, 5, 'success', 'in_app', 'Ticket créé', 'Votre ticket DSI-EDX-SED-1143260260814-001 a été créé avec succès et placé dans la File d\'attente.', 'Voir le ticket', '/app/requests/5', 0, 'public', NULL, 22, '8c0b1077-446a-4995-ac0e-d4b4cbae6ba5', 1, NULL, '2026-08-14 11:43:26', '2026-08-14 12:02:11', '2026-08-14 12:02:12'),
(7, 6, 'success', 'in_app', 'Ticket créé', 'Votre ticket DSI-EDX-SED-1328430260814-001 a été créé avec succès et placé dans la File d\'attente.', 'Voir le ticket', '/app/requests/6', 1, 'public', '2026-08-17 16:19:16', 23, 'f10f8320-5e42-47a2-82f6-48b02f79b623', 1, NULL, '2026-08-14 13:28:44', '2026-08-17 16:21:31', '2026-08-17 16:21:31'),
(7, 6, 'info', 'in_app', 'Ticket en cours de traitement', 'Votre ticket DSI-EDX-SED-1328430260814-001 est maintenant en cours de traitement.', 'Voir le ticket', '/app/requests/6', 1, 'public', '2026-08-17 16:19:09', 24, 'c2360cf5-ac02-4f61-86d4-e3b958d8286d', 1, NULL, '2026-08-15 11:44:02', '2026-08-17 16:21:33', '2026-08-17 16:21:34'),
(2, 6, 'info', 'in_app', 'Ticket assigné', 'Le ticket DSI-EDX-SED-1328430260814-001 vous a été attribué. Vous pouvez commencer votre intervention.', 'Voir le ticket', '/app/requests/6', 1, 'public', '2026-08-15 14:51:55', 25, 'c9da6e89-0d95-4123-8cc2-9618c1c44a13', 1, NULL, '2026-08-15 11:44:02', '2026-08-15 14:51:55', NULL),
(8, 7, 'success', 'in_app', 'Ticket créé', 'Votre ticket DSI-EDX-SED-1205150260815-001 a été créé avec succès et placé dans la File d\'attente.', 'Voir le ticket', '/app/requests/7', 0, 'public', NULL, 26, '70f30e19-a43c-4c33-9c85-ae52da61ad6a', 1, NULL, '2026-08-15 12:05:16', '2026-08-15 12:05:16', NULL),
(8, 8, 'success', 'in_app', 'Ticket créé', 'Votre ticket DSI-EDX-SED-1207430260815-001 a été créé avec succès et placé dans la File d\'attente.', 'Voir le ticket', '/app/requests/8', 0, 'public', NULL, 27, '23c21d33-ae3f-4d3b-84e5-f4c8a9642baf', 1, NULL, '2026-08-15 12:07:43', '2026-08-15 12:07:43', NULL),
(8, 8, 'warning', 'in_app', 'Ticket annulé', 'Votre ticket DSI-EDX-SED-1207430260815-001 a été annulé : merci, j\'ai deja trouvé solution à mon problème', 'Voir le ticket', '/app/requests/8', 0, 'public', NULL, 28, '195ff26a-ac88-47b4-a5ea-ba45f8d651ed', 1, NULL, '2026-08-15 12:10:39', '2026-08-15 13:17:22', '2026-08-15 13:17:23'),
(7, 9, 'success', 'in_app', 'Ticket créé', 'Votre ticket DSI-EDX-SED-0941090260819-001 a été créé avec succès et placé dans la File d\'attente.', 'Voir le ticket', '/app/requests/9', 0, 'public', NULL, 29, '439059ef-7150-4473-94d2-932a42b0fd9c', 1, NULL, '2026-08-19 09:41:10', '2026-08-19 09:41:10', NULL),
(7, 9, 'info', 'in_app', 'Ticket en cours de traitement', 'Votre ticket DSI-EDX-SED-0941090260819-001 est maintenant en cours de traitement.', 'Voir le ticket', '/app/requests/9', 0, 'public', NULL, 30, '2650f8a6-612b-490e-bd0d-2205c9c06dbb', 1, NULL, '2026-08-19 10:08:48', '2026-08-19 10:08:48', NULL),
(2, 9, 'info', 'in_app', 'Ticket assigné', 'Le ticket DSI-EDX-SED-0941090260819-001 vous a été attribué. Vous pouvez commencer votre intervention.', 'Voir le ticket', '/app/requests/9', 0, 'public', NULL, 31, '77e7eb9e-8bbf-4cc7-a6ad-4a7b574412cd', 1, NULL, '2026-08-19 10:08:48', '2026-08-19 10:08:48', NULL),
(6, 9, 'info', 'in_app', 'Ticket transmis', 'GASPARD GOEPOGUI vous a transmis le ticket DSI-EDX-SED-0941090260819-001. Consultez le travail déjà effectué et poursuivez le traitement. Motif : on doit changer le système de charge', 'Voir le ticket', '/app/requests/9', 0, 'public', NULL, 32, 'f467454e-2c72-4ef9-bc3e-948f1073b638', 1, NULL, '2026-08-19 10:12:36', '2026-08-19 10:12:36', NULL),
(2, 9, 'info', 'in_app', 'Ticket transmis', 'Ticket DSI-EDX-SED-0941090260819-001 transmis à AMADOU TOURE.', 'Voir le ticket', '/app/requests/9', 0, 'public', NULL, 33, '3658ae01-dd15-4626-a004-8a5bac91f3ac', 1, NULL, '2026-08-19 10:12:37', '2026-08-19 10:12:37', NULL),
(34, 10, 'success', 'in_app', 'Ticket créé', 'Votre ticket GEN-GEN-UNK-1205150260827-001 a été créé avec succès et placé dans la File d\'attente.', 'Voir le ticket', '/app/requests/10', 1, 'public', '2026-08-27 12:07:31', 34, '15e45281-9cbe-4eda-b7ff-4fb0c982ce82', 1, NULL, '2026-08-27 12:05:16', '2026-08-27 12:07:30', NULL),
(34, 10, 'info', 'in_app', 'Ticket en cours de traitement', 'Votre ticket GEN-GEN-UNK-1205150260827-001 est maintenant en cours de traitement.', 'Voir le ticket', '/app/requests/10', 1, 'public', '2026-08-27 15:41:33', 35, '0c3d98b3-2b52-45c9-8a52-e337cf75f9b0', 1, NULL, '2026-08-27 12:24:21', '2026-08-27 15:41:32', NULL),
(36, 10, 'info', 'in_app', 'Ticket assigné', 'Le ticket GEN-GEN-UNK-1205150260827-001 vous a été attribué. Vous pouvez commencer votre intervention.', 'Voir le ticket', '/app/requests/10', 1, 'public', '2026-08-27 12:24:48', 36, '93168251-8252-49fd-ad91-5aaa19d6525b', 1, NULL, '2026-08-27 12:24:21', '2026-08-27 12:24:48', NULL),
(34, 11, 'success', 'in_app', 'Ticket créé', 'Votre ticket EDG-26-00001 a été créé avec succès et placé dans la File d\'attente.', 'Voir le ticket', '/app/requests/11', 1, 'public', '2026-08-27 15:41:59', 37, 'b3efa1d5-e42b-45a2-b117-50d8d25d4ea0', 1, NULL, '2026-08-27 15:10:29', '2026-08-27 15:41:59', NULL);

-- --------------------------------------------------------

--
-- Structure de la table `organigram`
--

DROP TABLE IF EXISTS `organigram`;
CREATE TABLE IF NOT EXISTS `organigram` (
  `unity_id` int NOT NULL,
  `parent_id` int DEFAULT NULL,
  `id` int NOT NULL AUTO_INCREMENT,
  `uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` tinyint(1) NOT NULL,
  `infos` json DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uuid` (`uuid`),
  KEY `idx_org_status` (`status`,`deleted_at`),
  KEY `idx_org_unity` (`unity_id`),
  KEY `idx_org_parent` (`parent_id`)
) ENGINE=InnoDB AUTO_INCREMENT=45 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Déchargement des données de la table `organigram`
--

INSERT INTO `organigram` (`unity_id`, `parent_id`, `id`, `uuid`, `status`, `infos`, `created_at`, `updated_at`, `deleted_at`) VALUES
(1, NULL, 1, 'b01f2e16-e25a-4b16-b680-ac61147f144b', 0, NULL, '2026-06-25 19:11:44', '2026-07-27 13:13:11', NULL),
(2, NULL, 2, '3bd4a120-df00-4db2-b35f-fe4011d791b3', 0, NULL, '2026-06-25 19:11:44', '2026-07-23 14:37:51', NULL),
(3, NULL, 3, 'da1f0756-39da-4023-a096-c0e19f7685fa', 0, NULL, '2026-06-25 19:11:44', '2026-07-23 14:37:56', NULL),
(4, NULL, 4, '5ca7c9ce-d441-4d91-aed0-23a16c1a7bee', 0, NULL, '2026-06-25 19:11:44', '2026-07-23 14:38:01', NULL),
(5, NULL, 5, '7098a0f9-579d-40a6-8d81-b2a445c5ec46', 0, NULL, '2026-06-25 19:11:44', '2026-07-23 14:38:07', NULL),
(6, NULL, 6, 'cd3cbfa6-f621-4bb7-b650-6e92b564f804', 1, NULL, '2026-06-25 19:11:45', '2026-06-25 19:11:45', NULL),
(7, NULL, 7, 'fb3768cf-19dd-4443-a97a-486a232f0e9f', 0, NULL, '2026-06-25 19:11:45', '2026-07-23 14:38:16', NULL),
(8, NULL, 8, 'e54af440-a23e-4448-bc68-cbff87ebd186', 0, NULL, '2026-06-25 19:11:45', '2026-07-23 14:38:21', NULL),
(9, NULL, 9, '8f3d68ac-3128-4dd7-8fab-dc3d6f5da582', 0, NULL, '2026-06-25 19:11:45', '2026-07-23 12:40:22', NULL),
(10, NULL, 10, '028b36c8-5254-4dda-b74d-ba1d726121b5', 0, NULL, '2026-06-25 19:11:45', '2026-07-23 14:38:27', NULL),
(11, 13, 11, '658f9ff7-0cbe-4317-8df2-da170c80852d', 1, NULL, '2026-06-25 19:11:45', '2026-07-27 11:20:58', NULL),
(12, 13, 12, '993e33e0-8e8e-4386-bc92-b29ed481e401', 1, NULL, '2026-06-25 19:11:45', '2026-07-27 11:20:14', NULL),
(13, 6, 13, 'a8d58061-b282-494f-9af7-5733bb3ab3c2', 1, NULL, '2026-06-25 19:11:45', '2026-06-25 19:11:45', NULL),
(14, 6, 14, '2f7dcc92-1352-48d6-a69c-8723da8a0e49', 1, NULL, '2026-06-25 19:11:45', '2026-07-23 14:40:48', NULL),
(15, 6, 15, '9f63d011-5424-48e7-badc-67d2852464c2', 1, NULL, '2026-06-25 19:11:45', '2026-06-25 19:11:45', NULL),
(16, 13, 16, '698574fd-afba-4296-a1d3-ed3918cd3a66', 1, NULL, '2026-06-25 19:11:45', '2026-07-23 11:13:50', NULL),
(17, 14, 17, 'a7a6db0d-7a68-475f-b7a2-8e9a690329eb', 1, NULL, '2026-06-25 19:11:45', '2026-07-27 11:23:09', NULL),
(18, 14, 18, '655bb1af-717f-4aed-a376-7a49f15d7860', 1, NULL, '2026-06-25 19:11:45', '2026-07-27 11:21:56', NULL),
(19, 15, 19, '9b7e66d4-a14b-4a76-9b1b-7bc53b8719b1', 1, NULL, '2026-06-25 19:11:45', '2026-07-27 11:22:48', NULL),
(20, 15, 20, '9aec473b-e016-47e6-8a6c-979340db40ce', 1, NULL, '2026-06-25 19:11:45', '2026-07-27 11:22:19', NULL),
(21, 2, 21, '366447a6-c27b-498c-b66b-c246a14d6727', 0, NULL, '2026-06-25 19:11:45', '2026-07-23 14:37:51', NULL),
(22, 2, 22, '7e6c9c68-7faa-4e9a-b01f-dfe51a2a2c9b', 0, NULL, '2026-06-25 19:11:45', '2026-07-23 14:37:51', NULL),
(23, 2, 23, 'ee7e8023-ae4d-44a1-a407-cce3e7474cdd', 0, NULL, '2026-06-25 19:11:45', '2026-07-23 14:37:51', NULL),
(24, 2, 24, '0fc1c165-643f-4991-a37d-a6272ca0f643', 0, NULL, '2026-06-25 19:11:45', '2026-07-23 14:37:51', NULL),
(25, 3, 25, '8de674a8-7be9-451a-b9ac-9a85d79be48f', 0, NULL, '2026-06-25 19:11:45', '2026-07-23 14:37:56', NULL),
(26, 3, 26, 'bdf9d268-471c-4fec-93d3-a8245e8bb48e', 0, NULL, '2026-06-25 19:11:45', '2026-07-23 14:37:56', NULL),
(27, 3, 27, 'b456f13d-1bbe-4270-8f66-2eed90401e79', 0, NULL, '2026-06-25 19:11:45', '2026-07-23 14:37:56', NULL),
(28, 3, 28, 'f7fd2c4c-4e17-45fb-b2b3-a39bd82d4bd0', 0, NULL, '2026-06-25 19:11:45', '2026-07-23 14:37:56', NULL),
(29, 4, 29, '0188b456-3ac9-4f16-b145-fd6282bb6b71', 0, NULL, '2026-06-25 19:11:45', '2026-07-23 14:38:01', NULL),
(30, 4, 30, 'a7c4c76b-8de1-4dfc-92af-5b592a0b8b0d', 0, NULL, '2026-06-25 19:11:45', '2026-07-23 14:38:01', NULL),
(31, 4, 31, 'cdf2d0cb-8728-4aa9-ab21-f74f4c1d42fa', 0, NULL, '2026-06-25 19:11:45', '2026-07-23 14:38:01', NULL),
(32, 5, 32, '2073305f-8685-42f9-8076-cbdb1b53db9a', 0, NULL, '2026-06-25 19:11:45', '2026-07-23 14:38:07', NULL),
(33, 5, 33, '665c7d0f-0347-49fa-aab4-b5d1b0dd057e', 0, NULL, '2026-06-25 19:11:45', '2026-07-23 14:38:07', NULL),
(34, 5, 34, 'b0b64119-6de9-4f13-8eeb-623c5a461e6d', 0, NULL, '2026-06-25 19:11:45', '2026-07-23 14:38:07', NULL),
(35, 7, 35, 'f2018628-7ed0-418b-b8a2-28d0fa6ceb2b', 0, NULL, '2026-06-25 19:11:45', '2026-07-23 14:38:16', NULL),
(36, 7, 36, '8253fdff-17b4-4beb-b21f-da6a92b75ec4', 0, NULL, '2026-06-25 19:11:45', '2026-07-23 14:38:16', NULL),
(37, 7, 37, 'fa9e52d9-5a63-42d2-914b-4717993f575c', 0, NULL, '2026-06-25 19:11:45', '2026-07-23 14:38:16', NULL),
(38, 8, 38, '03d6b225-12b4-4104-ada2-3c9ae16c1bd2', 0, NULL, '2026-06-25 19:11:45', '2026-07-23 14:38:22', NULL),
(39, 8, 39, '62f86364-d9f8-414e-b6df-382286c03a2c', 0, NULL, '2026-06-25 19:11:45', '2026-07-23 14:38:22', NULL),
(40, 9, 40, 'ca8ca7f6-0c06-42c3-be90-87392bc27499', 0, NULL, '2026-06-25 19:11:45', '2026-07-23 12:40:22', NULL),
(41, 9, 41, '0797835d-357b-4013-9194-bb31609e31e5', 0, NULL, '2026-06-25 19:11:45', '2026-07-23 12:40:22', NULL),
(42, 1, 42, '9b565d2d-8ac8-4f44-9db0-eb96f7a58a29', 0, NULL, '2026-06-25 19:11:45', '2026-07-23 12:39:51', NULL),
(43, 1, 43, '6eb8fd4d-dccf-4439-831d-0d1df07ab8c7', 0, NULL, '2026-06-25 19:11:45', '2026-07-23 12:39:51', NULL);

-- --------------------------------------------------------

--
-- Structure de la table `priority_definition`
--

DROP TABLE IF EXISTS `priority_definition`;
CREATE TABLE IF NOT EXISTS `priority_definition` (
  `slug` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `label` varchar(100) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `color` enum('slate','blue','teal','amber','orange','red','purple') COLLATE utf8mb4_unicode_ci NOT NULL,
  `sort_order` smallint NOT NULL,
  `is_builtin` tinyint(1) NOT NULL,
  `id` int NOT NULL AUTO_INCREMENT,
  `uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` tinyint(1) NOT NULL,
  `infos` json DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `slug` (`slug`),
  UNIQUE KEY `uuid` (`uuid`),
  KEY `idx_prio_status` (`status`,`deleted_at`),
  KEY `idx_prio_order` (`sort_order`)
) ENGINE=InnoDB AUTO_INCREMENT=6 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Déchargement des données de la table `priority_definition`
--

INSERT INTO `priority_definition` (`slug`, `label`, `description`, `color`, `sort_order`, `is_builtin`, `id`, `uuid`, `status`, `infos`, `created_at`, `updated_at`, `deleted_at`) VALUES
('low', 'Basse', 'Demandes non urgentes, traitement dans les délais standards.', 'slate', 1, 1, 1, '0449a35d-495f-419e-bfc6-ed18898ced60', 1, NULL, '2026-06-25 19:11:44', '2026-08-15 15:03:04', NULL),
('medium', 'Moyenne', 'Demandes courantes nécessitant un suivi normal.', 'blue', 2, 1, 2, '4237dafe-9423-4961-b8b7-261347db1f5c', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('high', 'Haute', 'Demandes urgentes impactant plusieurs utilisateurs.', 'orange', 3, 1, 3, '0c4867bc-4df8-4d50-a7cd-b1ac7798797d', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('critical', 'Critique', 'Incidents majeurs à traiter immédiatement.', 'red', 4, 1, 4, '1244572c-2f2e-403d-b9a8-7617ebb41564', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL);

-- --------------------------------------------------------

--
-- Structure de la table `request`
--

DROP TABLE IF EXISTS `request`;
CREATE TABLE IF NOT EXISTS `request` (
  `request_status_id` int NOT NULL,
  `priority_definition_id` int NOT NULL,
  `request_category_id` int NOT NULL,
  `request_source` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `unity_id` int DEFAULT NULL,
  `on_behalf_unity_id` int DEFAULT NULL,
  `assignee_id` int DEFAULT NULL,
  `requester_id` int DEFAULT NULL,
  `ref` varchar(30) COLLATE utf8mb4_unicode_ci NOT NULL,
  `title` varchar(500) COLLATE utf8mb4_unicode_ci NOT NULL,
  `description` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `in_triage` tinyint(1) NOT NULL,
  `is_external` tinyint(1) NOT NULL,
  `requester_type` enum('internal','external') COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `submission_mode` enum('personal','on_behalf_of_unit') COLLATE utf8mb4_unicode_ci NOT NULL,
  `requester_name` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `requester_phone` varchar(30) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `requester_email` varchar(320) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `requester_address` text COLLATE utf8mb4_unicode_ci,
  `meter_number` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `client_ref` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `lat` double DEFAULT NULL,
  `lng` double DEFAULT NULL,
  `location_label` text COLLATE utf8mb4_unicode_ci,
  `sla_hours` smallint NOT NULL,
  `sla_elapsed` smallint NOT NULL,
  `sla_breached` tinyint(1) NOT NULL,
  `merged_into_id` int DEFAULT NULL,
  `sla_response_at` datetime DEFAULT NULL,
  `resolved_at` datetime DEFAULT NULL,
  `closed_at` datetime DEFAULT NULL,
  `id` int NOT NULL AUTO_INCREMENT,
  `uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` tinyint(1) NOT NULL,
  `infos` json DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_req_ref` (`ref`),
  UNIQUE KEY `ref` (`ref`),
  UNIQUE KEY `uuid` (`uuid`),
  KEY `on_behalf_unity_id` (`on_behalf_unity_id`),
  KEY `requester_id` (`requester_id`),
  KEY `idx_req_merged_into` (`merged_into_id`),
  KEY `idx_req_created` (`created_at`),
  KEY `idx_req_triage` (`in_triage`),
  KEY `idx_req_status` (`status`,`deleted_at`),
  KEY `idx_req_status_id` (`request_status_id`),
  KEY `idx_req_priority_def_id` (`priority_definition_id`),
  KEY `idx_req_category_id` (`request_category_id`),
  KEY `idx_req_source` (`request_source`),
  KEY `idx_req_unity` (`unity_id`),
  KEY `idx_req_assignee` (`assignee_id`)
) ENGINE=InnoDB AUTO_INCREMENT=12 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Déchargement des données de la table `request`
--

INSERT INTO `request` (`request_status_id`, `priority_definition_id`, `request_category_id`, `request_source`, `unity_id`, `on_behalf_unity_id`, `assignee_id`, `requester_id`, `ref`, `title`, `description`, `in_triage`, `is_external`, `requester_type`, `submission_mode`, `requester_name`, `requester_phone`, `requester_email`, `requester_address`, `meter_number`, `client_ref`, `lat`, `lng`, `location_label`, `sla_hours`, `sla_elapsed`, `sla_breached`, `merged_into_id`, `sla_response_at`, `resolved_at`, `closed_at`, `id`, `uuid`, `status`, `infos`, `created_at`, `updated_at`, `deleted_at`) VALUES
(11, 2, 23, NULL, 16, NULL, 6, 2, 'DSI-EDX-SED-1007490260812-001', 'mon ordinateur HP ne s\'allume pas', 'mon ordinateur HP ne s\'allume pas mon ordinateur HP ne s\'allume pas mon ordinateur HP ne s\'allume pas', 0, 0, NULL, 'personal', 'GASPARD GOEPOGUI', NULL, 'gaspard@edg.com.gn', NULL, NULL, NULL, NULL, NULL, NULL, 48, 0, 0, NULL, NULL, NULL, NULL, 1, '9abb4681-ab50-43f5-9b1c-9c2690d8df40', 1, '{\"auto_route\": true, \"cancel_reason\": \"mon problème est resolut\", \"sla_cycle_number\": 1, \"current_intervention_id\": \"req1-c1-i2\", \"intervention_order_in_cycle\": 2}', '2026-08-12 10:07:49', '2026-08-13 10:22:17', NULL),
(11, 2, 23, NULL, NULL, NULL, NULL, 5, 'GEN-GEN-UNK-1737030260812-001', 'mon charge ne fonctinne pas', 'mon charge ne fonctinne pas', 1, 0, NULL, 'personal', 'GASPARD KAMAN GOEPOGUI', NULL, 'gaspardkamangoepogui96@gmail.com', NULL, NULL, NULL, NULL, NULL, NULL, 48, 0, 0, NULL, NULL, NULL, NULL, 2, '9bcae0e3-031a-4f4d-aaba-7bd456c05b6b', 1, '{\"auto_route\": true, \"cancel_reason\": \"mon problème est resolue correctement\"}', '2026-08-12 17:37:03', '2026-08-13 09:49:01', NULL),
(6, 2, 23, NULL, 16, NULL, 7, 2, 'DSI-EDX-SED-1103350260813-001', 'mon clavier ne marche pas', 'mon clavier ne marche pas mon clavier ne marche pasmon clavier ne marche pas', 0, 0, NULL, 'personal', 'GASPARD GOEPOGUI', NULL, 'gaspard@edg.com.gn', NULL, NULL, NULL, NULL, NULL, NULL, 48, 0, 0, NULL, NULL, NULL, NULL, 3, '1f90ebfb-5047-4599-85a0-ada2f115301e', 1, '{\"auto_route\": true, \"sla_cycle_number\": 1, \"current_intervention_id\": \"req3-c1-i1\", \"intervention_order_in_cycle\": 1}', '2026-08-13 11:03:36', '2026-08-13 12:31:01', NULL),
(11, 2, 23, NULL, NULL, NULL, NULL, 7, 'DSI-EDX-SED-1105440260814-001', 'mon IPhone ne marche pas', 'mon IPhone ne marche pas mon IPhone ne marche pas mon IPhone ne marche pas', 1, 0, NULL, 'personal', 'Jams jamsatou1', NULL, 'goepoguigaspardkaman5@gmail.com', NULL, NULL, NULL, NULL, NULL, NULL, 48, 0, 0, NULL, NULL, NULL, NULL, 4, '229718b0-ad3e-45ac-831b-db443f1a1ae1', 1, '{\"auto_route\": true, \"cancel_reason\": \"je suis deja satisfait\"}', '2026-08-14 11:05:44', '2026-08-14 11:13:33', NULL),
(3, 2, 23, NULL, NULL, NULL, NULL, 7, 'DSI-EDX-SED-1143260260814-001', 'Mon clavier ne passe plus bien chef', 'Mon clavier ne passe plus bien chef Mon clavier ne passe plus bien chef Mon clavier ne passe plus bien chef', 1, 0, NULL, 'personal', 'Jams jamsatou1', NULL, 'goepoguigaspardkaman5@gmail.com', NULL, NULL, NULL, NULL, NULL, NULL, 48, 0, 0, NULL, NULL, NULL, NULL, 5, '04954b58-656c-43fa-8a73-21bab9a9a14e', 1, '{\"auto_route\": true}', '2026-08-14 11:43:26', '2026-08-14 11:43:27', NULL),
(6, 1, 8, NULL, 16, NULL, 2, 7, 'DSI-EDX-SED-1328430260814-001', 'mon chargeur Mac ne marche pas', 'mon chargeur Mac ne marche pas mon chargeur Mac ne marche pas mon chargeur Mac ne marche pas', 0, 0, NULL, 'personal', 'Jams jamsatou1', NULL, 'goepoguigaspardkaman5@gmail.com', NULL, NULL, NULL, NULL, NULL, NULL, 48, 0, 0, NULL, NULL, NULL, NULL, 6, 'a95e18cc-ce96-4157-9f85-06b17a4a8a13', 1, '{\"auto_route\": true, \"sla_cycle_number\": 1, \"current_intervention_id\": \"req6-c1-i1\", \"intervention_order_in_cycle\": 1}', '2026-08-14 13:28:44', '2026-08-15 11:44:02', NULL),
(3, 2, 23, NULL, NULL, NULL, NULL, 8, 'DSI-EDX-SED-1205150260815-001', 'Mon ordinateur ne marche pas', 'Mon ordinateur ne marche pas Mon ordinateur ne marche pas Mon ordinateur ne marche pas', 1, 0, NULL, 'personal', 'PAULETTE ONIVOGUI', NULL, 'pauletteonivogui2024@gmail.com', NULL, NULL, NULL, NULL, NULL, NULL, 48, 0, 0, NULL, NULL, NULL, NULL, 7, '7d3f3e63-125a-4a94-bedb-59da3c9371ac', 1, '{\"auto_route\": true}', '2026-08-15 12:05:15', '2026-08-15 12:05:16', NULL),
(11, 2, 23, NULL, NULL, NULL, NULL, 8, 'DSI-EDX-SED-1207430260815-001', 'Mon clavier ne marche pas', 'Mon clavier ne marche pas Mon clavier ne marche pas Mon clavier ne marche pas', 1, 0, NULL, 'personal', 'PAULETTE ONIVOGUI', NULL, 'onivoguipaulette5@gmail.com', NULL, NULL, NULL, NULL, NULL, NULL, 48, 0, 0, NULL, NULL, NULL, NULL, 8, '42920c0b-c96d-49cf-ac21-02954f9c565f', 1, '{\"auto_route\": true, \"cancel_reason\": \"merci, j\'ai deja trouvé solution à mon problème\"}', '2026-08-15 12:07:43', '2026-08-15 12:10:39', NULL),
(6, 2, 8, NULL, 16, NULL, 6, 7, 'DSI-EDX-SED-0941090260819-001', 'ma machine est en panne', 'ma machine est en panne ma machine est en panne ma machine est en panne', 0, 0, NULL, 'personal', 'GASPARD KAMUS GOEPOGUI', NULL, 'goepoguigaspardkaman5@gmail.com', NULL, NULL, NULL, NULL, NULL, NULL, 48, 0, 0, NULL, NULL, NULL, NULL, 9, '90a1964e-ac50-4899-8fb1-e912c4e66c4e', 1, '{\"auto_route\": true, \"sla_cycle_number\": 1, \"current_intervention_id\": \"req9-c1-i2\", \"intervention_order_in_cycle\": 2}', '2026-08-19 09:41:10', '2026-08-19 10:12:36', NULL),
(6, 2, 23, NULL, NULL, NULL, 36, 34, 'GEN-GEN-UNK-1205150260827-001', 'L\'application de ne marche pas', 'L\'application de ne marche pas  L\'application de ne marche pas  L\'application de ne marche pas  L\'application de ne marche pas  L\'application de ne marche pas', 0, 0, NULL, 'personal', 'Mohamed Tassilimy Diaby', NULL, 'diatas2@gmail.com', NULL, NULL, NULL, NULL, NULL, NULL, 48, 0, 0, NULL, NULL, NULL, NULL, 10, '068fd5cc-8dcf-42eb-8773-5a7ee05f6b75', 1, '{\"auto_route\": true, \"sla_cycle_number\": 1, \"current_intervention_id\": \"req10-c1-i1\", \"intervention_order_in_cycle\": 1}', '2026-08-27 12:05:15', '2026-08-27 12:24:21', NULL),
(3, 2, 23, NULL, NULL, NULL, NULL, 34, 'EDG-26-00001', 'mon application ne fonctionne plus', 'mon application ne fonctionne plus mon application ne fonctionne plus mon application ne fonctionne plus mon application ne fonctionne plus mon application ne fonctionne plus', 1, 0, NULL, 'personal', 'Mohamed Tassilimy Diaby', NULL, 'diatas2@gmail.com', NULL, NULL, NULL, NULL, NULL, NULL, 48, 0, 0, NULL, NULL, NULL, NULL, 11, '336932f6-f193-47d2-b217-8eddfeb6337f', 1, '{\"auto_route\": true}', '2026-08-27 15:10:29', '2026-08-27 15:10:29', NULL);

-- --------------------------------------------------------

--
-- Structure de la table `request_category`
--

DROP TABLE IF EXISTS `request_category`;
CREATE TABLE IF NOT EXISTS `request_category` (
  `code` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `label` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `sort_order` smallint NOT NULL,
  `is_builtin` tinyint(1) NOT NULL,
  `id` int NOT NULL AUTO_INCREMENT,
  `uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` tinyint(1) NOT NULL,
  `infos` json DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `code` (`code`),
  UNIQUE KEY `uuid` (`uuid`),
  KEY `idx_rc_status` (`status`,`deleted_at`),
  KEY `idx_rc_order` (`sort_order`)
) ENGINE=InnoDB AUTO_INCREMENT=25 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Déchargement des données de la table `request_category`
--

INSERT INTO `request_category` (`code`, `label`, `sort_order`, `is_builtin`, `id`, `uuid`, `status`, `infos`, `created_at`, `updated_at`, `deleted_at`) VALUES
('incident', 'Incident', 1, 1, 1, '847973ae-60ed-405b-9862-185bf954416d', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('demande_service', 'Demande de service', 2, 1, 2, '1604f283-95e7-43a9-9e75-894e4447f49d', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('maintenance_si', 'Maintenance SI', 3, 1, 3, '47e4d41f-1f40-4a81-bfc8-25f73bf66f8e', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('reseau', 'Réseau', 4, 1, 4, 'a5c3296f-087c-4593-9da1-9fced33ed5d6', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('habilitation', 'Habilitation / Accès', 5, 1, 5, 'a60de94d-e98d-43ea-a0be-f58bd0f1f05e', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('securite', 'Sécurité', 6, 1, 6, '1a6f8bd1-9a36-4ac7-b233-7f7e092ef01b', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('materiel', 'Matériel', 7, 1, 7, '126e5705-4ffd-4b7f-a4fd-98e81beddaad', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('logiciel', 'Logiciel', 8, 1, 8, '24a7b91a-6112-43aa-9150-7edc4105ff44', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('branchement', 'Branchement', 10, 1, 9, '10232954-e4f9-4b2e-aab8-fddbab90044d', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('panne', 'Panne / Interruption', 11, 1, 10, '61ec6698-22e4-47ab-bbf6-76686a900684', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('facturation', 'Facturation', 12, 1, 11, 'd7ec5e30-c044-4321-af5e-73594a287ae3', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('compteur', 'Compteur / Relevé', 13, 1, 12, '4b570084-6d37-486b-a2e5-681a53104cc4', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('reclamation', 'Réclamation', 14, 1, 13, '40bfcd29-4b67-4f13-905a-3d2fdd483b90', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('information', 'Demande d\'information', 15, 1, 14, 'c5c8427c-1ad6-4fa3-a709-7f556f0063de', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('acces_applicatif', 'Accès applicatif', 16, 1, 15, 'afbae730-5ffe-49d6-b8ee-52fc3339f4df', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('incident_technique', 'Incident technique', 17, 1, 16, 'e99f3a53-6ac1-4fb4-bbc9-063486d0323f', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('paie', 'Paie', 18, 1, 17, 'e8c2a4fb-ff1c-4e16-b692-203b23e50550', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('carrieres', 'Carrières', 19, 1, 18, '5fb62504-3298-49b7-b490-443175c56202', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('budget', 'Budget', 20, 1, 19, 'ee3a5132-c6a2-465e-b5ce-ddca7d40cce9', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('document_administratif', 'Document administratif', 21, 1, 20, 'b2964415-26e3-4de3-ad36-f72b6dd78af4', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('formation', 'Formation', 22, 1, 21, 'b2dadade-2f2b-46cb-9f58-a2b3684e3118', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('equipement', 'Équipement / Matériel', 23, 1, 22, '4606ad00-4cbc-44a0-a50b-d8b0dd74f968', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('autre', 'Autre', 99, 1, 23, '11e36228-3b3c-4fa4-8d47-81443b70ad3c', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL);

-- --------------------------------------------------------

--
-- Structure de la table `request_status`
--

DROP TABLE IF EXISTS `request_status`;
CREATE TABLE IF NOT EXISTS `request_status` (
  `code` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `label` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `sort_order` smallint NOT NULL,
  `is_builtin` tinyint(1) NOT NULL,
  `id` int NOT NULL AUTO_INCREMENT,
  `uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` tinyint(1) NOT NULL,
  `infos` json DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `code` (`code`),
  UNIQUE KEY `uuid` (`uuid`),
  KEY `idx_rs_status` (`status`,`deleted_at`),
  KEY `idx_rs_order` (`sort_order`)
) ENGINE=InnoDB AUTO_INCREMENT=15 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Déchargement des données de la table `request_status`
--

INSERT INTO `request_status` (`code`, `label`, `sort_order`, `is_builtin`, `id`, `uuid`, `status`, `infos`, `created_at`, `updated_at`, `deleted_at`) VALUES
('new', 'Nouvelle', 0, 1, 1, '9066e3a5-36bf-4358-8d6b-d40f58d31b21', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('pending', 'En attente', 1, 1, 2, '1d2b2ad7-ba94-4206-b80b-4141d04b76a5', 1, NULL, '2026-06-25 19:11:44', '2026-08-28 11:07:15', NULL),
('qualifying', 'En qualification', 2, 1, 3, 'f0a79fec-c456-4422-8d64-8526750ca84d', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('qualified', 'Qualifiée', 3, 1, 4, 'af56f105-fe94-4603-9c63-7a045cd5e4d0', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('assigned', 'Assignée', 4, 1, 5, 'f25e2a2f-0297-470d-8eb1-db3bbd53a11e', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('in_progress', 'En cours', 5, 1, 6, 'd4531d67-86b5-4bab-a831-d9c44f96d6be', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('escalated', 'Escaladée', 7, 1, 8, '5fa01eb1-8d91-437d-8c00-4c96be92b2fc', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('resolved', 'Résolue', 8, 1, 9, 'cc4eb8b9-07d7-4986-b774-fb627b7083fd', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('closed', 'Clôturée', 9, 1, 10, '31a78aaa-6b0e-4d5b-b65b-4a6a4980a6e5', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('cancelled', 'Annulée', 10, 1, 11, '47059e9c-e62d-466b-8a88-ced21c05e36f', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('reopened', 'Réouverte', 11, 1, 12, '9a7002ee-1fc8-428e-8175-09082038dd6f', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL),
('rejected', 'Rejeté', 12, 1, 13, '2360f600-9589-4212-b787-10380d1be602', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL);

-- --------------------------------------------------------

--
-- Structure de la table `routing_rule`
--

DROP TABLE IF EXISTS `routing_rule`;
CREATE TABLE IF NOT EXISTS `routing_rule` (
  `target_unity_id` int DEFAULT NULL,
  `name` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `condition_field` enum('category','priority','source','keyword') COLLATE utf8mb4_unicode_ci NOT NULL,
  `condition_value` text COLLATE utf8mb4_unicode_ci NOT NULL,
  `auto_assign` tinyint(1) NOT NULL,
  `sort_order` smallint NOT NULL,
  `id` int NOT NULL AUTO_INCREMENT,
  `uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` tinyint(1) NOT NULL,
  `infos` json DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uuid` (`uuid`),
  KEY `target_unity_id` (`target_unity_id`),
  KEY `idx_rr_order` (`sort_order`),
  KEY `idx_rr_status` (`status`,`deleted_at`)
) ENGINE=InnoDB AUTO_INCREMENT=48 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Déchargement des données de la table `routing_rule`
--

INSERT INTO `routing_rule` (`target_unity_id`, `name`, `condition_field`, `condition_value`, `auto_assign`, `sort_order`, `id`, `uuid`, `status`, `infos`, `created_at`, `updated_at`, `deleted_at`) VALUES
(6, 'AUDIT-incident', 'category', 'incident', 1, 1, 2, '94a41054-647b-481f-8bf4-7dfea6618c4f', 1, '{\"target_unity_label\": \"Direction des Systèmes d\'Information\", \"target_unity_codename\": \"DSI\"}', '2026-07-04 23:30:08', '2026-07-04 23:31:36', '2026-07-04 23:31:37'),
(6, 'AUDIT-maintenance_si', 'category', 'maintenance_si', 1, 2, 3, '2698a607-e25a-4679-9b4f-2ed2585e420f', 1, '{\"target_unity_label\": \"Direction des Systèmes d\'Information\", \"target_unity_codename\": \"DSI\"}', '2026-07-04 23:30:11', '2026-07-04 23:31:39', '2026-07-04 23:31:40'),
(6, 'AUDIT-reseau', 'category', 'reseau', 1, 3, 4, '23275b68-0220-446b-97b8-320267774ab7', 1, '{\"target_unity_label\": \"Direction des Systèmes d\'Information\", \"target_unity_codename\": \"DSI\"}', '2026-07-04 23:30:14', '2026-07-04 23:31:42', '2026-07-04 23:31:42'),
(6, 'AUDIT-habilitation', 'category', 'habilitation', 1, 4, 5, '201e8312-e7e7-40d1-8e2b-a783fe6c7768', 1, '{\"target_unity_label\": \"Direction des Systèmes d\'Information\", \"target_unity_codename\": \"DSI\"}', '2026-07-04 23:30:16', '2026-07-04 23:31:45', '2026-07-04 23:31:45'),
(6, 'AUDIT-logiciel', 'category', 'logiciel', 1, 5, 6, '9d13e46e-0dfa-4c55-94ce-fffe6984cf7c', 1, '{\"target_unity_label\": \"Direction des Systèmes d\'Information\", \"target_unity_codename\": \"DSI\"}', '2026-07-04 23:30:19', '2026-07-04 23:31:47', '2026-07-04 23:31:48'),
(6, 'AUDIT-acces_applicatif', 'category', 'acces_applicatif', 1, 6, 7, '3ab9b436-a508-4a9d-b5a2-95ce32f7579e', 1, '{\"target_unity_label\": \"Direction des Systèmes d\'Information\", \"target_unity_codename\": \"DSI\"}', '2026-07-04 23:30:21', '2026-07-04 23:31:50', '2026-07-04 23:31:50'),
(10, 'AUDIT-securite', 'category', 'securite', 1, 7, 8, 'fba8c43c-3cfe-4975-8400-645ffe975197', 1, '{\"target_unity_label\": \"Direction Qualité & Environnement\", \"target_unity_codename\": \"DQE\"}', '2026-07-04 23:30:24', '2026-07-04 23:31:52', '2026-07-04 23:31:53'),
(7, 'AUDIT-materiel', 'category', 'materiel', 1, 8, 9, 'b3bc791c-d040-4350-a0b0-564c7ace4861', 1, '{\"target_unity_label\": \"Direction de la Maintenance\", \"target_unity_codename\": \"DM\"}', '2026-07-04 23:30:27', '2026-07-04 23:31:55', '2026-07-04 23:31:55'),
(7, 'AUDIT-equipement', 'category', 'equipement', 1, 9, 10, '0c9f80e5-1d43-43da-9c73-22917cd1c22b', 1, '{\"target_unity_label\": \"Direction de la Maintenance\", \"target_unity_codename\": \"DM\"}', '2026-07-04 23:30:30', '2026-07-04 23:31:58', '2026-07-04 23:31:58'),
(3, 'AUDIT-branchement', 'category', 'branchement', 1, 10, 11, '3db5c6a6-c086-4e48-8ff3-62fbca85f7ac', 1, '{\"target_unity_label\": \"Direction Technique\", \"target_unity_codename\": \"DT\"}', '2026-07-04 23:30:32', '2026-07-04 23:32:00', '2026-07-04 23:32:01'),
(3, 'AUDIT-panne', 'category', 'panne', 1, 11, 12, 'ee7f3964-8783-4dbc-97d9-85f5b315af62', 1, '{\"target_unity_label\": \"Direction Technique\", \"target_unity_codename\": \"DT\"}', '2026-07-04 23:30:35', '2026-07-04 23:32:03', '2026-07-04 23:32:04'),
(3, 'AUDIT-compteur', 'category', 'compteur', 1, 12, 13, 'f24adc91-3226-4a14-b0f7-432cabd54b8c', 1, '{\"target_unity_label\": \"Direction Technique\", \"target_unity_codename\": \"DT\"}', '2026-07-04 23:30:38', '2026-07-04 23:32:06', '2026-07-04 23:32:07'),
(3, 'AUDIT-incident_technique', 'category', 'incident_technique', 1, 13, 14, '84d251c2-d867-496e-976c-7eb357284956', 1, '{\"target_unity_label\": \"Direction Technique\", \"target_unity_codename\": \"DT\"}', '2026-07-04 23:30:40', '2026-07-04 23:32:09', '2026-07-04 23:32:09'),
(5, 'AUDIT-facturation', 'category', 'facturation', 1, 14, 15, '85d073e3-aba1-4b95-9445-1bb825a2432d', 1, '{\"target_unity_label\": \"Direction Financière\", \"target_unity_codename\": \"DF\"}', '2026-07-04 23:30:43', '2026-07-04 23:32:11', '2026-07-04 23:32:12'),
(5, 'AUDIT-budget', 'category', 'budget', 1, 15, 16, '3573a611-9c4d-4e17-8fc1-0f1bbe93aaea', 1, '{\"target_unity_label\": \"Direction Financière\", \"target_unity_codename\": \"DF\"}', '2026-07-04 23:30:46', '2026-07-04 23:32:14', '2026-07-04 23:32:15'),
(2, 'AUDIT-reclamation', 'category', 'reclamation', 1, 16, 17, '5ad53f0b-1a34-4d2e-8d77-4c1ba2a3d00e', 1, '{\"target_unity_label\": \"Direction Commerciale\", \"target_unity_codename\": \"DC\"}', '2026-07-04 23:30:48', '2026-07-04 23:32:17', '2026-07-04 23:32:17'),
(2, 'AUDIT-information', 'category', 'information', 1, 17, 18, '85d3c76a-7643-4199-8def-6180633bc298', 1, '{\"target_unity_label\": \"Direction Commerciale\", \"target_unity_codename\": \"DC\"}', '2026-07-04 23:30:51', '2026-07-04 23:32:19', '2026-07-04 23:32:20'),
(4, 'AUDIT-paie', 'category', 'paie', 1, 18, 19, '60f2283c-3e13-4a7a-b85a-c5c18a1f9797', 1, '{\"target_unity_label\": \"Direction des Ressources Humaines\", \"target_unity_codename\": \"DRH\"}', '2026-07-04 23:30:54', '2026-07-04 23:32:22', '2026-07-04 23:32:23'),
(4, 'AUDIT-carrieres', 'category', 'carrieres', 1, 19, 20, 'acb784ff-a524-41af-8940-d8e809ff4ebf', 1, '{\"target_unity_label\": \"Direction des Ressources Humaines\", \"target_unity_codename\": \"DRH\"}', '2026-07-04 23:30:56', '2026-07-04 23:32:25', '2026-07-04 23:32:25'),
(4, 'AUDIT-formation', 'category', 'formation', 1, 20, 21, 'f76c6742-5d40-40e1-8c44-1dd1f7c52f57', 1, '{\"target_unity_label\": \"Direction des Ressources Humaines\", \"target_unity_codename\": \"DRH\"}', '2026-07-04 23:30:59', '2026-07-04 23:32:27', '2026-07-04 23:32:28'),
(9, 'AUDIT-document_administratif', 'category', 'document_administratif', 1, 21, 22, '0246f628-5838-479a-9327-77d5d3fd30cb', 1, '{\"target_unity_label\": \"Direction des Affaires Juridiques\", \"target_unity_codename\": \"DIAJ\"}', '2026-07-04 23:31:02', '2026-07-04 23:32:30', '2026-07-04 23:32:30'),
(1, 'AUDIT-demande_service', 'category', 'demande_service', 1, 22, 23, '90c127b0-b30d-4fc4-a8a9-cb6f7c2487fc', 1, '{\"target_unity_label\": \"Direction Générale\", \"target_unity_codename\": \"DG\"}', '2026-07-04 23:31:04', '2026-07-04 23:32:32', '2026-07-04 23:32:33'),
(1, 'AUDIT-autre', 'category', 'autre', 1, 23, 24, 'cdd4382a-10a1-4c67-8a68-cee78da9dc99', 1, '{\"target_unity_label\": \"Direction Générale\", \"target_unity_codename\": \"DG\"}', '2026-07-04 23:31:07', '2026-07-04 23:32:35', '2026-07-04 23:32:36'),
(6, 'AUDIT-incident', 'category', 'incident', 1, 1, 25, 'cd12ec12-ff55-41e8-85b5-0a07fd79e1ed', 1, '{\"target_unity_label\": \"Direction des Systèmes d\'Information\", \"target_unity_codename\": \"DSI\"}', '2026-07-04 23:44:07', '2026-07-04 23:45:35', '2026-07-04 23:45:36'),
(6, 'AUDIT-maintenance_si', 'category', 'maintenance_si', 1, 2, 26, '12b77221-7a88-4622-bfdd-13fd5d81ed49', 1, '{\"target_unity_label\": \"Direction des Systèmes d\'Information\", \"target_unity_codename\": \"DSI\"}', '2026-07-04 23:44:09', '2026-07-04 23:45:38', '2026-07-04 23:45:38'),
(6, 'AUDIT-reseau', 'category', 'reseau', 1, 3, 27, '7849b05a-6c3a-4726-9aee-eed7df480060', 1, '{\"target_unity_label\": \"Direction des Systèmes d\'Information\", \"target_unity_codename\": \"DSI\"}', '2026-07-04 23:44:12', '2026-07-04 23:45:40', '2026-07-04 23:45:41'),
(6, 'AUDIT-habilitation', 'category', 'habilitation', 1, 4, 28, '8f3cbb2f-cfe7-4ccf-80d0-948a16852c82', 1, '{\"target_unity_label\": \"Direction des Systèmes d\'Information\", \"target_unity_codename\": \"DSI\"}', '2026-07-04 23:44:15', '2026-07-04 23:45:43', '2026-07-04 23:45:43'),
(6, 'AUDIT-logiciel', 'category', 'logiciel', 1, 5, 29, 'ff6fcfb0-6068-4771-91be-84c81a24e317', 1, '{\"target_unity_label\": \"Direction des Systèmes d\'Information\", \"target_unity_codename\": \"DSI\"}', '2026-07-04 23:44:17', '2026-07-04 23:45:46', '2026-07-04 23:45:46'),
(6, 'AUDIT-acces_applicatif', 'category', 'acces_applicatif', 1, 6, 30, '9789f127-6faf-4932-a469-8077af8dba33', 1, '{\"target_unity_label\": \"Direction des Systèmes d\'Information\", \"target_unity_codename\": \"DSI\"}', '2026-07-04 23:44:20', '2026-07-04 23:45:49', '2026-07-04 23:45:49'),
(10, 'AUDIT-securite', 'category', 'securite', 1, 7, 31, '6c437cd8-c4f2-4edc-ba14-225dca630585', 1, '{\"target_unity_label\": \"Direction Qualité & Environnement\", \"target_unity_codename\": \"DQE\"}', '2026-07-04 23:44:22', '2026-07-04 23:45:51', '2026-07-04 23:45:52'),
(7, 'AUDIT-materiel', 'category', 'materiel', 1, 8, 32, '2f5502a8-3167-4dfe-934d-e1d822bd86f1', 1, '{\"target_unity_label\": \"Direction de la Maintenance\", \"target_unity_codename\": \"DM\"}', '2026-07-04 23:44:25', '2026-07-04 23:45:54', '2026-07-04 23:45:54'),
(7, 'AUDIT-equipement', 'category', 'equipement', 1, 9, 33, '8108eb1b-2efa-4482-9834-208372377645', 1, '{\"target_unity_label\": \"Direction de la Maintenance\", \"target_unity_codename\": \"DM\"}', '2026-07-04 23:44:28', '2026-07-04 23:45:56', '2026-07-04 23:45:57'),
(3, 'AUDIT-branchement', 'category', 'branchement', 1, 10, 34, 'b624cc07-57ed-4a8f-808d-35a4dac7ab9f', 1, '{\"target_unity_label\": \"Direction Technique\", \"target_unity_codename\": \"DT\"}', '2026-07-04 23:44:30', '2026-07-04 23:45:59', '2026-07-04 23:46:00'),
(3, 'AUDIT-panne', 'category', 'panne', 1, 11, 35, 'f5fa26e9-79fe-4428-9bc2-f0b3532375c0', 1, '{\"target_unity_label\": \"Direction Technique\", \"target_unity_codename\": \"DT\"}', '2026-07-04 23:44:33', '2026-07-04 23:46:02', '2026-07-04 23:46:02'),
(3, 'AUDIT-compteur', 'category', 'compteur', 1, 12, 36, '386ad599-f7f4-4bf5-8a1d-60d7c5cd63cb', 1, '{\"target_unity_label\": \"Direction Technique\", \"target_unity_codename\": \"DT\"}', '2026-07-04 23:44:35', '2026-07-04 23:46:04', '2026-07-04 23:46:05'),
(3, 'AUDIT-incident_technique', 'category', 'incident_technique', 1, 13, 37, '8be0b18c-802e-422b-87e9-fda176cdc0e8', 1, '{\"target_unity_label\": \"Direction Technique\", \"target_unity_codename\": \"DT\"}', '2026-07-04 23:44:38', '2026-07-04 23:46:07', '2026-07-04 23:46:08'),
(5, 'AUDIT-facturation', 'category', 'facturation', 1, 14, 38, 'eae2f2a4-b5c1-4177-aa7a-d3338ef6c802', 1, '{\"target_unity_label\": \"Direction Financière\", \"target_unity_codename\": \"DF\"}', '2026-07-04 23:44:41', '2026-07-04 23:46:10', '2026-07-04 23:46:10'),
(5, 'AUDIT-budget', 'category', 'budget', 1, 15, 39, 'be0bb5cb-b826-4b7a-b407-06ece89e5a95', 1, '{\"target_unity_label\": \"Direction Financière\", \"target_unity_codename\": \"DF\"}', '2026-07-04 23:44:43', '2026-07-04 23:46:12', '2026-07-04 23:46:13'),
(2, 'AUDIT-reclamation', 'category', 'reclamation', 1, 16, 40, '2008da79-d1d7-4e4e-8dc0-9b30feb3ddb4', 1, '{\"target_unity_label\": \"Direction Commerciale\", \"target_unity_codename\": \"DC\"}', '2026-07-04 23:44:46', '2026-07-04 23:46:15', '2026-07-04 23:46:15'),
(2, 'AUDIT-information', 'category', 'information', 1, 17, 41, '8c463606-8cb6-49c0-8c99-865d6a6db5ce', 1, '{\"target_unity_label\": \"Direction Commerciale\", \"target_unity_codename\": \"DC\"}', '2026-07-04 23:44:49', '2026-07-04 23:46:18', '2026-07-04 23:46:18'),
(4, 'AUDIT-paie', 'category', 'paie', 1, 18, 42, '9321e4cc-8852-4365-89de-29f7b9fd170b', 1, '{\"target_unity_label\": \"Direction des Ressources Humaines\", \"target_unity_codename\": \"DRH\"}', '2026-07-04 23:44:51', '2026-07-04 23:46:20', '2026-07-04 23:46:21'),
(4, 'AUDIT-carrieres', 'category', 'carrieres', 1, 19, 43, '5628b83f-761e-404e-977f-30ae717d799a', 1, '{\"target_unity_label\": \"Direction des Ressources Humaines\", \"target_unity_codename\": \"DRH\"}', '2026-07-04 23:44:54', '2026-07-04 23:46:23', '2026-07-04 23:46:23'),
(4, 'AUDIT-formation', 'category', 'formation', 1, 20, 44, '08d0be6b-5674-42b2-9c68-a412d8079d56', 1, '{\"target_unity_label\": \"Direction des Ressources Humaines\", \"target_unity_codename\": \"DRH\"}', '2026-07-04 23:44:56', '2026-07-04 23:46:26', '2026-07-04 23:46:26'),
(9, 'AUDIT-document_administratif', 'category', 'document_administratif', 1, 21, 45, 'bd7b35cf-ad60-4a26-89e7-4c0931063059', 1, '{\"target_unity_label\": \"Direction des Affaires Juridiques\", \"target_unity_codename\": \"DIAJ\"}', '2026-07-04 23:44:59', '2026-07-04 23:46:28', '2026-07-04 23:46:29'),
(1, 'AUDIT-demande_service', 'category', 'demande_service', 1, 22, 46, '7fd918e1-4c1b-417f-9657-6526c5c0dfc5', 1, '{\"target_unity_label\": \"Direction Générale\", \"target_unity_codename\": \"DG\"}', '2026-07-04 23:45:02', '2026-07-04 23:46:31', '2026-07-04 23:46:31'),
(1, 'AUDIT-autre', 'category', 'autre', 1, 23, 47, 'aa81af6f-e75c-40a6-9202-723384020bb3', 1, '{\"target_unity_label\": \"Direction Générale\", \"target_unity_codename\": \"DG\"}', '2026-07-04 23:45:05', '2026-07-04 23:46:34', '2026-07-04 23:46:34');

-- --------------------------------------------------------

--
-- Structure de la table `sla_policy`
--

DROP TABLE IF EXISTS `sla_policy`;
CREATE TABLE IF NOT EXISTS `sla_policy` (
  `category` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `priority` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `response_h` smallint NOT NULL,
  `resolution_h` smallint NOT NULL,
  `escalate_after_h` smallint NOT NULL,
  `id` int NOT NULL AUTO_INCREMENT,
  `uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` tinyint(1) NOT NULL,
  `infos` json DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uk_sla_cat_prio` (`category`,`priority`),
  UNIQUE KEY `uuid` (`uuid`),
  KEY `idx_sla_status` (`status`,`deleted_at`)
) ENGINE=InnoDB AUTO_INCREMENT=94 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Déchargement des données de la table `sla_policy`
--

INSERT INTO `sla_policy` (`category`, `priority`, `response_h`, `resolution_h`, `escalate_after_h`, `id`, `uuid`, `status`, `infos`, `created_at`, `updated_at`, `deleted_at`) VALUES
('incident', 'low', 24, 72, 96, 1, '315014bb-1efa-42cf-a974-95502ca80b40', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('incident', 'medium', 8, 48, 60, 2, 'f32b8932-88fb-44b9-ba50-b75c4e61091a', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('incident', 'high', 2, 24, 30, 3, '56ab1313-63c9-4fd5-8693-b48e5ab324ac', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('incident', 'critical', 1, 4, 6, 4, '512c9223-f44c-4704-a2b0-123faad5c029', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('demande_service', 'low', 24, 72, 96, 5, '1aa3e9cf-1742-4d53-8706-3ce88472f1e9', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('demande_service', 'medium', 8, 48, 60, 6, 'b5d1d40c-b864-4e82-b53a-97de959d2785', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('demande_service', 'high', 2, 24, 30, 7, '84cf5c6f-73cf-4593-83e9-0b2878ca1a0b', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('demande_service', 'critical', 1, 4, 6, 8, 'eae135f5-08b2-4bc1-8f76-ffe026b5b897', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('maintenance_si', 'low', 24, 72, 96, 9, '3a3d0624-aed9-4de1-9c92-a9d60d66a46a', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('maintenance_si', 'medium', 8, 48, 60, 10, 'e41fc717-42bf-48a8-b89e-28f9b90c236c', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('maintenance_si', 'high', 2, 24, 30, 11, 'c6f54580-7d10-4843-baf3-490541bc2526', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('maintenance_si', 'critical', 1, 4, 6, 12, 'ce925c97-3a2e-45e5-9354-5b17dc356fe3', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('reseau', 'low', 24, 72, 96, 13, '86284fbb-227a-4f57-b66a-bf6c5760c29d', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('reseau', 'medium', 8, 48, 60, 14, '8c00b046-186a-4cac-9909-1e7a1aef090f', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('reseau', 'high', 2, 24, 30, 15, '2214cb59-4dcb-40a7-b2f0-502dc88ed6f8', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('reseau', 'critical', 1, 4, 6, 16, '406d31da-1e34-4301-9cde-4286568678df', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('habilitation', 'low', 24, 72, 96, 17, '8cf98eed-d152-4a08-af48-705a970c6d12', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('habilitation', 'medium', 8, 48, 60, 18, '2d5d7d65-5502-4442-9b74-801bc564c23c', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('habilitation', 'high', 2, 24, 30, 19, 'cb5682e3-4fc9-47da-a28e-37a37c4ab236', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('habilitation', 'critical', 1, 4, 6, 20, '62377f39-b311-4a71-af03-8b14df46beb1', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('securite', 'low', 24, 72, 96, 21, 'e5d4ac72-8968-4722-8c10-04d3dd81086c', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('securite', 'medium', 8, 48, 60, 22, '150aa2c3-6b81-42a5-9b8d-5dd682f33a7c', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('securite', 'high', 2, 24, 30, 23, '052a982f-c86a-4b9c-99e2-0f4f30afdc76', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('securite', 'critical', 1, 4, 6, 24, '8b2febc8-1d84-4c76-bffc-0427cbd30481', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('materiel', 'low', 24, 72, 96, 25, '08643c0f-3164-4418-9e67-7bc98655ca3d', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('materiel', 'medium', 8, 48, 60, 26, '4de0f802-9312-41b8-a065-01397df112d7', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('materiel', 'high', 2, 24, 30, 27, '5e4ffcd8-4c52-43bb-bfb8-cd907e85bda4', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('materiel', 'critical', 1, 4, 6, 28, '5c8b6432-c981-4017-84e1-459685d7e004', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('logiciel', 'low', 24, 72, 96, 29, 'd108d3f3-c8fb-468b-916f-3170249fff1b', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('logiciel', 'medium', 8, 48, 60, 30, '5b7dd77e-5f87-49d0-9ad5-d90dcf7f2db9', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('logiciel', 'high', 2, 24, 30, 31, '4ba6d7fa-ca5a-4b5c-9f9b-4b60dceb965a', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('logiciel', 'critical', 1, 4, 6, 32, 'b7ce4c03-3c78-41c6-ae09-2fdaf0291363', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('branchement', 'low', 24, 72, 96, 33, '853899bb-facd-473e-b8ba-8152becd9b88', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('branchement', 'medium', 8, 48, 60, 34, '6a06feaa-7f27-42d6-be71-587f58657b97', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('branchement', 'high', 2, 24, 30, 35, '6ce15146-abca-4f88-bb67-e996ce9bea3d', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('branchement', 'critical', 1, 4, 6, 36, '84fee480-7ef9-486a-b3c0-233c612b5bec', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('panne', 'low', 24, 72, 96, 37, '0a06452f-0f01-40ac-a2f5-33ece93e4975', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('panne', 'medium', 8, 48, 60, 38, 'e28fedc8-b35e-412d-9d4c-a4922458b33c', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('panne', 'high', 2, 24, 30, 39, '8ef4f8ed-e989-4050-96b0-2f44fb936bba', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('panne', 'critical', 1, 4, 6, 40, 'fdbf92cb-5c2a-4659-93e8-b973ba499b09', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('facturation', 'low', 24, 72, 96, 41, 'd571c721-d4eb-4232-80b8-92f47231ca1a', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('facturation', 'medium', 8, 48, 60, 42, '689560f2-8f2d-4a25-ac65-a0360dcb7327', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('facturation', 'high', 2, 24, 30, 43, '887ea676-8867-4ce9-b5e6-728d93fec728', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('facturation', 'critical', 1, 4, 6, 44, '1643de2a-1182-4b12-900c-f44d1a713808', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('compteur', 'low', 24, 72, 96, 45, '3b2095f9-1f68-4027-9f9a-6aa01c0a58b3', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('compteur', 'medium', 8, 48, 60, 46, 'b9656f16-5be9-4240-8f9b-b223bcfddde5', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('compteur', 'high', 2, 24, 30, 47, '7b5e5a9b-e5fb-4a8e-9e14-57466380b404', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('compteur', 'critical', 1, 4, 6, 48, '80423760-f4a5-48a3-88a8-4acf097ab74d', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('reclamation', 'low', 24, 72, 96, 49, '1b8823d0-8866-4363-875a-6ffc76eeb55a', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('reclamation', 'medium', 8, 48, 60, 50, 'c49fc5ef-cde4-493d-b57f-b2c18e3d3146', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('reclamation', 'high', 2, 24, 30, 51, '49b1298a-c457-44a3-b896-97643105e4f2', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('reclamation', 'critical', 1, 4, 6, 52, '2e84bb74-6cf2-46ec-987d-9b506c5a0220', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('information', 'low', 24, 72, 96, 53, '7ff718a9-1bc0-448d-9e5e-ef61dbb1935c', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('information', 'medium', 8, 48, 60, 54, 'e51caa3f-21f7-4a98-b823-d1168aafdd90', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('information', 'high', 2, 24, 30, 55, '9ac87e90-33d5-40bf-81d5-3e62663469d5', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('information', 'critical', 1, 4, 6, 56, '85da7fe2-8dab-43ff-abde-92dec49d5175', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('acces_applicatif', 'low', 24, 72, 96, 57, '153e71a6-a32d-47b4-bc42-d23a34a3dbec', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('acces_applicatif', 'medium', 8, 48, 60, 58, 'a5da98a2-959a-49c0-8808-9fd79f743c66', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('acces_applicatif', 'high', 2, 24, 30, 59, 'b6e01123-263c-4330-a031-0dde49153f6e', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('acces_applicatif', 'critical', 1, 4, 6, 60, 'e66b0ae1-42e1-4102-8985-8ccd3d912ce3', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('incident_technique', 'low', 24, 72, 96, 61, '41e81224-171b-4c4f-b3a4-9a9f1b4557a8', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('incident_technique', 'medium', 8, 48, 60, 62, 'acb98798-9473-42ed-aacd-48045518b403', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('incident_technique', 'high', 2, 24, 30, 63, 'f48c5016-22fa-490f-997c-a134cd128b69', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('incident_technique', 'critical', 1, 4, 6, 64, 'b002371e-db09-4577-afc4-17f9e475e6fb', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('paie', 'low', 24, 72, 96, 65, 'a6db4d00-770c-4e53-8bba-6dade081a5c1', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('paie', 'medium', 8, 48, 60, 66, 'f8c0922d-bd89-4529-8be2-200505e99591', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('paie', 'high', 2, 24, 30, 67, '31331592-bbef-4773-b134-1677c5a70718', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('paie', 'critical', 1, 4, 6, 68, 'df6ee77c-b252-42c0-82b7-20deef47631c', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('carrieres', 'low', 24, 72, 96, 69, 'a135af4f-5156-4df0-a300-338539926a98', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('carrieres', 'medium', 8, 48, 60, 70, '48a2fafc-bfab-4360-b40e-09cbc0aa3dce', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('carrieres', 'high', 2, 24, 30, 71, '8ddbe14a-3b12-495a-8ca1-891cedc50e95', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('carrieres', 'critical', 1, 4, 6, 72, '824a18ca-0e28-48ae-9889-f2085cb91cb3', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('budget', 'low', 24, 72, 96, 73, '887e68fa-7a9e-40b6-b26c-c87845fe1710', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('budget', 'medium', 8, 48, 60, 74, '357a68bb-30ad-467f-83dc-02c4f2126eda', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('budget', 'high', 2, 24, 30, 75, '2cf3cb24-b9f8-491d-9301-26c5e40f1b04', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('budget', 'critical', 1, 4, 6, 76, 'a0439bfb-1c62-460a-9439-cd2458220b23', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('document_administratif', 'low', 24, 72, 96, 77, '4802a312-8188-40a3-bcbb-aa30aa456d8b', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('document_administratif', 'medium', 8, 48, 60, 78, 'bcc4511c-2a44-413a-9911-fbd28bfb871f', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('document_administratif', 'high', 2, 24, 30, 79, '367e9f25-df7b-4ec1-a088-55223715509b', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('document_administratif', 'critical', 1, 4, 6, 80, '9c793299-c268-4b2c-a1fd-1d339556d0d6', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('formation', 'low', 24, 72, 96, 81, '4d910ea9-9a4a-4107-b7ef-1e1a9feb36ae', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('formation', 'medium', 8, 48, 60, 82, '3a452e9c-b0c8-48b0-9a2f-e8dcaec524ca', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('formation', 'high', 2, 24, 30, 83, '3dbd6e62-79d4-4d38-a470-31044bd17ed6', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('formation', 'critical', 1, 4, 6, 84, 'a87e904f-d32e-4d7e-ba65-62a1cef14aff', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('equipement', 'low', 24, 72, 96, 85, 'b8176699-b751-4422-9811-50765e0617c5', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('equipement', 'medium', 8, 48, 60, 86, 'ba659241-60a1-4680-8fe5-458d7ad26c7e', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('equipement', 'high', 2, 24, 30, 87, '99c593e4-f70a-4b20-85d7-9e2666e6d762', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('equipement', 'critical', 1, 4, 6, 88, '27317231-7663-4189-b70e-ac9f82fc6bac', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('autre', 'low', 24, 72, 96, 89, 'a516efd4-b395-4e7e-afb3-064294dc02e2', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('autre', 'medium', 8, 48, 60, 90, 'e75097b7-884a-4311-92d7-bfc68427648d', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('autre', 'high', 2, 24, 30, 91, '570c3745-263e-4ff2-b19e-5c2a38ea047f', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL),
('autre', 'critical', 1, 4, 6, 92, '80f31beb-c1ec-47f8-aa88-5ea40b547f4f', 1, NULL, '2026-07-04 17:49:03', '2026-07-04 17:49:03', NULL);

-- --------------------------------------------------------

--
-- Structure de la table `task`
--

DROP TABLE IF EXISTS `task`;
CREATE TABLE IF NOT EXISTS `task` (
  `request_id` int NOT NULL,
  `from_agent_id` int DEFAULT NULL,
  `to_agent_id` int DEFAULT NULL,
  `from_unit_id` int DEFAULT NULL,
  `to_unit_id` int DEFAULT NULL,
  `task_type` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `reason` text COLLATE utf8mb4_unicode_ci,
  `task_status` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `id` int NOT NULL AUTO_INCREMENT,
  `uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` tinyint(1) NOT NULL,
  `infos` json DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uuid` (`uuid`),
  KEY `from_agent_id` (`from_agent_id`),
  KEY `to_agent_id` (`to_agent_id`),
  KEY `from_unit_id` (`from_unit_id`),
  KEY `to_unit_id` (`to_unit_id`),
  KEY `idx_task_req` (`request_id`),
  KEY `idx_task_tstatus` (`task_status`),
  KEY `idx_task_status` (`status`,`deleted_at`)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

-- --------------------------------------------------------

--
-- Structure de la table `unity`
--

DROP TABLE IF EXISTS `unity`;
CREATE TABLE IF NOT EXISTS `unity` (
  `label` varchar(200) COLLATE utf8mb4_unicode_ci NOT NULL,
  `codename` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `aleas` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `description` text COLLATE utf8mb4_unicode_ci,
  `id` int NOT NULL AUTO_INCREMENT,
  `uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` tinyint(1) NOT NULL,
  `infos` json DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  `deleted_at` datetime DEFAULT NULL,
  `parent_direction_id` int DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `codename` (`codename`),
  UNIQUE KEY `uuid` (`uuid`),
  KEY `idx_unity_status` (`status`,`deleted_at`),
  KEY `idx_unity_codename` (`codename`),
  KEY `idx_unity_parent_dir` (`parent_direction_id`)
) ENGINE=InnoDB AUTO_INCREMENT=46 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Déchargement des données de la table `unity`
--

INSERT INTO `unity` (`label`, `codename`, `aleas`, `description`, `id`, `uuid`, `status`, `infos`, `created_at`, `updated_at`, `deleted_at`, `parent_direction_id`) VALUES
('Direction Générale', 'DG', 'DG', NULL, 1, '14b9daf1-0ceb-469c-9ce6-578b1d8b847a', 0, NULL, '2026-06-25 19:11:44', '2026-07-27 13:13:11', NULL, NULL),
('Direction Commerciale', 'DC', 'DC', NULL, 2, '099d78c0-cafa-4538-975c-a1e7dd8bf0c3', 0, NULL, '2026-06-25 19:11:44', '2026-07-23 14:37:51', NULL, NULL),
('Direction Technique', 'DT', 'DT', NULL, 3, '91753ac0-57c9-4a3d-9261-8009abc005cd', 0, NULL, '2026-06-25 19:11:44', '2026-07-23 14:37:56', NULL, NULL),
('Direction des Ressources Humaines', 'DRH', 'DRH', NULL, 4, '341064b9-fe10-425f-83e9-b3caa842224f', 0, NULL, '2026-06-25 19:11:44', '2026-07-23 14:38:01', NULL, NULL),
('Direction Financière', 'DF', 'DF', NULL, 5, '2406fff6-2c2d-4e2b-90af-5a593b5176c6', 0, NULL, '2026-06-25 19:11:44', '2026-07-23 14:38:07', NULL, NULL),
('Direction des Systèmes d\'Information', 'DSI', 'DSI', NULL, 6, 'c1f1dea9-f3a3-4cd2-8414-8b297cd54306', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL, NULL),
('Direction de la Maintenance', 'DM', 'DM', NULL, 7, 'a43fc121-78e6-4e3a-bdb8-4334b332b71b', 0, NULL, '2026-06-25 19:11:44', '2026-07-23 14:38:16', NULL, NULL),
('Direction des Infrastructures', 'DI', 'DI', NULL, 8, '290ab6f2-ac4f-41d5-aa7a-a3b3a5cdad80', 0, NULL, '2026-06-25 19:11:44', '2026-07-23 14:38:21', NULL, NULL),
('Direction des Affaires Juridiques', 'DIAJ', 'DIAJ', NULL, 9, 'b697df3d-7263-40ca-8155-07e0af8b70fa', 0, NULL, '2026-06-25 19:11:44', '2026-07-23 12:40:22', NULL, NULL),
('Direction Qualité & Environnement', 'DQE', 'DQE', NULL, 10, '4bb86704-97c6-49f8-abef-0e2f2ae6da1b', 0, NULL, '2026-06-25 19:11:44', '2026-07-23 14:38:27', NULL, NULL),
('Secrétariat DSI', 'DSI-SEC', 'SEC', NULL, 11, '7bffa91a-93f5-41c5-b53a-f4fa29eac879', 1, '{\"org_type\": \"unit\"}', '2026-06-25 19:11:44', '2026-07-27 11:20:58', NULL, 6),
('Service d\'Appui DSI', 'DSI-APP', 'APPUI', NULL, 12, '6138bf4e-8b5e-46a3-88f7-3c3417060c6a', 1, '{\"org_type\": \"unit\"}', '2026-06-25 19:11:44', '2026-07-27 11:20:16', NULL, 6),
('Département Étude et Développement', 'DSI-DED', 'ED', NULL, 13, '9ddf1576-a327-4fcb-a7c5-7572a2e7a2c2', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL, NULL),
('Département Exploitation', 'DSI-DEX', 'EXP', NULL, 14, 'b5d42d30-2cb1-4d69-8404-1c2fd14e77ca', 1, '{\"org_type\": \"department\"}', '2026-06-25 19:11:44', '2026-07-23 14:40:48', NULL, 6),
('Département Infrastructure et Réseau', 'DSI-DIR', 'INR', NULL, 15, 'dc7024dd-c0d0-4c2a-8a2b-a30c3359bd77', 1, NULL, '2026-06-25 19:11:44', '2026-06-25 19:11:44', NULL, NULL),
('Service Étude & Digitalisation', 'DSI-SED', 'SED', NULL, 16, 'c3920cc7-33bd-4eb0-9025-a324ad0bf6e9', 1, NULL, '2026-06-25 19:11:44', '2026-07-23 11:13:50', NULL, NULL),
('Service Maintenance', 'DSI-SMT', 'SMNT', NULL, 17, '15b58b89-d7ec-490e-a5c7-8df38df82ef4', 1, '{\"org_type\": \"unit\"}', '2026-06-25 19:11:44', '2026-07-27 11:21:18', NULL, 6),
('Service Support', 'DSI-SSP', 'SUP', NULL, 18, '8825ad8b-fe43-4235-8964-0ea8bba6cdb5', 1, '{\"org_type\": \"unit\"}', '2026-06-25 19:11:44', '2026-07-27 11:21:56', NULL, 6),
('Service Réseau & Cybersécurité', 'DSI-SRC', 'SRC', NULL, 19, 'bb5d1af4-a626-4c97-b2a7-fd8e60ebb2a1', 1, '{\"org_type\": \"unit\"}', '2026-06-25 19:11:44', '2026-07-27 11:22:48', NULL, 6),
('Service Système & Habilitation', 'DSI-SSH', 'SSH', NULL, 20, '4175d270-ed1a-479f-84f3-52e573d43940', 1, '{\"org_type\": \"unit\"}', '2026-06-25 19:11:44', '2026-07-27 11:22:19', NULL, 6),
('Service Clientèle', 'DC-SC', 'SC', NULL, 21, 'ad682853-daac-4206-9ab4-0b29f831fe51', 0, NULL, '2026-06-25 19:11:44', '2026-07-23 14:37:51', NULL, NULL),
('Service Facturation', 'DC-SF', 'SF', NULL, 22, 'fc445531-c152-4525-bbf5-473bbf729270', 0, NULL, '2026-06-25 19:11:44', '2026-07-23 14:37:51', NULL, NULL),
('Service Recouvrement', 'DC-SR', 'SR', NULL, 23, 'eb2beee4-c88d-4984-8afc-4decda2e3710', 0, NULL, '2026-06-25 19:11:44', '2026-07-23 14:37:51', NULL, NULL),
('Service Commercial', 'DC-SCO', 'SCO', NULL, 24, '68b42da6-ce8a-4752-83ab-c42e99d0c58a', 0, NULL, '2026-06-25 19:11:44', '2026-07-23 14:37:51', NULL, NULL),
('Service Distribution', 'DT-SD', 'SD', NULL, 25, '6a0db9b2-146f-4e8b-803e-5fda469a9ed9', 0, NULL, '2026-06-25 19:11:44', '2026-07-23 14:37:56', NULL, NULL),
('Service Transport', 'DT-ST', 'ST', NULL, 26, '43f6a099-75c2-474d-ba4e-2e86feee4b51', 0, NULL, '2026-06-25 19:11:44', '2026-07-23 14:37:56', NULL, NULL),
('Service Production', 'DT-SP', 'SP', NULL, 27, '9bbafed8-21a4-4cfe-b463-623a2533eb61', 0, NULL, '2026-06-25 19:11:44', '2026-07-23 14:37:56', NULL, NULL),
('Service Métrologie', 'DT-SM', 'SM', NULL, 28, 'ba7a3020-8ef6-4e80-9874-b1caf4b33a7a', 0, NULL, '2026-06-25 19:11:44', '2026-07-23 14:37:56', NULL, NULL),
('Service Formation', 'DRH-SF', 'SF', NULL, 29, '818c5033-2c30-41ed-b7f9-a949cfb401aa', 0, NULL, '2026-06-25 19:11:44', '2026-07-23 14:38:01', NULL, NULL),
('Service Administration du Personnel', 'DRH-SAP', 'SAP', NULL, 30, '6c06710e-1ee9-4dc7-ae20-acea024bc5e9', 0, NULL, '2026-06-25 19:11:44', '2026-07-23 14:38:01', NULL, NULL),
('Service Recrutement', 'DRH-SRE', 'SRE', NULL, 31, '75a031ff-06e3-4740-99ad-fb5b047f8210', 0, NULL, '2026-06-25 19:11:44', '2026-07-23 14:38:01', NULL, NULL),
('Service Comptabilité', 'DF-SCO', 'SCO', NULL, 32, '97d7f231-1450-4ad8-9104-e99f60538f96', 0, NULL, '2026-06-25 19:11:44', '2026-07-23 14:38:07', NULL, NULL),
('Service Budget & Contrôle', 'DF-SBG', 'SBG', NULL, 33, '0d01e31d-bf03-491f-b5ba-81372008a08b', 0, NULL, '2026-06-25 19:11:44', '2026-07-23 14:38:07', NULL, NULL),
('Service Trésorerie', 'DF-STR', 'STR', NULL, 34, '94d5feab-3f42-46cc-baf0-ea2f7b528338', 0, NULL, '2026-06-25 19:11:44', '2026-07-23 14:38:07', NULL, NULL),
('Service Maintenance Réseau', 'DM-SMR', 'SMR', NULL, 35, '75330df3-c3d9-490e-b8f7-2d0cb856a1e5', 0, NULL, '2026-06-25 19:11:44', '2026-07-23 14:38:16', NULL, NULL),
('Service Maintenance Équipements', 'DM-SME', 'SME', NULL, 36, 'ec21ef95-8859-4e02-a5c0-4969dfca2f14', 0, NULL, '2026-06-25 19:11:44', '2026-07-23 14:38:16', NULL, NULL),
('Service Logistique', 'DM-SL', 'SL', NULL, 37, 'b814dc66-3bf4-4a37-85f9-0cd646a99bb1', 0, NULL, '2026-06-25 19:11:44', '2026-07-23 14:38:16', NULL, NULL),
('Service Études & Travaux', 'DI-SET', 'SET', NULL, 38, '1102a465-7b36-4b31-9b3e-6d1bd3c6996a', 0, NULL, '2026-06-25 19:11:44', '2026-07-23 14:38:22', NULL, NULL),
('Service Supervision', 'DI-SSU', 'SSU', NULL, 39, '54a88c0a-97f7-4055-ade7-fb2d7c594e0f', 0, NULL, '2026-06-25 19:11:44', '2026-07-23 14:38:22', NULL, NULL),
('Service Contentieux', 'DIAJ-SCT', 'SCT', NULL, 40, '2d433f43-2c2c-465e-b50c-771e43069829', 0, NULL, '2026-06-25 19:11:44', '2026-07-23 12:40:22', NULL, NULL),
('Service Contrats', 'DIAJ-SCN', 'SCN', NULL, 41, '50116395-5619-4f3d-bd06-4982ade1ef26', 0, NULL, '2026-06-25 19:11:44', '2026-07-23 12:40:22', NULL, NULL),
('Cabinet du Directeur Général', 'DG-CAB', 'CAB', NULL, 42, '837fc3be-477a-4e13-bca6-765e21b99bcb', 0, NULL, '2026-06-25 19:11:44', '2026-07-23 12:39:51', NULL, NULL),
('Service Communication', 'DG-COM', 'COM', NULL, 43, '17a9b835-81db-41b5-9463-468d4885b8b5', 0, NULL, '2026-06-25 19:11:44', '2026-07-23 12:39:51', NULL, NULL),
('TEST-SERVICE-AUDIT', 'TEST-SVC-AUDIT', NULL, NULL, 45, 'be221645-3da7-455f-ad86-187dd77297ee', 1, 'null', '2026-07-05 14:39:49', '2026-07-05 14:40:38', '2026-07-05 14:40:38', 4);

-- --------------------------------------------------------

--
-- Structure de la table `workflow`
--

DROP TABLE IF EXISTS `workflow`;
CREATE TABLE IF NOT EXISTS `workflow` (
  `request_id` int NOT NULL,
  `workflow_status` varchar(50) COLLATE utf8mb4_unicode_ci NOT NULL,
  `id` int NOT NULL AUTO_INCREMENT,
  `uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` tinyint(1) NOT NULL,
  `infos` json DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uuid` (`uuid`),
  KEY `idx_wf_req` (`request_id`),
  KEY `idx_wf_status` (`status`,`deleted_at`)
) ENGINE=InnoDB AUTO_INCREMENT=12 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Déchargement des données de la table `workflow`
--

INSERT INTO `workflow` (`request_id`, `workflow_status`, `id`, `uuid`, `status`, `infos`, `created_at`, `updated_at`, `deleted_at`) VALUES
(1, 'active', 1, '393f5db1-273d-4618-a123-054a3c2d7cad', 1, NULL, '2026-08-12 10:07:50', '2026-08-12 10:07:50', NULL),
(2, 'active', 2, '4dcc1388-9724-4f9d-93f7-9598912b8a6c', 1, NULL, '2026-08-12 17:37:03', '2026-08-12 17:37:03', NULL),
(3, 'active', 3, '3771c0ca-d308-45f3-bd06-3bfefc370014', 1, NULL, '2026-08-13 11:03:36', '2026-08-13 11:03:36', NULL),
(4, 'active', 4, '1f7f6422-b46d-45bf-95e4-03df294ce782', 1, NULL, '2026-08-14 11:05:44', '2026-08-14 11:05:44', NULL),
(5, 'active', 5, '4165ef80-1411-4cde-897d-fbb33534e0ef', 1, NULL, '2026-08-14 11:43:26', '2026-08-14 11:43:26', NULL),
(6, 'active', 6, '1a22e045-62f0-4ecc-9dee-68363c6f32d0', 1, NULL, '2026-08-14 13:28:44', '2026-08-14 13:28:44', NULL),
(7, 'active', 7, '84637068-8559-4c0a-a5e5-2879fa336dbd', 1, NULL, '2026-08-15 12:05:15', '2026-08-15 12:05:15', NULL),
(8, 'active', 8, '7d751413-e075-4b32-81e9-7c58e43ae8a0', 1, NULL, '2026-08-15 12:07:43', '2026-08-15 12:07:43', NULL),
(9, 'active', 9, '1aec7bf9-3e18-446e-bc3b-3efd50fa9886', 1, NULL, '2026-08-19 09:41:10', '2026-08-19 09:41:10', NULL),
(10, 'active', 10, '374418ba-253e-4dcf-976c-323627a8dd4b', 1, NULL, '2026-08-27 12:05:16', '2026-08-27 12:05:16', NULL),
(11, 'active', 11, '7a76ca17-d784-43c0-aaf1-96af1c1d281d', 1, NULL, '2026-08-27 15:10:29', '2026-08-27 15:10:29', NULL);

-- --------------------------------------------------------

--
-- Structure de la table `workflow_detail`
--

DROP TABLE IF EXISTS `workflow_detail`;
CREATE TABLE IF NOT EXISTS `workflow_detail` (
  `workflow_id` int DEFAULT NULL,
  `unity_id` int DEFAULT NULL,
  `agent_id` int DEFAULT NULL,
  `task_id` int DEFAULT NULL,
  `parent_id` int DEFAULT NULL,
  `event_type` varchar(50) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `label` varchar(500) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `actor_name` varchar(200) COLLATE utf8mb4_unicode_ci DEFAULT NULL,
  `accepted` tinyint(1) DEFAULT NULL,
  `activated` tinyint(1) NOT NULL,
  `comment` text COLLATE utf8mb4_unicode_ci,
  `id` int NOT NULL AUTO_INCREMENT,
  `uuid` varchar(36) COLLATE utf8mb4_unicode_ci NOT NULL,
  `status` tinyint(1) NOT NULL,
  `infos` json DEFAULT NULL,
  `created_at` datetime NOT NULL DEFAULT (now()),
  `updated_at` datetime NOT NULL DEFAULT (now()),
  `deleted_at` datetime DEFAULT NULL,
  PRIMARY KEY (`id`),
  UNIQUE KEY `uuid` (`uuid`),
  KEY `unity_id` (`unity_id`),
  KEY `agent_id` (`agent_id`),
  KEY `task_id` (`task_id`),
  KEY `parent_id` (`parent_id`),
  KEY `idx_wfd_wf` (`workflow_id`),
  KEY `idx_wfd_status` (`status`,`deleted_at`),
  KEY `idx_wfd_event_type` (`event_type`,`deleted_at`)
) ENGINE=InnoDB AUTO_INCREMENT=45 DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

--
-- Déchargement des données de la table `workflow_detail`
--

INSERT INTO `workflow_detail` (`workflow_id`, `unity_id`, `agent_id`, `task_id`, `parent_id`, `event_type`, `label`, `actor_name`, `accepted`, `activated`, `comment`, `id`, `uuid`, `status`, `infos`, `created_at`, `updated_at`, `deleted_at`) VALUES
(1, NULL, 2, NULL, NULL, 'created', 'Demande créée par l\'utilisateur', 'GASPARD GOEPOGUI', NULL, 1, NULL, 1, '5457c76b-7436-4a9b-b535-19439cd3aab9', 1, '{\"reason\": null, \"actor_id\": \"2\", \"actor_role\": \"admin\", \"new_status\": \"new\", \"old_status\": null, \"source_role\": \"admin\", \"target_role\": null, \"event_status\": \"new\", \"target_user_id\": null}', '2026-08-12 10:07:50', '2026-08-12 10:07:50', NULL),
(1, NULL, 2, NULL, 1, 'routed_to_support', 'Aucune règle de routage — envoi au support général', 'GASPARD GOEPOGUI', NULL, 1, NULL, 2, 'ecd05550-4ab7-4297-95f7-e492c172ed0d', 1, '{\"reason\": null, \"actor_id\": \"2\", \"dest_role\": \"support\", \"actor_role\": \"admin\", \"new_status\": \"qualifying\", \"old_status\": \"new\", \"source_role\": \"admin\", \"target_role\": \"support\", \"event_status\": \"to_qualify\", \"target_user_id\": null}', '2026-08-12 10:07:50', '2026-08-12 10:07:50', NULL),
(1, NULL, 7, NULL, 2, 'in_progress', 'Pris en charge par Jams jamsatou1 — traitement démarré', 'Jams jamsatou1', NULL, 1, NULL, 3, '4b640090-3a1d-426f-ae4a-af7f0a549bbe', 1, '{\"reason\": null, \"actor_id\": \"7\", \"actor_role\": \"agent-support\", \"new_status\": \"in_progress\", \"old_status\": \"in_progress\", \"source_role\": \"agent-support\", \"target_role\": null, \"event_status\": \"in_progress\", \"changed_fields\": [\"assignee_id\", \"category\", \"in_triage\", \"infos\", \"priority\", \"request_status\", \"unity_id\"], \"target_user_id\": null, \"intervention_id\": \"req1-c1-i1\", \"intervention_order\": 1, \"actor_service_label\": \"Service Étude & Digitalisation\", \"actor_direction_label\": \"Direction des Systèmes d\'Information\", \"intervention_actor_id\": \"7\", \"actor_department_label\": \"Département Étude et Développement\", \"intervention_actor_name\": \"Jams jamsatou1\", \"intervention_actor_role\": \"agent-support\", \"intervention_cycle_number\": 1}', '2026-08-12 11:35:42', '2026-08-12 11:35:42', NULL),
(1, NULL, 6, NULL, 3, 'treatment_transmitted', 'Traitement transmis à AMADOU TOURE', 'Jams jamsatou1', NULL, 1, 'ttttttttttttttttteee', 4, '87f3a2fe-7687-4245-840e-fac652261f16', 1, '{\"reason\": \"ttttttttttttttttteee\", \"actor_id\": \"7\", \"ended_at\": \"2026-08-12T12:56:28.730791\", \"dest_role\": \"agent-support\", \"work_done\": \"yyyyyyyyyyyyyyyyyy\", \"actor_role\": \"agent-support\", \"new_status\": \"in_progress\", \"old_status\": \"in_progress\", \"started_at\": \"2026-08-12T10:07:49\", \"instruction\": \"eeeeeeeeeeeeeeeeeeeeeeeeeeeeeee\", \"source_role\": \"agent-support\", \"target_role\": \"agent-support\", \"cycle_number\": 1, \"target_user_id\": \"6\", \"intervention_id\": \"req1-c1-i1\", \"new_assignee_id\": 6, \"duration_seconds\": 10119, \"target_user_name\": \"AMADOU TOURE\", \"next_intervention\": {\"started_at\": \"2026-08-12T12:56:28.730791\", \"intervention_id\": \"req1-c1-i2\", \"intervention_order\": 2, \"actor_service_label\": \"Service Étude & Digitalisation\", \"actor_direction_label\": \"Direction des Systèmes d\'Information\", \"intervention_actor_id\": \"6\", \"actor_department_label\": \"Département Étude et Développement\", \"intervention_actor_name\": \"AMADOU TOURE\", \"intervention_actor_role\": \"agent-support\", \"intervention_cycle_number\": 1}, \"intervention_order\": 1, \"actor_service_label\": \"Service Étude & Digitalisation\", \"previous_assignee_id\": 7, \"actor_direction_label\": \"Direction des Systèmes d\'Information\", \"intervention_actor_id\": \"7\", \"actor_department_label\": \"Département Étude et Développement\", \"intervention_actor_name\": \"Jams jamsatou1\", \"intervention_actor_role\": \"agent-support\", \"intervention_cycle_number\": 1}', '2026-08-12 12:56:29', '2026-08-12 12:56:29', NULL),
(2, NULL, 5, NULL, NULL, 'created', 'Demande créée par l\'utilisateur', 'GASPARD KAMAN GOEPOGUI', NULL, 1, NULL, 5, 'de82901d-7e8e-40c4-8645-a1763cfd9587', 1, '{\"reason\": null, \"actor_id\": \"5\", \"actor_role\": \"user\", \"new_status\": \"new\", \"old_status\": null, \"source_role\": \"user\", \"target_role\": null, \"event_status\": \"new\", \"target_user_id\": null}', '2026-08-12 17:37:03', '2026-08-12 17:37:03', NULL),
(2, NULL, 5, NULL, 5, 'routed_to_support', 'Aucune règle de routage — envoi au support général', 'GASPARD KAMAN GOEPOGUI', NULL, 1, NULL, 6, '395b0b1f-a53e-497c-9457-f1c37a4ecfa2', 1, '{\"reason\": null, \"actor_id\": \"5\", \"dest_role\": \"support\", \"actor_role\": \"user\", \"new_status\": \"qualifying\", \"old_status\": \"new\", \"source_role\": \"user\", \"target_role\": \"support\", \"event_status\": \"to_qualify\", \"target_user_id\": null}', '2026-08-12 17:37:04', '2026-08-12 17:37:04', NULL),
(2, NULL, 5, NULL, 6, 'cancelled', 'Demande annulée — mon problème est resolue correctement', 'GASPARD KAMAN GOEPOGUI', NULL, 1, 'mon problème est resolue correctement', 7, '39d3277d-b5c6-4cf4-81d9-decfd05d0eac', 1, '{\"reason\": \"mon problème est resolue correctement\", \"actor_id\": \"5\", \"actor_role\": \"user\", \"new_status\": \"cancelled\", \"old_status\": \"cancelled\", \"source_role\": \"user\", \"target_role\": null, \"event_status\": \"cancelled\", \"target_user_id\": null}', '2026-08-13 09:49:01', '2026-08-13 09:49:01', NULL),
(1, NULL, 2, NULL, 4, 'cancelled', 'Demande annulée — mon problème est resolut', 'GASPARD GOEPOGUI', NULL, 1, 'mon problème est resolut', 8, '7fdf1a72-26ba-4f4b-af1c-a938768e5d6c', 1, '{\"reason\": \"mon problème est resolut\", \"actor_id\": \"2\", \"actor_role\": \"admin\", \"new_status\": \"cancelled\", \"old_status\": \"cancelled\", \"source_role\": \"admin\", \"target_role\": null, \"event_status\": \"cancelled\", \"target_user_id\": null}', '2026-08-13 10:22:17', '2026-08-13 10:22:17', NULL),
(3, NULL, 2, NULL, NULL, 'created', 'Demande créée par l\'utilisateur', 'GASPARD GOEPOGUI', NULL, 1, NULL, 9, '042d0b3f-61d8-4b66-ac75-9bcc897d1448', 1, '{\"reason\": null, \"actor_id\": \"2\", \"actor_role\": \"admin\", \"new_status\": \"new\", \"old_status\": null, \"source_role\": \"admin\", \"target_role\": null, \"event_status\": \"new\", \"target_user_id\": null}', '2026-08-13 11:03:36', '2026-08-13 11:03:36', NULL),
(3, NULL, 2, NULL, 9, 'routed_to_support', 'Aucune règle de routage — envoi au support général', 'GASPARD GOEPOGUI', NULL, 1, NULL, 10, 'da3f58fb-5738-4e75-a401-62d987646f0c', 1, '{\"reason\": null, \"actor_id\": \"2\", \"dest_role\": \"support\", \"actor_role\": \"admin\", \"new_status\": \"qualifying\", \"old_status\": \"new\", \"source_role\": \"admin\", \"target_role\": \"support\", \"event_status\": \"to_qualify\", \"target_user_id\": null}', '2026-08-13 11:03:38', '2026-08-13 11:03:38', NULL),
(3, NULL, 2, NULL, 10, 'attachment_added', 'Pièce jointe ajoutée — edg recrutement.jpg', 'GASPARD GOEPOGUI', NULL, 1, NULL, 11, '7e0558c1-55e6-421d-b0a6-002afbc01c9c', 1, '{\"reason\": null, \"actor_id\": \"2\", \"filename\": \"edg recrutement.jpg\", \"mime_type\": \"image/jpeg\", \"actor_role\": \"admin\", \"new_status\": null, \"old_status\": null, \"size_bytes\": 66482, \"scan_status\": \"clean\", \"source_role\": \"admin\", \"target_role\": null, \"event_status\": \"qualifying\", \"attachment_id\": \"1\", \"request_status\": \"qualifying\", \"target_user_id\": null}', '2026-08-13 11:03:43', '2026-08-13 11:03:43', NULL),
(3, NULL, 7, NULL, 11, 'in_progress', 'Pris en charge par Jams jamsatou1 — traitement démarré', 'Jams jamsatou1', NULL, 1, NULL, 12, '4f815653-df9f-49d9-8d1d-7683961f7cd5', 1, '{\"reason\": null, \"actor_id\": \"7\", \"actor_role\": \"agent-support\", \"new_status\": \"in_progress\", \"old_status\": \"in_progress\", \"source_role\": \"agent-support\", \"target_role\": null, \"event_status\": \"in_progress\", \"changed_fields\": [\"assignee_id\", \"category\", \"in_triage\", \"infos\", \"priority\", \"request_status\", \"unity_id\"], \"target_user_id\": null, \"intervention_id\": \"req3-c1-i1\", \"intervention_order\": 1, \"actor_service_label\": \"Service Étude & Digitalisation\", \"actor_direction_label\": \"Direction des Systèmes d\'Information\", \"intervention_actor_id\": \"7\", \"actor_department_label\": \"Département Étude et Développement\", \"intervention_actor_name\": \"Jams jamsatou1\", \"intervention_actor_role\": \"agent-support\", \"intervention_cycle_number\": 1}', '2026-08-13 11:06:55', '2026-08-13 11:06:55', NULL),
(3, NULL, 7, NULL, 12, 'comment_added', 'Commentaire public ajouté', 'Jams jamsatou1', NULL, 1, 'Pouvez-vous me faire savoir  ce qui ne march pas ?', 13, 'afde5185-10f8-470b-abc8-8e9df1c3fb2a', 1, '{\"reason\": null, \"actor_id\": \"7\", \"is_public\": true, \"actor_role\": \"agent-support\", \"new_status\": null, \"old_status\": null, \"visibility\": \"public\", \"source_role\": \"agent-support\", \"target_role\": null, \"event_status\": \"in_progress\", \"request_status\": \"in_progress\", \"target_user_id\": null, \"intervention_id\": \"req3-c1-i1\", \"intervention_order\": 1, \"intervention_cycle_number\": 1}', '2026-08-13 12:29:18', '2026-08-13 16:21:24', '2026-08-13 16:21:24'),
(3, NULL, 7, NULL, 13, 'pending', 'Informations complémentaires demandées', 'Jams jamsatou1', NULL, 1, NULL, 14, '509bd8e4-960b-452e-aefb-9100f94d0384', 1, '{\"reason\": null, \"actor_id\": \"7\", \"actor_role\": \"agent-support\", \"new_status\": \"pending\", \"old_status\": \"pending\", \"source_role\": \"agent-support\", \"target_role\": null, \"event_status\": \"pending\", \"changed_fields\": [\"request_status\"], \"target_user_id\": null}', '2026-08-13 12:29:23', '2026-08-13 12:29:23', NULL),
(3, NULL, 7, NULL, 14, 'in_progress', 'Prise en charge — traitement en cours', 'Jams jamsatou1', NULL, 1, NULL, 15, '86830d92-5d99-4d7c-80ca-683a12e8a6da', 1, '{\"reason\": null, \"actor_id\": \"7\", \"actor_role\": \"agent-support\", \"new_status\": \"in_progress\", \"old_status\": \"in_progress\", \"source_role\": \"agent-support\", \"target_role\": null, \"event_status\": \"in_progress\", \"changed_fields\": [\"request_status\"], \"target_user_id\": null}', '2026-08-13 12:31:02', '2026-08-13 12:31:02', NULL),
(3, NULL, 7, NULL, 15, 'comment_added', 'Commentaire public ajouté', 'Jams jamsatou1', NULL, 1, 'bonjour', 16, 'd96d87db-5b52-40e7-a49e-bab4ad3f0674', 1, '{\"reason\": null, \"actor_id\": \"7\", \"is_public\": true, \"actor_role\": \"agent-support\", \"new_status\": null, \"old_status\": null, \"visibility\": \"public\", \"source_role\": \"agent-support\", \"target_role\": null, \"event_status\": \"in_progress\", \"request_status\": \"in_progress\", \"target_user_id\": null, \"intervention_id\": \"req3-c1-i1\", \"intervention_order\": 1, \"intervention_cycle_number\": 1}', '2026-08-13 16:10:01', '2026-08-13 16:10:01', NULL),
(3, NULL, 2, NULL, 16, 'comment_added', 'Commentaire interne ajouté', 'GASPARD GOEPOGUI', NULL, 1, '@Jams jamsatou1 oui bonjour monsieur veuillez me dire le souci', 17, 'b2039176-e39c-43b0-af42-1a99adb3e403', 1, '{\"reason\": null, \"actor_id\": \"2\", \"is_public\": false, \"actor_role\": \"admin\", \"new_status\": null, \"old_status\": null, \"visibility\": \"internal\", \"reply_to_id\": \"16\", \"source_role\": \"admin\", \"target_role\": null, \"event_status\": \"in_progress\", \"request_status\": \"in_progress\", \"target_user_id\": null}', '2026-08-13 16:12:49', '2026-08-13 16:12:49', NULL),
(4, NULL, 7, NULL, NULL, 'created', 'Demande créée par l\'utilisateur', 'Jams jamsatou1', NULL, 1, NULL, 18, 'b5c300ba-456f-410b-8cec-7f06b210720f', 1, '{\"reason\": null, \"actor_id\": \"7\", \"actor_role\": \"agent-support\", \"new_status\": \"new\", \"old_status\": null, \"source_role\": \"agent-support\", \"target_role\": null, \"event_status\": \"new\", \"target_user_id\": null}', '2026-08-14 11:05:44', '2026-08-14 11:05:44', NULL),
(4, NULL, 7, NULL, 18, 'routed_to_support', 'Aucune règle de routage — envoi au support général', 'Jams jamsatou1', NULL, 1, NULL, 19, '42cce473-8671-42f5-af09-0cefb92702a8', 1, '{\"reason\": null, \"actor_id\": \"7\", \"dest_role\": \"support\", \"actor_role\": \"agent-support\", \"new_status\": \"qualifying\", \"old_status\": \"new\", \"source_role\": \"agent-support\", \"target_role\": \"support\", \"event_status\": \"to_qualify\", \"target_user_id\": null}', '2026-08-14 11:05:45', '2026-08-14 11:05:45', NULL),
(4, NULL, 7, NULL, 19, 'cancelled', 'Demande annulée — je suis deja satisfait', 'Jams jamsatou1', NULL, 1, 'je suis deja satisfait', 20, 'd16076f3-d275-4572-aa6a-9e9b74f83d4c', 1, '{\"reason\": \"je suis deja satisfait\", \"actor_id\": \"7\", \"actor_role\": \"agent-support\", \"new_status\": \"cancelled\", \"old_status\": \"cancelled\", \"source_role\": \"agent-support\", \"target_role\": null, \"event_status\": \"cancelled\", \"target_user_id\": null}', '2026-08-14 11:13:33', '2026-08-14 11:13:33', NULL),
(5, NULL, 7, NULL, NULL, 'created', 'Demande créée par l\'utilisateur', 'Jams jamsatou1', NULL, 1, NULL, 21, 'f21ebec6-fe37-4f67-b9ec-c459ce419e4d', 1, '{\"reason\": null, \"actor_id\": \"7\", \"actor_role\": \"agent-support\", \"new_status\": \"new\", \"old_status\": null, \"source_role\": \"agent-support\", \"target_role\": null, \"event_status\": \"new\", \"target_user_id\": null}', '2026-08-14 11:43:26', '2026-08-14 11:43:26', NULL),
(5, NULL, 7, NULL, 21, 'routed_to_support', 'Aucune règle de routage — envoi au support général', 'Jams jamsatou1', NULL, 1, NULL, 22, 'f356dac7-66f6-4a46-9fde-ccd3b3becdbf', 1, '{\"reason\": null, \"actor_id\": \"7\", \"dest_role\": \"support\", \"actor_role\": \"agent-support\", \"new_status\": \"qualifying\", \"old_status\": \"new\", \"source_role\": \"agent-support\", \"target_role\": \"support\", \"event_status\": \"to_qualify\", \"target_user_id\": null}', '2026-08-14 11:43:27', '2026-08-14 11:43:27', NULL),
(5, NULL, 7, NULL, 22, 'attachment_added', 'Pièce jointe ajoutée — WhatsApp Image 2026-08-07 at 1.46.51 PM.jpeg', 'Jams jamsatou1', NULL, 1, NULL, 23, '01319b90-aab1-4402-ab6f-13e5837fed41', 1, '{\"reason\": null, \"actor_id\": \"7\", \"filename\": \"WhatsApp Image 2026-08-07 at 1.46.51 PM.jpeg\", \"mime_type\": \"image/jpeg\", \"actor_role\": \"agent-support\", \"new_status\": null, \"old_status\": null, \"size_bytes\": 65439, \"scan_status\": \"clean\", \"source_role\": \"agent-support\", \"target_role\": null, \"event_status\": \"qualifying\", \"attachment_id\": \"2\", \"request_status\": \"qualifying\", \"target_user_id\": null}', '2026-08-14 11:43:30', '2026-08-14 11:43:30', NULL),
(6, NULL, 7, NULL, NULL, 'created', 'Demande créée par l\'utilisateur', 'Jams jamsatou1', NULL, 1, NULL, 24, '9942e907-6065-47b2-a967-ab12595e0d55', 1, '{\"reason\": null, \"actor_id\": \"7\", \"actor_role\": \"agent-support\", \"new_status\": \"new\", \"old_status\": null, \"source_role\": \"agent-support\", \"target_role\": null, \"event_status\": \"new\", \"target_user_id\": null}', '2026-08-14 13:28:44', '2026-08-14 13:28:44', NULL),
(6, NULL, 7, NULL, 24, 'routed_to_support', 'Aucune règle de routage — envoi au support général', 'Jams jamsatou1', NULL, 1, NULL, 25, '28f6969b-0ea7-4433-8bf2-869229e0fb91', 1, '{\"reason\": null, \"actor_id\": \"7\", \"dest_role\": \"support\", \"actor_role\": \"agent-support\", \"new_status\": \"qualifying\", \"old_status\": \"new\", \"source_role\": \"agent-support\", \"target_role\": \"support\", \"event_status\": \"to_qualify\", \"target_user_id\": null}', '2026-08-14 13:28:44', '2026-08-14 13:28:44', NULL),
(6, NULL, 2, NULL, 25, 'in_progress', 'Pris en charge par GASPARD GOEPOGUI — traitement démarré', 'GASPARD GOEPOGUI', NULL, 1, NULL, 26, '8cdf9a53-0a96-4c9b-80b1-ea5c51b8b10f', 1, '{\"reason\": null, \"actor_id\": \"2\", \"actor_role\": \"admin\", \"new_status\": \"in_progress\", \"old_status\": \"in_progress\", \"source_role\": \"admin\", \"target_role\": null, \"event_status\": \"in_progress\", \"changed_fields\": [\"assignee_id\", \"category\", \"in_triage\", \"infos\", \"priority\", \"request_status\", \"unity_id\"], \"target_user_id\": null, \"intervention_id\": \"req6-c1-i1\", \"intervention_order\": 1, \"actor_service_label\": \"Service Étude & Digitalisation\", \"actor_direction_label\": \"Direction des Systèmes d\'Information\", \"intervention_actor_id\": \"2\", \"actor_department_label\": \"Département Étude et Développement\", \"intervention_actor_name\": \"GASPARD GOEPOGUI\", \"intervention_actor_role\": \"admin\", \"intervention_cycle_number\": 1}', '2026-08-15 11:44:02', '2026-08-15 11:44:02', NULL),
(7, NULL, 8, NULL, NULL, 'created', 'Demande créée par l\'utilisateur', 'PAULETTE ONIVOGUI', NULL, 1, NULL, 27, '79df5b95-4b22-41af-acfa-d08746a9f98b', 1, '{\"reason\": null, \"actor_id\": \"8\", \"actor_role\": \"agent-support\", \"new_status\": \"new\", \"old_status\": null, \"source_role\": \"agent-support\", \"target_role\": null, \"event_status\": \"new\", \"target_user_id\": null}', '2026-08-15 12:05:16', '2026-08-15 12:05:16', NULL),
(7, NULL, 8, NULL, 27, 'routed_to_support', 'Aucune règle de routage — envoi au support général', 'PAULETTE ONIVOGUI', NULL, 1, NULL, 28, '5fed2095-dc2c-4f8c-895f-39964d6c1848', 1, '{\"reason\": null, \"actor_id\": \"8\", \"dest_role\": \"support\", \"actor_role\": \"agent-support\", \"new_status\": \"qualifying\", \"old_status\": \"new\", \"source_role\": \"agent-support\", \"target_role\": \"support\", \"event_status\": \"to_qualify\", \"target_user_id\": null}', '2026-08-15 12:05:16', '2026-08-15 12:05:16', NULL),
(8, NULL, 8, NULL, NULL, 'created', 'Demande créée par l\'utilisateur', 'PAULETTE ONIVOGUI', NULL, 1, NULL, 29, '24fe427e-e2e9-42a8-95e8-b35cab72230e', 1, '{\"reason\": null, \"actor_id\": \"8\", \"actor_role\": \"agent-support\", \"new_status\": \"new\", \"old_status\": null, \"source_role\": \"agent-support\", \"target_role\": null, \"event_status\": \"new\", \"target_user_id\": null}', '2026-08-15 12:07:43', '2026-08-15 12:07:43', NULL),
(8, NULL, 8, NULL, 29, 'routed_to_support', 'Aucune règle de routage — envoi au support général', 'PAULETTE ONIVOGUI', NULL, 1, NULL, 30, '83f7e48f-5b7e-4e36-812a-5212d27b0e74', 1, '{\"reason\": null, \"actor_id\": \"8\", \"dest_role\": \"support\", \"actor_role\": \"agent-support\", \"new_status\": \"qualifying\", \"old_status\": \"new\", \"source_role\": \"agent-support\", \"target_role\": \"support\", \"event_status\": \"to_qualify\", \"target_user_id\": null}', '2026-08-15 12:07:43', '2026-08-15 12:07:43', NULL),
(8, NULL, 8, NULL, 30, 'cancelled', 'Demande annulée — merci, j\'ai deja trouvé solution à mon problème', 'PAULETTE ONIVOGUI', NULL, 1, 'merci, j\'ai deja trouvé solution à mon problème', 31, '52765659-678b-47e7-83e1-1c8636f4939e', 1, '{\"reason\": \"merci, j\'ai deja trouvé solution à mon problème\", \"actor_id\": \"8\", \"actor_role\": \"agent-support\", \"new_status\": \"cancelled\", \"old_status\": \"cancelled\", \"source_role\": \"agent-support\", \"target_role\": null, \"event_status\": \"cancelled\", \"target_user_id\": null}', '2026-08-15 12:10:39', '2026-08-15 12:10:39', NULL),
(6, NULL, 7, NULL, 26, 'comment_added', 'Commentaire public ajouté', 'GASPARD KAMUS GOEPOGUI', NULL, 1, 'Bonjour', 32, '40da5c75-92b8-40e9-9551-c89960568e86', 1, '{\"reason\": null, \"peer_id\": \"2\", \"actor_id\": \"7\", \"is_public\": true, \"actor_role\": \"agent-support\", \"new_status\": null, \"old_status\": null, \"visibility\": \"public\", \"source_role\": \"agent-support\", \"target_role\": null, \"event_status\": \"in_progress\", \"request_status\": \"in_progress\", \"target_user_id\": null}', '2026-08-17 16:14:49', '2026-08-17 16:14:49', NULL),
(9, NULL, 7, NULL, NULL, 'created', 'Demande créée par l\'utilisateur', 'GASPARD KAMUS GOEPOGUI', NULL, 1, NULL, 33, '1b223c61-a226-450e-8bfd-311abe5a92db', 1, '{\"reason\": null, \"actor_id\": \"7\", \"actor_role\": \"agent-support\", \"new_status\": \"new\", \"old_status\": null, \"source_role\": \"agent-support\", \"target_role\": null, \"event_status\": \"new\", \"target_user_id\": null}', '2026-08-19 09:41:10', '2026-08-19 09:41:10', NULL),
(9, NULL, 7, NULL, 33, 'routed_to_support', 'Aucune règle de routage — envoi au support général', 'GASPARD KAMUS GOEPOGUI', NULL, 1, NULL, 34, '1818e114-8262-4cb5-9029-15abad3c04eb', 1, '{\"reason\": null, \"actor_id\": \"7\", \"dest_role\": \"support\", \"actor_role\": \"agent-support\", \"new_status\": \"qualifying\", \"old_status\": \"new\", \"source_role\": \"agent-support\", \"target_role\": \"support\", \"event_status\": \"to_qualify\", \"target_user_id\": null}', '2026-08-19 09:41:11', '2026-08-19 09:41:11', NULL),
(9, NULL, 7, NULL, 34, 'attachment_added', 'Pièce jointe ajoutée — edg recrutement.jpg', 'GASPARD KAMUS GOEPOGUI', NULL, 1, NULL, 35, '1bea0aab-e486-4f50-8ac5-470842c39ed3', 1, '{\"reason\": null, \"actor_id\": \"7\", \"filename\": \"edg recrutement.jpg\", \"mime_type\": \"image/jpeg\", \"actor_role\": \"agent-support\", \"new_status\": null, \"old_status\": null, \"size_bytes\": 66482, \"scan_status\": \"clean\", \"source_role\": \"agent-support\", \"target_role\": null, \"event_status\": \"qualifying\", \"attachment_id\": \"3\", \"request_status\": \"qualifying\", \"target_user_id\": null}', '2026-08-19 09:41:14', '2026-08-19 09:41:14', NULL),
(9, NULL, 2, NULL, 35, 'in_progress', 'Pris en charge par GASPARD GOEPOGUI — traitement démarré', 'GASPARD GOEPOGUI', NULL, 1, NULL, 36, '5b8163d9-1151-404c-9fd1-5f1b8e5c133f', 1, '{\"reason\": null, \"actor_id\": \"2\", \"actor_role\": \"admin\", \"new_status\": \"in_progress\", \"old_status\": \"in_progress\", \"source_role\": \"admin\", \"target_role\": null, \"event_status\": \"in_progress\", \"changed_fields\": [\"assignee_id\", \"category\", \"in_triage\", \"infos\", \"priority\", \"request_status\", \"unity_id\"], \"target_user_id\": null, \"intervention_id\": \"req9-c1-i1\", \"intervention_order\": 1, \"actor_service_label\": \"Service Étude & Digitalisation\", \"actor_direction_label\": \"Direction des Systèmes d\'Information\", \"intervention_actor_id\": \"2\", \"actor_department_label\": \"Département Étude et Développement\", \"intervention_actor_name\": \"GASPARD GOEPOGUI\", \"intervention_actor_role\": \"admin\", \"intervention_cycle_number\": 1}', '2026-08-19 10:08:48', '2026-08-19 10:08:48', NULL),
(9, NULL, 6, NULL, 36, 'treatment_transmitted', 'Traitement transmis à AMADOU TOURE', 'GASPARD GOEPOGUI', NULL, 1, 'on doit changer le système de charge', 37, 'f7cac8bd-a98c-459c-b792-40181746909c', 1, '{\"reason\": \"on doit changer le système de charge\", \"actor_id\": \"2\", \"ended_at\": \"2026-08-19T10:12:36.100633\", \"dest_role\": \"agent-support\", \"work_done\": \"J\'ai branché le chargeur mais ça n\'a pas marché\", \"actor_role\": \"admin\", \"new_status\": \"in_progress\", \"old_status\": \"in_progress\", \"started_at\": \"2026-08-19T09:41:10\", \"source_role\": \"admin\", \"target_role\": \"agent-support\", \"cycle_number\": 1, \"target_user_id\": \"6\", \"intervention_id\": \"req9-c1-i1\", \"new_assignee_id\": 6, \"duration_seconds\": 1886, \"target_user_name\": \"AMADOU TOURE\", \"next_intervention\": {\"started_at\": \"2026-08-19T10:12:36.100633\", \"intervention_id\": \"req9-c1-i2\", \"intervention_order\": 2, \"actor_service_label\": \"Service Étude & Digitalisation\", \"actor_direction_label\": \"Direction des Systèmes d\'Information\", \"intervention_actor_id\": \"6\", \"actor_department_label\": \"Département Étude et Développement\", \"intervention_actor_name\": \"AMADOU TOURE\", \"intervention_actor_role\": \"agent-support\", \"intervention_cycle_number\": 1}, \"intervention_order\": 1, \"actor_service_label\": \"Service Étude & Digitalisation\", \"previous_assignee_id\": 2, \"actor_direction_label\": \"Direction des Systèmes d\'Information\", \"intervention_actor_id\": \"2\", \"actor_department_label\": \"Département Étude et Développement\", \"intervention_actor_name\": \"GASPARD GOEPOGUI\", \"intervention_actor_role\": \"admin\", \"intervention_cycle_number\": 1}', '2026-08-19 10:12:36', '2026-08-19 10:12:36', NULL),
(10, NULL, 34, NULL, NULL, 'created', 'Demande créée par l\'utilisateur', 'Mohamed Tassilimy Diaby', NULL, 1, NULL, 38, 'ecc56f26-691d-4936-8f7b-d0429b066f5d', 1, '{\"reason\": null, \"actor_id\": \"34\", \"actor_role\": \"user\", \"new_status\": \"new\", \"old_status\": null, \"source_role\": \"user\", \"target_role\": null, \"event_status\": \"new\", \"target_user_id\": null}', '2026-08-27 12:05:16', '2026-08-27 12:05:16', NULL),
(10, NULL, 34, NULL, 38, 'routed_to_support', 'Aucune règle de routage — envoi au support général', 'Mohamed Tassilimy Diaby', NULL, 1, NULL, 39, '11af1d3d-0b21-4060-b141-6767af9bcb63', 1, '{\"reason\": null, \"actor_id\": \"34\", \"dest_role\": \"support\", \"actor_role\": \"user\", \"new_status\": \"qualifying\", \"old_status\": \"new\", \"source_role\": \"user\", \"target_role\": \"support\", \"event_status\": \"to_qualify\", \"target_user_id\": null}', '2026-08-27 12:05:16', '2026-08-27 12:05:16', NULL),
(10, NULL, 34, NULL, 39, 'attachment_added', 'Pièce jointe ajoutée — Facture Master BS.pdf', 'Mohamed Tassilimy Diaby', NULL, 1, NULL, 40, '2bbc2029-1da1-44b7-80d9-e5e9834d3cc3', 1, '{\"reason\": null, \"actor_id\": \"34\", \"filename\": \"Facture Master BS.pdf\", \"mime_type\": \"application/pdf\", \"actor_role\": \"user\", \"new_status\": null, \"old_status\": null, \"size_bytes\": 664407, \"scan_status\": \"clean\", \"source_role\": \"user\", \"target_role\": null, \"event_status\": \"qualifying\", \"attachment_id\": \"4\", \"request_status\": \"qualifying\", \"target_user_id\": null}', '2026-08-27 12:05:20', '2026-08-27 12:05:20', NULL),
(10, NULL, 36, NULL, 40, 'in_progress', 'Pris en charge par Admin Admin — traitement démarré', 'Admin Admin', NULL, 1, NULL, 41, '04ea0525-cb9c-4585-91c5-098cf21ce199', 1, '{\"reason\": null, \"actor_id\": \"36\", \"actor_role\": \"admin\", \"new_status\": \"in_progress\", \"old_status\": \"in_progress\", \"source_role\": \"admin\", \"target_role\": null, \"event_status\": \"in_progress\", \"changed_fields\": [\"assignee_id\", \"category\", \"in_triage\", \"infos\", \"priority\", \"request_status\"], \"target_user_id\": null, \"intervention_id\": \"req10-c1-i1\", \"intervention_order\": 1, \"intervention_actor_id\": \"36\", \"intervention_actor_name\": \"Admin Admin\", \"intervention_actor_role\": \"admin\", \"intervention_cycle_number\": 1}', '2026-08-27 12:24:21', '2026-08-27 12:24:21', NULL),
(11, NULL, 34, NULL, NULL, 'created', 'Demande créée par l\'utilisateur', 'Mohamed Tassilimy Diaby', NULL, 1, NULL, 42, '1de4dc59-c3e4-4ee9-9adc-c2824fa8e067', 1, '{\"reason\": null, \"actor_id\": \"34\", \"actor_role\": \"user\", \"new_status\": \"new\", \"old_status\": null, \"source_role\": \"user\", \"target_role\": null, \"event_status\": \"new\", \"target_user_id\": null}', '2026-08-27 15:10:29', '2026-08-27 15:10:29', NULL),
(11, NULL, 34, NULL, 42, 'routed_to_support', 'Aucune règle de routage — envoi au support général', 'Mohamed Tassilimy Diaby', NULL, 1, NULL, 43, '02ee525f-6350-43ee-8e43-e8a6e799da82', 1, '{\"reason\": null, \"actor_id\": \"34\", \"dest_role\": \"support\", \"actor_role\": \"user\", \"new_status\": \"qualifying\", \"old_status\": \"new\", \"source_role\": \"user\", \"target_role\": \"support\", \"event_status\": \"to_qualify\", \"target_user_id\": null}', '2026-08-27 15:10:29', '2026-08-27 15:10:29', NULL),
(11, NULL, 34, NULL, 43, 'attachment_added', 'Pièce jointe ajoutée — edg recrutement.jpg', 'Mohamed Tassilimy Diaby', NULL, 1, NULL, 44, '42f44f8e-64bf-42e4-9bb3-d6582e25fbd4', 1, '{\"reason\": null, \"actor_id\": \"34\", \"filename\": \"edg recrutement.jpg\", \"mime_type\": \"image/jpeg\", \"actor_role\": \"user\", \"new_status\": null, \"old_status\": null, \"size_bytes\": 66482, \"scan_status\": \"clean\", \"source_role\": \"user\", \"target_role\": null, \"event_status\": \"qualifying\", \"attachment_id\": \"5\", \"request_status\": \"qualifying\", \"target_user_id\": null}', '2026-08-27 15:10:34', '2026-08-27 15:10:34', NULL);

--
-- Contraintes pour les tables déchargées
--

--
-- Contraintes pour la table `account`
--
ALTER TABLE `account`
  ADD CONSTRAINT `account_ibfk_1` FOREIGN KEY (`unity_id`) REFERENCES `unity` (`id`);

--
-- Contraintes pour la table `activity_log`
--
ALTER TABLE `activity_log`
  ADD CONSTRAINT `activity_log_ibfk_1` FOREIGN KEY (`actor_id`) REFERENCES `account` (`id`);

--
-- Contraintes pour la table `announcement`
--
ALTER TABLE `announcement`
  ADD CONSTRAINT `announcement_ibfk_1` FOREIGN KEY (`announcement_category_id`) REFERENCES `announcement_category` (`id`),
  ADD CONSTRAINT `announcement_ibfk_2` FOREIGN KEY (`announcement_priority_id`) REFERENCES `announcement_priority` (`id`),
  ADD CONSTRAINT `announcement_ibfk_3` FOREIGN KEY (`announcement_status_id`) REFERENCES `announcement_status` (`id`),
  ADD CONSTRAINT `announcement_ibfk_4` FOREIGN KEY (`author_id`) REFERENCES `account` (`id`);

--
-- Contraintes pour la table `announcement_target_role`
--
ALTER TABLE `announcement_target_role`
  ADD CONSTRAINT `announcement_target_role_ibfk_1` FOREIGN KEY (`announcement_id`) REFERENCES `announcement` (`id`) ON DELETE CASCADE;

--
-- Contraintes pour la table `appreciation`
--
ALTER TABLE `appreciation`
  ADD CONSTRAINT `appreciation_ibfk_1` FOREIGN KEY (`request_id`) REFERENCES `request` (`id`) ON DELETE CASCADE;

--
-- Contraintes pour la table `attachment`
--
ALTER TABLE `attachment`
  ADD CONSTRAINT `attachment_ibfk_1` FOREIGN KEY (`request_id`) REFERENCES `request` (`id`) ON DELETE CASCADE,
  ADD CONSTRAINT `attachment_ibfk_2` FOREIGN KEY (`uploader_id`) REFERENCES `account` (`id`);

--
-- Contraintes pour la table `communication_setting`
--
ALTER TABLE `communication_setting`
  ADD CONSTRAINT `communication_setting_ibfk_1` FOREIGN KEY (`updated_by`) REFERENCES `account` (`id`);

--
-- Contraintes pour la table `knowledge_article`
--
ALTER TABLE `knowledge_article`
  ADD CONSTRAINT `knowledge_article_ibfk_1` FOREIGN KEY (`author_id`) REFERENCES `account` (`id`);

--
-- Contraintes pour la table `notification`
--
ALTER TABLE `notification`
  ADD CONSTRAINT `notification_ibfk_1` FOREIGN KEY (`recipient_id`) REFERENCES `account` (`id`) ON DELETE CASCADE,
  ADD CONSTRAINT `notification_ibfk_2` FOREIGN KEY (`request_id`) REFERENCES `request` (`id`);

--
-- Contraintes pour la table `organigram`
--
ALTER TABLE `organigram`
  ADD CONSTRAINT `organigram_ibfk_1` FOREIGN KEY (`unity_id`) REFERENCES `unity` (`id`),
  ADD CONSTRAINT `organigram_ibfk_2` FOREIGN KEY (`parent_id`) REFERENCES `organigram` (`id`) ON DELETE SET NULL;

--
-- Contraintes pour la table `request`
--
ALTER TABLE `request`
  ADD CONSTRAINT `request_ibfk_1` FOREIGN KEY (`request_status_id`) REFERENCES `request_status` (`id`),
  ADD CONSTRAINT `request_ibfk_2` FOREIGN KEY (`priority_definition_id`) REFERENCES `priority_definition` (`id`),
  ADD CONSTRAINT `request_ibfk_3` FOREIGN KEY (`request_category_id`) REFERENCES `request_category` (`id`),
  ADD CONSTRAINT `request_ibfk_4` FOREIGN KEY (`unity_id`) REFERENCES `unity` (`id`),
  ADD CONSTRAINT `request_ibfk_5` FOREIGN KEY (`on_behalf_unity_id`) REFERENCES `unity` (`id`),
  ADD CONSTRAINT `request_ibfk_6` FOREIGN KEY (`assignee_id`) REFERENCES `account` (`id`),
  ADD CONSTRAINT `request_ibfk_7` FOREIGN KEY (`requester_id`) REFERENCES `account` (`id`),
  ADD CONSTRAINT `request_ibfk_8` FOREIGN KEY (`merged_into_id`) REFERENCES `request` (`id`);

--
-- Contraintes pour la table `routing_rule`
--
ALTER TABLE `routing_rule`
  ADD CONSTRAINT `routing_rule_ibfk_1` FOREIGN KEY (`target_unity_id`) REFERENCES `unity` (`id`);

--
-- Contraintes pour la table `task`
--
ALTER TABLE `task`
  ADD CONSTRAINT `task_ibfk_1` FOREIGN KEY (`request_id`) REFERENCES `request` (`id`),
  ADD CONSTRAINT `task_ibfk_2` FOREIGN KEY (`from_agent_id`) REFERENCES `account` (`id`),
  ADD CONSTRAINT `task_ibfk_3` FOREIGN KEY (`to_agent_id`) REFERENCES `account` (`id`),
  ADD CONSTRAINT `task_ibfk_4` FOREIGN KEY (`from_unit_id`) REFERENCES `unity` (`id`),
  ADD CONSTRAINT `task_ibfk_5` FOREIGN KEY (`to_unit_id`) REFERENCES `unity` (`id`);

--
-- Contraintes pour la table `unity`
--
ALTER TABLE `unity`
  ADD CONSTRAINT `fk_unity_parent_direction` FOREIGN KEY (`parent_direction_id`) REFERENCES `unity` (`id`) ON DELETE SET NULL;

--
-- Contraintes pour la table `workflow`
--
ALTER TABLE `workflow`
  ADD CONSTRAINT `workflow_ibfk_1` FOREIGN KEY (`request_id`) REFERENCES `request` (`id`);

--
-- Contraintes pour la table `workflow_detail`
--
ALTER TABLE `workflow_detail`
  ADD CONSTRAINT `workflow_detail_ibfk_1` FOREIGN KEY (`workflow_id`) REFERENCES `workflow` (`id`),
  ADD CONSTRAINT `workflow_detail_ibfk_2` FOREIGN KEY (`unity_id`) REFERENCES `unity` (`id`),
  ADD CONSTRAINT `workflow_detail_ibfk_3` FOREIGN KEY (`agent_id`) REFERENCES `account` (`id`),
  ADD CONSTRAINT `workflow_detail_ibfk_4` FOREIGN KEY (`task_id`) REFERENCES `task` (`id`),
  ADD CONSTRAINT `workflow_detail_ibfk_5` FOREIGN KEY (`parent_id`) REFERENCES `workflow_detail` (`id`);
COMMIT;

/*!40101 SET CHARACTER_SET_CLIENT=@OLD_CHARACTER_SET_CLIENT */;
/*!40101 SET CHARACTER_SET_RESULTS=@OLD_CHARACTER_SET_RESULTS */;
/*!40101 SET COLLATION_CONNECTION=@OLD_COLLATION_CONNECTION */;
