from __future__ import annotations

import re
from datetime import datetime, timezone
from typing import Any, Optional

from sqlalchemy import and_, func, or_, select
from sqlalchemy import true as sql_true
from sqlalchemy import update as sa_update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload

from api.core.exceptions import ConflictException
from api.core.error_codes import ErrorCode
from api.core.event_bus import AppEvent, emit as emit_event
from api.core.rbac import normalize_role
# Délai laissé au demandeur avant validation d'office (BR-AUTO-VALIDATION-001).
# Défini dans le planificateur, qui porte le job : une seule valeur pour le
# message envoyé au demandeur et pour l'échéance réellement appliquée.
from api.core.scheduler import AUTO_VALIDATION_DAYS
from api.core.ticket_actions import (
    BYPASS_TRANSITION_ROLES as _BYPASS_ROLES,
    TERMINAL_STATUSES,
    TREATING_ROLES,
    assert_assignment_allowed,
    assert_action_allowed,
    assert_is_current_handler,
    assert_qualify_target_allowed,
    assert_requester_is_not_handler,
    assert_role_specific_action_constraints,
    assert_service_reassignment_allowed,
    assert_ticket_scope,
    assert_transition_allowed,
    normalize_status,
)
from api.models.ModelAccount import Account
from api.models.ModelPriorityDefinition import PriorityDefinition
from api.models.ModelRequest import Request as RequestModel
from api.models.ModelRequestCategory import RequestCategory
from api.models.ModelRequestStatus import RequestStatus
from api.models.ModelUnity import Unity
from api.models.ModelWorkflow import Workflow
from api.repositories import RequestRepository, WorkflowDetailRepository
from api.schemas.SchemaRequest import RequestResponse, RequestListItemResponse, DistributionListItemResponse, PvTrackingItemResponse
from api.services.base_service import BaseService
from api.services.NotificationEmitter import emit as emit_notif, emit_bulk
from api.services.ServiceCrypto import decrypt_field

# Mapping statut → event_type spécifique (CDC §7 + §8)
# "pending", "qualified" et "escalated" supprimés du projet (2026-09-28) :
# plus aucune transition ne les atteint, ils ne sont donc plus cartographiés.
_STATUS_EVENT_MAP: dict[str, str] = {
    "qualifying":   "qualifying",
    "assigned":     "assigned",
    "in_progress":  "in_progress",
    "rejected":     "rejected",
}
# Procédure EDG/PS-GSI/Pro-02 tâche 2.1 — issue du point de contrôle
# « vérification de l'état réel de la requête ».
_FIELD_CHECK_CONFORMITY = frozenset({"conforme", "ecart"})

_STATUS_LABEL_MAP: dict[str, str] = {
    "qualifying":   "Ticket en cours de qualification",
    "assigned":     "Ticket assigné à un agent",
    "in_progress":  "Prise en charge — traitement en cours",
    "rejected":     "Ticket rejeté",
}


