"""Tests de estrés para el Agente de Voz."""

import pytest
import sys
import os
import time

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))


class TestStress:
    """Tests de estrés del sistema."""

    # ── NLP bajo carga ────────────────────────────────────────────────────────

    def test_intent_classifier_200_calls(self):
        """El clasificador de intenciones procesa 200 llamadas sin degradarse."""
        from nlp.intent_classifier import IntentClassifier
        clf = IntentClassifier()

        test_cases = [
            ("Hola buenos días", "saludo"),
            ("¿Cuál es el horario?", "faq"),
            ("Tengo un problema con mi factura", "crear_ticket"),
            ("¿Estado de mi pedido?", "consultar_estado"),
            ("Estoy muy molesto", "queja"),
            ("Quiero hablar con un agente", "escalar_humano"),
            ("Gracias, hasta luego", "despedida"),
        ]

        start = time.time()
        errors = 0
        for i in range(200):
            text, expected_intent = test_cases[i % len(test_cases)]
            result = clf.classify(text)
            if not isinstance(result, str):
                errors += 1

        elapsed = time.time() - start
        assert errors == 0, f"{errors} clasificaciones retornaron tipo incorrecto"
        assert elapsed < 10.0, f"200 clasificaciones tomaron {elapsed:.2f}s"

    def test_entity_extractor_200_calls(self):
        """El extractor de entidades procesa 200 llamadas sin degradarse."""
        from nlp.entity_extractor import EntityExtractor
        ext = EntityExtractor()

        texts = [
            "Mi ticket TKT-2026-000001 tiene un problema",
            "Mi número es 3001234567",
            "Mi correo es test@example.com",
            "Me cobraron $250,000",
            "Pedido #123456 no ha llegado",
        ]

        start = time.time()
        for i in range(200):
            result = ext.extract_all(texts[i % len(texts)])
            assert isinstance(result, dict)
        elapsed = time.time() - start
        assert elapsed < 5.0, f"200 extracciones tomaron {elapsed:.2f}s"

    # ── Validadores bajo carga ────────────────────────────────────────────────

    def test_validators_500_calls(self):
        """Los validadores procesan 500 llamadas sin error."""
        from utils.validators import Validators

        phones = ["3001234567", "310ABC456", "", "3209876543", "123"]
        emails = ["a@b.com", "invalid", "", "x@y.co", "no-at"]
        intents = ["faq", "saludo", "desconocida", "crear_ticket", ""]

        start = time.time()
        for i in range(500):
            Validators.validate_phone(phones[i % len(phones)])
            Validators.validate_email(emails[i % len(emails)])
            Validators.validate_intent(intents[i % len(intents)])
        elapsed = time.time() - start
        assert elapsed < 3.0, f"500 validaciones tomaron {elapsed:.2f}s"

    # ── FAQ bajo carga ────────────────────────────────────────────────────────

    def test_faq_manager_300_queries(self):
        """FAQManager responde 300 consultas sin degradarse."""
        from business.faq_manager import FAQManager
        faq = FAQManager()

        queries = [
            "¿Cuál es el horario de atención?",
            "¿Dónde están ubicados?",
            "¿Qué servicios ofrecen?",
            "Pregunta sin sentido xyzabc",
            "Hola buenos días",
        ]

        start = time.time()
        for i in range(300):
            result = faq.answer(queries[i % len(queries)])
            assert isinstance(result, str)
        elapsed = time.time() - start
        assert elapsed < 5.0, f"300 consultas FAQ tomaron {elapsed:.2f}s"

    # ── Sanitización bajo carga ───────────────────────────────────────────────

    def test_sanitize_input_1000_calls(self):
        """sanitize_input() procesa 1000 llamadas sin degradarse."""
        from utils.validators import Validators

        inputs = [
            "<script>alert('xss')</script>",
            "Texto normal sin problemas",
            "'; DROP TABLE users; --",
            "A" * 500,
            "",
        ]

        start = time.time()
        for i in range(1000):
            result = Validators.sanitize_input(inputs[i % len(inputs)])
            assert isinstance(result, str)
        elapsed = time.time() - start
        assert elapsed < 5.0, f"1000 sanitizaciones tomaron {elapsed:.2f}s"

    # ── Cache bajo carga ──────────────────────────────────────────────────────

    def test_redis_cache_500_operations(self):
        """RedisCache (modo memoria) procesa 500 operaciones sin error."""
        from integrations.redis_cache import RedisCache
        cache = RedisCache(host="localhost", port=6380)  # Fuerza modo memoria

        start = time.time()
        errors = 0
        for i in range(500):
            key = f"stress_{i % 50}"  # Reutilizar 50 claves
            try:
                cache.set(key, {"index": i, "data": f"value_{i}"}, ttl=60)
                val = cache.get(key)
                if val is None:
                    errors += 1
            except Exception:
                errors += 1
        elapsed = time.time() - start

        assert errors <= 5, f"{errors} operaciones de cache fallaron"
        assert elapsed < 5.0, f"500 operaciones de cache tomaron {elapsed:.2f}s"

    # ── Conversation manager bajo carga ──────────────────────────────────────

    def test_conversation_manager_many_intents(self):
        """ConversationManager registra muchos intents sin error."""
        from core.conversation_manager import ConversationManager
        mgr = ConversationManager(session_id="stress-intents")

        start = time.time()
        intents = ["faq", "saludo", "crear_ticket", "consultar_estado", "despedida"]
        for i in range(500):
            mgr.register_intent(intents[i % len(intents)])
        elapsed = time.time() - start

        assert sum(mgr.intent_counts.values()) == 500
        assert elapsed < 2.0, f"500 registros de intent tomaron {elapsed:.2f}s"

    # ── Ticket system bajo carga ──────────────────────────────────────────────

    def test_ticket_system_100_creates_no_db(self):
        """TicketSystem crea 100 tickets en modo simulado sin error."""
        from business.ticket_system import TicketSystem
        ts = TicketSystem()
        ts._get_db = lambda: None  # Modo sin DB

        descriptions = [
            "Problema con factura",
            "Error en el servicio",
            "No funciona el sistema",
            "Cobro incorrecto",
            "Queja por atención",
        ]

        start = time.time()
        for i in range(100):
            entities = {"phone": f"300{i:07d}"}
            result = ts.create(entities, descriptions[i % len(descriptions)])
            assert isinstance(result, str)
        elapsed = time.time() - start

        assert elapsed < 10.0, f"100 tickets en modo simulado tomaron {elapsed:.2f}s"
