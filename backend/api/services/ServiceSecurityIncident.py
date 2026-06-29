from __future__ import annotations

import base64
import logging
import os
import uuid
from datetime import datetime, timezone

from sqlalchemy.ext.asyncio import AsyncSession

from api.core.event_bus import AppEvent, emit as emit_event
from api.models.ModelSecurityIncident import SecurityIncident
from api.repositories.RepositorySecurityIncident import SecurityIncidentRepository
from api.repositories.RepositoryAccount import AccountRepository
from api.services.base_service import BaseService
from api.services.NotificationEmitter import emit as emit_notif

logger = logging.getLogger(__name__)

_UPLOAD_DIR = os.path.join(os.path.dirname(__file__), "..", "..", "uploads", "security")


def _ensure_upload_dir() -> str:
    path = os.path.abspath(_UPLOAD_DIR)
    os.makedirs(path, exist_ok=True)
    return path


def _save_photo(data_url: str) -> str | None:
    """Décode une data URL base64 et enregistre l'image JPEG. Retourne le chemin relatif."""
    try:
        if "," in data_url:
            data_url = data_url.split(",", 1)[1]
        raw = base64.b64decode(data_url)
        upload_dir = _ensure_upload_dir()
        filename = f"{uuid.uuid4()}.jpg"
        full_path = os.path.join(upload_dir, filename)
        with open(full_path, "wb") as f:
            f.write(raw)
        return f"/api/v1/admin/security-photos/{filename}"
    except Exception as exc:
        logger.warning("Impossible de sauvegarder la photo de sécurité : %s", exc)
        return None


class SecurityIncidentService(BaseService):
    def __init__(self, session: AsyncSession) -> None:
        super().__init__(session)
        self.repo = SecurityIncidentRepository(session)
        self.account_repo = AccountRepository(session)

    async def create_incident(
        self,
        *,
        identifier: str,
        captured_image: str,
        timestamp: str,
        user_agent: str,
        ip_address: str | None,
        browser: str | None = None,
        os_info: str | None = None,
        device_type: str | None = None,
        location_approx: str | None = None,
        attempt_count: int = 1,
    ) -> SecurityIncident:
        photo_path = _save_photo(captured_image)

        # ── Déduplication : chercher incident récent non résolu pour ce même identifiant ──
        existing = await self.repo.find_recent_by_identifier(identifier)
        if existing:
            incident = await self.repo.increment_attempt(
                existing,
                new_photo_path=photo_path,
                occurred_at=timestamp,
                attempt_count=attempt_count,
            )
            is_new = False
        else:
            incident = await self.repo.create({
                "email_attempted": identifier,
                "ip_address": ip_address,
                "user_agent": user_agent,
                "browser": browser,
                "os_info": os_info,
                "device_type": device_type,
                "location_approx": location_approx,
                "photo_path": photo_path,
                "occurred_at": timestamp,
                "attempt_count": attempt_count,
                "resolved": False,
            })
            is_new = True

        # ── SSE uniquement pour les nouveaux incidents (éviter le bruit) ──
        if is_new:
            await emit_event(AppEvent(
                type="security.incident.new",
                payload={
                    "id": incident.id,
                    "email_attempted": identifier,
                    "ip_address": ip_address,
                    "browser": browser,
                    "os_info": os_info,
                    "device_type": device_type,
                    "location_approx": location_approx,
                    "attempt_count": attempt_count,
                    "occurred_at": timestamp,
                },
                target={"roles": ["admin"]},
            ))

            # Notification in-app persistante pour tous les admins
            try:
                admins, _ = await self.account_repo.list_by_role("admin", page=1, limit=100)
                details = []
                if ip_address:
                    details.append(f"IP : {ip_address}")
                if browser:
                    details.append(f"Navigateur : {browser}")
                if os_info:
                    details.append(f"OS : {os_info}")
                if location_approx:
                    details.append(f"Position approximative : {location_approx}")
                details_str = " · ".join(details)
                for admin in admins:
                    await emit_notif(
                        self.session,
                        recipient_id=str(admin.id),
                        title="Alerte sécurité — Tentative d'accès non autorisée",
                        body=(
                            f"Tentative #{attempt_count} depuis l'identifiant « {identifier or 'inconnu'} ». "
                            + (details_str or "Aucune métadonnée disponible.")
                        ),
                        type="error",
                        channel="in_app",
                        action_label="Voir le journal",
                        action_url="/app/admin/security",
                        visibility="admin_only",
                    )
            except Exception as exc:
                logger.warning("Impossible d'envoyer les notifications admin : %s", exc)
        else:
            # Incident mis à jour (doublons évités) — SSE léger pour incrémenter le compteur en live
            await emit_event(AppEvent(
                type="security.incident.updated",
                payload={
                    "id": incident.id,
                    "attempt_count": attempt_count,
                    "occurred_at": timestamp,
                },
                target={"roles": ["admin"]},
            ))

        return incident

    async def list_all(self, *, page: int = 1, limit: int = 50):
        items, total = await self.repo.list_all(page=page, limit=limit)
        return self.paginate(items, total, page, limit)

    async def list_unresolved(self):
        return await self.repo.list_unresolved()

    async def resolve(self, incident_id: int, *, resolver_id: int, notes: str | None) -> SecurityIncident:
        return await self.repo.resolve(incident_id, resolver_id=resolver_id, notes=notes)

    async def delete_incident(self, incident_id: int) -> None:
        obj = await self.repo.get_by_id(incident_id)
        if obj is None:
            raise self.not_found("Incident de sécurité introuvable")
        await self.repo.delete(incident_id)
