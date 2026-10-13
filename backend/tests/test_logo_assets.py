"""
Logo EDG des PDF (PV d'intervention, dossier de ticket) et des e-mails : le
fichier doit se trouver DANS le backend. En production le backend est déployé
seul (dépôt edg-connect-backend) — un chemin vers frontend/ n'y existe pas, et
les documents sortaient sans logo, sans aucune erreur.
"""
from __future__ import annotations

from pathlib import Path

from fpdf import FPDF

from api.core import mailer
from api.services.ServiceExport import get_logo_path, pdf_safe_text
from api.services.ServicePvIntervention import PvInterventionService

BACKEND_DIR = Path(__file__).resolve().parents[1]
PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


def test_logo_lives_inside_the_backend():
    logo = get_logo_path()
    assert logo is not None
    assert logo.resolve().is_relative_to(BACKEND_DIR)
    assert logo.read_bytes().startswith(PNG_MAGIC)


def test_mailer_uses_the_same_backend_logo():
    assert mailer._logo_path.resolve() == get_logo_path().resolve()
    saved = (mailer._logo_bytes_cache, mailer._logo_bytes_loaded)
    try:
        mailer._logo_bytes_loaded = False
        assert (mailer._logo_bytes() or b"").startswith(PNG_MAGIC)
    finally:
        mailer._logo_bytes_cache, mailer._logo_bytes_loaded = saved


def test_pv_header_embeds_the_logo_image():
    def header_pdf(logo) -> bytes:
        pdf = FPDF(orientation="L", unit="mm", format="A4")
        pdf.add_page()
        width = pdf.w - pdf.l_margin - pdf.r_margin
        PvInterventionService._header(pdf, pdf_safe_text, logo, width)
        return bytes(pdf.output())

    assert b"/Subtype /Image" in header_pdf(get_logo_path())
    assert b"/Subtype /Image" not in header_pdf(None)  # témoin : le test détecte bien l'absence
