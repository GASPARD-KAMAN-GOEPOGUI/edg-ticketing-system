"""
Planificateur de tâches APScheduler — EDG Connect.

Jobs enregistrés :
  auto_escalation  — toutes les 10 min : escalade automatique SLA
"""
from __future__ import annotations

import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

_scheduler = AsyncIOScheduler(timezone="UTC")


async def _job_auto_escalation() -> None:
    """Marque les SLA dépassés puis escalade les tickets concernés."""
    try:
        from api.configs.Database import AsyncSessionLocal
        from api.services.ServiceEscalade import EscaladeService

        async with AsyncSessionLocal() as session:
            svc = EscaladeService(session)
            await svc.mark_sla_breached()
            count = await svc.run_auto_escalation()
            await session.commit()
            if count:
                logger.info("[Scheduler] auto_escalation : %d ticket(s) escaladé(s).", count)
    except Exception as exc:
        logger.error("[Scheduler] auto_escalation échoué : %s", exc)


def start_scheduler(interval_minutes: int = 10) -> None:
    """Démarre le scheduler et enregistre tous les jobs."""
    _scheduler.add_job(
        _job_auto_escalation,
        trigger=IntervalTrigger(minutes=interval_minutes),
        id="auto_escalation",
        replace_existing=True,
        misfire_grace_time=60,
    )
    _scheduler.start()
    logger.info("[Scheduler] Démarré — auto_escalation toutes les %d min.", interval_minutes)


def stop_scheduler() -> None:
    """Arrête proprement le scheduler."""
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[Scheduler] Arrêté.")
