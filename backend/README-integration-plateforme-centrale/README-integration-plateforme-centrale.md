# README - Integration de la plateforme centrale `manager-user`

Ce README explique comment integrer une application avec la plateforme centrale
`manager-user` utilisee par EDG.

Il est concu pour etre transmis a une autre equipe afin qu'elle puisse reproduire
l'integration sans intervention supplementaire.

Plateforme centrale de reference :

```text
https://appsecu.edgportal.com
```

Exemple d'application deja integree :

```text
Link Hub
CLIENT_APP_CODE=linkhub-web
```

Important : le `CLIENT_APP_SECRET` ne doit jamais etre mis dans ce document, dans le
frontend, dans Git, dans les logs ou dans une capture d'ecran. Il doit rester cote
backend, dans un `.env` local, un coffre de secrets ou les variables d'environnement
du serveur.

## 1. Objectif de l'integration

L'integration permet a une application metier de deleguer a `manager-user` :

- l'authentification des utilisateurs ;
- la generation et la validation des tokens ;
- le refresh des sessions ;
- la recuperation des scopes de l'utilisateur connecte ;
- la recuperation des groupes de l'utilisateur connecte ;
- le mapping des groupes centraux vers les roles applicatifs ;
- la creation et le rattachement des comptes a un groupe applicatif ;
- la modification des informations d'un compte central ;
- l'activation, la desactivation, la suppression et le reset mot de passe ;
- l'envoi de logs d'audit centralises.

L'application garde une table locale minimale, souvent appelee `accounts`, pour
stocker les informations utiles a l'interface metier : role applicatif, etat local,
nom affiche, identifiants centraux, etc.

## 2. Architecture recommandee

Le frontend ne communique jamais directement avec la plateforme centrale pour les
operations sensibles. Il appelle toujours le backend applicatif.

```text
Frontend
  |
  | 1. POST /api/auth/login
  v
Backend applicatif
  |
  | 2. source-token, login, scopes, groupes, comptes, logs
  v
Plateforme centrale manager-user
```

Raison : le backend possede le `CLIENT_APP_SECRET`. Le frontend ne doit jamais y
avoir acces.

## 3. Prerequis cote plateforme centrale

Avant de coder l'integration, demander ou creer dans `manager-user` :

1. une application cliente ;
2. un `CLIENT_APP_CODE` ;
3. un `CLIENT_APP_SECRET` ;
4. les groupes applicatifs necessaires ;
5. les scopes applicatifs necessaires ;
6. au moins un utilisateur admin de test rattache au bon groupe.

Pour Link Hub, les groupes utilises sont :

```text
admin-link-hub
manager-link-hub
collaborateur-linkhub
```

Pour une autre application, definir des groupes equivalents, par exemple :

```text
admin-mon-app
manager-mon-app
collaborateur-mon-app
```

## 4. Variables d'environnement

### Backend

Ajouter les variables suivantes cote backend :

```env
CENTRAL_AUTH_BASE_URL=https://appsecu.edgportal.com
CLIENT_APP_CODE=code-de-votre-application
CLIENT_APP_SECRET=secret-fourni-par-manager-user
HTTP_TIMEOUT_MS=8000
```

Variables applicatives classiques a conserver selon le projet :

```env
DATABASE_URL=mysql+pymysql://user:password@host:3306/database
JWT_SECRET_KEY=secret-local-pour-le-fallback
FRONTEND_ORIGINS=http://localhost:8080,https://votre-frontend.com
ACCESS_TOKEN_EXPIRE_MINUTES=480
```

### Frontend

Le frontend doit connaitre uniquement l'URL du backend applicatif :

```env
VITE_API_BASE_URL=http://127.0.0.1:8001/api
```

Ne jamais ajouter les variables suivantes au frontend :

```text
CLIENT_APP_SECRET
source_token
token machine
```

## 5. Dependances backend

Ajouter un client HTTP cote backend. Dans Link Hub, la dependance utilisee est :

