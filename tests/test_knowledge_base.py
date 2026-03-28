"""
Tests para Knowledge Base Manager (Gap #35)
"""
import json
import pytest
from src.knowledge_base.kb_manager import KnowledgeBaseManager, KBArticle
from src.knowledge_base.kb_search import KBSearch


class TestKnowledgeBaseManager:
    def setup_method(self):
        self.kb = KnowledgeBaseManager()

    def test_default_articles_loaded(self):
        stats = self.kb.get_stats()
        assert stats["published"] >= 3  # Al menos 3 articulos por defecto

    def test_create_article_valid(self):
        article_id = self.kb.create_article(
            title="Como cambiar mi plan",
            content="Para cambiar de plan, contacte a soporte...",
            category="faq",
            tags=["plan", "cambio", "tarifario"],
        )
        assert article_id is not None
        assert len(article_id) > 0

    def test_create_article_invalid_category_raises(self):
        with pytest.raises(ValueError, match="Categoria invalida"):
            self.kb.create_article(
                title="Test",
                content="Contenido de prueba",
                category="categoria_invalida",
                tags=[],
            )

    def test_get_article_increments_views(self):
        article_id = self.kb.create_article("Test View", "Contenido", "faq", ["test"])
        article = self.kb.get_article(article_id)
        assert article is not None
        assert article.views == 1
        # Segunda lectura
        self.kb.get_article(article_id)
        article = self.kb.get_article(article_id)
        assert article.views == 3

    def test_get_nonexistent_article(self):
        result = self.kb.get_article("nonexistent_id")
        assert result is None

    def test_search_returns_relevant_results(self):
        self.kb.create_article("Creacion de tickets", "Como crear tickets de soporte...", "faq", ["ticket", "crear"])
        results = self.kb.search("crear ticket")
        assert len(results) > 0
        # El primer resultado debe ser sobre tickets
        titles = [art.title.lower() for art, score in results]
        assert any("ticket" in t for t in titles)

    def test_search_with_category_filter(self):
        self.kb.create_article("Guia tecnica DB", "PostgreSQL VACUUM...", "technical", ["postgresql"])
        results_all = self.kb.search("ticket")
        results_faq = self.kb.search("ticket", category="faq")
        # El filtro por categoria debe retornar menos o igual resultados
        assert len(results_faq) <= len(results_all)

    def test_search_empty_query(self):
        results = self.kb.search("")
        assert len(results) == 0

    def test_search_returns_tuple_with_score(self):
        results = self.kb.search("agente")
        if results:
            article, score = results[0]
            assert isinstance(article, KBArticle)
            assert isinstance(score, float)

    def test_update_article_title(self):
        article_id = self.kb.create_article("Titulo Original", "Contenido", "faq", ["test"])
        success = self.kb.update_article(article_id, title="Titulo Actualizado")
        assert success is True
        article = self.kb.get_article(article_id)
        assert article.title == "Titulo Actualizado"
        assert article.version == 2

    def test_update_article_invalid_category_raises(self):
        article_id = self.kb.create_article("Test", "Contenido", "faq", ["test"])
        with pytest.raises(ValueError):
            self.kb.update_article(article_id, category="invalido")

    def test_update_nonexistent_article(self):
        result = self.kb.update_article("nonexistent", title="Nuevo titulo")
        assert result is False

    def test_delete_article_soft_delete(self):
        article_id = self.kb.create_article("Para borrar", "Contenido", "faq", ["borrar"])
        result = self.kb.delete_article(article_id)
        assert result is True
        article = self.kb.get_article(article_id)
        assert article is None  # No debe aparecer en busquedas

    def test_delete_nonexistent_article(self):
        result = self.kb.delete_article("nonexistent")
        assert result is False

    def test_mark_helpful(self):
        article_id = self.kb.create_article("Test Helpful", "Contenido", "faq", ["helpful"])
        self.kb.mark_helpful(article_id, helpful=True)
        self.kb.mark_helpful(article_id, helpful=True)
        self.kb.mark_helpful(article_id, helpful=False)
        article = self.kb.get_article(article_id)
        assert article.helpful_votes == 2
        assert article.unhelpful_votes == 1

    def test_helpfulness_score(self):
        article_id = self.kb.create_article("Test Score", "Contenido", "faq", ["score"])
        self.kb.mark_helpful(article_id, helpful=True)
        self.kb.mark_helpful(article_id, helpful=True)
        self.kb.mark_helpful(article_id, helpful=False)
        article = self.kb.get_article(article_id)
        assert abs(article.helpfulness_score() - 2/3) < 0.01

    def test_export_import_roundtrip(self):
        initial_stats = self.kb.get_stats()
        exported = self.kb.export_to_json()
        data = json.loads(exported)
        assert "articles" in data
        assert data["total_articles"] == initial_stats["total_articles"]

        # Importar en una nueva instancia
        kb2 = KnowledgeBaseManager.__new__(KnowledgeBaseManager)
        kb2._articles = {}
        kb2._index = {}
        imported_count = kb2.import_from_json(exported)
        assert imported_count > 0

    def test_export_is_valid_json(self):
        exported = self.kb.export_to_json()
        data = json.loads(exported)
        assert "exported_at" in data
        assert "articles" in data

    def test_list_by_category(self):
        self.kb.create_article("FAQ 1", "Contenido FAQ", "faq", ["faq1"])
        self.kb.create_article("FAQ 2", "Contenido FAQ", "faq", ["faq2"])
        faq_articles = self.kb.list_by_category("faq")
        assert len(faq_articles) >= 2
        for art in faq_articles:
            assert art.category == "faq"
            assert art.is_published is True

    def test_get_stats_structure(self):
        stats = self.kb.get_stats()
        assert "total_articles" in stats
        assert "published" in stats
        assert "by_category" in stats
        assert "avg_helpfulness" in stats
        assert "total_views" in stats


class TestKBSearch:
    def setup_method(self):
        self.kb = KnowledgeBaseManager()
        self.search = KBSearch(self.kb)

    def test_search_with_highlights(self):
        results = self.search.search_with_highlights("ticket soporte")
        for r in results:
            assert "id" in r
            assert "title" in r
            assert "snippet" in r
            assert "relevance_score" in r

    def test_search_with_highlights_empty_query(self):
        results = self.search.search_with_highlights("")
        assert results == []

    def test_suggest_related(self):
        article_id = self.kb.create_article(
            "Articulo con tags", "Contenido...", "faq",
            ["ticket", "soporte", "escalacion"]
        )
        self.kb.get_article(article_id)  # Registrar vista
        suggestions = self.search.suggest_related(article_id, limit=3)
        # Puede que no haya sugerencias si no hay articulos con tags similares
        assert isinstance(suggestions, list)

    def test_suggest_related_nonexistent(self):
        suggestions = self.search.suggest_related("nonexistent")
        assert suggestions == []
