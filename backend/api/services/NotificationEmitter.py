from __future__ import annotations

import asyncio
import logging
from datetime import datetime

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from api.core.event_bus import AppEvent, emit as emit_event
from api.repositories.RepositoryNotification import NotificationRepository

logger = logging.getLogger(__name__)

# Références fortes vers les tâches d'envoi d'email en arrière-plan — évite qu'elles
# soient garbage-collectées avant complétion (piège classique asyncio.create_task).
_background_email_tasks: set[asyncio.Task] = set()


def _send_email_fire_and_forget(coro) -> None:
    """Lance l'envoi d'email sans bloquer l'appelant. Le SMTP (Gmail) peut prendre
    plusieurs secondes, ce qui retardait la réponse HTTP de close/resolve/etc. au
    point de dépasser le timeout client (15s) — le ticket était bien mis à jour en
    base mais le frontend affichait quand même une erreur générique."""
    task = asyncio.create_task(coro)
    _background_email_tasks.add(task)
    task.add_done_callback(_background_email_tasks.discard)


def _display_date(value) -> str:
    if not value:
        return ""
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y à %H:%M")
    return str(value)


def _display_name(*parts: str | None) -> str:
    return " ".join(part for part in parts if part).strip()


def _request_label(obj, attr: str, fallback: str = "") -> str:
    ref = getattr(obj, attr, None)
    if not ref:
        return fallback
    return (
        getattr(ref, "label", None)
        or getattr(ref, "name", None)
        or getattr(ref, "code", None)
        or getattr(ref, "slug", None)
        or fallback
    )


