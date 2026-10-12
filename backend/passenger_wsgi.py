"""
Point d'entrée Passenger (cPanel « Setup Python App ») — EDG Support API.

Réglages de l'application Python dans cPanel :
  - Application root        : dossier du backend (contient ce fichier et api/)
  - Application startup file: passenger_wsgi.py
  - Application Entry point : application

L'interpréteur du venv est choisi par cPanel (rien à configurer ici).
Passenger ne parle que WSGI : a2wsgi adapte l'application ASGI FastAPI.
"""
import os
import sys

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# .env est lu dans le répertoire courant (Environment.Config.env_file = ".env") :
# on se place dans le dossier de l'app quel que soit le répertoire de lancement.
os.chdir(BASE_DIR)
if BASE_DIR not in sys.path:
    sys.path.insert(0, BASE_DIR)

from a2wsgi import ASGIMiddleware  # noqa: E402

from api.main import app  # noqa: E402

application = ASGIMiddleware(app)
