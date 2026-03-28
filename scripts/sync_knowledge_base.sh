#!/usr/bin/env bash
# =============================================================================
# sync_knowledge_base.sh - Sincronizar base de conocimiento
# =============================================================================
# USO:
#   bash scripts/sync_knowledge_base.sh [--source markdown|hubspot|all] [--dir PATH]
#
# OPCIONES:
#   --source SOURCE   Fuente de sincronizacion (default: markdown)
#   --dir PATH        Directorio de archivos Markdown (default: docs/)
#   --export FILE     Exportar KB a JSON tras sincronizacion
#   --stats           Mostrar estadisticas despues de sync
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
TIMESTAMP=$(date +"%Y%m%d_%H%M%S")

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BLUE='\033[0;34m'
NC='\033[0m'

SOURCE="markdown"
DOCS_DIR="${PROJECT_DIR}/docs"
EXPORT_FILE=""
SHOW_STATS=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --source) SOURCE="$2"; shift 2 ;;
        --dir) DOCS_DIR="$2"; shift 2 ;;
        --export) EXPORT_FILE="$2"; shift 2 ;;
        --stats) SHOW_STATS=true; shift ;;
        *) echo "Argumento desconocido: $1"; exit 1 ;;
    esac
done

log_ok() { echo -e "${GREEN}[OK]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }
log_info() { echo -e "${BLUE}[INFO]${NC} $*"; }

echo ""
echo "=== SINCRONIZACION DE KNOWLEDGE BASE - AgenteDeVoz ==="
echo "Fuente: ${SOURCE} | Directorio: ${DOCS_DIR}"
echo ""

# Verificar directorio
if [[ ! -d "$DOCS_DIR" ]]; then
    log_error "Directorio no encontrado: ${DOCS_DIR}"
    exit 1
fi

COUNT_MD=$(find "$DOCS_DIR" -name "*.md" 2>/dev/null | wc -l | tr -d ' ')
log_info "Archivos Markdown encontrados: ${COUNT_MD}"

# Sincronizacion desde Markdown
sync_from_markdown() {
    log_info "Sincronizando desde directorio: ${DOCS_DIR}"

    python3 -c "
import sys
sys.path.insert(0, '${PROJECT_DIR}')

from src.knowledge_base.kb_manager import KnowledgeBaseManager
from src.knowledge_base.kb_sync import KBSync

kb = KnowledgeBaseManager()
syncer = KBSync(kb)

result = syncer.sync_from_markdown_dir('${DOCS_DIR}')
print(f'Importados: {result[\"imported\"]} articulos')
print(f'Errores: {result[\"errors\"]}')
if result['error_details']:
    for err in result['error_details'][:5]:
        print(f'  ERROR: {err[\"file\"]} - {err[\"error\"]}')
" 2>&1 && log_ok "Sync desde Markdown completado" || log_error "Error en sync"
}

# Sincronizacion desde HubSpot
sync_from_hubspot() {
    if [[ -z "${HUBSPOT_API_KEY:-}" ]]; then
        log_warn "HUBSPOT_API_KEY no configurado. Saltando sync de HubSpot."
        log_info "Configurar: export HUBSPOT_API_KEY=tu_api_key"
        return 0
    fi

    log_info "Sincronizando desde HubSpot..."
    python3 -c "
import sys
sys.path.insert(0, '${PROJECT_DIR}')

from src.knowledge_base.kb_manager import KnowledgeBaseManager
from src.knowledge_base.kb_sync import KBSync
import os

kb = KnowledgeBaseManager()
syncer = KBSync(kb)

result = syncer.sync_from_hubspot(
    api_key=os.environ.get('HUBSPOT_API_KEY', ''),
    portal_id=os.environ.get('HUBSPOT_PORTAL_ID', '')
)
print(f'Resultado: {result[\"message\"]}')
" 2>&1
}

# Exportar KB a JSON
export_kb() {
    local output_file="$1"
    log_info "Exportando KB a: ${output_file}"

    python3 -c "
import sys
sys.path.insert(0, '${PROJECT_DIR}')
from src.knowledge_base.kb_manager import KnowledgeBaseManager

kb = KnowledgeBaseManager()
exported = kb.export_to_json()
with open('${output_file}', 'w', encoding='utf-8') as f:
    f.write(exported)
print(f'KB exportada a: ${output_file}')
" 2>&1 && log_ok "Exportacion completada" || log_error "Error en exportacion"
}

# Mostrar estadisticas
show_stats() {
    log_info "Estadisticas de la Knowledge Base:"
    python3 -c "
import sys
sys.path.insert(0, '${PROJECT_DIR}')
from src.knowledge_base.kb_manager import KnowledgeBaseManager

kb = KnowledgeBaseManager()
stats = kb.get_stats()
print(f'  Total articulos:    {stats[\"total_articles\"]}')
print(f'  Publicados:         {stats[\"published\"]}')
print(f'  Vistas totales:     {stats[\"total_views\"]}')
print(f'  Avg helpfulness:    {stats[\"avg_helpfulness\"]:.2f}')
print('  Por categoria:')
for cat, count in stats['by_category'].items():
    if count > 0:
        print(f'    {cat}: {count}')
" 2>&1
}

# Ejecutar segun fuente
case "$SOURCE" in
    markdown)
        sync_from_markdown
        ;;
    hubspot)
        sync_from_hubspot
        ;;
    all)
        sync_from_markdown
        sync_from_hubspot
        ;;
    *)
        log_error "Fuente no reconocida: ${SOURCE}. Opciones: markdown, hubspot, all"
        exit 1
        ;;
esac

# Exportar si se solicita
if [[ -n "$EXPORT_FILE" ]]; then
    export_kb "$EXPORT_FILE"
fi

# Mostrar estadisticas si se solicita
if [[ "$SHOW_STATS" == "true" ]]; then
    show_stats
fi

echo ""
log_ok "Sincronizacion completada: $(date)"
