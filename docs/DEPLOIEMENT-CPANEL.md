# Déploiement en production sur cPanel

Procédure suivie et vérifiée lors de la mise en production du 2026-10-13.

| Élément | Adresse / emplacement |
|---|---|
| Frontend (SPA statique) | https://support.edgportal.com → `~/public_html/support` |
| Backend (FastAPI via Passenger) | https://appsupport.edgportal.com → application Python `~/appsupport` |
| Base de données | MySQL cPanel (`supportdb`), importée depuis la base locale |
| Code source frontend | `~/edg-frontend` (clone de `edg-connect-frontend`) |
| Code source backend | `~/appsupport` (clone de `edg-connect-backend`, sans `tests/`) |

Contraintes de l'hébergement : Python 3.10, **pas de Redis**, Passenger
mono-thread pour Python, un cache **Varnish** devant les sites, Terminal cPanel
disponible.

Dans les commandes ci-dessous, `COMPTE` est le nom du compte cPanel (dossier
`/home/COMPTE`).

> **Collage dans le Terminal cPanel** — le terminal web fusionne parfois des
> lignes au collage (`import asynciofrom …`, `EOFncio.run(main())`). Coller les
> blocs d'un seul tenant ; sur une `SyntaxError` ou une commande introuvable,
> recoller le bloc. Ne jamais coller une ligne SQL seule dans bash.

---

## 1. Principes

- **Ne jamais coller le `.env` ou un token GitHub** dans un chat, un ticket ou
  un commit.
- **Le frontend n'a pas besoin d'application Node.** Le build produit des
  fichiers statiques (`index.html` + `assets/`) servis directement par le
  serveur web. L'application « Setup Node.js App » du frontend reste sur
  **Stop** : si elle est démarrée, cPanel réécrit le `.htaccess` de la racine
  du document avec un bloc Passenger et **tout le site passe en erreur 500**.
  Elle ne sert qu'à fournir l'environnement Node du build
  (`~/nodevenv/support/22`) — ne pas la supprimer, sinon cet environnement
  disparaît.
- **Le backend, lui, doit tourner** (Setup Python App → `appsupport` → Start).
- **Passenger n'exécute pas le démarrage FastAPI** (lifespan) : la préparation
  de la base se fait par `python -m api.cli init`, et les tâches périodiques par
  le cron `python -m api.cli cycle`.

---

## 2. Backend

### 2.1 Première installation

```bash
cd ~
git clone --no-checkout https://github.com/GASPARD-KAMAN-GOEPOGUI/edg-connect-backend.git appsupport
cd appsupport
git sparse-checkout set --no-cone '/*' '!/tests/'   # les tests ne sont pas déployés
git checkout main
```

Dans **Setup Python App** :

| Réglage | Valeur |
|---|---|
| Python version | 3.10 |
| Application root | `appsupport` |
| Application URL | `appsupport.edgportal.com` |
| Application startup file | `passenger_wsgi.py` |
| Application Entry point | `application` |

Ne saisir **aucune variable d'environnement** dans cette interface : elles
l'emporteraient sur le `.env` (une seule source de vérité).

Dépendances (dans le venv créé par cPanel) :

```bash
source /home/COMPTE/virtualenv/appsupport/3.10/bin/activate
cd ~/appsupport
pip install -r requirements.txt
```

### 2.2 Fichier `.env`

```bash
cd ~/appsupport
cp .env.production.example .env
chmod 600 .env
```

Remplacer chaque `CHANGEME` (voir les commentaires du fichier). Points
importants :

- `APP_ENV=production`, `DISABLE_AUTH=False`, `STATE_BACKEND=mysql`,
  `REDIS_URL=` vide, `SCHEDULER_IN_PROCESS=False`, `SEED_ORG_STRUCTURE=False`.
- `CORS_ORIGINS=["https://support.edgportal.com"]` (JSON, sans slash final).
- `ENCRYPTION_KEY` : **la même clé** que le `.env` local (base importée).
- `UPLOADS_DIR` : chemin absolu **hors** de `public_html` et hors de
  `~/appsupport`.
