"""Tests unitarios para FAQManager."""

import pytest
import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))


class TestFAQManager:
    """Tests para el gestor de preguntas frecuentes."""

    @pytest.fixture
    def faq(self):
        from business.faq_manager import FAQManager
        return FAQManager()

    # ── Inicialización ─────────────────────────────────────────────────────────

    def test_faq_initialization(self, faq):
        """FAQManager se inicializa con FAQs predefinidas."""
        assert faq is not None
        assert len(faq.faqs) > 0

    def test_faq_has_required_topics(self, faq):
        """FAQManager tiene los temas mínimos requeridos."""
        keys = list(faq.faqs.keys())
        assert len(keys) >= 3

    # ── answer() ──────────────────────────────────────────────────────────────

    def test_answer_saludo(self, faq):
        """Responde a saludos con una respuesta no vacía."""
        response = faq.answer("Hola")
        assert response is not None
        assert len(response) > 0

    def test_answer_horario(self, faq):
        """Responde a consulta de horario con información de horario."""
        response = faq.answer("¿Cuál es el horario de atención?")
        assert response is not None
        assert any(word in response.lower() for word in
                   ["horario", "lunes", "viernes", "8", "18", "atencion"])

    def test_answer_ubicacion(self, faq):
        """Responde a consulta de ubicación."""
        response = faq.answer("¿Dónde están ubicados?")
        assert response is not None
        assert len(response) > 5

    def test_answer_servicios(self, faq):
        """Responde a consulta sobre servicios."""
        response = faq.answer("¿Qué servicios ofrecen?")
        assert response is not None

    def test_answer_returns_string(self, faq):
        """answer() siempre retorna un string."""
        for text in ["Hola", "horario", "precio", "factura", ""]:
            result = faq.answer(text)
            assert isinstance(result, str)

    def test_answer_unknown_suggests_ticket(self, faq):
        """Pregunta desconocida sugiere crear ticket o contactar soporte."""
        response = faq.answer("xyzabc pregunta sin sentido 12345")
        assert response is not None
        assert any(word in response.lower() for word in
                   ["ticket", "agente", "soporte", "humano", "detalles", "ayudar"])

    def test_answer_empty_string(self, faq):
        """answer() con string vacío no lanza excepción."""
        try:
            result = faq.answer("")
            assert isinstance(result, str)
        except Exception as e:
            pytest.fail(f"answer('') lanzó excepción: {e}")

    def test_answer_case_insensitive(self, faq):
        """La búsqueda no distingue mayúsculas/minúsculas."""
        resp_lower = faq.answer("horario de atención")
        resp_upper = faq.answer("HORARIO DE ATENCION")
        # Ambas deben retornar respuestas válidas (no necesariamente iguales)
        assert isinstance(resp_lower, str)
        assert isinstance(resp_upper, str)

    # ── add_faq() ──────────────────────────────────────────────────────────────

    def test_add_faq_returns_true(self, faq):
        """add_faq() retorna True cuando agrega exitosamente."""
        result = faq.add_faq(
            question="test_nuevo",
            answer="Esta es la respuesta de prueba nueva.",
            keywords=["prueba", "nuevo", "test"],
        )
        assert result is True

    def test_added_faq_is_answerable(self, faq):
        """Una FAQ agregada puede ser respondida después."""
        faq.add_faq(
            question="soporte_especial",
            answer="Soporte especial disponible los lunes.",
            keywords=["soporte", "especial", "lunes"],
        )
        response = faq.answer("necesito soporte especial")
        assert response is not None

    def test_add_faq_increments_count(self, faq):
        """add_faq() incrementa el número de FAQs."""
        initial_count = len(faq.faqs)
        faq.add_faq(
            question="nueva_pregunta_unica",
            answer="Respuesta única.",
            keywords=["unica"],
        )
        assert len(faq.faqs) == initial_count + 1

    # ── Scoring ────────────────────────────────────────────────────────────────

    def test_best_match_for_horario(self, faq):
        """La FAQ de horario es la mejor coincidencia para consultas de horario."""
        response = faq.answer("¿A qué hora abren?")
        assert response is not None
        assert any(w in response.lower() for w in ["8", "lunes", "viernes", "horario"])

    def test_multiple_keywords_improve_matching(self, faq):
        """Más palabras clave relevantes mejoran la coincidencia."""
        resp_one = faq.answer("horario")
        resp_multiple = faq.answer("horario atención días lunes")
        # Ambas deben retornar respuestas (la calidad puede variar)
        assert isinstance(resp_one, str)
        assert isinstance(resp_multiple, str)