class RequestService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.repo = RequestRepository(session)
        self.detail_repo = WorkflowDetailRepository(session)

    async def _guard_ticket_action(
        self,
        id: str,
        action: str,
        *,
        target_status: Optional[str] = None,
        actor=None,
        actor_role: Optional[str] = None,
    ):
        obj = await self.get_by_id(id)
        effective_role = str(getattr(actor, "role", actor_role or "") or "")
        if effective_role:
            assert_action_allowed(effective_role, action)
        if actor is not None:
            # Les deux roles qui beneficiaient d'un perimetre elargi (director,
            # chief-departement) ont ete retires le 2026-09-25.
            assert_ticket_scope(actor, obj, action=action, allowed_dir_unity_ids=None)
            assert_role_specific_action_constraints(actor, obj, action)
        if target_status is not None:
            assert_transition_allowed(
                obj.request_status,
                target_status,
                actor_role=effective_role or None,
            )
        return obj

    # ── Helper : traduit codes string → IDs FK ────────────────────────────────

    async def _translate_codes(self, data: dict) -> dict:
        out = dict(data)
        if "request_status" in out:
            code = out.pop("request_status")
            if code is not None:
                code = normalize_status(code)
                r = await self.session.execute(
                    select(RequestStatus.id)
                    .where(RequestStatus.code == code)
                    .where(RequestStatus.deleted_at.is_(None))
                )
                status_id = r.scalar_one_or_none()
                if status_id is None:
                    # Fallback vers "new" si le code demandé n'existe pas
                    r2 = await self.session.execute(
                        select(RequestStatus.id)
                        .where(RequestStatus.code == "new")
                        .where(RequestStatus.deleted_at.is_(None))
                    )
                    status_id = r2.scalar_one_or_none()
                if status_id is not None:
                    out["request_status_id"] = status_id
        if "category" in out:
            code = out.pop("category")
            if code is not None:
                # Cherche par code exact (insensible à la casse), puis fallback "autre"
                r = await self.session.execute(
                    select(RequestCategory.id)
                    .where(RequestCategory.code == code.lower())
                    .where(RequestCategory.deleted_at.is_(None))
                )
                cat_id = r.scalar_one_or_none()
                if cat_id is None:
                    r2 = await self.session.execute(
                        select(RequestCategory.id)
                        .where(RequestCategory.code == "autre")
                        .where(RequestCategory.deleted_at.is_(None))
                    )
                    cat_id = r2.scalar_one_or_none()
                if cat_id is not None:
                    out["request_category_id"] = cat_id
        if "priority" in out:
            slug = out.pop("priority")
            if slug is not None:
                r = await self.session.execute(
                    select(PriorityDefinition.id)
                    .where(PriorityDefinition.slug == slug)
                    .where(PriorityDefinition.deleted_at.is_(None))
                )
                prio_id = r.scalar_one_or_none()
                if prio_id is None:
                    # Fallback vers "medium" si le slug demandé n'existe pas
                    r2 = await self.session.execute(
                        select(PriorityDefinition.id)
                        .where(PriorityDefinition.slug == "medium")
                        .where(PriorityDefinition.deleted_at.is_(None))
                    )
                    prio_id = r2.scalar_one_or_none()
                if prio_id is not None:
                    out["priority_definition_id"] = prio_id
        if "source" in out:
            out["request_source"] = out.pop("source")
        if "direction_id" in out:
            # direction_id n'est pas une vraie colonne (propriété calculée) — une direction
            # est elle-même une Unity racine, donc on la retient comme unity_id UNIQUEMENT
            # si aucun service plus précis n'a déjà été fourni. Le ticket reste orienté via
            # le routage automatique (routing_rule) ou la file de triage (in_triage), cette
            # traduction ne fait que conserver la suggestion de direction au lieu de la perdre.
            dir_id = out.pop("direction_id")
            if dir_id is not None and not out.get("unity_id"):
                out["unity_id"] = dir_id
        return out

    # ── Helper : workflow ─────────────────────────────────────────────────────

    async def _get_or_create_workflow(self, request_id: int) -> int:
        """Retourne l'ID du Workflow actif de la demande ; en crée un si absent."""
        row = await self.session.execute(
            select(Workflow.id)
            .where(Workflow.request_id == request_id)
            .where(Workflow.deleted_at.is_(None))
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

    async def _atomic_conditional_update(
        self,
        current: RequestModel,
        *,
        values: dict[str, Any],
        require_current_assignee: bool,
        commit: bool = True,
    ) -> RequestModel:
        """
        BR-TRANSMIT-001 — écriture atomique conditionnelle (compare-and-set côté SQL)
        pour empêcher deux transmissions/résolutions simultanées d'écraser silencieusement
        l'affectation l'une de l'autre sur la base d'un état obsolète. `require_current_assignee`
        vaut False pour l'admin (bypass exceptionnel, cf. assert_is_current_handler).

        Écrit via un UPDATE Core brut (pas `self.repo.update`) pour que la clause WHERE
        porte la condition de concurrence. Rafraîchit ensuite `current` (déjà chargé dans
        l'identity map de la session) plutôt que de refaire un SELECT : un SELECT après un
        UPDATE Core renverrait sinon l'objet ORM encore en cache, avec des valeurs perimées.

        `commit=False` — perf (harmonisation transactionnelle) : flush au lieu de
        commit, l'appelant orchestre un commit unique en fin de requête (get_db()).
        C'est toujours le tout premier écrit de resolve()/transmit_treatment(), donc
        le rollback sur conflit de concurrence (rowcount == 0) reste sans risque —
        rien d'autre n'est encore flush à ce stade.
        """
        stmt = sa_update(RequestModel).where(RequestModel.id == current.id)
        if require_current_assignee:
            stmt = stmt.where(RequestModel.assignee_id == current.assignee_id)
        stmt = stmt.values(**values)
        result = await self.session.execute(stmt)
        if result.rowcount == 0:
            await self.session.rollback()
            raise ConflictException(
                "Ce ticket a été modifié par un autre utilisateur. Veuillez actualiser la page.",
                error_code=ErrorCode.TICKET_STATE_CONFLICT,
            )
        if commit:
            await self.session.commit()
        else:
            await self.session.flush()
        await self.session.refresh(current)
        return current

    async def _next_treatment_cycle(
        self, request_id: int, *, fallback_started_at: datetime
    ) -> tuple[int, datetime, datetime, Optional[int]]:
        """
        BR-TRANSMIT-001 — calcule (cycle_number, started_at, ended_at, duration_seconds)
        pour l'événement de transmission/terminaison en cours de création. Un nouveau
        cycle commence à chaque `assigned` (prise en charge initiale) ou
        `treatment_transmitted` (transmission) ; cycle_number = nombre de cycles déjà
        clôturés (transmis ou terminés) + 1 — reconstruit uniquement depuis
        workflow_detail (append-only), sans nouvelle table.
        """
        events = await self.detail_repo.list_by_request(str(request_id))
        cycle_number = sum(
            1 for e in events if e.event_type in ("treatment_transmitted", "treatment_completed")
        ) + 1
        started_at = fallback_started_at
        for event in reversed(events):
            if event.event_type in ("assigned", "treatment_transmitted"):
                started_at = event.created_at
                break
        ended_at = datetime.now(timezone.utc).replace(tzinfo=None)
        duration_seconds = int((ended_at - started_at).total_seconds()) if started_at else None
        return cycle_number, started_at, ended_at, duration_seconds

    async def _sla_cycle_snapshot(
        self,
        request_id: int,
        *,
        sla_hours: int,
        fallback_created_at: datetime,
        ended_at: datetime,
        current_infos: Optional[dict] = None,
    ) -> dict[str, Any]:
        """
        BR-SLA-REOPEN-001 — instantané SLA du cycle qui se clôture (résolution en
        cours). Un nouveau cycle SLA démarre à chaque réouverture approuvée
        (`reopened`) ; reconstruit uniquement depuis `workflow_detail`
        (append-only, sans nouvelle table) : `sla_cycle_number` = nombre de
        résolutions déjà enregistrées (`treatment_completed`) + 1 ;
        `sla_cycle_started_at` = date de la dernière réouverture, ou date de
        création si le ticket n'a jamais été réouvert. Gelé définitivement dans
        l'événement de résolution (`infos`) — jamais recalculé après coup, le
        premier cycle SLA reste donc intact quel que soit le nombre de
        réouvertures ultérieures.
        BR-TRACE-001 : si `request.infos.sla_cycle_number` (compteur explicite,
        incrémenté par `reopen()`) est disponible, il est utilisé tel quel plutôt
        que recompté — cohérent avec la consigne de ne jamais dériver le cycle.
        Le comptage par événements reste un filet de sécurité pour les tickets
        antérieurs à ce compteur.
        Temps de réponse (`sla_response_hours`) : première prise en charge
        (`assigned`/`in_progress`/`treatment_transmitted`) après le début du
        cycle — approximation basée sur les événements réellement tracés
        (aucune donnée dédiée "première réponse" n'existe dans le modèle), à
        `None` si aucun événement de prise en charge n'est retrouvé.
        """
        events = await self.detail_repo.list_by_request(str(request_id))
        explicit_cycle = (current_infos or {}).get("sla_cycle_number") if isinstance(current_infos, dict) else None
        sla_cycle_number = (
            int(explicit_cycle) if explicit_cycle
            else sum(1 for e in events if e.event_type == "treatment_completed") + 1
        )
        started_at = fallback_created_at
        reopen_reason: Optional[str] = None
        for event in reversed(events):
            if event.event_type == "reopened":
                started_at = event.created_at
                reopen_reason = event.comment or (event.infos or {}).get("reopen_reason")
                break
        response_at = next(
            (
                e.created_at for e in events
                if e.created_at and started_at and e.created_at >= started_at
                and e.event_type in ("assigned", "in_progress", "treatment_transmitted")
            ),
            None,
        )
        elapsed_hours = round((ended_at - started_at).total_seconds() / 3600, 2) if started_at else None
        response_hours = round((response_at - started_at).total_seconds() / 3600, 2) if response_at and started_at else None
        breached = bool(sla_hours > 0 and elapsed_hours is not None and elapsed_hours > sla_hours)
        return {
            "sla_cycle_number": sla_cycle_number,
            "sla_cycle_started_at": started_at.isoformat() if started_at else None,
            "sla_hours_target": sla_hours if sla_hours > 0 else None,
            "sla_elapsed_hours": elapsed_hours,
            "sla_response_hours": response_hours,
            "sla_breached": breached,
            "sla_reopen_reason": reopen_reason,
        }

    # ── BR-TRACE-001 — traçabilité complète des interventions ──────────────────
    #
    # Une "intervention" est le conteneur logique du travail complet d'un seul
    # intervenant (commentaires, pièces jointes, travail effectué), depuis le
    # moment où il devient l'intervenant courant jusqu'à sa transmission ou sa
    # résolution. Contrairement au cycle SLA (BR-SLA-REOPEN-001, recalculé pour
    # les rapports), le cycle et l'ordre d'une intervention sont ici demandés
    # explicitement enregistrés — jamais recalculés après coup. Le pointeur
    # "intervention courante" (cycle_number/intervention_order/intervention_id)
    # vit dans `request.infos` (colonne JSON déjà existante, aucune nouvelle
    # colonne/table) au même titre que le flag `reopen_requested` déjà présent :
    # c'est un état "live", mis à jour à chaque ouverture/fermeture, jamais une
    # donnée historique — l'historique lui-même reste entièrement porté par les
    # événements `workflow_detail` (append-only), chacun figeant sa propre copie
    # de ce pointeur au moment de sa création.

    async def _actor_identity_snapshot(self, account_id: Optional[int | str]) -> dict[str, Any]:
        """Identité figée de l'intervenant TITULAIRE de l'intervention (peut être
        différent de l'acteur qui écrit l'événement — ex. un admin/chef qui
        assigne un agent : l'intervention appartient à l'agent, pas à celui qui
        l'assigne). Inclut `intervention_actor_id`/`intervention_actor_name` en
        plus du matricule + direction/département/service, résolus via
        l'organigramme, au moment de l'action — jamais recalculés ensuite, même
        si le compte change ensuite d'unité."""
        if not account_id:
            return {}
        from api.repositories.RepositoryAccount import AccountRepository

        account = await AccountRepository(self.session).get_by_id(int(account_id))
        if account is None:
            return {}
        org = await self._org_labels_for_unity(getattr(account, "unity_id", None))
        # PV d'intervention EDG/PS-GSI/PV-01, bloc « Affectation » — le badge et
        # le statut (titulaire / prestataire / stagiaire) sont figés ICI, au
        # moment de l'intervention : un stagiaire devenu titulaire ne doit pas
        # réécrire ses anciens PV. Le PV imprime le badge ; à défaut (prestataire
        # ou stagiaire sans badge EDG), il imprime le nom complet, déjà figé
        # juste au-dessus dans `intervention_actor_name` — la case ne reste
        # jamais vide sur un document destiné à être signé.
        return self._clean_infos({
            "intervention_actor_id": str(account.id),
            "intervention_actor_name": self._account_display_name(account),
            "intervention_actor_role": normalize_role(getattr(account, "role", None)),
            "actor_status": getattr(account, "intervenant_status", None),
            "actor_matricule": getattr(account, "matricule", None),
            "actor_direction_label": org.get("direction_label"),
            "actor_department_label": org.get("department_label"),
            "actor_service_label": org.get("service_label"),
        })

    async def _org_labels_for_unity(self, unity_id: Optional[int | str]) -> dict[str, Any]:
        """Direction / département / service d'une unité, résolus via
        l'organigramme **à l'instant de l'appel**. Brique commune à tous les
        figeages d'identité organisationnelle (intervenant, demandeur, service
        traitant) : ils doivent tous lire l'organigramme de la même façon, sinon
        deux tickets contemporains pourraient afficher des libellés divergents
        pour la même unité."""
        if not unity_id:
            return {}
        try:
            normalized_id = int(unity_id)
        except (TypeError, ValueError):
            return {}
        chain = await self._org_chain_for_unity(normalized_id)
        if not chain:
            return {}
        service = chain[0]
        direction = chain[-1]
        departement = chain[1] if len(chain) >= 3 else None
        return self._clean_infos({
            "service_label": service.label if service else None,
            "department_label": departement.label if departement else None,
            "direction_label": direction.label if direction else None,
            "direction_id": direction.id if direction else None,
        })

    async def _requester_identity_snapshot(self, account_id: Optional[int | str]) -> dict[str, Any]:
        """Identité organisationnelle FIGÉE du demandeur, écrite dans
        `request.infos` à la création de la demande et jamais recalculée ensuite.

        Sans ce figeage, un demandeur qui change de service ou de fonction
        réécrit rétroactivement l'origine de TOUS ses anciens tickets : le
        dossier d'un incident traité en janvier afficherait le service qu'il
        occupe en décembre. Même principe et même forme que
        `_actor_identity_snapshot` côté intervenant (BR-TRACE-001)."""
        if not account_id:
            return {}
        from api.repositories.RepositoryAccount import AccountRepository

        account = await AccountRepository(self.session).get_by_id(int(account_id))
        if account is None:
            return {}
        org = await self._org_labels_for_unity(getattr(account, "unity_id", None))
        return self._clean_infos({
            "requester_unit_id": getattr(account, "unity_id", None),
            "requester_job": getattr(account, "job", None),
            "requester_matricule": getattr(account, "matricule", None),
            "requester_direction_id": org.get("direction_id"),
            "requester_direction_label": org.get("direction_label"),
            "requester_department_label": org.get("department_label"),
            "requester_service_label": org.get("service_label"),
        })

    async def _handler_org_snapshot(self, unity_id: Optional[int | str]) -> dict[str, Any]:
        """Organisation TRAITANTE figée au moment de la qualification.

        `request.unity_id` gèle déjà le service en tant qu'identifiant, mais la
        direction en est *dérivée* (`unity.parent_direction_id`) et les libellés
        sont lus en direct : réorganiser l'organigramme ou renommer un service
        réécrirait donc l'historique. On fige ici les libellés et la direction
        effectivement retenus le jour de la qualification."""
        org = await self._org_labels_for_unity(unity_id)
        if not org:
            return {}
        return self._clean_infos({
            "handler_unit_id": int(unity_id),
            "handler_direction_id": org.get("direction_id"),
            "handler_direction_label": org.get("direction_label"),
            "handler_department_label": org.get("department_label"),
            "handler_service_label": org.get("service_label"),
        })

    async def _open_intervention(
        self, current_infos: Optional[dict], assignee_id: Optional[int | str], request_id: int | str,
    ) -> tuple[dict[str, Any], dict[str, Any]]:
        """Ouvre une nouvelle intervention pour `assignee_id` : calcule et
        enregistre explicitement `intervention_id`/`intervention_order`
        (jamais recalculés), et pointe le nouveau conteneur courant dans
        `request.infos` pour que les événements suivants du même intervenant
        (commentaires, pièces jointes) s'y rattachent jusqu'à la prochaine
        transmission/résolution.
        Retourne (nouveaux `infos` de la demande, métadonnées à figer dans
        l'événement d'ouverture — `assigned`/`treatment_transmitted`).
        """
        infos = dict(current_infos) if isinstance(current_infos, dict) else {}
        sla_cycle_number = int(infos.get("sla_cycle_number") or 1)
        intervention_order = int(infos.get("intervention_order_in_cycle") or 0) + 1
        intervention_id = f"req{request_id}-c{sla_cycle_number}-i{intervention_order}"
        infos["sla_cycle_number"] = sla_cycle_number
        infos["intervention_order_in_cycle"] = intervention_order
        infos["current_intervention_id"] = intervention_id
        identity = await self._actor_identity_snapshot(assignee_id)
        # Procédure EDG/PS-GSI/Pro-02 — le constat terrain (tâche 2.1) précède la
        # résolution (tâche 2.2). Ces deux tâches sont, dans le document, sous la
        # responsabilité du SEUL technicien : un chef de service, un chef de
        # division, un chef de département ou un directeur qui termine un
        # traitement ne réalise pas une intervention de terrain et n'est donc pas
        # concerné.
        #
        # Le drapeau est posé ICI, à l'ouverture de l'intervention, plutôt que
        # déduit d'une date en dur : les interventions ouvertes avant la mise en
        # service de la règle ne le portent pas et restent résolvables — même
        # logique « absent = antérieur = exempté » que le figeage des identités
        # organisationnelles.
        # TSI (tâche 3.4) — nom et badge de l'intervenant courant recopiés sur le
        # ticket. La requête du tableau de suivi saute volontairement les
        # relations de workflow (perf), donc `interventions` n'y est pas
        # reconstruit : sans ce pointeur, le TSI ne pourrait nommer personne.
        infos["current_intervenant_name"] = identity.get("intervention_actor_name")
        infos["current_intervenant_badge"] = (
            identity.get("actor_matricule") or identity.get("intervention_actor_name")
        )
        if identity.get("intervention_actor_role") == "technicien":
            infos["field_check_required"] = True
        else:
            # Une transmission d'un technicien vers un autre rôle ne doit pas
            # laisser traîner le drapeau du précédent.
            infos.pop("field_check_required", None)
        meta = self._clean_infos({
            "intervention_id": intervention_id,
            "intervention_order": intervention_order,
            # Nommé "intervention_cycle_number" (et non "cycle_number") pour ne
            # jamais entrer en collision avec le `cycle_number` déjà utilisé par
            # BR-TRANSMIT-001 (compteur global de transmissions/résolutions,
            # jamais réinitialisé) — sur le même événement, les deux coexistent
            # avec des sens différents. Valeur numériquement alignée sur
            # `sla_cycle_number` (BR-SLA-REOPEN-001) mais suivie indépendamment
            # via ce pointeur explicite, jamais recalculée.
            "intervention_cycle_number": sla_cycle_number,
            **identity,
        })
        return infos, meta

    @staticmethod
    def _current_intervention_meta(current_infos: Optional[dict]) -> dict[str, Any]:
        """Métadonnées de l'intervention EN COURS (à figer dans l'événement qui
        la ferme : `treatment_transmitted`/`treatment_completed`), lues depuis le
        pointeur `request.infos` sans jamais être recalculées."""
        infos = current_infos if isinstance(current_infos, dict) else {}
        return RequestService._clean_infos({
            "intervention_id": infos.get("current_intervention_id"),
            "intervention_order": infos.get("intervention_order_in_cycle"),
            "intervention_cycle_number": infos.get("sla_cycle_number") or 1,
        })

    @staticmethod
    def _intervention_meta_for_actor(
        current_infos: Optional[dict], assignee_id: Optional[int | str], actor_id: Optional[int | str],
    ) -> dict[str, Any]:
        """Rattache un événement secondaire (commentaire, pièce jointe) à
        l'intervention ouverte, uniquement si son auteur est l'intervenant
        courant du ticket (sinon l'événement reste visible dans l'historique
        mais hors de tout conteneur d'intervention — ex. message du demandeur)."""
        if not assignee_id or not actor_id or str(actor_id) != str(assignee_id):
            return {}
        return RequestService._current_intervention_meta(current_infos)

    @staticmethod
    def _account_display_name(account_or_name=None, firstname: Optional[str] = None) -> Optional[str]:
        """Nom lisible stable pour la timeline, sans exposer de logique UI."""
        if account_or_name is None and not firstname:
            return None
        if isinstance(account_or_name, str):
            name = account_or_name
        else:
            name = getattr(account_or_name, "name", None)
            firstname = getattr(account_or_name, "firstname", firstname)
        parts = [p for p in (firstname, name) if p]
        return " ".join(parts) if parts else None

    @staticmethod
    def _clean_infos(infos: dict[str, Any]) -> dict[str, Any]:
        return {k: v for k, v in infos.items() if v is not None}

    @staticmethod
    def _same_account(left: Any, right: Any) -> bool:
        return left is not None and right is not None and str(left) == str(right)

    async def _ref_unity_by_id(self, unity_id: Any) -> Unity | None:
        if unity_id is None:
            return None
        try:
            normalized_id = int(unity_id)
        except (TypeError, ValueError):
            return None
        row = await self.session.execute(
            select(Unity)
            .where(Unity.id == normalized_id)
            .where(Unity.deleted_at.is_(None))
            .limit(1)
        )
        return row.scalar_one_or_none()

    async def _org_chain_for_unity(self, unity_id: int) -> list[Unity]:
        """Chaîne organigramme feuille→racine (ex : Service, Département, Direction)."""
        from api.models.ModelOrganigram import Organigram

        row = await self.session.execute(
            select(Organigram)
            .where(Organigram.unity_id == unity_id)
            .where(Organigram.deleted_at.is_(None))
            .limit(1)
        )
        node = row.scalar_one_or_none()
        if node is None:
            unity = await self._ref_unity_by_id(unity_id)
            return [unity] if unity else []

        chain: list[Unity] = []
        visited: set[int] = set()
        while node is not None and node.unity_id not in visited:
            visited.add(node.unity_id)
            chain.append(node.unity)
            if node.parent_id is None:
                break
            parent_row = await self.session.execute(
                select(Organigram)
                .where(Organigram.id == node.parent_id)
                .where(Organigram.deleted_at.is_(None))
                .limit(1)
            )
            node = parent_row.scalar_one_or_none()
        return chain

    @staticmethod
    def _build_reference_base(submitted_at: datetime) -> str:
        """Base de référence métier : EDG-{AA}, ex. EDG-26 pour 2026.

        La séquence (partie après la base, gérée par repo.next_ref) repart de
        00001 à chaque changement d'année — voir RepositoryRequest.next_ref().
        """
        return f"EDG-{submitted_at.year % 100:02d}"

    async def _direction_unity_ids(self, direction_id: int | str | None) -> set[int]:
        """Retourne la direction et ses services via organigramme + parent_direction_id."""
        if direction_id is None:
            return set()
        try:
            root_id = int(direction_id)
        except (TypeError, ValueError):
            return set()

        from api.models.ModelOrganigram import Organigram

        ids: set[int] = {root_id}
        org_row = await self.session.execute(
            select(Organigram.id)
            .where(Organigram.unity_id == root_id, Organigram.deleted_at.is_(None))
            .limit(1)
        )
        org_id = org_row.scalar_one_or_none()
        if org_id:
            child_rows = await self.session.execute(
                select(Organigram.unity_id)
                .where(Organigram.parent_id == org_id, Organigram.deleted_at.is_(None))
            )
            ids.update(int(uid) for (uid,) in child_rows.all() if uid is not None)

        unity_rows = await self.session.execute(
            select(Unity.id)
            .where(Unity.parent_direction_id == root_id, Unity.deleted_at.is_(None))
        )
        ids.update(int(uid) for (uid,) in unity_rows.all() if uid is not None)
        return ids

    # ── Sérialisation ─────────────────────────────────────────────────────────

    @staticmethod
    def _decrypt_schema(schema: RequestResponse) -> RequestResponse:
        updates: dict[str, Any] = {"request_status": normalize_status(schema.request_status)}
        if schema.description and schema.description.startswith("enc:"):
            updates["description"] = decrypt_field(schema.description)
        return schema.copy(update=updates)

    @staticmethod
    def _serialize(items: list, schema_cls=RequestListItemResponse) -> list:
        """Convertit les ORM Request en RequestListItemResponse (schéma allégé liste) et déchiffre les champs sensibles.

        `schema_cls` permet à un appel dont l'endpoint est gardé de servir un
        schéma plus large — voir `list_distribution`, seule liste autorisée à
        exposer `proposed_solution`. Par défaut, rien ne change."""
        result = []
        for item in items:
            schema = schema_cls.from_orm(item)
            updates = {"request_status": normalize_status(schema.request_status)}
            if schema.description and schema.description.startswith("enc:"):
                updates["description"] = decrypt_field(schema.description)
            result.append(schema.copy(update=updates))
        return result

    # ── Listes ────────────────────────────────────────────────────────────────

    # RequestListItemResponse ne sérialise ni attachments/tasks (endpoints dédiés)
    # ni timelines/appreciation (réservés à la page détail) — inutile de les
    # charger sur les listes/dashboards (jusqu'à 500 tickets d'un coup).
    _LIST_LOAD_OPTIONS = [
        noload(RequestModel.attachments),
        noload(RequestModel.tasks),
        noload(RequestModel.workflows),
        noload(RequestModel.appreciation),
    ]

    async def list_all(self, *, page: int = 1, limit: int = 20):
        items, total = await self.repo.list(
            order_by="-created_at", page=page, limit=limit,
            load_options=self._LIST_LOAD_OPTIONS,
        )
        return self.paginate(self._serialize(items), total, page, limit)

    async def list_filtered(
        self,
        *,
        request_status: Optional[str] = None,
        exclude_status: Optional[str] = None,
        is_external: Optional[bool] = None,
        direction_id: Optional[str] = None,
        unit_id: Optional[str] = None,
        assignee_id: Optional[str] = None,
        requester_id: Optional[str] = None,
        exclude_requester_id: Optional[str] = None,
        # BR-REQUESTER-NEVER-LOSES-001 — quand il est fourni, le périmètre devient
        # « unité OU je suis demandeur OU je suis assigné » au lieu de la seule
        # unité (voir RepositoryRequest._apply_filters).
        scope_actor_id: Optional[str] = None,
        search: Optional[str] = None,
        sla_breached: Optional[bool] = None,
        in_triage: Optional[bool] = None,
        date_from: Optional[str] = None,
        date_to: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ):
        # Résolution unity_id : unit_id = match exact ; direction_id = direction + tous ses services
        if unit_id is not None:
            effective_unity_id = unit_id
        elif direction_id is not None:
            effective_unity_id = list(await self._direction_unity_ids(direction_id))
        else:
            effective_unity_id = None

        if search:
            items, total = await self.repo.search(
                search,
                filters={
                    k: v for k, v in {
                        "request_status": request_status,
                        "exclude_request_status": exclude_status,
                        "is_external": is_external,
                        "unity_id": effective_unity_id,
                        "assignee_id": assignee_id,
                        "requester_id": requester_id,
                        "exclude_requester_id": exclude_requester_id,
                        "scope_actor_id": scope_actor_id,
                    }.items() if v is not None
                },
                page=page,
                limit=limit,
            )
        else:
            filters: dict[str, Any] = {}
            if request_status is not None:
                filters["request_status"] = request_status
            if exclude_status is not None:
                filters["exclude_request_status"] = exclude_status
            if is_external is not None:
                filters["is_external"] = is_external
            if effective_unity_id is not None:
                filters["unity_id"] = effective_unity_id
            if assignee_id is not None:
                filters["assignee_id"] = assignee_id
            if requester_id is not None:
                filters["requester_id"] = requester_id
            if exclude_requester_id is not None:
                filters["exclude_requester_id"] = exclude_requester_id
            if scope_actor_id is not None:
                filters["scope_actor_id"] = scope_actor_id
            if sla_breached is not None:
                filters["sla_breached"] = sla_breached
            if in_triage is not None:
                filters["in_triage"] = in_triage
            if date_from:
                from datetime import datetime as _dt
                try:
                    filters["date_from"] = _dt.fromisoformat(date_from)
                except ValueError:
                    pass
            if date_to:
                from datetime import datetime as _dt, timedelta as _td
                try:
                    # Inclure tout le jour "date_to" jusqu'à 23:59:59
                    filters["date_to"] = _dt.fromisoformat(date_to).replace(
                        hour=23, minute=59, second=59, microsecond=999999
                    )
                except ValueError:
                    pass

            items, total = await self.repo.list(
                filters=filters or None,
                order_by="-created_at",
                page=page,
                limit=limit,
                load_options=self._LIST_LOAD_OPTIONS,
            )
        return self.paginate(self._serialize(items), total, page, limit)

    async def list_by_status(self, status: str, *, page: int = 1, limit: int = 20):
        items, total = await self.repo.list_by_status(status, page=page, limit=limit)
        return self.paginate(self._serialize(items), total, page, limit)

    async def list_by_assignee(self, assignee_id: str, *, page: int = 1, limit: int = 20):
        items, total = await self.repo.list_by_assignee(assignee_id, page=page, limit=limit)
        return self.paginate(self._serialize(items), total, page, limit)

    async def list_by_direction(self, direction_id: str, *, page: int = 1, limit: int = 20):
        return await self.list_filtered(direction_id=direction_id, page=page, limit=limit)

    async def list_by_requester(self, requester_id: str, *, page: int = 1, limit: int = 20):
        items, total = await self.repo.list_by_requester(requester_id, page=page, limit=limit)
        return self.paginate(self._serialize(items), total, page, limit)

    async def list_pending_triage(self, *, page: int = 1, limit: int = 20):
        items, total = await self.repo.list_pending_triage(page=page, limit=limit)
        return self.paginate(self._serialize(items), total, page, limit)

    async def list_sla_breached(self, *, page: int = 1, limit: int = 20):
        items, total = await self.repo.list_sla_breached(page=page, limit=limit)
        return self.paginate(self._serialize(items), total, page, limit)

    async def list_transmitted_by_me(
        self,
        actor_id: str,
        *,
        search: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
        retransmitted_only: bool = False,
    ):
        items, total = await self.repo.list_transmitted_by_actor(
            actor_id,
            search=search,
            page=page,
            limit=limit,
            retransmitted_only=retransmitted_only,
        )
        return self.paginate(self._serialize(items), total, page, limit)

    async def list_queue(
        self,
        *,
        direction_id: Optional[str] = None,
        assignee_id: Optional[str] = None,
        unassigned_only: bool = False,
        priority: Optional[str] = None,
        request_status: Optional[str] = None,
        search: Optional[str] = None,
        page: int = 1,
        limit: int = 20,
    ):
        items, total = await self.repo.list_queue(
            direction_id=direction_id,
            assignee_id=assignee_id,
            unassigned_only=unassigned_only,
            priority=priority,
            request_status=request_status,
            search=search,
            page=page,
            limit=limit,
        )
        return self.paginate(self._serialize(items), total, page, limit)

    async def qualify_triage(
        self,
        id: str,
        data: dict,
        *,
        actor_id: Optional[str] = None,
        actor_name: Optional[str] = None,
        actor_role: Optional[str] = None,
        actor=None,
    ):
        """Qualifie une demande de triage : fixe l'unité/catégorie/priorité, in_triage=False.
        Si assignee_id fourni → status=assigned directement (routage vers une personne précise).
        Sinon → status=qualifying (la direction prend en charge).
        """
        patch = {k: v for k, v in data.items() if k in {"category", "priority", "proposed_solution"}}
        # Organisation traitante — déterminée par le SERVEUR, pas par le formulaire.
        # Seule la DSI traite les incidents : le service (et donc, par remontée,
        # le département et la direction) qui prend en charge la demande est
        # toujours celui du chef de service qui qualifie. Son rattachement est
        # déjà renseigné par l'administrateur au back-office, il n'a donc rien à
        # ressaisir. `unity_id` reste renseigné pour la traçabilité : c'est lui
        # qui distingue l'organisation TRAITANTE de celle du DEMANDEUR
        # (`requester_unit_id`, lu sur le compte du demandeur).
        actor_unity_id = getattr(actor, "unity_id", None)
        if actor_unity_id is not None:
            patch["unity_id"] = actor_unity_id
        elif "unit_id" in data:
            # Repli : acteur sans rattachement (ex. admin), l'appelant fournit la cible.
            patch["unity_id"] = data["unit_id"]
        elif "direction_id" in data:
            patch["unity_id"] = data["direction_id"]
        patch["in_triage"] = False

        assignee_id = data.get("assignee_id")
        assert_qualify_target_allowed(actor_role, actor_id, assignee_id)

        # BR-DISTRIBUTION-001 — orienter vers un chef de division support n'en fait
        # PAS le traitant : le ticket entre dans sa file "Distribution"
        # (`distributor_id` renseigne, `assignee_id` laisse vide) et c'est lui qui
        # decidera ensuite de le prendre ou de l'assigner a un technicien.
        target_is_division_chief = False
        if assignee_id and str(assignee_id) != str(actor_id or ""):
            row = await self.session.execute(
                select(Account.role).where(Account.id == int(assignee_id))
            )
            target_role_value = row.scalar_one_or_none()
            target_is_division_chief = (
                normalize_role(str(target_role_value or "")) == "chef-division-support"
            )

        if target_is_division_chief:
            patch["distributor_id"] = int(assignee_id)
            # Pas de traitant a ce stade : le ticket attend d'etre reparti.
            patch["request_status"] = "qualifying"
        elif assignee_id:
            patch["assignee_id"] = int(assignee_id)
            # BR-TRAITEMENT-PROGRESSIF-001 (2026-09-27) — remplace
            # BR-QUEUE-AUTO-START-001. Une prise ou une assignation depuis la
            # File d'attente ne démarre plus le traitement : elle désigne un
            # intervenant, rien de plus. Le traitement ne commence qu'au geste
            # explicite du traitant (`POST /{id}/start-treatment`), qui seul
            # peut horodater le vrai début et enregistrer le lieu.
            patch["request_status"] = "assigned"
        else:
            patch["request_status"] = "qualifying"

        current = await self._guard_ticket_action(
            id,
            "qualify",
            target_status=patch["request_status"],
            actor=actor,
            actor_role=actor_role,
        )
        # BR-DISTRIBUTION-001 — un ticket deja oriente vers un CDS ne peut pas etre
        # re-qualifie/reattribue par le chef de service tant que le CDS n'a pas
        # tranche : cela le sortirait silencieusement de sa file Distribution.
        self._assert_not_in_active_distribution(current, actor)
        if assignee_id:
            assert_requester_is_not_handler(current, assignee_id)
        if assignee_id and actor is not None:
            row = await self.session.execute(
                select(Account.unity_id, Account.role)
                .where(Account.id == int(assignee_id))
            )
            assignee_row = row.first()
            if assignee_row is None:
                raise self.not_found("Cet intervenant n'existe pas.", error_code=ErrorCode.ACCOUNT_NOT_FOUND)
            assignee_unity_id, assignee_role = assignee_row
            # Perimetre elargi supprime avec les roles director/chief-departement
            # (2026-09-25) : plus aucun role n'en beneficie.
            allowed_scope_unity_ids = None
            assert_assignment_allowed(
                actor,
                current,
                assignee_id,
                target_unity_id=assignee_unity_id,
                target_role=assignee_role,
                allowed_scope_unity_ids=allowed_scope_unity_ids,
            )

        # Traçabilité — l'organisation traitante retenue ici est gelée avec ses
        # libellés (voir `_handler_org_snapshot`). Fusionné sur les `infos`
        # existantes du ticket : ce champ JSON porte déjà les pointeurs
        # d'intervention et le snapshot du demandeur, qu'un remplacement
        # effacerait.
        handler_identity = await self._handler_org_snapshot(patch.get("unity_id"))
        # PV d'intervention EDG/PS-GSI/PV-01, bloc « Réception » — le PV demande
        # le responsable et son badge. C'est le chef de service qui réceptionne
        # et qualifie (tâche 1.2). Son identité doit être figée ICI : s'il impute
        # le ticket à un chef de division, aucune intervention n'est ouverte à
        # son nom, donc `_actor_identity_snapshot` ne la gèlerait jamais.
        receiver_identity: dict[str, Any] = {}
        if actor is not None:
            receiver_identity = self._clean_infos({
                "receiver_id": str(getattr(actor, "id", "") or "") or None,
                "receiver_name": actor_name or self._account_display_name(actor),
                "receiver_badge": getattr(actor, "matricule", None),
            })
        if handler_identity or receiver_identity:
            current_infos = getattr(current, "infos", None)
            patch["infos"] = {
                **(current_infos if isinstance(current_infos, dict) else {}),
                **handler_identity,
                **receiver_identity,
            }

        obj = await self.update(
            id,
            patch,
            actor_id=actor_id,
            actor_name=actor_name,
            actor_role=actor_role,
        )

        # BR-DISTRIBUTION-001 — trace + notification propres a l'entree en Distribution
        # (l'evenement generique d'`update()` ne couvre pas ce cas : il n'y a pas de
        # nouveau traitant, donc ni intervention ouverte ni notification "Ticket assigne").
        if target_is_division_chief:
            await self._record_distribution_event(
                id,
                event_type="distributed_to_division",
                label=f"Orienté vers le chef de division support — {actor_name or 'Chef de service'}",
                actor_id=actor_id,
                actor_name=actor_name,
                actor_role=actor_role,
                dest_id=int(assignee_id),
                dest_role="chef-division-support",
            )
            await emit_notif(
                self.session,
                recipient_id=str(assignee_id),
                title="Ticket à répartir",
                body=(
                    f"Le ticket {getattr(obj, 'ref', '')} vous a été orienté pour répartition. "
                    f"Prenez-le en charge ou assignez-le à un technicien de votre division."
                ),
                type="info",
                request_id=str(id),
                action_label="Ouvrir la Distribution",
                action_url="/app/distribution",
                commit=False,
            )
            await emit_event(AppEvent(
                type="request.distributed",
                payload={"id": str(id), "distributor_id": str(assignee_id)},
                target={"user_ids": [int(assignee_id)]},
            ))
        return obj

    # ── BR-DISTRIBUTION-001 — file "Distribution" du chef de division support ──

    def _assert_not_in_active_distribution(self, current, actor) -> None:
        """BR-DISTRIBUTION-001 — un ticket en Distribution active (oriente vers un CDS,
        pas encore reparti) ne peut sortir QUE par les actions de distribution du CDS
        destinataire (`/distribution/take`, `/distribution/assign`).

        Sans cette garde, l'etat "distributor_id renseigne + assignee_id NULL" rendait
        le ticket "libre" pour les chemins d'assignation generiques : un technicien du
        service pouvait s'auto-assigner via POST /{id}/assign, et le chef de service
        pouvait se le reattribuer via une re-qualification — court-circuitant dans les
        deux cas la decision de repartition du chef de division.

        Sans effet sur l'existant : la condition ne peut etre vraie que pour un ticket
        effectivement en Distribution (`distributor_id` NULL partout ailleurs)."""
        distributor_id = getattr(current, "distributor_id", None)
        if distributor_id is None:
            return
        if getattr(current, "assignee_id", None) is not None:
            return
        if normalize_role(str(getattr(actor, "role", "") or "")) == "admin":
            return
        # Le chef de division DESTINATAIRE est justement celui que le message
        # ci-dessous designe comme seul habilite : le bloquer revenait a lui
        # interdire de prendre en charge un ticket qui l'attend dans SA propre
        # file de distribution. Seuls les autres restent ecartes — au premier
        # rang desquels le chef de service qui vient de l'orienter, qui ne doit
        # pas pouvoir reprendre un ticket qu'il a envoye (BR-DISTRIBUTION-001).
        actor_id = getattr(actor, "id", None)
        if actor_id is not None and str(actor_id) == str(distributor_id):
            return
        raise self.forbidden(
            "Ce ticket est en cours de répartition par le chef de division support : "
            "seul ce dernier peut le prendre en charge ou l'assigner à un technicien."
        )

    async def _load_distribution_ticket(self, id: str, actor):
        """Charge un ticket en verifiant qu'il est bien dans la Distribution de l'acteur.

        Garde de securite centrale : elle rend impossible qu'un CDS agisse sur le
        ticket d'un autre CDS en manipulant l'ID dans la requete HTTP."""
        current = await self.repo.get_by_id(id)
        if current is None:
            raise self.not_found("Ce ticket n'existe pas.", error_code=ErrorCode.REQUEST_NOT_FOUND)

        actor_id = getattr(actor, "id", None)
        is_admin = normalize_role(str(getattr(actor, "role", "") or "")) == "admin"
        if not is_admin and str(getattr(current, "distributor_id", None) or "") != str(actor_id or ""):
            raise self.forbidden(
                "Ce ticket ne fait pas partie de votre file de distribution.",
            )
        if getattr(current, "assignee_id", None) is not None:
            raise ConflictException(
                "Ce ticket a déjà été réparti : il n'est plus dans votre file de distribution.",
                error_code=ErrorCode.TICKET_STATE_CONFLICT,
            )
        if normalize_status(current.request_status) in TERMINAL_STATUSES:
            raise ConflictException(
                "Ce ticket est clôturé : il ne peut plus être réparti.",
                error_code=ErrorCode.TICKET_STATE_CONFLICT,
            )
        return current

    async def _exit_distribution(
        self,
        current,
        *,
        new_assignee_id: int,
        actor_id: Optional[str],
        actor_name: Optional[str],
        actor_role: Optional[str],
        event_type: str,
        label: str,
        dest_role: str,
    ):
        """Sortie de la file Distribution : designe le responsable OPERATIONNEL.

        Ecriture atomique conditionnelle (`assignee_id IS NULL`) : si deux actions
        concurrentes ciblent le meme ticket (prise en charge + assignation), une
        seule peut reussir — le ticket ne peut jamais atterrir dans deux boites de
        traitement a la fois."""
        old_status = current.request_status
        # BR-TRAITEMENT-PROGRESSIF-001 — la sortie de Distribution désigne le
        # responsable opérationnel ; le traitement démarre à son geste explicite.
        translated = await self._translate_codes({"request_status": "assigned"})
        # `opening_meta` porte l'identité FIGÉE du nouvel intervenant (nom, badge,
        # statut, organisation) produite par `_actor_identity_snapshot`. Elle était
        # ici silencieusement jetée : les interventions ouvertes par la
        # distribution — c'est-à-dire le chemin NOMINAL de la procédure — n'avaient
        # donc aucune identité figée, ni dans le journal d'interventions ni dans le
        # PV. Elle est désormais jointe à l'événement d'ouverture, comme sur les
        # chemins `assign()` et `transmit_treatment()`.
        new_infos, opening_meta = await self._open_intervention(
            getattr(current, "infos", None), str(new_assignee_id), str(current.id)
        )

        stmt = (
            sa_update(RequestModel)
            .where(RequestModel.id == current.id)
            .where(RequestModel.assignee_id.is_(None))  # compare-and-set concurrence
            .values(**translated, assignee_id=new_assignee_id, in_triage=False, infos=new_infos)
        )
        result = await self.session.execute(stmt)
        if result.rowcount == 0:
            await self.session.rollback()
            raise ConflictException(
                "Ce ticket vient d'être réparti par une autre action. Veuillez actualiser la page.",
                error_code=ErrorCode.TICKET_STATE_CONFLICT,
            )
        await self.session.flush()
        await self.session.refresh(current)

        await self._record_distribution_event(
            str(current.id),
            event_type=event_type,
            label=label,
            actor_id=actor_id,
            actor_name=actor_name,
            actor_role=actor_role,
            dest_id=new_assignee_id,
            dest_role=dest_role,
            old_status=old_status,
            new_status="in_progress",
            extra_infos=opening_meta,
        )
        await self.session.commit()
        await self.session.refresh(current)
        return current

    async def distribution_take(
        self, id: str, *, actor, actor_name: Optional[str] = None,
    ):
        """Le chef de division prend lui-meme le ticket : il devient responsable
        operationnel et le ticket rejoint SA boite de traitement."""
        current = await self._load_distribution_ticket(id, actor)
        actor_id = str(getattr(actor, "id", "") or "")
        actor_role = normalize_role(str(getattr(actor, "role", "") or ""))
        assert_requester_is_not_handler(current, actor_id)

        obj = await self._exit_distribution(
            current,
            new_assignee_id=int(actor_id),
            actor_id=actor_id,
            actor_name=actor_name,
            actor_role=actor_role,
            event_type="distribution_taken",
            label=f"Pris en charge par le chef de division — {actor_name or ''}".strip(" —"),
            dest_role=actor_role,
        )
        await emit_event(AppEvent(
            type="request.assigned",
            payload={"id": str(id), "assignee_id": actor_id},
            target={"roles": "all"},
        ))
        return obj

    async def distribution_assign(
        self, id: str, technician_id: str, *, actor, actor_name: Optional[str] = None,
    ):
        """Le chef de division assigne le ticket a un technicien de SA division :
        le technicien devient responsable operationnel."""
        current = await self._load_distribution_ticket(id, actor)
        actor_id = str(getattr(actor, "id", "") or "")
        actor_role = normalize_role(str(getattr(actor, "role", "") or ""))

        row = await self.session.execute(
            select(Account.role, Account.unity_id, Account.account_status, Account.name)
            .where(Account.id == int(technician_id), Account.deleted_at.is_(None))
        )
        target = row.first()
        if target is None:
            raise self.not_found("Ce technicien n'existe pas.", error_code=ErrorCode.ACCOUNT_NOT_FOUND)
        target_role, target_unity_id, target_status, target_name = target

        if normalize_role(str(target_role or "")) != "technicien":
            raise self.forbidden(
                "Seul un technicien peut recevoir un ticket depuis la distribution.",
            )
        if str(target_status or "") != "active":
            raise self.forbidden("Ce technicien n'est pas actif.")
        actor_unity_id = getattr(actor, "unity_id", None)
        if normalize_role(str(getattr(actor, "role", "") or "")) != "admin":
            if not actor_unity_id or str(target_unity_id or "") != str(actor_unity_id):
                raise self.forbidden(
                    "Ce technicien n'appartient pas à votre division.",
                )
        assert_requester_is_not_handler(current, technician_id)

        obj = await self._exit_distribution(
            current,
            new_assignee_id=int(technician_id),
            actor_id=actor_id,
            actor_name=actor_name,
            actor_role=actor_role,
            event_type="distribution_assigned",
            label=f"Assigné au technicien {target_name or ''}".strip(),
            dest_role="technicien",
        )
        await emit_notif(
            self.session,
            recipient_id=str(technician_id),
            title="Ticket assigné",
            body=(
                f"Le ticket {getattr(obj, 'ref', '')} vous a été assigné par votre "
                f"chef de division. Il est disponible dans votre boîte de traitement."
            ),
            type="info",
            request_id=str(id),
            action_label="Ouvrir le ticket",
            action_url="/app/my-tickets",
        )
        await emit_event(AppEvent(
            type="request.assigned",
            payload={"id": str(id), "assignee_id": str(technician_id)},
            target={"roles": "all"},
        ))
        return obj

    async def list_distribution(self, account_id: str, *, page: int = 1, limit: int = 50):
        """File "Distribution" d'un chef de division : tickets qui lui ont ete
        orientes et qui n'ont pas encore de responsable operationnel."""
        items, total = await self.repo.list_distribution_for(account_id, page=page, limit=limit)
        # Procédure tâche 1.4 — le CDS décide de prendre ou d'affecter DEPUIS la
        # liste : il lui faut le descriptif de solution proposée sans ouvrir la
        # fiche. Endpoint déjà gardé par `_distribution_guard`.
        return self.paginate(
            self._serialize(items, DistributionListItemResponse), total, page, limit,
        )

    async def _record_distribution_event(
        self,
        request_id: str,
        *,
        event_type: str,
        label: str,
        actor_id: Optional[str],
        actor_name: Optional[str],
        actor_role: Optional[str],
        dest_id: Optional[int] = None,
        dest_role: Optional[str] = None,
        old_status: Optional[str] = None,
        new_status: Optional[str] = None,
        extra_infos: Optional[dict[str, Any]] = None,
    ) -> None:
        """BR-DISTRIBUTION-001 — journalise une etape de distribution dans le systeme
        d'audit existant (`workflow_detail`), sans mecanisme parallele.

        `extra_infos` transporte l'identite figee de l'intervention ouverte par
        cette etape (voir `_exit_distribution`) : sans elle, une intervention nee
        d'une distribution resterait anonyme dans le journal et sur le PV."""
        wf_id = await self._get_or_create_workflow(int(request_id))
        infos: dict[str, Any] = {"source_role": actor_role, **(extra_infos or {})}
        if dest_role:
            infos["dest_role"] = dest_role
        if old_status:
            infos["old_status"] = old_status
        if new_status:
            infos["new_status"] = new_status
        await self.detail_repo.create_event({
            "workflow_id": wf_id,
            "event_type": event_type,
            "label": label,
            "actor_id": actor_id,
            "actor_name": actor_name,
            **({"dest_id": dest_id} if dest_id else {}),
            "infos": infos,
        }, commit=False)

    # ── Constat d'intervention (procédure tâche 2.1) ──────────────────────────

    @staticmethod
    def _field_check_event(request) -> Optional[Any]:
        """Constat terrain de l'intervention EN COURS, s'il existe.

        Rattaché à `current_intervention_id` et non au ticket : après une
        transmission, le nouvel intervenant doit faire SON propre constat — celui
        de son prédécesseur ne vaut pas pour lui."""
        infos = request.infos if isinstance(request.infos, dict) else {}
        intervention_id = infos.get("current_intervention_id")
        if not intervention_id:
            return None
        for event in reversed(request.timelines or []):
            if event.event_type != "field_check":
                continue
            event_infos = event.infos if isinstance(event.infos, dict) else {}
            if event_infos.get("intervention_id") == intervention_id:
                return event
        return None

    def _assert_field_check_done(self, request) -> None:
        """Procédure EDG/PS-GSI/Pro-02 — la tâche 2.1 (« qualifier la demande »,
        point de contrôle « vérification de l'état réel de la requête ») précède
        la 2.2 (« résoudre le problème »). On ne peut donc pas clore un
        traitement sans avoir consigné son constat.

        N'est exigé que si l'intervention porte `field_check_required`, posé à son
        ouverture : les interventions antérieures à la règle restent résolvables."""
        infos = request.infos if isinstance(request.infos, dict) else {}
        if not infos.get("field_check_required"):
            return
        if self._field_check_event(request) is not None:
            return
        raise self.bad_request(
            "Consignez d'abord votre constat d'intervention : la procédure impose "
            "de vérifier l'état réel de la requête avant de la résoudre.",
            error_code=ErrorCode.MISSING_REQUIRED_FIELD,
        )

    async def field_check(
        self,
        id: str,
        *,
        conformity: str,
        findings: str,
        observed_category: Optional[str] = None,
        observed_priority: Optional[str] = None,
        actor=None,
        actor_id: Optional[str] = None,
        actor_name: Optional[str] = None,
        actor_role: Optional[str] = None,
    ):
        """Tâche 2.1 — l'intervenant confronte l'état réel de la requête à ce qui
        a été décrit, avant d'intervenir.

        Distinct de la qualification du chef de service (tâches 1.2/1.3, réservée
        à la File d'attente) : celle-ci oriente le ticket sur pièce, celle-là
        constate sur le terrain. Aucune table ni colonne : un événement du
        `workflow_detail`, comme les étapes de distribution."""
        clean_findings = findings.strip() if isinstance(findings, str) else ""
        if not clean_findings:
            raise self.bad_request(
                "Décrivez ce que vous avez constaté sur le terrain.",
                error_code=ErrorCode.MISSING_REQUIRED_FIELD,
            )
        if conformity not in _FIELD_CHECK_CONFORMITY:
            raise self.bad_request(
                "Indiquez si l'état réel est conforme à la demande ou s'il s'en écarte.",
                error_code=ErrorCode.INVALID_FIELD_VALUE,
            )

        current = await self.get_by_id(id)
        if actor is not None:
            assert_is_current_handler(actor, current)

        infos = current.infos if isinstance(current.infos, dict) else {}
        intervention_id = infos.get("current_intervention_id")
        is_gap = conformity == "ecart"

        # BR-FIELD-CHECK-REQUALIFY-001 — le constat REQUALIFIE le ticket.
        #
        # La catégorie et la priorité constatées n'étaient consignées que dans
        # l'événement de workflow : le ticket gardait la qualification faite sur
        # pièce, et l'écart relevé sur le terrain n'apparaissait nulle part sur la
        # demande elle-même (ni dans les listes, ni dans les filtres, ni dans les
        # statistiques, ni dans le calcul du SLA qui dépend de la priorité).
        # L'intervenant qui constate sur place est la meilleure source : ses
        # valeurs sont désormais appliquées à la demande. L'ancienne valeur reste
        # tracée dans l'événement ci-dessous, et le chef de service est prévenu.
        requalify: dict = {}
        previous_category = getattr(current, "category", None)
        previous_priority = getattr(current, "priority", None)
        if observed_category and str(observed_category) != str(previous_category or ""):
            requalify["category"] = observed_category
        if observed_priority and str(observed_priority) != str(previous_priority or ""):
            requalify["priority"] = observed_priority

        wf_id = await self._get_or_create_workflow(int(id))
        await self.detail_repo.create_event({
            "workflow_id": wf_id,
            "event_type": "field_check",
            "label": (
                "Constat d'intervention — écart avec la demande"
                if is_gap else "Constat d'intervention — conforme à la demande"
            ),
            "actor_id": actor_id,
            "actor_name": actor_name,
            "infos": self._clean_infos({
                "actor_role": actor_role,
                "source_role": actor_role,
                "conformity": conformity,
                "findings": clean_findings,
                "observed_category": observed_category,
                "observed_priority": observed_priority,
                # Requalification effective : on garde trace de ce qui portait le
                # ticket avant le constat, pour savoir ce que le terrain a corrigé.
                "requalified": bool(requalify),
                "previous_category": previous_category if "category" in requalify else None,
                "previous_priority": previous_priority if "priority" in requalify else None,
                # Rattache le constat à l'intervention, pas au ticket : après une
                # transmission, le suivant refait le sien.
                "intervention_id": intervention_id,
                **self._current_intervention_meta(current.infos),
            }),
        }, commit=False)

        # BR-TRAITEMENT-PROGRESSIF-001 — marque le constat SUR LE TICKET, rattaché
        # à l'intervention en cours. C'est ce marqueur que `start_treatment` lit
        # pour refuser un démarrage sans constat, sans rejouer tout le journal.
        marked_infos = dict(current.infos) if isinstance(current.infos, dict) else {}
        marked_infos["field_check_intervention_id"] = intervention_id
        marked_infos["field_check_at"] = datetime.now(timezone.utc).isoformat()
        await self.repo.update(str(id), {"infos": marked_infos}, commit=False)

        if requalify:
            translated = await self._translate_codes(requalify)
            updated = await self.repo.update(str(id), translated, commit=False)
            if updated is None:
                raise self.not_found(
                    "Cette demande n'existe pas.", error_code=ErrorCode.REQUEST_NOT_FOUND
                )
            self._logger.info(
                f"Constat — demande {getattr(current, 'ref', id)} requalifiée : "
                f"{', '.join(f'{k}={v}' for k, v in requalify.items())}"
            )

        # Un écart remet en cause la qualification, qui appartient au chef de
        # service (tâches 1.2/1.3) : il doit l'apprendre. Aucun chemin de retour
        # n'est créé pour autant — transmission et mise en attente restent les
        # voies existantes.
        if is_gap:
            await self._notify_handling_chiefs(current, id, clean_findings, actor_name)

        await emit_event(AppEvent(
            type="request.field_checked",
            payload={
                "id": str(id),
                "conformity": conformity,
                "requalified": bool(requalify),
                **({"category": requalify["category"]} if "category" in requalify else {}),
                **({"priority": requalify["priority"]} if "priority" in requalify else {}),
            },
            target={"roles": "all"},
        ))
        return await self.get_by_id(id)

    async def start_treatment(
        self,
        id: str,
        *,
        location: str,
        actor=None,
        actor_id: Optional[str] = None,
        actor_name: Optional[str] = None,
        actor_role: Optional[str] = None,
    ):
        """BR-TRAITEMENT-PROGRESSIF-001 — « Démarrer le traitement ».

        Deuxième geste du workflow progressif, entre le constat (tâche 2.1) et la
        résolution (tâche 2.2). Il matérialise le début RÉEL de l'intervention :
        l'horodatage est pris **ici, côté serveur**, jamais reçu du navigateur.

        Le lieu est saisi par le traitant et lui seul : le demandeur ne le
        renseigne plus à la création (décision produit du 2026-09-27).
        """
        clean_location = location.strip() if isinstance(location, str) else ""
        if not clean_location:
            raise self.bad_request(
                "Indiquez le lieu de l'intervention.",
                error_code=ErrorCode.MISSING_REQUIRED_FIELD,
            )

        current = await self.get_by_id(id)
        if actor is not None:
            assert_is_current_handler(actor, current)

        # Double démarrage : refus explicite plutôt qu'une transition invalide.
        if current.request_status == "in_progress":
            raise self.bad_request(
                "Le traitement de ce ticket est déjà démarré.",
                error_code=ErrorCode.INVALID_STATUS_TRANSITION,
            )
        if current.request_status != "assigned":
            raise self.bad_request(
                "Ce ticket doit vous être assigné avant que vous puissiez démarrer "
                "son traitement.",
                error_code=ErrorCode.INVALID_STATUS_TRANSITION,
            )

        # Démarrage sans constat : refus. On réutilise la garde de `resolve()`
        # plutôt que d'en écrire une seconde — elle porte déjà la règle exacte
        # (exigé seulement si l'intervention porte `field_check_required`, donc
        # du technicien) et retrouve le constat de l'intervention EN COURS, celui
        # d'un intervenant précédent ne valant pas pour le suivant.
        self._assert_field_check_done(current)
        infos = dict(current.infos) if isinstance(current.infos, dict) else {}

        started_at = datetime.now(timezone.utc)
        infos["treatment_started_at"] = started_at.isoformat()
        infos["treatment_location"] = clean_location

        translated = await self._translate_codes({"request_status": "in_progress"})
        updated = await self.repo.update(
            str(id),
            # `location_label` est le champ que le PV imprime déjà (`place`) :
            # on le renseigne ici plutôt que d'en créer un second.
            {"infos": infos, "location_label": clean_location, **translated},
            commit=False,
        )
        if updated is None:
            raise self.not_found(
                "Cette demande n'existe pas.", error_code=ErrorCode.REQUEST_NOT_FOUND
            )

        wf_id = await self._get_or_create_workflow(int(id))
        await self.detail_repo.create_event({
            "workflow_id": wf_id,
            "event_type": "treatment_started",
            "label": "Traitement démarré",
            "actor_id": actor_id,
            "actor_name": actor_name,
            "activated": True,
            "infos": self._clean_infos({
                "actor_role": actor_role,
                "source_role": actor_role,
                "old_status": "assigned",
                "new_status": "in_progress",
                "treatment_location": clean_location,
                "treatment_started_at": started_at.isoformat(),
                **self._current_intervention_meta(current.infos),
            }),
        }, commit=False)

        await emit_event(AppEvent(
            type="request.status_changed",
            payload={"id": str(id), "status": "in_progress"},
            target={"roles": "all"},
        ))
        return await self.get_by_id(id)

    async def _notify_handling_chiefs(
        self, request, request_id: str, findings: str, actor_name: Optional[str],
    ) -> None:
        """Prévient le(s) chef(s) de service de l'unité TRAITANTE — celle que la
        qualification a inscrite sur le ticket. Choix déterministe, plutôt que de
        rechercher dans le journal qui a qualifié."""
        if not request.unity_id:
            return
        rows = await self.session.execute(
            select(Account.id).where(
                Account.unity_id == int(request.unity_id),
                Account.role == "chief-service",
                Account.deleted_at.is_(None),
            )
        )
        who = actor_name or "L'intervenant"
        ref = getattr(request, "ref", "")
        for (chief_id,) in rows.all():
            await emit_notif(
                self.session,
                recipient_id=str(chief_id),
                title="Écart constaté sur le terrain",
                body=(
                    f"{who} signale un écart entre la demande {ref} "
                    f"et l'état réel constaté : {findings[:180]}"
                ),
                type="warning",
                request_id=str(request_id),
                action_label="Ouvrir le ticket",
                action_url=f"/app/requests/{request_id}",
                commit=False,
            )

    # ── PV d'intervention — circuit (procédure tâches 3.3 et 3.4) ─────────────

    @staticmethod
    def _pv_state(request) -> dict[str, Any]:
        """État du PV, lu depuis `infos`. Aucune table ni colonne : le PV est un
        document dérivé du ticket, seul son circuit est journalisé."""
        infos = request.infos if isinstance(request.infos, dict) else {}
        return {
            "validated_at": infos.get("pv_validated_at"),
            "validated_by": infos.get("pv_validated_by"),
            "submitted_at": infos.get("pv_submitted_at"),
            "submitted_by": infos.get("pv_submitted_by"),
            "archived_at": infos.get("pv_archived_at"),
            "archived_by": infos.get("pv_archived_by"),
        }

    async def record_pv_validation(
        self,
        request_id: str,
        *,
        confirmed: bool,
        actor_id: Optional[str] = None,
        actor_name: Optional[str] = None,
        automatic: bool = False,
    ) -> bool:
        """Tâche 3.2 — « valider le dépannage » par le demandeur.

        Appelé depuis `ServiceAppreciation` : la validation n'est pas un geste
        supplémentaire, c'est la confirmation de résolution que le demandeur
        donne déjà avec son appréciation. On l'inscrit ici au circuit du PV
        plutôt que de lui créer une seconde validation concurrente.

        `confirmed=False` (le demandeur conteste, le ticket est rouvert) efface
        tout le circuit : le PV de l'intervention précédente ne vaut plus, et
        celle qui suivra devra produire le sien."""
        current = await self.get_by_id(request_id)
        infos = dict(current.infos) if isinstance(current.infos, dict) else {}
        if confirmed:
            if infos.get("pv_validated_at"):
                return False  # déjà validé, on ne réécrit pas l'horodatage d'origine
            infos["pv_validated_at"] = datetime.now(timezone.utc).isoformat()
            infos["pv_validated_by"] = actor_id
            # BR-AUTO-VALIDATION-001 — distingue une validation SUBIE (silence du
            # demandeur pendant le délai) d'une validation DONNÉE. Sans ce drapeau,
            # les deux seraient indiscernables dans le journal comme dans les
            # statistiques, et l'on croirait à une approbation explicite.
            infos["pv_validated_automatically"] = bool(automatic)
            label = (
                f"Dépannage validé automatiquement — sans réponse du demandeur "
                f"sous {AUTO_VALIDATION_DAYS} jours"
                if automatic
                else f"Dépannage validé par le demandeur — {actor_name or ''}".strip(" —")
            )
        else:
            for key in (
                "pv_validated_at", "pv_validated_by",
                "pv_submitted_at", "pv_submitted_by",
                "pv_archived_at", "pv_archived_by",
            ):
                infos.pop(key, None)
            label = "Dépannage contesté par le demandeur — circuit du PV réinitialisé"

        await self.repo.update(request_id, {"infos": infos}, commit=False)
        wf_id = await self._get_or_create_workflow(int(request_id))
        await self.detail_repo.create_event({
            "workflow_id": wf_id,
            "event_type": "pv_validated" if confirmed else "pv_invalidated",
            "label": label,
            "actor_id": actor_id,
            "actor_name": actor_name,
            "infos": self._clean_infos({
                "actor_role": "system" if automatic else "user",
                "source_role": "system" if automatic else "user",
                "auto_validated": bool(automatic) if confirmed else None,
            }),
        }, commit=False)

        # BR-TRAITEMENT-PROGRESSIF-001 — soumission AUTOMATIQUE au chef de
        # division dès que le demandeur a validé. Le traitant n'a plus de geste
        # manuel à faire : « Terminer le traitement » enclenche le circuit, la
        # validation du demandeur (tâche 3.2) le libère. La tâche 3.2 reste donc
        # un vrai point de contrôle, elle n'est pas court-circuitée.
        #
        # Le PV est soumis AU NOM DU TRAITANT (`assignee_id`), pas du demandeur
        # qui valide : c'est lui qui l'a établi (tâche 3.1).
        #
        # Idempotence : on ne soumet que si ce n'est pas déjà fait, donc une
        # double validation ou un double clic ne produit ni seconde soumission,
        # ni seconde transition, ni notification en double.
        if confirmed and not infos.get("pv_submitted_at"):
            await self._record_pv_submission(
                current,
                infos,
                actor_id=str(current.assignee_id) if current.assignee_id else None,
                actor_name=infos.get("current_intervenant_name"),
                actor_role=None,
            )
        return True

    def _assert_is_last_handler(self, request, actor) -> None:
        """Le PV est soumis APRÈS la résolution, donc sur un statut terminal —
        `assert_is_current_handler` ne convient pas, sa liste de statuts
        autorisés étant `COLLABORATIVE_STATUSES`. La règle reste la même sur le
        fond : c'est l'intervenant qui a traité le ticket, pas un rôle."""
        if normalize_role(str(getattr(actor, "role", "") or "")) == "admin":
            return
        assignee_id = getattr(request, "assignee_id", None)
        actor_id = getattr(actor, "id", None)
        if assignee_id is None or actor_id is None or str(assignee_id) != str(actor_id):
            raise self.forbidden(
                "Seul l'intervenant qui a traité ce ticket peut soumettre son PV.",
            )

    async def pv_submit(
        self,
        id: str,
        *,
        attachments: Optional[list[dict]] = None,
        actor=None,
        actor_id: Optional[str] = None,
        actor_name: Optional[str] = None,
        actor_role: Optional[str] = None,
    ):
        """Tâche 3.3 — « Soumettre le PV d'intervention au Chef de division ».

        Le destinataire n'est pas choisi : c'est le chef de division qui a
        réparti ce ticket (`distributor_id`), déjà enregistré par la tâche 1.4.
        La pièce jointe facultative est le PV **signé et scanné** — la signature
        étant manuscrite, c'est ainsi qu'elle entre dans le système."""
        current = await self.get_by_id(id)
        if actor is not None:
            self._assert_is_last_handler(current, actor)
        if current.request_status not in {"resolved", "closed"}:
            raise self.bad_request(
                "Terminez le traitement avant de soumettre le PV d'intervention.",
                error_code=ErrorCode.INVALID_STATUS_TRANSITION,
            )
        # La tâche 3.2 (« valider le dépannage », par le demandeur) précède la
        # 3.3 : on ne soumet pas au chef de division un PV que le demandeur n'a
        # pas encore validé.
        if not self._pv_state(current)["validated_at"]:
            raise self.bad_request(
                "Le demandeur n'a pas encore validé le dépannage : le PV ne peut "
                "pas être soumis.",
                error_code=ErrorCode.INVALID_STATUS_TRANSITION,
            )

        infos = dict(current.infos) if isinstance(current.infos, dict) else {}
        return await self._record_pv_submission(
            current,
            infos,
            actor_id=actor_id,
            actor_name=actor_name,
            actor_role=actor_role,
            attachment_count=len(attachments or []) or None,
        )

    async def _record_pv_submission(
        self,
        current,
        infos: dict,
        *,
        actor_id: Optional[str],
        actor_name: Optional[str],
        actor_role: Optional[str],
        attachment_count: Optional[int] = None,
    ):
        """Écrit la soumission du PV — marqueurs, journal, notification au chef de
        division, événement temps réel.

        Partagée par la soumission manuelle (`pv_submit`) et la soumission
        AUTOMATIQUE déclenchée par la validation du demandeur
        (`record_pv_validation`) : un seul endroit produit une soumission, donc
        les deux chemins ne peuvent pas diverger. `infos` est muté puis écrit par
        l'appelant unique ci-dessous, ce qui garde l'opération dans la même
        transaction que ce qui l'a déclenchée.

        **Idempotence** : l'appelant vérifie `pv_submitted_at` avant d'appeler.
        """
        request_id = str(current.id)
        infos["pv_submitted_at"] = datetime.now(timezone.utc).isoformat()
        infos["pv_submitted_by"] = actor_id
        obj = await self.repo.update(request_id, {"infos": infos}, commit=False)

        wf_id = await self._get_or_create_workflow(int(request_id))
        await self.detail_repo.create_event({
            "workflow_id": wf_id,
            "event_type": "pv_submitted",
            "label": f"PV d'intervention soumis au chef de division — {actor_name or ''}".strip(" —"),
            "actor_id": actor_id,
            "actor_name": actor_name,
            "infos": self._clean_infos({
                "actor_role": actor_role,
                "source_role": actor_role,
                "attachment_count": attachment_count,
            }),
        }, commit=False)

        if current.distributor_id:
            await emit_notif(
                self.session,
                recipient_id=str(current.distributor_id),
                title="PV d'intervention à archiver",
                body=(
                    f"Le PV du ticket {getattr(current, 'ref', '')} vous est soumis. "
                    f"Enregistrez-le et archivez-le."
                ),
                type="info",
                request_id=request_id,
                action_label="Ouvrir le suivi des interventions",
                action_url="/app/pv-tracking",
                commit=False,
            )
        await emit_event(AppEvent(
            type="request.pv_submitted",
            payload={"id": request_id},
            target={"user_ids": [int(current.distributor_id)]} if current.distributor_id else {"roles": "all"},
        ))
        return obj

    async def pv_archive(
        self,
        id: str,
        *,
        actor=None,
        actor_id: Optional[str] = None,
        actor_name: Optional[str] = None,
        actor_role: Optional[str] = None,
    ):
        """Tâche 3.4 — « Enregistrer et archiver le PV d'intervention ».

        Réservé au chef de division destinataire (`distributor_id`), l'admin
        gardant son bypass habituel. Archiver un PV qui n'a pas été soumis n'a
        pas de sens : la tâche 3.3 précède la 3.4."""
        current = await self.get_by_id(id)
        actor_normalized = normalize_role(str(getattr(actor, "role", actor_role or "") or ""))
        if actor_normalized != "admin":
            if not current.distributor_id or str(current.distributor_id) != str(getattr(actor, "id", "")):
                raise self.forbidden(
                    "Seul le chef de division qui a réparti ce ticket peut archiver son PV.",
                )
        state = self._pv_state(current)
        if not state["submitted_at"]:
            raise self.bad_request(
                "Ce PV n'a pas encore été soumis par l'intervenant.",
                error_code=ErrorCode.INVALID_STATUS_TRANSITION,
            )

        infos = dict(current.infos) if isinstance(current.infos, dict) else {}
        infos["pv_archived_at"] = datetime.now(timezone.utc).isoformat()
        infos["pv_archived_by"] = actor_id
        obj = await self.repo.update(id, {"infos": infos}, commit=False)

        wf_id = await self._get_or_create_workflow(int(id))
        await self.detail_repo.create_event({
            "workflow_id": wf_id,
            "event_type": "pv_archived",
            "label": f"PV d'intervention enregistré et archivé — {actor_name or ''}".strip(" —"),
            "actor_id": actor_id,
            "actor_name": actor_name,
            "infos": self._clean_infos({"actor_role": actor_role, "source_role": actor_role}),
        }, commit=False)

        await emit_event(AppEvent(
            type="request.pv_archived",
            payload={"id": str(id)},
            target={"roles": "all"},
        ))
        return obj

    async def list_pv_tracking(self, account_id: str, *, page: int = 1, limit: int = 50):
        """TSI — Tableau de Suivi des Interventions (livrable de la tâche 3.4).

        Distinct du rapport `GET /reports/interventions`, qui agrège des
        statistiques : le TSI est un suivi **ligne à ligne**, du ticket réparti
        jusqu'à l'archivage de son PV."""
        items, total = await self.repo.list_pv_tracking_for(account_id, page=page, limit=limit)
        return self.paginate(self._serialize(items, PvTrackingItemResponse), total, page, limit)

    async def list_resolved_by(self, account_id: str, *, page: int = 1, limit: int = 50):
        """Onglet « Tickets résolus » — le travail termine de l'intervenant connecte.

        `RequestListItemResponse` et non `RequestResponse` : cette liste n'a
        besoin ni de l'historique de workflow ni du CSAT, et le schema allege
        n'expose pas `proposed_solution`.
        """
        items, total = await self.repo.list_resolved_by(account_id, page=page, limit=limit)
        return self.paginate(self._serialize(items, RequestListItemResponse), total, page, limit)

    # ── Lectures unitaires ────────────────────────────────────────────────────

    async def get_by_id(self, id: str, *, include_deleted: bool = False):
        obj = await self.repo.get_by_id(id, include_deleted=include_deleted)
        if obj is None:
            raise self.not_found(
                "Cette demande n'existe pas.",
                error_code=ErrorCode.REQUEST_NOT_FOUND,
                field="id",
                value=id,
            )
        return obj

    async def get_by_ref(self, ref: str):
        obj = await self.repo.find_by_ref(ref)
        if obj is None:
            raise self.not_found(
                f"Aucune demande avec la référence '{ref}'.",
                error_code=ErrorCode.REQUEST_NOT_FOUND,
                field="ref",
                value=ref,
            )
        return obj

    async def track(self, ref: str, email: Optional[str] = None, phone: Optional[str] = None):
        obj = await self.repo.find_by_ref(ref)
        if obj is None:
            raise self.not_found(
                "Aucune demande trouvée pour ces coordonnées.",
                error_code=ErrorCode.REQUEST_NOT_FOUND,
                field="ref",
                value=ref,
            )

        if not email and not phone:
            raise self.not_found(
                "Aucune demande trouvée pour ces coordonnées.",
                error_code=ErrorCode.REQUEST_NOT_FOUND,
                field="ref",
                value=ref,
            )

        # Coordonnées du demandeur : compte interne prioritaire, sinon champs libres
        if obj.requester:
            actual_email = (obj.requester.email or "").strip().lower()
            actual_phone = (obj.requester.phone or "").strip()
        else:
            actual_email = (obj.requester_email or "").strip().lower()
            actual_phone = (obj.requester_phone or "").strip()

        _strip_phone = lambda s: re.sub(r"[\s\-\(\)\.]", "", s)

        credential_ok = False
        if email and actual_email and email.strip().lower() == actual_email:
            credential_ok = True
        if phone and actual_phone and _strip_phone(phone) == _strip_phone(actual_phone):
            credential_ok = True

        if not credential_ok:
            raise self.not_found(
                "Aucune demande trouvée pour ces coordonnées.",
                error_code=ErrorCode.REQUEST_NOT_FOUND,
                field="ref",
                value=ref,
            )

        return obj

    # ── Auto-affectation ──────────────────────────────────────────────────────

    async def _select_auto_assignee(
        self, unity_id: int, *, exclude_id: Optional[int | str] = None,
    ) -> Optional[int]:
        """Retourne l'agent disponible le moins chargé dans l'unité cible.

        BR-REQUESTER-NO-SELF-TREATMENT-001 — `exclude_id` (typiquement le
        demandeur du ticket) est exclu des candidats, sans autre restriction
        sur le nombre d'agents disponibles restants.
        """
        # Statuts terminaux — exclus du comptage de charge active
        terminal_result = await self.session.execute(
            select(RequestStatus.id)
            .where(RequestStatus.code.in_(["resolved", "closed", "cancelled", "rejected"]))
            .where(RequestStatus.deleted_at.is_(None))
        )
        terminal_ids = [r[0] for r in terminal_result.fetchall()]

        # Charge active de chaque agent (demandes non terminées assignées)
        load_filter = (
            RequestModel.request_status_id.not_in(terminal_ids)
            if terminal_ids
            else sql_true()
        )
        load_sq = (
            select(RequestModel.assignee_id, func.count().label("cnt"))
            .where(RequestModel.deleted_at.is_(None))
            .where(RequestModel.assignee_id.is_not(None))
            .where(load_filter)
            .group_by(RequestModel.assignee_id)
            .subquery()
        )

        # Agent disponible le moins chargé dans l'unité
        stmt = (
            select(Account.id)
            .outerjoin(load_sq, Account.id == load_sq.c.assignee_id)
            .where(Account.unity_id == unity_id)
            .where(Account.role.in_(["chief-service", "technicien", "chef-division-support"]))
            .where(Account.account_status == "active")
            .where(or_(Account.availability.is_(None), Account.availability == "available"))
            .where(Account.deleted_at.is_(None))
        )
        if exclude_id is not None:
            stmt = stmt.where(Account.id != int(exclude_id))
        stmt = stmt.order_by(func.coalesce(load_sq.c.cnt, 0).asc()).limit(1)

        result = await self.session.execute(stmt)
        return result.scalar_one_or_none()

    async def _auto_assign(
        self,
        request_id: int,
        unity_id: int,
        *,
        actor_id: Optional[str] = None,
    ) -> None:
        """Affecte la demande à l'agent disponible le moins chargé de l'unité."""
        agent_id = await self._select_auto_assignee(unity_id)
        if agent_id is None:
            return

        current = await self.repo.get_by_id(str(request_id))
        if current is not None:
            assert_transition_allowed(current.request_status, "assigned")

        translated = await self._translate_codes({"request_status": "assigned"})
        await self.repo.update(str(request_id), {
            "assignee_id": agent_id,
            "unity_id": unity_id,
            "in_triage": False,
            **translated,
        })

    # ── Routage automatique ───────────────────────────────────────────────────

    async def _notify_queue_managers(self, obj, *, reason: str) -> None:
        """Prévient les gestionnaires de la file d'attente qu'un ticket y attend.

        BR-NO-AUTO-HANDOVER-001 — plus aucun ticket n'est attribué automatiquement,
        donc il n'y a plus d'assigné à notifier. Ce sont les titulaires de la file
        (chef de service, et l'admin qui y a accès) qu'il faut alerter, sans quoi
        un ticket pourrait dormir sans que personne ne sache qu'il est arrivé.
        """
        from api.repositories.RepositoryAccount import AccountRepository

        acc_repo = AccountRepository(self.session)
        managers, _ = await acc_repo.list(
            filters={"role": ["chief-service", "admin"]},
            only_active=True,
            limit=50,
        )
        for manager in managers:
            await emit_notif(
                self.session,
                recipient_id=str(manager.id),
                title="Nouveau ticket à qualifier",
                body=f"Le ticket {obj.ref} est en file d'attente ({reason}).",
                type="info",
                request_id=str(obj.id),
                action_label="Ouvrir la file d'attente",
                action_url="/app/queue",
                commit=False,
            )

    async def _apply_routing(
        self,
        obj,
        wf_id: int,
        *,
        actor_id: Optional[str] = None,
        actor_name: Optional[str] = None,
        raw_description: str = "",
        actor_role: str = "user",
    ) -> bool:
        """
        Évalue les règles de routage et oriente la demande.

        Retourne True si une règle a matché (ROUTED_TO_SERVICE),
        False si aucune règle (ROUTED_TO_SUPPORT / triage).

        Mapping sans nouvelles tables :
          current_holder_id   → request.assignee_id
          current_holder_role → dérivé de assignee.role
          current_service_id  → request.unity_id
          event_status        → workflow_detail.infos["event_status"]
        """
        from api.repositories.RepositoryRoutingRule import RoutingRuleRepository
        from api.repositories.RepositoryAccount import AccountRepository

        rr_repo = RoutingRuleRepository(self.session)
        acc_repo = AccountRepository(self.session)

        matched = await rr_repo.find_matching_rule(
            category=obj.category,
            priority=obj.priority,
            source=obj.request_source,
            title=obj.title,
            description=raw_description,
        )

        if matched and matched.target_unity_id:
            target_unity_id = matched.target_unity_id
            chief = await acc_repo.find_chief_for_unity(target_unity_id)

            # Conflit d'intérêt / BR-REQUESTER-NO-SELF-TREATMENT-001 : le demandeur
            # (actor_id, ce point d'appel de _apply_routing ne reçoit jamais que le
            # requester_id — voir create()) est lui-même le chef de l'unité cible.
            # On bascule en triage pour éviter l'auto-traitement (biais, traçabilité).
            if chief and str(chief.id) == str(actor_id):
                self._logger.warning(
                    f"Demande {obj.ref} → conflit d'intérêt : requester #{actor_id} "
                    f"est chef de l'unité {target_unity_id} — basculement en triage"
                )
                if actor_id:
                    await emit_notif(
                        self.session,
                        recipient_id=str(actor_id),
                        title="Ticket transmis au support général",
                        body=(
                            f"Votre ticket {obj.ref} a été transmis au support général "
                            f"car vous êtes responsable du service cible (neutralité garantie)."
                        ),
                        type="info",
                        request_id=str(obj.id),
                        action_label="Suivre mon ticket",
                        action_url=f"/app/requests/{obj.id}",
                        commit=False,
                    )
                # Fall-through au bloc triage ci-dessous
            else:
                # BR-NO-AUTO-HANDOVER-001 — une règle de routage ORIENTE vers une
                # unité, elle n'ATTRIBUE plus le ticket à une personne. Aucun
                # niveau ne doit recevoir un ticket à traiter sans action d'envoi
                # explicite : le ticket reste donc en file d'attente, où seuls le
                # chef de service et l'admin le voient, et c'est la qualification
                # qui désignera le traitant. `matched.auto_assign` est conservé en
                # base et tracé dans l'événement, mais n'assigne plus personne.
                event_label = f"Orientation automatique — {matched.name}"

                await self.detail_repo.create_event({
                    "workflow_id": wf_id,
                    "event_type": "routed_to_service",
                    "label": event_label,
                    "actor_name": actor_name,
                    "actor_id": actor_id,
                    "dest_id": None,
                    "unity_id": target_unity_id,
                    "activated": True,
                    "infos": self._clean_infos({
                        "event_status": "to_qualify",
                        "rule_id": str(matched.id),
                        "rule_name": matched.name,
                        "auto_assign": matched.auto_assign,
                        "auto_assigned": False,
                        "source_role": actor_role,
                        "actor_role": actor_role,
                        "dest_role": "chief-service",
                        "target_role": "chief-service",
                        "old_status": getattr(obj, "request_status", None),
                        "new_status": "qualifying",
                        "target_unity_id": target_unity_id,
                    }),
                }, commit=False)

                assert_transition_allowed(obj.request_status, "qualifying", actor_role=actor_role)
                status_translated = await self._translate_codes({"request_status": "qualifying"})
                await self.repo.update(str(obj.id), {
                    "unity_id": target_unity_id,
                    "in_triage": True,
                    **status_translated,
                }, commit=False)

                await self._notify_queue_managers(obj, reason=f"orienté vers l'unité {target_unity_id}")

                await emit_event(AppEvent(
                    type="request.routed",
                    payload={"id": obj.id, "unity_id": target_unity_id, "rule": matched.name},
                    target={"roles": "all"},
                ))
                self._logger.info(
                    f"Demande {obj.ref} orientée → unité={target_unity_id} "
                    f"(file d'attente, aucune attribution automatique)"
                )
                return True

        # Aucune règle OU conflit d'intérêt → file d'attente, SANS traitant.
        #
        # BR-NO-AUTO-HANDOVER-001 — ce chemin assignait le ticket au premier agent
        # actif par ordre alphabétique (find_support_agent), tous rôles
        # opérationnels confondus : un technicien ou un chef de division pouvait
        # donc se voir attribuer un ticket sans qu'aucune action d'envoi ne le lui
        # adresse. Le ticket reste désormais dans la file d'attente, visible du
        # seul chef de service (et de l'admin), jusqu'à sa qualification.
        await self.detail_repo.create_event({
            "workflow_id": wf_id,
            "event_type": "routed_to_support",
            "label": "Aucune règle de routage — mise en file d'attente",
            "actor_name": actor_name,
            "actor_id": actor_id,
            "dest_id": None,
            "activated": True,
            "infos": self._clean_infos({
                "event_status": "to_qualify",
                "source_role": actor_role,
                "actor_role": actor_role,
                "dest_role": "chief-service",
                "target_role": "chief-service",
                "old_status": getattr(obj, "request_status", None),
                "new_status": "qualifying",
            }),
        }, commit=False)

        assert_transition_allowed(obj.request_status, "qualifying", actor_role=actor_role)
        status_qualifying = await self._translate_codes({"request_status": "qualifying"})
        await self.repo.update(str(obj.id), {
            "assignee_id": None,
            "in_triage": True,
            **status_qualifying,
        }, commit=False)

        await self._notify_queue_managers(obj, reason="aucune règle de routage")

        self._logger.info(f"Demande {obj.ref} → file d'attente (aucun traitant désigné)")
        return False

    @staticmethod
    def _should_auto_route(data: dict) -> bool:
        infos = data.get("infos")
        if isinstance(infos, dict) and infos.get("auto_route") is True:
            return True
        return data.get("auto_route") is True

    # ── Créations ─────────────────────────────────────────────────────────────

    async def create(self, data: dict):
        self._logger.info(f"Création demande — catégorie={data.get('category')!r}")

        # BR-NO-ORPHAN-TICKET-001 — toute demande naît DANS la file d'attente.
        #
        # `in_triage` valait False par défaut (modèle) et seul le routage, appelé
        # après l'insertion, le passait à True. Or ce routage est volontairement
        # « best effort » : en cas d'échec, il journalise et poursuit. Le ticket
        # restait alors `new`, sans assigné et hors triage — donc invisible à la
        # fois de la file d'attente (qui exige `in_triage`) et de toute boîte de
        # traitement : plus personne ne pouvait le prendre en charge.
        # L'état par défaut doit être l'état sûr ; le routage ne fait plus que
        # l'affiner.
        data.setdefault("in_triage", True)

        duplicate = await self.repo.find_duplicate(
            title=data.get("title", ""),
            category=data.get("category", ""),
            requester_id=data.get("requester_id"),
            requester_email=data.get("requester_email"),
            meter_number=data.get("meter_number"),
        )
        if duplicate is not None:
            raise self.conflict(
                f"Une demande identique est déjà en cours de traitement (réf. {duplicate.ref}).",
                error_code=ErrorCode.DUPLICATE_REQUEST,
                field="title",
                hint=(
                    f"Votre demande \"{duplicate.title}\" est déjà enregistrée sous "
                    f"la référence {duplicate.ref} avec le statut "
                    f"\"{duplicate.request_status}\". Consultez son avancement ou "
                    f"contactez votre agent de support."
                ),
            )

        submitted_at = datetime.now(timezone.utc)
        ref_base = self._build_reference_base(submitted_at)
        category_code = data.get("category")
        raw_description = data.get("description", "")

        # SLA — résout sla_hours depuis la politique catégorie+priorité (sla_policy),
        # sauf si déjà fourni explicitement par l'appelant.
        if not data.get("sla_hours"):
            from api.repositories.RepositorySlaPolicy import SlaPolicyRepository
            sla_policy = await SlaPolicyRepository(self.session).find_policy(
                (category_code or "").lower(), data.get("priority", "medium")
            )
            if sla_policy is not None:
                data["sla_hours"] = sla_policy.resolution_h

        # Traçabilité — identité organisationnelle du demandeur figée ici, une
        # fois pour toutes (voir `_requester_identity_snapshot`).
        requester_identity = await self._requester_identity_snapshot(data.get("requester_id"))
        if requester_identity:
            existing_infos = data.get("infos")
            data["infos"] = {
                **(existing_infos if isinstance(existing_infos, dict) else {}),
                **requester_identity,
            }

        obj = None
        workflow_steps: list[dict] = []
        ref = ""
        for attempt in range(25):
            ref = await self.repo.next_ref(ref_base)
            data["ref"] = ref
            translated = await self._translate_codes(data)
            workflow_steps = translated.pop("workflows", None) or []
            try:
                obj = await self.repo.create(translated)
                break
            except ConflictException as exc:
                if exc.error_code != "REF_ALREADY_EXISTS":
                    raise
                self._logger.warning(
                    "Collision référence %s détectée, nouvelle tentative (%s/25)",
                    ref,
                    attempt + 1,
                )
        if obj is None:
            raise self.conflict(
                "Impossible de générer une référence unique pour cette demande.",
                error_code=ErrorCode.REF_ALREADY_EXISTS,
                field="ref",
                value=ref_base,
                hint="Réessayez dans quelques secondes.",
            )
        wf_id = await self._get_or_create_workflow(obj.id)

        # Étape 1 — événement CREATED
        # Perf (harmonisation transactionnelle 2026-08) : à partir d'ici, toutes
        # les écritures de ce flux passent en flush (commit=False) — un seul
        # commit réel a lieu en fin de requête HTTP (dependency get_db(), qui
        # commit après un retour réussi et rollback sur exception). `obj` (le
        # ticket) reste lui committé plus haut par self.repo.create() pour
        # préserver intacte la logique de retry sur collision de référence
        # (IntegrityError → rollback → nouvelle tentative), qui a besoin d'un
        # commit/rollback réel à cette étape précise.
        await self.detail_repo.create_event({
            "workflow_id": wf_id,
            "event_type": "created",
            "label": "Demande créée par l'utilisateur",
            "actor_id": data.get("requester_id"),
            "actor_name": data.get("requester_name"),
            "activated": True,
            "infos": {
                "event_status": "new",
                "source_role": data.get("requester_role", "user"),
                "actor_role": data.get("requester_role", "user"),
                "new_status": "new",
            },
        }, commit=False)

        # Circuit de validation optionnel (pattern edgrh)
        for i, step in enumerate(workflow_steps):
            step_data = dict(step) if isinstance(step, dict) else step
            step_data["workflow_id"] = wf_id
            step_data.setdefault("activated", i == 0)
            step_data.setdefault("accepted", None)
            await self.detail_repo.create(step_data, commit=False)

        self._logger.info(f"Demande créée — ref={ref}")
        await emit_event(AppEvent(
            type="request.created",
            payload={"id": obj.id, "ref": ref, "category": category_code},
            target={"roles": ["chief-service", "technicien", "chef-division-support", "admin"]},
        ))

        # BR-NOTIFICATION-WORKFLOW-001 §5 — le demandeur doit être informé que son
        # ticket est bien créé et placé en File d'attente, avant même tout routage.
        requester_id = data.get("requester_id")
        if requester_id:
            await emit_notif(
                self.session,
                recipient_id=str(requester_id),
                title="Ticket créé",
                body=f"Votre ticket {ref} a été créé avec succès et placé dans la File d'attente.",
                type="success",
                request_id=str(obj.id),
                action_label="Voir le ticket",
                action_url=f"/app/requests/{obj.id}",
                commit=False,
            )

        # Les chefs de service (CSSHF) tiennent la File d'attente : ils doivent
        # apprendre qu'une demande est arrivée même s'ils étaient déconnectés au
        # moment de sa création. L'événement SSE ci-dessus ne fait que rafraîchir
        # les écrans déjà ouverts — il ne laisse aucune trace consultable plus
        # tard. Le fan-out est volontairement limité à `chief-service` : l'admin
        # voit la même file mais ne qualifie pas, le notifier à chaque création
        # n'apporterait que du bruit.
        from api.repositories.RepositoryAccount import AccountRepository

        # `list_by_role_strict` et non `list_by_role` : cette dernière élargit
        # `chief-service` au groupe {chief-service, technicien,
        # chef-division-support} via `_role_filter`, ce qui notifierait des rôles
        # qui n'ont pas accès à la File d'attente.
        chiefs = await AccountRepository(self.session).list_by_role_strict(
            "chief-service"
        )
        # Un chef de service qui crée sa propre demande reçoit déjà « Ticket
        # créé » ci-dessus : l'exclure évite une double notification.
        chief_ids = [str(c.id) for c in chiefs if str(c.id) != str(requester_id or "")]
        if chief_ids:
            await emit_bulk(
                self.session,
                recipient_ids=chief_ids,
                title="Nouvelle demande à qualifier",
                body=f"La demande {ref} vient d'être créée et attend une qualification.",
                type="info",
                request_id=str(obj.id),
                action_label="Ouvrir la File d'attente",
                action_url="/app/queue?tab=qualify",
                commit=False,
            )

        # Étape 2 — routage automatique uniquement si explicitement demandé.
        # begin_nested() = SAVEPOINT : si le routage échoue en cours de route
        # (ex. contrainte FK improbable), seules SES propres écritures sont
        # annulées — le ticket/événement/notification déjà flush ci-dessus
        # restent intacts et seront bien commités en fin de requête. Le routage
        # reste strictement "best effort" (échec = log + poursuite), exactement
        # comme avant, mais sans risque de corrompre la création elle-même.
        if self._should_auto_route(data):
            try:
                async with self.session.begin_nested():
                    await self._apply_routing(
                        obj, wf_id,
                        actor_id=data.get("requester_id"),
                        actor_name=data.get("requester_name"),
                        raw_description=raw_description,
                        actor_role=data.get("requester_role", "user"),
                    )
            except Exception as exc:
                self._logger.warning(f"Routage échoué pour demande {ref}: {exc}")

        # Re-fetch pour retourner l'état complet après routage — nécessaire
        # désormais aussi pour peupler les colonnes server_default
        # (created_at/updated_at) qu'un simple flush ne rapatrie pas côté
        # objet Python (elles restent lisibles en base, dans la même
        # transaction, dès le flush — seule l'instance ORM locale ne les a pas).
        fresh = await self.repo.get_by_id(obj.id)
        if fresh is not None:
            obj = fresh

        return obj

    async def submit_external(self, data: dict):
        """Soumission publique externe — force is_external=True et requester_type=external."""
        data["is_external"] = True
        data["requester_type"] = "external"
        data.setdefault("request_status", "new")
        data.setdefault("in_triage", True)
        return await self.create(data)

    # ── Mises à jour ──────────────────────────────────────────────────────────

    async def update(
        self,
        id: str,
        data: dict,
        *,
        actor_id: Optional[str] = None,
        actor_name: Optional[str] = None,
        actor_role: Optional[str] = None,
    ):
        raw_status = data.get("request_status")
        status_code = normalize_status(raw_status) if raw_status else None
        if raw_status and status_code != raw_status:
            data = {**data, "request_status": status_code}
        data.pop("status_reason", None)
        current = await self.repo.get_by_id(id)

        # Validation stricte de la matrice : les routes dediees portent les exceptions metier.
        if status_code and current is not None:
            assert_transition_allowed(
                current.request_status,
                status_code,
                actor_role=actor_role,
            )

        # BR-TRACE-001 — un `assignee_id` different de l'actuel ouvre une nouvelle
        # intervention (qualification directe vers une personne, auto-assignation,
        # prise en charge) — couvre ce chemin générique en plus de `assign()` et
        # `transmit_treatment()` dédiés.
        opening_meta: dict[str, Any] = {}
        new_assignee_id = data.get("assignee_id")
        if (
            new_assignee_id
            and current is not None
            and str(new_assignee_id) != str(getattr(current, "assignee_id", None) or "")
        ):
            # Base de fusion : les `infos` fournies par l'appelant si elles
            # existent, sinon celles en base. Sans ça, un appelant qui patche
            # `infos` ET l'assignation (cas de `qualify_triage`, qui y fige
            # l'organisation traitante) verrait son patch silencieusement
            # écrasé par l'état relu en base.
            patched_infos = data.get("infos")
            new_infos, opening_meta = await self._open_intervention(
                patched_infos if isinstance(patched_infos, dict) else getattr(current, "infos", None),
                new_assignee_id,
                id,
            )
            data = {**data, "infos": new_infos}

        translated = await self._translate_codes(data)
        obj = await self.repo.update(id, translated, commit=False)
        if obj is None:
            raise self.not_found(
                "Cette demande n'existe pas.",
                error_code=ErrorCode.REQUEST_NOT_FOUND,
                field="id",
                value=id,
            )
        if status_code:
            event_type = _STATUS_EVENT_MAP.get(status_code, "status_changed")
            if status_code == "in_progress" and opening_meta and new_assignee_id:
                # BR-QUEUE-AUTO-START-001 §7 — une seule ligne de journal cohérente
                # ("pris/assigné" + "traitement démarré"), jamais deux événements
                # distincts pour la même action utilisateur.
                intervenant_name = opening_meta.get("intervention_actor_name")
                event_label = (
                    f"Pris en charge par {intervenant_name} — traitement démarré"
                    if intervenant_name
                    else "Pris en charge — traitement démarré"
                )
            else:
                event_label = _STATUS_LABEL_MAP.get(status_code, f"Statut → {status_code}")
            wf_id = await self._get_or_create_workflow(int(id))
            await self.detail_repo.create_event({
                "workflow_id": wf_id,
                "event_type": event_type,
                "label": event_label,
                "actor_id": actor_id,
                "actor_name": actor_name,
                # BR-TRANSMIT-HANDOVER-001 — sur une assignation, on enregistre le
                # DESTINATAIRE (`dest_id` → colonne `agent_id`), comme le fait déjà
                # le chemin `assign()` dédié. C'est ce qui permet à « Tickets
                # transmis » de distinguer une assignation à un tiers d'une
                # auto-assignation (« Prendre le ticket »), qui ne transmet rien.
                **(
                    {"dest_id": int(new_assignee_id)}
                    if event_type == "assigned" and new_assignee_id
                    else {}
                ),
                "activated": True,
                "infos": self._clean_infos({
                    "event_status": status_code,
                    "source_role": actor_role,
                    "actor_role": actor_role,
                    "old_status": getattr(current, "request_status", None),
                    "new_status": status_code,
                    "changed_fields": sorted(data.keys()),
                    # BR-TRACE-001 — intervention ouverte, le cas échéant (qualification
                    # directe, auto-assignation, prise en charge).
                    **opening_meta,
                }),
            }, commit=False)
            await emit_event(AppEvent(
                type="request.status_changed",
                payload={"id": id, "status": status_code},
                target={"roles": "all"},
            ))
            # Notification individuelle au demandeur (CDC §6.3). BR-NOTIFICATION-
            # WORKFLOW-001 §22 — seuls les événements importants/actionnables
            # déclenchent un email ; les étapes de progression routinière restent
            # App-only pour éviter le bruit. Exception ajoutée (2026-08) : "in_progress"
            # passe aussi par email — c'est le statut posé par une prise/assignation
            # depuis la File d'attente (BR-QUEUE-AUTO-START-001), le demandeur doit être
            # notifié par mail dès qu'un intervenant prend effectivement son ticket
            # (couvre aussi la reprise pending → in_progress, même signal côté demandeur).
            # "qualifying" volontairement absent (harmonisation statuts/notifications,
            # 2026-08) : c'est un état technique de file d'attente (pas encore de
            # prise en charge active), donc pas d'événement métier distinct pour le
            # demandeur — cf. "new" = file d'attente. "pending" retiré : statut
            # inatteignable désormais (cf. ticket_actions.ALLOWED_TRANSITIONS).
            _notif_map = {
                "assigned":     ("Ticket pris en charge", "Votre ticket {ref} a été pris en charge par un intervenant.", "info", False),
                "in_progress":  ("Ticket en cours de traitement", "Votre ticket {ref} est maintenant en cours de traitement.", "info", True),
            }
            if status_code in _notif_map and obj is not None and obj.requester_id:
                title_tpl, body_tpl, notif_type, send_email_flag = _notif_map[status_code]
                ref_val = getattr(obj, "ref", id)
                await emit_notif(
                    self.session,
                    recipient_id=str(obj.requester_id),
                    title=title_tpl,
                    body=body_tpl.format(ref=ref_val),
                    type=notif_type,
                    request_id=id,
                    action_label="Voir le ticket",
                    action_url=f"/app/requests/{id}",
                    send_email=send_email_flag,
                    commit=False,
                )

            # BR-NOTIFICATION-WORKFLOW-001 §4/§6/§7 + BR-QUEUE-AUTO-START-001 —
            # cohérence assign()/qualify_triage() : toute transition qui installe
            # réellement un nouvel intervenant (assignee_id changé, intervention
            # ouverte via BR-TRACE-001 ci-dessus) doit notifier CE nouvel
            # intervenant (App+Email), quel que soit le chemin technique emprunté.
            # `status_code` vaut désormais "in_progress" pour une prise/assignation
            # depuis la File d'attente (qualify_triage()) — "assigned" reste
            # couvert pour les autres chemins génériques qui en dépendraient encore
            # (ex. PATCH admin direct). Ne se déclenche jamais pour `escalated`
            # (déjà notifié nominativement par les routes d'escalade dédiées).
            if status_code in ("assigned", "in_progress") and opening_meta and new_assignee_id:
                await emit_notif(
                    self.session,
                    recipient_id=str(new_assignee_id),
                    title="Ticket assigné",
                    body=f"Le ticket {getattr(obj, 'ref', id)} vous a été attribué. Vous pouvez commencer votre intervention.",
                    type="info",
                    request_id=id,
                    action_label="Voir le ticket",
                    action_url=f"/app/requests/{id}",
                    commit=False,
                )
        else:
            if data:
                wf_id = await self._get_or_create_workflow(int(id))
                await self.detail_repo.create_event({
                    "workflow_id": wf_id,
                    "event_type": "request_updated",
                    "label": "Demande mise à jour",
                    "actor_id": actor_id,
                    "actor_name": actor_name,
                    "activated": True,
                    "infos": self._clean_infos({
                        "event_status": getattr(obj, "request_status", None),
                        "source_role": actor_role,
                        "actor_role": actor_role,
                        "changed_fields": sorted(data.keys()),
                    }),
                }, commit=False)
            await emit_event(AppEvent(
                type="request.updated",
                payload={"id": id},
                target={"roles": "all"},
            ))
        return obj

    _REQUESTER_EDIT_STATUSES = ("new", "qualifying")

    async def requester_edit(self, id: str, data: dict, *, actor_id: str, actor_role: str = "user"):
        """Modification personnelle d'un ticket par son demandeur.
        Autorisé uniquement si request_status in ('new', 'qualifying') — dès que le
        ticket est qualifié/assigné/traité, le contenu d'origine est verrouillé pour
        préserver la traçabilité du workflow ; toute information complémentaire passe
        par les commentaires/réponses/pièces jointes. Un ticket réouvert (reopened)
        reste verrouillé : ce n'est volontairement pas un statut autorisé ici.
        Seuls le titre et la description sont modifiables depuis l'espace personnel.
        """
        from fastapi import HTTPException as _HTTP

        req = await self.repo.get_by_id(id)
        if req is None:
            raise self.not_found("Demande introuvable", error_code=ErrorCode.REQUEST_NOT_FOUND)

        if str(req.requester_id) != str(actor_id):
            raise _HTTP(status_code=403, detail="Seul le demandeur peut modifier ce ticket.")

        if req.request_status not in self._REQUESTER_EDIT_STATUSES:
            raise _HTTP(
                status_code=422,
                detail="Ce ticket ne peut plus être modifié — un acteur est déjà intervenu.",
            )

        patch: dict = {}
        if data.get("title"):
            patch["title"] = data["title"].strip()
        raw_desc = data.get("description", "")
        if raw_desc:
            patch["description"] = raw_desc.strip()

        if not patch:
            raise _HTTP(
                status_code=422,
                detail="Aucune modification autorisée à enregistrer.",
            )

        patch["assignee_id"] = None

        translated_patch = await self._translate_codes(patch)
        await self.repo.update(id, translated_patch)

        wf_id = await self._get_or_create_workflow(req.id)
        await self.detail_repo.create_event({
            "workflow_id": wf_id,
            "event_type": "requester_edit",
            "label": "Ticket modifié par le demandeur",
            "actor_id": actor_id,
            "actor_name": req.requester_name,
            "activated": True,
            "infos": {
                "event_status": "new",
                "source_role": actor_role,
                "actor_role": actor_role,
                "old_status": req.request_status,
                "new_status": "new",
                "changed_fields": sorted(patch.keys()),
            },
        })

        fresh = await self.repo.get_by_id(id)
        try:
            await self._apply_routing(
                fresh, wf_id,
                actor_id=actor_id,
                actor_name=req.requester_name,
                raw_description=raw_desc,
                actor_role=actor_role,
            )
        except Exception as exc:
            self._logger.warning(f"Re-routage échoué pour demande {req.ref}: {exc}")

        return await self.repo.get_by_id(id)

    async def assign(
        self, id: str, assignee_id: str, *,
        actor_id: Optional[str] = None,
        actor_name: Optional[str] = None,
        actor_role: Optional[str] = None,
        actor=None,
    ):
        # BR-TRAITEMENT-PROGRESSIF-001 — assigner désigne un intervenant ; le
        # traitement ne démarre qu'à son geste explicite (`start_treatment`).
        current = await self._guard_ticket_action(
            id,
            "assign",
            target_status="assigned",
            actor=actor,
            actor_role=actor_role,
        )
        # BR-DISTRIBUTION-001 — la Distribution est la seule porte de sortie tant que
        # le chef de division n'a pas tranche (cf. _assert_not_in_active_distribution).
        self._assert_not_in_active_distribution(current, actor)
        row = await self.session.execute(
            select(
                Account.unity_id,
                Unity.parent_direction_id,
                Account.name,
                Account.firstname,
                Account.role,
            )
            .select_from(Account)
            .outerjoin(Unity, Unity.id == Account.unity_id)
            .where(Account.id == int(assignee_id))
        )
        assignee_row = row.first()
        if assignee_row is None:
            raise self.not_found("Cet agent n'existe pas.", error_code=ErrorCode.ACCOUNT_NOT_FOUND)

        (
            assignee_unity_id,
            assignee_parent_dir_id,
            assignee_name_raw,
            assignee_firstname,
            assignee_role,
        ) = assignee_row
        assignee_name = self._account_display_name(assignee_name_raw, assignee_firstname)

        if actor is not None:
            # Perimetre elargi supprime avec les roles director/chief-departement
            # (2026-09-25) : plus aucun role n'en beneficie.
            allowed_scope_unity_ids = None
            assert_assignment_allowed(
                actor,
                current,
                assignee_id,
                target_unity_id=assignee_unity_id,
                target_role=assignee_role,
                allowed_scope_unity_ids=allowed_scope_unity_ids,
            )
        assert_requester_is_not_handler(current, assignee_id)

        if actor_role not in _BYPASS_ROLES:
            assignee_direction_id = assignee_parent_dir_id or assignee_unity_id

            if current.direction_id is not None and assignee_direction_id != current.direction_id:
                raise self.bad_request(
                    "Cet agent n'appartient pas à la direction de ce ticket.",
                    error_code=ErrorCode.INVALID_STATUS_TRANSITION,
                )

        # BR-TRACE-001 — ouvre l'intervention du nouvel assigné.
        new_infos, opening_meta = await self._open_intervention(current.infos, assignee_id, id)

        # BR-TRAITEMENT-PROGRESSIF-001 — le ticket est assigné, pas démarré.
        translated = await self._translate_codes({"request_status": "assigned"})
        assign_patch = {
            "assignee_id": assignee_id,
            "in_triage": False,
            "infos": new_infos,
            **translated,
        }
        # BR-QUALIF-ORG-001 — l'organisation traitante est figée à la
        # qualification et ne doit jamais être réécrite ensuite. Mais une
        # assignation directe (routage dynamique vers un agent, sans passer par
        # la file de qualification) laissait `unity_id` vide : le ticket
        # n'appartenait alors à aucune unité et disparaissait de toutes les vues
        # scopées par unité. On ne la renseigne donc QUE si elle est encore vide.
        if current.unity_id is None and assignee_unity_id is not None:
            assign_patch["unity_id"] = assignee_unity_id
        obj = await self.repo.update(id, assign_patch, commit=False)
        if obj is None:
            raise self.not_found("Cette demande n'existe pas.", error_code=ErrorCode.REQUEST_NOT_FOUND)
        wf_id_assign = await self._get_or_create_workflow(int(id))
        await self.detail_repo.create_event({
            "workflow_id": wf_id_assign,
            # event_type reste "assigned" : décrit l'action réalisée (une
            # assignation) — event_status/new_status ci-dessous portent le
            # statut métier résultant réel (in_progress), sans dupliquer
            # l'événement (section 7, BR-QUEUE-AUTO-START-001).
            "event_type": "assigned",
            # Plus de « traitement démarré » ici : depuis
            # BR-TRAITEMENT-PROGRESSIF-001, assigner ne démarre plus le
            # traitement, qui attend le geste explicite du traitant.
            "label": f"Ticket assigné à {assignee_name or assignee_id}",
            "actor_id": actor_id,
            "actor_name": actor_name,
            "dest_id": assignee_id,
            "activated": True,
            "infos": self._clean_infos({
                "event_status": "in_progress",
                "source_role": actor_role,
                "actor_role": actor_role,
                "dest_role": assignee_role,
                "target_role": assignee_role,
                "target_user_id": str(assignee_id),
                "target_user_name": assignee_name,
                # BR-TRACE-001 — intervention ouverte par cette assignation.
                **opening_meta,
                "old_status": current.request_status,
                "new_status": "in_progress",
                "old_assignee_id": current.assignee_id,
                "new_assignee_id": assignee_id,
                "target_unity_id": assignee_unity_id,
            }),
        }, commit=False)
        await emit_notif(
            self.session,
            recipient_id=assignee_id,
            title="Ticket assigné",
            body=f"Le ticket {obj.ref} vous a été attribué. Vous pouvez commencer votre intervention.",
            type="info",
            request_id=id,
            action_label="Voir le ticket",
            action_url=f"/app/requests/{id}",
            commit=False,
        )
        # BR-NOTIFICATION-WORKFLOW-001 §7 — le demandeur est informé (App only, la
        # personne qui assigne n'a pas besoin d'être notifiée de sa propre action).
        if obj.requester_id and not self._same_account(obj.requester_id, assignee_id):
            await emit_notif(
                self.session,
                recipient_id=str(obj.requester_id),
                title="Ticket pris en charge",
                body=f"Votre ticket {obj.ref} a été pris en charge par un intervenant.",
                type="info",
                request_id=id,
                action_label="Voir le ticket",
                action_url=f"/app/requests/{id}",
                send_email=False,
                commit=False,
            )
        await emit_event(AppEvent(
            type="request.assigned",
            payload={"id": id, "assignee_id": assignee_id},
            target={"roles": "all"},
        ))
        return obj

    async def close(
        self,
        id: str,
        *,
        actor_id: Optional[str] = None,
        actor_name: Optional[str] = None,
        actor_role: Optional[str] = None,
        actor=None,
    ):
        current = await self._guard_ticket_action(
            id,
            "close",
            target_status="closed",
            actor=actor,
            actor_role=actor_role,
        )
        translated = await self._translate_codes({"request_status": "closed"})
        obj = await self.repo.update(id, {
            **translated,
            "closed_at": datetime.now(timezone.utc).replace(tzinfo=None),
        }, commit=False)
        if obj is None:
            raise self.not_found("Cette demande n'existe pas.", error_code=ErrorCode.REQUEST_NOT_FOUND)
        wf_id_close = await self._get_or_create_workflow(int(id))
        await self.detail_repo.create_event({
            "workflow_id": wf_id_close,
            "event_type": "closed",
            "label": "Demande clôturée",
            "actor_id": actor_id,
            "actor_name": actor_name,
            "activated": True,
            "infos": self._clean_infos({
                "event_status": "closed",
                "source_role": actor_role,
                "actor_role": actor_role,
                "old_status": current.request_status,
                "new_status": "closed",
            }),
        }, commit=False)
        if obj.requester_id:
            await emit_notif(
                self.session,
                recipient_id=str(obj.requester_id),
                title="Ticket clôturé",
                body=f"Votre ticket {obj.ref} est maintenant clôturé.",
                type="success",
                request_id=id,
                action_label="Voir le ticket",
                action_url=f"/app/requests/{id}",
                commit=False,
            )
        # Lot finition §3 — le dernier intervenant est informé de la confirmation du
        # demandeur (App-only) : purement informatif, ne réaffecte rien, ne rouvre
        # aucune intervention, `assignee_id` déjà inchangé par close().
        last_handler_id = current.assignee_id
        if last_handler_id and str(last_handler_id) != str(obj.requester_id or ""):
            await emit_notif(
                self.session,
                recipient_id=str(last_handler_id),
                title="Ticket clôturé",
                body=f"Le demandeur a confirmé la résolution du ticket {obj.ref}.",
                type="info",
                request_id=id,
                action_label="Voir le ticket",
                action_url=f"/app/requests/{id}",
                send_email=False,
                commit=False,
            )
        await emit_event(AppEvent(type="request.closed", payload={"id": id}, target={"roles": "all"}))
        return obj

    async def resolve(
        self,
        id: str,
        *,
        actor_id: Optional[str] = None,
        actor_name: Optional[str] = None,
        actor_role: Optional[str] = None,
        actor=None,
        summary: str = "",
        solution: str = "",
        work_done: str = "",
        recommendations: Optional[str] = None,
        attachments: Optional[list[dict]] = None,
    ):
        """
        BR-TRANSMIT-001 — "Terminer le traitement". Autorisé à l'intervenant actuel
        (request.assignee_id == actor.id) parmi les rôles traitants, sans restriction
        de rôle supplémentaire (les restrictions historiques portaient sur les
        rôles chef de département et directeur, retirés le 2026-09-25)
        (BR-DIRECTOR-RESOLVE-001). Résumé/solution/travail réalisé désormais
        obligatoires pour tous les rôles (remplace le motif "exceptionnel" réservé
        à chief-service (role supprime), Lot 2.6).
        """
        clean_summary = summary.strip() if isinstance(summary, str) else ""
        clean_solution = solution.strip() if isinstance(solution, str) else ""
        clean_work_done = work_done.strip() if isinstance(work_done, str) else ""
        if not clean_summary:
            raise self.bad_request("Le résumé final est obligatoire.", error_code=ErrorCode.MISSING_REQUIRED_FIELD)
        if not clean_solution:
            raise self.bad_request("La solution appliquée est obligatoire.", error_code=ErrorCode.MISSING_REQUIRED_FIELD)
        if not clean_work_done:
            raise self.bad_request("Le travail réalisé est obligatoire.", error_code=ErrorCode.MISSING_REQUIRED_FIELD)
        clean_recommendations = recommendations.strip() if isinstance(recommendations, str) else ""

        effective_role = str(getattr(actor, "role", actor_role or "") or "")
        if effective_role:
            assert_action_allowed(effective_role, "resolve")

        current = await self.get_by_id(id)
        if actor is not None:
            assert_is_current_handler(actor, current)
        # Procédure tâche 2.1 avant 2.2 — pas de résolution sans constat terrain.
        self._assert_field_check_done(current)
        # BR-TRAITEMENT-PROGRESSIF-001 — pas de terminaison sans démarrage. Seul
        # `assigned` traduit un traitement jamais démarré : un ticket en attente
        # ou escaladé a, lui, bien été démarré auparavant, et reste résoluble.
        if current.request_status == "assigned":
            raise self.bad_request(
                "Démarrez le traitement avant de le terminer.",
                error_code=ErrorCode.INVALID_STATUS_TRANSITION,
            )
        # Transition de statut toujours validée, y compris pour admin (comportement
        # inchangé : BYPASS_TRANSITION_ROLES n'est jamais activé sur ce chemin).
        assert_transition_allowed(current.request_status, "resolved", actor_role=effective_role or None)

        previous_status = current.request_status
        cycle_number, started_at, ended_at, duration_seconds = await self._next_treatment_cycle(
            int(id), fallback_started_at=current.created_at
        )
        # BR-TRACE-001 — fige les métadonnées de l'intervention fermée par cette
        # résolution AVANT toute mise à jour du pointeur (jamais recalculées).
        intervention_meta = self._current_intervention_meta(current.infos)
        actor_identity = await self._actor_identity_snapshot(current.assignee_id)

        new_infos = dict(current.infos) if isinstance(current.infos, dict) else {}
        new_infos["current_intervention_id"] = None

        translated = await self._translate_codes({"request_status": "resolved"})
        require_guard = normalize_role(effective_role) not in _BYPASS_ROLES
        obj = await self._atomic_conditional_update(
            current,
            values={**translated, "resolved_at": ended_at, "in_triage": False, "infos": new_infos},
            require_current_assignee=require_guard,
            commit=False,
        )

        sla_snapshot = await self._sla_cycle_snapshot(
            int(id),
            sla_hours=int(current.sla_hours or 0),
            fallback_created_at=current.created_at,
            ended_at=ended_at,
            current_infos=current.infos,
        )

        wf_id_res = await self._get_or_create_workflow(int(id))
        await self.detail_repo.create_event({
            "workflow_id": wf_id_res,
            "event_type": "treatment_completed",
            "label": f"Traitement terminé — {clean_summary}",
            "actor_id": actor_id,
            "actor_name": actor_name,
            "activated": True,
            "infos": self._clean_infos({
                "event_status": "resolved",
                "source_role": actor_role,
                "actor_role": actor_role,
                "summary": clean_summary,
                "solution": clean_solution,
                "work_done": clean_work_done,
                "recommendations": clean_recommendations or None,
                "attachment_ids": [a["attachment_id"] for a in attachments] if attachments else None,
                "attachments": attachments or None,
                "old_status": previous_status,
                "new_status": "resolved",
                "previous_status": previous_status,
                "started_at": started_at.isoformat() if started_at else None,
                "ended_at": ended_at.isoformat(),
                "duration_seconds": duration_seconds,
                "cycle_number": cycle_number,
                # BR-SLA-REOPEN-001 — instantané gelé du cycle SLA clos par cette résolution.
                **sla_snapshot,
                # BR-TRACE-001 — intervention fermée par cette résolution (id/ordre/cycle
                # explicites, identité figée de l'intervenant).
                **intervention_meta,
                **actor_identity,
            }),
        }, commit=False)
        await emit_notif(
            self.session,
            recipient_id=getattr(obj, "requester_id", None),
            # Titre inchangé (« Ticket résolu ») : le délai de validation est
            # annoncé dans le corps, pas dans le titre.
            title="Ticket résolu",
            body=(
                f"Le traitement du ticket {obj.ref} est terminé. Résumé : {clean_summary} "
                f"Consultez la solution, puis confirmez la résolution ou rouvrez le ticket "
                f"si le problème persiste. "
                # BR-AUTO-VALIDATION-001 — le demandeur doit savoir dès maintenant
                # que son silence vaudra acceptation : la relance part à la
                # résolution, pas à l'approche de l'échéance.
                f"Sans réponse de votre part sous {AUTO_VALIDATION_DAYS} jours, "
                f"la résolution sera validée automatiquement."
            ),
            type="success",
            request_id=id,
            action_label="Confirmer la résolution",
            action_url=f"/app/requests/{id}",
            commit=False,
        )
        await emit_event(AppEvent(type="request.resolved", payload={"id": id}, target={"roles": "all"}))
        return obj

    async def list_transmit_targets(self, id: str, *, actor) -> dict:
        """Destinataires autorisés pour « Transmettre le traitement ».

        BR-TRANSMIT-SCOPE-TECH-001 — un technicien ne choisit pas librement dans
        l'organisation : il ne peut transmettre qu'à ses collègues techniciens du
        MÊME service, ou remonter au responsable qui lui a distribué ce ticket
        (`distributor_id` — le chef de division dans le circuit de distribution).
        Le chef de service n'est donc pas une cible possible pour lui.

        Les autres rôles traitants gardent l'annuaire libre : `restricted=False`,
        et le client conserve ses filtres direction/département/service.

        Une seule source de vérité : cette méthode alimente la liste affichée ET
        le contrôle de `transmit_treatment()`. Masquer des champs côté client ne
        protège rien — l'API resterait appelable directement.
        """
        from api.repositories.RepositoryAccount import AccountRepository

        current = await self.repo.get_by_id(id)
        if current is None:
            raise self.not_found("Cette demande n'existe pas.", error_code=ErrorCode.REQUEST_NOT_FOUND)

        if normalize_role(getattr(actor, "role", "")) != "technicien":
            return {"restricted": False, "items": []}

        acc_repo = AccountRepository(self.session)
        allowed: dict[int, Any] = {}

        # 1. Collègues techniciens du même service (hors soi-même).
        if getattr(actor, "unity_id", None) is not None:
            peers, _ = await acc_repo.list(
                filters={"role": "technicien", "unity_id": actor.unity_id},
                only_active=True,
                limit=200,
            )
            for peer in peers:
                if int(peer.id) != int(actor.id):
                    allowed[int(peer.id)] = peer

        # 2. Sa sortie vers le haut : le chef de division.
        #
        # En priorité celui qui lui a distribué CE ticket. À défaut — ticket reçu
        # par transmission directe, sans passer par la file Distribution, donc
        # sans `distributor_id` — les chefs de division de son service. Sans ce
        # repli, un technicien dans ce cas n'aurait AUCUNE cible hiérarchique et
        # ne pourrait plus faire remonter le ticket : il resterait bloqué avec.
        distributor_id = getattr(current, "distributor_id", None)
        if distributor_id is not None and int(distributor_id) != int(actor.id):
            distributor = await acc_repo.get_by_id(int(distributor_id))
            if distributor is not None and distributor.status is True:
                allowed[int(distributor.id)] = distributor
        elif getattr(actor, "unity_id", None) is not None:
            chiefs, _ = await acc_repo.list(
                filters={"role": "chef-division-support", "unity_id": actor.unity_id},
                only_active=True,
                limit=50,
            )
            for chief in chiefs:
                if int(chief.id) != int(actor.id):
                    allowed[int(chief.id)] = chief

        items = [
            {
                "id": str(acc.id),
                "name": self._account_display_name(acc),
                # « Badge » au sens du formulaire : le matricule du personnel.
                "matricule": getattr(acc, "matricule", None),
                "role": normalize_role(acc.role),
                # Trié en tête : la voie de remontée hiérarchique, qu'elle vienne
                # du distributeur de ce ticket ou du repli sur le service.
                "is_distributor": (
                    int(acc.id) == int(distributor_id) if distributor_id
                    else normalize_role(acc.role) == "chef-division-support"
                ),
            }
            for acc in allowed.values()
        ]
        # Le responsable d'abord (remontée hiérarchique), puis les pairs par nom.
        items.sort(key=lambda it: (not it["is_distributor"], (it["name"] or "").lower()))
        return {"restricted": True, "items": items}

    async def _assert_transmit_target_in_scope(self, current, actor, target) -> None:
        """Verrou serveur de BR-TRANSMIT-SCOPE-TECH-001 (voir list_transmit_targets)."""
        if actor is None or normalize_role(getattr(actor, "role", "")) != "technicien":
            return

        allowed_ids = {
            int(it["id"]) for it in (await self.list_transmit_targets(str(current.id), actor=actor))["items"]
        }
        if int(target.id) not in allowed_ids:
            raise self.forbidden(
                "En tant que technicien, vous ne pouvez transmettre qu'à un technicien "
                "de votre service ou au responsable qui vous a confié ce ticket.",
                hint="Choisissez un destinataire dans la liste proposée.",
            )

    async def transmit_treatment(
        self,
        id: str,
        *,
        to_user_id: str,
        work_done: str,
        reason: str,
        instruction: Optional[str] = None,
        attachments: Optional[list[dict]] = None,
        actor_id: Optional[str] = None,
        actor_name: Optional[str] = None,
        actor_role: Optional[str] = None,
        actor=None,
    ):
        """
        BR-TRANSMIT-001 — "Transmettre le traitement". Le nombre, l'ordre et les rôles
        des intervenants ne sont jamais connus à l'avance : le prochain intervenant est
        choisi librement dans tout l'annuaire (aucune restriction de direction/service),
        sous réserve d'être actif et de porter un rôle traitant. Le ticket reste dans son
        statut actif courant (jamais forcé à `assigned`) — seul assignee_id change.
        Ne construit jamais de chaîne fixe : chaque transmission crée un seul événement
        `treatment_transmitted`, jamais un circuit complet (voir create_circuit, non
        réutilisé ici — chaîne prédéfinie, incompatible avec ce workflow dynamique).
        """
        from api.repositories.RepositoryAccount import AccountRepository

        clean_work_done = work_done.strip() if isinstance(work_done, str) else ""
        clean_reason = reason.strip() if isinstance(reason, str) else ""
        if not clean_work_done:
            raise self.bad_request("Le travail effectué est obligatoire.", error_code=ErrorCode.MISSING_REQUIRED_FIELD)
        if not clean_reason:
            raise self.bad_request("Le motif est obligatoire.", error_code=ErrorCode.MISSING_REQUIRED_FIELD)
        clean_instruction = instruction.strip() if isinstance(instruction, str) else ""

        effective_role = str(getattr(actor, "role", actor_role or "") or "")
        if effective_role:
            assert_action_allowed(effective_role, "transmit_treatment")

        current = await self.get_by_id(id)
        if actor is not None:
            assert_is_current_handler(actor, current)

        try:
            target_id_int = int(to_user_id)
        except (TypeError, ValueError):
            raise self.bad_request("Identifiant de destinataire invalide.", error_code=ErrorCode.VALIDATION_ERROR)

        acc_repo = AccountRepository(self.session)
        target = await acc_repo.get_by_id(target_id_int)
        if target is None:
            raise self.not_found("Ce destinataire n'existe pas.", error_code=ErrorCode.ACCOUNT_NOT_FOUND)
        if target.status is not True:
            raise self.bad_request("Ce destinataire est inactif.", error_code=ErrorCode.INVALID_FIELD_VALUE)
        target_role = normalize_role(target.role)
        if target_role not in TREATING_ROLES:
            raise self.bad_request(
                "Ce destinataire n'a pas un rôle de traitement autorisé.",
                error_code=ErrorCode.INVALID_FIELD_VALUE,
            )
        await self._assert_transmit_target_in_scope(current, actor, target)
        assert_requester_is_not_handler(current, target_id_int)
        target_name = self._account_display_name(target)

        previous_assignee_id = current.assignee_id
        cycle_number, started_at, ended_at, duration_seconds = await self._next_treatment_cycle(
            int(id), fallback_started_at=current.created_at
        )
        # BR-TRACE-001 — fige l'intervention fermée par cette transmission (celle de
        # l'émetteur), puis ouvre la nouvelle intervention du destinataire.
        closing_meta = self._current_intervention_meta(current.infos)
        closing_identity = await self._actor_identity_snapshot(previous_assignee_id)
        new_infos, opening_meta = await self._open_intervention(current.infos, target_id_int, id)

        require_guard = normalize_role(effective_role) not in _BYPASS_ROLES
        obj = await self._atomic_conditional_update(
            current,
            values={"assignee_id": target_id_int, "in_triage": False, "infos": new_infos},
            require_current_assignee=require_guard,
            commit=False,
        )

        wf_id = await self._get_or_create_workflow(int(id))
        await self.detail_repo.create_event({
            "workflow_id": wf_id,
            "event_type": "treatment_transmitted",
            "label": f"Traitement transmis à {target_name or to_user_id}",
            "actor_id": actor_id,
            "actor_name": actor_name,
            "dest_id": target_id_int,
            "comment": clean_reason,
            "activated": True,
            "infos": self._clean_infos({
                "source_role": actor_role,
                "actor_role": actor_role,
                "dest_role": target_role,
                "target_role": target_role,
                "target_user_id": str(target_id_int),
                "target_user_name": target_name,
                "work_done": clean_work_done,
                "reason": clean_reason,
                "instruction": clean_instruction or None,
                "attachment_ids": [a["attachment_id"] for a in attachments] if attachments else None,
                "attachments": attachments or None,
                "previous_assignee_id": previous_assignee_id,
                "new_assignee_id": target_id_int,
                "old_status": current.request_status,
                "new_status": current.request_status,
                "started_at": started_at.isoformat() if started_at else None,
                "ended_at": ended_at.isoformat(),
                "duration_seconds": duration_seconds,
                "cycle_number": cycle_number,
                # BR-TRACE-001 — intervention fermée (émetteur) : id/ordre/cycle explicites
                # + identité figée. `next_intervention` référence et décrit entièrement
                # l'intervention ouverte pour le destinataire — cette transmission est le
                # seul événement qui marque son début (aucun événement `assigned` séparé
                # n'est créé pour une transmission), donc la seule source disponible pour
                # que cette nouvelle intervention soit malgré tout retrouvable même si le
                # destinataire n'a encore rien fait sur le ticket.
                **closing_meta,
                **closing_identity,
                "next_intervention": {**opening_meta, "started_at": ended_at.isoformat()},
            }),
        }, commit=False)

        await emit_notif(
            self.session,
            recipient_id=str(target_id_int),
            title="Ticket transmis",
            body=(
                f"{actor_name or 'Un intervenant'} vous a transmis le ticket {obj.ref}. "
                f"Consultez le travail déjà effectué et poursuivez le traitement. Motif : {clean_reason}"
            ),
            type="info",
            request_id=id,
            action_label="Voir le ticket",
            action_url=f"/app/requests/{id}",
            commit=False,
        )
        # BR-NOTIFICATION-WORKFLOW-001 §8 — confirmation légère App-only à l'émetteur
        # (previous_assignee_id = l'acteur lui-même) : pas d'email, pas de détails
        # internes, juste l'accusé que la transmission a bien eu lieu.
        if previous_assignee_id and not self._same_account(previous_assignee_id, target_id_int):
            await emit_notif(
                self.session,
                recipient_id=str(previous_assignee_id),
                title="Ticket transmis",
                body=f"Ticket {obj.ref} transmis à {target_name or target_id_int}.",
                type="info",
                request_id=id,
                action_label="Voir le ticket",
                action_url=f"/app/requests/{id}",
                send_email=False,
                commit=False,
            )
        await emit_event(AppEvent(
            type="request.transmitted",
            payload={"id": id, "assignee_id": target_id_int},
            target={"roles": "all"},
        ))
        return obj

    async def reopen(
        self,
        id: str,
        *,
        actor_id: Optional[str] = None,
        actor_name: Optional[str] = None,
        actor_role: Optional[str] = None,
        actor=None,
        reason: str,
    ):
        """
        BR-REOPEN-QUEUE-001 (révision — réouverture immédiate) : le demandeur réouvre
        son ticket lui-même, sans approbation hiérarchique. Motif obligatoire. Le
        ticket retourne directement dans la File d'attente (`assignee_id=None`,
        `in_triage=True`) pour un nouveau cycle de traitement entièrement dynamique —
        aucun intervenant n'est connu à l'avance (BR-REQUESTER-NO-SELF-TREATMENT-001 :
        le demandeur ne redevient jamais lui-même intervenant).

        L'ancien mécanisme en deux phases (`request_reopen` → approbation chef/
        directeur/admin → `reopen`) est supprimé : il n'existe plus qu'un seul
        comportement métier officiel de réouverture.
        """
        obj = await self.get_by_id(id)
        effective_actor_role = actor_role or getattr(actor, "role", None) or "user"
        if actor is not None:
            await self._guard_ticket_action(
                id,
                "reopen",
                target_status="reopened",
                actor=actor,
                actor_role=effective_actor_role,
            )

        translated_status = (obj.request_status or "").lower()
        if translated_status not in ("resolved", "rejected", "closed"):
            raise self.bad_request(
                "La réouverture n'est possible que sur un ticket à l'état RESOLVED, REJECTED ou CLOSED.",
                error_code=ErrorCode.INVALID_STATUS_TRANSITION,
            )

        # Fenêtre de 7 jours pour rouvrir un ticket fermé automatiquement
        if translated_status == "closed" and obj.closed_at:
            from datetime import timedelta
            deadline = obj.closed_at + timedelta(days=7)
            if datetime.now(timezone.utc).replace(tzinfo=None) > deadline:
                raise self.bad_request(
                    "La fenêtre de réouverture (7 jours après fermeture) est expirée. Créez une nouvelle demande.",
                    error_code=ErrorCode.INVALID_STATUS_TRANSITION,
                )

        clean_reason = reason.strip() if isinstance(reason, str) else ""
        if not clean_reason:
            raise self.bad_request(
                "Un motif est obligatoire pour réouvrir un ticket.",
                field="reason",
            )

        # Historique des cycles déjà écoulés — uniquement pour numéroter le nouveau
        # cycle dans l'événement `reopened` (jamais pour recalculer/modifier les
        # cycles passés, qui restent figés dans workflow_detail, append-only).
        past_events = await self.detail_repo.list_by_request(str(id))
        previous_cycle_number = sum(
            1 for e in past_events if e.event_type in ("treatment_transmitted", "treatment_completed")
        )

        previous_assignee_id = obj.assignee_id
        previous_status = obj.request_status
        current_infos = dict(obj.infos) if isinstance(obj.infos, dict) else {}
        # BR-NOTIFICATION-WORKFLOW-001 §14/§15 — nouveau cycle SLA indépendant
        # (BR-SLA-REOPEN-001) : le flag anti-répétition de l'alerte préventive doit
        # repartir à zéro pour ce nouveau cycle, sinon `warn_sla_approaching()` ne
        # préviendrait plus jamais le nouvel intervenant.
        current_infos.pop("sla_warning_sent_at", None)
        # BR-TRACE-001 — nouveau cycle d'intervention explicitement enregistré (jamais
        # recalculé) : incrémente le compteur de cycle et remet l'ordre des interventions
        # à zéro, pour que la première intervention du nouveau cycle reparte à 1.
        next_sla_cycle_number = int(current_infos.get("sla_cycle_number") or 1) + 1
        current_infos["sla_cycle_number"] = next_sla_cycle_number
        current_infos["intervention_order_in_cycle"] = 0
        current_infos["current_intervention_id"] = None
        translated = await self._translate_codes({"request_status": "reopened"})
        updated = await self.repo.update(id, {
            **translated,
            "infos": current_infos,
            "assignee_id": None,
            "in_triage": True,
            # BR-SLA-REOPEN-001 — nouveau cycle SLA : les indicateurs "live" (utilisés
            # par l'escalade auto SLA) repartent de zéro à partir de cette réouverture,
            # sans jamais toucher le cycle précédent déjà gelé dans l'événement
            # `treatment_completed` correspondant. Sans ce reset, `sla_breached` resterait
            # à True après une réouverture (le scheduler ne le remet jamais à False) et
            # déclencherait une escalade automatique immédiate et injustifiée du nouveau cycle.
            "sla_breached": False,
            "sla_elapsed": 0,
        }, commit=False)
        if updated is None:
            raise self.not_found("Cette demande n'existe pas.", error_code=ErrorCode.REQUEST_NOT_FOUND)

        reopened_at = datetime.now(timezone.utc).replace(tzinfo=None)
        wf_id = await self._get_or_create_workflow(int(id))
        await self.detail_repo.create_event({
            "workflow_id": wf_id,
            "event_type": "reopened",
            "label": f"Ticket réouvert — {clean_reason}",
            "actor_id": actor_id,
            "actor_name": actor_name,
            "comment": clean_reason,
            "activated": True,
            "infos": self._clean_infos({
                "source": "reopen_immediate",
                "source_role": actor_role,
                "actor_role": actor_role,
                "requester_id": str(obj.requester_id) if obj.requester_id else None,
                "previous_status": previous_status,
                "new_status": "reopened",
                "old_status": previous_status,
                "new_status_full": "reopened",
                "previous_assignee_id": previous_assignee_id,
                "new_assignee_id": None,
                "reopen_reason": clean_reason,
                # BR-REOPEN-QUEUE-001 (révision) — plus d'approbation distincte :
                # celui qui demande et celui qui déclenche la réouverture sont
                # toujours la même personne (le demandeur).
                "reopen_requested_by": str(actor_id) if actor_id else None,
                "reopen_approved_by": str(actor_id) if actor_id else None,
                "reopened_at": reopened_at.isoformat(),
                "previous_cycle_number": previous_cycle_number,
                "next_cycle_number": previous_cycle_number + 1,
                # BR-TRACE-001 — cycle d'intervention explicitement ouvert par cette
                # réouverture (distinct de next_cycle_number ci-dessus, qui compte les
                # transmissions/résolutions globales — voir note terminologique BR-TRACE-001).
                "intervention_cycle_number": next_sla_cycle_number,
            }),
        }, commit=False)

        # Notifie le requérant — confirmation, ticket remis en file d'attente pour un
        # nouveau cycle. App + Email (défaut) : événement important/actionnable.
        if obj.requester_id:
            await emit_notif(
                self.session,
                recipient_id=str(obj.requester_id),
                title="Ticket réouvert",
                body=f"Votre ticket {obj.ref} a été réouvert et replacé dans la File d'attente pour un nouveau cycle de traitement.",
                type="info",
                request_id=id,
                action_label="Voir le ticket",
                action_url=f"/app/requests/{id}",
                commit=False,
            )

        # BR-NOTIF-001 : jamais d'affectation automatique — l'ancien intervenant n'est
        # informé qu'à titre indicatif (App-only, il ne redevient jamais assignee_id
        # ici) — BR-REQUESTER-NO-SELF-TREATMENT-001 : le demandeur ne devient jamais
        # intervenant de son propre ticket, donc previous_assignee_id != requester_id.
        notified_ids = {str(obj.requester_id)} if obj.requester_id else set()
        if previous_assignee_id and str(previous_assignee_id) not in notified_ids:
            await emit_notif(
                self.session,
                recipient_id=str(previous_assignee_id),
                title="Ticket réouvert",
                body=f"Le ticket {obj.ref} sur lequel vous êtes intervenu a été réouvert.",
                type="warning",
                request_id=id,
                action_label="Voir le ticket",
                action_url=f"/app/requests/{id}",
                send_email=False,
                commit=False,
            )
            notified_ids.add(str(previous_assignee_id))
        if obj.unity_id:
            from api.repositories.RepositoryAccount import AccountRepository

            acc_repo = AccountRepository(self.session)
            chief = await acc_repo.find_chief_for_unity(obj.unity_id)
            if chief and str(chief.id) not in notified_ids:
                await emit_notif(
                    self.session,
                    recipient_id=str(chief.id),
                    title="Ticket réouvert — File d'attente",
                    body=f"Le ticket {obj.ref} a été réouvert et replacé dans la File d'attente ; une nouvelle prise en charge est nécessaire.",
                    type="warning",
                    request_id=id,
                    action_label="Voir la file d'attente",
                    action_url="/app/queue",
                    send_email=False,
                    commit=False,
                )

        await emit_event(AppEvent(type="request.reopened", payload={"id": id}, target={"roles": "all"}))
        fresh = await self.repo.get_by_id(int(id))
        return fresh if fresh else updated

    async def cancel(
        self,
        id: str,
        *,
        actor_id: Optional[str] = None,
        actor_name: Optional[str] = None,
        actor_role: Optional[str] = None,
        actor=None,
        reason: Optional[str] = None,
    ):
        clean_reason = reason.strip() if isinstance(reason, str) else ""
        if not clean_reason:
            raise self.bad_request(
                "Un motif est obligatoire pour annuler une demande.",
                field="reason",
            )

        current = await self._guard_ticket_action(
            id,
            "cancel",
            target_status="cancelled",
            actor=actor,
            actor_role=actor_role,
        )
        translated = await self._translate_codes({"request_status": "cancelled"})
        patch: dict[str, Any] = dict(translated)
        existing = await self.repo.get_by_id(int(id))
        existing_infos = (existing.infos or {}) if existing else {}
        patch["infos"] = {**existing_infos, "cancel_reason": clean_reason}
        obj = await self.repo.update(id, patch, commit=False)
        if obj is None:
            raise self.not_found("Cette demande n'existe pas.", error_code=ErrorCode.REQUEST_NOT_FOUND)
        wf_id_cancel = await self._get_or_create_workflow(int(id))
        await self.detail_repo.create_event({
            "workflow_id": wf_id_cancel,
            "event_type": "cancelled",
            "label": f"Demande annulée — {clean_reason}",
            "actor_id": actor_id,
            "actor_name": actor_name,
            "comment": clean_reason,
            "activated": True,
            "infos": self._clean_infos({
                "event_status": "cancelled",
                "source_role": actor_role,
                "actor_role": actor_role,
                "old_status": current.request_status,
                "new_status": "cancelled",
                "reason": clean_reason,
            }),
        }, commit=False)
        # BR-NOTIFICATION-WORKFLOW-001 §20/§22 — annulation absente de la liste des
        # événements "email important" pour le porteur actuel (qui doit surtout
        # savoir qu'il doit arrêter, in-app suffit). Le demandeur, lui, reçoit un
        # email de confirmation de son annulation.
        if obj.requester_id:
            await emit_notif(
                self.session,
                recipient_id=str(obj.requester_id),
                title="Ticket annulé",
                body=f"Votre ticket {obj.ref} a été annulé : {clean_reason}",
                type="warning",
                request_id=id,
                action_label="Voir le ticket",
                action_url=f"/app/requests/{id}",
                send_email=True,
                commit=False,
            )
        if obj.assignee_id and not self._same_account(obj.assignee_id, obj.requester_id):
            await emit_notif(
                self.session,
                recipient_id=str(obj.assignee_id),
                title="Ticket annulé",
                body=f"Le ticket {obj.ref} qui vous était assigné a été annulé : {clean_reason}. Vous ne devez plus poursuivre le traitement.",
                type="warning",
                request_id=id,
                action_label="Voir le ticket",
                action_url=f"/app/requests/{id}",
                send_email=False,
                commit=False,
            )
        await emit_event(AppEvent(type="request.cancelled", payload={"id": id}, target={"roles": "all"}))
        return obj

    async def reassign_service(
        self,
        id: str,
        target_unity_id: int,
        *,
        actor_id: Optional[str] = None,
        actor_name: Optional[str] = None,
        actor_role: Optional[str] = None,
        actor=None,
        reason: Optional[str] = None,
    ):
        """
        Réaffectation vers un autre service (action chef).

        Trouve le chef du service cible, crée un événement reassigned_service,
        met à jour la demande (unity_id, assignee_id, status=assigned).
        """
        from api.repositories.RepositoryAccount import AccountRepository

        clean_reason = reason.strip() if isinstance(reason, str) else ""
        obj = await self._guard_ticket_action(
            id,
            "reassign",
            target_status="assigned",
            actor=actor,
            actor_role=actor_role,
        )
        target_row = await self.session.execute(
            select(Unity.id, Unity.parent_direction_id, Unity.label)
            .where(Unity.id == int(target_unity_id), Unity.deleted_at.is_(None))
        )
        target_unity = target_row.first()
        if target_unity is None:
            raise self.not_found("Service cible introuvable.", error_code=ErrorCode.UNIT_NOT_FOUND)

        target_unity_db_id, target_parent_direction_id, target_label = target_unity
        target_direction_id = target_parent_direction_id or target_unity_db_id
        # La direction de l'acteur n'etait resolue que pour `chief-departement`,
        # role retire le 2026-09-25 : l'action est desormais reservee a l'admin,
        # qui a un perimetre global.
        actor_direction_id = None

        if actor is not None:
            assert_service_reassignment_allowed(
                actor,
                obj,
                target_unity_id,
                target_direction_id=target_direction_id,
                actor_direction_id=actor_direction_id,
                reason=clean_reason,
            )

        if obj.unity_id is not None and int(obj.unity_id) == int(target_unity_id):
            raise self.bad_request(
                "Ce ticket est déjà affecté à ce service.",
                error_code=ErrorCode.INVALID_STATUS_TRANSITION,
            )
        previous_assignee_id = obj.assignee_id
        wf_id = await self._get_or_create_workflow(int(id))
        acc_repo = AccountRepository(self.session)
        chief = await acc_repo.find_chief_for_unity(target_unity_id)
        # BR-REQUESTER-NO-SELF-TREATMENT-001 — le chef du service cible ne peut pas
        # devenir intervenant s'il est le demandeur de ce ticket ; traité comme
        # "aucun chef trouvé" (même repli que le cas chief=None déjà géré ci-dessous).
        if chief is not None and str(chief.id) == str(obj.requester_id):
            chief = None

        await self.detail_repo.create_event({
            "workflow_id": wf_id,
            "event_type": "reassigned_service",
            "label": f"Réaffecté vers {target_label or 'un autre service'}{' — ' + clean_reason if clean_reason else ''}",
            "actor_id": actor_id,
            "actor_name": actor_name,
            "dest_id": chief.id if chief else None,
            "unity_id": target_unity_id,
            "comment": clean_reason or None,
            "activated": True,
            "infos": self._clean_infos({
                "event_status": "pending_validation",
                "source_role": actor_role,
                "actor_role": actor_role,
                "dest_role": getattr(chief, "role", None) or "chief-service",
                "target_role": getattr(chief, "role", None) or "chief-service",
                "target_user_id": str(chief.id) if chief else None,
                "target_user_name": self._account_display_name(chief) if chief else None,
                "previous_unity_id": obj.unity_id,
                "target_unity_id": target_unity_id,
                "target_direction_id": target_direction_id,
                "old_status": obj.request_status,
                "new_status": "assigned",
                "old_assignee_id": obj.assignee_id,
                "new_assignee_id": chief.id if chief else None,
                "reason": clean_reason or None,
            }),
        }, commit=False)

        status_translated = await self._translate_codes({"request_status": "assigned"})
        await self.repo.update(id, {
            "unity_id": target_unity_id,
            "assignee_id": chief.id if chief else None,
            "in_triage": False,
            **status_translated,
        }, commit=False)

        # Lot finition §4 — règle globale : la responsabilité actuelle détermine les
        # notifications opérationnelles. Nouveau responsable (chef cible) : App+Email
        # (déjà en place). Demandeur : App-only (réorientation informative, pas une
        # action de sa part). Ancien responsable : App-only, uniquement s'il perd
        # réellement la responsabilité (assignee_id changé). Anciens intervenants
        # historiques (workflow_detail) : jamais notifiés — historique ≠ abonnement.
        notified_ids: set[str] = set()
        if chief:
            await emit_notif(
                self.session,
                recipient_id=str(chief.id),
                title="Ticket réaffecté vers votre service",
                body=f"Le ticket {obj.ref} a été réaffecté à votre service et nécessite une prise en charge.",
                type="info",
                request_id=id,
                action_label="Voir le ticket",
                action_url=f"/app/requests/{id}",
                commit=False,
            )
            notified_ids.add(str(chief.id))
        if obj.requester_id:
            await emit_notif(
                self.session,
                recipient_id=str(obj.requester_id),
                title="Ticket réaffecté",
                body=f"Votre ticket {obj.ref} a été réorienté vers un autre service pour poursuivre son traitement.",
                type="info",
                request_id=id,
                action_label="Voir le ticket",
                action_url=f"/app/requests/{id}",
                send_email=False,
                commit=False,
            )
            notified_ids.add(str(obj.requester_id))
        if previous_assignee_id and str(previous_assignee_id) not in notified_ids:
            await emit_notif(
                self.session,
                recipient_id=str(previous_assignee_id),
                title="Ticket réaffecté",
                body=f"Le ticket {obj.ref} a été réaffecté vers un autre service.",
                type="info",
                request_id=id,
                action_label="Voir le ticket",
                action_url=f"/app/requests/{id}",
                send_email=False,
                commit=False,
            )

        await emit_event(AppEvent(
            type="request.reassigned",
            payload={"id": id, "unity_id": target_unity_id},
            target={"roles": "all"},
        ))

        fresh = await self.repo.get_by_id(int(id))
        return fresh if fresh else obj

    async def transfer_direction(
        self,
        id: str,
        target_direction_id: int,
        *,
        actor_id: Optional[str] = None,
        actor_name: Optional[str] = None,
        actor_role: Optional[str] = None,
        actor=None,
        reason: Optional[str] = None,
    ):
        """
        Transfert inter-direction.

        Le directeur source sort le ticket de son périmètre quand aucun service
        de sa direction ne peut le traiter. Le ticket entre alors dans la
        direction cible comme une demande à qualifier, sans assignation directe.
        """
        from api.repositories.RepositoryAccount import AccountRepository

        clean_reason = reason.strip() if isinstance(reason, str) else ""
        if not clean_reason:
            raise self.bad_request(
                "Un motif est obligatoire pour transférer une demande vers une autre direction.",
                field="reason",
            )

        obj = await self._guard_ticket_action(
            id,
            "transfer_direction",
            actor=actor,
            actor_role=actor_role,
        )

        if normalize_status(obj.request_status) in TERMINAL_STATUSES:
            raise self.bad_request(
                "Un ticket finalisé ne peut pas être transféré vers une autre direction.",
                error_code=ErrorCode.INVALID_STATUS_TRANSITION,
            )
        assert_transition_allowed(obj.request_status, "qualifying", actor_role=actor_role)

        try:
            target_direction_int = int(target_direction_id)
        except (TypeError, ValueError):
            raise self.bad_request("Direction cible invalide.", field="target_direction_id")

        target_row = await self.session.execute(
            select(Unity.id, Unity.parent_direction_id, Unity.label)
            .where(Unity.id == target_direction_int, Unity.deleted_at.is_(None))
        )
        target_direction = target_row.first()
        if target_direction is None:
            raise self.not_found("Direction cible introuvable.", error_code=ErrorCode.UNIT_NOT_FOUND)

        target_direction_db_id, target_parent_direction_id, target_label = target_direction
        if target_parent_direction_id is not None:
            raise self.bad_request(
                "La cible doit être une direction, pas un service.",
                field="target_direction_id",
            )

        source_direction_id = obj.direction_id or obj.unity_id
        if source_direction_id is not None and int(source_direction_id) == int(target_direction_db_id):
            raise self.bad_request(
                "Ce ticket est déjà dans cette direction.",
                error_code=ErrorCode.INVALID_STATUS_TRANSITION,
            )

        previous_assignee_id = obj.assignee_id
        wf_id = await self._get_or_create_workflow(int(id))
        acc_repo = AccountRepository(self.session)
        # Le role `director` a ete retire le 2026-09-25 : cette recherche
        # renvoie toujours une liste vide, le transfert de direction ne notifie
        # donc plus personne nominativement. La variable est conservee car
        # l'evenement et les notifications traitent deja le cas `None`.
        target_directors = await acc_repo.find_directors_by_direction(int(target_direction_db_id))
        first_director = target_directors[0] if target_directors else None

        await self.detail_repo.create_event({
            "workflow_id": wf_id,
            "event_type": "transferred_direction",
            "label": f"Transféré vers {target_label or 'une autre direction'} — {clean_reason}",
            "actor_id": actor_id,
            "actor_name": actor_name,
            "dest_id": first_director.id if first_director else None,
            "unity_id": target_direction_db_id,
            "comment": clean_reason,
            "activated": True,
            "infos": self._clean_infos({
                "event_status": "qualifying",
                "source_role": actor_role,
                "actor_role": actor_role,
                "dest_role": None,
                "target_role": None,
                "target_user_id": str(first_director.id) if first_director else None,
                "target_user_name": self._account_display_name(first_director) if first_director else None,
                "previous_direction_id": source_direction_id,
                "target_direction_id": target_direction_db_id,
                "target_direction_name": target_label,
                "previous_unity_id": obj.unity_id,
                "target_unity_id": target_direction_db_id,
                "old_status": obj.request_status,
                "new_status": "qualifying",
                "old_assignee_id": obj.assignee_id,
                "new_assignee_id": None,
                "reason": clean_reason,
            }),
        }, commit=False)

        status_translated = await self._translate_codes({"request_status": "qualifying"})
        existing_infos = dict(obj.infos) if isinstance(obj.infos, dict) else {}
        existing_infos.update({
            "last_transfer_reason": clean_reason,
            "last_transfer_from_direction_id": source_direction_id,
            "last_transfer_to_direction_id": target_direction_db_id,
        })
        await self.repo.update(id, {
            "unity_id": target_direction_db_id,
            "assignee_id": None,
            "in_triage": False,
            "infos": existing_infos,
            **status_translated,
        }, commit=False)

        # Lot finition §4 — même principe que reassign_service : responsabilité
        # actuelle → notifications. Nouveau directeur cible : App+Email (déjà en
        # place). Demandeur : App-only. Ancien responsable : App-only, uniquement
        # s'il perd réellement la responsabilité (assignee_id vidé par ce transfert).
        notified_ids: set[str] = set()
        if first_director:
            await emit_notif(
                self.session,
                recipient_id=str(first_director.id),
                title="Ticket transféré vers votre direction",
                body=f"Le ticket {obj.ref} a été transféré vers votre direction et nécessite une prise en charge.",
                type="info",
                request_id=id,
                action_label="Voir le ticket",
                action_url=f"/app/requests/{id}",
                commit=False,
            )
            notified_ids.add(str(first_director.id))
        if obj.requester_id:
            await emit_notif(
                self.session,
                recipient_id=str(obj.requester_id),
                title="Ticket transféré",
                body=f"Votre ticket {obj.ref} a été transféré vers une autre direction afin de poursuivre son traitement.",
                type="info",
                request_id=id,
                action_label="Voir le ticket",
                action_url=f"/app/requests/{id}",
                send_email=False,
                commit=False,
            )
            notified_ids.add(str(obj.requester_id))
        if previous_assignee_id and str(previous_assignee_id) not in notified_ids:
            await emit_notif(
                self.session,
                recipient_id=str(previous_assignee_id),
                title="Ticket transféré",
                body=f"Le ticket {obj.ref} a été transféré vers une autre direction.",
                type="info",
                request_id=id,
                action_label="Voir le ticket",
                action_url=f"/app/requests/{id}",
                send_email=False,
                commit=False,
            )

        await emit_event(AppEvent(
            type="request.transferred_direction",
            payload={
                "id": id,
                "from_direction_id": source_direction_id,
                "to_direction_id": target_direction_db_id,
            },
            target={"user_ids": [int(first_director.id)] if first_director else []},
        ))

        fresh = await self.repo.get_by_id(int(id))
        return fresh if fresh else obj

    async def change_priority(
        self,
        id: str,
        priority: str,
        *,
        actor_id: Optional[str] = None,
        actor_name: Optional[str] = None,
        actor_role: Optional[str] = None,
        actor=None,
    ):
        clean_priority = priority.strip().lower() if isinstance(priority, str) else ""
        if not clean_priority:
            raise self.bad_request("La priorité est obligatoire.", field="priority")

        obj = await self._guard_ticket_action(
            id,
            "change_priority",
            actor=actor,
            actor_role=actor_role,
        )
        if normalize_status(obj.request_status) in TERMINAL_STATUSES:
            raise self.bad_request(
                "La priorité d'un ticket finalisé ne peut pas être modifiée.",
                error_code=ErrorCode.INVALID_STATUS_TRANSITION,
            )

        priority_row = await self.session.execute(
            select(PriorityDefinition.id)
            .where(PriorityDefinition.slug == clean_priority)
            .where(PriorityDefinition.deleted_at.is_(None))
        )
        priority_id = priority_row.scalar_one_or_none()
        if priority_id is None:
            raise self.bad_request(
                "Priorité inconnue.",
                field="priority",
            )

        old_priority = obj.priority
        if old_priority == clean_priority:
            return obj

        updated = await self.repo.update(id, {"priority_definition_id": priority_id}, commit=False)
        if updated is None:
            raise self.not_found("Cette demande n'existe pas.", error_code=ErrorCode.REQUEST_NOT_FOUND)

        wf_id = await self._get_or_create_workflow(int(id))
        await self.detail_repo.create_event({
            "workflow_id": wf_id,
            "event_type": "priority_changed",
            "label": f"Priorité modifiée — {old_priority} → {clean_priority}",
            "actor_id": actor_id,
            "actor_name": actor_name,
            "activated": True,
            "infos": self._clean_infos({
                "event_status": obj.request_status,
                "actor_id": actor_id,
                "source_role": actor_role,
                "actor_role": actor_role,
                "target_user_id": "",
                "target_role": "",
                "old_status": obj.request_status,
                "new_status": obj.request_status,
                "reason": "Changement de priorité",
                "old_priority": old_priority,
                "new_priority": clean_priority,
            }),
        }, commit=False)
        await emit_event(AppEvent(
            type="request.priority_changed",
            payload={"id": id, "priority": clean_priority},
            target={"roles": "all"},
        ))

        fresh = await self.repo.get_by_id(int(id))
        return fresh if fresh else updated

    async def reject(
        self,
        id: str,
        *,
        actor_id: Optional[str] = None,
        actor_name: Optional[str] = None,
        actor_role: Optional[str] = None,
        actor=None,
        reason: Optional[str] = None,
    ):
        """
        Rejet de la demande par le chef de service (validation refusée).

        Crée l'événement rejected, passe le statut à 'rejected',
        notifie le requérant.
        """
        clean_reason = reason.strip() if isinstance(reason, str) else ""
        if not clean_reason:
            raise self.bad_request(
                "Un motif est obligatoire pour rejeter une demande.",
                field="reason",
            )

        obj = await self._guard_ticket_action(
            id,
            "reject",
            target_status="rejected",
            actor=actor,
            actor_role=actor_role,
        )
        wf_id = await self._get_or_create_workflow(int(id))

        status_translated = await self._translate_codes({"request_status": "rejected"})
        await self.repo.update(id, {
            **status_translated,
            "assignee_id": obj.requester_id,
        }, commit=False)

        await self.detail_repo.create_event({
            "workflow_id": wf_id,
            "event_type": "rejected",
            "label": f"Demande rejetée — {clean_reason}",
            "actor_id": actor_id,
            "actor_name": actor_name,
            "comment": clean_reason,
            "activated": True,
            "infos": self._clean_infos({
                "event_status": "rejected",
                "source_role": actor_role,
                "actor_role": actor_role,
                "dest_role": "user",
                "target_role": "user",
                "target_user_id": str(obj.requester_id) if obj.requester_id else None,
                "target_user_name": obj.requester_name,
                "old_status": obj.request_status,
                "new_status": "rejected",
                "reason": clean_reason,
            }),
        }, commit=False)

        if obj.requester_id:
            await emit_notif(
                self.session,
                recipient_id=str(obj.requester_id),
                title="Ticket rejeté",
                body=f"Le ticket {obj.ref} a été rejeté. Motif : {clean_reason}",
                type="warning",
                request_id=id,
                action_label="Voir le ticket",
                action_url=f"/app/requests/{id}",
                commit=False,
            )

        await emit_event(AppEvent(type="request.rejected", payload={"id": id}, target={"roles": "all"}))

        fresh = await self.repo.get_by_id(int(id))
        return fresh if fresh else obj

    async def list_by_unity(self, unity_id: str, *, page: int = 1, limit: int = 20):
        return await self.list_filtered(unit_id=unity_id, page=page, limit=limit)

    async def delete(self, id: str) -> bool:
        await self.get_by_id(id)
        return await self.repo.delete(id)

    async def delete_by_uuid(self, id: str, uuid: str) -> bool:
        """Suppression avec vérification uuid — pattern edgrh delete_uuid()."""
        req = await self.get_by_id(id)
        if str(req.uuid) != uuid:
            raise self.bad_request("UUID invalide pour cette demande.")
        return await self.repo.delete(id)

    async def restore(self, id: str):
        """Restauration soft-delete — pattern edgrh /restore/{id}."""
        ok = await self.repo.restore(int(id))
        if not ok:
            raise self.not_found("Demande introuvable ou non supprimée")
        return await self.repo.get_by_id(int(id))

    async def get_first_filtered(
        self,
        *,
        request_status: Optional[str] = None,
        unity_id: Optional[str] = None,
        assignee_id: Optional[str] = None,
        requester_id: Optional[str] = None,
        is_external: Optional[bool] = None,
        in_triage: Optional[bool] = None,
        sla_breached: Optional[bool] = None,
        category: Optional[str] = None,
        priority: Optional[str] = None,
    ):
        """Retourne le PREMIER résultat filtré — pattern edgrh get_items()."""
        result = await self.list_filtered(
            request_status=request_status,
            unit_id=unity_id,
            assignee_id=assignee_id,
            requester_id=requester_id,
            is_external=is_external,
            in_triage=in_triage,
            sla_breached=sla_breached,
            page=1,
            limit=1,
        )
        items = result.get("items") or result.get("data") or []
        if not items:
            raise self.not_found("Aucune demande correspondant aux critères.")
        return items[0]

    async def count_by_status(self) -> dict[str, int]:
        return await self.repo.count_by_status()

    async def workload_by_unit(self, unity_ids: list[int]) -> list[dict[str, Any]]:
        """Charge actuelle (tickets non terminaux) par agent, pour le Centre de répartition."""
        counts = await self.repo.count_active_by_assignee(
            unity_ids, exclude_statuses=list(TERMINAL_STATUSES)
        )
        return [
            {"assignee_id": assignee_id, "active_count": count}
            for assignee_id, count in counts.items()
        ]

    async def search(self, q: str, *, page: int = 1, limit: int = 20):
        items, total = await self.repo.search(q, page=page, limit=limit)
        return self.paginate(self._serialize(items), total, page, limit)
