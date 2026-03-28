"""Tests de carga y concurrencia para el Agente de Voz."""

import pytest
import sys
import os
import time
from concurrent.futures import ThreadPoolExecutor, as_completed

sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "..", "src"))


class TestConcurrency:
    """Tests de concurrencia para el agente."""

    def test_concurrent_sessions_10(self):
        """10 sesiones concurrentes completan sin error."""
        num_sessions = 10
        results = []

        def run_session(session_id: str) -> dict:
            from core.agent import CustomerServiceAgent
            agent = CustomerServiceAgent(session_id=session_id)
            greeting = agent.start_call()
            response = agent.process_input(text_input="Hola, buenos días")
            farewell = agent.end_call()
            return {
                "session_id": session_id,
                "greeting_ok": len(greeting) > 0,
                "response_ok": isinstance(response, str),
                "farewell_ok": len(farewell) > 0,
                "deactivated": not agent.is_active,
            }

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {
                executor.submit(run_session, f"concurrent-{i:03d}"): i
                for i in range(num_sessions)
            }
            for future in as_completed(futures):
                try:
                    results.append(future.result(timeout=30))
                except Exception as e:
                    results.append({"error": str(e)})

        assert len(results) == num_sessions
        errors = [r for r in results if "error" in r]
        assert len(errors) == 0, f"Sesiones con error: {errors}"

        for r in results:
            assert r.get("greeting_ok") is True
            assert r.get("deactivated") is True

    def test_concurrent_sessions_5_with_faq(self):
        """5 sesiones concurrentes procesando preguntas FAQ."""
        num_sessions = 5
        results = []

        def run_faq_session(session_id: str) -> bool:
            from core.agent import CustomerServiceAgent
            agent = CustomerServiceAgent(session_id=session_id)
            agent.start_call()
            r1 = agent.process_input(text_input="¿Cuál es el horario de atención?")
            r2 = agent.process_input(text_input="¿Dónde están ubicados?")
            agent.end_call()
            return len(r1) > 0 and len(r2) > 0

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = [
                executor.submit(run_faq_session, f"faq-concurrent-{i}")
                for i in range(num_sessions)
            ]
            results = [f.result(timeout=30) for f in futures]

        assert all(results), "Todas las sesiones FAQ deben completar exitosamente"

    def test_concurrent_sessions_independent(self):
        """Las sesiones concurrentes mantienen estado independiente."""
        results = {}

        def run_with_marker(session_id: str, marker: str) -> str:
            from core.agent import CustomerServiceAgent
            agent = CustomerServiceAgent(session_id=session_id)
            agent.start_call()
            # Marcar la conversación con un ID único
            agent.conversation.set_context("marker", marker)
            time.sleep(0.05)  # Simular procesamiento
            stored_marker = agent.conversation.get_context("marker")
            agent.end_call()
            return stored_marker

        with ThreadPoolExecutor(max_workers=5) as executor:
            futures = {
                executor.submit(run_with_marker, f"iso-{i}", f"marker-{i}"): i
                for i in range(5)
            }
            for future, i in futures.items():
                results[i] = future.result(timeout=30)

        # Cada sesión debe tener su propio marcador
        for i in range(5):
            assert results[i] == f"marker-{i}", \
                f"Sesión {i} tiene marcador incorrecto: {results[i]}"

    def test_conversation_manager_thread_safe(self):
        """ConversationManager maneja múltiples operaciones desde hilos distintos."""
        from core.conversation_manager import ConversationManager

        manager = ConversationManager(session_id="thread-safe-test")
        errors = []

        def add_messages(count: int):
            for i in range(count):
                try:
                    manager.add_message("user", f"Mensaje {i}")
                except Exception as e:
                    errors.append(str(e))

        with ThreadPoolExecutor(max_workers=3) as executor:
            futures = [executor.submit(add_messages, 5) for _ in range(3)]
            for f in futures:
                f.result(timeout=10)

        assert len(errors) == 0, f"Errores en hilos: {errors}"

    def test_redis_cache_concurrent_access(self):
        """RedisCache maneja acceso concurrente sin corrupción."""
        from integrations.redis_cache import RedisCache
        cache = RedisCache(host="localhost", port=6380)  # Fallback a memoria
        errors = []
        results = {}

        def write_and_read(i: int):
            key = f"conc_test_{i}"
            cache.set(key, {"index": i}, ttl=60)
            time.sleep(0.02)
            val = cache.get(key)
            return val

        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = {executor.submit(write_and_read, i): i for i in range(10)}
            for future, i in futures.items():
                try:
                    results[i] = future.result(timeout=10)
                except Exception as e:
                    errors.append(str(e))

        assert len(errors) == 0
        # Al menos la mayoría de lecturas deben retornar los valores escritos
        correct = sum(1 for i, v in results.items() if v and v.get("index") == i)
        assert correct >= 7, f"Solo {correct}/10 valores fueron correctos"

    def test_performance_single_session_10_turns(self):
        """Una sesión de 10 turnos completa en menos de 10 segundos."""
        from core.agent import CustomerServiceAgent

        start = time.time()
        agent = CustomerServiceAgent(session_id="perf-test-001")
        agent.start_call()

        inputs = [
            "Hola", "¿Horario?", "Tengo un problema",
            "Problema con factura", "¿Estado de mi pedido?",
            "Estoy molesto", "Quiero hablar con supervisor",
            "¿Cuánto demoran?", "Gracias", "Adiós",
        ]
        for text in inputs:
            agent.process_input(text_input=text)

        agent.end_call()
        elapsed = time.time() - start

        assert elapsed < 10.0, f"10 turnos tomaron {elapsed:.1f}s (máximo 10s)"


