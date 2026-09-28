"""
Service d'envoi SMS via une passerelle HTTP générique.

Protocole attendu (configurable via .env) :
  POST SMS_GATEWAY_URL
  Authorization: Bearer SMS_API_KEY
  Content-Type: application/json
  {"to": "<numéro>", "from": "<sender>", "message": "<corps>"}

La réponse HTTP 2xx est considérée comme un succès.
Si SMS_GATEWAY_URL est vide, l'envoi est silencieusement ignoré.
"""
from __future__ import annotations

import logging

import httpx

from api.configs.Environment import get_environment

logger = logging.getLogger(__name__)


async def send_sms(
    *,
    to: str,
    message: str,
) -> bool:
    """
    Envoie un SMS au numéro `to`.
    Retourne True si l'envoi a réussi, False sinon (erreur ou désactivé).
    """
    env = get_environment()
    if not env.SMS_GATEWAY_URL:
        logger.debug("ServiceSMS : SMS_GATEWAY_URL non configuré — envoi ignoré.")
        return False

    # Le coupe-circuit CommunicationSetting.sms_on et l'expéditeur surchargeable
    # ont été retirés le 2026-09-24 : l'expéditeur vient de SMS_SENDER (.env) et
    # l'envoi se coupe en vidant SMS_GATEWAY_URL.
    sender = env.SMS_SENDER

    payload = {
        "to": to,
        "from": sender,
        "message": message,
    }
    headers: dict[str, str] = {"Content-Type": "application/json"}
    if env.SMS_API_KEY:
        headers["Authorization"] = f"Bearer {env.SMS_API_KEY}"

    try:
        async with httpx.AsyncClient(timeout=10.0) as client:
            resp = await client.post(env.SMS_GATEWAY_URL, json=payload, headers=headers)
            resp.raise_for_status()
            logger.info("ServiceSMS : SMS envoyé à %s (status %d).", to, resp.status_code)
            return True
    except httpx.HTTPStatusError as exc:
        logger.warning(
            "ServiceSMS : erreur HTTP %d pour %s : %s",
            exc.response.status_code, to, exc.response.text[:200],
        )
    except Exception as exc:
        logger.warning("ServiceSMS : envoi échoué pour %s : %s", to, exc)

    return False
