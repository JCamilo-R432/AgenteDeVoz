"""
LLM Response Generator — AgenteDeVoz
Genera respuestas naturales usando OpenAI o Anthropic con todo el contexto
de la conversación: historial, intención detectada, entidades, perfil del cliente.

Fallback automático:
  OpenAI → Anthropic → respuesta basada en reglas
"""
import logging
from typing import Dict, List, Optional, Any

from config.settings import settings

logger = logging.getLogger(__name__)

# Groq client (lazy loaded)
_groq_client = None

# ── System prompt base del agente ──────────────────────────────────────────────

SYSTEM_PROMPT = """Eres Ana, una agente virtual de atención al cliente profesional, amable y eficiente.

PERSONALIDAD:
- Hablas en español, de forma cálida pero profesional
- Eres concisa: tus respuestas de voz deben tener máximo 2-3 oraciones
- Nunca dices que eres una IA a menos que te lo pregunten directamente
- Siempre buscas resolver el problema del cliente en el menor número de pasos

CAPACIDADES:
- Responder preguntas frecuentes sobre el servicio
- Crear tickets de soporte con número de seguimiento
- Consultar el estado de pedidos y tickets existentes
- Registrar quejas formales
- Transferir con agentes humanos cuando sea necesario

INFORMACIÓN DE LA EMPRESA:
{company_context}

CONTEXTO DEL CLIENTE:
{customer_context}

INTENCIÓN DETECTADA: {intent}
ENTIDADES EXTRAÍDAS: {entities}

INSTRUCCIONES:
1. Responde directamente al último mensaje del usuario
2. Si detectas frustración, muestra empatía ANTES de dar la solución
3. Si necesitas crear un ticket, hazlo y menciona el número en la respuesta
4. Si no tienes la información, ofrece crear un ticket o transferir
5. Tus respuestas serán convertidas a voz, evita markdown, listas con guiones, o caracteres especiales
6. Usa puntuación normal para que el TTS suene natural"""


COMPANY_CONTEXT_DEFAULT = """
- Horario de atención presencial: Lunes a Viernes 8am-6pm, Sábados 9am-1pm
- Atención virtual 24/7 por este canal
- Tiempo de respuesta tickets: Urgente=2h, Alta=8h, Media=24h, Baja=72h
- Garantía de productos: 12 meses contra defectos de fabricación
- Métodos de pago: Tarjeta débito/crédito, PSE, transferencia, efectivo
- Contacto: Tel 601-555-1234 | soporte@empresa.com | WhatsApp 300-123-4567
"""


