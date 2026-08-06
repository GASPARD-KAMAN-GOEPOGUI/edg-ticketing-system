from __future__ import annotations

from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import noload

from api.core.ticket_actions import STATUS_ALIASES, normalize_status
from api.models.ModelPriorityDefinition import PriorityDefinition
from api.models.ModelRequest import Request
from api.models.ModelRequestCategory import RequestCategory
from api.models.ModelRequestStatus import RequestStatus
from api.models.ModelUnity import Unity
from api.repositories.base_repository import BaseRepository

# RequestListItemResponse (schéma de liste) ne sérialise ni attachments/tasks
# (endpoints dédiés) ni timelines/appreciation (réservés à la page détail d'un
# ticket). Ces relations sont marquées lazy="selectin" au niveau du modèle pour
# les endpoints qui en ont besoin (détail), mais les charger sur CHAQUE requête
# de liste est un aller-retour DB (et un poids JSON) pur gaspillage.
_SKIP_UNUSED_RELS = [
    noload(Request.attachments),
    noload(Request.tasks),
    noload(Request.workflows),
    noload(Request.appreciation),
]


class RequestRepository(BaseRepository[Request]):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(Request, session)

    # ── Statuts par code ──────────────────────────────────────────────────────

    _INACTIVE_STATUSES: list[str] = ["resolved", "closed", "cancelled", "rejected"]
    _ACTIVE_STATUSES: list[str] = [
        "new", "qualifying", "qualified", "assigned",
        "in_progress", "pending", "escalated", "reopened",
    ]
    _QUALIFIABLE_STATUSES: list[str] = ["new", "qualifying", "qualified", "reopened"]

    # ── Surcharge _apply_filters : traduit code → subquery FK ─────────────────

    _CODE_FK_MAP: dict = {
        "request_status": (
            Request.request_status_id, RequestStatus, "code"
        ),
        "category": (
            Request.request_category_id, RequestCategory, "code"
        ),
        "priority": (
            Request.priority_definition_id, PriorityDefinition, "slug"
        ),
    }

    def _expand_status_codes(self, codes: list[str]) -> list[str]:
        expanded = {normalize_status(str(code)) for code in codes}
        for alias, canonical in STATUS_ALIASES.items():
            if canonical in expanded:
                expanded.add(alias)
        return sorted(expanded)

    def _apply_filters(self, stmt, filters: dict):
        filters = dict(filters)
        # Filtres plage de dates sur created_at
        date_from = filters.pop("date_from", None)
        date_to = filters.pop("date_to", None)
        exclude_request_status = filters.pop("exclude_request_status", None)
        unassigned_only = filters.pop("unassigned_only", None)
        if date_from:
            stmt = stmt.where(Request.created_at >= date_from)
        if date_to:
            stmt = stmt.where(Request.created_at <= date_to)
        if exclude_request_status:
            excluded_codes = (
                list(exclude_request_status)
                if isinstance(exclude_request_status, (list, tuple, set))
                else [s.strip() for s in str(exclude_request_status).split(",") if s.strip()]
            )
            stmt = stmt.where(Request.request_status_id.notin_(self._status_in_sub(excluded_codes)))
        if unassigned_only:
            stmt = stmt.where(Request.assignee_id.is_(None))

        regular: dict = {}
        for key, val in filters.items():
            if key in self._CODE_FK_MAP:
                fk_col, ref_model, code_attr = self._CODE_FK_MAP[key]
                ref_col = getattr(ref_model, code_attr)
                sub = select(ref_model.id).where(ref_model.deleted_at.is_(None))
                if isinstance(val, (list, tuple, set)):
                    if key == "request_status":
                        val = self._expand_status_codes([str(v) for v in val])
                    sub = sub.where(ref_col.in_(list(val)))
                    stmt = stmt.where(fk_col.in_(sub))
                else:
                    if key == "request_status":
                        stmt = stmt.where(
                            fk_col.in_(sub.where(ref_col.in_(self._expand_status_codes([str(val)]))))
                        )
                    else:
                        stmt = stmt.where(
                            fk_col == sub.where(ref_col == val).scalar_subquery()
                        )
            else:
                regular[key] = val
        return super()._apply_filters(stmt, regular)

    # ── Helpers subquery internes ──────────────────────────────────────────────

    def _status_in_sub(self, codes: list[str]):
        return (
            select(RequestStatus.id)
            .where(RequestStatus.code.in_(self._expand_status_codes(codes)))
            .where(RequestStatus.deleted_at.is_(None))
        )

    def _category_sub(self, code: str):
        return (
            select(RequestCategory.id)
            .where(RequestCategory.code == code)
            .where(RequestCategory.deleted_at.is_(None))
            .scalar_subquery()
        )

    # ── Méthodes de recherche / liste ─────────────────────────────────────────

    async def find_by_ref(self, ref: str) -> Request | None:
        return await self.get_one({"ref": ref})

    async def find_duplicate(
        self,
        *,
        title: str,
        category: str,
        requester_id: int | None,
        requester_email: str | None,
        meter_number: str | None,
    ) -> Request | None:
        """Retourne une demande active avec même titre + catégorie + demandeur."""
        title_clean = title.strip().lower()
        if not title_clean or not category:
            return None
        if requester_id is None and not requester_email and not meter_number:
            return None

        inactive_sub = self._status_in_sub(self._INACTIVE_STATUSES)
        cat_sub = self._category_sub(category)

        stmt = (
            select(self.model)
            .where(self.model.deleted_at.is_(None))
            .where(func.lower(self.model.title) == title_clean)
            .where(self.model.request_category_id == cat_sub)
            .where(self.model.request_status_id.notin_(inactive_sub))
        )

        if requester_id is not None:
            stmt = stmt.where(self.model.requester_id == requester_id)
        elif requester_email:
            stmt = stmt.where(
                func.lower(self.model.requester_email) == requester_email.strip().lower()
            )
        else:
            stmt = stmt.where(self.model.meter_number == meter_number.strip())

        result = await self.session.execute(stmt)
        return result.scalars().first()

    async def list_by_status(
        self, status_code: str, *, page: int = 1, limit: int = 20
    ) -> tuple[list[Request], int]:
        return await self.list(
            filters={"request_status": status_code},
            order_by="-created_at",
            page=page,
            limit=limit,
            load_options=_SKIP_UNUSED_RELS,
        )

    async def list_by_assignee(
        self,
        assignee_id: str,
        *,
        status_code: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[Request], int]:
        filters: dict = {"assignee_id": assignee_id}
        if status_code:
            filters["request_status"] = status_code
        return await self.list(
            filters=filters, order_by="-created_at", page=page, limit=limit,
            load_options=_SKIP_UNUSED_RELS,
        )

    async def list_by_direction(
        self, direction_id: str, *, page: int = 1, limit: int = 20
    ) -> tuple[list[Request], int]:
        _ids = await self._direction_unity_ids(direction_id)
        return await self.list(
            filters={"unity_id": _ids},
            order_by="-created_at",
            page=page,
            limit=limit,
            load_options=_SKIP_UNUSED_RELS,
        )

    async def _direction_unity_ids(self, direction_id: str | int) -> list[int]:
        root_id = int(direction_id)
        ids: list[int] = [root_id]

        from api.models.ModelOrganigram import Organigram as _Org

        org_row = await self.session.execute(
            select(_Org.id)
            .where(_Org.unity_id == root_id, _Org.deleted_at.is_(None))
            .limit(1)
        )
        org_id = org_row.scalar_one_or_none()
        if org_id:
            child_rows = await self.session.execute(
                select(_Org.unity_id)
                .where(_Org.parent_id == org_id, _Org.deleted_at.is_(None))
            )
            ids.extend(int(uid) for (uid,) in child_rows.all() if uid is not None)

        unity_rows = await self.session.execute(
            select(Unity.id)
            .where(Unity.parent_direction_id == root_id, Unity.deleted_at.is_(None))
        )
        ids.extend(int(uid) for (uid,) in unity_rows.all() if uid is not None)
        return sorted(set(ids))

    async def list_pending_triage(
        self, *, page: int = 1, limit: int = 20
    ) -> tuple[list[Request], int]:
        return await self.list(
            filters={
                "in_triage": True,
                "request_status": self._QUALIFIABLE_STATUSES,
            },
            order_by="-created_at",
            page=page,
            limit=limit,
            load_options=_SKIP_UNUSED_RELS,
        )

    async def list_sla_breached(
        self, *, page: int = 1, limit: int = 20
    ) -> tuple[list[Request], int]:
        return await self.list(
            filters={"sla_breached": True},
            order_by="-created_at",
            page=page,
            limit=limit,
            load_options=_SKIP_UNUSED_RELS,
        )

    async def list_transmitted_by_actor(
        self, actor_id: str, *, search: str | None = None, page: int = 1, limit: int = 20
    ) -> tuple[list[Request], int]:
        """
        BR-TRANSMIT-001 — tickets où `actor_id` a personnellement transmis le
        traitement (event_type='treatment_transmitted') à un moment de
        l'historique, indépendamment du porteur actuel ou du statut courant.

        L'émetteur ne vit que dans infos.actor_id (JSON) : create_event() écrit
        dest_id (destinataire) dans la colonne réelle agent_id quand dest_id est
        fourni, jamais l'émetteur (cf. RepositoryWorkflowDetail.create_event()).
        Un ticket peut avoir été transmis plusieurs fois par le même acteur
        (cycles différents) — dédupliqué ici (GROUP BY), classé par la
        transmission la plus récente. Même style de requête JSON brute déjà
        utilisé par ServiceStats.py (escalation_stats/global_kpis).
        """
        params = {"actor_id": str(actor_id)}
        search_clause = ""
        if search and search.strip():
            params["search_like"] = f"%{search.strip().lower()}%"
            search_clause = """
                  AND (
                    LOWER(COALESCE(r.ref, '')) LIKE :search_like
                    OR LOWER(COALESCE(r.title, '')) LIKE :search_like
                    OR LOWER(COALESCE(r.description, '')) LIKE :search_like
                    OR LOWER(COALESCE(r.requester_name, '')) LIKE :search_like
                    OR LOWER(COALESCE(r.requester_email, '')) LIKE :search_like
                    OR LOWER(COALESCE(r.meter_number, '')) LIKE :search_like
                  )
            """

        count_stmt = text(f"""
            SELECT COUNT(*) FROM (
                SELECT wf.request_id
                FROM workflow_detail wd
                JOIN workflow wf ON wf.id = wd.workflow_id
                JOIN request r   ON r.id = wf.request_id AND r.deleted_at IS NULL
                WHERE wd.event_type = 'treatment_transmitted'
                  AND wd.deleted_at IS NULL
                  AND JSON_UNQUOTE(JSON_EXTRACT(wd.infos, '$.actor_id')) = :actor_id
                  {search_clause}
                GROUP BY wf.request_id
            ) t
        """)
        total = (await self.session.execute(count_stmt, params)).scalar_one() or 0
        if not total:
            return [], 0

        ids_stmt = text(f"""
            SELECT wf.request_id AS request_id, MAX(wd.created_at) AS last_transmitted_at
            FROM workflow_detail wd
            JOIN workflow wf ON wf.id = wd.workflow_id
            JOIN request r   ON r.id = wf.request_id AND r.deleted_at IS NULL
            WHERE wd.event_type = 'treatment_transmitted'
              AND wd.deleted_at IS NULL
              AND JSON_UNQUOTE(JSON_EXTRACT(wd.infos, '$.actor_id')) = :actor_id
              {search_clause}
            GROUP BY wf.request_id
            ORDER BY last_transmitted_at DESC
            LIMIT :limit OFFSET :offset
        """)
        rows = (await self.session.execute(
            ids_stmt,
            {**params, "limit": limit, "offset": max(0, (page - 1) * limit)},
        )).all()
        ordered_ids = [int(row.request_id) for row in rows]
        if not ordered_ids:
            return [], total

        # Hydratation via le pipeline standard (mêmes load_options que les
        # autres listes) — pagination déjà faite ci-dessus, limit=len(ids) suffit.
        # L'ordre pertinent est celui de la dernière transmission (ci-dessus),
        # pas le tri par défaut de .list() — réordonné en Python juste après.
        items, _ = await self.list(
            filters={"id": ordered_ids},
            limit=len(ordered_ids),
            page=1,
            load_options=_SKIP_UNUSED_RELS,
        )
        by_id = {item.id: item for item in items}
        ordered_items = [by_id[i] for i in ordered_ids if i in by_id]
        return ordered_items, total

    async def list_by_requester(
        self, requester_id: str, *, page: int = 1, limit: int = 20
    ) -> tuple[list[Request], int]:
        return await self.list(
            filters={"requester_id": requester_id},
            order_by="-created_at",
            page=page,
            limit=limit,
            load_options=_SKIP_UNUSED_RELS,
        )

    async def search(
        self,
        term: str,
        *,
        filters: dict | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[Request], int]:
        return await self.list(
            filters=filters,
            search=(["ref", "title", "requester_name", "requester_email", "meter_number"], term),
            order_by="-created_at",
            page=page,
            limit=limit,
            load_options=_SKIP_UNUSED_RELS,
        )

    async def list_queue(
        self,
        *,
        direction_id: str | None = None,
        assignee_id: str | None = None,
        unassigned_only: bool = False,
        priority: str | None = None,
        request_status: str | None = None,
        search: str | None = None,
        page: int = 1,
        limit: int = 20,
    ) -> tuple[list[Request], int]:
        # Si un statut précis est demandé, on filtre sur ce seul statut ;
        # sinon on utilise la liste des statuts actifs par défaut.
        filters: dict = {
            "request_status": request_status if request_status else self._ACTIVE_STATUSES,
            "in_triage": False,
        }
        if direction_id:
            filters["unity_id"] = await self._direction_unity_ids(direction_id)
        if assignee_id:
            filters["assignee_id"] = assignee_id
        if unassigned_only:
            filters["unassigned_only"] = True
        if priority:
            filters["priority"] = priority
        if search:
            return await self.search(search, filters=filters, page=page, limit=limit)
        return await self.list(
            filters=filters, order_by="-created_at", page=page, limit=limit,
            load_options=_SKIP_UNUSED_RELS,
        )

    async def count_by_status(self) -> dict[str, int]:
        """Retourne {status_code: count} pour le tableau de bord."""
        stmt = (
            select(RequestStatus.code, func.count(Request.id))
            .join(RequestStatus, Request.request_status_id == RequestStatus.id)
            .where(Request.deleted_at.is_(None))
            .group_by(RequestStatus.code)
        )
        rows = (await self.session.execute(stmt)).all()
        return {row[0]: row[1] for row in rows}

    async def count_active_by_assignee(
        self,
        unity_ids: list[int],
        *,
        exclude_statuses: list[str],
    ) -> dict[int, int]:
        """Nombre de tickets non terminaux par agent assigné, pour le périmètre donné."""
        if not unity_ids:
            return {}
        stmt = (
            select(Request.assignee_id, func.count(Request.id))
            .join(RequestStatus, Request.request_status_id == RequestStatus.id)
            .where(
                Request.deleted_at.is_(None),
                Request.unity_id.in_(unity_ids),
                Request.assignee_id.isnot(None),
                RequestStatus.code.notin_(exclude_statuses),
            )
            .group_by(Request.assignee_id)
        )
        rows = (await self.session.execute(stmt)).all()
        return {int(row[0]): row[1] for row in rows}

    async def next_ref(self, base: str | int) -> str:
        """
        Calcule la prochaine référence unique pour une base donnée.

        Nouvelle forme métier :
            DIR-DEPT-SVC-HHMMSSYYYMMDD-SEQ
        (direction / département / service du demandeur, résolus via l'organigramme)

        La méthode conserve aussi l'ancien appel next_ref(year) par prudence.
        Elle se base sur le MAX du suffixe parmi TOUTES les lignes, y compris
        les soft-deleted, car la contrainte unique sur `ref` s'applique aussi
        aux lignes supprimées.
        """
        if isinstance(base, int):
            prefix = f"EDG-{base}-"
            seq_width = 4
        else:
            prefix = f"{base.rstrip('-').upper()}-"
            seq_width = 3
        stmt = select(Request.ref).where(Request.ref.like(f"{prefix}%"))
        refs = [row[0] for row in (await self.session.execute(stmt)).all()]
        max_num = 0
        for r in refs:
            suffix = r[len(prefix):]
            if suffix.isdigit():
                max_num = max(max_num, int(suffix))
        return f"{prefix}{max_num + 1:0{seq_width}d}"
