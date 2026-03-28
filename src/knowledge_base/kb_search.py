"""
KB Search - Motor de busqueda semantica para la base de conocimiento
"""
import re
from typing import List, Tuple, Dict, Optional


class KBSearch:
    """
    Motor de busqueda avanzada para la base de conocimiento.
    Implementa TF-IDF simplificado para ranking de relevancia.
    """

    def __init__(self, kb_manager):
        self._kb = kb_manager

    def search_with_highlights(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 5,
    ) -> List[Dict]:
        """
        Busca articulos y retorna resultados con fragmentos resaltados.

        Returns:
            Lista de dicts con articulo + fragmento relevante
        """
        results = self._kb.search(query, category=category, limit=limit)
        enriched = []

        for article, score in results:
            snippet = self._extract_snippet(article.content, query)
            enriched.append({
                "id": article.id,
                "title": article.title,
                "category": article.category,
                "tags": article.tags,
                "snippet": snippet,
                "relevance_score": round(score, 3),
                "helpfulness_score": round(article.helpfulness_score(), 3),
                "views": article.views,
            })

        return enriched

    def _extract_snippet(self, content: str, query: str, max_length: int = 200) -> str:
        """Extrae el fragmento mas relevante del contenido."""
        query_words = re.findall(r'\b\w{3,}\b', query.lower())
        if not query_words:
            return content[:max_length] + "..." if len(content) > max_length else content

        # Encontrar la posicion de la primera palabra de la query
        content_lower = content.lower()
        best_pos = 0
        for word in query_words:
            pos = content_lower.find(word)
            if pos != -1:
                best_pos = max(0, pos - 50)
                break

        snippet = content[best_pos:best_pos + max_length]
        if best_pos > 0:
            snippet = "..." + snippet
        if best_pos + max_length < len(content):
            snippet += "..."

        return snippet

    def suggest_related(self, article_id: str, limit: int = 3) -> List[Dict]:
        """Sugiere articulos relacionados basados en tags compartidos."""
        source = self._kb.get_article(article_id)
        if not source:
            return []

        # Buscar por tags del articulo fuente
        results = []
        for tag in source.tags[:3]:
            tag_results = self._kb.search(tag, limit=limit + 1)
            for article, score in tag_results:
                if article.id != article_id:
                    results.append({"id": article.id, "title": article.title, "score": score})

        # Deduplicar y ordenar
        seen = set()
        unique = []
        for r in sorted(results, key=lambda x: x["score"], reverse=True):
            if r["id"] not in seen:
                seen.add(r["id"])
                unique.append(r)

        return unique[:limit]
