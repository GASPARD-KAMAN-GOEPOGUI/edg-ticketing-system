from __future__ import annotations

import logging

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.event_bus import AppEvent, emit as emit_event
from api.repositories.RepositoryNotification import NotificationRepository

logger = logging.getLogger(__name__)


async def emit(
    session: AsyncSession,
    *,
    recipient_id: str | None,
    title: str,
    body: str,
    type: str = "info",
    channel: str = "in_app",
    request_id: str | None = None,
    action_label: str | None = None,
    action_url: str | None = None,
    visibility: str = "public",
    # SMS uniquement : numéro du destinataire (ex. "+224XXXXXXXX")
    sms_to: str | None = None,
) -> None:
    """
    Émet une notification.
    - channel='in_app' (défaut) : enregistrement en base + SSE
    - channel='sms' : envoi via ServiceSMS (nécessite sms_to)
    - channel='both' : in_app + SMS
    Silencieux si recipient_id est None/vide (sauf pour canal SMS seul).
    """
    send_inapp = channel in ("in_app", "both")
    send_sms_flag = channel in ("sms", "both")

    if send_inapp:
        if not recipient_id:
            pass  # notification in-app ignorée sans destinataire
        else:
            try:
                recipient_id_int = int(recipient_id)
            except (ValueError, TypeError):
                recipient_id_int = None

            if recipient_id_int:
                repo = NotificationRepository(session)
                obj = await repo.create({
                    "recipient_id": recipient_id_int,
                    "type": type,
                    "channel": "in_app",
                    "title": title,
                    "body": body,
                    "request_id": request_id,
                    "action_label": action_label,
                    "action_url": action_url,
                    "visibility": visibility,
                })
                await emit_event(AppEvent(
                    type="notification.created",
                    payload={
                        "id": obj.id,
                        "request_id": request_id,
                        "title": title,
                        "type": type,
                    },
                    target={"user_ids": [recipient_id_int]},
                ))

                # Email automatique si email_on=True dans CommunicationSetting
                try:
                    from sqlalchemy import select as _select
                    from api.models.ModelCommunicationSetting import CommunicationSetting
                    from api.models.ModelAccount import Account
                    from api.core.mailer import send_notification_email

                    cs_row = await session.execute(_select(CommunicationSetting).limit(1))
                    cs = cs_row.scalar_one_or_none()
                    if cs is None or cs.email_on:
                        acc_row = await session.execute(
                            _select(Account.email, Account.name, Account.firstname)
                            .where(Account.id == recipient_id_int)
                        )
                        acc = acc_row.first()
                        if acc and acc.email:
                            name = f"{acc.firstname or ''} {acc.name or ''}".strip() or acc.name or ""
                            await send_notification_email(
                                to_email=acc.email,
                                recipient_name=name,
                                title=title,
                                body=body,
                                action_url=action_url,
                                action_label=action_label or "Voir la demande",
                            )
                except Exception as _exc:
                    logger.warning("NotificationEmitter : email auto échoué : %s", _exc)

    if send_sms_flag:
        if not sms_to:
            # Récupère le numéro du destinataire depuis Account si recipient_id connu
            if recipient_id:
                try:
                    rid = int(recipient_id)
                    from api.models.ModelAccount import Account
                    row = await session.execute(
                        select(Account.phone).where(Account.id == rid)
                    )
                    sms_to = row.scalar_one_or_none()
                except Exception:
                    pass

        if sms_to:
            try:
                from api.services.ServiceSMS import send_sms
                await send_sms(session, to=sms_to, message=f"{title}\n{body}")
            except Exception as exc:
                logger.warning("NotificationEmitter : SMS échoué : %s", exc)
        else:
            logger.debug("NotificationEmitter : canal SMS sans numéro — ignoré.")
