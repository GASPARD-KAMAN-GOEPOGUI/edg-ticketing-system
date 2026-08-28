"""
Service d'export de rapports — EDG Support.
Formats supportés : CSV, Excel (xlsx), PDF.
"""
from __future__ import annotations

import csv
import io
import logging
from datetime import date, datetime
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)

ExportFormat = Literal["csv", "excel", "pdf"]

# Caractères "typographiques" hors Latin-1 (polices de base fpdf2/PDF) —
# transposés vers leur équivalent ASCII le plus proche. Tout le reste
# d'irreprésentable (emoji, autres scripts) est neutralisé en aval par
# l'encode/decode latin-1 de pdf_safe_text() plutôt que de faire planter
# l'export sur un contenu utilisateur imprévisible (titre, commentaire...).
_PDF_CHAR_MAP = {
    "—": "-", "–": "-",       # tiret cadratin/demi-cadratin — –
    "‘": "'", "’": "'",       # apostrophes courbes ' '
    "“": '"', "”": '"',       # guillemets courbes " "
    "…": "...",                    # points de suspension …
    " ": " ",                      # espace insécable
}


def pdf_safe_text(value: Any) -> str:
    """Neutralise tout caractère non supporté par les polices de base fpdf2
    (Latin-1 uniquement) — nécessaire car le contenu exporté (titres,
    commentaires, motifs...) est du texte libre saisi par les utilisateurs,
    jamais garanti Latin-1 (tiret cadratin, guillemets courbes, emoji...)."""
    text = "" if value is None else str(value)
    for src, dst in _PDF_CHAR_MAP.items():
        text = text.replace(src, dst)
    return text.encode("latin-1", errors="replace").decode("latin-1")


def get_logo_path() -> Path | None:
    """Chemin du logo EDG — réutilise l'asset frontend existant (même pattern
    que core/mailer.py pour l'en-tête des emails), aucune copie dupliquée."""
    path = Path(__file__).resolve().parents[3] / "frontend" / "src" / "assets" / "edg_logo.png"
    return path if path.exists() else None


def make_branded_pdf(doc_title: str):
    """Crée un document FPDF avec logo EDG en en-tête + filigrane sur chaque
    page (paysage A4). Utilisé par les exports qui veulent ce branding (ex.
    dossier de ticket) ; n'affecte pas export_pdf() ci-dessus, qui reste
    volontairement inchangé pour les rapports existants.

    fpdf2 n'expose header()/footer() que via une sous-classe de FPDF — définie
    ici (dans la fonction, pas au niveau module) pour garder l'import de fpdf2
    paresseux, comme export_pdf() ci-dessus."""
    try:
        from fpdf import FPDF
    except ImportError:
        raise RuntimeError("fpdf2 requis pour les exports PDF. pip install fpdf2")

    logo_path = get_logo_path()
    safe_title = pdf_safe_text(doc_title)

    class _BrandedPDF(FPDF):
        def header(self) -> None:
            logo_bottom_y = 8.0
            if logo_path:
                wm_w = 130.0
                with self.local_context(fill_opacity=0.07):
                    self.image(str(logo_path), x=(self.w - wm_w) / 2, y=(self.h - wm_w) / 2, w=wm_w)
                logo_y = 8.0
                info = self.image(str(logo_path), x=10, y=logo_y, w=16)
                # Hauteur réelle rendue (dépend du ratio du fichier logo) — évite de
                # figer une hauteur supposée : la ligne de séparation ci-dessous doit
                # passer sous le logo entier, jamais le traverser.
                logo_bottom_y = logo_y + info.rendered_height
            self.set_xy(0, 10)
            self.set_font("Helvetica", "B", 14)
            self.set_text_color(26, 82, 118)
            self.cell(self.w, 7, safe_title, align="C")
            self.set_xy(0, 17)
            self.set_font("Helvetica", "", 8)
            self.set_text_color(120, 120, 120)
            self.cell(self.w, 5, pdf_safe_text("EDG Support — Électricité de Guinée"), align="C")
            self.set_y(max(24.0, logo_bottom_y + 2.0))
            self.set_draw_color(26, 82, 118)
            self.set_line_width(0.4)
            self.line(10, self.get_y(), self.w - 10, self.get_y())
            self.ln(4)

        def footer(self) -> None:
            self.set_y(-14)
            self.set_font("Helvetica", "I", 7)
            self.set_text_color(150, 150, 150)
            stamp = datetime.now().strftime("%d/%m/%Y à %H:%M")
            self.cell(0, 5, pdf_safe_text(f"Page {self.page_no()}/{{nb}} — Généré le {stamp}"), align="C")

    pdf = _BrandedPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=18)
    pdf.set_margins(10, 10, 10)
    pdf.alias_nb_pages()
    return pdf


# ── CSV ───────────────────────────────────────────────────────────────────────

def export_csv(rows: list[dict], columns: list[str]) -> bytes:
    """Génère un fichier CSV à partir d'une liste de dicts."""
    buf = io.StringIO()
    writer = csv.DictWriter(buf, fieldnames=columns, extrasaction="ignore")
    writer.writeheader()
    for row in rows:
        writer.writerow({k: _fmt(row.get(k)) for k in columns})
    return buf.getvalue().encode("utf-8-sig")  # BOM pour Excel


# ── Excel ─────────────────────────────────────────────────────────────────────

