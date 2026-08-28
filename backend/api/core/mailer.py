"""
Mailer EDG Support — envoi d'emails transactionnels via SMTP async.

Configuration requise dans .env :
    SMTP_HOST=smtp.gmail.com
    SMTP_PORT=587
    SMTP_USER=votre@gmail.com
    SMTP_PASSWORD=xxxx xxxx xxxx xxxx   # Mot de passe d'application Google

Si SMTP_HOST est vide, l'envoi est ignoré silencieusement (mode dev sans email).
"""
from __future__ import annotations

import logging
import re
from datetime import datetime
from html import escape
from email.mime.image import MIMEImage
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path
from unicodedata import combining, normalize

from api.configs.Environment import get_environment

logger = logging.getLogger(__name__)
_env = get_environment()
_templates_dir = Path(__file__).resolve().parents[2] / "templates"
_logo_path = Path(__file__).resolve().parents[3] / "frontend" / "src" / "assets" / "edg_logo.png"
_LOGO_CID = "edg_logo"

_EMAIL_VARIANTS = {
    "creation": {
        "template": "ticket_confirmation_creation.html",
        "number": "1",
        "color": "#008D24",
        "soft_color": "#eaf8ee",
        "icon": "&#10004;",
        "headline": "Votre ticket a bien ete enregistre !",
        "subtitle": "Merci. Nous avons bien recu votre ticket. Notre equipe va l'analyser dans les plus brefs delais.",
    },
    "received": {
        "template": "ticket_accuse_reception.html",
        "number": "2",
        "color": "#1d6fd8",
        "soft_color": "#eaf3ff",
        "icon": "&#9993;",
        "headline": "Nous avons bien recu votre ticket",
        "subtitle": "Votre ticket est en cours d'analyse par notre equipe support.",
    },
    "assigned": {
        "template": "ticket_affectation.html",
        "number": "3",
        "color": "#f28c00",
        "soft_color": "#fff3df",
        "icon": "&#128100;",
        "headline": "Votre ticket a ete assigne",
        "subtitle": "Un agent a ete designe pour traiter votre ticket.",
    },
    "status": {
        "template": "ticket_changement_statut.html",
        "number": "4",
        "color": "#f4b400",
        "soft_color": "#fff8d9",
        "icon": "&#128339;",
        "headline": "Mise a jour du statut de votre ticket",
        "subtitle": "Le statut de votre ticket a ete modifie.",
    },
    "validated": {
        "template": "ticket_validation.html",
        "number": "5",
        "color": "#008D24",
        "soft_color": "#eaf8ee",
        "icon": "&#128737;",
        "headline": "Votre ticket a ete valide",
        "subtitle": "La solution proposee a ete validee.",
    },
    "resolved": {
        "template": "ticket_resolution.html",
        "number": "6",
        "color": "#0b9da8",
        "soft_color": "#e5fbfb",
        "icon": "&#9881;",
        "headline": "Votre ticket a ete resolu",
        "subtitle": "L'agent a marque votre ticket comme resolu.",
    },
    "closed": {
        "template": "ticket_cloture.html",
        "number": "7",
        "color": "#008D24",
        "soft_color": "#eaf8ee",
        "icon": "&#10004;",
        "headline": "Votre ticket est cloture",
        "subtitle": "Votre ticket a ete cloture avec succes.",
    },
    "reopened": {
        "template": "ticket_reouverture.html",
        "number": "8",
        "color": "#6f52d9",
        "soft_color": "#f1edff",
        "icon": "&#8635;",
        "headline": "Votre ticket a ete rouvert",
        "subtitle": "Votre ticket a ete rouvert pour traitement.",
    },
    "transfer": {
        "template": "ticket_transfert.html",
        "number": "9",
        "color": "#1d6fd8",
        "soft_color": "#eaf3ff",
        "icon": "&#8644;",
        "headline": "Votre ticket a ete transfere",
        "subtitle": "Votre ticket a ete transfere a une autre direction.",
    },
    "sla": {
        "template": "ticket_alerte_sla.html",
        "number": "10",
        "color": "#f4b400",
        "soft_color": "#fff8d9",
        "icon": "&#9888;",
        "headline": "Delai de traitement depasse",
        "subtitle": "Le delai de traitement de votre ticket est depasse.",
    },
    "rejected": {
        "template": "ticket_rejet_annulation.html",
        "number": "11",
        "color": "#ef2f32",
        "soft_color": "#ffecec",
        "icon": "&#10005;",
        "headline": "Votre ticket a ete rejete",
        "subtitle": "Votre ticket ne peut pas etre traite.",
    },
    "payment": {
        "template": "ticket_recu_paiement.html",
        "number": "12",
        "color": "#008D24",
        "soft_color": "#eaf8ee",
        "icon": "&#128462;",
        "headline": "Paiement recu avec succes",
        "subtitle": "Nous avons bien recu votre paiement.",
    },
}
_GENERIC_VARIANT = {
    "template": "notification_email.html",
    "number": "",
    "color": "#008D24",
    "soft_color": "#eaf8ee",
    "icon": "&#8505;",
    "headline": "",
    "subtitle": "",
}


