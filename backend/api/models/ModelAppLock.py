"""
Verrou applicatif nommé, partagé entre processus via la base — EDG Support.

Sert à empêcher deux exécutions simultanées d'une même tâche planifiée
(cron cPanel lançant `python -m api.cli cycle` pendant qu'un cycle précédent
tourne encore). Un verrou expiré (processus tué) peut être repris.
Voir api/core/app_lock.py.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, String
from sqlalchemy.orm import Mapped, mapped_column

from .base import MYSQL_ARGS, Base


class AppLock(Base):
    __tablename__ = "app_lock"

    name: Mapped[str] = mapped_column(String(100), primary_key=True)
    holder: Mapped[str] = mapped_column(String(200), nullable=False)
    acquired_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (MYSQL_ARGS,)
