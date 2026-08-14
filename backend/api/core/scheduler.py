"""
Planificateur de tâches APScheduler — EDG Connect.

Jobs enregistrés :
  auto_escalation  — toutes les 10 min : escalade automatique SLA
  auto_close       — toutes les 6 h   : fermeture tickets résolus depuis > 4 jours
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

_scheduler = AsyncIOScheduler(timezone="UTC")

AUTO_CLOSE_DAYS = 4  # jours avant fermeture automatique après résolution


async def _job_auto_escalation() -> None:
    """Marque les SLA dépassés puis escalade les tickets concernés."""
    try:
        from api.configs.Database import AsyncSessionLocal
        from api.services.ServiceEscalade import EscaladeService

        async with AsyncSessionLocal() as session:
            svc = EscaladeService(session)
            # BR-NOTIFICATION-WORKFLOW-001 §14 — alerte préventive avant dépassement,
            # exécutée avant le marquage effectif du dépassement (ordre sans incidence
            # fonctionnelle : un ticket qui vient de dépasser son SLA à ce passage
            # précis n'est simplement pas éligible à l'alerte préventive ce tour-ci).
            await svc.warn_sla_approaching()
            await svc.mark_sla_breached()
            count = await svc.run_auto_escalation()
            await session.commit()
            if count:
                logger.info("[Scheduler] auto_escalation : %d ticket(s) escaladé(s).", count)
    except Exception as exc:
        logger.error("[Scheduler] auto_escalation échoué : %s", exc)


async def _job_auto_close() -> None:
    """Ferme automatiquement les tickets résolus depuis plus de 4 jours sans confirmation utilisateur."""
    try:
        from sqlalchemy import select
        from api.configs.Database import AsyncSessionLocal
        from api.models.ModelRequest import Request as RequestModel
        from api.models.ModelRequestStatus import RequestStatus
        from api.services.ServiceRequest import RequestService

        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=AUTO_CLOSE_DAYS)

        async with AsyncSessionLocal() as session:
            result = await session.execute(
                select(RequestModel.id)
                .join(RequestStatus, RequestModel.request_status_id == RequestStatus.id)
                .where(RequestStatus.code == "resolved")
                .where(RequestModel.resolved_at.isnot(None))
                .where(RequestModel.resolved_at <= cutoff)
                .where(RequestModel.deleted_at.is_(None))
            )
            ids = [row[0] for row in result.all()]

            if not ids:
                return

            svc = RequestService(session)
            closed = 0
            for req_id in ids:
                try:
                    await svc.close(str(req_id), actor_id=None)
                    closed += 1
                except Exception as exc:
                    logger.warning("[Scheduler] auto_close ticket %s échoué : %s", req_id, exc)

            await session.commit()
            if closed:
                logger.info("[Scheduler] auto_close : %d ticket(s) fermé(s) automatiquement.", closed)
    except Exception as exc:
        logger.error("[Scheduler] auto_close échoué : %s", exc)


def start_scheduler(interval_minutes: int = 10) -> None:
    """Démarre le scheduler et enregistre tous les jobs."""
    # Job "auto_escalation" désactivé sur demande : plus aucune action automatique
    # sur le SLA (alerte préventive, marquage de dépassement, escalade + réassignation
    # automatique) — un ticket ne doit plus changer de statut/responsable sans action
    # humaine explicite. `_job_auto_escalation()` / `warn_sla_approaching()` /
    # `mark_sla_breached()` / `run_auto_escalation()` restent en place, simplement
    # plus invoqués automatiquement.
    _scheduler.add_job(
        _job_auto_close,
        trigger=IntervalTrigger(hours=6),
        id="auto_close",
        replace_existing=True,
        misfire_grace_time=300,
    )
    _scheduler.start()
    logger.info(
        "[Scheduler] Démarré — auto_escalation désactivé, auto_close toutes les 6h.",
    )


def stop_scheduler() -> None:
    """Arrête proprement le scheduler."""
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[Scheduler] Arrêté.")
