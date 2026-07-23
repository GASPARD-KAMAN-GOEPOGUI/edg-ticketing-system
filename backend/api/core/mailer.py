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
from datetime import datetime
from html import escape
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from api.configs.Environment import get_environment

logger = logging.getLogger(__name__)
_env = get_environment()


def _is_configured() -> bool:
    return bool(_env.SMTP_HOST and _env.SMTP_USER and _env.SMTP_PASSWORD)


def _p(text: str) -> str:
    """Convertit un texte libre en HTML sûr avec conservation des retours ligne."""
    return "<br>".join(escape(text or "").splitlines())


def _render_edg_email(
    *,
    title: str,
    greeting_name: str = "",
    intro: str = "",
    main_html: str = "",
    action_url: str | None = None,
    action_label: str = "Voir la demande",
    warning: str | None = None,
    footer_year: str | None = None,
) -> str:
    year = footer_year or str(datetime.now().year)
    greeting = f"Bonjour <strong>{escape(greeting_name)}</strong>," if greeting_name else "Bonjour,"
    action_block = ""
    if action_url:
        action_block = f"""
                        <table width="100%" cellpadding="0" cellspacing="0" style="margin:24px 0;">
                            <tr>
                                <td align="center">
                                    <a href="{escape(action_url, quote=True)}"
                                       style="background:#009E24FA;color:#ffffff;text-decoration:none;
                                              padding:14px 0;border-radius:30px;font-size:14px;
                                              font-weight:600;display:block;width:100%;max-width:260px;
                                              box-shadow:0 4px 10px rgba(0,158,36,0.25);text-align:center;">
                                        {escape(action_label)}
                                    </a>
                                </td>
                            </tr>
                        </table>"""

    warning_block = ""
    if warning:
        warning_block = f"""
                        <table width="100%" cellpadding="0" cellspacing="0"
                               style="background:#fff7ed;border-left:5px solid #f59e0b;border-radius:8px;">
                            <tr>
                                <td style="padding:14px;color:#92400e;font-size:13px;line-height:1.5;">
                                    <strong>Important :</strong><br>
                                    {_p(warning)}
                                </td>
                            </tr>
                        </table>"""

    return f"""<!DOCTYPE html>
<html lang="fr">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>{escape(title)}</title>
</head>
<body style="margin:0;padding:0;background-color:#f4fdf7;">
<table width="100%" cellpadding="0" cellspacing="0" style="padding:10px;background-color:#f4fdf7;">
    <tr>
        <td align="center">
            <table width="100%" cellpadding="0" cellspacing="0"
                   style="max-width:600px;background:#ffffff;border-radius:12px;overflow:hidden;font-family:Arial,sans-serif;border:1px solid #dcefe2;">
                <tr>
                    <td style="background:#009E24FA;color:#ffffff;padding:20px 16px;text-align:center;">
                        <h2 style="margin:0;font-weight:700;font-size:20px;">EDG Connect</h2>
                        <p style="margin:6px 0 0;color:rgba(255,255,255,0.86);font-size:13px;">
                            Portail de gestion des demandes
                        </p>
                    </td>
                </tr>
                <tr>
                    <td style="padding:20px 16px;color:#1f2937;font-size:14px;line-height:1.6;">
                        <p style="margin-top:0;">{greeting}</p>
                        <h3 style="margin:0 0 12px;color:#111827;font-size:18px;font-weight:700;">
                            {escape(title)}
                        </h3>
                        {f'<p style="margin:0 0 16px;color:#4b5563;">{_p(intro)}</p>' if intro else ''}
                        {main_html}
                        {action_block}
                        {warning_block}
                    </td>
                </tr>
                <tr>
                    <td style="background:#f9fafb;text-align:center;padding:14px;font-size:12px;color:#6b7280;border-top:1px solid #e5e7eb;">
                        <strong style="color:#009E24FA;">EDG Connect</strong> - Électricité de Guinée<br>
                        © {escape(year)} Tous droits réservés<br>
                        Cet email est automatique, merci de ne pas y répondre.
                    </td>
                </tr>
            </table>
        </td>
    </tr>
</table>
</body>
</html>"""


def _code_box(code: str) -> str:
    return f"""
                        <table width="100%" cellpadding="0" cellspacing="0"
                               style="margin:16px 0;border:2px dashed #009E24FA;background:#f0fff4;border-radius:10px;">
                            <tr>
                                <td style="padding:18px;text-align:center;">
                                    <div style="margin:0;color:#009E24FA;font-size:30px;font-weight:700;letter-spacing:6px;font-family:'Courier New',monospace;">
                                        {escape(code)}
                                    </div>
                                </td>
                            </tr>
                        </table>"""


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
    html = _render_edg_email(
        title="Réinitialisation du mot de passe",
        greeting_name=name,
        intro="Vous avez demandé une réinitialisation de votre mot de passe. Voici votre code de vérification à 6 chiffres :",
        main_html=_code_box(code),
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
) -> bool:
    """
    Envoie un email de notification générique (affectation, résolution, escalade…).
    Retourne False si SMTP non configuré.
    """
    if not _is_configured():
        return False

    html = _render_edg_email(
        title=title,
        greeting_name=recipient_name,
        intro=body,
        action_url=action_url,
        action_label=action_label,
    )

    msg = MIMEMultipart("alternative")
    msg["From"] = f"EDG Connect <{_env.SMTP_USER}>"
    msg["To"] = to_email
    msg["Subject"] = title
    msg.attach(MIMEText(html, "html", "utf-8"))
    try:
        await _smtp_send(msg)
        logger.info("Email notification envoyé à %r : %s", to_email, title)
        return True
    except Exception as exc:
        logger.warning("Echec email notification à %r : %s", to_email, exc)
        return False
