from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, BaseColumns, MYSQL_ARGS

if TYPE_CHECKING:
    from .ModelUnity import Unity


class Account(Base, BaseColumns):
    """
    Auth JWT auto-hébergée. password_hash stocké avec Argon2.
    is_edg_employee = 1 pour les agents/employés EDG — positionné automatiquement
    quand un matricule valide est fourni.
    unity_id pointe vers la Unity (Direction / Service) à laquelle appartient le compte.
    """

    __tablename__ = "account"

    # ── Clé étrangère organisationnelle ───────────────────────────────────────
    unity_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("unity.id"), nullable=True
    )

    # ── Attributs métier ──────────────────────────────────────────────────────
    keycloak_id: Mapped[Optional[str]] = mapped_column(
        String(255), unique=True, nullable=True
    )
    password_hash: Mapped[Optional[str]] = mapped_column(
        String(255), nullable=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    firstname: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(30), unique=True, nullable=True)
    role: Mapped[str] = mapped_column(
        SAEnum("public", "user", "agent", "chief", "director", "dg", "admin",
               name="role_enum"),
        nullable=False,
        default="user",
    )
    account_status: Mapped[str] = mapped_column(
        String(50), nullable=False, default="active"
    )
    matricule: Mapped[Optional[str]] = mapped_column(
        String(20), unique=True, nullable=True
    )
    job: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    avatar_url: Mapped[Optional[str]] = mapped_column(String(2048), nullable=True)
    is_edg_employee: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    email_verified: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    mfa_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    availability: Mapped[Optional[str]] = mapped_column(
        SAEnum("available", "busy", "overload", "off",
               name="agent_availability_enum"),
        nullable=True,
    )
    notif_sla_alerts: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notif_escalations: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notif_comments: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    notif_resolutions: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)

    # ── Dates ─────────────────────────────────────────────────────────────────
    activated_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)

    # ── Relations ─────────────────────────────────────────────────────────────
    unity: Mapped[Optional[Unity]] = relationship(
        "Unity",
        back_populates="accounts",
        foreign_keys="Account.unity_id",
        lazy="raise",
    )

    __table_args__ = (
        Index("idx_account_role", "role"),
        Index("idx_account_unity", "unity_id"),
        Index("idx_account_status", "status", "deleted_at"),
        MYSQL_ARGS,
    )
