"""
Knowledge Base Manager - AgenteDeVoz
Gap #35: Base de conocimiento con busqueda semantica

Gestiona articulos de conocimiento para:
- Respuestas FAQ del agente de voz
- Guias de troubleshooting para agentes humanos
- Documentacion tecnica interna
"""
import json
import uuid
import re
from datetime import datetime
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple


@dataclass
class KBArticle:
    id: str
    title: str
    content: str
    category: str
    tags: List[str]
    author: str
    created_at: datetime
    updated_at: datetime
    helpful_votes: int = 0
    unhelpful_votes: int = 0
    views: int = 0
    is_published: bool = True
    version: int = 1

    def helpfulness_score(self) -> float:
        """Calcula el score de utilidad del articulo."""
        total = self.helpful_votes + self.unhelpful_votes
        if total == 0:
            return 0.5  # Neutral por defecto
        return self.helpful_votes / total

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "title": self.title,
            "content": self.content,
            "category": self.category,
            "tags": self.tags,
            "author": self.author,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
            "helpful_votes": self.helpful_votes,
            "unhelpful_votes": self.unhelpful_votes,
            "views": self.views,
            "is_published": self.is_published,
            "version": self.version,
            "helpfulness_score": round(self.helpfulness_score(), 3),
        }


class KnowledgeBaseManager:
    """
    Gestor de base de conocimiento con busqueda por relevancia.

    Implementa busqueda por:
    1. Coincidencia exacta de titulos
    2. Busqueda de palabras clave en contenido
    3. Filtrado por categoria y tags
    4. Ranking por score de utilidad y vistas
    """

    CATEGORIES = [
        "faq", "troubleshooting", "billing", "technical",
        "escalation", "policy", "training", "product"
    ]

    def __init__(self):
        self._articles: Dict[str, KBArticle] = {}
        self._index: Dict[str, List[str]] = {}  # keyword -> [article_ids]
        self._load_default_articles()

    def create_article(
        self,
        title: str,
        content: str,
        category: str,
        tags: List[str],
        author: str = "admin",
        is_published: bool = True,
    ) -> str:
        """
        Crea un nuevo articulo en la base de conocimiento.

        Args:
            title: Titulo descriptivo del articulo
            content: Contenido completo en Markdown
            category: Categoria del articulo
            tags: Lista de etiquetas para busqueda

        Returns:
            ID del articulo creado
        """
        if category not in self.CATEGORIES:
            raise ValueError(f"Categoria invalida: {category}. Opciones: {self.CATEGORIES}")

        article_id = str(uuid.uuid4())[:12]
        now = datetime.utcnow()

        article = KBArticle(
            id=article_id,
            title=title,
            content=content,
            category=category,
            tags=[t.lower().strip() for t in tags],
            author=author,
            created_at=now,
            updated_at=now,
            is_published=is_published,
        )

        self._articles[article_id] = article
        self._index_article(article)
        return article_id

    def _index_article(self, article: KBArticle) -> None:
        """Indexa el articulo para busqueda rapida por keywords."""
        keywords = set()
        # Extraer palabras del titulo y contenido
        text = f"{article.title} {article.content} {' '.join(article.tags)}"
        words = re.findall(r'\b[a-zA-ZáéíóúñÁÉÍÓÚÑ]{3,}\b', text.lower())
        keywords.update(words)
        keywords.update(article.tags)

        # Stop words en espanol
        stop_words = {'que', 'como', 'para', 'por', 'una', 'uno', 'del', 'las', 'los', 'con', 'por'}
        keywords -= stop_words

        for keyword in keywords:
            if keyword not in self._index:
                self._index[keyword] = []
            if article.id not in self._index[keyword]:
                self._index[keyword].append(article.id)

    def search(
        self,
        query: str,
        category: Optional[str] = None,
        limit: int = 5,
    ) -> List[Tuple[KBArticle, float]]:
        """
        Busca articulos relevantes para la consulta.

        Args:
            query: Texto de busqueda
            category: Filtrar por categoria (opcional)
            limit: Numero maximo de resultados

        Returns:
            Lista de (KBArticle, relevance_score) ordenada por relevancia
        """
        query_words = re.findall(r'\b[a-zA-ZáéíóúñÁÉÍÓÚÑ]{3,}\b', query.lower())
        if not query_words:
            return []

        # Calcular score por coincidencia de keywords
        article_scores: Dict[str, float] = {}
        for word in query_words:
            matching_ids = self._index.get(word, [])
            for article_id in matching_ids:
                article_scores[article_id] = article_scores.get(article_id, 0) + 1

        # Filtrar por categoria si se especifica
        results = []
        for article_id, score in article_scores.items():
            article = self._articles.get(article_id)
            if not article or not article.is_published:
                continue
            if category and article.category != category:
                continue

            # Bonus por coincidencia en titulo
            title_words = set(re.findall(r'\b\w{3,}\b', article.title.lower()))
            title_match = len(set(query_words) & title_words)
            score += title_match * 2

            # Bonus por helpfulness y vistas
            relevance = score + (article.helpfulness_score() * 0.5) + (min(article.views, 100) / 200)
            results.append((article, relevance))

        # Ordenar por relevancia
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]

    def get_article(self, article_id: str) -> Optional[KBArticle]:
        """Retorna un articulo por ID y registra una vista."""
        article = self._articles.get(article_id)
        if article and article.is_published:
            article.views += 1
        return article

    def update_article(self, article_id: str, **kwargs) -> bool:
        """
        Actualiza un articulo existente.

        Args:
            **kwargs: Campos a actualizar (title, content, category, tags, is_published)
        """
        article = self._articles.get(article_id)
        if not article:
            return False

        updatable_fields = {"title", "content", "category", "tags", "is_published"}
        for key, value in kwargs.items():
            if key in updatable_fields:
                if key == "category" and value not in self.CATEGORIES:
                    raise ValueError(f"Categoria invalida: {value}")
                setattr(article, key, value)

        article.updated_at = datetime.utcnow()
        article.version += 1

        # Re-indexar
        self._index_article(article)
        return True

    def delete_article(self, article_id: str) -> bool:
        """Elimina un articulo (soft delete marcando como no publicado)."""
        article = self._articles.get(article_id)
        if not article:
            return False
        article.is_published = False
        return True

    def mark_helpful(self, article_id: str, helpful: bool) -> bool:
        """Registra un voto de utilidad para un articulo."""
        article = self._articles.get(article_id)
        if not article:
            return False
        if helpful:
            article.helpful_votes += 1
        else:
            article.unhelpful_votes += 1
        return True

    def export_to_json(self) -> str:
        """Exporta toda la base de conocimiento a JSON."""
        data = {
            "exported_at": datetime.utcnow().isoformat(),
            "total_articles": len(self._articles),
            "articles": [a.to_dict() for a in self._articles.values()],
        }
        return json.dumps(data, indent=2, ensure_ascii=False, default=str)

    def import_from_json(self, json_data: str) -> int:
        """
        Importa articulos desde JSON.

        Returns:
            Numero de articulos importados exitosamente
        """
        imported = 0
        try:
            data = json.loads(json_data)
            articles = data.get("articles", [])
            for a in articles:
                try:
                    self.create_article(
                        title=a["title"],
                        content=a["content"],
                        category=a.get("category", "faq"),
                        tags=a.get("tags", []),
                        author=a.get("author", "import"),
                        is_published=a.get("is_published", True),
                    )
                    imported += 1
                except Exception:
                    continue
        except json.JSONDecodeError:
            pass
        return imported

    def list_by_category(self, category: str) -> List[KBArticle]:
        """Lista todos los articulos publicados de una categoria."""
        return [
            a for a in self._articles.values()
            if a.category == category and a.is_published
        ]

    def get_stats(self) -> Dict:
        """Estadisticas de la base de conocimiento."""
        published = [a for a in self._articles.values() if a.is_published]
        return {
            "total_articles": len(self._articles),
            "published": len(published),
            "by_category": {
                cat: len([a for a in published if a.category == cat])
                for cat in self.CATEGORIES
            },
            "avg_helpfulness": (
                sum(a.helpfulness_score() for a in published) / len(published)
                if published else 0
            ),
            "total_views": sum(a.views for a in published),
        }

    def _load_default_articles(self) -> None:
        """Carga articulos predeterminados para el agente de voz."""
        defaults = [
            {
                "title": "Como crear un ticket de soporte",
                "content": """
## Crear Ticket de Soporte

Para crear un ticket, diga al agente:
- "Quiero crear un ticket"
- "Necesito reportar un problema"
- "Tengo una queja"

El agente le solicitara:
1. Descripcion del problema
2. Nivel de urgencia (bajo/medio/alto/critico)
3. Datos de contacto para seguimiento

Recibirá un número de ticket para rastrear su caso.
                """.strip(),
                "category": "faq",
                "tags": ["ticket", "soporte", "crear", "reportar"],
            },
            {
                "title": "Estados de ticket y tiempos de respuesta",
                "content": """
## Estados de Ticket

| Estado | Descripcion | Tiempo Objetivo |
|--------|-------------|-----------------|
| ABIERTO | Ticket recibido | - |
| EN_PROCESO | Agente asignado | < 15 min (urgente) |
| ESCALADO | Requiere supervision | < 1 hora |
| RESUELTO | Solucionado | - |
| CERRADO | Confirmado por cliente | - |

Para consultar el estado, diga su numero de ticket al agente.
                """.strip(),
                "category": "faq",
                "tags": ["ticket", "estado", "tiempo", "respuesta", "sla"],
            },
            {
                "title": "Cuando escalar a un agente humano",
                "content": """
## Escalacion a Agente Humano

El agente de voz escalara automaticamente cuando:
- La consulta supera su capacidad de respuesta
- El cliente solicita hablar con un humano
- El problema requiere acciones manuales en sistemas internos
- Se detecta frustacion alta del cliente

Para solicitar un agente humano, diga:
- "Quiero hablar con un agente"
- "Necesito hablar con una persona"
- "Comuniqueme con soporte"
                """.strip(),
                "category": "escalation",
                "tags": ["escalar", "humano", "agente", "persona", "soporte"],
            },
        ]

        for article_data in defaults:
            self.create_article(**article_data, author="system")
