import logging
import re
from typing import Dict, List, Optional


class EntityExtractor:
    """
    Extractor de entidades específicas del dominio de atención al cliente.

    Complementa al IntentClassifier para extraer datos estructurados
    del texto libre del usuario.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    def extract_all(self, text: str) -> Dict[str, Optional[str]]:
        """
        Extrae todas las entidades posibles del texto.

        Args:
            text: Texto libre del usuario.

        Returns:
            Dict con todas las entidades encontradas (sin valores None).
        """
        entities = {
            "ticket_id": self.extract_ticket_id(text),
            "order_id": self.extract_order_id(text),
            "phone": self.extract_phone(text),
            "email": self.extract_email(text),
            "date": self.extract_date(text),
            "amount_charged": self.extract_amount(text, context="cobrado|facturado|cobraron"),
            "amount_expected": self.extract_amount(text, context="debería|esperado|correcto"),
            "product_name": self.extract_product_name(text),
            "problem_type": self.classify_problem_type(text),
        }
        return {k: v for k, v in entities.items() if v is not None}

    def extract_ticket_id(self, text: str) -> Optional[str]:
        """Extrae ticket en formato TKT-YYYY-NNNNNN."""
        match = re.search(r"TKT-\d{4}-\d{6}", text.upper())
        return match.group() if match else None

    def extract_order_id(self, text: str) -> Optional[str]:
        """Extrae número de pedido (6-10 dígitos)."""
        match = re.search(r"(?:pedido|orden|número|no\.?)\s*#?\s*(\d{6,10})", text.lower())
        if match:
            return match.group(1)
        # Fallback: cualquier secuencia de 6-10 dígitos
        match = re.search(r"#(\d{6,10})", text)
        return match.group(1) if match else None

    def extract_phone(self, text: str) -> Optional[str]:
        """Extrae número de teléfono colombiano."""
        # Celular colombiano: 3XXXXXXXXX
        match = re.search(r"\b(3\d{9})\b", text)
        if match:
            return match.group(1)
        # Fijo Bogotá: 6XXXXXXX
        match = re.search(r"\b(6\d{7})\b", text)
        return match.group(1) if match else None

    def extract_email(self, text: str) -> Optional[str]:
        """Extrae dirección de correo electrónico."""
        match = re.search(r"[\w\.-]+@[\w\.-]+\.\w{2,}", text)
        return match.group() if match else None

    def extract_date(self, text: str) -> Optional[str]:
        """Extrae fecha en diferentes formatos."""
        patterns = [
            r"\d{1,2}/\d{1,2}/\d{4}",    # DD/MM/YYYY
            r"\d{1,2}-\d{1,2}-\d{4}",    # DD-MM-YYYY
            r"\d{4}-\d{2}-\d{2}",         # YYYY-MM-DD
            r"\d{1,2}\s+de\s+\w+\s+de\s+\d{4}",  # 15 de marzo de 2026
        ]
        for pattern in patterns:
            match = re.search(pattern, text)
            if match:
                return match.group()
        return None

    def extract_amount(self, text: str, context: Optional[str] = None) -> Optional[str]:
        """
        Extrae monto monetario, opcionalmente buscando cerca de palabras de contexto.

        Args:
            text: Texto a analizar.
            context: Regex de palabras de contexto para refinar la búsqueda.

        Returns:
            Monto como string (ej: "150000") o None.
        """
        # Buscar montos con $ o terminados en "pesos"
        pattern = r"\$?\s*(\d{1,3}(?:[.,]\d{3})*(?:\.\d{2})?)\s*(?:pesos|cop)?"

        if context:
            ctx_match = re.search(context, text.lower())
            if ctx_match:
                # Buscar monto en los 50 caracteres alrededor del contexto
                start = max(0, ctx_match.start() - 10)
                end = min(len(text), ctx_match.end() + 50)
                snippet = text[start:end]
                match = re.search(pattern, snippet)
                if match:
                    return match.group(1).replace(",", "").replace(".", "")

        match = re.search(pattern, text)
        if match:
            return match.group(1).replace(",", "").replace(".", "")
        return None

    def extract_product_name(self, text: str) -> Optional[str]:
        """Extrae nombre de producto mencionado (heurística básica)."""
        product_patterns = [
            r"(?:producto|servicio|plan|paquete)\s+([A-Za-záéíóúÁÉÍÓÚ\s]+?)(?:\s+que|\s+el|\s+la|$)",
        ]
        for pattern in product_patterns:
            match = re.search(pattern, text.lower())
            if match:
                return match.group(1).strip().title()
        return None

    def classify_problem_type(self, text: str) -> Optional[str]:
        """Clasifica el tipo de problema mencionado."""
        problem_map = {
            "facturacion": ["factura", "cobro", "cargo", "cobrado", "pago", "débito"],
            "tecnico": ["no funciona", "falla", "error", "caído", "lento", "bug"],
            "envio": ["envío", "entrega", "paquete", "llegó", "demora", "courier"],
            "atencion": ["atención", "trato", "servicio", "grosero", "mal atendido"],
        }
        text_lower = text.lower()
        for problem_type, keywords in problem_map.items():
            if any(kw in text_lower for kw in keywords):
                return problem_type
        return None

    def build_ticket_context(self, entities: Dict, text: str) -> Dict:
        """
        Construye un contexto estructurado para crear un ticket a partir de entidades.

        Args:
            entities: Entidades extraídas del texto.
            text: Texto original del usuario.

        Returns:
            Dict con datos estructurados para el ticket.
        """
        context = {
            "description": text,
            "category": entities.get("problem_type", "otro"),
            "priority": "ALTA" if entities.get("problem_type") == "facturacion" else "MEDIA",
        }

        if entities.get("amount_charged"):
            context["amount_charged"] = entities["amount_charged"]
        if entities.get("amount_expected"):
            context["amount_expected"] = entities["amount_expected"]
        if entities.get("order_id"):
            context["reference"] = entities["order_id"]

        return context