```txt
httpx==0.28.1
```

Installation :

```bash
pip install httpx==0.28.1
```

Recommandation importante : utiliser `trust_env=False` avec `httpx.Client`.
Cela evite que des variables proxy locales mal configurees interceptent les appels
vers la plateforme centrale.

Exemple :

```python
with httpx.Client(base_url=CENTRAL_AUTH_BASE_URL, timeout=8, trust_env=False) as client:
    response = client.post("/v1/auth/login", json=payload)
```

## 6. Endpoints centraux utilises

### Authentification client : source token

Endpoint central :

```text
POST /v1/client-app-auth/source-token
```

Payload envoye par le backend applicatif :

```json
{
  "client_code": "code-de-votre-application",
  "client_secret": "secret-de-votre-application"
}
```

Reponse attendue :

```json
{
  "source_token": "source-token",
  "token_type": "bearer",
  "expires_in": 300,
  "client_code": "code-de-votre-application"
}
```

Le `source_token` sert uniquement a executer le login utilisateur. Il ne doit pas
etre retourne au frontend.

### Login utilisateur

Endpoint central :

```text
POST /v1/auth/login
```

Payload envoye par le backend applicatif :

```json
{
  "email": "utilisateur@edg.com.gn",
  "password": "mot-de-passe",
  "source_token": "source-token-recu"
}
```

Reponse centrale possible :

```json
{
  "user_id": 1398,
  "bearer_token": "access-token-central",
  "refresh_token": "refresh-token-central",
  "client_app_id": 1,
  "token_type": "bearer",
  "expires_in": 180,
  "refresh_expires_in": 3600,
  "expires_at": "2026-08-01T15:20:00Z",
  "refresh_expires_at": "2026-08-01T16:17:00Z"
}
```

Selon les versions, le token peut s'appeler `bearer_token` ou `access_token`.
Le backend doit accepter les deux noms et retourner au frontend un contrat stable.

### Refresh token

Endpoint central :

```text
POST /v1/auth/refresh
```

Payload envoye par le backend applicatif :

```json
{
  "refresh_token": "refresh-token-central"
}
```

Le central retourne un nouveau bearer token et les nouvelles durees d'expiration.
Le backend ne doit pas recalculer artificiellement la duree restante du refresh
token : il doit utiliser les champs renvoyes par le central.

### Scopes de l'utilisateur connecte

Endpoint central :

```text
GET /v1/auth/me/scopes
Authorization: Bearer <bearer-central>
```

Reponse type :

```json
{
  "actor_type": "user",
  "user_id": 1398,
  "email": "utilisateur@edg.com.gn",
  "client_app_id": 1,
  "client_code": "linkhub-web",
  "source": "central",
  "scopes": [
    "account-link-hub.read",
    "applications-link-hub.read"
  ]
}
```

### Groupes de l'utilisateur connecte

Endpoint central :

```text
GET /api/me/groups
Authorization: Bearer <bearer-central>
```

Reponse type :

```json
[
  {
    "group_id": 10,
    "uuid": "uuid-du-groupe",
    "name": "Admin Link Hub",
    "codename": "admin-link-hub",
    "infos": {},
    "is_activated": true,
    "description": "Administrateurs Link Hub"
  }
]
```

Les groupes inactifs ne doivent pas donner de role applicatif.

### Token machine pour actions d'administration

Endpoint central :

```text
POST /v1/client-app-auth/token
```

Payload envoye par le backend :

```json
{
  "client_app_code": "code-de-votre-application",
  "client_app_secret": "secret-de-votre-application"
}
```

Reponse attendue :

```json
{
  "access_token": "token-machine",
  "token_type": "bearer",
  "expires_in": 300,
  "client_app_code": "code-de-votre-application"
}
```

Ce token machine est utilise uniquement cote backend pour certaines operations
sur les comptes centraux.

## 7. Contrat API recommande cote application