def _is_configured() -> bool:
    return bool(_env.SMTP_HOST and _env.SMTP_USER and _env.SMTP_PASSWORD)


_logo_bytes_cache: bytes | None = None
_logo_bytes_loaded = False


def _logo_bytes() -> bytes | None:
    """Octets bruts du logo, pour attache MIME inline (Content-ID) — voir
    _attach_logo(). Le data URI direct dans le HTML (essayé avant) n'était pas
    fiable : plusieurs clients mail (Gmail notamment) le bloquent/n'affichent
    rien. Le CID est la méthode standard, correctement affichée en corps
    d'email — à condition que Content-Disposition soit bien "inline" (pas
    "attachment") pour ne pas apparaître comme pièce jointe téléchargeable.
    Mis en cache (le fichier ne change pas en cours d'exécution)."""
    global _logo_bytes_cache, _logo_bytes_loaded
    if not _logo_bytes_loaded:
        _logo_bytes_loaded = True
        try:
            _logo_bytes_cache = _logo_path.read_bytes()
        except Exception as exc:
            logger.debug("Logo email non chargé : %s", exc)
            _logo_bytes_cache = None
    return _logo_bytes_cache


def _attach_logo(msg: MIMEMultipart) -> None:
    """Attache le logo en pièce inline (Content-ID), référencée dans le HTML via
    src="cid:edg_logo" (voir _render_template). Silencieux si le fichier logo
    est introuvable — l'email part quand même, juste sans logo."""
    data = _logo_bytes()
    if not data:
        return
    image = MIMEImage(data, _subtype="png")
    image.add_header("Content-ID", f"<{_LOGO_CID}>")
    image.add_header("Content-Disposition", "inline", filename="edg_logo.png")
    msg.attach(image)


def _build_message(*, to_email: str, subject: str, html: str) -> MIMEMultipart:
    """Construit le message MIME complet (HTML + logo inline) — source unique
    pour les 4 fonctions d'envoi, pour ne pas dupliquer la structure
    multipart/related + attache du logo à chaque endroit."""
    msg = MIMEMultipart("related")
    msg["From"] = f"EDG Support <{_env.SMTP_USER}>"
    msg["To"] = to_email
    msg["Subject"] = subject

    alt = MIMEMultipart("alternative")
    alt.attach(MIMEText(html, "html", "utf-8"))
    msg.attach(alt)

    _attach_logo(msg)
    return msg


def _render_template(template_name: str, **context: object) -> str:
    data = {"year": datetime.now().year, "logo_cid": f"cid:{_LOGO_CID}", **context}
    template = (_templates_dir / template_name).read_text(encoding="utf-8")
    template = re.sub(
        r'{%\s*include\s+"([^"]+)"\s*%}',
        lambda match: (_templates_dir / match.group(1)).read_text(encoding="utf-8"),
        template,
    )
    template = _render_details_loop(template, data.get("details") or {})
    template = _render_conditionals(template, data)
    return _render_variables(template, data)


