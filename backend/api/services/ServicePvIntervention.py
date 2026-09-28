"""PV d'intervention — formulaire officiel EDG/PS-GSI/PV-01 (version 03).

Procédure EDG/PS-GSI/Pro-02, tâche 3.1 « Établir le PV d'Intervention ». Le PV
est la donnée de sortie unique de la procédure (§3) et son information
documentée (§5).

Aucune donnée n'est collectée pour ce document : tout provient de ce que les
blocs 1 et 2 ont déjà figé — organisation traitante (tâche 1.3), constat terrain
(tâche 2.1), horaires et identité de l'intervenant (BR-TRACE-001), et les champs
obligatoires de la résolution (tâche 2.2). Le PV est une mise en forme.

**Émargement électronique** (décision du 2026-09-27, qui révise celle du
2026-09-22) : les validations faites dans l'application sont portées sur le
document, un ✓ tenant lieu de signature.

  - Signature du traitant (bloc Affectation) et émargement « Responsable IT » :
    ✓ dès que le traitement est terminé.
  - Émargement « Requérant » : ✓ dès qu'il a validé le dépannage (tâche 3.2),
    suivi de *(automatique)* si la validation a été faite d'office après son
    silence (BR-AUTO-VALIDATION-001).
  - Tant que l'acte correspondant n'a pas eu lieu, la zone reste **vierge** :
    une case vide reste une case à signer au stylo, elle ne doit jamais laisser
    croire à un accord.

`proposed_solution` (tâche 1.3) n'y figure jamais : c'est une piste interne, que
le demandeur — destinataire de ce PV — ne doit pas voir.
"""
from __future__ import annotations

from datetime import datetime
from typing import Any, Optional

from sqlalchemy.ext.asyncio import AsyncSession

from api.core.error_codes import ErrorCode
from api.repositories import RequestRepository
from api.services.base_service import BaseService

# En-tête réglementaire du formulaire — ne jamais l'inventer ni le paramétrer.
PV_REF = "EDG/PS-GSI/PV-01"
PV_VERSION = "03"
PV_DATE = "02/06/2026"
PV_PROCESS = "PROCESSUS GERER LE SYSTEME D'INFORMATION"
PV_TITLE = "PV D'INTERVENTION"
PV_FOOTER = "Avant utilisation d'un document papier, verifier sa validite"

_BLUE = (26, 82, 118)
_BAND = (222, 222, 222)
_LINE = (120, 120, 120)

_CHECKED = "[X]"
_UNCHECKED = "[ ]"

# Canal de réception — le formulaire n'offre que Mail et Téléphone.
_MAIL_SOURCES = {"email"}
_PHONE_SOURCES = {"telephone"}


def _checkbox(selected: bool) -> str:
    return _CHECKED if selected else _UNCHECKED


