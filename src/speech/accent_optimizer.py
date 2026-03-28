"""
Accent Optimizer - AgenteDeVoz
Gap #17: STT optimizado para acentos regionales y condiciones adversas

Mejora la precision del STT para:
- Acentos de Colombia, Mexico, Argentina, Espana, Chile, Peru
- Audio con ruido ambiental (call center, calle, etc.)
- Habla rapida o lenta
- Vocabulario tecnico/regional
"""
import logging
from typing import Dict, List, Optional, Tuple
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)


class RegionalAccent(Enum):
    COLOMBIA = "es-CO"
    MEXICO = "es-MX"
    ARGENTINA = "es-AR"
    SPAIN = "es-ES"
    CHILE = "es-CL"
    PERU = "es-PE"
    DEFAULT = "es-419"  # Espanol latinoamericano generico


@dataclass
class AccentProfile:
    accent: RegionalAccent
    phonetic_variations: Dict[str, List[str]]
    common_words: List[str]
    speech_rate_factor: float   # 0.8 a 1.2 (relativo a velocidad base)
    confidence_threshold: float
    google_stt_model: str       # Modelo Google STT recomendado


class AccentOptimizer:
    """
    Optimizador de STT para acentos regionales.
    Mejora la precision del reconocimiento ajustando configuracion
    del STT engine y post-procesando transcripciones.
    """

    def __init__(self):
        self.accent_profiles = self._load_accent_profiles()
        self.active_accent: Optional[RegionalAccent] = None
        self.adaptation_history: List[Dict] = []
        logger.info("AccentOptimizer inicializado con %d perfiles", len(self.accent_profiles))

    def _load_accent_profiles(self) -> Dict[RegionalAccent, AccentProfile]:
        """Carga perfiles de acentos regionales con sus particularidades."""
        return {
            RegionalAccent.COLOMBIA: AccentProfile(
                accent=RegionalAccent.COLOMBIA,
                phonetic_variations={
                    "ll": ["y", "ll"],       # Yeismo regional
                    "s_final": ["s", ""],    # Aspiracion de s final
                    "d_inter": ["d", ""],    # Perdida de d intervocalica
                },
                common_words=[
                    "parce", "chevere", "bacano", "mas o menos", "pues",
                    "listo", "hagame el favor", "sumercé", "chino"
                ],
                speech_rate_factor=1.0,
                confidence_threshold=0.85,
                google_stt_model="latest_long",
            ),
            RegionalAccent.MEXICO: AccentProfile(
                accent=RegionalAccent.MEXICO,
                phonetic_variations={
                    "x": ["x", "j"],         # Sonido de x/j alternado
                    "tl": ["tl", "t"],       # Simplificacion de tl
                    "s_final": ["s"],        # Conservacion de s final
                },
                common_words=[
                    "orale", "que onda", "chido", "cuate", "padre",
                    "ahorita", "mande", "no manches", "wey"
                ],
                speech_rate_factor=1.05,
                confidence_threshold=0.85,
                google_stt_model="latest_long",
            ),
            RegionalAccent.ARGENTINA: AccentProfile(
                accent=RegionalAccent.ARGENTINA,
                phonetic_variations={
                    "ll": ["sh", "zh", "y"],  # Sheismo porteno
                    "y": ["sh", "zh", "y"],
                    "vos_pronoun": ["vos"],   # Voseo
                },
                common_words=[
                    "che", "copado", "barbaro", "boludo", "piba",
                    "laburo", "mina", "fiaca", "groso"
                ],
                speech_rate_factor=0.95,
                confidence_threshold=0.85,
                google_stt_model="latest_long",
            ),
            RegionalAccent.SPAIN: AccentProfile(
                accent=RegionalAccent.SPAIN,
                phonetic_variations={
                    "c_z": ["th", "s"],    # Distincion castellana
                    "ll": ["y", "ll"],
                    "s_aspiration": [],    # Sin aspiracion de s
                },
                common_words=[
                    "tio", "guay", "vale", "mola", "coger",
                    "coche", "ordenador", "movil", "chaval"
                ],
                speech_rate_factor=1.1,
                confidence_threshold=0.85,
                google_stt_model="latest_long",
            ),
            RegionalAccent.CHILE: AccentProfile(
                accent=RegionalAccent.CHILE,
                phonetic_variations={
                    "ch": ["sh", "ch"],     # Pronunciacion palatizada
                    "s_final": ["h", ""],   # Aspiracion/supresion de s final
                    "d_inter": ["d", ""],
                },
                common_words=[
                    "po", "weon", "cachai", "fome", "altiro",
                    "puta madre", "cuico", "filete", "galletita"
                ],
                speech_rate_factor=1.05,
                confidence_threshold=0.83,
                google_stt_model="latest_long",
            ),
            RegionalAccent.PERU: AccentProfile(
                accent=RegionalAccent.PERU,
                phonetic_variations={
                    "ll": ["y", "ll"],
                    "vocales_andinas": ["e/i", "o/u"],  # Confusion vocalica andina
                },
                common_words=[
                    "pe", "causa", "pata", "jerma", "chibolo",
                    "bacán", "misio", "al toque", "chompa"
                ],
                speech_rate_factor=0.98,
                confidence_threshold=0.84,
                google_stt_model="latest_long",
            ),
        }

    def detect_accent(self, audio_features: Dict) -> RegionalAccent:
        """
        Detecta acento basado en caracteristicas del audio y transcripcion.

        Args:
            audio_features: Dict con "transcribed_words", "phonetic_patterns", etc.

        Returns:
            RegionalAccent detectado
        """
        common_words = audio_features.get("transcribed_words", [])
        words_lower = [w.lower() for w in common_words]

        accent_scores: Dict[RegionalAccent, int] = {a: 0 for a in RegionalAccent}

        for accent, profile in self.accent_profiles.items():
            for word in profile.common_words:
                if word in " ".join(words_lower):
                    accent_scores[accent] += 2

        best_accent = max(accent_scores, key=accent_scores.get)

        if accent_scores[best_accent] > 0:
            self.active_accent = best_accent
            logger.info("Acento detectado: %s", best_accent.value)
            return best_accent

        # Fallback: si la app es para Colombia, usar ese como default
        self.active_accent = RegionalAccent.COLOMBIA
        return RegionalAccent.COLOMBIA

    def get_stt_config(self, accent: RegionalAccent) -> Dict:
        """
        Retorna la configuracion optima de Google Cloud STT para el acento.

        Returns:
            Dict compatible con google.cloud.speech.RecognitionConfig
        """
        profile = self.accent_profiles.get(accent)
        language_code = accent.value if accent != RegionalAccent.DEFAULT else "es-419"

        config = {
            "language_code": language_code,
            "model": profile.google_stt_model if profile else "latest_long",
            "use_enhanced": True,
            "enable_automatic_punctuation": True,
            "enable_word_confidence": True,
            "alternative_language_codes": ["es-419"],  # Fallback
            "speech_contexts": self._get_speech_contexts(accent),
        }

        if profile:
            config["speech_contexts"].extend([
                {"phrases": profile.common_words, "boost": 15}
            ])

        return config

    def _get_speech_contexts(self, accent: RegionalAccent) -> List[Dict]:
        """Contextos de habla para mejorar reconocimiento de vocabulario del dominio."""
        base_phrases = [
            "numero de ticket", "estado del ticket", "escalacion",
            "soporte tecnico", "facturacion", "reconexion",
            "agente", "asistente", "plan tarifario"
        ]
        return [{"phrases": base_phrases, "boost": 10}]

    def optimize_transcript(self, text: str, accent: RegionalAccent) -> str:
        """
        Post-procesa transcripcion para corregir errores tipicos del acento.

        Args:
            text: Transcripcion original del STT
            accent: Acento detectado

        Returns:
            Transcripcion optimizada
        """
        if accent not in self.accent_profiles:
            return text

        optimized = text
        profile = self.accent_profiles[accent]

        # Correcciones especificas por acento
        if accent == RegionalAccent.ARGENTINA:
            # Normalizar voseo a tuteo para el NLP
            voseo_replacements = {
                "vos sos": "tu eres",
                "vos tenes": "tu tienes",
                "vos queres": "tu quieres",
                "vos podes": "tu puedes",
            }
            for voseo, tuteo in voseo_replacements.items():
                optimized = optimized.replace(voseo, tuteo)

        self.adaptation_history.append({
            "original": text,
            "optimized": optimized,
            "accent": accent.value,
        })

        return optimized

    def adapt_to_speech_rate(self, audio_duration_s: float, word_count: int) -> float:
        """
        Calcula y retorna el factor de velocidad de habla.

        Args:
            audio_duration_s: Duracion del audio en segundos
            word_count: Numero de palabras transcritas

        Returns:
            Factor de velocidad (1.0 = velocidad normal)
        """
        if audio_duration_s <= 0 or word_count <= 0:
            return 1.0

        # Velocidad en palabras por minuto
        wpm = (word_count / audio_duration_s) * 60

        # Velocidad normal: ~130-150 wpm
        normal_wpm = 140.0
        rate_factor = wpm / normal_wpm

        # Limitar a rango razonable
        rate_factor = max(0.5, min(2.0, rate_factor))

        if rate_factor < 0.7:
            logger.info("Habla lenta detectada (WPM: %.0f, factor: %.2f)", wpm, rate_factor)
        elif rate_factor > 1.4:
            logger.info("Habla rapida detectada (WPM: %.0f, factor: %.2f)", wpm, rate_factor)

        return rate_factor

    def handle_noisy_audio(self, audio_data: bytes, snr_db: float) -> Tuple[bytes, str]:
        """
        Evalua y opcionalmente pre-procesa audio con ruido.

        Args:
            audio_data: Audio en bytes (PCM16)
            snr_db: Signal-to-Noise Ratio en dB

        Returns:
            (audio_procesado, nivel_ruido)
        """
        if snr_db < 10:
            noise_level = "high"
            logger.warning("Ruido alto detectado (SNR: %.1f dB) - aplicando filtro", snr_db)
            audio_data = self._apply_noise_reduction(audio_data)
        elif snr_db < 20:
            noise_level = "moderate"
            logger.info("Ruido moderado (SNR: %.1f dB)", snr_db)
        else:
            noise_level = "low"

        return audio_data, noise_level

    def _apply_noise_reduction(self, audio_data: bytes) -> bytes:
        """
        Aplica reduccion de ruido al audio.
        En produccion usar: pip install noisereduce librosa
        """
        try:
            import noisereduce as nr  # type: ignore
            import numpy as np
            audio_array = np.frombuffer(audio_data, dtype=np.int16).astype(np.float32)
            reduced = nr.reduce_noise(y=audio_array, sr=16000)
            return reduced.astype(np.int16).tobytes()
        except ImportError:
            logger.debug("noisereduce no disponible, retornando audio original")
            return audio_data

    def get_accuracy_metrics(self, accent: RegionalAccent) -> Dict:
        """Retorna metricas de precision para el acento dado."""
        history_for_accent = [
            h for h in self.adaptation_history if h.get("accent") == accent.value
        ]
        return {
            "accent": accent.value,
            "total_samples": len(history_for_accent),
            "accuracy": 0.92,        # Placeholder; en prod calcular con ground truth
            "wer": 0.08,             # Word Error Rate
            "cer": 0.05,             # Character Error Rate
            "optimizations_applied": len([h for h in history_for_accent if h["original"] != h["optimized"]]),
        }

    def fine_tune_model(self, training_data: List[Tuple[str, str]]) -> bool:
        """
        Fine-tuning del modelo con datos especificos del cliente.

        Args:
            training_data: Lista de (transcripcion_stt, transcripcion_correcta)
        """
        if len(training_data) < 10:
            logger.warning("Se necesitan al menos 10 muestras para fine-tuning")
            return False

        logger.info("Iniciando fine-tuning con %d muestras", len(training_data))
        # En produccion: Google Cloud STT Custom Models o Speech Adaptation API
        # https://cloud.google.com/speech-to-text/docs/adaptation
        logger.info("En produccion: usar Google Speech Adaptation API con phrases boost")
        return True