def _render_details_loop(template: str, details: object) -> str:
    pattern = re.compile(
        r"{%\s*for\s+label,\s*value\s+in\s+details\.items\(\)\s*%}(.*?){%\s*endfor\s*%}",
        re.DOTALL,
    )
    if not isinstance(details, dict):
        details = {}

    def repl(match: re.Match[str]) -> str:
        row_template = match.group(1)
        rows: list[str] = []
        visible_items = [(key, value) for key, value in details.items() if value]
        for index, (label, value) in enumerate(visible_items):
            row = row_template
            # BR-EMAIL-TEMPLATE-001 — `{% if not loop.last %}` est imbriqué à
            # l'intérieur de `{% if value %}` dans le template de base. Ces
            # substitutions regex ne comprennent pas l'imbrication : chaque
            # `.*?{% endif %}` s'arrête au PREMIER `{% endif %}` rencontré, quel
            # que soit son propriétaire réel. Résoudre l'imbriqué (`not loop.last`)
            # AVANT l'englobant (`value`) est donc obligatoire — dans l'ordre
            # inverse, `{% if value %}` se referme sur le mauvais `{% endif %}`
            # (celui d'un `not loop.last`), laissant un `{% endif %}` orphelin
            # visible tel quel dans l'email final.
            border = index != len(visible_items) - 1
            row = re.sub(
                r"{%\s*if\s+not\s+loop\.last\s*%}(.*?){%\s*endif\s*%}",
                lambda border_match: border_match.group(1) if border else "",
                row,
                flags=re.DOTALL,
            )
            row = re.sub(r"{%\s*if\s+value\s*%}(.*?){%\s*endif\s*%}", r"\1", row, flags=re.DOTALL)
            row = row.replace("{{ label }}", escape(str(label)))
            row = row.replace("{{ value }}", escape(str(value)))
            rows.append(row)
        return "".join(rows)

    return pattern.sub(repl, template)


def _render_conditionals(template: str, context: dict[str, object]) -> str:
    pattern = re.compile(r"{%\s*if\s+([a-zA-Z_][a-zA-Z0-9_]*)\s*%}(.*?){%\s*endif\s*%}", re.DOTALL)
    previous = None
    while previous != template:
        previous = template
        template = pattern.sub(
            lambda match: match.group(2) if context.get(match.group(1)) else "",
            template,
        )
    return template


def _render_variables(template: str, context: dict[str, object]) -> str:
    def repl(match: re.Match[str]) -> str:
        key = match.group(1).strip()
        safe = False
        if "|" in key:
            key, filter_name = [part.strip() for part in key.split("|", 1)]
            safe = filter_name == "safe"
        value = context.get(key, "")
        text = "" if value is None else str(value)
        return text if safe else escape(text, quote=True)

    return re.sub(r"{{\s*([^}]+)\s*}}", repl, template)


def _strip_accents(value: str) -> str:
    return "".join(
        char for char in normalize("NFKD", value or "") if not combining(char)
    ).lower()


def _notification_key(title: str, body: str, notification_type: str | None = None) -> str:
    text = _strip_accents(f"{notification_type or ''} {title} {body}")
    if any(word in text for word in ("paiement", "recu de paiement")):
        return "payment"
    if any(word in text for word in ("sla", "delai", "retard", "escalade automatique")):
        return "sla"
    if any(word in text for word in ("rejet", "rejetee", "refusee", "refus", "annul")):
        return "rejected"
    if any(word in text for word in ("reouverture", "rouverte", "remis en traitement")):
        return "reopened"
    if any(word in text for word in ("transf", "reaffect")):
        return "transfer"
    if any(word in text for word in ("clotur", "fermeture", "fermee")):
        return "closed"
    if any(word in text for word in ("resolu", "resolution", "resolue")):
        return "resolved"
    if any(word in text for word in ("valid", "approuv")):
        return "validated"
    if "assign" in text:
        return "assigned"
    if any(word in text for word in ("statut", "mise a jour")):
        return "status"
    if any(word in text for word in ("recue", "recu", "support general", "qualifier", "a traiter")):
        return "received"
    if any(word in text for word in ("cree", "creation", "enregistree", "transmise")):
        return "creation"
    return "received"


