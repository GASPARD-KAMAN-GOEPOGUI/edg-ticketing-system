#!/usr/bin/env bash
# ─── Sauvegarde EDG Connect ───────────────────────────────────────────────────
# Usage : ./backup.sh [répertoire-de-sortie]
# Produit : edg_backup_YYYYMMDD_HHMMSS.tar.gz
# Cron recommandé : 0 2 * * * /app/scripts/backup.sh /backups >> /var/log/edg_backup.log 2>&1

set -euo pipefail

BACKUP_DIR="${1:-/backups}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)
BACKUP_NAME="edg_backup_${TIMESTAMP}"
TMP_DIR="/tmp/${BACKUP_NAME}"

# Variables d'environnement (source .env si disponible)
if [ -f /app/.env.production ]; then
    set -a && source /app/.env.production && set +a
fi

DB_HOST="${DATABASE_HOSTNAME:-db}"
DB_PORT="${DATABASE_PORT:-3306}"
DB_NAME="${DATABASE_NAME:-edg_ticketing}"
DB_USER="${DATABASE_USERNAME:-edg_user}"
DB_PASS="${DATABASE_PASSWORD}"
UPLOADS_DIR="${UPLOADS_PATH:-/app/uploads}"
RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-30}"

echo "═══════════════════════════════════════════════"
echo " EDG Connect — Sauvegarde ${TIMESTAMP}"
echo "═══════════════════════════════════════════════"

mkdir -p "${TMP_DIR}" "${BACKUP_DIR}"

# ── 1. Dump MySQL ──────────────────────────────────────────────────────────────
echo "[1/4] Dump base de données..."
mysqldump \
    --host="${DB_HOST}" \
    --port="${DB_PORT}" \
    --user="${DB_USER}" \
    --password="${DB_PASS}" \
    --single-transaction \
    --routines \
    --triggers \
    --events \
    --set-gtid-purged=OFF \
    "${DB_NAME}" > "${TMP_DIR}/database.sql"

echo "      ✓ ${DB_NAME} → database.sql ($(du -sh ${TMP_DIR}/database.sql | cut -f1))"

# ── 2. Copie des uploads ──────────────────────────────────────────────────────
echo "[2/4] Copie des fichiers uploadés..."
if [ -d "${UPLOADS_DIR}" ]; then
    cp -r "${UPLOADS_DIR}" "${TMP_DIR}/uploads"
    echo "      ✓ uploads ($(du -sh ${TMP_DIR}/uploads | cut -f1))"
else
    echo "      ⚠ ${UPLOADS_DIR} introuvable — ignoré"
fi

# ── 3. Métadonnées ────────────────────────────────────────────────────────────
echo "[3/4] Écriture des métadonnées..."
cat > "${TMP_DIR}/backup_meta.json" << EOF
{
  "timestamp": "${TIMESTAMP}",
  "db_name": "${DB_NAME}",
  "db_host": "${DB_HOST}",
  "hostname": "$(hostname)",
  "created_by": "$(whoami)",
  "app_version": "${APP_VERSION:-unknown}"
}
EOF

# ── 4. Compression & nettoyage ────────────────────────────────────────────────
echo "[4/4] Compression..."
ARCHIVE="${BACKUP_DIR}/${BACKUP_NAME}.tar.gz"
tar -czf "${ARCHIVE}" -C /tmp "${BACKUP_NAME}"
rm -rf "${TMP_DIR}"

SIZE=$(du -sh "${ARCHIVE}" | cut -f1)
echo "      ✓ Archive : ${ARCHIVE} (${SIZE})"

# ── Rotation : suppression des backups > RETENTION_DAYS jours ─────────────────
echo "Rotation : suppression des backups > ${RETENTION_DAYS} jours..."
find "${BACKUP_DIR}" -name "edg_backup_*.tar.gz" -mtime +${RETENTION_DAYS} -delete -print \
    | sed 's/^/  supprimé : /'

echo "═══════════════════════════════════════════════"
echo " Sauvegarde terminée : ${ARCHIVE}"
echo "═══════════════════════════════════════════════"
