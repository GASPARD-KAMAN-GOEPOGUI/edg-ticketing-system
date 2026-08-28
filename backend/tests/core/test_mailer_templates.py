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


# ── 5. Emails de validation de compte (création / association) ────────────────
# Notification post-validation plateforme centrale — voir ServiceAccount.py
# (_dispatch_account_email) : les deux nouveaux templates ne sont qu'un
# {% include %} du template de base, mais leur contenu (action_url absent si
# CORS_ORIGINS vide) doit rester sans balise Jinja brute, comme les autres.

def test_account_created_email_renders_clean_sans_action_url():
    html = mailer._render_template(
        "account_created_email.html",
        title="Votre compte a été créé avec succès",
        color="#008D24",
        icon="&#10004;",
        headline="Compte créé avec succès",
        subtitle="Votre compte EDG Support a été créé et est maintenant actif.",
        details={"Adresse email": "nouveau@test.edg.gn"},
        action_url=None,
        action_label="Se connecter",
        support_email="support@edg-support.gn",
        support_phone="(+224) 153 456 789",
    )
    _assert_no_raw_template_syntax(html)
    assert "nouveau@test.edg.gn" in html


def test_account_associated_email_renders_clean_avec_action_url():
    html = mailer._render_template(
        "account_associated_email.html",
        title="Votre compte a été associé à l'application avec succès",
        color="#008D24",
        icon="&#10004;",
        headline="Association réussie",
        subtitle="Votre compte a été associé à l'application EDG Support avec succès.",
        details={"Adresse email": "existant@test.edg.gn"},
        action_url="http://localhost:5173/login",
        action_label="Accéder à l'application",
        support_email="support@edg-support.gn",
        support_phone="(+224) 153 456 789",
    )
    _assert_no_raw_template_syntax(html)
    assert "existant@test.edg.gn" in html
    assert "groupe" not in html.lower()


async def test_send_account_associated_email_content_ne_mentionne_jamais_groupe(monkeypatch):
    """Garde-fou §6 : le message d'association ne doit jamais employer le mot
    'groupe' — uniquement l'association à l'application, indépendamment du
    groupe central réel de l'utilisateur."""
    monkeypatch.setattr(mailer, "_is_configured", lambda: True)
    captured: dict = {}

    async def _fake_smtp_send(msg):
        captured["msg"] = msg

    monkeypatch.setattr(mailer, "_smtp_send", _fake_smtp_send)

    sent = await mailer.send_account_associated_email("guard@test.edg.gn", "Jean Dupont")
    assert sent is True

    # Structure MIME : related (logo inline en CID) > alternative > text/html —
    # voir mailer.py::_build_message(). Le HTML est donc 2 niveaux sous le message,
    # plus 1 niveau direct comme avant l'ajout du logo inline.
    html = captured["msg"].get_payload()[0].get_payload()[0].get_payload(decode=True).decode("utf-8")
    assert "groupe" not in html.lower()
    assert "associé" in html.lower()


# ── 6. Logo inline (Content-ID) ────────────────────────────────────────────────
# Remplace l'ancien data URI (non fiable — Gmail notamment n'affichait rien) par
# une pièce MIME inline référencée via cid: — voir mailer.py::_attach_logo().

def test_render_template_reference_le_logo_en_cid_pas_en_data_uri():
    html = mailer._render_template(
        "account_created_email.html",
        title="t", color="#000", icon="&#10004;", headline="h", subtitle="s",
        details={}, action_url=None, action_label="a",
        support_email="support@edg-support.gn", support_phone="(+224) 153 456 789",
    )
    assert f'src="cid:{mailer._LOGO_CID}"' in html
    assert "data:image" not in html


async def test_send_account_created_email_attache_le_logo_en_inline_pas_en_piece_jointe(monkeypatch):
    monkeypatch.setattr(mailer, "_is_configured", lambda: True)
    captured: dict = {}

    async def _fake_smtp_send(msg):
        captured["msg"] = msg

    monkeypatch.setattr(mailer, "_smtp_send", _fake_smtp_send)

    sent = await mailer.send_account_created_email("nouveau@test.edg.gn", "Jean Dupont")
    assert sent is True

    msg = captured["msg"]
    assert msg.get_content_type() == "multipart/related"

    # La pièce logo doit exister, porter le bon Content-ID, et être marquée
    # "inline" — jamais "attachment" (sinon Gmail l'affiche comme pièce jointe
    # téléchargeable en plus du corps, le problème que ce mécanisme évite).
    logo_parts = [
        part for part in msg.walk()
        if part.get_content_type() == "image/png"
    ]
    assert len(logo_parts) == 1
    logo_part = logo_parts[0]
    assert logo_part["Content-ID"] == f"<{mailer._LOGO_CID}>"
    assert logo_part.get_content_disposition() == "inline"
    assert logo_part.get_payload(decode=True) == mailer._logo_bytes()