class TestStressLite:
    """Tests de estrés ligeros (sin infraestructura externa)."""

    def test_100_intent_classifications(self):
        """100 clasificaciones de intención en tiempo razonable."""
        from nlp.intent_classifier import IntentClassifier

        classifier = IntentClassifier()
        texts = [
            "Hola buenos días", "¿Cuál es el horario?", "Tengo un problema",
            "Quiero un supervisor", "Gracias adiós", "Estoy molesto",
        ]
        start = time.time()
        for i in range(100):
            text = texts[i % len(texts)]
            result = classifier.classify(text)
            assert isinstance(result, str)
        elapsed = time.time() - start
        assert elapsed < 5.0, f"100 clasificaciones tomaron {elapsed:.2f}s"

    def test_100_entity_extractions(self):
        """100 extracciones de entidades en tiempo razonable."""
        from nlp.entity_extractor import EntityExtractor

        extractor = EntityExtractor()
        texts = [
            "Mi número es 3001234567",
            "Mi ticket es TKT-2026-000001",
            "Mi correo es test@test.com",
            "Me cobraron $150,000",
        ]
        start = time.time()
        for i in range(100):
            text = texts[i % len(texts)]
            result = extractor.extract_all(text)
            assert isinstance(result, dict)
        elapsed = time.time() - start
        assert elapsed < 3.0, f"100 extracciones tomaron {elapsed:.2f}s"

    def test_conversation_manager_1000_messages(self):
        """ConversationManager maneja 1000 mensajes sin degradarse."""
        from core.conversation_manager import ConversationManager

        mgr = ConversationManager(session_id="stress-conv-001")
        start = time.time()
        for i in range(1000):
            mgr.add_message("user" if i % 2 == 0 else "assistant", f"Mensaje de estrés {i}")
        elapsed = time.time() - start

        # Verificar que el historial está limitado
        history = mgr.get_history()
        assert len(history) <= mgr.MAX_HISTORY_IN_MEMORY
        assert elapsed < 2.0, f"1000 mensajes tomaron {elapsed:.2f}s"
