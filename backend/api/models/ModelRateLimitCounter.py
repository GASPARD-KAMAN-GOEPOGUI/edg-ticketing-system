"""
Compteur de la limitation des tentatives — EDG Support.

Stockage MySQL (STATE_BACKEND=mysql) des compteurs de RateLimitMiddleware,
partagé entre les processus Passenger. Fenêtre fixe, même logique que le
stockage Redis (INCR puis EXPIRE au premier coup). Voir api/core/rate_limit_store.py.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import CHAR, DateTime, Index, Integer
from sqlalchemy.orm import Mapped, mapped_column

from .base import MYSQL_ARGS, Base


class RateLimitCounter(Base):
    __tablename__ = "rate_limit_counter"

    # Empreinte SHA-256 (hex) de « IP:chemin » : longueur fixe, 256 octets en
    # utf8mb4 — sous la limite d'index de 767 octets (MySQL 5.7 / MariaDB en
    # ROW_FORMAT COMPACT), quelle que soit la longueur de l'IP ou du chemin.
    key_hash: Mapped[str] = mapped_column(CHAR(64), primary_key=True)
    count: Mapped[int] = mapped_column(Integer, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (Index("idx_rate_limit_counter_expires_at", "expires_at"), MYSQL_ARGS)
