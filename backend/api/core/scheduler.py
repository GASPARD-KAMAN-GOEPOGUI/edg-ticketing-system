"""
Planificateur de tâches APScheduler — EDG Support.

Jobs enregistrés :
  auto_validation  — toutes les 6 h   : validation d'office des tickets résolus
                                        depuis > 3 jours sans réponse du demandeur
  auto_close       — toutes les 6 h   : fermeture tickets résolus depuis > 4 jours

L'ordre compte : la validation d'office passe à J+3 et libère le circuit du PV,
la fermeture suit à J+4. Un ticket validé (par le demandeur ou d'office) n'est
donc jamais fermé avant que son PV ait été soumis au chef de division.
"""
from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

logger = logging.getLogger(__name__)

_scheduler = AsyncIOScheduler(timezone="UTC")

AUTO_CLOSE_DAYS = 4  # jours avant fermeture automatique après résolution
# BR-AUTO-VALIDATION-001 — jours CALENDAIRES (week-end compris) laissés au
# demandeur pour valider la résolution ou rouvrir le ticket. Passé ce délai, le
# système valide à sa place et le PV part au chef de division : sans cela, un
# demandeur silencieux bloquait indéfiniment le circuit du PV.
AUTO_VALIDATION_DAYS = 3


async def _job_auto_validation() -> None:
    """Valide d'office les résolutions restées sans réponse du demandeur.

    La validation d'office emprunte EXACTEMENT le même chemin que la validation
    humaine (`record_pv_validation`) : elle déclenche donc la soumission
    automatique du PV au chef de division, comme si le demandeur avait confirmé.

    Aucune note de satisfaction n'est créée — le système ne peut pas inventer un
    ressenti. L'événement du journal porte `auto_validated`, ce qui distingue
    sans ambiguïté une validation subie d'une validation donnée, notamment pour
    les statistiques CSAT.
    """
    try:
        from sqlalchemy import select
        from api.configs.Database import AsyncSessionLocal
        from api.models.ModelRequest import Request as RequestModel
        from api.models.ModelRequestStatus import RequestStatus
        from api.services.ServiceRequest import RequestService

        cutoff = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=AUTO_VALIDATION_DAYS)

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
            validated = 0
            for req_id in ids:
                try:
                    # Idempotent : record_pv_validation ressort immédiatement si
                    # `pv_validated_at` existe déjà (demandeur ayant validé, ou
                    # passage précédent de ce job).
                    done = await svc.record_pv_validation(
                        str(req_id), confirmed=True, actor_id=None,
                        actor_name=None, automatic=True,
                    )
                    if done:
                        validated += 1
                except Exception as exc:
                    logger.warning(
                        "[Scheduler] auto_validation ticket %s échouée : %s", req_id, exc
                    )

            await session.commit()
            if validated:
                logger.info(
                    "[Scheduler] auto_validation : %d résolution(s) validée(s) d'office "
                    "après %d jours sans réponse du demandeur.",
                    validated, AUTO_VALIDATION_DAYS,
                )
    except Exception as exc:
        logger.error("[Scheduler] auto_validation échouée : %s", exc)


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
    # Job "auto_escalation" supprimé le 2026-09-26 avec le statut "escalated" :
    # il était déjà désactivé (aucun changement de statut/responsable sans action
    # humaine) et son service `ServiceEscalade` n'existe plus.
    _scheduler.add_job(
        _job_auto_validation,
        trigger=IntervalTrigger(hours=6),
        id="auto_validation",
        replace_existing=True,
        misfire_grace_time=300,
    )
    _scheduler.add_job(
        _job_auto_close,
        trigger=IntervalTrigger(hours=6),
        id="auto_close",
        replace_existing=True,
        misfire_grace_time=300,
    )
    _scheduler.start()
    logger.info(
        "[Scheduler] Démarré — auto_validation (%d j) et auto_close (%d j), toutes les 6h.",
        AUTO_VALIDATION_DAYS, AUTO_CLOSE_DAYS,
    )


def stop_scheduler() -> None:
    """Arrête proprement le scheduler."""
    if _scheduler.running:
        _scheduler.shutdown(wait=False)
        logger.info("[Scheduler] Arrêté.")