def export_excel(
    rows: list[dict],
    columns: list[str],
    headers: list[str] | None = None,
    sheet_name: str = "Rapport",
    title: str = "Rapport EDG",
) -> bytes:
    """Génère un fichier Excel (.xlsx) avec mise en forme basique."""
    try:
        from openpyxl import Workbook
        from openpyxl.styles import Alignment, Font, PatternFill
        from openpyxl.utils import get_column_letter
    except ImportError:
        raise RuntimeError("openpyxl requis pour les exports Excel. pip install openpyxl")

    wb = Workbook()
    ws = wb.active
    ws.title = sheet_name[:31]

    header_labels = headers or columns

    # Titre
    ws.merge_cells(f"A1:{get_column_letter(len(columns))}1")
    title_cell = ws["A1"]
    title_cell.value = title
    title_cell.font = Font(bold=True, size=13)
    title_cell.alignment = Alignment(horizontal="center")

    # Date génération
    ws.merge_cells(f"A2:{get_column_letter(len(columns))}2")
    date_cell = ws["A2"]
    date_cell.value = f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}"
    date_cell.alignment = Alignment(horizontal="center")
    date_cell.font = Font(italic=True, size=9)

    # En-têtes colonnes (ligne 4)
    header_fill = PatternFill("solid", fgColor="1A5276")
    header_font = Font(bold=True, color="FFFFFF")
    for col_idx, label in enumerate(header_labels, start=1):
        cell = ws.cell(row=4, column=col_idx, value=label)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center")

    # Données
    alt_fill = PatternFill("solid", fgColor="EBF5FB")
    for row_idx, row in enumerate(rows, start=5):
        for col_idx, col in enumerate(columns, start=1):
            cell = ws.cell(row=row_idx, column=col_idx, value=_fmt(row.get(col)))
            if row_idx % 2 == 0:
                cell.fill = alt_fill
            cell.alignment = Alignment(horizontal="left")

    # Largeur auto des colonnes
    for col_idx in range(1, len(columns) + 1):
        letter = get_column_letter(col_idx)
        max_len = max(
            (len(str(ws.cell(row=r, column=col_idx).value or "")) for r in range(4, 5 + len(rows))),
            default=8,
        )
        ws.column_dimensions[letter].width = min(max_len + 4, 50)

    buf = io.BytesIO()
    wb.save(buf)
    return buf.getvalue()


# ── PDF ───────────────────────────────────────────────────────────────────────

def export_pdf(
    rows: list[dict],
    columns: list[str],
    headers: list[str] | None = None,
    title: str = "Rapport EDG",
    subtitle: str = "",
) -> bytes:
    """Génère un fichier PDF simple via fpdf2."""
    try:
        from fpdf import FPDF
    except ImportError:
        raise RuntimeError("fpdf2 requis pour les exports PDF. pip install fpdf2")

    header_labels = headers or columns

    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()

    # En-tête
    pdf.set_font("Helvetica", "B", 16)
    pdf.set_text_color(26, 82, 118)
    pdf.cell(0, 10, title, ln=True, align="C")

    if subtitle:
        pdf.set_font("Helvetica", "I", 10)
        pdf.set_text_color(100, 100, 100)
        pdf.cell(0, 6, subtitle, ln=True, align="C")

    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(150, 150, 150)
    pdf.cell(0, 5, f"Généré le {datetime.now().strftime('%d/%m/%Y à %H:%M')}", ln=True, align="C")
    pdf.ln(4)

    # Calcul largeur colonnes
    page_w = pdf.w - 2 * pdf.l_margin
    col_w = page_w / max(len(columns), 1)
    col_w = min(col_w, 55)

    # En-têtes tableau
    pdf.set_font("Helvetica", "B", 8)
    pdf.set_fill_color(26, 82, 118)
    pdf.set_text_color(255, 255, 255)
    for label in header_labels:
        pdf.cell(col_w, 8, str(label)[:20], border=1, align="C", fill=True)
    pdf.ln()

    # Données
    pdf.set_font("Helvetica", "", 8)
    pdf.set_text_color(0, 0, 0)
    for i, row in enumerate(rows):
        if i % 2 == 0:
            pdf.set_fill_color(235, 245, 251)
        else:
            pdf.set_fill_color(255, 255, 255)
        for col in columns:
            val = str(_fmt(row.get(col)) or "")[:25]
            pdf.cell(col_w, 7, val, border=1, align="L", fill=True)
        pdf.ln()

    pdf.set_font("Helvetica", "I", 8)
    pdf.set_text_color(120, 120, 120)
    pdf.ln(3)
    pdf.cell(0, 5, f"Total : {len(rows)} ligne(s)", ln=True)

    return pdf.output()


# ── Utilitaire ────────────────────────────────────────────────────────────────

def _fmt(val: Any) -> Any:
    if isinstance(val, (datetime, date)):
        return val.strftime("%d/%m/%Y %H:%M") if isinstance(val, datetime) else val.strftime("%d/%m/%Y")
    if val is None:
        return ""
    return val


def build_response(content: bytes, fmt: ExportFormat, filename: str):
    """Construit une FastAPI Response avec les bons headers."""
    from fastapi.responses import Response

    mime_map = {
        "csv": "text/csv",
        "excel": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "pdf": "application/pdf",
    }
    ext_map = {"csv": "csv", "excel": "xlsx", "pdf": "pdf"}
    media_type = mime_map[fmt]
    fname = f"{filename}.{ext_map[fmt]}"
    return Response(
        content=content,
        media_type=media_type,
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )
