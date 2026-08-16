# Cahier Des Charges

## Application De Ticketing / Support Informatique

**Électricité de Guinée**

**Direction des Systèmes d'Information**

**EDG - DSI**

---

## 1. Contexte

Dans le cadre de l'amélioration de la gestion des incidents, demandes de services et interventions informatiques au sein de la Direction des Systèmes d'Information (DSI) de Électricité de Guinée, il est envisagé de mettre en place une application centralisée de Ticketing/Support.

Cette plateforme permettra :

- la gestion complète des tickets informatiques ;
- le suivi des incidents et demandes ;
- la traçabilité des interventions ;
- l'assignation des tâches aux services compétents ;
- la supervision des délais de traitement ;
- la production de statistiques et rapports.

L'application couvrira tout le cycle de vie d'un ticket :

**Ouverture -> Qualification -> Affectation -> Traitement -> Validation -> Fermeture**

---

## 2. Objectifs Du Projet

### 2.1 Objectif Général

Mettre en place une plateforme informatique centralisée de gestion des tickets de support pour la DSI d'EDG.

### 2.2 Objectifs Spécifiques

L'application devra permettre :

- la création et le suivi des tickets ;
- la gestion des incidents informatiques ;
- la gestion des demandes de services ;
- l'assignation automatique ou manuelle des tickets ;
- la gestion des priorités et niveaux d'urgence ;
- le suivi des interventions ;
- la gestion des SLA, c'est-à-dire les délais de traitement ;
- les notifications automatiques ;
- la génération de statistiques et tableaux de bord ;
- la traçabilité complète des actions ;
- l'archivage des tickets clôturés.

---

## 3. Présentation De La DSI

### 3.1 Structure Organisationnelle

- Direction
- Secrétariat
- Service d'Appui

### 3.2 Départements

#### 1. Département Étude Et Développement

Service :

- Étude & Digitalisation

#### 2. Département Exploitation

Services :

- Maintenance
- Support

#### 3. Département Infrastructure Et Réseau

Services :

- Réseau & Cybersécurité
- Système & Habilitation

---

## 4. Périmètre Du Projet

Le système devra couvrir :

- tous les utilisateurs EDG ;
- tous les services de la DSI ;
- les demandes informatiques internes ;
- les incidents matériels et logiciels ;
- les demandes réseau ;
- les habilitations systèmes ;
- les demandes d'assistance ;
- les interventions terrain et à distance.

---

## 5. Types De Tickets

L'application devra permettre plusieurs catégories :

| Type | Description |
| --- | --- |
| Incident | Dysfonctionnement informatique |
| Demande de service | Nouvelle demande utilisateur |
| Maintenance | Intervention préventive/corrective |
| Réseau | Problème réseau/internet |
| Habilitation | Création/modification d'accès |
| Sécurité | Incident cybersécurité |
| Matériel | Panne matériel |
| Logiciel | Installation/configuration logiciel |

---

## 6. Acteurs Du Système

| Acteur | Rôle |
| --- | --- |
| Utilisateur | Création et suivi des tickets |
| Agent Support | Traitement des tickets |
| Chef de Service | Supervision des tickets du service |
| Chef Département | Validation et suivi départemental |
| Administrateur | Paramétrage et administration |
| Direction DSI | Consultation des statistiques globales |

---

## 7. Workflow Général Du Ticket

### 7.1 Étapes Du Ticket

#### 1. Ouverture Du Ticket

L'utilisateur :

- crée un ticket ;
- renseigne les informations ;
- joint des fichiers si nécessaire.

#### 2. Qualification

Le support :

- analyse le ticket ;
- définit :
  - la catégorie ;
  - la priorité ;
  - le niveau de criticité ;
  - le service concerné.

#### 3. Affectation

Le ticket est :

- affecté automatiquement ;
- ou affecté manuellement à :
  - un service ;
  - un agent ;
  - un département.

#### 4. Traitement

L'agent :

- prend en charge le ticket ;
- ajoute des commentaires ;
- effectue les interventions ;
- change le statut.

#### 5. Validation

Le demandeur :

- confirme la résolution ;
- ou demande une réouverture.

#### 6. Fermeture

Le ticket est :

- clôturé ;
- archivé ;
- historisé.

---

## 8. Gestion Des Statuts

| Statut | Description |
| --- | --- |
| Nouveau | Ticket créé |
| En attente qualification | Analyse initiale |
| Affecté | Assigné à un agent/service |
| En cours | Traitement actif |
| En attente utilisateur | Attente retour utilisateur |
| Résolu | Incident résolu |
| Fermé | Ticket clôturé |
| Rejeté | Ticket invalidé |
| Réouvert | Ticket rouvert |

---

## 9. Gestion Des Priorités

| Priorité | Délai |
| --- | --- |
| Critique | Immédiat |
| Haute | < 4h |
| Moyenne | < 24h |
| Faible | < 72h |

---

## 10. Fonctionnalités Principales

### 10.1 Gestion Des Tickets

Le système doit permettre :

