"""
Service d'escalade automatique SLA — EDG Support.

Détecte les tickets dont le SLA est dépassé et les passe au statut 'escalated'.
Pour chaque ticket : réassigne au chef de service, crée un WorkflowDetail, notifie le chef.
Utilisé par le scheduler APScheduler (job périodique toutes les 10 minutes).
"""
from __future__ import annotations

import logging

from sqlalchemy import select, text, update
from sqlalchemy.ext.asyncio import AsyncSession

from api.models.ModelAccount import Account
from api.models.ModelOrganigram import Organigram
from api.models.ModelRequest import Request as RequestModel
from api.models.ModelRequestStatus import RequestStatus
from api.models.ModelWorkflow import Workflow
from api.models.ModelWorkflowDetail import WorkflowDetail

logger = logging.getLogger(__name__)

_TERMINAL = ("resolved", "closed", "cancelled", "rejected", "escalated")


async def find_hierarchical_chief(
    session: AsyncSession,
    unity_id: int | None,
    exclude_account_id: int | None = None,
    *,
    exclude_requester_id: int | None = None,
) -> int | None:
    """Chef hierarchique le plus proche pour une unite donnee.

    Cherche d'abord un chef (chief-service/chief-departement) dans la meme unite
    (en excluant exclude_account_id, utile quand la personne qui traite le ticket
    est elle-meme un chef — on doit alors remonter au niveau superieur), sinon
    remonte l'organigramme jusqu'a trouver un chef ou un directeur dans l'unite
    parente.

    BR-REQUESTER-NO-SELF-TREATMENT-001 — `exclude_requester_id` (demandeur du
    ticket escalade) est exclu au meme titre que exclude_account_id, a chaque
    niveau : le demandeur ne doit jamais devenir intervenant de son propre
    ticket via une escalade, meme si l'organigramme le designerait normalement
    comme chef hierarchique.
    """
    if not unity_id:
        return None

    filters = [
        Account.unity_id == unity_id,
        Account.role.in_(("chief-service", "chief-departement")),
        Account.account_status == "active",
        Account.deleted_at.is_(None),
    ]
    if exclude_account_id is not None:
        filters.append(Account.id != exclude_account_id)
    if exclude_requester_id is not None:
        filters.append(Account.id != exclude_requester_id)
    row = await session.execute(select(Account.id).where(*filters).limit(1))
    chief_id = row.scalar_one_or_none()
    if chief_id:
        return chief_id

    # Remonte a l'unite parente via l'organigramme
    parent_org_row = await session.execute(
        select(Organigram.parent_id)
        .where(Organigram.unity_id == unity_id, Organigram.deleted_at.is_(None))
        .limit(1)
    )
    parent_org_id = parent_org_row.scalar_one_or_none()
    if not parent_org_id:
        return None

    parent_unity_row = await session.execute(
        select(Organigram.unity_id)
        .where(Organigram.id == parent_org_id, Organigram.deleted_at.is_(None))
    )
    parent_unity_id = parent_unity_row.scalar_one_or_none()
    if not parent_unity_id:
        return None

    filters = [
        Account.unity_id == parent_unity_id,
        Account.role.in_(("chief-service", "chief-departement", "director")),
        Account.account_status == "active",
        Account.deleted_at.is_(None),
    ]
    if exclude_account_id is not None:
        filters.append(Account.id != exclude_account_id)
    if exclude_requester_id is not None:
        filters.append(Account.id != exclude_requester_id)
    row = await session.execute(select(Account.id).where(*filters).limit(1))
    return row.scalar_one_or_none()


