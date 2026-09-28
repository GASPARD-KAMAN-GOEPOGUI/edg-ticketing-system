"""Retrait de la table `communication_setting`.

Decision produit du 2026-09-24. Cette table etait un singleton (une ligne)
portant les reglages de canaux de communication. Sur ses neuf colonnes metier,
trois seulement etaient reellement consommees par le code :

  - `email_on`   : garde dans `NotificationEmitter` (envoi des mails)
  - `sms_on`     : garde dans `ServiceSMS`
  - `sender_sms` : expediteur SMS, avec repli sur `SMS_SENDER` (.env)

Les six autres (`internal_notif_on`, `banner_on`, `whatsapp_on`,
`push_mobile_on`, `sender_email`, `reply_to`) n'etaient lues nulle part :
l'expediteur des mails vient de `SMTP_USER` (.env), pas de cette table.

CONSEQUENCE ASSUMEE : il n'y a plus de coupe-circuit en base pour les mails et
les SMS. L'envoi se coupe desormais cote configuration — `SMTP_HOST` vide pour
les mails, `SMS_GATEWAY_URL` vide pour les SMS — ce qui suppose un redemarrage.

Les gardes retirees etaient de toute facon en fail-open (`if cs is None or
cs.email_on`), donc le comportement par defaut est INCHANGE : les envois
continuent exactement comme avant.

AUCUNE DONNEE PERDUE : la table etait vide au moment de la migration.

`activity_log` n'est PAS concernee : elle reste en place (exigence CDC 10.5 et
13 sur la journalisation des connexions).

Revision ID: 027
Revises: 026
Create Date: 2026-09-24
"""
from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "027"
down_revision: Union[str, None] = "026"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_table("communication_setting")


def downgrade() -> None:
    op.create_table(
        "communication_setting",
        sa.Column("updated_by", sa.Integer(), sa.ForeignKey("account.id"), nullable=True),
        sa.Column("internal_notif_on", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("email_on", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("sms_on", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("banner_on", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("whatsapp_on", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("push_mobile_on", sa.Boolean(), nullable=False, server_default=sa.text("0")),
        sa.Column("sender_email", sa.String(255), nullable=True),
        sa.Column("sender_sms", sa.String(11), nullable=True),
        sa.Column("reply_to", sa.String(255), nullable=True),
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("uuid", sa.String(36), nullable=False, unique=True),
        sa.Column("status", sa.Boolean(), nullable=False, server_default=sa.text("1")),
        sa.Column("infos", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", sa.DateTime(), nullable=False,
                  server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("deleted_at", sa.DateTime(), nullable=True),
    )
