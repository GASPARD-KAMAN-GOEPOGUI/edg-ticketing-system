"""
Jetons révoqués par une déconnexion — EDG Support.

Les jetons sont émis par la plateforme centrale, qui n'expose pas de route de
révocation : sans cette table, un jeton (access ou refresh) restait valable
après la déconnexion jusqu'à son expiration. Seule l'empreinte SHA-256 est
conservée, jamais le jeton. Voir api/core/token_revocation.py.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy import CHAR, DateTime, Index
from sqlalchemy.orm import Mapped, mapped_column

from .base import MYSQL_ARGS, Base


class RevokedToken(Base):
    __tablename__ = "revoked_token"

    token_hash: Mapped[str] = mapped_column(CHAR(64), primary_key=True)
    revoked_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    expires_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    __table_args__ = (Index("idx_revoked_token_expires_at", "expires_at"), MYSQL_ARGS)
