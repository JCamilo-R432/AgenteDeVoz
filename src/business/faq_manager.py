import logging
from typing import Dict, List, Optional


class FAQManager:
    """
    Gestor de preguntas frecuentes.

    En MVP usa una base de conocimiento en memoria. En producción
    este contenido vendría de una base de datos o CMS.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.faqs = self._load_faqs()

    def _load_faqs(self) -> List[Dict]:
        """Carga las FAQs con sus palabras clave y respuestas."""
        return [
            {
                "id": "saludo",
                "keywords": ["hola", "buenos", "buenas", "hey", "buen día"],
                "response": (
                    "¡Hola! Bienvenido al servicio de atención al cliente. "
                    "¿En qué puedo ayudarte hoy? Puedo responder preguntas frecuentes, "
                    "crear un ticket de soporte, consultar el estado de un pedido, "
                    "o conectarte con un agente humano."
                ),
            },
            {
                "id": "horario",
                "keywords": ["horario", "hora", "abierto", "cerrado", "atienden", "disponible"],
                "response": (
                    "Nuestro horario de atención presencial es de lunes a viernes "
                    "de 8:00 AM a 6:00 PM, y sábados de 9:00 AM a 1:00 PM. "
                    "Este servicio de voz está disponible las 24 horas, los 7 días de la semana."
                ),
            },
            {
                "id": "ubicacion",
                "keywords": ["ubicación", "dirección", "dónde", "oficina", "sede"],
                "response": (
                    "Estamos ubicados en la Calle 123 número 45-67, Bogotá, Colombia. "
                    "También puedes atenderte completamente en línea a través de este servicio. "
                    "¿Necesitas indicaciones para llegar?"
                ),
            },
            {
                "id": "contacto",
                "keywords": ["contacto", "teléfono", "email", "correo", "comunicar", "número"],
                "response": (
                    "Puedes contactarnos de las siguientes formas: "
                    "Por teléfono al 601 555 1234, "
                    "por email a soporte@empresa.com, "
                    "o por WhatsApp al 300 123 4567. "
                    "También puedes crear un ticket y te contactaremos pronto."
                ),
            },
            {
                "id": "tiempo_reparacion",
                "keywords": ["demora", "tiempo", "cuánto tarda", "reparación", "días"],
                "response": (
                    "El tiempo de reparación depende del tipo de servicio. "
                    "Para servicios estándar, el tiempo estimado es de 3 a 5 días hábiles. "
                    "Para el servicio exprés, contamos con atención en 24 horas con un costo adicional. "
                    "¿Te gustaría crear un ticket para iniciar el proceso?"
                ),
            },
            {
                "id": "garantia",
                "keywords": ["garantía", "garantia", "cobertura", "reparación gratis"],
                "response": (
                    "Nuestros productos tienen garantía de 12 meses contra defectos de fabricación. "
                    "La garantía cubre partes y mano de obra en casos de falla no causada por el usuario. "
                    "Para aplicar la garantía, necesitas presentar la factura de compra. "
                    "¿Deseas iniciar un proceso de garantía?"
                ),
            },
            {
                "id": "pagos",
                "keywords": ["pago", "pagar", "factura", "cobro", "tarjeta", "efectivo", "PSE"],
                "response": (
                    "Aceptamos los siguientes métodos de pago: "
                    "tarjeta débito y crédito (Visa, Mastercard), "
                    "pago PSE, transferencia bancaria, y efectivo en nuestras oficinas. "
                    "Para dudas sobre un cobro específico en tu factura, puedo crear un ticket."
                ),
            },
        ]

    def answer(self, query: str) -> str:
        """
        Busca y retorna la respuesta más relevante para la consulta.

        Args:
            query: Texto de la pregunta del usuario.

        Returns:
            Respuesta de la FAQ o mensaje de fallback.
        """
        query_lower = query.lower()
        best_match: Optional[Dict] = None
        best_score = 0

        for faq in self.faqs:
            score = sum(1 for kw in faq["keywords"] if kw in query_lower)
            if score > best_score:
                best_score = score
                best_match = faq

        if best_match and best_score > 0:
            self.logger.info(f"FAQ encontrada: {best_match['id']} (score: {best_score})")
            return best_match["response"]

        self.logger.info(f"Sin FAQ para: '{query[:60]}'")
        return (
            "No encontré información específica sobre eso en nuestra base de conocimiento. "
            "¿Te gustaría que cree un ticket para que un especialista te contacte con una respuesta?"
        )

    def add_faq(self, faq_id: str, response: str, keywords: List[str]) -> bool:
        """Agrega una nueva FAQ en tiempo de ejecución."""
        try:
            # Verificar que no exista ya
            existing_ids = [f["id"] for f in self.faqs]
            if faq_id in existing_ids:
                self.logger.warning(f"FAQ '{faq_id}' ya existe. Actualizando.")
                self.faqs = [f for f in self.faqs if f["id"] != faq_id]

            self.faqs.append({
                "id": faq_id,
                "keywords": keywords,
                "response": response,
            })
            self.logger.info(f"FAQ '{faq_id}' agregada.")
            return True
        except Exception as e:
            self.logger.error(f"Error agregando FAQ '{faq_id}': {e}")
            return False

    def list_faqs(self) -> List[str]:
        """Retorna la lista de IDs de FAQs disponibles."""
        return [f["id"] for f in self.faqs]