def _notification_context(
    *,
    title: str,
    body: str,
    action_url: str | None,
    action_label: str,
    notification_type: str | None = None,
    request_details: dict[str, object] | None = None,
) -> tuple[str, dict[str, object]]:
    key = _notification_key(title, body, notification_type)
    variant = {**_GENERIC_VARIANT, **_EMAIL_VARIANTS.get(key, {})}
    details = dict(request_details or {})
    if not details:
        details = {"Objet": body}
    context = {
        **variant,
        "title": title,
        "body": body,
        "headline": variant.get("headline") or title,
        "subtitle": variant.get("subtitle") or body,
        "details": details,
        "action_url": action_url,
        "action_label": action_label,
        "support_email": "support@edg-support.gn",
        "support_phone": "(+224) 153 456 789",
    }
    return str(variant["template"]), context


def _app_login_url() -> str | None:
    """URL de connexion de l'application — dérivée de CORS_ORIGINS (première
    origine configurée), seule information d'URL publique déjà présente dans
    la configuration ; pas de variable d'environnement dédiée à ce jour."""
    origins = _env.CORS_ORIGINS
    if not origins:
        return None
    return f"{origins[0].rstrip('/')}/login"


async def send_account_created_email(to_email: str, name: str = "") -> bool:
    """
    Email A — compte nouvellement créé ET validé par la plateforme centrale
    (voir ServiceAccount.create()). Ne jamais appeler avant confirmation
    réelle de cette validation. Catch-and-log comme send_notification_email() :
    un échec d'envoi ne doit jamais remettre en cause la création du compte.
    """
    if not _is_configured():
        logger.warning("SMTP non configuré — email de création de compte non envoyé à %r", to_email)
        return False

    subject = "Votre compte a été créé avec succès"
    greeting = f"Bonjour {name}, v" if name else "V"
    login_url = _app_login_url()
    html = _render_template(
        "account_created_email.html",
        title=subject,
        color="#008D24",
        icon="&#10004;",
        headline="Compte créé avec succès",
        subtitle=(
            f"{greeting}otre compte EDG Support a été créé et est maintenant actif. "
            "Vous pouvez dès à présent vous connecter avec les identifiants choisis lors "
            "de votre inscription."
        ),
        details={"Adresse email": to_email},
        action_url=login_url,
        action_label="Se connecter",
        support_email="support@edg-support.gn",
        support_phone="(+224) 153 456 789",
    )

    msg = _build_message(to_email=to_email, subject=subject, html=html)

    try:
        await _smtp_send(msg)
        logger.info("Email de création de compte envoyé à %r", to_email)
        return True
    except Exception as exc:
        logger.warning("Echec email de création de compte à %r : %s", to_email, exc)
        return False


async def send_account_associated_email(to_email: str, name: str = "") -> bool:
    """
    Email B — compte central existant nouvellement associé à CETTE application
    (voir ServiceAccount.provision_from_central()), après validation centrale
    réelle (scopes/groupes revérifiés). Ne jamais parler de "groupe" ici — le
    message porte uniquement sur l'association à l'application.
    """
    if not _is_configured():
        logger.warning("SMTP non configuré — email d'association de compte non envoyé à %r", to_email)
        return False

    subject = "Votre compte a été associé à l'application avec succès"
    greeting = f"Bonjour {name}, v" if name else "V"
    login_url = _app_login_url()
    html = _render_template(
        "account_associated_email.html",
        title=subject,
        color="#008D24",
        icon="&#10004;",
        headline="Association réussie",
        subtitle=(
            f"{greeting}otre compte a été associé à l'application EDG Support avec succès. "
            "Vous pouvez dès à présent y accéder avec vos identifiants habituels."
        ),
        details={"Adresse email": to_email},
        action_url=login_url,
        action_label="Accéder à l'application",
        support_email="support@edg-support.gn",
        support_phone="(+224) 153 456 789",
    )

    msg = _build_message(to_email=to_email, subject=subject, html=html)

    try:
        await _smtp_send(msg)
        logger.info("Email d'association de compte envoyé à %r", to_email)
        return True
    except Exception as exc:
        logger.warning("Echec email d'association de compte à %r : %s", to_email, exc)
        return False