def _request_email_details(req) -> dict[str, str]:
    assignee = getattr(req, "assignee", None)
    details = {
        "Numero de ticket": getattr(req, "ref", "") or str(getattr(req, "id", "")),
        "Service concerne": _request_label(req, "unity"),
        "Date de creation": _display_date(getattr(req, "created_at", None)),
        "Agent assigne": _display_name(
            getattr(assignee, "firstname", None),
            getattr(assignee, "name", None),
        ),
        "Date de resolution": _display_date(getattr(req, "resolved_at", None)),
        "Date de cloture": _display_date(getattr(req, "closed_at", None)),
    }
    if getattr(req, "sla_breached", False):
        details["Delai limite SLA"] = _display_date(getattr(req, "sla_response_at", None))
    return {key: value for key, value in details.items() if value}


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
    # BR-NOTIFICATION-WORKFLOW-001 §22 — permet à un appelant de forcer une
    # notification App-only (ex. confirmation légère à l'émetteur d'une
    # transmission) sans passer par un canal SMS et sans email systématique.
    send_email: bool = True,
    # Perf — flush au lieu de commit quand l'appelant orchestre lui-même un
    # commit unique en fin de transaction (cf. ServiceRequest.create()). Défaut
    # True : comportement strictement inchangé pour tous les autres appelants.
    commit: bool = True,
) -> None:
    """
    Émet une notification.
    - channel='in_app' (défaut) : enregistrement en base + SSE
    - channel='sms' : envoi via ServiceSMS (nécessite sms_to)
    - channel='both' : in_app + SMS
    - send_email=False : désactive l'envoi email pour cet appel précis
      (App only), sans toucher aux autres canaux.
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
                }, commit=commit)
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

                # Email automatique, sauf opt-out explicite de l'appelant
                # (send_email=False, BR-NOTIFICATION-WORKFLOW-001 §22 — App-only
                # pour les confirmations légères/internes). Le coupe-circuit
                # CommunicationSetting.email_on a été retiré le 2026-09-24 :
                # l'envoi se coupe désormais en vidant SMTP_HOST dans .env.
                if send_email:
                    try:
                        from sqlalchemy import select as _select
                        from api.models.ModelAccount import Account
                        from api.models.ModelRequest import Request
                        from api.core.mailer import send_notification_email
                        acc_row = await session.execute(
                            _select(Account.email, Account.name, Account.firstname)
                            .where(Account.id == recipient_id_int)
                        )
                        acc = acc_row.first()
                        if acc and acc.email:
                            name = f"{acc.firstname or ''} {acc.name or ''}".strip() or acc.name or ""
                            request_details = None
                            if request_id:
                                try:
                                    req_row = await session.execute(
                                        _select(Request).where(Request.id == int(request_id))
                                    )
                                    req = req_row.scalar_one_or_none()
                                    if req:
                                        request_details = _request_email_details(req)
                                except Exception as detail_exc:
                                    logger.debug(
                                        "NotificationEmitter : details email indisponibles : %s",
                                        detail_exc,
                                    )
                            _send_email_fire_and_forget(send_notification_email(
                                to_email=acc.email,
                                recipient_name=name,
                                title=title,
                                body=body,
                                action_url=action_url,
                                action_label=action_label or "Voir le ticket",
                                notification_type=type,
                                request_details=request_details,
                            ))
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
                await send_sms(to=sms_to, message=f"{title}\n{body}")
            except Exception as exc:
                logger.warning("NotificationEmitter : SMS échoué : %s", exc)
        else:
            logger.debug("NotificationEmitter : canal SMS sans numéro — ignoré.")


async def emit_bulk(
    session: AsyncSession,
    *,
    recipient_ids: list[str],
    title: str,
    body: str,
    type: str = "info",
    request_id: str | None = None,
    action_label: str | None = None,
    action_url: str | None = None,
    visibility: str = "public",
    send_email: bool = True,
    # Perf — flush au lieu de commit quand l'appelant orchestre lui-même un
    # commit unique en fin de transaction (ex. ServiceRequest.create()).
    commit: bool = True,
) -> None:
    """Fan-out in-app vers plusieurs destinataires en une seule transaction.

    `emit()` appelé en boucle (ex. une diffusion vers tous les comptes actifs)
    fait un COMMIT + un SELECT Account par destinataire — N commits séquentiels
    qui bloquent la requête HTTP. Ici : un seul `bulk_create` (un commit), un
    seul SELECT Account (IN), et un seul événement SSE
    ciblant tous les destinataires (le client invalide juste `["notifications"]`,
    peu importe le payload — cf. `invalidation-map.ts`).
    """
    ids: list[int] = []
    for rid in recipient_ids:
        try:
            ids.append(int(rid))
        except (TypeError, ValueError):
            continue
    if not ids:
        return

    repo = NotificationRepository(session)
    await repo.bulk_create([
        {
            "recipient_id": rid,
            "type": type,
            "channel": "in_app",
            "title": title,
            "body": body,
            "request_id": request_id,
            "action_label": action_label,
            "action_url": action_url,
            "visibility": visibility,
        }
        for rid in ids
    ], commit=commit)

    await emit_event(AppEvent(
        type="notification.created",
        payload={"title": title, "type": type, "request_id": request_id},
        target={"user_ids": ids},
    ))

    if send_email:
        try:
            from sqlalchemy import select as _select
            from api.models.ModelAccount import Account
            from api.core.mailer import send_notification_email
            acc_rows = await session.execute(
                _select(Account.email, Account.name, Account.firstname)
                .where(Account.id.in_(ids))
                .where(Account.email.isnot(None))
            )
            for acc in acc_rows.all():
                name = f"{acc.firstname or ''} {acc.name or ''}".strip() or acc.name or ""
                _send_email_fire_and_forget(send_notification_email(
                    to_email=acc.email,
                    recipient_name=name,
                    title=title,
                    body=body,
                    action_url=action_url,
                    action_label=action_label or "Voir le ticket",
                    notification_type=type,
                    request_details=None,
                ))
        except Exception as _exc:
            logger.warning("NotificationEmitter : email fan-out bulk échoué : %s", _exc)
