"""
Export du dossier fonctionnel complet d'une demande — réservé à l'espace Administration.

Reconstruit l'intégralité du parcours d'UNE demande (identification, demandeur,
structure organisationnelle, acteurs, historique, escalades, conversations,
pièces jointes, notifications) exclusivement depuis les données réellement
persistées (Request, WorkflowDetail, Attachment, Notification, Organigram) —
aucune nouvelle donnée, aucune nouvelle relation.

Aucune information de délai/SLA n'est incluse (sla_hours, sla_elapsed,
sla_breached, sla_response_at, et tout champ dérivé de infos.sla_*).
"""
from __future__ import annotations

import io
from datetime import date, datetime
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from api.core.error_codes import ErrorCode
from api.repositories import (
    AccountRepository,
    NotificationRepository,
    OrganigramRepository,
    RequestRepository,
    UnityRepository,
)
from api.services.base_service import BaseService

_HEADER_FILL = "1A5276"
_ALT_FILL = "EBF5FB"
_EMPTY_MESSAGE = "Aucune donnée enregistrée"
_NOT_AVAILABLE = "Information non disponible actuellement"

_COMMENT_EVENT = "comment_added"
_ESCALATION_EVENTS = {"escalation_manual", "escalation_auto"}

_EVENT_LABELS: dict[str, str] = {
    "created": "Création de la demande",
    "qualifying": "Mise en qualification",
    "qualified": "Qualification effectuée",
    "assigned": "Affectation",
    "in_progress": "Prise en charge",
    "treatment_transmitted": "Transmission du traitement",
    "treatment_completed": "Résolution",
    "closed": "Clôture",
    "cancelled": "Annulation",
    "rejected": "Rejet",
    "reopened": "Réouverture",
    "escalation_manual": "Escalade manuelle",
    "escalation_auto": "Escalade automatique",
}


def _detail_for_event(event_type: str | None, infos: dict | None) -> str:
    infos = infos or {}
    if event_type == "treatment_transmitted":
        target = infos.get("target_user_name") or "destinataire non renseigné"
        reason = infos.get("reason") or infos.get("instruction")
        return f"Transmis à {target}" + (f" — motif : {reason}" if reason else "")
    if event_type == "treatment_completed":
        solution = infos.get("solution") or infos.get("summary")
        return "Résolution" + (f" — solution : {solution}" if solution else "")
    if event_type == "cancelled":
        reason = infos.get("reason")
        return "Annulé" + (f" — motif : {reason}" if reason else "")
    if event_type == "rejected":
        reason = infos.get("reason")
        return "Rejeté" + (f" — motif : {reason}" if reason else "")
    if event_type == "reopened":
        reason = infos.get("reopen_reason") or infos.get("sla_reopen_reason")
        return "Réouverture" + (f" — motif : {reason}" if reason else "")
    if event_type == "assigned":
        target = infos.get("target_user_name")
        return f"Affecté à {target}" if target else "Affectation"
    return _EVENT_LABELS.get(event_type or "", event_type or "Événement")


def _fmt(value: Any) -> Any:
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y %H:%M")
    if isinstance(value, date):
        return value.strftime("%d/%m/%Y")
    if isinstance(value, bool):
        return "Oui" if value else "Non"
    if value is None:
        return ""
    return value


def _write_table_sheet(wb, name: str, rows: list[dict[str, Any]]) -> None:
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    ws = wb.create_sheet(title=name[:31])
    if not rows:
        ws.cell(row=1, column=1, value=_EMPTY_MESSAGE).font = Font(italic=True)
        ws.column_dimensions["A"].width = 40
        return

    headers = list(rows[0].keys())
    header_fill = PatternFill("solid", fgColor=_HEADER_FILL)
    header_font = Font(bold=True, color="FFFFFF")
    for col_idx, label in enumerate(headers, start=1):
        cell = ws.cell(row=1, column=col_idx, value=label)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    alt_fill = PatternFill("solid", fgColor=_ALT_FILL)
    for row_idx, row in enumerate(rows, start=2):
        for col_idx, key in enumerate(headers, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=_fmt(row.get(key)))
            if row_idx % 2 == 0:
                cell.fill = alt_fill
            cell.alignment = Alignment(horizontal="left", wrap_text=True, vertical="top")

    for col_idx in range(1, len(headers) + 1):
        letter = get_column_letter(col_idx)
        max_len = max(
            (len(str(ws.cell(row=r, column=col_idx).value or "")) for r in range(1, len(rows) + 2)),
            default=8,
        )
        ws.column_dimensions[letter].width = min(max_len + 4, 60)


