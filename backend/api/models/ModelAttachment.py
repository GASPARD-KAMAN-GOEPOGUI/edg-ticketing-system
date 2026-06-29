from __future__ import annotations

from typing import TYPE_CHECKING, Optional

from sqlalchemy import Boolean, Enum as SAEnum, ForeignKey, Index, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from .base import Base, BaseColumns, MYSQL_ARGS

if TYPE_CHECKING:
    from .ModelRequest import Request
    from .ModelAccount import Account


class Attachment(Base, BaseColumns):
    """MinIO S3 on-premise · 10 Mo/fichier · 5 max/demande · ClamAV."""

    __tablename__ = "attachment"

    request_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("request.id", ondelete="CASCADE"), nullable=False
    )
    uploader_id: Mapped[Optional[int]] = mapped_column(
        Integer, ForeignKey("account.id"), nullable=True
    )
    filename: Mapped[str] = mapped_column(String(500), nullable=False)
    storage_path: Mapped[str] = mapped_column(Text, nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    clamav_clean: Mapped[Optional[bool]] = mapped_column(Boolean, nullable=True)
    scan_status: Mapped[str] = mapped_column(
        SAEnum("pending_scan", "clean", "quarantined", "deleted",
               name="scan_status_enum"),
        nullable=False,
        default="pending_scan",
    )

    request: Mapped[Request] = relationship(
        "Request", back_populates="attachments", lazy="raise"
    )
    uploader: Mapped[Optional[Account]] = relationship(
        "Account", foreign_keys="Attachment.uploader_id", lazy="raise"
    )

    __table_args__ = (
        Index("idx_att_req", "request_id"),
        Index("idx_att_status", "status", "deleted_at"),
        MYSQL_ARGS,
    )
