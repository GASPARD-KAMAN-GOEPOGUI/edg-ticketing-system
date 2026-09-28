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

Le chef de service (CSSHF) :

- analyse le ticket ;
- définit :
  - la catégorie ;
  - la priorité ;
  - le niveau de criticité.

**La qualification est un point de contrôle bloquant** (précisé le 2026-09-26) :
aucun ticket ne quitte la File d'attente avant que la **catégorie**, la
**priorité** et la **solution proposée** aient été saisies. Ces champs s'ouvrent
**vides**, même lorsque le ticket portait déjà une valeur : un pré-remplissage
permettrait de valider sans avoir rien examiné, ce qui viderait le contrôle de
son sens. Les valeurs d'origine restent consultables sur la fiche du ticket.
Orienter vers un chef de division support exige en plus de le désigner ; prendre
le ticket pour soi-même ne le demande pas, puisqu'il n'y a alors personne à qui
l'orienter.

Un service pouvant compter **plusieurs chefs de division support**, la liste
d'imputation les identifie au format **`nom complet.badge`** — le badge étant le
libellé métier du matricule. Sans badge renseigné, le nom complet est affiché
seul.

**Le service traitant n'est pas saisi.** Seule la DSI traite les incidents :
l'organisation qui prend en charge la demande (direction, département, service)
est toujours celle du chef de service qui qualifie. Son rattachement étant déjà
renseigné par l'administrateur lors de son enregistrement au back-office, il est
repris automatiquement sur le ticket, sans ressaisie. Cette déduction est faite
**côté serveur** : une direction ou un service transmis par un appel API est
ignoré.

Un ticket porte donc deux photographies organisationnelles distinctes :

| Dimension | Source | Ce qu'elle répond |
| --- | --- | --- |
| Demandeur | compte du demandeur (direction, département, service, fonction, matricule) | d'où vient la demande |
| Traitement | compte du chef de service qui qualifie | qui prend en charge |

#### 3. Affectation

Après qualification, le chef de service a deux issues :

- prendre le ticket pour son propre traitement ;
- ou l'orienter vers un **chef de division support de son propre service**, qui
  le reçoit dans sa file « Distribution » et décide ensuite de le traiter ou de
  l'assigner à un technicien de sa division.

La chaîne de transmission dynamique qui suit (d'un intervenant A à un
intervenant An) n'est pas concernée par cette restriction : elle reste libre.

#### 4. Traitement

L'agent :

- prend en charge le ticket ;
- ajoute des commentaires ;
- effectue les interventions ;
- change le statut.

**Workflow progressif** (2026-09-27) : les actions de traitement ne sont pas
toutes proposées en même temps. Le traitant en voit **une seule à la fois**,
selon l'état réel du ticket :

| État du ticket | Action proposée |
| --- | --- |
| Assigné, sans constat | Constat d'intervention |
| Assigné, constat consigné | Démarrer le traitement |
| En cours | Terminer le traitement |
| Résolu ou clôturé | aucune |

**Une assignation ne démarre plus le traitement** : elle désigne un intervenant.
Le traitement commence au geste explicite du traitant, qui saisit alors le
**lieu de l'intervention** ; la date et l'heure de début sont horodatées par le
système, jamais saisies. Le **demandeur ne renseigne pas le lieu** : c'est une
donnée de terrain, connue du seul traitant.

À la terminaison, la date et l'heure de fin sont enregistrées de la même façon,
et le PV est établi. Il est **soumis automatiquement** au chef de division dès
que le demandeur a validé le dépannage — la tâche 3.2 reste donc un point de
contrôle, et le traitant n'a plus de soumission manuelle à faire.

**« Transmettre le traitement » est indépendant de ce workflow** : il reste
proposé à chaque étape, avec ses propres règles.

**Constat d'intervention** (procédure EDG/PS-GSI/Pro-02 tâche 2.1) : avant de
résoudre, le **technicien** confronte l'état réel trouvé sur place à ce que
décrit la demande. Il déclare le constat **conforme** ou en **écart**, et
consigne ses observations.

En cas d'écart, il précise la **catégorie observée** et la **priorité
observée**, toutes deux **obligatoires** et **choisies dans une liste** (précisé
le 2026-09-26) — le même référentiel que celui de la qualification, puisque
l'intérêt du constat est justement de comparer les deux. Elles étaient
auparavant saisies en texte libre et facultatives, ce qui produisait des
libellés hétérogènes et souvent vides. Un écart remet en cause la qualification,
qui appartient au chef de service : celui-ci en est averti.

Le constat du traitant actuel est consultable dans l'onglet **Description** du
ticket, à la suite de la description du demandeur et de la solution proposée. Il
est visible de **tous**, demandeur inclus — contrairement à la solution proposée,
qui reste réservée au support. Le bouton de saisie disparaît une fois le constat
de l'intervention en cours consigné, et réapparaît pour l'intervenant suivant
après une transmission, qui ouvre une nouvelle intervention.

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
- fermeture.

Destinataires à la création d'un ticket (précisé le 2026-09-26) : le demandeur
reçoit une confirmation (« Ticket créé »), et **tous les chefs de service
(`chief-service`)** reçoivent « Nouvelle demande à qualifier », in-app et par
email. Ce sont eux qui tiennent la File d'attente. L'administrateur en est
volontairement exclu : il voit la même file mais ne qualifie pas, le notifier à
chaque création ne produirait que du bruit. Ces notifications sont persistées en
base, donc consultables même si le destinataire était déconnecté au moment de la
création — l'évènement temps réel (SSE) ne fait que rafraîchir les écrans ouverts.

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

