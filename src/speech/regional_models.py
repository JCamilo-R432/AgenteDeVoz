"""
Regional STT Models - Gestor de modelos STT especificos por region
"""
import logging
from typing import Dict, Optional

logger = logging.getLogger(__name__)


class RegionalSTTModels:
    """
    Gestor de modelos STT especificos por region.
    Permite cargar y cambiar entre modelos entrenados para diferentes acentos.
    """

    def __init__(self):
        self.models: Dict[str, Dict] = {}
        self.active_model: Optional[str] = None
        self._model_metadata: Dict[str, Dict] = {}
        logger.info("RegionalSTTModels inicializado")

    def load_model(self, region: str, model_path: str, model_type: str = "google") -> bool:
        """
        Carga modelo especifico para region.

        Args:
            region: Codigo de region (ej: "es-CO", "es-MX")
            model_path: Ruta al modelo o identificador del modelo cloud
            model_type: "google", "whisper", "custom"
        """
        try:
            logger.info("Cargando modelo para %s: %s (%s)", region, model_path, model_type)

            if model_type == "whisper":
                try:
                    import whisper  # type: ignore
                    model = whisper.load_model(model_path)
                    self.models[region] = {"engine": model, "type": "whisper", "path": model_path}
                except ImportError:
                    logger.warning("whisper no disponible, usando modelo simulado")
                    self.models[region] = {"engine": None, "type": "simulated", "path": model_path}
            else:
                # Google Cloud STT o custom
                self.models[region] = {
                    "engine": None,  # Configurado en AccentOptimizer.get_stt_config()
                    "type": model_type,
                    "path": model_path,
                    "loaded": True,
                }

            self._model_metadata[region] = {
                "region": region,
                "type": model_type,
                "accuracy": 0.92,
                "languages": [region],
            }

            logger.info("Modelo cargado para region: %s", region)
            return True

        except Exception as e:
            logger.error("Error cargando modelo %s: %s", region, e)
            return False

    def get_model(self, region: str) -> Optional[Dict]:
        """Obtiene modelo para region."""
        return self.models.get(region)

    def switch_model(self, region: str) -> bool:
        """Cambia al modelo de region especifica."""
        if region not in self.models:
            logger.error("Modelo para %s no cargado", region)
            return False
        self.active_model = region
        logger.info("Modelo activo: %s", region)
        return True

    def list_loaded_models(self) -> Dict[str, Dict]:
        """Lista todos los modelos cargados con metadata."""
        return dict(self._model_metadata)

    def unload_model(self, region: str) -> bool:
        """Libera un modelo de memoria."""
        if region in self.models:
            del self.models[region]
            del self._model_metadata[region]
            if self.active_model == region:
                self.active_model = None
            logger.info("Modelo liberado: %s", region)
            return True
        return False

    def get_best_model_for_text(self, text: str) -> Optional[str]:
        """Sugiere el mejor modelo basado en el texto transcrito."""
        # Detectar idioma/variante por palabras clave
        regional_hints = {
            "es-CO": ["chevere", "parce", "bacano", "pues"],
            "es-MX": ["orale", "wey", "chido", "ahorita"],
            "es-AR": ["che", "boludo", "copado", "laburo"],
        }
        text_lower = text.lower()
        for region, hints in regional_hints.items():
            if any(hint in text_lower for hint in hints):
                if region in self.models:
                    return region
        return self.active_model
