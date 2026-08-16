# Mode de développement LAN

Permet d'utiliser EDG Connect depuis un téléphone ou un autre PC connecté au
**même réseau Wi-Fi/LAN** que le poste de développement, sans toucher à la
configuration habituelle.

## Démarrage normal (inchangé)

```powershell
# Frontend
cd frontend
npm run dev

# Backend (autre terminal)
cd backend
.\start-dev.ps1
```

Accessible uniquement depuis `http://localhost:3000` (frontend) et
`http://localhost:8000` (backend) sur ce PC.

## Démarrage LAN

Depuis la racine du projet :

```powershell
.\scripts\dev-lan.ps1
```

Le script :
1. détecte automatiquement l'adresse IPv4 LAN du PC (Wi-Fi/Ethernet, en
   ignorant VPN/WSL/Docker/vEthernet) ;
2. vérifie que les ports 8000 (backend) et 3000 (frontend) sont libres ;
3. vérifie le pare-feu Windows pour ces deux ports (crée les règles s'il est
   lancé en administrateur, sinon affiche la commande à lancer soi-même) ;
4. génère `frontend/.env.lan.local` (jamais committé) avec
   `VITE_API_URL=http://<IP_LAN>:8000/api/v1` ;
5. démarre le backend (`start-dev.ps1 -BindHost 0.0.0.0`) et le frontend
   (`vite dev --host 0.0.0.0 --mode lan`) dans deux fenêtres séparées ;
6. attend que les deux répondent, affiche les URLs et un QR code (best
   effort, nécessite une connexion internet — ignoré silencieusement sinon).

## Utilisation depuis le téléphone

1. Connecter le téléphone au **même réseau Wi-Fi** que le PC.
2. Lancer `.\scripts\dev-lan.ps1` sur le PC.
3. Scanner le QR code affiché, ou taper l'URL `http://<IP_LAN>:3000` dans le
   navigateur du téléphone.
4. Se connecter normalement (même formulaire de login, même JWT, mêmes
   droits que sur le PC).

Arrêter l'environnement LAN : `CTRL+C` dans la fenêtre du script — ferme le
backend et le frontend qu'il a démarrés (rien d'autre).

## Options du script

```powershell
.\scripts\dev-lan.ps1 -BackendPort 8000 -FrontendPort 3000
.\scripts\dev-lan.ps1 -IpAddress 192.168.1.25   # si la détection automatique se trompe
.\scripts\dev-lan.ps1 -NoQrCode                 # désactive l'appel réseau vers l'API de QR code
```

## Pourquoi ça fonctionne sans modifier le code

- **CORS** : `backend/api/main.py` autorise déjà toutes les origines en
  développement (`allow_origins=["*"]`), avec `allow_credentials=False` —
  sûr, car l'authentification EDG Connect n'utilise aucun cookie (JWT en
  header `Authorization: Bearer`, stocké en `localStorage`).
- **API URL** : le frontend lit `VITE_API_URL` comme URL absolue (nécessaire
  car TanStack Start intercepte `/api/*` avant le proxy Vite). Le mode LAN
  écrit cette variable dans `frontend/.env.lan.local`, chargé uniquement par
  `vite dev --mode lan` — `.env.development` (utilisé par `npm run dev`)
  n'est jamais modifié.
- **SSE** (notifications temps réel) : dérive aussi son URL de
  `VITE_API_URL`, donc fonctionne automatiquement en LAN.

## Dépannage

| Symptôme | Cause probable |
|---|---|
| Page blanche / ne charge pas sur le téléphone | Téléphone sur un autre réseau (4G, autre Wi-Fi) — vérifier qu'il est bien sur le même Wi-Fi que le PC |
| Frontend s'affiche mais aucune donnée / erreurs réseau | `frontend/.env.lan.local` mal généré, ou backend non démarré — relancer le script |
| "API non joignable via l'IP LAN" | Pare-feu Windows bloque le port 8000 — lancer la commande `New-NetFirewallRule` affichée par le script, en PowerShell administrateur |
| Port 8000 ou 3000 déjà utilisé | Un backend/frontend tourne déjà — fermez-le, ou relancez avec `-BackendPort`/`-FrontendPort` |
| Mauvaise IP détectée (VPN, Docker, WSL actif) | Forcer l'IP réelle : `.\scripts\dev-lan.ps1 -IpAddress 192.168.1.25` |
| QR code non généré | Pas de connexion internet (appel best-effort à une API publique) — utilisez l'URL affichée en texte |
