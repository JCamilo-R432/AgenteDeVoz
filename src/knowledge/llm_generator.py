"""
Generador de respuestas con LLM + Contexto de KB (RAG).
Usa Groq para velocidad (< 500ms).
"""
import os
import logging
from typing import Optional, Dict, List

logger = logging.getLogger(__name__)

class LLMResponseGenerator:
    """Genera respuestas naturales usando LLM + contexto de KB."""
    
    def __init__(self):
        self.api_key = os.getenv("GROQ_API_KEY") or os.getenv("OPENAI_API_KEY")
        self.model = os.getenv("LLM_MODEL", "llama3-8b-8192")  # Groq default
        self.base_url = os.getenv("LLM_BASE_URL", "https://api.groq.com/openai/v1")
        
    def generate(self, user_query: str, kb_context: List[Dict], 
                 emotion: Optional[Dict] = None) -> str:
        """
        Genera respuesta natural combinando query + contexto KB + emoción.
        """
        # Si no hay contexto de KB, usar fallback
        if not kb_context:
            return self._generate_fallback(user_query, emotion)
        
        # Construir prompt con contexto
        prompt = self._build_prompt(user_query, kb_context, emotion)
        
        try:
            # Intentar con Groq/OpenAI
            response = self._call_llm(prompt)
            if response:
                return response.strip()
        except Exception as e:
            logger.warning(f"LLM call failed: {e}")
        
        # Fallback si LLM falla
        return self._generate_fallback(user_query, emotion)
    
    def _build_prompt(self, query: str, kb_results: List[Dict], 
                      emotion: Optional[Dict]) -> str:
        """Construye prompt optimizado para respuesta concisa."""
        
        # Prefijo empático si hay emoción
        empathy_prefix = ""
        if emotion:
            emo = emotion.get("emotion", "neutral")
            if emo == "enojo":
                empathy_prefix = "El usuario está enojado. Respondé con empatía, validá su enojo y ofrecé solución inmediata.\n"
            elif emo == "tristeza":
                empathy_prefix = "El usuario está triste. Respondé con calidez y comprensión.\n"
            elif emo == "ansiedad":
                empathy_prefix = "El usuario tiene prisa/ansiedad. Respondé de forma rápida, clara y tranquilizadora.\n"
        
        # Contexto de KB formateado
        kb_text = "\n".join([
            f"- {r['question']}: {r['answer']}" 
            for r in kb_results[:2]  # Top 2 para no saturar
        ])
        
        return f"""{empathy_prefix}Sos un asistente de servicio al cliente de Econify.

INFORMACIÓN DISPONIBLE:
{kb_text}

PREGUNTA DEL USUARIO: "{query}"

INSTRUCCIONES:
1. Respondé EXACTAMENTE lo que preguntan, de forma natural y conversacional
2. Usá la información de arriba, pero NO la copies textual - adaptala al contexto
3. Sé breve (máx 3-4 oraciones) pero completo
4. Si la pregunta es sobre pagos/envíos/devoluciones, confirmá con "Sí" o "No" primero
5. Terminá invitando a continuar la conversación

RESPUESTA:"""
    
    def _call_llm(self, prompt: str, max_tokens: int = 200) -> Optional[str]:
        """Llama al LLM (Groq/OpenAI compatible)."""
        if not self.api_key:
            return None
        
        try:
            from openai import OpenAI
            
            client = OpenAI(
                api_key=self.api_key,
                base_url=self.base_url
            )
            
            response = client.chat.completions.create(
                model=self.model,
                messages=[{"role": "user", "content": prompt}],
                max_tokens=max_tokens,
                temperature=0.3,  # Bajo para respuestas consistentes
                timeout=5  # Timeout corto para no bloquear
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            logger.error(f"LLM API error: {e}")
            return None
    
    def _generate_fallback(self, query: str, emotion: Optional[Dict]) -> str:
        """Fallback cuando no hay KB match o LLM falla."""
        empathy = ""
        if emotion and emotion.get("intensity", 0) >= 7:
            empathy = "Entiendo que esto es importante para vos. "
        
        return f"""{empathy}Para darte la respuesta más precisa, ¿podrías contarme un poco más?

Estoy aquí para ayudarte con:
📋 Pedidos y compras
🧾 Facturación y comprobantes
💳 Métodos de pago y promociones
🚚 Envíos y seguimiento
🔄 Devoluciones y cambios

¿Sobre qué tema es tu consulta?"""

# Singleton
llm_generator = LLMResponseGenerator()
