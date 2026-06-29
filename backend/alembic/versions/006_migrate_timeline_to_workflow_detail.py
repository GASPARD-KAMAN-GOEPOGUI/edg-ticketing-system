"""migrate request_timeline history to workflow_detail

Revision ID: 006
Revises: 005
Create Date: 2026-06-20

ÉTAPES :
  1. Pour chaque request_id dans request_timeline sans workflow → crée 1 workflow (archived)
  2. Pour chaque ligne request_timeline → insère dans workflow_detail avec workflow_id valide
     Idempotence : skip si JSON_EXTRACT(infos, '$.rt_id') = rt.id déjà présent
"""

from alembic import op
from sqlalchemy import text

revision = "006"
down_revision = "005"
branch_labels = None
depends_on = None


def upgrade() -> None:
    conn = op.get_bind()

    # ── ÉTAPE 1 : créer 1 workflow par demande sans workflow ──────────────────
    # Statut 'archived' = historique complété ; uuid = UUID() MySQL natif
    conn.execute(text("""
        INSERT INTO workflow (request_id, workflow_status, uuid, status, created_at, updated_at)
        SELECT
            rt.request_id,
            'archived',
            UUID(),
            1,
            MIN(rt.created_at),
            MIN(rt.created_at)
        FROM request_timeline rt
        WHERE rt.deleted_at IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM workflow w
              WHERE w.request_id = rt.request_id
                AND w.deleted_at IS NULL
          )
        GROUP BY rt.request_id
        ORDER BY rt.request_id
    """))

    # ── ÉTAPE 2 : migrer les 75 lignes request_timeline → workflow_detail ────
    # Idempotence : on saute si JSON_EXTRACT(infos, '$.rt_id') = rt.id existe déjà
    conn.execute(text("""
        INSERT INTO workflow_detail
            (workflow_id, request_id, event_type, label,
             agent_id, actor_name,
             accepted, activated, status, uuid,
             infos, created_at, updated_at)
        SELECT
            w.id                                                         AS workflow_id,
            rt.request_id                                                AS request_id,
            rt.event_type                                                AS event_type,
            rt.label                                                     AS label,
            rt.actor_id                                                  AS agent_id,
            rt.actor_name                                                AS actor_name,
            NULL                                                         AS accepted,
            0                                                            AS activated,
            COALESCE(rt.status, 1)                                      AS status,
            UUID()                                                       AS uuid,
            JSON_OBJECT(
                'migrated_from', 'request_timeline',
                'rt_id', rt.id
            )                                                            AS infos,
            rt.created_at                                                AS created_at,
            rt.updated_at                                                AS updated_at
        FROM request_timeline rt
        JOIN workflow w
          ON w.request_id = rt.request_id
         AND w.deleted_at IS NULL
        WHERE rt.deleted_at IS NULL
          AND NOT EXISTS (
              SELECT 1 FROM workflow_detail wd
              WHERE wd.infos IS NOT NULL
                AND JSON_EXTRACT(wd.infos, '$.rt_id') = rt.id
          )
        ORDER BY rt.request_id, rt.created_at
    """))


def downgrade() -> None:
    conn = op.get_bind()

    # Supprime uniquement les lignes workflow_detail issues de la migration
    conn.execute(text("""
        DELETE FROM workflow_detail
        WHERE infos IS NOT NULL
          AND JSON_EXTRACT(infos, '$.migrated_from') = 'request_timeline'
    """))

    # Supprime les workflows créés par cette migration (ceux qui n'ont aucune
    # relation autre que les lignes migrated_from request_timeline)
    conn.execute(text("""
        DELETE FROM workflow
        WHERE id NOT IN (
            SELECT DISTINCT workflow_id
            FROM workflow_detail
            WHERE workflow_id IS NOT NULL
              AND deleted_at IS NULL
              AND (infos IS NULL OR JSON_EXTRACT(infos, '$.migrated_from') IS NULL)
        )
        AND workflow_status = 'archived'
        AND deleted_at IS NULL
    """))
