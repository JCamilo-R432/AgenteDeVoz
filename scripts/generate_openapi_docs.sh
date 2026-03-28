#!/usr/bin/env bash
# =============================================================================
# generate_openapi_docs.sh - Generar y validar documentacion OpenAPI
# =============================================================================
# USO:
#   bash scripts/generate_openapi_docs.sh [--format html|json|yaml] [--serve]
#
# REQUISITOS:
#   pip install pyyaml swagger-ui-bundle
#   (Opcional) npm install -g @redocly/cli
# =============================================================================

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SCHEMA_FILE="${PROJECT_DIR}/src/docs/openapi_schema.yaml"
OUTPUT_DIR="${PROJECT_DIR}/docs/api"

GREEN='\033[0;32m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
NC='\033[0m'

FORMAT="html"
SERVE=false

while [[ $# -gt 0 ]]; do
    case $1 in
        --format) FORMAT="$2"; shift 2 ;;
        --serve) SERVE=true; shift ;;
        *) echo "Argumento desconocido: $1"; exit 1 ;;
    esac
done

log_ok() { echo -e "${GREEN}[OK]${NC} $*"; }
log_warn() { echo -e "${YELLOW}[WARN]${NC} $*"; }
log_error() { echo -e "${RED}[ERROR]${NC} $*"; }

echo ""
echo "=== GENERADOR DE DOCUMENTACION OPENAPI ==="
echo ""

# Verificar que el schema existe
if [[ ! -f "$SCHEMA_FILE" ]]; then
    log_error "Schema no encontrado: ${SCHEMA_FILE}"
    exit 1
fi

mkdir -p "$OUTPUT_DIR"

# Validar el schema YAML
echo "Validando schema OpenAPI..."
python3 -c "
import yaml
import sys

try:
    with open('${SCHEMA_FILE}') as f:
        schema = yaml.safe_load(f)

    # Verificaciones basicas
    required_fields = ['openapi', 'info', 'paths']
    missing = [f for f in required_fields if f not in schema]
    if missing:
        print(f'FALLO: Campos requeridos faltantes: {missing}')
        sys.exit(1)

    version = schema.get('openapi', '')
    if not version.startswith('3.'):
        print(f'ADVERTENCIA: Version OpenAPI {version}, se recomienda 3.0.x')

    paths_count = len(schema.get('paths', {}))
    schemas_count = len(schema.get('components', {}).get('schemas', {}))
    print(f'Schema valido - OpenAPI {version}')
    print(f'Paths: {paths_count} | Schemas: {schemas_count}')

except yaml.YAMLError as e:
    print(f'Error en YAML: {e}')
    sys.exit(1)
except Exception as e:
    print(f'Error: {e}')
    sys.exit(1)
" 2>&1

log_ok "Schema validado"

# Generar JSON desde YAML
echo "Generando JSON desde YAML..."
python3 -c "
import yaml
import json

with open('${SCHEMA_FILE}') as f:
    schema = yaml.safe_load(f)

output = '${OUTPUT_DIR}/openapi.json'
with open(output, 'w') as f:
    json.dump(schema, f, indent=2)
print(f'JSON generado: {output}')
" 2>&1
log_ok "JSON generado: ${OUTPUT_DIR}/openapi.json"

# Generar HTML con Swagger UI
if [[ "$FORMAT" == "html" ]]; then
    echo "Generando Swagger UI HTML..."
    python3 -c "
try:
    import swagger_ui_bundle
    output_dir = '${OUTPUT_DIR}'
    import json

    with open('${OUTPUT_DIR}/openapi.json') as f:
        schema_content = f.read()

    html = f'''<!DOCTYPE html>
<html lang=\"es\">
<head>
    <meta charset=\"UTF-8\">
    <meta name=\"viewport\" content=\"width=device-width, initial-scale=1.0\">
    <title>AgenteDeVoz API - Documentacion</title>
    <link rel=\"stylesheet\" href=\"https://unpkg.com/swagger-ui-dist@5/swagger-ui.css\">
</head>
<body>
    <div id=\"swagger-ui\"></div>
    <script src=\"https://unpkg.com/swagger-ui-dist@5/swagger-ui-bundle.js\"></script>
    <script src=\"https://unpkg.com/swagger-ui-dist@5/swagger-ui-standalone-preset.js\"></script>
    <script>
    window.onload = () => {{
        const spec = {schema_content};
        SwaggerUIBundle({{
            spec: spec,
            dom_id: '#swagger-ui',
            presets: [SwaggerUIBundle.presets.apis, SwaggerUIStandalonePreset],
            layout: 'StandaloneLayout',
            deepLinking: true,
            defaultModelsExpandDepth: 1,
        }});
    }};
    </script>
</body>
</html>'''

    with open(f'{output_dir}/index.html', 'w') as f:
        f.write(html)
    print(f'HTML generado: {output_dir}/index.html')
except ImportError:
    print('swagger-ui-bundle no instalado. Generando HTML basico...')
    with open('${OUTPUT_DIR}/index.html', 'w') as f:
        f.write('<html><body><h1>AgenteDeVoz API</h1><p>Instalar swagger-ui-bundle: pip install swagger-ui-bundle</p></body></html>')
" 2>&1
    log_ok "HTML generado: ${OUTPUT_DIR}/index.html"
fi

# Validar con redocly si esta disponible
if command -v redocly &>/dev/null; then
    echo "Validando con Redocly CLI..."
    redocly lint "$SCHEMA_FILE" 2>&1 && log_ok "Redocly: sin errores" || log_warn "Redocly: advertencias encontradas"
else
    log_warn "Redocly CLI no instalado. Para validacion adicional: npm install -g @redocly/cli"
fi

# Copiar schema al directorio publico
cp "$SCHEMA_FILE" "${OUTPUT_DIR}/openapi.yaml"
log_ok "Schema YAML copiado a: ${OUTPUT_DIR}/openapi.yaml"

echo ""
echo "Documentacion generada en: ${OUTPUT_DIR}/"
echo "  - openapi.yaml  (schema fuente)"
echo "  - openapi.json  (schema en JSON)"
echo "  - index.html    (Swagger UI)"
echo ""

# Servir localmente si se solicita
if [[ "$SERVE" == "true" ]]; then
    echo "Iniciando servidor local en http://localhost:8080/docs/api/"
    cd "$PROJECT_DIR"
    python3 -m http.server 8080 &
    echo "PID: $!"
    echo "Presiona Ctrl+C para detener"
    wait
fi