def _as_datetime(value: Any) -> Optional[datetime]:
    """Accepte un datetime OU une chaîne ISO.

    Les horodatages du PV viennent de deux sources de nature différente : des
    colonnes SQL (`resolved_at` → datetime) et les métadonnées d'intervention
    reconstruites depuis le journal (`started_at`/`ended_at` → chaînes ISO, un
    JSON ne portant pas de type date). Les formateurs ne testaient que
    `isinstance(value, datetime)` : toute la partie intervention — date et heure
    de début comme de fin — ressortait donc VIDE alors que la donnée existait.
    """
    if isinstance(value, datetime):
        return value
    if isinstance(value, str) and value.strip():
        try:
            return datetime.fromisoformat(value.strip().replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


def _duration(start: Any, end: Any) -> str:
    """Durée réelle de l'intervention : écart entre début et fin.

    Distincte du SLA (`sla_hours`), qui est le délai CONTRACTUEL accordé. Le
    formulaire demande ici le temps effectivement passé.

    Unité choisie selon l'ordre de grandeur, pour rester lisible sur un document
    imprimé : minutes en deçà d'une heure, heures en deçà d'un jour, jours
    au-delà. Les deux horodatages peuvent porter des fuseaux différents (ou aucun)
    selon leur origine — on les ramène donc au même référentiel avant de
    soustraire, sinon Python refuse l'opération.
    """
    a, b = _as_datetime(start), _as_datetime(end)
    if a is None or b is None:
        return ""
    if (a.tzinfo is None) != (b.tzinfo is None):
        a = a.replace(tzinfo=None)
        b = b.replace(tzinfo=None)
    seconds = (b - a).total_seconds()
    if seconds < 0:
        return ""
    minutes = int(seconds // 60)
    if minutes < 60:
        return f"{minutes} min"
    hours, rest_min = divmod(minutes, 60)
    if hours < 24:
        return f"{hours} h" if rest_min == 0 else f"{hours} h {rest_min:02d}"
    days, rest_hours = divmod(hours, 24)
    return f"{days} j" if rest_hours == 0 else f"{days} j {rest_hours} h"


def _date(value: Any) -> str:
    parsed = _as_datetime(value)
    return parsed.strftime("%d/%m/%Y") if parsed else ""


def _time(value: Any) -> str:
    parsed = _as_datetime(value)
    return parsed.strftime("%H:%M") if parsed else ""


class PvInterventionService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.request_repo = RequestRepository(session)

    # ── Données ───────────────────────────────────────────────────────────────

    async def build(self, request_id: str) -> tuple[bytes, str]:
        req = await self.request_repo.get_by_id(request_id, include_deleted=True)
        if req is None:
            raise self.not_found(
                "Cette demande n'existe pas.",
                error_code=ErrorCode.REQUEST_NOT_FOUND,
                field="id",
                value=request_id,
            )
        data = self._collect(req)
        content = self._render(data)
        stamp = datetime.now().strftime("%Y%m%d_%H%M")
        return content, f"PV_{req.ref}_{stamp}"

    @staticmethod
    def _last_intervention(req) -> dict[str, Any]:
        """Le PV documente l'intervention qui a conduit à la résolution, donc la
        dernière du ticket. Les précédentes (transmissions) restent au journal
        d'interventions ; un PV par intervention serait un autre document."""
        interventions = req.interventions or []
        return interventions[-1] if interventions else {}

    def _field_check(self, req) -> dict[str, Any]:
        """Constat terrain de la dernière intervention (tâche 2.1)."""
        target = self._last_intervention(req).get("intervention_id")
        for event in reversed(req.timelines or []):
            if event.event_type != "field_check":
                continue
            infos = event.infos if isinstance(event.infos, dict) else {}
            if target is None or infos.get("intervention_id") == target:
                return infos
        return {}

    def _collect(self, req) -> dict[str, Any]:
        frozen = req.infos if isinstance(req.infos, dict) else {}
        iv = self._last_intervention(req)
        fc = self._field_check(req)
        source = (req.request_source or "").lower()

        # Badge de l'intervenant, ou son nom complet à défaut : un prestataire ou
        # un stagiaire n'a pas forcément de badge EDG, et la case ne doit jamais
        # rester vide sur un document destiné à être signé.
        badge = iv.get("actor_matricule") or iv.get("actor_name") or ""
        status = (iv.get("actor_status") or "").lower()

        appreciation = req.appreciation
        return {
            "ref": req.ref,
            "received_by_mail": source in _MAIL_SOURCES,
            "received_by_phone": source in _PHONE_SOURCES,
            "requester_service": frozen.get("requester_service_label") or "",
            "requester_name": req.requester_name or "",
            "receiver_name": frozen.get("receiver_name") or "",
            "receiver_badge": frozen.get("receiver_badge") or "",
            "handler_department": frozen.get("handler_department_label") or "",
            "handler_service": frozen.get("handler_service_label") or "",
            # Le lieu est saisi par le TRAITANT au démarrage du traitement
            # (`treatment_location`), depuis la décision produit du 2026-09-27 qui
            # a retiré ce champ du formulaire de création. Le PV lisait encore
            # `location_label`, que plus personne ne renseigne — d'où une ligne de
            # pointillés systématique. Repli conservé pour les tickets antérieurs.
            "place": frozen.get("treatment_location") or req.location_label or "",
            "is_titulaire": status == "titulaire",
            "is_prestataire": status == "prestataire",
            "is_stagiaire": status == "stagiaire",
            "badge": badge,
            "assignment_date": _date(iv.get("started_at")),
            "sla_hours": req.sla_hours or 0,
            # Temps réellement passé sur l'intervention (début → fin), à ne pas
            # confondre avec `sla_hours`, le délai contractuel accordé.
            "intervention_duration": _duration(iv.get("started_at"), iv.get("ended_at")),
            "start_date": _date(iv.get("started_at")),
            "end_date": _date(iv.get("ended_at")),
            "start_time": _time(iv.get("started_at")),
            "end_time": _time(iv.get("ended_at")),
            "field_check": fc.get("findings") or "",
            "field_check_gap": fc.get("conformity") == "ecart",
            "work_done": iv.get("work_done") or "",
            "solution": iv.get("solution") or "",
            "recommendations": iv.get("recommendations") or "",
            "resolved_at": _date(req.resolved_at),
            # Émargement électronique (décision produit du 2026-09-27) — la
            # validation faite dans l'application tient lieu de signature.
            #   IT        : le traitement est terminé (même fait que la date
            #               déjà imprimée dans cette colonne).
            #   Requérant : il a validé le dépannage (tâche 3.2). Un ticket
            #               rouvert efface cette validation, la case redevient
            #               donc vide — cohérent, l'accord a été retiré.
            "it_signed": bool(req.resolved_at),
            "requester_signed": bool(frozen.get("pv_validated_at")),
            # Validation d'office après silence du demandeur : signalée comme
            # telle, sans quoi le document laisserait croire à un accord explicite.
            "requester_signed_auto": bool(frozen.get("pv_validated_automatically")),
            "appreciation_comment": getattr(appreciation, "comment", None) or "",
            "appreciation_rating": getattr(appreciation, "rating", None),
            "appreciation_date": _date(getattr(appreciation, "created_at", None)),
        }

    # ── Rendu ─────────────────────────────────────────────────────────────────

    def _render(self, d: dict[str, Any]) -> bytes:
        from fpdf import FPDF
        from api.services.ServiceExport import get_logo_path, pdf_safe_text

        logo = get_logo_path()

        class _PvPDF(FPDF):
            def footer(self) -> None:
                self.set_y(-12)
                self.set_font("Helvetica", "BI", 8)
                self.set_text_color(200, 40, 40)
                self.cell(0, 5, pdf_safe_text(PV_FOOTER), align="C")

        pdf = _PvPDF(orientation="L", unit="mm", format="A4")
        pdf.set_auto_page_break(auto=True, margin=16)
        pdf.set_margins(10, 10, 10)
        pdf.add_page()

        width = pdf.w - pdf.l_margin - pdf.r_margin
        self._header(pdf, pdf_safe_text, logo, width)
        self._band(pdf, pdf_safe_text, width, "RESERVEE A L'INFORMATIQUE")
        self._reception(pdf, pdf_safe_text, width, d)
        self._affectation(pdf, pdf_safe_text, width, d)
        self._traitement(pdf, pdf_safe_text, width, d)
        self._emargement(pdf, pdf_safe_text, width, d)
        return bytes(pdf.output())

    @staticmethod
    def _header(pdf, safe, logo, width: float) -> None:
        """Cartouche réglementaire : logo | processus + titre | réf/version/date."""
        top = pdf.get_y()
        h = 20.0
        logo_w, ref_w = 40.0, 70.0
        mid_w = width - logo_w - ref_w

        pdf.set_draw_color(*_LINE)
        pdf.rect(pdf.l_margin, top, logo_w, h)
        pdf.rect(pdf.l_margin + logo_w, top, mid_w, h)
        pdf.rect(pdf.l_margin + logo_w + mid_w, top, ref_w, h)

        if logo:
            pdf.image(str(logo), x=pdf.l_margin + 12, y=top + 4, w=16)

        pdf.set_xy(pdf.l_margin + logo_w, top + 3)
        pdf.set_font("Helvetica", "B", 11)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(mid_w, 6, safe(PV_PROCESS), align="C")
        pdf.set_xy(pdf.l_margin + logo_w, top + 11)
        pdf.set_font("Helvetica", "B", 12)
        pdf.cell(mid_w, 6, safe(PV_TITLE), align="C")

        pdf.set_font("Helvetica", "", 9)
        for i, line in enumerate((
            f"Ref : {PV_REF}", f"Version : {PV_VERSION}", f"Date : {PV_DATE}",
        )):
            pdf.set_xy(pdf.l_margin + logo_w + mid_w + 2, top + 2 + i * 5.5)
            pdf.cell(ref_w - 4, 5, safe(line))

        pdf.set_y(top + h + 3)

    @staticmethod
    def _band(pdf, safe, width: float, title: str) -> None:
        pdf.set_font("Helvetica", "BI", 9)
        pdf.set_fill_color(*_BAND)
        pdf.set_text_color(0, 0, 0)
        pdf.cell(width, 6, f"  {safe(title)}", fill=True, border=1,
                 new_x="LMARGIN", new_y="NEXT")
        pdf.ln(1)

    @staticmethod
    def _section(pdf, safe, title: str) -> None:
        pdf.set_font("Helvetica", "BI", 8.5)
        pdf.set_text_color(*_BLUE)
        pdf.cell(0, 5, safe(title), new_x="LMARGIN", new_y="NEXT")
        pdf.set_text_color(0, 0, 0)

    def _reception(self, pdf, safe, width: float, d: dict[str, Any]) -> None:
        self._section(pdf, safe, "Reception")
        top = pdf.get_y()
        pdf.set_font("Helvetica", "", 9)
        pdf.set_xy(pdf.l_margin + 2, top + 2)
        line = (
            f"Mail {_checkbox(d['received_by_mail'])}     "
            f"Telephone {_checkbox(d['received_by_phone'])}     "
            f"Service : {d['requester_service'] or '.' * 20}     "
            f"Responsable : {d['receiver_name'] or '.' * 18}     "
            f"Badge : {d['receiver_badge'] or '.' * 12}     "
            f"N Fiche : {d['ref']}"
        )
        pdf.multi_cell(width - 4, 5, safe(line))
        bottom = pdf.get_y() + 2
        pdf.set_draw_color(*_LINE)
        pdf.rect(pdf.l_margin, top, width, bottom - top)
        pdf.set_y(bottom + 2)

    def _affectation(self, pdf, safe, width: float, d: dict[str, Any]) -> None:
        self._section(pdf, safe, "Affectation")
        top = pdf.get_y()
        left_w = width * 0.55
        pdf.set_font("Helvetica", "", 9)

        left_lines = [
            # Département et Service sont des INFORMATIONS, pas des options : ils
            # portaient une case cochée dès que la valeur existait, ce qui n'avait
            # aucun sens sur le document imprimé.
            f"Departement : {d['handler_department'] or '.' * 22}",
            f"Service : {d['handler_service'] or '.' * 26}",
            # Les trois cases restent vides quand le traitant n'a aucun statut
            # renseigné : on ne présume pas d'un statut sur un document signé.
            f"{_checkbox(d['is_titulaire'])} Titulaire    "
            f"{_checkbox(d['is_prestataire'])} Prestataire    "
            f"{_checkbox(d['is_stagiaire'])} Stagiaire",
            f"Badge : {d['badge'] or '.' * 26}",
            # Signature du traitant : remplacée par la marque électronique dès
            # qu'il a terminé son intervention. Tant que ce n'est pas le cas, la
            # ligne à signer au stylo demeure.
            "Signature : " if d["it_signed"] else "Signature : ______________________",
        ]
        signature_row = len(left_lines) - 1
        for i, text in enumerate(left_lines):
            y = top + 2 + i * 5.5
            pdf.set_xy(pdf.l_margin + 2, y)
            pdf.cell(left_w - 4, 5, safe(text))
            if i == signature_row and d["it_signed"]:
                # Surimpression : le ✓ vient de ZapfDingbats, le libellé reste en
                # Helvetica — deux polices ne peuvent pas cohabiter dans un
                # `cell()`. On le place juste après le texte, dont on mesure la
                # largeur réelle plutôt que de la deviner.
                pdf.set_font("Helvetica", "", 9)
                offset = pdf.get_string_width(safe(text))
                self._sign_mark(pdf, safe, pdf.l_margin + 2 + offset - 3, y - 1.5, 5,
                                signed=True)

        right_lines = [
            f"Lieu : {d['place'] or '.' * 30}",
            f"Date : {d['assignment_date'] or '.' * 14}     "
            # Durée réelle de l'intervention (début → fin). Le SLA contractuel
            # reste disponible dans `sla_hours` mais n'est pas ce que le
            # formulaire demande ici.
            f"Delai d'execution : {d['intervention_duration'] or '.' * 8}",
            f"Date Debut : {d['start_date'] or '..........'}     "
            f"Heure Debut : {d['start_time'] or '.....'}",
            f"Date Fin : {d['end_date'] or '..........'}     "
            f"Heure Fin : {d['end_time'] or '.....'}",
        ]
        for i, text in enumerate(right_lines):
            pdf.set_xy(pdf.l_margin + left_w + 2, top + 2 + i * 5.5)
            pdf.cell(width - left_w - 4, 5, safe(text))

        height = 2 + max(len(left_lines), len(right_lines)) * 5.5 + 2
        pdf.set_draw_color(*_LINE)
        pdf.rect(pdf.l_margin, top, width, height)
        pdf.line(pdf.l_margin + left_w, top, pdf.l_margin + left_w, top + height)
        pdf.set_y(top + height + 2)

    def _traitement(self, pdf, safe, width: float, d: dict[str, Any]) -> None:
        self._section(pdf, safe, "Traitement")
        top = pdf.get_y()
        pdf.set_xy(pdf.l_margin + 2, top + 2)

        blocks: list[tuple[str, str]] = []
        if d["field_check"]:
            label = "Constat (ecart avec la demande)" if d["field_check_gap"] else "Constat (conforme)"
            blocks.append((label, d["field_check"]))
        if d["work_done"]:
            blocks.append(("Travail realise", d["work_done"]))
        if d["solution"]:
            blocks.append(("Solution appliquee", d["solution"]))
        if d["recommendations"]:
            blocks.append(("Recommandations", d["recommendations"]))

        if not blocks:
            pdf.set_font("Helvetica", "I", 9)
            pdf.set_text_color(120, 120, 120)
            pdf.multi_cell(width - 4, 5, safe("Intervention non encore documentee."))
            pdf.set_text_color(0, 0, 0)
        for label, value in blocks:
            pdf.set_x(pdf.l_margin + 2)
            pdf.set_font("Helvetica", "B", 8.5)
            pdf.cell(width - 4, 5, safe(label), new_x="LMARGIN", new_y="NEXT")
            pdf.set_x(pdf.l_margin + 2)
            pdf.set_font("Helvetica", "", 9)
            pdf.multi_cell(width - 4, 5, safe(value), new_x="LMARGIN", new_y="NEXT")

        bottom = max(pdf.get_y() + 2, top + 26)
        pdf.set_draw_color(*_LINE)
        pdf.rect(pdf.l_margin, top, width, bottom - top)
        pdf.set_y(bottom + 2)

    @staticmethod
    def _sign_mark(pdf, safe, x: float, y: float, row_h: float, *,
                   signed: bool, note: str = "") -> None:
        """Marque d'émargement électronique dans une case déjà dessinée.

        Rien n'est imprimé si l'acte n'a pas eu lieu : une case vide reste une
        case à signer au stylo, elle ne doit jamais laisser croire à un accord.

        `3` est le code du ✓ (U+2713) dans ZapfDingbats — police standard du
        format PDF, donc aucun fichier à embarquer.
        """
        if not signed:
            return
        # Le curseur doit être rendu tel quel : la boucle appelante lit
        # `pdf.get_y()` pour placer la ligne suivante, et une surimpression qui
        # laisse le curseur ailleurs décale tout le tableau (les marques se
        # retrouvaient dans la ligne « Date »).
        saved_x, saved_y = pdf.get_x(), pdf.get_y()
        pdf.set_text_color(0, 128, 0)
        pdf.set_font("ZapfDingbats", "", 11)
        pdf.set_xy(x + 3, y + (row_h / 2) - 3)
        pdf.cell(6, 6, "3")
        if note:
            pdf.set_font("Helvetica", "I", 7.5)
            pdf.set_text_color(90, 90, 90)
            pdf.set_xy(x + 10, y + (row_h / 2) - 2.5)
            pdf.cell(30, 5, safe(note))
        pdf.set_text_color(0, 0, 0)
        pdf.set_font("Helvetica", "", 9)
        pdf.set_xy(saved_x, saved_y)

    def _emargement(self, pdf, safe, width: float, d: dict[str, Any]) -> None:
        """Émargement et appréciations — un ✓ marque chaque validation acquise
        dans l'application ; la zone reste vierge tant qu'elle ne l'est pas."""
        top = pdf.get_y()
        label_w = width * 0.18
        col_w = (width - label_w) / 2
        row_h = 12.0

        pdf.set_draw_color(*_LINE)
        pdf.set_font("Helvetica", "BI", 8.5)
        pdf.set_fill_color(214, 240, 245)
        pdf.set_xy(pdf.l_margin, top)
        pdf.cell(label_w, 6, "", border=1, fill=True)
        pdf.cell(col_w, 6, safe("  Responsable IT"), border=1, fill=True)
        pdf.cell(col_w, 6, safe("  Requerant"), border=1, fill=True,
                 new_x="LMARGIN", new_y="NEXT")

        for label, left, right in (
            ("Emargement", "", ""),
            ("Date", d["resolved_at"], d["appreciation_date"]),
        ):
            y = pdf.get_y()
            pdf.set_font("Helvetica", "BI", 8.5)
            pdf.set_fill_color(214, 240, 245)
            pdf.set_xy(pdf.l_margin, y)
            pdf.cell(label_w, row_h, safe(f"  {label}"), border=1, fill=True)
            pdf.set_font("Helvetica", "", 9)
            pdf.set_fill_color(255, 255, 255)
            pdf.cell(col_w, row_h, safe(f"  {left}"), border=1)
            pdf.cell(col_w, row_h, safe(f"  {right}"), border=1,
                     new_x="LMARGIN", new_y="NEXT")

            # Émargement électronique — surimprimé APRÈS les cellules : le ✓ doit
            # être tracé en ZapfDingbats (seule police du PDF de base à porter ce
            # glyphe ; Helvetica est limitée au Latin-1 et rendrait un « ? »),
            # tandis que la mention reste en Helvetica. Deux polices sur une même
            # ligne imposent donc d'écrire par-dessus plutôt que dans la cellule.
            if label == "Emargement":
                self._sign_mark(pdf, safe, pdf.l_margin + label_w, y, row_h,
                                signed=d["it_signed"], note="")
                self._sign_mark(pdf, safe, pdf.l_margin + label_w + col_w, y, row_h,
                                signed=d["requester_signed"],
                                note="(automatique)" if d["requester_signed_auto"] else "")

        y = pdf.get_y()
        rating = d["appreciation_rating"]
        note = f"Note : {rating}/5" if rating else ""
        text = " - ".join(p for p in (note, d["appreciation_comment"]) if p)
        # Libellé sur deux lignes ("Appreciations du" / "Requerant") comme sur le
        # formulaire : la cellule est dessinée vide, puis le texte est positionné
        # ligne par ligne — écrire deux `cell()` au même y les superposerait.
        pdf.set_fill_color(214, 240, 245)
        pdf.set_xy(pdf.l_margin, y)
        pdf.cell(label_w, row_h, "", border=1, fill=True)
        pdf.set_font("Helvetica", "BI", 8.5)
        for i, line in enumerate(("Appreciations du", "Requerant")):
            pdf.set_xy(pdf.l_margin + 2, y + 2 + i * 4.5)
            pdf.cell(label_w - 4, 4.5, safe(line))
        pdf.set_font("Helvetica", "", 9)
        pdf.set_fill_color(255, 255, 255)
        pdf.set_xy(pdf.l_margin + label_w, y)
        pdf.cell(width - label_w, row_h, safe(f"  {text}"), border=1,
                 new_x="LMARGIN", new_y="NEXT")
