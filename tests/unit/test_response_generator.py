"""
Tests: ResponseGenerator
Verifica la generación de respuestas LLM con fallbacks.
"""
import pytest
from unittest.mock import MagicMock, patch


@pytest.fixture
def generator():
    from nlp.response_generator import ResponseGenerator
    return ResponseGenerator()


class TestResponseGeneratorInit:
    def test_importable(self):
        from nlp.response_generator import ResponseGenerator
        assert ResponseGenerator is not None

    def test_instantiates(self, generator):
        assert generator is not None

    def test_has_company_context(self, generator):
        assert generator.company_context
        assert len(generator.company_context) > 20


class TestBuildMessages:
    def test_appends_user_message(self, generator):
        history = [{"role": "assistant", "content": "Hola, ¿en qué te ayudo?"}]
        messages = generator._build_messages(history, "Quiero crear un ticket")
        assert messages[-1]["role"] == "user"
        assert messages[-1]["content"] == "Quiero crear un ticket"

    def test_limits_history_to_8_turns(self, generator):
        history = [
            {"role": "user" if i % 2 == 0 else "assistant", "content": f"msg {i}"}
            for i in range(20)
        ]
        messages = generator._build_messages(history, "nuevo mensaje")
        assert len(messages) <= 9  # 8 history + 1 current

    def test_removes_timestamp_from_history(self, generator):
        history = [{"role": "user", "content": "hola", "timestamp": "2026-01-01T00:00:00"}]
        messages = generator._build_messages(history, "siguiente")
        for m in messages:
            assert "timestamp" not in m

    def test_empty_history(self, generator):
        messages = generator._build_messages([], "primera pregunta")
        assert len(messages) == 1
        assert messages[0]["content"] == "primera pregunta"


class TestBuildSystemPrompt:
    def test_contains_intent(self, generator):
        prompt = generator._build_system_prompt("crear_ticket", {}, None, None)
        assert "crear_ticket" in prompt

    def test_contains_entities(self, generator):
        prompt = generator._build_system_prompt("faq", {"phone": "3001234567"}, None, None)
        assert "3001234567" in prompt

    def test_contains_action_result(self, generator):
        prompt = generator._build_system_prompt(
            "crear_ticket", {}, None, "Ticket TKT-2026-001234 creado"
        )
        assert "TKT-2026-001234" in prompt

    def test_contains_customer_name(self, generator):
        ctx = {"name": "Carlos", "account_id": "ACC-001", "plan": "pro"}
        prompt = generator._build_system_prompt("saludo", {}, ctx, None)
        assert "Carlos" in prompt

    def test_unauthenticated_customer(self, generator):
        prompt = generator._build_system_prompt("saludo", {}, None, None)
        assert "no autenticado" in prompt.lower() or "No identificado" in prompt


class TestOpenAIIntegration:
    def test_generate_uses_openai_when_available(self, generator):
        mock_response = MagicMock()
        mock_response.choices[0].message.content = "Claro, te ayudo con eso."

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response
        generator._openai_client = mock_client
        generator._anthropic_client = None

        result = generator.generate(
            user_text="Hola",
            history=[],
            intent="saludo",
            entities={},
        )
        assert result == "Claro, te ayudo con eso."
        mock_client.chat.completions.create.assert_called_once()

    def test_falls_back_to_anthropic_on_openai_error(self, generator):
        mock_openai = MagicMock()
        mock_openai.chat.completions.create.side_effect = Exception("rate limit")

        mock_message = MagicMock()
        mock_message.content[0].text = "Hola, soy Ana."
        mock_anthropic = MagicMock()
        mock_anthropic.messages.create.return_value = mock_message

        generator._openai_client = mock_openai
        generator._anthropic_client = mock_anthropic

        result = generator.generate("Hola", [], "saludo", {})
        assert result == "Hola, soy Ana."

    def test_falls_back_to_rules_when_both_fail(self, generator):
        mock_openai = MagicMock()
        mock_openai.chat.completions.create.side_effect = Exception("error")
        mock_anthropic = MagicMock()
        mock_anthropic.messages.create.side_effect = Exception("error")

        generator._openai_client = mock_openai
        generator._anthropic_client = mock_anthropic

        result = generator.generate("Hola", [], "saludo", {})
        assert isinstance(result, str)
        assert len(result) > 5

    def test_no_llm_uses_rule_fallback(self, generator):
        generator._openai_client = None
        generator._anthropic_client = None

        result = generator.generate("Hola", [], "saludo", {})
        assert "Hola" in result or "Bienvenido" in result


class TestRuleBasedFallback:
    def test_saludo_fallback(self, generator):
        result = generator._rule_based_fallback("saludo", {}, None, None)
        assert "Hola" in result or "Bienvenido" in result

    def test_despedida_fallback(self, generator):
        result = generator._rule_based_fallback("despedida", {}, None, None)
        assert "placer" in result.lower() or "día" in result.lower()

    def test_queja_fallback_shows_empathy(self, generator):
        result = generator._rule_based_fallback("queja", {}, None, None)
        assert "molestia" in result.lower() or "siento" in result.lower()

    def test_action_result_returned_directly(self, generator):
        result = generator._rule_based_fallback(
            "crear_ticket", {}, "Ticket TKT-2026-001234 creado exitosamente.", None
        )
        assert "TKT-2026-001234" in result

    def test_uses_customer_name_in_fallback(self, generator):
        ctx = {"name": "María"}
        result = generator._rule_based_fallback("saludo", {}, None, ctx)
        assert "María" in result

    def test_unknown_intent_returns_generic(self, generator):
        result = generator._rule_based_fallback("unknown_intent_xyz", {}, None, None)
        assert isinstance(result, str)
        assert len(result) > 5