def _pdf_section_break(pdf, title: str) -> None:
    """Nouvelle page + bandeau de titre de section (équivalent PDF d'un onglet
    Excel) — une page par section garde le document lisible malgré des
    tableaux de longueur très variable (0 à des centaines de lignes)."""
    from api.services.ServiceExport import pdf_safe_text

    pdf.add_page()
    pdf.set_font("Helvetica", "B", 12)
    pdf.set_fill_color(26, 82, 118)
    pdf.set_text_color(255, 255, 255)
    pdf.cell(0, 9, f"  {pdf_safe_text(title)}", fill=True, new_x="LMARGIN", new_y="NEXT")
    pdf.set_text_color(0, 0, 0)
    pdf.ln(3)


def _pdf_kv_rows(pdf, rows: list[tuple[str, Any]]) -> None:
    """Rend la feuille Synthèse (paires libellé/valeur, avec bandeaux de
    sous-section) en PDF — même structure que _write_kv_sheet côté Excel."""
    from api.services.ServiceExport import pdf_safe_text

    for label, value in rows:
        if label.startswith("— ") and label.endswith(" —"):
            pdf.ln(2)
            pdf.set_font("Helvetica", "B", 10)
            pdf.set_fill_color(235, 245, 251)
            pdf.set_text_color(26, 82, 118)
            pdf.cell(0, 7, pdf_safe_text(label.strip("— ")), fill=True, new_x="LMARGIN", new_y="NEXT")
            pdf.set_text_color(0, 0, 0)
            continue
        pdf.set_font("Helvetica", "B", 9)
        pdf.set_text_color(60, 60, 60)
        pdf.cell(55, 6, pdf_safe_text(label))
        pdf.set_font("Helvetica", "", 9)
        pdf.set_text_color(0, 0, 0)
        pdf.multi_cell(0, 6, pdf_safe_text(_fmt(value)) or "-", new_x="LMARGIN", new_y="NEXT")


def _pdf_data_table(pdf, rows: list[dict[str, Any]]) -> None:
    """Rend une feuille tabulaire (Acteurs/Historique/Escalades/...) en PDF —
    utilise l'API Table de fpdf2 (retour à la ligne automatique dans les
    cellules, pas de troncature du contenu)."""
    from fpdf.fonts import FontFace
    from api.services.ServiceExport import pdf_safe_text

    if not rows:
        pdf.set_font("Helvetica", "I", 9)
        pdf.set_text_color(120, 120, 120)
        pdf.cell(0, 8, pdf_safe_text(_EMPTY_MESSAGE))
        return

    headers = list(rows[0].keys())
    page_w = pdf.w - pdf.l_margin - pdf.r_margin
    col_w = page_w / len(headers)
    pdf.set_font("Helvetica", "", 8)
    # Réinitialise l'état fill/text laissé par _pdf_section_break() juste avant
    # — sinon les lignes "non remplies" de la table héritent du bleu foncé du
    # bandeau de section (texte illisible sur fond sombre).
    pdf.set_fill_color(255, 255, 255)
    pdf.set_text_color(0, 0, 0)
    with pdf.table(
        col_widths=[col_w] * len(headers),
        text_align="LEFT",
        headings_style=FontFace(emphasis="BOLD", color=255, fill_color=(26, 82, 118)),
        cell_fill_color=(235, 245, 251),
        cell_fill_mode="ROWS",
        line_height=5,
    ) as table:
        header_row = table.row()
        for h in headers:
            header_row.cell(pdf_safe_text(h))
        for row in rows:
            data_row = table.row()
            for h in headers:
                data_row.cell(pdf_safe_text(_fmt(row.get(h))) or "-")


