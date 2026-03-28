"""
Agente de Servicio al Cliente con LLM nativo.
Entiende, conoce, genera y recuerda - como un humano.
"""
import os
import logging
from typing import Optional, List, Dict
from openai import OpenAI

from core.agent_system_prompt import SYSTEM_PROMPT, SYSTEM_PROMPT_SHORT
from knowledge.kb import kb  # Base de conocimiento para RAG

logger = logging.getLogger(__name__)

class LLMAgent:
    """Agente con LLM para respuestas naturales y contextuales."""
    
    def __init__(self, session_id: str, use_short_prompt: bool = False):
        self.session_id = session_id
        self.api_key = os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
        self.model = os.getenv("LLM_MODEL", "llama3-8b-8192")
        self.system_prompt = SYSTEM_PROMPT_SHORT if use_short_prompt else SYSTEM_PROMPT
        self.conversation_history: List[Dict] = []
        
        # Configurar cliente (Groq es compatible con API de OpenAI)
        if self.api_key:
            self.client = OpenAI(api_key=self.api_key, base_url=self.base_url)
        else:
            self.client = None
            logger.warning("No API key configured - LLM calls will fail")
    
    def process(self, user_message: str, emotion: Optional[Dict] = None) -> str:
        """
        Procesa mensaje del usuario y genera respuesta con LLM.
        """
        # 1. Agregar mensaje al historial
        self.conversation_history.append({"role": "user", "content": user_message})
        
        # 2. Buscar contexto relevante en KB (RAG)
        kb_context = self._get_kb_context(user_message)
        
        # 3. Construir mensajes para el LLM
        messages = self._build_messages(user_message, kb_context, emotion)
        
        # 4. Generar respuesta con LLM
        response = self._call_llm(messages)
        
        # 5. Agregar respuesta al historial
        self.conversation_history.append({"role": "assistant", "content": response})
        
        # 6. Limitar historial para no saturar contexto
        self._trim_history(max_turns=10)
        
        return response
    
    def _get_kb_context(self, query: str) -> str:
        """Busca información relevante en la base de conocimiento."""
        if not kb:
            return ""
        
        results = kb.search(query, top_k=3)
        if not results:
            return ""
        
        # Formatear contexto para el LLM
        context_parts = []
        for r in results:
            context_parts.append(f"• {r['answer']}")
        
        return "\n".join(context_parts)
    
    def _build_messages(self, user_message: str, kb_context: str, 
                        emotion: Optional[Dict]) -> List[Dict]:
        """Construye la conversación para enviar al LLM."""
        messages = [{"role": "system", "content": self.system_prompt}]
        
        # Agregar contexto de KB si existe
        if kb_context:
            kb_instruction = f"\n\n📚 INFORMACIÓN RELEVANTE DISPONIBLE:\n{kb_context}"
            # Inyectar contexto en el último mensaje de sistema o como user
            messages.append({
                "role": "user", 
                "content": f"Contexto disponible: {kb_context}\n\nPregunta del usuario: {user_message}"
            })
        else:
            messages.append({"role": "user", "content": user_message})
        
        # Agregar historial reciente (últimos 6 mensajes para contexto)
        for msg in self.conversation_history[-6:]:
            if msg["role"] == "user" and msg["content"] != user_message:
                messages.append(msg)
        
        return messages
    
    def _call_llm(self, messages: List[Dict], max_tokens: int = 300) -> str:
        """Llama al LLM y retorna la respuesta."""
        if not self.client:
            return self._fallback_response(messages[-1]["content"])
        
        try:
            response = self.client.chat.completions.create(
                model=self.model,
                messages=messages,
                max_tokens=max_tokens,
                temperature=0.3,  # Bajo para consistencia
                top_p=0.9,
                timeout=8  # Timeout razonable
            )
            
            return response.choices[0].message.content.strip()
            
        except Exception as e:
            logger.error(f"LLM call failed: {e}")
            return self._fallback_response(messages[-1]["content"])
    
    def _fallback_response(self, user_message: str) -> str:
        """Fallback cuando el LLM no está disponible."""
        # Respuesta genérica pero útil
        return f"Entiendo tu consulta: \"{user_message[:50]}...\". Para darte la mejor respuesta, ¿podrías contarme un poco más? Estoy aquí para ayudarte con pedidos, pagos, envíos, devoluciones o facturación. ¿En qué te ayudo?"
    
    def _trim_history(self, max_turns: int):
        """Mantiene el historial dentro de límites razonables."""
        # Mantener solo los últimos N turnos (user+assistant = 1 turno)
        if len(self.conversation_history) > max_turns * 2:
            self.conversation_history = self.conversation_history[-max_turns*2:]
    
    def reset(self):
        """Resetea la conversación."""
        self.conversation_history = []
