#!/usr/bin/env bash
# ─── Restauration EDG Connect ─────────────────────────────────────────────────
# Usage : ./restore.sh /backups/edg_backup_20240614_020000.tar.gz
# ATTENTION : écrase la base de données et les uploads existants

set -euo pipefail

ARCHIVE="${1:-}"

if [ -z "${ARCHIVE}" ] || [ ! -f "${ARCHIVE}" ]; then
    echo "❌ Usage : $0 /chemin/vers/edg_backup_YYYYMMDD_HHMMSS.tar.gz"
    exit 1
fi

# Confirmation sécurité
echo "⚠  RESTAURATION — Cette opération va ÉCRASER la base de données actuelle."
echo "   Archive : ${ARCHIVE}"
read -r -p "   Tapez 'CONFIRMER' pour continuer : " CONFIRM
if [ "${CONFIRM}" != "CONFIRMER" ]; then
    echo "Annulé."
    exit 0
fi

# Variables d'environnement
if [ -f /app/.env.production ]; then
    set -a && source /app/.env.production && set +a
fi

DB_HOST="${DATABASE_HOSTNAME:-db}"
DB_PORT="${DATABASE_PORT:-3306}"
DB_NAME="${DATABASE_NAME:-edg_ticketing}"
DB_USER="${DATABASE_USERNAME:-edg_user}"
DB_PASS="${DATABASE_PASSWORD}"
UPLOADS_DIR="${UPLOADS_PATH:-/app/uploads}"

TMP_DIR="/tmp/edg_restore_$(date +%s)"
echo "Extraction de l'archive..."
mkdir -p "${TMP_DIR}"
tar -xzf "${ARCHIVE}" -C "${TMP_DIR}"

EXTRACT_DIR=$(find "${TMP_DIR}" -maxdepth 1 -mindepth 1 -type d | head -1)

if [ ! -f "${EXTRACT_DIR}/database.sql" ]; then
    echo "❌ database.sql introuvable dans l'archive."
    rm -rf "${TMP_DIR}"
    exit 1
fi

# Afficher les métadonnées
if [ -f "${EXTRACT_DIR}/backup_meta.json" ]; then
    echo "Métadonnées de la sauvegarde :"
    cat "${EXTRACT_DIR}/backup_meta.json"
    echo ""
fi

# ── 1. Restauration base de données ───────────────────────────────────────────
echo "[1/3] Restauration base de données..."
mysql \
    --host="${DB_HOST}" \
    --port="${DB_PORT}" \
    --user="${DB_USER}" \
    --password="${DB_PASS}" \
    "${DB_NAME}" < "${EXTRACT_DIR}/database.sql"
echo "      ✓ Base de données restaurée"

# ── 2. Restauration uploads ───────────────────────────────────────────────────
echo "[2/3] Restauration des fichiers uploadés..."
if [ -d "${EXTRACT_DIR}/uploads" ]; then
    rm -rf "${UPLOADS_DIR}"
    cp -r "${EXTRACT_DIR}/uploads" "${UPLOADS_DIR}"
    echo "      ✓ Uploads restaurés"
else
    echo "      ⚠ Pas de répertoire uploads dans l'archive"
fi

# ── 3. Nettoyage ──────────────────────────────────────────────────────────────
echo "[3/3] Nettoyage..."
rm -rf "${TMP_DIR}"

echo "═══════════════════════════════════════════════"
echo " ✅ Restauration terminée avec succès"
echo " Relancez le backend : docker compose restart backend"
echo "═══════════════════════════════════════════════"