Le frontend appelle le backend applicatif, pas le central.

### Login applicatif

Route applicative :

```text
POST /api/auth/login
```

Payload frontend :

```json
{
  "email": "utilisateur@edg.com.gn",
  "password": "mot-de-passe"
}
```

Reponse backend recommandee :

```json
{
  "access_token": "bearer-central",
  "token_type": "bearer",
  "expires_in": 180,
  "refresh_token": "refresh-central",
  "refresh_expires_in": 3600,
  "expires_at": "2026-08-01T15:20:00Z",
  "refresh_expires_at": "2026-08-01T16:17:00Z",
  "user": {
    "id": "central:1398",
    "user_id": 1398,
    "user_uuid": "",
    "email": "utilisateur@edg.com.gn",
    "full_name": "utilisateur",
    "phone": "",
    "job_title": "",
    "direction": "",
    "must_change_password": false,
    "role": "admin",
    "is_active": true
  }
}
```

### Refresh applicatif

Route applicative :

```text
POST /api/auth/refresh
```

Payload frontend :

```json
{
  "refresh_token": "refresh-central"
}
```

Le backend relaie vers `/v1/auth/refresh`, reconstruit la reponse applicative,
puis le frontend remplace le bearer token stocke.

### Utilisateur courant

Routes applicatives utiles :

```text
GET /api/auth/me
GET /api/auth/me/scopes
GET /api/auth/me/groups
DELETE /api/auth/logout
```

Chaque route protegee doit recevoir :

```text
Authorization: Bearer <access-token>
```

## 8. Validation des routes protegees

Le backend doit accepter deux modes :

1. mode central, si les variables centrales sont configurees ;
2. mode local, si les variables centrales sont absentes.

En mode central, pour valider un bearer token :

1. lire le header `Authorization` ;
2. extraire le bearer token ;
3. appeler `/v1/auth/me/scopes` ;
4. appeler `/api/me/groups` ;
5. construire un utilisateur applicatif temporaire ;
6. mapper ses groupes vers un role applicatif ;
7. appliquer les guards applicatifs habituels.

En mode local, l'application peut conserver son JWT local pour le developpement ou
un fallback d'urgence.

## 9. Mapping groupes centraux vers roles applicatifs

Exemple Link Hub :

```text
admin-link-hub          -> admin
manager-link-hub        -> editor
collaborateur-linkhub   -> viewer
```

Priorite recommandee :

```text
admin > editor > viewer
```

Si un utilisateur appartient a plusieurs groupes actifs, appliquer le role le plus
eleve.

Exemple de fonction :

```python
GROUP_ROLE_PRIORITY = {
    "admin-link-hub": "admin",
    "manager-link-hub": "editor",
    "collaborateur-linkhub": "viewer",
}

def role_from_groups(groups):
    active_codenames = {
        group["codename"].strip().lower()
        for group in groups
        if group.get("is_activated") is not False
    }

    for codename, role in GROUP_ROLE_PRIORITY.items():
        if codename in active_codenames:
            return role

    return "viewer"
```

## 10. Scopes applicatifs

Les scopes servent aux permissions fines. Les groupes servent au role principal
dans l'interface.

Scopes Link Hub :

```text
account-link-hub.create
account-link-hub.delete
account-link-hub.detail
account-link-hub.read
account-link-hub.update
applications-link-hub.create
applications-link-hub.delete
applications-link-hub.detail
applications-link-hub.read
applications-link-hub.update
```

Pour une nouvelle application, definir une convention claire :

```text
resource-mon-app.read
resource-mon-app.detail
resource-mon-app.create
resource-mon-app.update
resource-mon-app.delete
```

## 11. Table locale `accounts`

L'application doit garder un miroir local minimal. Exemple de champs :

```text
id                    UUID local, cle primaire
user_id               identifiant numerique central
user_uuid             UUID central
email                 email utilisateur
full_name             nom affiche dans l'application
phone                 telephone
password_hash         fallback local uniquement
role                  role applicatif local: admin, editor, viewer
is_active             etat local
must_change_password  utile pour fallback local
created_at
updated_at
```