class ResponseGenerator:
    """
    Genera respuestas conversacionales usando LLM con contexto completo.

    Prioridad de proveedor:
      1. OpenAI (si OPENAI_API_KEY está configurada)
      2. Anthropic (si ANTHROPIC_API_KEY está configurada)
      3. Fallback a respuestas basadas en reglas (siempre disponible)
    """

    # Tokens máximos para la respuesta (voz: respuestas cortas)
    MAX_TOKENS = 150
    TEMPERATURE = 0.4  # Baja para consistencia, suficiente para naturalidad

    def __init__(self, company_context: Optional[str] = None):
        self.company_context = company_context or COMPANY_CONTEXT_DEFAULT
        self._openai_client = None
        self._anthropic_client = None
        self._init_clients()

    def _init_clients(self) -> None:
        if settings.OPENAI_API_KEY:
            try:
                from openai import OpenAI
                self._openai_client = OpenAI(api_key=settings.OPENAI_API_KEY)
                logger.info("ResponseGenerator: OpenAI listo")
            except Exception as e:
                logger.warning(f"ResponseGenerator: OpenAI no disponible — {e}")

        if settings.ANTHROPIC_API_KEY:
            try:
                import anthropic
                self._anthropic_client = anthropic.Anthropic(
                    api_key=settings.ANTHROPIC_API_KEY
                )
                logger.info("ResponseGenerator: Anthropic listo")
            except Exception as e:
                logger.warning(f"ResponseGenerator: Anthropic no disponible — {e}")

    def _get_groq_client(self):
        """Inicializa cliente Groq si está configurado."""
        global _groq_client
        if _groq_client is None and settings.GROQ_API_KEY:
            try:
                from groq import Groq
                _groq_client = Groq(api_key=settings.GROQ_API_KEY)
                logger.info("ResponseGenerator: Groq listo")
            except Exception as e:
                logger.warning(f"ResponseGenerator: Groq no disponible — {e}")
        return _groq_client

    # ── API pública ────────────────────────────────────────────────────────────

    def generate(
        self,
        user_text: str,
        history: List[Dict[str, str]],
        intent: str,
        entities: Dict[str, Any],
        customer_context: Optional[Dict[str, Any]] = None,
        action_result: Optional[str] = None,
    ) -> str:
        """
        Genera una respuesta natural para el usuario.

        Args:
            user_text:        Último mensaje del usuario.
            history:          Historial completo (formato OpenAI: role/content).
            intent:           Intención detectada por el clasificador.
            entities:         Entidades extraídas del mensaje.
            customer_context: Datos del cliente (nombre, cuenta, historial).
            action_result:    Resultado de acción ejecutada (ej: "Ticket TKT-2024-001234 creado").

        Returns:
            Texto de respuesta listo para TTS.
        """
        system = self._build_system_prompt(intent, entities, customer_context, action_result)
        messages = self._build_messages(history, user_text)

        # Intentar LLM en orden de preferencia
        if self._openai_client:
            response = self._call_openai(system, messages)
            if response:
                logger.info(f"Respuesta generada por OpenAI | intent={intent}")
                return response

        if self._anthropic_client:
            response = self._call_anthropic(system, messages)
            if response:
                logger.info(f"Respuesta generada por Anthropic | intent={intent}")
                return response

        # Fallback a respuesta contextual sin LLM
        logger.warning("LLM no disponible, usando fallback de reglas")
        return self._rule_based_fallback(intent, entities, action_result, customer_context)

    # ── Construcción de prompts ────────────────────────────────────────────────

    def _build_system_prompt(
        self,
        intent: str,
        entities: Dict,
        customer_context: Optional[Dict],
        action_result: Optional[str],
    ) -> str:
        # Contexto del cliente
        if customer_context:
            name = customer_context.get("name", "")
            account = customer_context.get("account_id", "")
            plan = customer_context.get("plan", "")
            history_summary = customer_context.get("history_summary", "Sin historial previo")
            customer_str = (
                f"Nombre: {name or 'No identificado'} | "
                f"Cuenta: {account or 'No verificada'} | "
                f"Plan: {plan or 'No especificado'} | "
                f"Historial: {history_summary}"
            )
        else:
            customer_str = "Cliente no autenticado aún"

        # Incluir resultado de acción ejecutada si existe
        if action_result:
            customer_str += f"\n\nACCIÓN COMPLETADA: {action_result}"

        entities_str = (
            ", ".join(f"{k}={v}" for k, v in entities.items())
            if entities else "ninguna"
        )

        return SYSTEM_PROMPT.format(
            company_context=self.company_context,
            customer_context=customer_str,
            intent=intent,
            entities=entities_str,
        )

    def _build_messages(
        self,
        history: List[Dict[str, str]],
        user_text: str,
    ) -> List[Dict[str, str]]:
        """Combina historial + mensaje actual. Limita a los últimos 8 turnos."""
        # Solo role y content, sin timestamp
        clean_history = [
            {"role": m["role"], "content": m["content"]}
            for m in history[-8:]
            if m.get("role") in ("user", "assistant") and m.get("content")
        ]
        # Evitar duplicar el último mensaje si ya está en historial
        if clean_history and clean_history[-1]["role"] == "user":
            clean_history = clean_history[:-1]

        clean_history.append({"role": "user", "content": user_text})
        return clean_history

    # ── Proveedores LLM ────────────────────────────────────────────────────────

    def _call_openai(
        self,
        system: str,
        messages: List[Dict[str, str]],
    ) -> Optional[str]:
        try:
            response = self._openai_client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "system", "content": system}] + messages,
                max_tokens=self.MAX_TOKENS,
                temperature=self.TEMPERATURE,
                timeout=8.0,
            )
            text = response.choices[0].message.content.strip()
            return text if text else None
        except Exception as e:
            logger.warning(f"OpenAI response generation failed: {e}")
            return None

    def _call_anthropic(
        self,
        system: str,
        messages: List[Dict[str, str]],
    ) -> Optional[str]:
        try:
            response = self._anthropic_client.messages.create(
                model="claude-haiku-4-5-20251001",
                system=system,
                messages=messages,
                max_tokens=self.MAX_TOKENS,
                temperature=self.TEMPERATURE,
            )
            text = response.content[0].text.strip()
            return text if text else None
        except Exception as e:
            logger.warning(f"Anthropic response generation failed: {e}")
            return None

    # ── Fallback de reglas ─────────────────────────────────────────────────────

    def _rule_based_fallback(
        self,
        intent: str,
        entities: Dict,
        action_result: Optional[str],
        customer_context: Optional[Dict],
    ) -> str:
        """Respuesta mínima cuando no hay LLM disponible."""
        if action_result:
            return action_result

        name = ""
        if customer_context:
            name = customer_context.get("name", "")
        greeting = f"{name}, " if name else ""

        fallbacks = {
            "saludo": (
                f"Hola {name}! Bienvenido. ¿En qué puedo ayudarte hoy?"
                if name else
                "¡Hola! Bienvenido. ¿En qué puedo ayudarte hoy?"
            ),
            "faq": f"{greeting}Déjame buscar esa información para ti. ¿Puedes darme más detalles?",
            "crear_ticket": f"{greeting}Entendido. Voy a registrar tu caso ahora mismo.",
            "consultar_estado": f"{greeting}Permíteme verificar el estado de tu solicitud.",
            "queja": f"{greeting}Entiendo tu molestia y lo siento mucho. Voy a escalar tu caso de inmediato.",
            "escalar_humano": f"{greeting}Por supuesto, te voy a transferir con un agente humano ahora.",
            "despedida": f"Fue un placer atenderte{', ' + name if name else ''}. ¡Que tengas un excelente día!",
        }
        return fallbacks.get(intent, f"{greeting}Entendido. ¿Cómo puedo ayudarte mejor?")