def _write_kv_sheet(wb, name: str, rows: list[tuple[str, Any]]) -> None:
    from openpyxl.styles import Alignment, Font, PatternFill

    ws = wb.active
    ws.title = name[:31]
    section_font = Font(bold=True, color="FFFFFF")
    section_fill = PatternFill("solid", fgColor=_HEADER_FILL)
    label_font = Font(bold=True)
    for row_idx, (label, value) in enumerate(rows, start=1):
        if label.startswith("— ") and label.endswith(" —"):
            ws.merge_cells(f"A{row_idx}:B{row_idx}")
            cell = ws.cell(row=row_idx, column=1, value=label.strip("— "))
            cell.font = section_font
            cell.fill = section_fill
            continue
        ws.cell(row=row_idx, column=1, value=label).font = label_font
        ws.cell(row=row_idx, column=2, value=_fmt(value)).alignment = Alignment(wrap_text=True, vertical="top")
    ws.column_dimensions["A"].width = 32
    ws.column_dimensions["B"].width = 70


class RequestExportService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.request_repo = RequestRepository(session)
        self.notification_repo = NotificationRepository(session)
        self.organigram_repo = OrganigramRepository(session)
        self.unity_repo = UnityRepository(session)
        self.account_repo = AccountRepository(session)

    async def build_dossier(self, request_id: str, fmt: str = "excel") -> tuple[bytes, str]:
        req = await self.request_repo.get_by_id(request_id, include_deleted=True)
        if req is None:
            raise self.not_found(
                "Cette demande n'existe pas.",
                error_code=ErrorCode.REQUEST_NOT_FOUND,
                field="id",
                value=request_id,
            )

        events = sorted(req.timelines or [], key=lambda e: e.created_at or datetime.min)
        org_chain = await self._organizational_chain(req)

        summary_rows = self._build_summary(req, org_chain, events)
        actor_rows = self._build_actors(events, req)
        history_rows = self._build_history(events)
        escalation_rows = self._build_escalations(events)
        conversation_rows = self._build_conversations(events)
        attachment_rows = await self._build_attachments(req)
        notification_rows = await self._build_notifications(req.id)

        if fmt == "pdf":
            content = self._render_pdf(
                req.ref, summary_rows, actor_rows, history_rows, escalation_rows,
                conversation_rows, attachment_rows, notification_rows,
            )
        else:
            content = self._render_workbook(
                summary_rows, actor_rows, history_rows, escalation_rows,
                conversation_rows, attachment_rows, notification_rows,
            )
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        filename = f"Dossier_{req.ref}_{stamp}"
        return content, filename

    # ── Structure organisationnelle ──────────────────────────────────────────

    async def _organizational_chain(self, req) -> list[str]:
        unity_id = req.requester.unity_id if req.requester else None
        if not unity_id:
            return []
        node = await self.organigram_repo.find_by_unity(unity_id)
        if node is None:
            unity = await self.unity_repo.get_by_id(unity_id)
            return [unity.label] if unity else []
        ancestors = await self.organigram_repo.get_ancestors(node.id)
        # `get_ancestors` renvoie [parent immédiat, ..., racine] (level croissant) ;
        # on veut l'ordre Direction (racine) → ... → Unité du demandeur.
        chain_ids = [a["unity_id"] for a in reversed(ancestors)] + [unity_id]
        labels: list[str] = []
        for uid in chain_ids:
            unity = await self.unity_repo.get_by_id(uid)
            labels.append(unity.label if unity else f"Unité #{uid}")
        return labels

    # ── Feuille Synthèse ──────────────────────────────────────────────────────

    def _build_summary(self, req, org_chain: list[str], events: list) -> list[tuple[str, Any]]:
        resolved_evt = next((e for e in events if e.event_type == "treatment_completed"), None)
        closed_evt = next((e for e in events if e.event_type == "closed"), None)
        cancelled_evt = next((e for e in events if e.event_type == "cancelled"), None)
        rejected_evt = next((e for e in events if e.event_type == "rejected"), None)
        last_evt = events[-1] if events else None

        requester = req.requester
        if requester:
            requester_block = [
                ("Nom complet", " ".join(p for p in (requester.firstname, requester.name) if p) or requester.name),
                ("Email", requester.email or _NOT_AVAILABLE),
                ("Téléphone", requester.phone or _NOT_AVAILABLE),
                ("Fonction", requester.job or _NOT_AVAILABLE),
                ("Matricule", requester.matricule or _NOT_AVAILABLE),
            ]
        else:
            requester_block = [
                ("Nom complet", req.requester_name or _NOT_AVAILABLE),
                ("Email", req.requester_email or _NOT_AVAILABLE),
                ("Téléphone", req.requester_phone or _NOT_AVAILABLE),
                ("Adresse", req.requester_address or _NOT_AVAILABLE),
            ]

        return [
            ("— IDENTIFICATION DE LA DEMANDE —", ""),
            ("Référence", req.ref),
            ("UUID", req.uuid),
            ("Titre", req.title),
            ("Description", req.description),
            ("Type de demandeur", "Externe (citoyen/client)" if req.is_external else "Interne (employé EDG)"),
            ("Mode de soumission", "Pour le compte d'une unité" if req.submission_mode == "on_behalf_of_unit" else "Personnel"),
            ("Catégorie", req.request_category_ref.label if req.request_category_ref else _NOT_AVAILABLE),
            ("Priorité", req.priority_definition_ref.label if req.priority_definition_ref else _NOT_AVAILABLE),
            ("Statut actuel", req.request_status_ref.label if req.request_status_ref else _NOT_AVAILABLE),
            ("Date de création", req.created_at),
            ("Dernière modification", req.updated_at),
            ("— DEMANDEUR —", ""),
            *requester_block,
            ("Structure organisationnelle", " > ".join(org_chain) if org_chain else _NOT_AVAILABLE),
            ("— TRAITEMENT ACTUEL —", ""),
            ("Responsable actuel", req.assignee_name or _NOT_AVAILABLE),
            ("Unité responsable", req.unity.label if req.unity else _NOT_AVAILABLE),
            ("Dernier événement", _detail_for_event(last_evt.event_type, last_evt.infos) if last_evt else _NOT_AVAILABLE),
            ("Dernier acteur", last_evt.actor_name if last_evt and last_evt.actor_name else _NOT_AVAILABLE),
            ("Date de la dernière action", last_evt.created_at if last_evt else _NOT_AVAILABLE),
            ("— RÉSOLUTION —", ""),
            ("Résolue", bool(resolved_evt)),
            ("Résolue par", resolved_evt.actor_name if resolved_evt else "—"),
            ("Date de résolution", req.resolved_at or (resolved_evt.created_at if resolved_evt else None)),
            ("Solution", (resolved_evt.infos or {}).get("solution") if resolved_evt else "—"),
            ("— VALIDATION —", ""),
            ("Circuit de validation distinct", _NOT_AVAILABLE),
            ("— CLÔTURE —", ""),
            ("Clôturée", bool(closed_evt)),
            ("Clôturée par", closed_evt.actor_name if closed_evt else "—"),
            ("Date de clôture", req.closed_at or (closed_evt.created_at if closed_evt else None)),
            ("— ANNULATION —", ""),
            ("Annulée", bool(cancelled_evt)),
            ("Annulée par", cancelled_evt.actor_name if cancelled_evt else "—"),
            ("Date d'annulation", cancelled_evt.created_at if cancelled_evt else None),
            ("Motif d'annulation", (cancelled_evt.infos or {}).get("reason") if cancelled_evt else "—"),
            ("— REJET —", ""),
            ("Rejetée", bool(rejected_evt)),
            ("Rejetée par", rejected_evt.actor_name if rejected_evt else "—"),
            ("Motif de rejet", (rejected_evt.infos or {}).get("reason") if rejected_evt else "—"),
        ]

    # ── Feuille Acteurs ───────────────────────────────────────────────────────

    def _build_actors(self, events: list, req) -> list[dict[str, Any]]:
        stats: dict[str, dict[str, Any]] = {}

        def _touch(name: str | None, role: str | None, when: datetime | None) -> None:
            if not name:
                return
            s = stats.setdefault(name, {"role": role or "", "first": when, "last": when, "count": 0})
            s["count"] += 1
            if role and not s["role"]:
                s["role"] = role
            if when:
                if not s["first"] or when < s["first"]:
                    s["first"] = when
                if not s["last"] or when > s["last"]:
                    s["last"] = when

        if req.requester:
            _touch(
                " ".join(p for p in (req.requester.firstname, req.requester.name) if p) or req.requester.name,
                "Demandeur",
                req.created_at,
            )
        elif req.requester_name:
            _touch(req.requester_name, "Demandeur (externe)", req.created_at)

        for e in events:
            infos = e.infos or {}
            name = infos.get("intervention_actor_name") or e.actor_name
            role = infos.get("intervention_actor_role") or infos.get("actor_role")
            _touch(name, role, e.created_at)

        rows = []
        for name, s in sorted(stats.items(), key=lambda kv: kv[1]["first"] or datetime.min):
            rows.append({
                "Acteur": name,
                "Rôle": s["role"] or _NOT_AVAILABLE,
                "Première action": s["first"],
                "Dernière action": s["last"],
                "Nombre d'actions": s["count"],
            })
        return rows

    # ── Feuille Historique ────────────────────────────────────────────────────

    def _build_history(self, events: list) -> list[dict[str, Any]]:
        rows = []
        for e in events:
            if e.event_type == _COMMENT_EVENT:
                continue
            infos = e.infos or {}
            rows.append({
                "Date": e.created_at,
                "Type d'événement": _EVENT_LABELS.get(e.event_type or "", e.event_type or "Événement"),
                "Ancien statut": infos.get("old_status") or "",
                "Nouveau statut": infos.get("new_status") or "",
                "Acteur": e.actor_name or _NOT_AVAILABLE,
                "Description": _detail_for_event(e.event_type, infos) or e.comment or e.label or "",
            })
        return rows

    # ── Feuille Escalades ─────────────────────────────────────────────────────

    def _build_escalations(self, events: list) -> list[dict[str, Any]]:
        rows = []
        for e in events:
            if e.event_type not in _ESCALATION_EVENTS:
                continue
            infos = e.infos or {}
            rows.append({
                "Date": e.created_at,
                "Type": "Automatique (SLA)" if e.event_type == "escalation_auto" else "Manuelle",
                "Émetteur": e.actor_name or _NOT_AVAILABLE,
                "Destinataire": infos.get("to_agent_name") or _NOT_AVAILABLE,
                "Niveau": infos.get("level") or _NOT_AVAILABLE,
                "Raison": e.comment or infos.get("reason") or "",
                "Statut de l'escalade": infos.get("status") or _NOT_AVAILABLE,
                "Commentaire de décision": infos.get("decision_comment") or "",
                "Commentaire DG": infos.get("dg_comment") or "",
            })
        return rows

    # ── Feuille Conversations ─────────────────────────────────────────────────

    def _build_conversations(self, events: list) -> list[dict[str, Any]]:
        rows = []
        for e in events:
            if e.event_type != _COMMENT_EVENT:
                continue
            infos = e.infos or {}
            rows.append({
                "Date": e.created_at,
                "Auteur": e.actor_name or _NOT_AVAILABLE,
                "Visibilité": "Public (visible du demandeur)" if infos.get("is_public") else "Interne (staff uniquement)",
                "Message": e.comment or "",
                "Pièce jointe associée": infos.get("filename") or "—",
            })
        return rows

    # ── Feuille Pièces jointes ────────────────────────────────────────────────

    async def _build_attachments(self, req) -> list[dict[str, Any]]:
        rows = []
        cache: dict[int, str] = {}
        for att in req.attachments or []:
            uploader_name = _NOT_AVAILABLE
            if att.uploader_id:
                if att.uploader_id not in cache:
                    acc = await self.account_repo.get_by_id(att.uploader_id, include_deleted=True)
                    cache[att.uploader_id] = self._account_label(acc)
                uploader_name = cache[att.uploader_id]
            rows.append({
                "Nom du fichier": att.filename,
                "Type MIME": att.mime_type,
                "Taille": self._human_size(att.size_bytes),
                "Ajoutée par": uploader_name,
                "Date d'ajout": att.created_at,
                "Statut de scan antivirus": att.scan_status,
            })
        return rows

    # ── Feuille Notifications ─────────────────────────────────────────────────

    async def _build_notifications(self, request_id: int) -> list[dict[str, Any]]:
        notifications, _total = await self.notification_repo.list_by_request(str(request_id), limit=500)
        rows = []
        cache: dict[int, str] = {}
        for n in notifications:
            if n.recipient_id not in cache:
                acc = await self.account_repo.get_by_id(n.recipient_id, include_deleted=True)
                cache[n.recipient_id] = self._account_label(acc)
            rows.append({
                "Date": n.created_at,
                "Type": n.type,
                "Canal": n.channel,
                "Destinataire": cache[n.recipient_id],
                "Titre": n.title,
                "Message": n.body,
                "Lue": n.is_read,
            })
        return rows

    # ── Rendu du classeur ─────────────────────────────────────────────────────

    def _render_workbook(
        self, summary_rows, actor_rows, history_rows, escalation_rows,
        conversation_rows, attachment_rows, notification_rows,
    ) -> bytes:
        try:
            from openpyxl import Workbook
        except ImportError:
            raise RuntimeError("openpyxl requis pour l'export du dossier. pip install openpyxl")

        wb = Workbook()
        _write_kv_sheet(wb, "Synthèse", summary_rows)
        _write_table_sheet(wb, "Acteurs", actor_rows)
        _write_table_sheet(wb, "Historique", history_rows)
        _write_table_sheet(wb, "Escalades", escalation_rows)
        _write_table_sheet(wb, "Conversations", conversation_rows)
        _write_table_sheet(wb, "Pièces jointes", attachment_rows)
        _write_table_sheet(wb, "Notifications", notification_rows)

        buf = io.BytesIO()
        wb.save(buf)
        return buf.getvalue()

    # ── Rendu PDF (logo EDG en en-tête + filigrane) ──────────────────────────

    def _render_pdf(
        self, ref: str, summary_rows, actor_rows, history_rows, escalation_rows,
        conversation_rows, attachment_rows, notification_rows,
    ) -> bytes:
        from api.services.ServiceExport import make_branded_pdf

        pdf = make_branded_pdf(f"Dossier — {ref}")

        _pdf_section_break(pdf, "Synthèse")
        _pdf_kv_rows(pdf, summary_rows)

        for title, rows in (
            ("Acteurs", actor_rows),
            ("Historique", history_rows),
            ("Escalades", escalation_rows),
            ("Conversations", conversation_rows),
            ("Pièces jointes", attachment_rows),
            ("Notifications", notification_rows),
        ):
            _pdf_section_break(pdf, title)
            _pdf_data_table(pdf, rows)

        return bytes(pdf.output())

    # ── Utilitaires ───────────────────────────────────────────────────────────

    @staticmethod
    def _account_label(acc) -> str:
        if acc is None:
            return "Compte introuvable"
        parts = [p for p in (acc.firstname, acc.name) if p]
        return " ".join(parts) if parts else acc.name

    @staticmethod
    def _human_size(size_bytes: int | None) -> str:
        if not size_bytes:
            return "—"
        size = float(size_bytes)
        for unit in ("o", "Ko", "Mo", "Go"):
            if size < 1024:
                return f"{size:.0f} {unit}" if unit == "o" else f"{size:.1f} {unit}"
            size /= 1024
        return f"{size:.1f} To"