Regles :

- `user_id` est necessaire pour la suppression centrale via `/v1/users/{user_id}` ;
- `user_uuid` est necessaire pour la modification, l'activation, la desactivation
  et le reset mot de passe ;
- ne pas creer manuellement de compte local sans rattachement central en production
  centralisee ;
- en developpement local, un compte sans `user_id` ni `user_uuid` peut exister
  seulement si le fallback local est volontairement utilise.

## 12. Gestion des comptes

### Creation d'un compte

Route applicative recommandee :

```text
POST /api/accounts
```

Payload frontend :

```json
{
  "email": "m.diallo@edg.com.gn",
  "full_name": "Mamadou Diallo",
  "phone": "+224625000000",
  "role": "viewer",
  "is_active": true
}
```

Le backend transforme le role applicatif en groupe central :

```text
admin  -> admin-link-hub
editor -> manager-link-hub
viewer -> collaborateur-linkhub
```

Endpoint central :

```text
POST /v1/client-app-users/group-membership
```

Payload backend vers central :

```json
{
  "group_codename": "collaborateur-linkhub",
  "email": "m.diallo@edg.com.gn",
  "phone": "+224625000000",
  "name": "Mamadou",
  "last_name": "Diallo",
  "password": "EDG2026@"
}
```

Points importants :

- cet endpoint de creation/rattachement est public ;
- aucun bearer machine n'est requis ;
- `client_app_code` n'est pas envoye dans ce payload ;
- le central cherche l'utilisateur par `email OR phone` ;
- le central cree l'appartenance active si elle n'existe pas deja ;
- le backend cree ou met a jour ensuite le miroir local `accounts`.

Statuts centraux possibles :

```text
created_and_added
existing_added
already_member
identity_conflict
```

Reponse centrale type :

```json
{
  "status": "created_and_added",
  "message": null,
  "client_app_code": "public",
  "user_id": 15,
  "user_uuid": "uuid-central",
  "user_is_activated": true,
  "group_codename": "collaborateur-linkhub"
}
```

### Modification d'un compte

Route applicative :

```text
PUT /api/accounts/{account_id}
```

Payload frontend :

```json
{
  "email": "m.diallo@edg.com.gn",
  "full_name": "Mamadou Diallo",
  "phone": "+224625000000",
  "role": "editor",
  "is_active": true
}
```

Le backend recupere d'abord un token machine :

```text
POST /v1/client-app-auth/token
```

Puis met a jour le compte central :

```text
PUT /v1/client-app-users/{user_uuid}
Authorization: Bearer <token-machine>
```

Payload :

```json
{
  "email": "m.diallo@edg.com.gn",
  "phone": "+224625000000",
  "name": "Mamadou",
  "last_name": "Diallo"
}
```

Si le role change, le backend ajoute l'utilisateur au nouveau groupe puis le retire
de l'ancien groupe.

Ajout groupe :

```text
PUT /v1/client-app-users/group-membership
Authorization: Bearer <token-machine>
```

```json
{
  "user_uuid": "uuid-central",
  "group_codename": "manager-link-hub"
}
```

Retrait groupe :

```text
DELETE /v1/client-app-users/group-membership
Authorization: Bearer <token-machine>
```

```json
{
  "user_uuid": "uuid-central",
  "group_codename": "collaborateur-linkhub"
}
```

### Activation

Route applicative :

```text
POST /api/accounts/{account_id}/activate
```

Endpoint central :

```text
POST /v1/client-app-users/{user_uuid}/activate
Authorization: Bearer <token-machine>
```

Payload :

```json
{}
```

Le backend met ensuite `accounts.is_active = true` selon la reponse centrale.

### Desactivation

Route applicative :

```text
POST /api/accounts/{account_id}/deactivate
```