async def send_reset_code_email(to_email: str, code: str, name: str = "") -> bool:
    """
    Envoie le code de réinitialisation par email.
    Retourne True si envoyé, False si SMTP non configuré.
    Lance une exception si la connexion SMTP échoue.
    """
    if not _is_configured():
        logger.warning("SMTP non configuré — email non envoyé à %r", to_email)
        return False

    subject = "Votre code de réinitialisation EDG Support"
    greeting = f"Bonjour {name}, v" if name else "V"
    html = _render_template(
        "reset_code_email.html",
        title="Réinitialisation du mot de passe",
        color="#1d6fd8",
        icon="&#128273;",
        headline="Code de vérification",
        subtitle=(
            f"{greeting}oici le code à 6 chiffres pour réinitialiser votre mot de passe. "
            "Il est valable 15 minutes et ne doit être partagé avec personne. "
            "Si vous n'êtes pas à l'origine de cette demande, ignorez cet email."
        ),
        details={"Code de vérification": code, "Expire dans": "15 minutes"},
        support_email="support@edg-support.gn",
        support_phone="(+224) 153 456 789",
    )

    msg = _build_message(to_email=to_email, subject=subject, html=html)

    await _smtp_send(msg)
    logger.info("Email reset envoyé à %r", to_email)
    return True


async def _smtp_send(msg: MIMEMultipart) -> None:
    import aiosmtplib
    await aiosmtplib.send(
        msg,
        hostname=_env.SMTP_HOST,
        port=_env.SMTP_PORT,
        username=_env.SMTP_USER,
        password=_env.SMTP_PASSWORD,
        start_tls=True,
    )


def render_notification_html(
    *,
    title: str,
    body: str,
    recipient_name: str = "",
    action_url: str | None = None,
    action_label: str = "Voir le ticket",
    notification_type: str | None = None,
    request_details: dict[str, object] | None = None,
) -> str:
    """
    Rend le HTML final d'un email de notification ticket — sans envoi SMTP.
    Réutilisée par `send_notification_email()` (source unique de rendu) et par
    les tests (générer/valider le HTML avant tout envoi réel).
    """
    template_name, context = _notification_context(
        title=title,
        body=body,
        action_url=action_url,
        action_label=action_label,
        notification_type=notification_type,
        request_details=request_details,
    )
    return _render_template(template_name, greeting_name=recipient_name, **context)


async def send_notification_email(
    *,
    to_email: str,
    recipient_name: str = "",
    title: str,
    body: str,
    action_url: str | None = None,
    action_label: str = "Voir le ticket",
    notification_type: str | None = None,
    request_details: dict[str, object] | None = None,
) -> bool:
    """
    Envoie un email de notification générique (affectation, résolution, escalade…).
    Retourne False si SMTP non configuré.
    """
    if not _is_configured():
        return False

    html = render_notification_html(
        title=title,
        body=body,
        recipient_name=recipient_name,
        action_url=action_url,
        action_label=action_label,
        notification_type=notification_type,
        request_details=request_details,
    )

    msg = _build_message(to_email=to_email, subject=title, html=html)
    try:
        await _smtp_send(msg)
        logger.info("Email notification envoyé à %r : %s", to_email, title)
        return True
    except Exception as exc:
        logger.warning("Echec email notification à %r : %s", to_email, exc)
        return False
