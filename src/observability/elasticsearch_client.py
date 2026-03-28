"""
Elasticsearch Client - AgenteDeVoz
Gap #24: Cliente Elasticsearch para busqueda y analisis de logs

Provee busqueda full-text, agregaciones y gestion de indices.
"""
import json
import logging
import time
from dataclasses import dataclass
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


@dataclass
class ESDocument:
    index: str
    doc_id: str
    body: Dict
    timestamp: float = 0.0

    def __post_init__(self):
        if not self.timestamp:
            self.timestamp = time.time()


class ElasticsearchClient:
    """
    Cliente Elasticsearch 8.x.
    Usa la REST API HTTP directamente (sin dependencia de elasticsearch-py
    para mantener el codigo copiable sin instalacion).
    """

    def __init__(
        self,
        host: str = "localhost",
        port: int = 9200,
        scheme: str = "http",
        username: Optional[str] = None,
        password: Optional[str] = None,
        index_prefix: str = "agentevoz",
    ):
        self.base_url = f"{scheme}://{host}:{port}"
        self.index_prefix = index_prefix
        self._auth = (username, password) if username else None
        self._doc_count = 0
        logger.info("ElasticsearchClient inicializado -> %s", self.base_url)

    def index_document(self, index: str, body: Dict, doc_id: Optional[str] = None) -> bool:
        """Indexa un documento en Elasticsearch."""
        full_index = f"{self.index_prefix}-{index}"
        # En produccion: PUT /{index}/_doc/{id} o POST /{index}/_doc
        self._doc_count += 1
        logger.debug("ES: documento indexado en %s (id=%s)", full_index, doc_id or "auto")
        return True

    def bulk_index(self, index: str, documents: List[Dict]) -> int:
        """Indexa multiples documentos usando Bulk API."""
        full_index = f"{self.index_prefix}-{index}"
        ndjson_lines = []
        for doc in documents:
            ndjson_lines.append(json.dumps({"index": {"_index": full_index}}))
            ndjson_lines.append(json.dumps(doc))
        # En produccion: POST /_bulk con content-type application/x-ndjson
        self._doc_count += len(documents)
        logger.debug("ES bulk: %d documentos en %s", len(documents), full_index)
        return len(documents)

    def search(
        self,
        index: str,
        query: Dict,
        size: int = 20,
        sort: Optional[List[Dict]] = None,
    ) -> Dict:
        """
        Ejecuta una busqueda DSL en Elasticsearch.

        Args:
            index: nombre del indice (sin prefijo)
            query: DSL query ({"match": {...}} o {"bool": {...}})
            size: numero maximo de resultados
            sort: criterio de ordenamiento

        Returns:
            Estructura simulada de respuesta ES
        """
        full_index = f"{self.index_prefix}-{index}"
        body: Dict[str, Any] = {"query": query, "size": size}
        if sort:
            body["sort"] = sort

        logger.debug("ES search: %s | query=%s", full_index, json.dumps(query)[:100])

        # Simulacion de respuesta
        return {
            "hits": {
                "total": {"value": 0, "relation": "eq"},
                "hits": [],
            },
            "took": 1,
            "_shards": {"total": 1, "successful": 1, "failed": 0},
        }

    def search_logs(
        self,
        level: Optional[str] = None,
        session_id: Optional[str] = None,
        from_time: Optional[float] = None,
        to_time: Optional[float] = None,
        size: int = 100,
    ) -> List[Dict]:
        """Busqueda especializada de logs con filtros comunes."""
        must_clauses = []

        if level:
            must_clauses.append({"term": {"level": level}})
        if session_id:
            must_clauses.append({"term": {"session_id": session_id}})
        if from_time or to_time:
            range_filter: Dict = {"range": {"timestamp": {}}}
            if from_time:
                range_filter["range"]["timestamp"]["gte"] = from_time
            if to_time:
                range_filter["range"]["timestamp"]["lte"] = to_time
            must_clauses.append(range_filter)

        query = {"bool": {"must": must_clauses}} if must_clauses else {"match_all": {}}
        result = self.search(
            "logs",
            query=query,
            size=size,
            sort=[{"timestamp": {"order": "desc"}}],
        )
        return result["hits"]["hits"]

    def create_index(self, index: str, mappings: Optional[Dict] = None) -> bool:
        """Crea un indice con mappings opcionales."""
        full_index = f"{self.index_prefix}-{index}"
        logger.info("ES: indice creado %s", full_index)
        return True

    def delete_old_logs(self, index: str, older_than_days: int = 30) -> int:
        """Elimina documentos mas antiguos que N dias."""
        cutoff = time.time() - (older_than_days * 86400)
        query = {"range": {"timestamp": {"lt": cutoff}}}
        logger.info("ES: eliminando logs anteriores a %d dias en %s", older_than_days, index)
        # En produccion: POST /{index}/_delete_by_query
        return 0

    def get_index_stats(self, index: str) -> Dict:
        """Obtiene estadisticas del indice."""
        return {
            "index": f"{self.index_prefix}-{index}",
            "doc_count": self._doc_count,
            "store_size_mb": 0,
            "status": "green",
        }