Endpoint central :

```text
POST /v1/client-app-users/{user_uuid}/deactivate
Authorization: Bearer <token-machine>
```

Payload :

```json
{}
```

Le backend met ensuite `accounts.is_active = false` selon la reponse centrale.

### Reset mot de passe

Route applicative :

```text
POST /api/accounts/{account_id}/reset-password
```

Le frontend ne doit pas saisir ni envoyer de nouveau mot de passe admin. Il declenche
seulement l'action apres confirmation.

Endpoint central :

```text
POST /v1/client-app-users/{user_uuid}/reset-password
Authorization: Bearer <token-machine>
```

Payload envoye par le backend :

```json
{
  "password": "EDG2026@"
}
```

Dans Link Hub, la valeur par defaut est :

```text
EDG2026@
```

Adapter cette valeur si votre projet impose une autre politique.

### Suppression

Route applicative :

```text
DELETE /api/accounts/{account_id}
```

Endpoint central :

```text
DELETE /v1/users/{user_id}
Authorization: Bearer <bearer-utilisateur-central>
```

Points importants :

- la suppression utilise le bearer token de l'utilisateur connecte, pas le token machine ;
- le compte local doit avoir un `user_id` central ;
- apres succes central, supprimer le miroir local `accounts` ;
- interdire a un utilisateur de supprimer ou desactiver son propre compte ;
- afficher une confirmation UI obligatoire avant l'action.

## 13. Audit centralise

Les mutations applicatives doivent envoyer un log vers :

```text
POST /v1/logs/
Authorization: Bearer <bearer-utilisateur-central>
```

Payload recommande :

```json
{
  "object_id": "id-local-ou-central",
  "infos": {
    "action": "create",
    "action_family": "account",
    "status": "success",
    "object_id": "id-local-ou-central",
    "message": "Compte cree: m.diallo@edg.com.gn",
    "request_payload": {},
    "before": {},
    "after": {}
  }
}
```

Actions recommandees :

```text
create
update
delete
activate
reset_password
```

Familles recommandees :

```text
account
application
```

L'audit doit etre non bloquant. Si l'envoi du log echoue, l'action metier ne doit
pas echouer uniquement pour cette raison.

Masquer les champs sensibles avant envoi :

```text
password
client_secret
secret
token
source_token
bearer_token
refresh_token
authorization
```

## 14. Comportement frontend attendu

Le frontend doit :

1. appeler `POST /api/auth/login` ;
2. stocker `access_token`, `refresh_token`, `expires_at` et l'utilisateur courant ;
3. envoyer `Authorization: Bearer <access_token>` sur les routes protegees ;
4. en cas de `401`, appeler une seule fois `POST /api/auth/refresh` ;
5. remplacer le bearer token si le refresh reussit ;
6. rejouer la requete initiale une seule fois ;
7. nettoyer la session locale si le refresh echoue ;
8. afficher les actions selon le role applicatif retourne par le backend ;
9. afficher une confirmation avant suppression, activation, desactivation et reset
   mot de passe.

Ne pas deduire le role uniquement cote frontend depuis les scopes. Le backend doit
retourner un `user.role` deja resolu.

## 15. Confirmations UI obligatoires

Les actions suivantes doivent toujours demander une confirmation :

```text
suppression
activation
desactivation
reset mot de passe
```

Pattern recommande :

1. clic sur l'action ;
2. affichage d'une confirmation avec le nom de l'utilisateur ;
3. execution backend uniquement apres confirmation ;
4. toast de succes ou d'erreur ;
5. rafraichissement de la liste locale.

Pour le reset mot de passe, afficher clairement le mot de passe par defaut applique
par le backend.

## 16. Fallback local

Le backend peut conserver un mode local si une des variables suivantes est absente :

```text
CENTRAL_AUTH_BASE_URL
CLIENT_APP_CODE
CLIENT_APP_SECRET
```

Dans ce mode :

