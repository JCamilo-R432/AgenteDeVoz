"""
Voice Model Trainer - Entrenamiento y ajuste de modelos de voz personalizados
"""
import logging
from typing import List, Dict, Optional

logger = logging.getLogger(__name__)


class VoiceModelTrainer:
    """
    Gestiona el entrenamiento de modelos de voz personalizados.
    Permite adaptar el STT a vocabulario especifico del negocio
    (terminologia tecnica, nombres de productos, etc.)
    """

    def __init__(self):
        self._custom_phrases: List[str] = []
        self._boost_phrases: Dict[str, int] = {}  # phrase -> boost_value
        self._training_sessions: List[Dict] = []

    def add_domain_vocabulary(self, phrases: List[str], boost: int = 20) -> None:
        """
        Agrega vocabulario de dominio para mejorar precision del STT.

        Args:
            phrases: Lista de frases o palabras tecnicas del negocio
            boost: Valor de boost (1-20) para el modelo de lenguaje
        """
        for phrase in phrases:
            phrase = phrase.strip().lower()
            if phrase not in self._custom_phrases:
                self._custom_phrases.append(phrase)
                self._boost_phrases[phrase] = min(max(boost, 1), 20)

        logger.info(f"Agregadas {len(phrases)} frases al vocabulario de dominio")

    def get_speech_adaptation_config(self) -> Dict:
        """
        Retorna la configuracion de adaptacion para Google Cloud STT.
        Usar en SpeechContext al llamar recognize().
        """
        return {
            "phrases": self._custom_phrases,
            "speech_contexts": [
                {"phrases": self._custom_phrases, "boost": 15}
            ],
        }

    def get_default_vocabulary(self) -> List[str]:
        """Vocabulario por defecto para servicio al cliente en telecomunicaciones."""
        return [
            "numero de ticket", "estado del ticket", "escalacion",
            "plan tarifario", "facturacion", "portabilidad",
            "agente", "asistente", "soporte tecnico",
            "reconexion", "suspension", "contrato",
        ]

    def log_training_session(self, session_data: Dict) -> None:
        """Registra una sesion de entrenamiento para auditoria."""
        self._training_sessions.append(session_data)

    def get_training_history(self) -> List[Dict]:
        """Retorna el historial de sesiones de entrenamiento."""
        return self._training_sessions