async def find_director_for_department(
    session: AsyncSession, department_unity_id: int | None,
) -> int | None:
    """Directeur de la direction rattachee a un departement — Lot 3.3, "Escalade
    exceptionnelle". Contrairement a find_hierarchical_chief (chef le plus proche,
    quel que soit son role), cette fonction cible strictement un compte role="director",
    en remontant l'organigramme depuis le departement jusqu'a la direction. Utilisee
    pour l'action "Escalader au Directeur" qui court-circuite volontairement la
    hierarchie normale (chief-departement -> chief le plus proche).
    """
    if not department_unity_id:
        return None

    current_unity_id = department_unity_id
    for _ in range(5):  # borne de securite, la hierarchie reelle a 3 niveaux
        row = await session.execute(
            select(Account.id)
            .where(
                Account.unity_id == current_unity_id,
                Account.role == "director",
                Account.account_status == "active",
                Account.deleted_at.is_(None),
            )
            .limit(1)
        )
        director_id = row.scalar_one_or_none()
        if director_id:
            return director_id

        parent_org_row = await session.execute(
            select(Organigram.parent_id)
            .where(Organigram.unity_id == current_unity_id, Organigram.deleted_at.is_(None))
            .limit(1)
        )
        parent_org_id = parent_org_row.scalar_one_or_none()
        if not parent_org_id:
            return None

        parent_unity_row = await session.execute(
            select(Organigram.unity_id)
            .where(Organigram.id == parent_org_id, Organigram.deleted_at.is_(None))
        )
        parent_unity_id = parent_unity_row.scalar_one_or_none()
        if not parent_unity_id or parent_unity_id == current_unity_id:
            return None
        current_unity_id = parent_unity_id

    return None


