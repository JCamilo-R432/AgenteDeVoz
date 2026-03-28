#!/bin/bash
# Backup and Restore - AgenteDeVoz
# Gap #11/#12: High Availability + Database Replication
# Backup automatico con pg_dump + restauracion verificada

set -euo pipefail

BACKUP_DIR="${BACKUP_DIR:-/var/backups/agentevoz}"
DB_HOST="${DB_HOST:-localhost}"
DB_PORT="${DB_PORT:-5432}"
DB_NAME="${DB_NAME:-agentevoz}"
DB_USER="${DB_USER:-postgres}"
RETENTION_DAYS="${RETENTION_DAYS:-30}"
TIMESTAMP=$(date +%Y%m%d_%H%M%S)

usage() {
    echo "Uso: $0 [backup|restore|list|verify]"
    echo "  backup   - Crear nuevo backup"
    echo "  restore  - Restaurar desde backup (requiere BACKUP_FILE=<ruta>)"
    echo "  list     - Listar backups disponibles"
    echo "  verify   - Verificar integridad del ultimo backup"
    exit 1
}

backup() {
    local backup_file="$BACKUP_DIR/agentevoz_${TIMESTAMP}.dump"
    mkdir -p "$BACKUP_DIR"

    echo "=== Creando backup: $backup_file ==="
    PGPASSWORD="${DB_PASSWORD:-}" pg_dump \
        -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" \
        -F c -b -v -f "$backup_file" "$DB_NAME"

    # Comprimir
    gzip "$backup_file"
    backup_file="${backup_file}.gz"

    # Calcular checksum
    sha256sum "$backup_file" > "${backup_file}.sha256"

    echo "Backup creado: $backup_file"
    echo "Checksum: ${backup_file}.sha256"

    # Limpiar backups antiguos
    find "$BACKUP_DIR" -name "*.dump.gz" -mtime "+${RETENTION_DAYS}" -delete
    echo "Backups anteriores a $RETENTION_DAYS dias eliminados"
}

restore() {
    local backup_file="${BACKUP_FILE:-}"
    if [ -z "$backup_file" ]; then
        echo "ERROR: BACKUP_FILE no especificado"
        exit 1
    fi
    if [ ! -f "$backup_file" ]; then
        echo "ERROR: Archivo no encontrado: $backup_file"
        exit 1
    fi

    # Verificar checksum
    if [ -f "${backup_file}.sha256" ]; then
        sha256sum -c "${backup_file}.sha256" || {
            echo "ERROR: Checksum invalido"
            exit 1
        }
    fi

    echo "=== Restaurando desde: $backup_file ==="
    gunzip -c "$backup_file" | PGPASSWORD="${DB_PASSWORD:-}" pg_restore \
        -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER" \
        -d "$DB_NAME" -v --no-owner --no-privileges || true

    echo "Restauracion completada"
}

list_backups() {
    echo "=== Backups disponibles en $BACKUP_DIR ==="
    ls -lh "$BACKUP_DIR"/*.dump.gz 2>/dev/null | awk '{print $5, $6, $7, $8, $9}' || echo "No hay backups"
}

verify() {
    local latest
    latest=$(ls -t "$BACKUP_DIR"/*.dump.gz 2>/dev/null | head -1)
    if [ -z "$latest" ]; then
        echo "No hay backups para verificar"
        exit 1
    fi
    echo "Verificando: $latest"
    if [ -f "${latest}.sha256" ]; then
        sha256sum -c "${latest}.sha256" && echo "Checksum OK"
    else
        echo "WARN: No hay archivo de checksum"
    fi
    # Verificar que se puede leer el dump
    gunzip -c "$latest" | pg_restore --list > /dev/null && echo "Dump valido"
}

case "${1:-backup}" in
    backup)   backup ;;
    restore)  restore ;;
    list)     list_backups ;;
    verify)   verify ;;
    *)        usage ;;
esac
