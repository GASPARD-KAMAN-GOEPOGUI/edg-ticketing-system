"""
Correction rendu template email ticket — EDG-SUP.

Couvre, sans envoi SMTP réel (`render_notification_html`, pur/synchrone) :
  - absence de toute balise Jinja brute ({% %}, {{ }}) dans le HTML final,
    pour les 12 variantes ticket + la variante générique ;
  - absence de la barre/badge numéroté (supprimé du template de base) ;
  - non-régression sur les 7 scénarios réels du cycle de vie d'un ticket
    (créé, assigné, transmis, résolu, réouvert, rejeté, clôturé), avec les
    titres réellement envoyés par ServiceRequest.py ;
  - le cas exact du bug rapporté : plusieurs lignes de détails visibles
    (comme sur la capture d'écran) ne doivent plus laisser de {% endif %}
    orphelin entre les lignes.

Ne touche ni SMTP, ni NotificationEmitter, ni le workflow ticket — ces tests
n'appellent que des fonctions pures de rendu HTML (api.core.mailer).
"""
from __future__ import annotations

import re

import pytest

from api.core import mailer

_SAMPLE_DETAILS = {
    "Numéro de ticket": "TSD-1343570260807-001",
    "Objet": "Test reopen-queue resume-workflow",
    "Service concerné": "Direction de Test",
    "Priorité": "Moyenne",
}

# Fingerprint CSS unique de l'ex-barre/badge (border-radius:8px, padding:4px 9px)
# — distinct du bouton CTA (border-radius:6px, padding:11px 22px) présent par
# ailleurs dans le même template, donc sans faux positif possible.
_BADGE_CSS_FINGERPRINT = "border-radius:8px;padding:4px 9px"

_ALL_VARIANTS = {**mailer._EMAIL_VARIANTS, "generic": mailer._GENERIC_VARIANT}

# Titres réels envoyés par ServiceRequest.py pour les 7 étapes du cycle de vie
# demandées (grep sur `title="..."`, vocabulaire "ticket" déjà en place côté
# émission — non modifié ici, uniquement vérifié).
_LIFECYCLE_SCENARIOS = {
    "created": ("Ticket créé", "Votre ticket a été enregistré avec succès."),
    "assigned": ("Ticket assigné", "Un agent a été désigné pour traiter votre ticket."),
    "transmitted": ("Ticket transmis", "Le traitement de votre ticket a été transmis."),
    "resolved": ("Ticket résolu", "Votre ticket a été marqué comme résolu."),
    "reopened": ("Ticket réouvert", "Votre ticket a été rouvert pour traitement."),
    "rejected": ("Ticket rejeté", "Votre ticket ne peut pas être traité en l'état."),
    "closed": ("Ticket clôturé", "Votre ticket a été clôturé avec succès."),
}


def _render_variant_directly(variant: dict, *, details: dict | None = None) -> str:
    context = {
        **variant,
        "title": variant["headline"] or "Notification",
        "body": variant["subtitle"] or "",
        "details": details if details is not None else dict(_SAMPLE_DETAILS),
        "action_url": "https://edg-support.example/app/requests/1",
        "action_label": "Voir le ticket",
        "support_email": "support@edg-support.gn",
        "support_phone": "(+224) 153 456 789",
        "greeting_name": "Fatoumata",
    }
    return mailer._render_template(variant["template"], **context)


def _assert_no_raw_template_syntax(html: str) -> None:
    assert "{%" not in html, "balise Jinja ouvrante brute trouvée dans le HTML rendu"
    assert "%}" not in html, "balise Jinja fermante brute (ex: {% endif %}) trouvée dans le HTML rendu"
    assert "{{" not in html, "variable Jinja brute trouvée dans le HTML rendu"


# ── 1. Les 12 variantes + la générique : aucune balise Jinja brute ─────────────

@pytest.mark.parametrize("key", sorted(_ALL_VARIANTS))
def test_ticket_email_variant_has_no_raw_jinja_tags(key):
    html = _render_variant_directly(_ALL_VARIANTS[key])
    _assert_no_raw_template_syntax(html)


# ── 2. Les 12 variantes : plus de barre/badge numéroté ─────────────────────────

@pytest.mark.parametrize("key", sorted(mailer._EMAIL_VARIANTS))
def test_ticket_email_variant_has_no_number_badge(key):
    html = _render_variant_directly(mailer._EMAIL_VARIANTS[key])
    assert _BADGE_CSS_FINGERPRINT not in html
    # Enchaînement visuel attendu : l'en-tête ("Plateforme de gestion des
    # tickets") se referme directement dans la ligne de l'icône de statut
    # (border-radius:50%), sans <tr> intermédiaire (l'ex-barre/badge).
    assert re.search(
        r"Plateforme de gestion des tickets\s*</td>\s*</tr>\s*</table>\s*</td>\s*</tr>\s*<tr>\s*<td[^>]*>\s*<div[^>]*border-radius:50%",
        html,
    ), "une ligne <tr> intermédiaire subsiste entre l'en-tête et l'icône de statut"


# ── 3. Cycle de vie réel du ticket (7 scénarios demandés) ──────────────────────

@pytest.mark.parametrize("scenario", sorted(_LIFECYCLE_SCENARIOS))
def test_ticket_lifecycle_email_renders_clean(scenario):
    title, body = _LIFECYCLE_SCENARIOS[scenario]
    html = mailer.render_notification_html(
        title=title,
        body=body,
        recipient_name="Fatoumata Conté",
        action_url="https://edg-support.example/app/requests/1",
        request_details=dict(_SAMPLE_DETAILS),
    )
    _assert_no_raw_template_syntax(html)
    assert _BADGE_CSS_FINGERPRINT not in html
    assert "ticket" in html.lower()


# ── 4. Reproduction exacte du bug rapporté (plusieurs lignes de détails) ──────

def test_multiple_detail_rows_leave_no_orphan_endif():
    """Capture d'écran d'origine : 4 lignes de détails, un {% endif %} restait
    visible après CHAQUE ligne (Numéro de ticket / Objet / Service / Priorité).
    """
    html = mailer.render_notification_html(
        title="Ticket créé",
        body="Test reopen-queue resume-workflow",
        request_details=dict(_SAMPLE_DETAILS),
    )
    _assert_no_raw_template_syntax(html)
    for label in _SAMPLE_DETAILS:
        assert label in html
    assert html.count("{% endif %}") == 0
    assert "endif" not in html


def test_single_detail_row_still_renders_correctly():
    """Cas de repli : un seul détail visible (ex. {"Objet": body}), le plus
    fréquent en pratique — ne doit pas non plus laisser de balise brute."""
    html = mailer.render_notification_html(
        title="Ticket créé",
        body="Ceci est le corps du message.",
    )
    _assert_no_raw_template_syntax(html)
    assert "Objet" in html
