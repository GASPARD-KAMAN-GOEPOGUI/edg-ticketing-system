"""
Commandes d'exploitation — EDG Support.

  python -m api.cli check   Contrôle le schéma de la base, en LECTURE SEULE stricte.
                            Code de sortie 0 si conforme, 2 si écart (liste
                            affichée), 1 si la base est injoignable.
  python -m api.cli init    Initialise la base (non destructif, voir api/bootstrap.py).
                            Code de sortie 2 si le schéma existant est incompatible.
  python -m api.cli cycle   Exécute UNE fois les tâches planifiées existantes
                            (validation d'office J+3, puis fermeture J+4), puis
                            se termine. Destiné au cron cPanel (toutes les heures).

À lancer depuis le dossier de l'application (celui de passenger_wsgi.py) pour
que le fichier .env soit trouvé.
"""
from __future__ import annotations

import argparse
import asyncio
import logging
import os
import socket
import sys
import uuid

logger = logging.getLogger("api.cli")

CYCLE_LOCK_NAME = "scheduler_cycle"
# Un cycle crashé (processus tué) libère le verrou à l'expiration : le cron
# horaire suivant peut alors le reprendre.
CYCLE_LOCK_TTL_SECONDS = 50 * 60
# Délai maximal laissé aux emails lancés en tâche de fond avant la sortie.
EMAIL_DRAIN_TIMEOUT_SECONDS = 60


async def run_check(*, engine=None) -> int:
    """Lecture seule : uniquement la réflexion du schéma (aucun create_all,
    aucun seed, aucune écriture)."""
    from sqlalchemy.exc import DBAPIError

    from api.bootstrap import check_schema
    from api.configs import Database

    try:
        issues = await check_schema(engine or Database.engine)
    except (DBAPIError, OSError) as exc:
        logger.error("Base injoignable : %s", exc)
        return 1
    if issues:
        logger.error(
            "Schéma incompatible avec le code (%d écart(s)) :\n  - %s",
            len(issues), "\n  - ".join(issues),
        )
        return 2
    logger.info("Schéma conforme au code : 0 écart.")
    return 0


async def run_init(*, engine=None, session_factory=None) -> int:
    from api.bootstrap import SchemaMismatchError, initialize

    try:
        await initialize(strict_schema=True, engine=engine, session_factory=session_factory)
    except SchemaMismatchError as exc:
        logger.error("%s", exc)
        logger.error("Initialisation interrompue : aucune modification n'a été faite en base.")
        return 2
    logger.info("Initialisation terminée.")
    return 0


async def run_cycle(*, session_factory=None, drain_emails: bool = True) -> int:
    """Un cycle complet sous verrou. Retourne 0 aussi quand le verrou est déjà
    pris (cycle précédent en cours) : ce n'est pas une erreur pour le cron."""
    from api.configs import Database
    from api.core import app_lock
    from api.core.scheduler import _job_auto_close, _job_auto_validation
    from api.services.NotificationEmitter import drain_background_emails

    session_factory = session_factory or Database.AsyncSessionLocal
    holder = f"{socket.gethostname()}:{os.getpid()}:{uuid.uuid4().hex[:8]}"

    if not await app_lock.acquire(session_factory, CYCLE_LOCK_NAME, holder, CYCLE_LOCK_TTL_SECONDS):
        logger.info("Cycle ignoré : un autre cycle est en cours (verrou %r).", CYCLE_LOCK_NAME)
        return 0
    try:
        logger.info("Cycle démarré (%s).", holder)
        # Ordre métier documenté dans scheduler.py : J+3 libère le circuit du
        # PV avant la fermeture J+4.
        await _job_auto_validation()
        await _job_auto_close()
        if drain_emails:
            unfinished = await drain_background_emails(EMAIL_DRAIN_TIMEOUT_SECONDS)
            if unfinished:
                logger.warning("%d email(s) non terminé(s) après %ss.", unfinished, EMAIL_DRAIN_TIMEOUT_SECONDS)
        logger.info("Cycle terminé.")
    finally:
        await app_lock.release(session_factory, CYCLE_LOCK_NAME, holder)
    return 0


async def _main_async(command: str) -> int:
    from api.configs import Database

    try:
        if command == "check":
            return await run_check()
        if command == "init":
            return await run_init()
        return await run_cycle()
    finally:
        await Database.engine.dispose()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m api.cli", description="Commandes d'exploitation EDG Support.")
    parser.add_argument("command", choices=["check", "init", "cycle"])
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s | %(levelname)-8s | %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    return asyncio.run(_main_async(args.command))


if __name__ == "__main__":
    sys.exit(main())
