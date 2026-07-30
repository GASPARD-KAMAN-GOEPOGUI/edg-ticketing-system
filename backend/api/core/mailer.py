"""
Mailer EDG Connect — envoi d'emails transactionnels via SMTP async.

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
from email.mime.multipart import MIMEMultipart
from email.mime.image import MIMEImage
from email.mime.text import MIMEText
from pathlib import Path
from unicodedata import combining, normalize

from api.configs.Environment import get_environment

logger = logging.getLogger(__name__)
_env = get_environment()
_templates_dir = Path(__file__).resolve().parents[2] / "templates"
_logo_path = Path(__file__).resolve().parents[3] / "frontend" / "src" / "assets" / "edg_logo.png"

_EMAIL_VARIANTS = {
    "creation": {
        "template": "ticket_confirmation_creation.html",
        "number": "1",
        "color": "#008D24",
        "soft_color": "#eaf8ee",
        "icon": "&#10004;",
        "headline": "Votre demande a bien ete enregistree !",
        "subtitle": "Merci. Nous avons bien recu votre demande. Notre equipe va l'analyser dans les plus brefs delais.",
    },
    "received": {
        "template": "ticket_accuse_reception.html",
        "number": "2",
        "color": "#1d6fd8",
        "soft_color": "#eaf3ff",
        "icon": "&#9993;",
        "headline": "Nous avons bien recu votre demande",
        "subtitle": "Votre demande est en cours d'analyse par notre equipe support.",
    },
    "assigned": {
        "template": "ticket_affectation.html",
        "number": "3",
        "color": "#f28c00",
        "soft_color": "#fff3df",
        "icon": "&#128100;",
        "headline": "Votre demande a ete assignee",
        "subtitle": "Un agent a ete designe pour traiter votre demande.",
    },
    "status": {
        "template": "ticket_changement_statut.html",
        "number": "4",
        "color": "#f4b400",
        "soft_color": "#fff8d9",
        "icon": "&#128339;",
        "headline": "Mise a jour du statut de votre demande",
        "subtitle": "Le statut de votre demande a ete modifie.",
    },
    "validated": {
        "template": "ticket_validation.html",
        "number": "5",
        "color": "#008D24",
        "soft_color": "#eaf8ee",
        "icon": "&#128737;",
        "headline": "Votre demande a ete validee",
        "subtitle": "La solution proposee a ete validee.",
    },
    "resolved": {
        "template": "ticket_resolution.html",
        "number": "6",
        "color": "#0b9da8",
        "soft_color": "#e5fbfb",
        "icon": "&#9881;",
        "headline": "Votre demande a ete resolue",
        "subtitle": "L'agent a marque votre demande comme resolue.",
    },
    "closed": {
        "template": "ticket_cloture.html",
        "number": "7",
        "color": "#008D24",
        "soft_color": "#eaf8ee",
        "icon": "&#10004;",
        "headline": "Votre demande est cloturee",
        "subtitle": "Votre demande a ete cloturee avec succes.",
    },
    "reopened": {
        "template": "ticket_reouverture.html",
        "number": "8",
        "color": "#6f52d9",
        "soft_color": "#f1edff",
        "icon": "&#8635;",
        "headline": "Votre demande a ete rouverte",
        "subtitle": "Votre demande a ete rouverte pour traitement.",
    },
    "transfer": {
        "template": "ticket_transfert.html",
        "number": "9",
        "color": "#1d6fd8",
        "soft_color": "#eaf3ff",
        "icon": "&#8644;",
        "headline": "Votre demande a ete transferee",
        "subtitle": "Votre demande a ete transferee a une autre direction.",
    },
    "sla": {
        "template": "ticket_alerte_sla.html",
        "number": "10",
        "color": "#f4b400",
        "soft_color": "#fff8d9",
        "icon": "&#9888;",
        "headline": "Delai de traitement depasse",
        "subtitle": "Le delai de traitement de votre demande est depasse.",
    },
    "rejected": {
        "template": "ticket_rejet_annulation.html",
        "number": "11",
        "color": "#ef2f32",
        "soft_color": "#ffecec",
        "icon": "&#10005;",
        "headline": "Votre demande a ete rejetee",
        "subtitle": "Votre demande ne peut pas etre traitee.",
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


def _render_template(template_name: str, **context: object) -> str:
    data = {"year": datetime.now().year, **context}
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
            row = re.sub(r"{%\s*if\s+value\s*%}(.*?){%\s*endif\s*%}", r"\1", row, flags=re.DOTALL)
            border = index != len(visible_items) - 1
            row = re.sub(
                r"{%\s*if\s+not\s+loop\.last\s*%}(.*?){%\s*endif\s*%}",
                lambda border_match: border_match.group(1) if border else "",
                row,
                flags=re.DOTALL,
            )
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


def _attach_logo(msg: MIMEMultipart) -> None:
    if not _logo_path.exists():
        return
    try:
        with _logo_path.open("rb") as logo_file:
            logo = MIMEImage(logo_file.read())
        logo.add_header("Content-ID", "<edg-logo>")
        logo.add_header("Content-Disposition", "inline", filename="edg_logo.png")
        msg.attach(logo)
    except Exception as exc:
        logger.debug("Logo email non attache : %s", exc)


async def send_reset_code_email(to_email: str, code: str, name: str = "") -> bool:
    """
    Envoie le code de réinitialisation par email.
    Retourne True si envoyé, False si SMTP non configuré.
    Lance une exception si la connexion SMTP échoue.
    """
    if not _is_configured():
        logger.warning("SMTP non configuré — email non envoyé à %r", to_email)
        return False

    subject = "Votre code de réinitialisation EDG Connect"
    html = _render_template(
        "reset_code_email.html",
        title="Réinitialisation du mot de passe",
        greeting_name=name,
        intro="Vous avez demandé une réinitialisation de votre mot de passe. Voici votre code de vérification à 6 chiffres :",
        code=code,
        warning=(
            "Ce code est valable 15 minutes. Ne le partagez avec personne. "
            "Si vous n'avez pas demandé cette réinitialisation, ignorez cet email."
        ),
    )

    msg = MIMEMultipart("alternative")
    msg["From"] = f"EDG Connect <{_env.SMTP_USER}>"
    msg["To"] = to_email
    msg["Subject"] = subject
    msg.attach(MIMEText(html, "html", "utf-8"))

    import aiosmtplib  # import tardif — optionnel si non installé
    await aiosmtplib.send(
        msg,
        hostname=_env.SMTP_HOST,
        port=_env.SMTP_PORT,
        username=_env.SMTP_USER,
        password=_env.SMTP_PASSWORD,
        start_tls=True,
    )
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


async def send_notification_email(
    *,
    to_email: str,
    recipient_name: str = "",
    title: str,
    body: str,
    action_url: str | None = None,
    action_label: str = "Voir la demande",
    notification_type: str | None = None,
    request_details: dict[str, object] | None = None,
) -> bool:
    """
    Envoie un email de notification générique (affectation, résolution, escalade…).
    Retourne False si SMTP non configuré.
    """
    if not _is_configured():
        return False

    template_name, context = _notification_context(
        title=title,
        body=body,
        action_url=action_url,
        action_label=action_label,
        notification_type=notification_type,
        request_details=request_details,
    )
    html = _render_template(template_name, greeting_name=recipient_name, **context)

    msg = MIMEMultipart("related")
    msg_alt = MIMEMultipart("alternative")
    msg["From"] = f"EDG Connect <{_env.SMTP_USER}>"
    msg["To"] = to_email
    msg["Subject"] = title
    msg_alt.attach(MIMEText(html, "html", "utf-8"))
    msg.attach(msg_alt)
    _attach_logo(msg)
    try:
        await _smtp_send(msg)
        logger.info("Email notification envoyé à %r : %s", to_email, title)
        return True
    except Exception as exc:
        logger.warning("Echec email notification à %r : %s", to_email, exc)
        return False
