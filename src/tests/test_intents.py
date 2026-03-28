"""Tests para el clasificador de intenciones y extractor de entidades."""

import sys
import os

import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))


class TestIntentClassifier:
    """Tests unitarios para IntentClassifier."""

    @pytest.fixture
    def classifier(self):
        from nlp.intent_classifier import IntentClassifier
        return IntentClassifier()

    # ── Clasificación de intenciones ─────────────────────────────────────────

    def test_classify_saludo(self, classifier):
        assert classifier.classify("Hola, buenos días") == "saludo"

    def test_classify_saludo_buenas_tardes(self, classifier):
        assert classifier.classify("Buenas tardes") == "saludo"

    def test_classify_faq_horario(self, classifier):
        intent = classifier.classify("¿Cuál es el horario de atención?")
        assert intent == "faq"

    def test_classify_faq_direccion(self, classifier):
        intent = classifier.classify("¿Dónde están ubicados?")
        assert intent == "faq"

    def test_classify_crear_ticket(self, classifier):
        intent = classifier.classify("Tengo un problema con mi pedido")
        assert intent == "crear_ticket"

    def test_classify_crear_ticket_keyword(self, classifier):
        intent = classifier.classify("Quiero reportar una falla en el servicio")
        assert intent == "crear_ticket"

    def test_classify_consultar_estado(self, classifier):
        intent = classifier.classify("¿Cuál es el estado de mi pedido?")
        assert intent == "consultar_estado"

    def test_classify_consultar_ticket(self, classifier):
        intent = classifier.classify("Quiero consultar mi ticket TKT-2026-000001")
        assert intent == "consultar_estado"

    def test_classify_queja(self, classifier):
        intent = classifier.classify("Estoy muy molesto con el servicio")
        assert intent == "queja"

    def test_classify_queja_pésimo(self, classifier):
        intent = classifier.classify("Pésima atención, inaceptable")
        assert intent == "queja"

    def test_classify_escalar_humano(self, classifier):
        intent = classifier.classify("Quiero hablar con un supervisor")
        assert intent == "escalar_humano"

    def test_classify_escalar_agente(self, classifier):
        intent = classifier.classify("Quiero hablar con un agente humano")
        assert intent == "escalar_humano"

    def test_classify_despedida(self, classifier):
        intent = classifier.classify("Gracias, eso es todo")
        assert intent == "despedida"

    def test_classify_despedida_adios(self, classifier):
        intent = classifier.classify("Adiós, hasta luego")
        assert intent == "despedida"

    def test_classify_unknown_falls_back_to_faq(self, classifier):
        """Texto sin intención clara hace fallback a 'faq'."""
        intent = classifier.classify("xyzabc 123")
        assert intent == "faq"

    def test_classify_empty_returns_sin_intencion(self, classifier):
        intent = classifier.classify("")
        assert intent == "sin_intencion"

    # ── Extracción de entidades ───────────────────────────────────────────────

    def test_extract_ticket_id(self, classifier):
        entities = classifier.extract_entities("Mi ticket es TKT-2026-000123")
        assert "ticket_id" in entities
        assert entities["ticket_id"] == "TKT-2026-000123"

    def test_extract_order_id(self, classifier):
        entities = classifier.extract_entities("Mi pedido es #123456")
        assert "order_id" in entities
        assert "123456" in entities["order_id"]

    def test_extract_phone_colombian(self, classifier):
        entities = classifier.extract_entities("Mi número es 3001234567")
        assert "phone" in entities
        assert entities["phone"] == "3001234567"

    def test_extract_email(self, classifier):
        entities = classifier.extract_entities("Mi correo es juan@test.com")
        assert "email" in entities
        assert entities["email"] == "juan@test.com"

    def test_extract_amount(self, classifier):
        entities = classifier.extract_entities("Me cobraron $150,000 pesos")
        assert "amount" in entities

    def test_extract_no_entities_in_simple_text(self, classifier):
        entities = classifier.extract_entities("Hola, ¿cómo estás?")
        # No debe haber entidades en un saludo simple
        assert len(entities) == 0

    # ── Análisis de sentimiento ───────────────────────────────────────────────

    def test_sentiment_negative(self, classifier):
        sentiment = classifier.analyze_sentiment("Estoy muy enojado, pésimo servicio")
        assert sentiment == "negative"

    def test_sentiment_positive(self, classifier):
        sentiment = classifier.analyze_sentiment("Excelente servicio, muy contento con la atención")
        assert sentiment == "positive"

    def test_sentiment_neutral(self, classifier):
        sentiment = classifier.analyze_sentiment("Quiero consultar el estado de mi pedido")
        assert sentiment == "neutral"


class TestEntityExtractor:
    """Tests unitarios para EntityExtractor."""

    @pytest.fixture
    def extractor(self):
        from nlp.entity_extractor import EntityExtractor
        return EntityExtractor()

    def test_extract_ticket_id_format(self, extractor):
        result = extractor.extract_ticket_id("Mi ticket TKT-2026-000456 tiene un problema")
        assert result == "TKT-2026-000456"

    def test_extract_ticket_id_not_found(self, extractor):
        result = extractor.extract_ticket_id("No tengo número de ticket")
        assert result is None

    def test_extract_phone_celular(self, extractor):
        result = extractor.extract_phone("Llámame al 3201234567")
        assert result == "3201234567"

    def test_extract_email(self, extractor):
        result = extractor.extract_email("mi correo es soporte@empresa.com.co")
        assert result == "soporte@empresa.com.co"

    def test_extract_amount_with_peso_sign(self, extractor):
        result = extractor.extract_amount("me cobraron $150,000")
        assert result == "150000"

    def test_classify_problem_type_facturacion(self, extractor):
        result = extractor.classify_problem_type("Me llegó una factura incorrecta")
        assert result == "facturacion"

    def test_classify_problem_type_tecnico(self, extractor):
        result = extractor.classify_problem_type("El servicio no funciona, hay un error")
        assert result == "tecnico"

    def test_classify_problem_type_none(self, extractor):
        result = extractor.classify_problem_type("Quiero información general")
        assert result is None

    def test_extract_all_returns_only_found_entities(self, extractor):
        """extract_all no incluye claves con valor None."""
        result = extractor.extract_all("Tengo el ticket TKT-2026-000001")
        assert "ticket_id" in result
        # No debe incluir entidades no encontradas
        for value in result.values():
            assert value is not None

    def test_build_ticket_context(self, extractor):
        entities = {"problem_type": "facturacion", "amount_charged": "150000"}
        context = extractor.build_ticket_context(entities, "Me cobraron de más")
        assert context["category"] == "facturacion"
        assert context["priority"] == "ALTA"
        assert "amount_charged" in context
