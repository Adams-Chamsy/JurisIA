#!/usr/bin/env bash
# ============================================================
# JurisIA — Script de Déploiement Production
# Zero-downtime via rolling restart + backup DB automatique
# Usage : ./deploy.sh [--skip-backup] [--rollback <image_tag>]
# ============================================================
set -euo pipefail

# ── Variables ────────────────────────────────────────────────
COMPOSE_FILE="/opt/jurisai/docker-compose.prod.yml"
APP_DIR="/opt/jurisai"
BACKUP_DIR="/opt/jurisai/backups"
LOG_FILE="/var/log/jurisai/deploy.log"
SLACK_WEBHOOK="${SLACK_WEBHOOK_URL:-}"
DATE=$(date '+%Y%m%d_%H%M%S')
SKIP_BACKUP=false
ROLLBACK_TAG=""

# Couleurs
RED='\033[0;31m'; GREEN='\033[0;32m'; YELLOW='\033[1;33m'; NC='\033[0m'

log()  { echo -e "${GREEN}[$(date '+%H:%M:%S')]${NC} $1" | tee -a "$LOG_FILE"; }
warn() { echo -e "${YELLOW}[$(date '+%H:%M:%S')] WARN:${NC} $1" | tee -a "$LOG_FILE"; }
err()  { echo -e "${RED}[$(date '+%H:%M:%S')] ERROR:${NC} $1" | tee -a "$LOG_FILE"; exit 1; }

# ── Parse arguments ──────────────────────────────────────────
while [[ $# -gt 0 ]]; do
    case $1 in
        --skip-backup) SKIP_BACKUP=true; shift ;;
        --rollback)    ROLLBACK_TAG="$2"; shift 2 ;;
        *) err "Argument inconnu : $1" ;;
    esac
done

# ── Notification Slack ───────────────────────────────────────
notify_slack() {
    local msg="$1"
    if [[ -n "$SLACK_WEBHOOK" ]]; then
        curl -s -X POST "$SLACK_WEBHOOK" \
            -H 'Content-type: application/json' \
            -d "{\"text\": \"$msg\"}" > /dev/null || true
    fi
}

# ── Rollback ─────────────────────────────────────────────────
if [[ -n "$ROLLBACK_TAG" ]]; then
    log "🔄 ROLLBACK vers l'image : $ROLLBACK_TAG"
    cd "$APP_DIR"
    sed -i "s|image: .*jurisai-backend:.*|image: ghcr.io/jurisai/jurisai-backend:${ROLLBACK_TAG}|g" \
        docker-compose.prod.yml
    docker compose -f "$COMPOSE_FILE" up -d --force-recreate backend
    log "✅ Rollback terminé"
    notify_slack "🔄 JurisIA rollback vers $ROLLBACK_TAG effectué"
    exit 0
fi

# ── Vérifications préalables ────────────────────────────────
log "🔍 Vérification de l'environnement..."
command -v docker >/dev/null || err "Docker non installé"
[[ -f "$COMPOSE_FILE" ]]     || err "docker-compose.prod.yml introuvable"
[[ -f "$APP_DIR/.env" ]]     || err "Fichier .env introuvable"

mkdir -p "$BACKUP_DIR" /var/log/jurisai

# ── Backup BDD ──────────────────────────────────────────────
if [[ "$SKIP_BACKUP" != "true" ]]; then
    log "💾 Backup PostgreSQL..."
    BACKUP_FILE="$BACKUP_DIR/pg_backup_${DATE}.sql.gz"
    docker compose -f "$COMPOSE_FILE" exec -T postgres \
        pg_dump -U jurisai jurisai_prod | gzip > "$BACKUP_FILE"
    log "✅ Backup créé : $BACKUP_FILE ($(du -sh "$BACKUP_FILE" | cut -f1))"
    # Garder uniquement les 7 derniers backups
    ls -tp "$BACKUP_DIR"/*.sql.gz 2>/dev/null | grep -v '/$' | tail -n +8 | xargs -I{} rm -- {} || true
else
    warn "Backup ignoré (--skip-backup)"
fi

# ── Pull de la nouvelle image ────────────────────────────────
log "📥 Pull des nouvelles images Docker..."
cd "$APP_DIR"
docker compose -f "$COMPOSE_FILE" pull backend || err "Échec du pull Docker"

# ── Migrations Alembic ───────────────────────────────────────
log "🗄️  Exécution des migrations Alembic..."
docker compose -f "$COMPOSE_FILE" run --rm backend \
    alembic upgrade head || err "Migrations Alembic échouées"
log "✅ Migrations OK"

# ── Déploiement (rolling restart) ────────────────────────────
log "🚀 Déploiement du backend..."
docker compose -f "$COMPOSE_FILE" up -d --force-recreate --no-deps backend

# ── Health check post-déploiement ────────────────────────────
log "🏥 Health check post-déploiement..."
MAX_RETRIES=12
RETRY_INTERVAL=5

for i in $(seq 1 $MAX_RETRIES); do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/health || echo "000")
    if [[ "$HTTP_CODE" == "200" ]]; then
        log "✅ Health check OK (tentative $i/$MAX_RETRIES)"
        break
    fi
    if [[ $i -eq $MAX_RETRIES ]]; then
        err "Health check échoué après $MAX_RETRIES tentatives. Lancement du rollback automatique..."
        # Auto-rollback
        docker compose -f "$COMPOSE_FILE" up -d --force-recreate --no-deps backend
        notify_slack "🔴 JurisIA déploiement ÉCHOUÉ — Rollback automatique lancé"
        exit 1
    fi
    warn "Tentative $i/$MAX_RETRIES — Code HTTP : $HTTP_CODE. Retry dans ${RETRY_INTERVAL}s..."
    sleep $RETRY_INTERVAL
done

# ── Nettoyage des images inutilisées ─────────────────────────
log "🧹 Nettoyage des images Docker inutilisées..."
docker image prune -f --filter "until=24h" > /dev/null || true

# ── Succès ────────────────────────────────────────────────────
DEPLOY_MSG="✅ JurisIA déployé avec succès — $(date '+%d/%m/%Y %H:%M') — $(git -C "$APP_DIR" rev-parse --short HEAD 2>/dev/null || echo 'N/A')"
log "$DEPLOY_MSG"
notify_slack "$DEPLOY_MSG"
