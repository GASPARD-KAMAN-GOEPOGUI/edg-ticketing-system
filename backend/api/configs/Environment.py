from functools import lru_cache
from typing import List

from pydantic import BaseSettings


class Environment(BaseSettings):
    # App
    APP_NAME: str = "EDG Support API"
    APP_VERSION: str = "0.1.0"
    APP_ENV: str = "development"
    DEBUG_MODE: bool = False
    PORT: int = 8000

    # Database
    DATABASE_DIALECT: str = "mysql+aiomysql"
    DATABASE_HOSTNAME: str = "localhost"
    DATABASE_PORT: int = 3306
    DATABASE_NAME: str = "edg_ticketing"
    DATABASE_USERNAME: str = "root"
    DATABASE_PASSWORD: str = ""

    # Plateforme centrale d'authentification manager-user
    CENTRAL_AUTH_BASE_URL: str = ""
    CLIENT_APP_CODE: str = ""
    CLIENT_APP_SECRET: str = ""
    HTTP_TIMEOUT_MS: int = 8000

    # Redis — rate limiting distribué (optionnel)
    REDIS_URL: str = ""

    # ClamAV — antivirus pour les pièces jointes (optionnel)
    CLAMAV_HOST: str = "localhost"
    CLAMAV_PORT: int = 3310
    CLAMAV_TIMEOUT: int = 30      # secondes
    CLAMAV_ENABLED: bool = False  # passer à True en production avec un daemon clamd

    # Auth
    DISABLE_AUTH: bool = False

    # Durée de vie (secondes) du cache des scopes/groupes centraux. Chaque requête
    # protégée validait le bearer token par DEUX appels HTTP à la plateforme
    # centrale ; un écran qui déclenche 5 requêtes coûtait 10 allers-retours. Le
    # cache les mutualise par token. Contrepartie assumée : un changement de
    # groupe ou une révocation côté central met jusqu'à TTL secondes à être vu —
    # d'où une valeur volontairement basse. 0 désactive le cache (comportement
    # historique, un appel réseau par requête).
    CENTRAL_AUTH_CACHE_TTL: int = 45

    # Seed — structure organisationnelle (unity + organigram)
    # True : le demarrage reinsere l'organigramme EDG de reference (comportement
    # historique). False : la structure est laissee entierement a la main de
    # l'admin, qui cree directions et services depuis le back-office ; le seed
    # n'y touche plus. Les autres references (statuts, priorites, categories)
    # restent semees dans les deux cas : ce sont des enums techniques.
    SEED_ORG_STRUCTURE: bool = True

    # CORS
    CORS_ORIGINS: List[str] = ["http://localhost:5173"]

    # SMTP
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USER: str = ""
    SMTP_PASSWORD: str = ""

    # SMS Gateway (générique HTTP — ex. Orange Guinée, Vonage, etc.)
    SMS_GATEWAY_URL: str = ""          # ex. https://api.orange.com/smsmessaging/v1/...
    SMS_API_KEY: str = ""              # clé ou token Bearer
    SMS_SENDER: str = "EDG"            # ID expéditeur des SMS

    # Chiffrement des champs sensibles (Fernet/AES-128)
    ENCRYPTION_KEY: str = ""           # clé Fernet base64 32-bytes ; vide = chiffrement désactivé

    class Config:
        env_file = ".env"
        env_file_encoding = "utf-8"
        case_sensitive = False


@lru_cache()
def get_environment() -> Environment:
    return Environment()
