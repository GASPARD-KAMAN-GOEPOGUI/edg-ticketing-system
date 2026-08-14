# À sourcer une fois par terminal, avant de lancer uvicorn :
#   . .\dev-env.ps1
#   uvicorn api.main:app --reload --port 8000
#
# UVICORN_RELOAD_DIRS limite la surveillance du hot-reload au code source
# (api/) au lieu de tout backend/ (venv/, __pycache__/, uploads/...), qui
# pouvait bloquer silencieusement le rechargement (serveur injoignable sans
# avoir été arrêté). Uvicorn lit ses options CLI depuis des variables
# d'environnement préfixées UVICORN_ (auto_envvar_prefix).

$env:UVICORN_RELOAD_DIRS = "api"
Write-Host "UVICORN_RELOAD_DIRS=api (surveillance du hot-reload limitée à api/)" -ForegroundColor Green