class EscaladeService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def run_auto_escalation(self) -> int:
        """
        Parcourt tous les tickets actifs dont le SLA est dépassé et les escalade.
        Retourne le nombre de tickets escaladés.
        """
        escalated_status_id = await self._status_id("escalated")
        if escalated_status_id is None:
            logger.warning("EscaladeService : statut 'escalated' introuvable en base.")
            return 0

        terminal_ids = await self._terminal_status_ids()

        result = await self.session.execute(
            select(
                RequestModel.id,
                RequestModel.ref,
                RequestModel.assignee_id,
                RequestModel.unity_id,
                RequestModel.requester_id,
            )
            .where(
                RequestModel.deleted_at.is_(None),
                RequestModel.sla_hours > 0,
                RequestModel.sla_breached.is_(True),
                RequestModel.request_status_id.not_in(terminal_ids),
                RequestModel.request_status_id != escalated_status_id,
            )
        )
        tickets = result.all()

        if not tickets:
            return 0

        ticket_ids = [t[0] for t in tickets]

        # Statut en masse → escalated
        await self.session.execute(
            update(RequestModel)
            .where(RequestModel.id.in_(ticket_ids))
            .values(request_status_id=escalated_status_id, sla_breached=True)
        )

        # Traitement individuel : WorkflowDetail + réassignation + notification
        for t_id, t_ref, t_assignee, t_unity_id, t_requester in tickets:
            chief_id = await self._find_chief(t_unity_id, exclude_requester_id=t_requester)
            workflow_id = await self._get_or_create_workflow(t_id)

            label = "Escalade automatique — délai SLA dépassé"
            comment = f"Le ticket {t_ref} a dépassé son délai SLA. Statut passé à « Escaladé »."
            if chief_id:
                label += " · Réassigné au chef de service"
                comment += f" Réassigné à l'agent #{chief_id}."

            self.session.add(
                WorkflowDetail(
                    workflow_id=workflow_id,
                    event_type="escalation_auto",
                    label=label,
                    actor_name="Système (escalade automatique)",
                    comment=comment,
                    activated=True,
                    accepted=None,
                )
            )

            if chief_id and chief_id != t_assignee:
                await self.session.execute(
                    update(RequestModel)
                    .where(RequestModel.id == t_id)
                    .values(assignee_id=chief_id)
                )
                await self._notify(
                    recipient_id=str(chief_id),
                    title="Escalade automatique SLA",
                    body=(
                        f"Le ticket {t_ref} vous a été réassigné suite au dépassement "
                        f"du délai SLA. Veuillez le traiter en priorité."
                    ),
                    notif_type="warning",
                    request_id=str(t_id),
                )

        await self._log_escalations(tickets)

        logger.info("EscaladeService : %d ticket(s) escaladé(s).", len(ticket_ids))
        return len(ticket_ids)

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _status_id(self, code: str) -> int | None:
        row = await self.session.execute(
            select(RequestStatus.id).where(
                RequestStatus.code == code,
                RequestStatus.deleted_at.is_(None),
            )
        )
        return row.scalar_one_or_none()

    async def _terminal_status_ids(self) -> list[int]:
        rows = await self.session.execute(
            select(RequestStatus.id).where(
                RequestStatus.code.in_(_TERMINAL),
                RequestStatus.deleted_at.is_(None),
            )
        )
        return [r[0] for r in rows.all()]

    async def _get_or_create_workflow(self, request_id: int) -> int | None:
        """Retourne l'ID du workflow actif de la demande, ou en crée un nouveau."""
        row = await self.session.execute(
            select(Workflow.id)
            .where(
                Workflow.request_id == request_id,
                Workflow.deleted_at.is_(None),
            )
            .order_by(Workflow.id.desc())
            .limit(1)
        )
        wf_id = row.scalar_one_or_none()
        if wf_id is not None:
            return wf_id

        wf = Workflow(request_id=request_id, workflow_status="active")
        self.session.add(wf)
        await self.session.flush()
        return wf.id

    async def _find_chief(
        self, unity_id: int | None, *, exclude_requester_id: int | None = None,
    ) -> int | None:
        """Chef dans la même unité ; sinon chef/directeur dans l'unité parente."""
        return await find_hierarchical_chief(
            self.session, unity_id, exclude_requester_id=exclude_requester_id,
        )

    async def _notify(
        self,
        *,
        recipient_id: str,
        title: str,
        body: str,
        notif_type: str = "warning",
        request_id: str | None = None,
        send_email: bool = True,
    ) -> None:
        try:
            from api.services.NotificationEmitter import emit
            await emit(
                self.session,
                recipient_id=recipient_id,
                title=title,
                body=body,
                type=notif_type,
                channel="in_app",
                request_id=request_id,
                action_label="Voir le ticket",
                action_url=f"/app/requests/{request_id}" if request_id else None,
                send_email=send_email,
            )
        except Exception as exc:
            logger.warning("EscaladeService : notification échouée : %s", exc)

    async def _log_escalations(self, tickets: list) -> None:
        """Enregistre une entrée ActivityLog pour chaque ticket escaladé."""
        try:
            from api.models.ModelActivityLog import ActivityLog
            entries = [
                ActivityLog(
                    actor="Système",
                    actor_role="admin",
                    action=f"Escalade automatique SLA — ticket {t[1]}",
                    category="escalade",
                    target=str(t[0]),
                    log_status="warning",
                    actor_id=None,
                )
                for t in tickets
            ]
            self.session.add_all(entries)
        except Exception as exc:
            logger.warning("EscaladeService : journalisation échouée : %s", exc)

    async def warn_sla_approaching(self, threshold_ratio: float = 0.8) -> int:
        """
        BR-NOTIFICATION-WORKFLOW-001 §14 — alerte préventive App-only à
        l'intervenant actuel quand un ticket approche (mais n'a pas encore
        atteint) son échéance SLA.

        Anti-répétition : réutilise `request.infos` (même pattern déjà en place
        pour `reopen_requested`/pointeurs d'intervention — aucune nouvelle
        colonne) pour marquer `sla_warning_sent_at` dès le premier avertissement
        du cycle SLA courant, afin qu'un même cycle ne redéclenche jamais cette
        alerte au passage suivant du scheduler (10 min). Le flag est remis à
        zéro à chaque réouverture (`ServiceRequest.reopen`, nouveau cycle SLA).
        """
        # Filtrage seuil/anti-répétition en SQL brut : ne renvoie que des ids (pas
        # `infos`, dont le décodage JSON via text() brut n'est pas garanti — voir
        # relecture/merge ORM ci-dessous, seul chemin sûr pour écrire `infos` sans
        # écraser son contenu existant, ex. pointeurs BR-TRACE-001).
        id_rows = await self.session.execute(
            text("""
                SELECT r.id
                FROM request r
                JOIN request_status rs ON rs.id = r.request_status_id
                LEFT JOIN (
                    SELECT w.request_id, MAX(wd.created_at) AS last_reopened_at
                    FROM workflow_detail wd
                    JOIN workflow w ON w.id = wd.workflow_id
                    WHERE wd.event_type = 'reopened' AND wd.deleted_at IS NULL
                    GROUP BY w.request_id
                ) rw ON rw.request_id = r.id
                WHERE r.deleted_at IS NULL
                  AND r.sla_hours > 0
                  AND r.sla_breached = 0
                  AND r.assignee_id IS NOT NULL
                  AND rs.code NOT IN ('resolved', 'closed', 'cancelled', 'rejected', 'escalated')
                  AND TIMESTAMPDIFF(
                        MINUTE, COALESCE(rw.last_reopened_at, r.created_at), NOW()
                      ) >= (r.sla_hours * 60 * :threshold)
                  AND JSON_UNQUOTE(JSON_EXTRACT(r.infos, '$.sla_warning_sent_at')) IS NULL
            """),
            {"threshold": threshold_ratio},
        )
        candidate_ids = [row[0] for row in id_rows.all()]
        if not candidate_ids:
            return 0

        warned = 0
        for t_id in candidate_ids:
            obj_row = await self.session.execute(
                select(RequestModel.ref, RequestModel.assignee_id, RequestModel.infos)
                .where(RequestModel.id == t_id)
            )
            row = obj_row.first()
            if row is None or not row.assignee_id:
                continue
            current_infos = dict(row.infos) if isinstance(row.infos, dict) else {}
            current_infos["sla_warning_sent_at"] = "now"
            await self.session.execute(
                update(RequestModel).where(RequestModel.id == t_id).values(infos=current_infos)
            )
            await self._notify(
                recipient_id=str(row.assignee_id),
                title="SLA bientôt dépassé",
                body=f"Attention : le ticket {row.ref} a consommé {int(threshold_ratio * 100)} % de son délai SLA.",
                notif_type="warning",
                request_id=str(t_id),
                # Lot finition §2 — App uniquement par défaut pour l'alerte préventive.
                send_email=False,
            )
            warned += 1
        if warned:
            logger.info("EscaladeService : %d ticket(s) avertis (SLA proche de l'échéance).", warned)
        return warned

    async def mark_sla_breached(self) -> int:
        """
        Met à jour sla_breached et sla_elapsed (heures écoulées) sur tous les tickets actifs.
        Appelé avant run_auto_escalation pour synchroniser les flags (CDC §6.1).

        BR-SLA-REOPEN-001 : l'ancre du calcul n'est plus systématiquement `created_at`
        — un ticket déjà réouvert au moins une fois mesure son cycle SLA courant depuis
        sa dernière réouverture (`workflow_detail.event_type='reopened'` le plus récent),
        jamais depuis la création d'origine. Le premier cycle SLA n'est jamais recalculé :
        cette requête ne touche que les compteurs "live" (`sla_elapsed`/`sla_breached`),
        le cycle précédent restant gelé dans l'événement `treatment_completed`
        correspondant (`ServiceRequest._sla_cycle_snapshot`).
        """
        # Mise à jour de sla_elapsed sur tous les tickets actifs (pas uniquement breached)
        await self.session.execute(
            text("""
                UPDATE request r
                JOIN request_status rs ON rs.id = r.request_status_id
                LEFT JOIN (
                    SELECT w.request_id, MAX(wd.created_at) AS last_reopened_at
                    FROM workflow_detail wd
                    JOIN workflow w ON w.id = wd.workflow_id
                    WHERE wd.event_type = 'reopened' AND wd.deleted_at IS NULL
                    GROUP BY w.request_id
                ) rw ON rw.request_id = r.id
                SET r.sla_elapsed = TIMESTAMPDIFF(HOUR, COALESCE(rw.last_reopened_at, r.created_at), NOW())
                WHERE r.deleted_at IS NULL
                  AND r.sla_hours > 0
                  AND rs.code NOT IN ('resolved', 'closed', 'cancelled', 'rejected')
            """)
        )

        result = await self.session.execute(
            text("""
                UPDATE request r
                JOIN request_status rs ON rs.id = r.request_status_id
                LEFT JOIN (
                    SELECT w.request_id, MAX(wd.created_at) AS last_reopened_at
                    FROM workflow_detail wd
                    JOIN workflow w ON w.id = wd.workflow_id
                    WHERE wd.event_type = 'reopened' AND wd.deleted_at IS NULL
                    GROUP BY w.request_id
                ) rw ON rw.request_id = r.id
                SET r.sla_breached = 1
                WHERE r.deleted_at IS NULL
                  AND r.sla_hours > 0
                  AND r.sla_breached = 0
                  AND TIMESTAMPDIFF(HOUR, COALESCE(rw.last_reopened_at, r.created_at), NOW()) >= r.sla_hours
                  AND rs.code NOT IN ('resolved', 'closed', 'cancelled', 'rejected', 'escalated')
            """)
        )
        count = result.rowcount
        if count:
            logger.info("EscaladeService : %d ticket(s) marqués sla_breached=True.", count)
        return count
