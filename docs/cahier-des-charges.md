# Cahier des Charges — EDG Connect
## Plateforme de gestion des demandes internes — Électricité de Guinée (EDG)

---

## 1. Présentation générale

**EDG Connect** est une application web de gestion des demandes de support interne pour Électricité de Guinée. Elle centralise la création, le suivi, le traitement et le reporting de toutes les demandes émises par les agents et employés de l'entreprise.

- **Type** : ITSM interne (80 % des demandes proviennent d'employés avec un compte)
- **Public** : Employés internes principalement ; accès public limité à la consultation de statut par référence
- **Langues** : Français
- **Déploiement** : SPA (TanStack Start/React 19) + API REST (FastAPI / Python)

---

## 2. Objectifs

| # | Objectif |
|---|----------|
| O1 | Centraliser toutes les demandes internes en un seul outil |
| O2 | Assurer la traçabilité complète du cycle de vie de chaque demande |
| O3 | Automatiser le routage des demandes vers les bons services |
| O4 | Gérer les SLA (délais de résolution) par priorité et par direction |
| O5 | Permettre aux managers de superviser les performances de leur équipe |
| O6 | Produire des rapports et statistiques exploitables (CSAT, SLA, volume) |
| O7 | Garantir la sécurité des accès (RBAC, JWT, biométrie optionnelle) |
| O8 | Diffuser des annonces et notifications en temps réel (SSE) |

---

## 3. Périmètre et acteurs

### 3.1 Ce qui est dans le périmètre
- Soumission de demandes par les employés internes connectés (compte EDG obligatoire)
- Traitement par les agents EDG
- Supervision par les chefs de service et directeurs
- Pilotage global par le Directeur Général
- Administration système (utilisateurs, SLA, référentiels, routing)
- Base de connaissances (version connectée `/app/knowledge` + lecture publique `/knowledge`)
- Notifications en temps réel
- Suivi public de demande par référence (`/track`, lecture seule)

### 3.2 Ce qui est HORS périmètre
- **Demandes de citoyens/clients externes sans compte EDG** — décision confirmée : seuls les employés EDG peuvent soumettre des demandes. La route `/create-request` sert uniquement de passerelle vers la connexion employé.
- Formulaire de soumission anonyme (supprimé)
- Facturation / paiements

### 3.3 Rôles et accès

| Rôle | Label | Accès racine |
|------|-------|--------------|
| `public` | Visiteur | `/` (landing + tracking public) |
| `user` | Demandeur | `/app/` (dashboard + mes demandes) |
| `agent` | Agent support | `/app/queue` (file d'attente) |
| `chief` | Chef de service | `/app/supervision` (supervision équipe) |
| `director` | Directeur | `/app/direction` (tableau de bord direction) |
| `dg` | Directeur Général | `/app/dg` (tableau de bord global) |
| `admin` | Administrateur | `/app/admin/users` (backoffice) |

---

## 4. Cycle de vie d'une demande

### 4.1 Statuts et transitions

```
new → qualifying → qualified → assigned → in_progress
                                              ↓         ↓         ↓
                                           pending  escalated  rejected
                                              ↓
                                           (retour in_progress après réponse)
                                              ↓
                                           resolved → closed
                                              ↓
                                           reopened (si insatisfait)
```

| Statut | Code | Signification |
|--------|------|---------------|
| Nouveau | `new` | Demande soumise, non encore prise en charge |
| En qualification | `qualifying` | Agent qualifie la demande |
| Qualifié | `qualified` | Demande qualifiée, prête à être assignée |
| Assigné | `assigned` | Ticket assigné à un agent spécifique |
| En cours | `in_progress` | Traitement actif |
| En attente | `pending` | Agent attend retour du demandeur |
| Escaladé | `escalated` | Escaladé au niveau supérieur |
| Rejeté | `rejected` | Demande rejetée (hors périmètre, doublon…) |
| Résolu | `resolved` | Problème résolu |
| Fermé | `closed` | Résolution confirmée |
| Réouvert | `reopened` | Demandeur insatisfait — réouverture |

### 4.2 Acteurs par transition

| Transition | Acteur autorisé |
|-----------|-----------------|
| Créer une demande | user, agent, admin |
| Qualifier | agent, chief |
| Assigner | agent (auto-assign ou chief) |
| Prise en charge | agent assigné |
| Demander infos (pending) | agent |
| Répondre au pending | user demandeur |
| Escalader | agent, chief |
| Résoudre | agent assigné |
| Fermer | user demandeur (confirmation) ou auto |
| Rouvrir | user demandeur |
| Rejeter | agent, chief |

---

## 5. Fonctionnalités par rôle

### 5.1 Rôle `user` (Demandeur)

| # | Fonctionnalité | Vue |
|---|---------------|-----|
| U1 | Soumettre une nouvelle demande | `/app/new` |
| U2 | Consulter la liste de ses demandes | `/app/requests` |
| U3 | Voir le détail et historique d'une demande | `/app/requests/:id` |
| U4 | Répondre à une demande d'info complémentaire (pending) | `/app/requests/:id` |
| U5 | Fermer / noter sa satisfaction (CSAT 1-5) | `/app/requests/:id` |
| U6 | Consulter la base de connaissances | `/app/knowledge` |
| U7 | Recevoir des notifications en temps réel | Toutes vues |
| U8 | Gérer son profil | `/app/profile` |
| U9 | Dashboard personnel (KPIs mes demandes) | `/app/` |

### 5.2 Rôle `agent` (Agent support)

| # | Fonctionnalité | Vue |
|---|---------------|-----|
| A1 | Consulter la file d'attente des nouvelles demandes | `/app/queue` |
| A2 | Triage : qualifier, prioriser, router une demande | `/app/triage` |
| A3 | Consulter et gérer ses tickets assignés | `/app/my-tickets` |
| A4 | Traiter un ticket (changer statut, commenter) | `/app/requests/:id` |
| A5 | Demander des informations complémentaires (pending) | `/app/requests/:id` |
| A6 | Escalader un ticket | `/app/requests/:id` |
| A7 | Résoudre un ticket | `/app/requests/:id` |
| A8 | Consulter la base de connaissances | `/app/knowledge` |
| A9 | Voir ses stats personnelles (taux résolution, SLA, délai moyen) | `/app/my-tickets` |
| A10 | Recevoir notifications (réponse demandeur sur pending) | Temps réel |

### 5.3 Rôle `chief` (Chef de service)

| # | Fonctionnalité | Vue |
|---|---------------|-----|
| C1 | Tableau de bord de son service | `/app/supervision` |
| C2 | Consulter les tickets de son équipe | `/app/supervision` |
| C3 | Gérer les escalades reçues | `/app/chief-inbox` |
| C4 | Publier un message d'équipe | `/app/supervision` |
| C5 | Consulter les historiques de demandes | `/app/requests/history` |
| C6 | Accéder aux annonces | Via notifications |
| C7 | Toutes les fonctionnalités agent (A1–A10) | Mêmes vues |

### 5.4 Rôle `director` (Directeur de direction)

| # | Fonctionnalité | Vue |
|---|---------------|-----|
| D1 | Tableau de bord direction (KPIs, SLA, volume) | `/app/direction` |
| D2 | Vue des demandes de sa direction | `/app/direction` |
| D3 | Vue des performances par service | `/app/direction` |
| D4 | Gérer les règles de routage de sa direction | `/app/direction` |
| D5 | Consulter les rapports | `/app/reports` |
| D6 | Consulter le centre SLA | `/app/sla-center` |

### 5.5 Rôle `dg` (Directeur Général)

| # | Fonctionnalité | Vue |
|---|---------------|-----|
| DG1 | Tableau de bord global (toutes directions) | `/app/dg` |
| DG2 | KPIs : volume, SLA global, CSAT global | `/app/dg` |
| DG3 | Performance par direction | `/app/dg` |
| DG4 | Rapports complets | `/app/reports` |
| DG5 | Publier des annonces globales | Via admin ou DG panel |
| DG6 | Consulter le centre SLA | `/app/sla-center` |

### 5.6 Rôle `admin` (Administrateur système)

| # | Fonctionnalité | Vue |
|---|---------------|-----|
| AD1 | Gestion des utilisateurs et rôles | `/app/admin/users` |
| AD2 | Gestion de l'organigramme (directions + services) | `/app/admin/org` + `/app/admin/directions` + `/app/admin/units` |
| AD3 | Configuration des SLA et priorités | `/app/admin/sla` + `/app/admin/priorities` |
| AD4 | Configuration du routage automatique | `/app/admin/routing` |
| AD5 | Gestion des workflows | `/app/admin/references` |
| AD6 | Publication d'annonces | `/app/admin/homepage` |
| AD7 | Consultation des journaux d'activité (audit trail) | `/app/admin/logs` |
| AD8 | Consultation des journaux de sécurité | `/app/admin/security` |
| AD9 | Configuration des canaux de communication | `/app/admin/communication` |
| AD10 | Gestion de la base de connaissances | `/app/admin/knowledge` |
| AD11 | Rapports et statistiques | `/app/reports` |

---

## 6. Règles métier

### 6.1 SLA (Service Level Agreement)
- Chaque priorité (`low`, `normal`, `high`, `critical`) a un délai de résolution cible exprimé en heures
- Le délai est calculé depuis la création de la demande
- Une demande est SLA-breached si `sla_elapsed > sla_hours`
- Planificateur toutes les 10 minutes pour vérifier les SLA dépassés

### 6.2 Routage automatique
- Des règles de routage associent une catégorie/mot-clé à une direction + unité cible
- Le routage est déclenché à la soumission ou à la qualification
- Chaque directeur peut gérer les règles de sa propre direction

### 6.3 Notifications
- Toute transition de statut déclenche une notification au demandeur
- La réponse d'un demandeur à un `pending_info` notifie l'agent assigné
- Les annonces publiées sont visibles dans l'espace de notifications

### 6.4 Escalade
- Un ticket peut être escaladé par l'agent ou le chef
- L'escalade arrive dans la boîte du chef (`chief-inbox`)
- Le chef peut traiter ou réassigner

### 6.5 Satisfaction (CSAT)
- Le demandeur peut noter sa satisfaction de 1 à 5 à la clôture
- Le CSAT est agrégé par agent, par direction, et globalement
- Visible pour le chief, director, dg, admin

### 6.6 Base de connaissances
- Articles consultables par tous les utilisateurs connectés
- Gestion (CRUD) réservée à l'admin
- Catégorisés par direction / thème

### 6.7 Annonces
- Publiées par admin/DG pour toute la plateforme
- Publiées par chef de service pour son équipe uniquement (audience=unit)
- Canaux : in_app (notifications), e-mail (optionnel)

---

## 7. Sécurité et conformité

| Exigence | Détail |
|---------|--------|
| S1 | Authentification JWT (access + refresh tokens) |
| S2 | Rotation automatique du token (pre-emptive + reactive 401) |
| S3 | Authentification biométrique optionnelle (InsightFace ArcFace, seuil 40) |
| S4 | RBAC strict : chaque endpoint vérifie le rôle via `require_roles` |
| S5 | Rate limiting sur les routes auth (login 10/60s, register 5/60s, reset 3/60s) |
| S6 | Chiffrement des champs sensibles (ServiceCrypto) |
| S7 | Journaux d'activité (audit trail) pour toutes les actions critiques |
| S8 | Journaux de sécurité (tentatives d'authentification biométrique) |
| S9 | `DISABLE_AUTH=True` interdit en production |
| S10 | CORS restreint aux origines configurées en production |

---

## 8. Architecture technique

### 8.1 Frontend
- **Framework** : React 19 + TanStack Router (file-based routing) + TanStack Query
- **UI** : Tailwind CSS 4, shadcn/ui, Radix UI, Recharts
- **Auth** : JWT dans localStorage, `isAuthenticated()`, `getRole()`, `useUser()`
- **Temps réel** : SSE (Server-Sent Events) via `/api/v1/events` (préfixe du routeur backend : `/events`)
- **Formulaires** : React Hook Form + Zod

### 8.2 Backend
- **Framework** : FastAPI (Python 3.10+)
- **Base de données** : MySQL via SQLAlchemy async
- **Auth** : JWT (python-jose), bcrypt passwords
- **Biométrie** : InsightFace ArcFace (ONNX)
- **Notifications temps réel** : SSE + asyncio event bus
- **SLA scheduler** : APScheduler (intervalle 10 minutes)
- **Rate limiting** : Redis (prod) ou mémoire (dev)

### 8.3 Données de référence (seed)
- Statuts de demande (14 statuts)
- Priorités (4 niveaux)
- Catégories de demande
- Workflows et étapes
- Canaux de communication
- Un compte admin initial

---

## 9. Interfaces et vues

### 9.1 Vues publiques (sans authentification)
| Route | Description |
|-------|-------------|
| `/` | Landing page + accès connexion |
| `/login` | Connexion email/mot de passe |
| `/register` | Inscription (employés) |
| `/forgot-password` | Réinitialisation mot de passe |
| `/create-request` | Passerelle employé → redirige vers `/login` (demandes internes uniquement) |
| `/track` | Suivi d'une demande par référence (lecture seule) |
| `/knowledge` | Base de connaissances publique (lecture seule) |
| `/admin-login` | Connexion administrateur dédiée |

### 9.2 Vues authentifiées communes
| Route | Rôles | Description |
|-------|-------|-------------|
| `/app/` | tous | Dashboard adapté au rôle |
| `/app/notifications` | tous | Centre de notifications |
| `/app/profile` | tous | Profil utilisateur |
| `/app/knowledge` | tous | Base de connaissances |
| `/app/requests` | tous | Liste des demandes (filtrée par rôle) |
| `/app/requests/:id` | tous | Détail et historique d'une demande |
| `/app/new` | user, admin | Créer une nouvelle demande |

### 9.3 Vues agents
| Route | Rôles | Description |
|-------|-------|-------------|
| `/app/queue` | agent, chief, admin | File d'attente (non assignées) |
| `/app/triage` | agent, chief, admin | Triage et qualification |
| `/app/my-tickets` | agent, chief, admin | Mes tickets assignés + stats perso |

### 9.4 Vues supervision
| Route | Rôles | Description |
|-------|-------|-------------|
| `/app/supervision` | chief, director, admin | Tableau de bord équipe + message équipe |
| `/app/chief-inbox` | chief | Escalades reçues |
| `/app/sla-center` | chief, director, dg, admin | Centre de suivi SLA |
| `/app/direction` | director | Tableau de bord direction + routing rules |
| `/app/dg` | dg | Tableau de bord DG |
| `/app/reports` | chief, director, dg, admin | Rapports et graphiques |

### 9.5 Vues administration
| Route | Rôles | Description |
|-------|-------|-------------|
| `/app/admin/users` | admin | Gestion utilisateurs et rôles |
| `/app/admin/org` | admin | Organigramme graphique |
| `/app/admin/directions` | admin | Liste directions (CRUD) |
| `/app/admin/units` | admin | Liste services/unités (CRUD) |
| `/app/admin/sla` | admin | Politiques SLA |
| `/app/admin/priorities` | admin | Priorités et niveaux |
| `/app/admin/routing` | admin | Règles de routage global |
| `/app/admin/references` | admin | Référentiels (catégories, workflows) |
| `/app/admin/knowledge` | admin | Gestion base de connaissances |
| `/app/admin/homepage` | admin | Gestion annonces |
| `/app/admin/communication` | admin | Paramètres communication (SMTP…) |
| `/app/admin/logs` | admin | Journaux d'activité |
| `/app/admin/security` | admin | Journaux de sécurité |
| `/app/admin/audit` | admin | Audit trail |
