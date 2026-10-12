"""
Liaison jeton -> (compte, version de session) — EDG Support.

Stockage MySQL (STATE_BACKEND=mysql) des liaisons de api/core/session_registry.py,
partagé entre les processus Passenger : un jeton lié à une version antérieure
à une révocation est refusé quel que soit le processus qui reçoit la requête.
Seule l'empreinte SHA-256 du jeton est conservée.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import CHAR, DateTime, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column

from .base import MYSQL_ARGS, Base


class SessionBinding(Base):
    __tablename__ = "session_binding"

    token_hash: Mapped[str] = mapped_column(CHAR(64), primary_key=True)
    account_id: Mapped[int] = mapped_column(Integer, nullable=False)
    version: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (Index("idx_session_binding_expires_at", "expires_at"), MYSQL_ARGS)
