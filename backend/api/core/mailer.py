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
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

from api.configs.Environment import get_environment

logger = logging.getLogger(__name__)
_env = get_environment()


def _is_configured() -> bool:
    return bool(_env.SMTP_HOST and _env.SMTP_USER and _env.SMTP_PASSWORD)


async def send_reset_code_email(to_email: str, code: str, name: str = "") -> bool:
    """
    Envoie le code de réinitialisation par email.
    Retourne True si envoyé, False si SMTP non configuré.
    Lance une exception si la connexion SMTP échoue.
    """
    if not _is_configured():
        logger.warning("SMTP non configuré — email non envoyé à %r", to_email)
        return False

    subject = "Votre code de réinitialisation EDG Services"
    greeting = f"Bonjour{' ' + name if name else ''},"
    html = f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f4f6fb;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6fb;padding:40px 0;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0"
             style="background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">

        <!-- En-tête -->
        <tr>
          <td style="background:linear-gradient(135deg,#2563eb,#1d4ed8);padding:32px 40px;text-align:center;">
            <h1 style="margin:0;color:#ffffff;font-size:22px;font-weight:700;letter-spacing:-0.3px;">
              ⚡ EDG Services
            </h1>
            <p style="margin:6px 0 0;color:rgba(255,255,255,0.75);font-size:13px;">
              Électricité de Guinée
            </p>
          </td>
        </tr>

        <!-- Corps -->
        <tr>
          <td style="padding:40px 40px 32px;">
            <p style="margin:0 0 12px;color:#1e293b;font-size:15px;">{greeting}</p>
            <p style="margin:0 0 24px;color:#475569;font-size:14px;line-height:1.6;">
              Vous avez demandé une réinitialisation de votre mot de passe.<br>
              Voici votre code de vérification à 6 chiffres&nbsp;:
            </p>

            <!-- Code -->
            <div style="background:#f1f5f9;border:2px dashed #2563eb;border-radius:12px;
                        padding:24px;text-align:center;margin:0 0 24px;">
              <span style="font-family:'Courier New',monospace;font-size:40px;font-weight:700;
                           color:#2563eb;letter-spacing:0.4em;">{code}</span>
            </div>

            <p style="margin:0 0 8px;color:#64748b;font-size:13px;line-height:1.6;">
              Ce code est valable <strong>15 minutes</strong>.
              Ne le partagez avec personne.
            </p>
            <p style="margin:0;color:#64748b;font-size:13px;line-height:1.6;">
              Si vous n'avez pas demandé cette réinitialisation, ignorez cet email —
              votre compte reste sécurisé.
            </p>
          </td>
        </tr>

        <!-- Pied de page -->
        <tr>
          <td style="background:#f8fafc;padding:20px 40px;border-top:1px solid #e2e8f0;">
            <p style="margin:0;color:#94a3b8;font-size:12px;text-align:center;">
              Électricité de Guinée (EDG) — Portail de gestion des demandes<br>
              Cet email est envoyé automatiquement, merci de ne pas y répondre.
            </p>
          </td>
        </tr>

      </table>
    </td></tr>
  </table>
</body>
</html>"""

    msg = MIMEMultipart("alternative")
    msg["From"] = f"EDG Services <{_env.SMTP_USER}>"
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

    greeting = f"Bonjour{' ' + recipient_name if recipient_name else ''},"
    action_block = ""
    if action_url:
        action_block = f"""
        <div style="margin:24px 0;text-align:center;">
          <a href="{action_url}"
             style="background:#2563eb;color:#ffffff;text-decoration:none;
                    padding:12px 28px;border-radius:8px;font-size:14px;font-weight:600;">
            {action_label}
          </a>
        </div>"""

    html = f"""<!DOCTYPE html>
<html lang="fr">
<head><meta charset="UTF-8"><meta name="viewport" content="width=device-width,initial-scale=1"></head>
<body style="margin:0;padding:0;background:#f4f6fb;font-family:'Segoe UI',Arial,sans-serif;">
  <table width="100%" cellpadding="0" cellspacing="0" style="background:#f4f6fb;padding:40px 0;">
    <tr><td align="center">
      <table width="560" cellpadding="0" cellspacing="0"
             style="background:#ffffff;border-radius:16px;overflow:hidden;box-shadow:0 4px 24px rgba(0,0,0,0.08);">
        <tr>
          <td style="background:linear-gradient(135deg,#2563eb,#1d4ed8);padding:28px 40px;text-align:center;">
            <h1 style="margin:0;color:#ffffff;font-size:20px;font-weight:700;">EDG Connect</h1>
            <p style="margin:4px 0 0;color:rgba(255,255,255,0.75);font-size:12px;">Électricité de Guinée — Support DSI</p>
          </td>
        </tr>
        <tr>
          <td style="padding:36px 40px 28px;">
            <p style="margin:0 0 8px;color:#1e293b;font-size:15px;">{greeting}</p>
            <h2 style="margin:0 0 12px;color:#1e293b;font-size:17px;font-weight:600;">{title}</h2>
            <p style="margin:0 0 20px;color:#475569;font-size:14px;line-height:1.7;">{body}</p>
            {action_block}
          </td>
        </tr>
        <tr>
          <td style="background:#f8fafc;padding:16px 40px;border-top:1px solid #e2e8f0;">
            <p style="margin:0;color:#94a3b8;font-size:12px;text-align:center;">
              EDG Connect — Portail de gestion des demandes DSI<br>
              Cet email est automatique, merci de ne pas y répondre.
            </p>
          </td>
        </tr>
      </table>
    </td></tr>
  </table>
</body>
</html>"""

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
