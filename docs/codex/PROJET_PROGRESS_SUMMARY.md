# Synthèse de progression EDG Connect

## Objet

Ce document sert de mémoire de travail pour la suite des interventions Codex sur EDG Connect. Il recense les corrections, normalisations et validations déjà menées depuis le début de la session, afin que l’agent puisse reprendre le contexte sans repartir de zéro.

## Contexte métier

Le projet EDG Connect est une application de gestion des demandes et tickets EDG, structurée autour des rôles métier suivants :

- `user`
- `chief-service`
- `chief-service`
- `chief-departement`
- `director`
- `admin`

Le rôle `dg` n’est plus considéré comme un acteur métier distinct dans le modèle canonique actuel. La vue globale reste réservée à `admin`.

## Correctifs et alignements réalisés

### 1. Normalisation des rôles métier et du RBAC

Les correctifs ont consisté à aligner la logique backend sur la nomenclature métier canonique, tout en conservant une compatibilité technique avec les libellés historiques déjà présents en base.

Fichiers clés concernés :

- `backend/api/core/rbac.py`
- `backend/api/core/ticket_actions.py`
- `backend/api/models/ModelAccount.py`
- `backend/api/dependencies.py`
- `backend/api/routes/RouteRequest.py`
- `backend/api/routes/RouteAttachment.py`
- `backend/api/services/ServiceAccount.py`
- `backend/tests/api/test_ticket_actions.py`

Résultat :

- le rôle `chief-service` est désormais le nom canonique de l’assistance métier ;
- le rôle `chief-service` désigne bien le chef de service ;
- le rôle `chief-departement` est utilisé pour le niveau départemental ;
- la compatibilité historique sur les anciens libellés est gardée au niveau d’adaptation technique, mais la logique métier est désormais standardisée.

### 2. Vérification des permissions de ticket

La couche de décision sur les actions tickets a été alignée sur le nouveau modèle de rôle.

Résultat constaté :

- `chief-service` peut accomplir les actions autorisées à ce niveau ;
- les rejections et refus de certaines actions sont correctement bloqués selon le périmètre métier ;
- les permissions ne reposent plus sur des labels anciens non canonisés.

### 3. Structure organisationnelle Direction / Département / Service

La structure organisationnelle a été stabilisée autour de la hiérarchie :

- direction
- département
- service / unité

Fichiers clés concernés :

- `backend/api/routes/RouteDirectionsUnits.py`
- `backend/api/main.py`
- `frontend/src/routes/app.admin.directions.tsx`
- `frontend/src/routes/app.admin.directions.$id.tsx`
- `frontend/src/routes/app.admin.departments.tsx`
- `frontend/src/routes/app.admin.units.tsx`
- `frontend/src/routes/app.admin.org.tsx`

Résultat :

- la hiérarchie administrative est cohérente ;
- l’interface d’admin présente une représentation plus claire des entités organisationnelles ;
- le détail direction conserve un rendu exploitable même lorsque des sous-branches sont incomplètes.

### 4. Correction du seed organisationnel et de la persistance

Le problème identifié concernait les données de référence réinjectées au démarrage, qui rétablissaient parfois des unités ou directions supprimées par l’admin.

Fichiers clés concernés :

- `backend/api/seed_references.py`
- `backend/tests/api/test_seed_references_org.py`

Résultat :

- le seed ne restaure plus automatiquement les éléments soft-deleted supprimés ;
- les suppressions administratives sont désormais plus fiables ;
- l’organisation persistée reste cohérente entre les relances de l’application.

### 5. Formulaire admin et attribution d’orga / rôle

La gestion des comptes admin a été ajustée pour que l’attribution de rôle et d’organisation soit cohérente avec la hiérarchie réelle.

Fichiers clés concernés :

- `frontend/src/routes/app.admin.users.tsx`
- `frontend/src/lib/api/accounts.ts`
- `backend/api/schemas/SchemaAccount.py`
- `backend/api/routes/RouteUsers.py`
- `backend/api/services/ServiceAccount.py`

Résultat :

- l’interface admin ne présente plus d’ambiguïté sur les niveaux organisationnels ;
- la validation backend protège la cohérence de l’affectation ;
- la configuration administrative reste alignée sur la structure métier.

### 6. Doctrine de navigation et d’accès frontend

Les vues frontend ont été adaptées pour rester cohérentes avec le rôle canonique et éviter les incohérences de navigation.

Fichiers clés concernés :

- `frontend/src/lib/session.ts`
- `frontend/src/components/app-layout.tsx`
- `frontend/src/routes/app.admin.*`

Résultat :

- la session frontend normalise l’affichage côté UX ;
- le backend reste la source de vérité pour les décisions de sécurité ;
- les écrans métier restent orientés selon le périmètre réel du rôle.

## Nettoyage des données persistées

Une passe de nettoyage a été effectuée sur les données de compte pour normaliser les valeurs de rôle déjà stockées.

Résultat observé :

- les comptes historiques ont été ramenés à la nomenclature canonique ;
- les rôles persistés sont désormais cohérents avec la logique de permissions actuelle ;
- le système d’authentification et les contrôles de route peuvent s’appuyer sur un modèle stable.

## Vérifications exécutées

Les vérifications ciblées suivantes ont été exécutées et validées :

1. Vérification directe Python du moteur RBAC :
   - sortie observée : `VERIFICATION_OK`

2. Vérification de la base des comptes :
   - liste d’identités récupérée depuis la table `account` ;
   - observation confirmée : les comptes sont désormais cohérents avec les rôles normalisés.

3. Vérification du seed de démonstration :
   - compte admin initial identifié ;
   - mot de passe de bootstrap connu et exploitable pour les tests de connexion.

## État courant

L’application est actuellement dans un état de cohérence fonctionnelle sur le périmètre de rôles et de permissions traité.

Les valeurs maîtrisées à ce stade sont les suivantes :

- `user`
- `chief-service`
- `chief-service`
- `chief-departement`
- `director`
- `admin`

Le système conserve une compatibilité technique avec les anciens libellés historiques, mais l’usage métier standardisé est désormais celui-ci.

## Recommandation de poursuite

La suite logique consiste à :

1. continuer la validation des parcours frontend avec les comptes de test connus ;
2. vérifier les écrans restants qui peuvent encore afficher des libellés métier obsolètes ;
3. ne pas introduire de nouveaux rôles ni d’alias métier sans mise à jour de la documentation et du modèle de permissions.

## Source de vérité de travail

Les références de travail à conserver en priorité sont :

- `AGENTS.md`
- `docs/codex/`
- les fichiers backend/frontend directement liés au module touché

Le backend demeure la source de vérité pour les décisions d’accès, tandis que le frontend reste un adaptateur d’affichage et de navigation.