- login par JWT local ;
- verification du `password_hash` local ;
- roles lus depuis `accounts.role` ;
- activation/desactivation locales ;
- pas d'appel central ;
- pas d'audit central.

Ce fallback est pratique en developpement. En production centralisee, les trois
variables centrales doivent etre presentes.

## 17. Gestion des erreurs frequentes

### `Service d'authentification central indisponible`

Causes possibles :

- URL centrale incorrecte ;
- reseau indisponible ;
- proxy local mal configure ;
- timeout trop bas ;
- certificat ou DNS non accessible depuis le serveur.

Actions :

```bash
curl https://appsecu.edgportal.com
```

Verifier aussi l'utilisation de `trust_env=False` si le poste de developpement a
des variables proxy parasites.

### `invalid_client_credentials`

Causes possibles :

- `CLIENT_APP_CODE` incorrect ;
- `CLIENT_APP_SECRET` incorrect ;
- secret non charge par le backend ;
- mauvaise variable d'environnement sur le serveur.

### `invalid_source_token`

Le backend doit demander un nouveau `source_token` et retenter le login une fois.
Si l'erreur persiste, verifier l'horloge serveur, les credentials client et la duree
de validite du source token.

### Role incorrect dans l'interface

Verifier :

```text
GET /api/auth/me/groups
GET /api/auth/me/scopes
```

Verifier ensuite :

- le `codename` exact du groupe ;
- l'etat `is_activated` du groupe ;
- le mapping groupe -> role ;
- la priorite entre roles.

### Compte local non rattache au central

Messages possibles :

```text
Ce compte local n'est pas rattache a un user_uuid central.
Ce compte local n'est pas rattache a un user_id central.
```

Causes :

- compte cree manuellement en base ;
- creation centrale echouee mais miroir local cree ;
- migration incomplete depuis une ancienne table `users`.

Actions :

- verifier `accounts.user_id` ;
- verifier `accounts.user_uuid` ;
- recreer ou resynchroniser le compte via la plateforme centrale ;
- eviter les creations locales directes en production centralisee.

### CORS ou appel frontend bloque

Verifier que l'origine frontend est autorisee cote backend :

```env
FRONTEND_ORIGINS=http://localhost:8080,https://votre-frontend.com
```

Le frontend doit appeler le backend applicatif :

```env
VITE_API_BASE_URL=https://votre-backend.com/api
```

## 18. Tests rapides

Remplacer les valeurs d'exemple avant execution.

Healthcheck backend :

```bash
curl http://127.0.0.1:8001/api/health
```

Login applicatif :

```bash
curl -X POST http://127.0.0.1:8001/api/auth/login \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"utilisateur@edg.com.gn\",\"password\":\"mot-de-passe\"}"
```

Scopes :

```bash
curl http://127.0.0.1:8001/api/auth/me/scopes \
  -H "Authorization: Bearer <bearer-central>"
```

Groupes :

```bash
curl http://127.0.0.1:8001/api/auth/me/groups \
  -H "Authorization: Bearer <bearer-central>"
```

Utilisateur courant :

```bash
curl http://127.0.0.1:8001/api/auth/me \
  -H "Authorization: Bearer <bearer-central>"
```

Liste des comptes :

```bash
curl http://127.0.0.1:8001/api/accounts \
  -H "Authorization: Bearer <bearer-central>"
```

Creation d'un compte :

```bash
curl -X POST http://127.0.0.1:8001/api/accounts \
  -H "Authorization: Bearer <bearer-central>" \
  -H "Content-Type: application/json" \
  -d "{\"email\":\"m.diallo@edg.com.gn\",\"full_name\":\"Mamadou Diallo\",\"phone\":\"+224625000000\",\"role\":\"viewer\",\"is_active\":true}"
```

Refresh :

```bash
curl -X POST http://127.0.0.1:8001/api/auth/refresh \
  -H "Content-Type: application/json" \
  -d "{\"refresh_token\":\"<refresh-token-central>\"}"
```

