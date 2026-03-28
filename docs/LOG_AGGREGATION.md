# Log Aggregation (Gap #24)

## Descripcion
Agregacion centralizada de logs estructurados (JSON) en Elasticsearch o Loki.

## Uso
```python
from src.observability.log_aggregation import LogAggregator, LogLevel

logger = LogAggregator(
    service_name="agentevoz",
    backend="elasticsearch",
    backend_url="http://localhost:9200",
    min_level=LogLevel.INFO,
)

logger.info("Sesion iniciada", session_id="sess_001", trace_id="abc123")
logger.error("Error en STT", session_id="sess_001", error_code="STT_TIMEOUT")
logger.flush()  # Forzar envio del buffer
```

## Formato de log (JSON)
```json
{
  "log_id": "a1b2c3d4e5f6",
  "timestamp": 1711195200.0,
  "level": "ERROR",
  "service": "agentevoz",
  "message": "Error en STT",
  "session_id": "sess_001",
  "trace_id": "abc123",
  "error_code": "STT_TIMEOUT"
}
```

## Backends soportados
| Backend | URL | Formato |
|---------|-----|---------|
| Elasticsearch | http://es:9200 | NDJSON Bulk API |
| Loki | http://loki:3100 | Push API streams |
| stdout | - | JSON directo |

## Setup ELK
```bash
scripts/setup_elasticsearch.sh
```

## Elasticsearch - busqueda de logs
```python
from src.observability.elasticsearch_client import ElasticsearchClient

es = ElasticsearchClient(host="localhost", port=9200)
logs = es.search_logs(level="ERROR", session_id="sess_001")
```

## Retencion
- Logs ERROR/CRITICAL: 90 dias
- Logs INFO/WARNING: 30 dias
- Logs DEBUG: 7 dias
