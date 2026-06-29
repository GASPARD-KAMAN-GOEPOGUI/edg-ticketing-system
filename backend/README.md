# EDG Connect — Backend API

Backend FastAPI pour la plateforme de gestion des requêtes d'Électricité de Guinée.

## Stack

- **FastAPI** — framework web async
- **SQLAlchemy 2 (async)** + **aiomysql** — ORM et driver MySQL async
- **Pydantic v1** — validation et sérialisation des schémas
- **Gunicorn** + **Uvicorn workers** — serveur de production
- **Pipenv** / **pip** — gestion des dépendances

## Prérequis

- Python 3.11+
- MySQL actif en local (WampServer ou autre)

## Installation

```bash
# Cloner et entrer dans le dossier backend
cd backend

# Option 1 — pip + venv
python -m venv venv
venv\Scripts\activate        # Windows
pip install -r requirements.txt

# Option 2 — Pipenv
pipenv install
pipenv shell

# Copier et adapter le .env
copy .env.example .env

# Créer la base de données MySQL (terminal admin)
mysql -u root -e "CREATE DATABASE IF NOT EXISTS edg_ticketing CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;"
```

## Lancer le serveur

```bash
# Développement (hot-reload)
uvicorn api.main:app --reload --host 0.0.0.0 --port 8000

# Production (gunicorn + uvicorn workers)
gunicorn api.main:app -c gunicorn_conf.py
```

Le serveur démarre sur **http://localhost:8000**

| URL | Description |
|-----|-------------|
| `GET /` | Message de bienvenue |
| `GET /health` | Test de connexion à la DB |
| `/docs` | Documentation Swagger interactive |
| `/redoc` | Documentation ReDoc |

## Architecture (couches)

```
routes → services → repositories → models
```

```
api/
├── main.py              # app FastAPI, CORS, routeurs
├── dependencies.py      # Depends() centralisés (get_db, etc.)
├── configs/
│   ├── Environment.py   # BaseSettings — lit le .env
│   └── Database.py      # create_async_engine + AsyncSession + Base
├── models/              # Modèles SQLAlchemy (tables DB)
├── repositories/        # Accès aux données (CRUD)
├── services/            # Logique métier
├── schemas/pydantic/    # Schémas Pydantic v1 (request/response)
└── routes/              # Routeurs FastAPI par domaine fonctionnel
```
