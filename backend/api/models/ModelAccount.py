from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship


from .base import Base, BaseColumns, MYSQL_ARGS

if TYPE_CHECKING:
    from .ModelUnity import Unity

# PV d'intervention EDG/PS-GSI/PV-01, bloc « Affectation » — cases à cocher
# Titulaire / Prestataire, auxquelles s'ajoute Stagiaire (demande métier).
# Qualifie l'INTERVENANT, jamais le demandeur.
INTERVENANT_STATUSES = frozenset({"titulaire", "prestataire", "stagiaire"})


class Account(Base, BaseColumns):
    """
    Identité déléguée à la plateforme centrale manager-user (central_user_id/central_user_uuid).
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
    central_user_id: Mapped[Optional[int]] = mapped_column(
        Integer, unique=True, nullable=True
    )
    central_user_uuid: Mapped[Optional[str]] = mapped_column(
        String(64), unique=True, nullable=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    firstname: Mapped[Optional[str]] = mapped_column(String(200), nullable=True)
    email: Mapped[str] = mapped_column(String(320), unique=True, nullable=False)
    phone: Mapped[Optional[str]] = mapped_column(String(30), unique=True, nullable=True)
    role: Mapped[str] = mapped_column(
        SAEnum(
            "public",
            "user",
            "chief-service",
            "technicien",
            "chef-division-support",
            "admin",
            name="role_enum",
        ),
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

    # ── Consentement (rattachement post-login sans groupe support central) ─────
    consent_accepted_at: Mapped[Optional[datetime]] = mapped_column(nullable=True)
    consent_version: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)

    # ── Relations ─────────────────────────────────────────────────────────────
    unity: Mapped[Optional[Unity]] = relationship(
        "Unity",
        back_populates="accounts",
        foreign_keys="Account.unity_id",
        lazy="raise",
    )

    @property
    def unit_id(self) -> Optional[int]:
        """Alias API : le compte est rattaché à une unité organisationnelle."""
        return self.unity_id

    @property
    def direction_id(self) -> Optional[int]:
        """Direction du compte.

        Seul le rôle `director` voyait son unité rattachée interprétée comme une
        direction. Ce rôle ayant été retiré le 2026-09-25, la propriété renvoie
        désormais toujours `None`. Elle est conservée parce que plusieurs
        appelants la lisent encore sur un compte (`actor.direction_id`) : la
        supprimer casserait ces accès, alors qu'un `None` y est déjà traité.
        """
        return None

    @property
    def intervenant_status(self) -> Optional[str]:
        """Statut de l'intervenant au sens du PV d'intervention
        (EDG/PS-GSI/PV-01) : `titulaire`, `prestataire` ou `stagiaire`.

        Stocké dans `infos` et NON dans une colonne dédiée : la table `account`
        est partagée avec la plateforme centrale, et l'on ne modifie pas son
        schéma (cf. migration 024). `infos` porte déjà des données propres à
        EDG Connect (indicateur d'e-mail de bienvenue), c'est donc l'endroit
        cohérent.

        Distinct de `is_edg_employee`, booléen déduit de la présence d'un badge :
        un stagiaire EDG peut avoir un badge sans être titulaire."""
        infos = self.infos if isinstance(self.infos, dict) else {}
        value = infos.get("intervenant_status")
        return value if value in INTERVENANT_STATUSES else None

    __table_args__ = (
        Index("idx_account_role", "role"),
        Index("idx_account_unity", "unity_id"),
        Index("idx_account_status", "status", "deleted_at"),
        Index("idx_account_central_user_id", "central_user_id"),
        MYSQL_ARGS,
    )