- `DATABASE_PASSWORD` : **éviter le caractère `@`** — il casse l'URL de
  connexion construite par `api/configs/Database.py`. Choisir un mot de passe
  sans `@`.

### 2.3 Base de données

1. Créer la base et l'utilisateur dans **Bases de données MySQL** (tous les
   privilèges), puis importer le dump de la base locale (phpMyAdmin).
2. Vérifier la conformité du schéma — lecture seule :

   ```bash
   cd ~/appsupport && source /home/COMPTE/virtualenv/appsupport/3.10/bin/activate
   python -m api.cli check
   ```

   Résultat attendu : `Schéma conforme au code : 0 écart.` Tant qu'un écart
   subsiste, **ne pas lancer `init`** (il refuse de toute façon).

3. Écart rencontré : table en `latin1_swedish_ci`
   (`appreciation : charset de latin1_swedish_ci au lieu de utf8mb4`).
   Diagnostiquer avant de corriger :
   - si les **colonnes** sont déjà en `utf8mb4` et que les accents s'affichent
     correctement, seul le jeu de caractères **par défaut** de la table est en
     cause :

     ```sql
     ALTER TABLE appreciation DEFAULT CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
     ```

     (aucune donnée réécrite) ;
   - ne **pas** utiliser `CONVERT TO CHARACTER SET` dans ce cas : cela
     réécrirait aussi la colonne JSON `infos` (`utf8mb4_bin`).

   Sauvegarder les lignes de la table (export JSON ou phpMyAdmin) avant toute
   modification.

