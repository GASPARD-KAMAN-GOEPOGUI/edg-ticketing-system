"""
Service d'export de rapports — EDG Connect.
Formats supportés : CSV, Excel (xlsx), PDF.
"""
from __future__ import annotations

import csv
import io
import logging
from datetime import date, datetime
from typing import Any, Literal

logger = logging.getLogger(__name__)

ExportFormat = Literal["csv", "excel", "pdf"]


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