**Traçabilité organisationnelle** — chaque ticket conserve, d'un côté, la
direction / le département / le service / la fonction / le matricule du
**demandeur**, et de l'autre la direction / le département / le service qui
**traite** la demande (voir §7.1).

Ces informations sont **figées au moment des faits** et ne sont jamais
recalculées ensuite : celles du demandeur à la création de la demande, celles de
l'organisation traitante à la qualification, celles de chaque intervenant à
l'ouverture de son intervention. Une mutation de personnel, un changement de
fonction, un renommage de service ou une réorganisation de l'organigramme ne
réécrivent donc pas l'historique : un ticket traité en janvier continue
d'afficher la situation de janvier.

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

### 11.2 Escalade Automatique — RETIRÉE (2026-09-26)

L'escalade est retirée en même temps que le statut `escalated` : un ticket ne
doit plus changer de statut ni de responsable sans action humaine explicite
(règle déjà appliquée au job planifié, désactivé avant ce retrait). L'endpoint
`POST /requests/{id}/escalate`, le service `ServiceEscalade`, `GET
/stats/escalations` et toute l'interface d'arbitrage ont été supprimés.

Les statuts `pending` et `qualified` sont retirés par la même occasion. Les
trois codes cessent d'être des **cibles** mais restent des **sources** de
transition, afin qu'aucun ticket déjà en base ne se retrouve figé sans action
disponible.

### 11.3 Base De Connaissance — RETIRÉE (2026-09-24)

Cette fonctionnalité était optionnelle (« le système *pourra* intégrer ») et n'a
jamais été alimentée : la table `knowledge_article` était vide en production.

Elle a été retirée du périmètre sur décision produit du 2026-09-24, avec ses
tables (`knowledge_article`, `knowledge_category`), ses routes API, ses pages
(`/knowledge` public, `/app/knowledge`, `/app/admin/knowledge`) et la permission
`view_knowledge` / `manage_knowledge`. La route `/help`, qui n'était qu'une
redirection vers `/knowledge`, disparaît également.

Un éventuel retour de la fonctionnalité passera par une nouvelle spécification.

### 11.4 Annonces Institutionnelles — RETIRÉE (2026-09-24)

Le module d'annonces (publication d'un message à destination de tout ou partie
des rôles, avec catégorie, priorité, canaux de diffusion et statistiques de
consultation) a été retiré du périmètre à la même date, avec ses cinq tables
(`announcement`, `announcement_target_role`, `announcement_category`,
`announcement_priority`, `announcement_status`), ses routes API, ses événements
SSE `announcement.*` et le panneau « Annonce globale » de l'espace DG.

La table `announcement` était vide en production au moment du retrait.

**Conséquence sur les écrans conservés :**

- `/app/admin/communication` ne porte plus que les réglages de canaux et
  d'expéditeur, qui servent les notifications de tickets (email, SMS,
  notifications internes). La table `communication_setting` est conservée.
- Le panneau et la page de notifications perdent l'onglet « Annonces ». Les
  notifications non rattachées à un ticket sont désormais étiquetées
  « Système ».

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
| 2026-08-19 | Rattachement post-login pour un utilisateur authentifié par la plateforme centrale sans compte local (auto-provisioning silencieux si groupe support déjà présent, sinon écran de consentement `/consent` puis rattachement à `collaborateur-support`) — nouvel endpoint `POST /auth/consent/accept`, nouvelles pages `/legal/terms` et `/legal/privacy` — détails techniques dans `docs/mise-a-jour-backend.md`. |
| 2026-09-22 | Qualification : suppression de la saisie Direction / Département / Service (§7.1). Seule la DSI traitant les incidents, l'organisation traitante est désormais déduite côté serveur du rattachement du chef de service qui qualifie. Le formulaire `/app/queue` ne conserve que Catégorie, Priorité et Chef de division support. Exposition de la fonction (`requester_job`) et du matricule (`employee_matricule`) du demandeur, jusque-là lus par le frontend mais jamais fournis par l'API (§10.5) — détails techniques dans `docs/mise-a-jour-backend.md`. |
| 2026-09-24 | Retrait de la table **`communication_setting`** (migration Alembic `027`), table vide et singleton dont seules 3 colonnes sur 9 étaient consommées (`email_on`, `sms_on`, `sender_sms`). Les gardes étaient en *fail-open* : le comportement d'envoi est **inchangé**. Conséquence assumée : plus de coupe-circuit en base pour les mails et SMS — la coupure passe désormais par `SMTP_HOST` / `SMS_GATEWAY_URL` vides dans `.env`, donc un redémarrage. Écran `/app/admin/communication` supprimé (il n'était lié à aucun menu). **`activity_log` est conservée** — exigence §10.5 et §13 sur la journalisation des connexions — détails techniques dans `docs/mise-a-jour-backend.md`. |
| 2026-09-24 | Retrait des fonctionnalités **Base de connaissance** (§11.3) et **Annonces institutionnelles** (§11.4), ainsi que du référentiel *Statuts de compte*. Huit tables supprimées (migration Alembic `026`), aucune donnée métier perdue (`announcement` et `knowledge_article` étaient vides). La colonne `account.account_status` est conservée mais n'est plus validée contre un référentiel. Rouvre l'écart CDC **DG5** (panneau « Annonce globale » de l'espace DG), retrait assumé — détails techniques dans `docs/mise-a-jour-backend.md`. |
| 2026-09-22 | Figeage des identités organisationnelles (§10.5) : celles du demandeur à la création, celles de l'organisation traitante à la qualification. Une mutation de personnel ou une réorganisation de l'organigramme ne réécrit plus rétroactivement l'historique des tickets. Complète le figeage des intervenants (BR-TRACE-001) déjà en place — détails techniques dans `docs/mise-a-jour-backend.md`. |
