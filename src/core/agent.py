import logging
from datetime import datetime
from typing import Dict, Optional

from config.settings import settings
from core.conversation_manager import ConversationManager
from core.quick_responses import get_quick_response
from nlp.intent_classifier import IntentClassifier
from nlp.entity_extractor import EntityExtractor
from nlp.response_generator import ResponseGenerator
from speech.stt_engine import STTEngine
from speech.tts_engine import TTSEngine
from utils.validators import Validators
from business.faq_manager import FAQManager

logger = logging.getLogger(__name__)


class CustomerServiceAgent:
    """Agente de Servicio al Cliente con quick_responses."""
    
    def __init__(self, session_id: str):
        self.session_id = session_id
        self.is_active = True
        self.conversation = ConversationManager(session_id)
        self.intent_classifier = IntentClassifier()
        self.entity_extractor = EntityExtractor()
        self.response_generator = ResponseGenerator()
        self.stt = STTEngine()
        self.tts = TTSEngine()
        self.faq = FAQManager()
        self.logger = logging.getLogger(f"agent.{session_id}")
        self.logger.info(f"Agente inicializado | Sesión: {session_id}")
    
    def process_input(
        self,
        audio_input: Optional[str] = None,
        text_input: Optional[str] = None,
    ) -> str:
        """Procesa entrada con quick_responses."""
        if not self.is_active:
            return "La sesión ha finalizado."

        try:
            # 1. Obtener texto
            if audio_input:
                user_text = self.stt.transcribe(audio_input)
                if not user_text:
                    return self._handle_silence()
            else:
                user_text = text_input

            if not user_text or not user_text.strip():
                return self._handle_silence()

            # 2. Sanitizar
            user_text = Validators.sanitize_input(user_text)
            self.logger.info(f"[{self.session_id}] Usuario: {user_text}")

            # 3. Quick responses (PRIMARY)
            quick_response = get_quick_response(user_text)
            if quick_response:
                self.conversation.add_message("user", user_text)
                self.conversation.add_message("assistant", quick_response)
                self.logger.info(f"[{self.session_id}] Quick: {quick_response[:80]}...")
                try:
                    self.tts.speak(quick_response)
                except:
                    pass
                return quick_response

            # 4. Fallback
            fallback = "Para ayudarte mejor, ¿podrías contarme un poco más? Estoy aquí para: 📋 Pedidos, 🧾 Facturación, 💳 Pagos, 🚚 Envíos, 🔄 Devoluciones. ¿Sobre qué tema?"
            
            self.conversation.add_message("user", user_text)
            self.conversation.add_message("assistant", fallback)
            try:
                self.tts.speak(fallback)
            except:
                pass
            return fallback

        except Exception as e:
            self.logger.error(f"[{self.session_id}] Error: {e}", exc_info=True)
            return "Disculpa el inconveniente. ¿Podrías repetirme qué necesitás?"
    
    def _handle_silence(self) -> str:
        """Maneja silencio o input vacío."""
        return "¿Hola? ¿Estás ahí? Por favor, decime en qué te ayudo."
    
    def end_session(self):
        """Finaliza la sesión."""
        self.is_active = False
        self.logger.info(f"[{self.session_id}] Sesión finalizada")