4. Correction ponctuelle des anciennes connexions journalisées sans rôle
   (valeur `''` hors de l'ENUM `actor_role`) :

   ```sql
   UPDATE activity_log SET actor_role = 'public' WHERE actor_role = '';
   ```

   À faire une seule fois, après avoir vérifié que `'public'` figure dans
   l'ENUM de la colonne. Le code actuel journalise déjà `'public'`.

### 2.4 Initialisation et démarrage

```bash
cd ~/appsupport && source /home/COMPTE/virtualenv/appsupport/3.10/bin/activate
python -m api.cli init                       # → « Initialisation terminée. »
mkdir -p tmp && touch tmp/restart.txt        # redémarre l'application Python
```

`init` est idempotent : il ne crée que les tables, références et dossiers
manquants, et ne crée le compte admin de secours que si **aucun** admin
n'existe.

Vérifications :

```bash
curl -s -w "\n→ %{http_code}\n" https://appsupport.edgportal.com/health
# → {"status":"ok","database":"connected"}  → 200

curl -s -o /dev/null -w "CORS preflight → %{http_code}\n" -X OPTIONS \
  -H "Origin: https://support.edgportal.com" -H "Access-Control-Request-Method: POST" \
  https://appsupport.edgportal.com/api/v1/auth/login
# → 200
```

### 2.5 Tâche cron horaire

Test manuel :

```bash
cd /home/COMPTE/appsupport && /home/COMPTE/virtualenv/appsupport/3.10/bin/python -m api.cli cycle; echo "code retour : $?"
# → Cycle démarré… / Purge des entrées expirées : {…} / Cycle terminé. / code retour : 0
```

Puis **Tâches Cron** → « Une fois par heure » (`0 * * * *`) :

```
cd /home/COMPTE/appsupport && /home/COMPTE/virtualenv/appsupport/3.10/bin/python -m api.cli cycle >> /home/COMPTE/appsupport/cycle.log 2>&1
```

Le cycle purge les liaisons de session, compteurs de connexion et jetons
révoqués expirés, exécute la validation d'office et la fermeture automatique,
et termine les e-mails en attente. Un verrou en base (`app_lock`) empêche deux
cycles simultanés. Contrôle : `tail -5 ~/appsupport/cycle.log`.

### 2.6 Mise à jour du backend

```bash
cd ~/appsupport && source /home/COMPTE/virtualenv/appsupport/3.10/bin/activate
git pull                                     # le sparse-checkout est conservé
pip install -r requirements.txt
python -m api.cli check                      # doit afficher 0 écart
python -m api.cli init
touch tmp/restart.txt
curl -s -w "\n→ %{http_code}\n" https://appsupport.edgportal.com/health
```

---

## 3. Frontend

### 3.1 Configuration de build

`frontend/.env.production` est **versionné** et chargé automatiquement par
`npm run build` :

```
VITE_API_URL=https://appsupport.edgportal.com/api/v1
VITE_REALTIME_MODE=polling
```

Vite fige ces valeurs dans le JavaScript : toute modification exige un nouveau
build. En production, le temps réel fonctionne par **polling** (cloche relue
toutes les 30 s) — un flux SSE bloquerait un processus Passenger entier.

### 3.2 Première installation

```bash
cd ~
git clone https://github.com/GASPARD-KAMAN-GOEPOGUI/edg-connect-frontend.git edg-frontend
```

### 3.3 Build sur le serveur

```bash
source ~/nodevenv/support/22/bin/activate
cd ~/edg-frontend
npm ci --include=dev
RAYON_NUM_THREADS=1 GOMAXPROCS=1 UV_THREADPOOL_SIZE=2 npm run build
ls -a dist/client       # → .htaccess  assets  index.html
```

- `--include=dev` : npm est configuré en `omit=dev` sur l'hébergement ; sans
  cette option, Vite et les outils de build ne sont pas installés.
- `RAYON_NUM_THREADS=1 …` : l'hébergement limite le nombre de threads ; sans
  ces variables, le build plante (`EAGAIN` du pool de threads).
- `npm run build` vide `dist/` avant chaque build (script `prebuild`).
- Les noms des fichiers `assets/` diffèrent d'un build local, à taille égale :
  c'est attendu (ordre de génération des routes selon le chemin du projet).

### 3.4 Publication — première fois

La racine du document de `support.edgportal.com` est
**`~/public_html/support`** (et non `~/support`, qui est le dossier de
l'application Node). Elle contient déjà un `.htaccess` géré par CloudLinux
(bloc « DO NOT REMOVE ») : on le **conserve** et on ajoute nos règles
dessous.

```bash
cp -a ~/public_html/support ~/public_html-support-sauvegarde-$(date +%Y%m%d)
cp ~/public_html/support/.htaccess ~/htaccess-cloudlinux

cp -a ~/edg-frontend/dist/client/. ~/public_html/support/
{ cat ~/htaccess-cloudlinux; printf '\n\n'; cat ~/edg-frontend/dist/client/.htaccess; } > ~/public_html/support/.htaccess
```

Le `.htaccess` du projet (`frontend/public/.htaccess`) force HTTPS, renvoie
toutes les routes de l'application vers `index.html`, renvoie une vraie 404
pour un fichier `assets/` absent, interdit la mise en cache de `index.html`
et met les `assets/` en cache un an.

### 3.5 Publication — mises à jour

```bash
source ~/nodevenv/support/22/bin/activate
cd ~/edg-frontend && git pull
npm ci --include=dev
RAYON_NUM_THREADS=1 GOMAXPROCS=1 UV_THREADPOOL_SIZE=2 npm run build
cp -a dist/client/index.html dist/client/assets ~/public_html/support/
```

Ne **pas** recopier `.htaccess` (le bloc CloudLinux serait perdu) — sauf si
`frontend/public/.htaccess` a changé : refaire alors la fusion du §3.4.

Les anciens fichiers `assets/` restent dans le dossier ; ils sont inoffensifs
(un onglet ouvert avant la mise à jour peut encore les charger). Les supprimer
de temps en temps n'est pas obligatoire.

### 3.6 Vérifications

```bash
UA="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 Chrome/130.0 Safari/537.36"
for p in / /index.html /app/requests/1 /assets/inexistant.js; do
  echo "$p : $(curl -sI -A "$UA" "https://support.edgportal.com$p" | tr -d '\r' | grep -iE '^(HTTP|age|cache-control)' | tr '\n' ' ')"
done
```

| Adresse | Attendu |
|---|---|
| `/`, `/index.html` | `200`, `cache-control: no-cache, must-revalidate` |
| `/app/requests/1` | `200` (renvoi vers `index.html`) |
| `/assets/inexistant.js` | `404` |
| un fichier `/assets/…` réel | `200`, `max-age=31536000, immutable` |

Le `tr -d '\r'` est nécessaire : sans lui, les retours chariot des en-têtes
HTTP effacent l'affichage de la ligne.

---

## 4. Cache Varnish de l'hébergeur

Un cache Varnish est placé devant les sites (en-têtes `edge-cache-engine:
varnish`, `age`). Aucun bouton de purge n'est disponible dans cPanel.

- `index.html` n'est **pas** mis en cache (il respecte `no-cache`) : une mise à
  jour du frontend est visible immédiatement, sans purge.
- Les **404 sont mis en cache** quelques minutes. Si une adresse renvoie 404
  alors que le fichier existe, comparer avec `?v=123` à la fin de l'adresse :
  `200` avec le paramètre = ancienne 404 en cache, qui expirera d'elle-même.
  Si elle persiste, demander une purge au support de l'hébergeur.

---

## 5. Dépannage

| Symptôme | Cause | Solution |
|---|---|---|
| Frontend : 500 sur toutes les adresses | Application Node « support » démarrée : bloc Passenger dans le `.htaccess` | Stop dans Setup Node.js App, puis refaire la fusion du `.htaccess` (§3.4) |
| Frontend : 403 sur `/`, 404 ailleurs | Fichiers copiés hors de la racine du document | Copier dans `~/public_html/support` |
| Frontend : 404 sur une adresse qui existe | 404 en cache Varnish | Tester avec `?v=123` ; attendre l'expiration (§4) |
| `npm ci` : `ERESOLVE` | Version de nitro non alignée | La version de `nitro` est figée dans `package.json` ; ne pas la passer en plage `^` |
| Build : Vite ou un outil de build introuvable | `omit=dev` | `npm ci --include=dev` |
| Build : `EAGAIN` / thread pool | Limite de threads | Préfixer par `RAYON_NUM_THREADS=1 GOMAXPROCS=1 UV_THREADPOOL_SIZE=2` |
| Backend : connexion base refusée, mot de passe correct | `@` dans `DATABASE_PASSWORD` | Changer le mot de passe |
| Backend : `init` refuse de démarrer | Écart de schéma | `python -m api.cli check`, corriger l'écart (§2.3) |
| Connexion : erreur 500 | Valeur hors ENUM en base (mode MySQL strict) | Voir `docs/codex/KNOWN_ISSUES.md` (KI-ENUM-001) |
| Navigateur : erreur CORS | `CORS_ORIGINS` différent de l'origine exacte | `["https://support.edgportal.com"]`, puis `touch tmp/restart.txt` |

Journaux du backend : `~/appsupport/stderr.log` (s'il existe) et les journaux
d'erreurs de cPanel (**Métriques → Erreurs**).

---

## 6. Checklist de mise en production

- [ ] `python -m api.cli check` → 0 écart
- [ ] `python -m api.cli init` → « Initialisation terminée. »
- [ ] Application Python redémarrée (`touch tmp/restart.txt`)
- [ ] `/health` → 200, `"database":"connected"`
- [ ] Préflight CORS → 200
- [ ] Frontend publié dans `~/public_html/support`, `.htaccess` fusionné
- [ ] Application Node du frontend sur **Stop**
- [ ] Vérifications §3.6 conformes
- [ ] Cron horaire enregistré, `cycle.log` alimenté
- [ ] Test de fumée dans le navigateur (navigation privée) :
      connexion, liste des requêtes, détail d'une requête, pièce jointe,
      création d'une requête, cloche des notifications, déconnexion