- création ticket ;
- modification ticket ;
- suivi ticket ;
- historique ticket ;
- réouverture ticket ;
- clôture ticket ;
- affectation ticket ;
- escalade ticket ;
- fusion ticket ;
- duplication ticket.

### 10.2 Tableau De Bord

Le tableau de bord devra afficher :

- nombre total de tickets ;
- tickets ouverts ;
- tickets en retard ;
- tickets résolus ;
- tickets critiques ;
- tickets par service ;
- tickets par département ;
- performance agents ;
- statistiques SLA.

### 10.3 Notifications

Notifications par :

- email ;
- SMS, optionnel ;
- notifications internes.

Évènements :

- création ticket ;
- affectation ;
- changement statut ;
- résolution ;
- fermeture ;
- escalade.

### 10.4 Gestion Des Utilisateurs

Le système devra gérer :

- authentification ;
- gestion des rôles ;
- gestion des permissions ;
- réinitialisation mot de passe ;
- gestion des profils.

### 10.5 Historique & Traçabilité

Le système doit journaliser :

- toutes les actions ;
- les changements de statut ;
- les affectations ;
- les connexions ;
- les modifications.

**Export du dossier complet d'une demande (Administration)** — réservé au rôle
`admin` : depuis la fiche détail d'un ticket dans l'espace Administration,
génération d'un dossier Excel complet (identification, demandeur, structure
organisationnelle, acteurs, historique, escalades, conversations, pièces
jointes, notifications) reconstruit à partir des données réellement
enregistrées. Aucune donnée de délai/SLA n'y figure. Lecture seule : aucun
changement de statut, notification ou événement métier déclenché par l'export.

### 10.6 Gestion Documentaire

Possibilité de :

- joindre des fichiers ;
- ajouter des captures d'écran ;
- joindre des rapports PDF ;
- stocker des documents techniques.

---

## 11. Fonctionnalités Avancées

### 11.1 SLA (Service Level Agreement)

Le système devra :

- calculer automatiquement les délais ;
- générer des alertes ;
- détecter les dépassements.

### 11.2 Escalade Automatique

Si un ticket dépasse le délai :

- notification automatique ;
- escalade vers supérieur hiérarchique.

### 11.3 Base De Connaissance

Le système pourra intégrer :

- FAQ ;
- solutions fréquentes ;
- guides techniques ;
- procédures.

---

## 12. Exigences Techniques

### 12.1 Architecture

Architecture web :

- front-end ;
- back-end ;
- API REST ;
- base de données.

### 12.2 Technologies Proposées

| Couche | Technologies |
| --- | --- |
| Front-End | Angular / React |
| Back-End | Django / Laravel / FastAPI |
| Base de données | MySQL / PostgreSQL |
| API | REST API |
| Authentification | JWT / Active Directory |
| Hébergement | Serveur EDG / Cloud |

---

## 13. Sécurité

Le système devra garantir :

- authentification sécurisée ;
- gestion des habilitations ;
- journalisation ;
- chiffrement des mots de passe ;
- protection contre les accès non autorisés ;
- sauvegarde des données ;
- gestion des sessions.

---

## 14. Rapports & Statistiques

Le système devra produire :

- rapport journalier ;
- rapport mensuel ;
- rapport par service ;
- rapport par agent ;
- temps moyen de résolution ;
- taux de satisfaction ;
- taux SLA.

Formats :

- PDF ;
- Excel ;
- CSV.

---

## 15. Contraintes

- Interface simple et intuitive ;
- application responsive ;
- multi-utilisateurs ;
- haute disponibilité ;
- performances optimisées ;
- compatible réseau interne EDG.

---

## 16. Livrables Attendus

| Livrable | Description |
| --- | --- |
| Cahier des charges | Document fonctionnel |
| Maquettes | Interfaces utilisateur |
| Base de données | Schéma relationnel |
| API | Documentation API |
| Application Web | Plateforme complète |
| Documentation technique | Guide technique |
| Manuel utilisateur | Guide d'utilisation |
| Formation | Formation utilisateurs |

---

## 17. Planning Prévisionnel

| Phase | Durée |
| --- | --- |
| Analyse & conception | 2 semaines |
| Maquettage | 1 semaine |
| Développement | 6 semaines |
| Tests | 2 semaines |
| Déploiement | 1 semaine |
| Formation | 1 semaine |

---

## 18. Conclusion

La mise en place de cette application de Ticketing/Support permettra à la DSI d'EDG :

- d'améliorer la gestion des incidents ;
- d'optimiser le support informatique ;
- de renforcer la traçabilité ;
- d'améliorer la qualité de service ;
- de réduire les délais de traitement ;
- d'avoir une meilleure visibilité sur les activités informatiques.

---

## 19. Journal Des Évolutions

| Date | Évolution |
| --- | --- |
| 2026-08-15 | Ajout de l'export du dossier complet d'une demande, réservé à l'espace Administration (§10.5) — détails techniques dans `docs/mise-a-jour-backend.md`. |