## 19. Checklist d'integration

### Preparation centrale

- [ ] Application cliente creee dans `manager-user`.
- [ ] `CLIENT_APP_CODE` recupere.
- [ ] `CLIENT_APP_SECRET` recupere et stocke uniquement cote backend.
- [ ] Groupes applicatifs crees.
- [ ] Scopes applicatifs crees.
- [ ] Utilisateur admin de test rattache au groupe admin.

### Backend

- [ ] Variables `CENTRAL_AUTH_BASE_URL`, `CLIENT_APP_CODE`, `CLIENT_APP_SECRET` ajoutees.
- [ ] Client HTTP central implemente avec timeout et `trust_env=False`.
- [ ] Flux `source-token` puis `login` implemente.
- [ ] Refresh token implemente.
- [ ] Validation bearer central implemente.
- [ ] Recuperation `/v1/auth/me/scopes` implemente.
- [ ] Recuperation `/api/me/groups` implemente.
- [ ] Mapping groupes -> roles implemente.
- [ ] Table locale `accounts` creee ou adaptee.
- [ ] Creation compte central + miroir local branchee.
- [ ] Modification compte central + miroir local branchee.
- [ ] Changement de groupe central branche.
- [ ] Activation/desactivation branchees.
- [ ] Reset mot de passe branche.
- [ ] Suppression centrale + suppression locale branchees.
- [ ] Audit centralise branche et non bloquant.
- [ ] Masquage des champs sensibles dans les logs.

### Frontend

- [ ] Login via backend applicatif.
- [ ] Bearer token ajoute aux routes protegees.
- [ ] Refresh automatique sur `401`.
- [ ] Nettoyage session si refresh impossible.
- [ ] Affichage selon `user.role`.
- [ ] Confirmations UI pour actions sensibles.
- [ ] Aucun secret central present dans le bundle frontend.

### Verification

- [ ] Login admin central reussi.
- [ ] `/api/auth/me` retourne le bon role.
- [ ] `/api/auth/me/groups` retourne les groupes attendus.
- [ ] `/api/auth/me/scopes` retourne les scopes attendus.
- [ ] Creation compte test reussie.
- [ ] Modification role test reussie.
- [ ] Activation/desactivation test reussies.
- [ ] Reset mot de passe test reussi.
- [ ] Suppression test reussie.
- [ ] Logs visibles cote central.

## 20. Regles de securite a respecter

- Ne jamais exposer `CLIENT_APP_SECRET` au frontend.
- Ne jamais commiter `.env` contenant les secrets.
- Ne jamais journaliser les mots de passe, tokens ou secrets.
- Toujours passer par le backend pour les actions sensibles.
- Utiliser `Authorization: Bearer <token>` uniquement en header.
- Ne pas transmettre de token dans les query params.
- Les tokens machine doivent rester temporaires et uniquement cote backend.
- L'audit ne doit pas contenir de donnees sensibles.
- Les actions destructives doivent demander confirmation.
- L'utilisateur ne doit pas pouvoir supprimer ou desactiver son propre compte admin.

## 21. Structure de reference Link Hub

Dans Link Hub, les fichiers utiles sont :

```text
backend/app/central_auth.py      client central, login, refresh, scopes, groupes, comptes
backend/app/central_audit.py     logs centralises et masquage des donnees sensibles
backend/app/deps.py              validation JWT local ou bearer central
backend/app/routers/auth.py      routes /api/auth/*
backend/app/routers/users.py     routes /api/accounts et alias /api/users
backend/app/models.py            table locale accounts
backend/app/config.py            variables d'environnement
backend/app/main.py              montage des routes et compatibilite /api/users
src/lib/auth.ts                  stockage session et refresh automatique frontend
src/lib/usersStore.ts            appels frontend de gestion des comptes
```

Ce projet peut servir de reference concrete pour reproduire l'integration dans une
autre application.
