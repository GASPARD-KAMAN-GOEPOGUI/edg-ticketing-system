from __future__ import annotations

import uuid as _uuid
from datetime import datetime
from typing import Optional

from sqlalchemy import Boolean, DateTime, Integer, JSON, SmallInteger, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

MYSQL_ARGS = {
    "mysql_engine": "InnoDB",
    "mysql_charset": "utf8mb4",
    "mysql_collate": "utf8mb4_unicode_ci",
}


class Base(DeclarativeBase):
    pass


class BaseColumns:
    """
    Patron obligatoire v1.7+ — id INT AUTO_INCREMENT (clé interne, jamais exposée)
    + uuid CHAR(36) (identifiant public opaque utilisé dans les URLs et réponses API).
    Toutes les FK référencent la colonne id (INT).
    """

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    uuid: Mapped[str] = mapped_column(
        String(36),
        unique=True,
        nullable=False,
        default=lambda: str(_uuid.uuid4()),
    )
    status: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    infos: Mapped[Optional[dict]] = mapped_column(JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, nullable=False, server_default=func.now(), onupdate=func.now()
    )
    deleted_at: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class BaseRefColumns(BaseColumns):
    """
    Extension pour les 14 tables de référence dynamiques.
    Ajoute code (identifiant logique stocké dans les colonnes métier),
    label, sort_order et is_builtin.
    """

    code: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    label: Mapped[str] = mapped_column(String(200), nullable=False)
    sort_order: Mapped[int] = mapped_column(SmallInteger, nullable=False, default=0)
    is_builtin: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
