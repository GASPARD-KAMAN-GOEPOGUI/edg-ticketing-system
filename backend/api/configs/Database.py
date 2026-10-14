from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession
from sqlalchemy.orm import sessionmaker, declarative_base
from api.configs.Environment import get_environment

env = get_environment()

DATABASE_URL = (
    f"{env.DATABASE_DIALECT}://{env.DATABASE_USERNAME}:{env.DATABASE_PASSWORD}"
    f"@{env.DATABASE_HOSTNAME}:{env.DATABASE_PORT}/{env.DATABASE_NAME}"
)

# Connexion MySQL en UTC (= heure de Guinée), quel que soit le fuseau du serveur.
# En production (hébergeur en France), MySQL suit l'heure de Paris (CEST/CET) :
# NOW() et les valeurs par défaut des colonnes (created_at, updated_at…) étaient
# 1 à 2 h en avance, et incohérentes avec les dates écrites en UTC par
# l'application (interventions, résolution, échéances du cycle horaire).
MYSQL_UTC_INIT_COMMAND = "SET time_zone = '+00:00'"


def engine_connect_args(dialect: str) -> dict:
    """Arguments de connexion du pilote : fuseau UTC imposé pour MySQL."""
    return {"init_command": MYSQL_UTC_INIT_COMMAND} if dialect.startswith("mysql") else {}


engine = create_async_engine(
    DATABASE_URL,
    echo=False,          # SQL visible via setup_logging(debug=True) — pas de doublon
    pool_pre_ping=True,
    pool_recycle=3600,
    connect_args=engine_connect_args(env.DATABASE_DIALECT),
)

AsyncSessionLocal = sessionmaker(
    engine,
    class_=AsyncSession,
    expire_on_commit=False,
)

Base = declarative_base()
