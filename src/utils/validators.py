import re
from typing import Optional, Tuple


class Validators:
    """Validadores de datos de entrada del agente de voz."""

    @staticmethod
    def validate_phone(phone: str) -> bool:
        """Valida formato de teléfono colombiano (10 dígitos)."""
        clean = phone.replace(" ", "").replace("-", "").replace("+57", "")
        return bool(re.match(r"^\d{10}$", clean))

    @staticmethod
    def validate_email(email: str) -> bool:
        """Valida formato de email."""
        return bool(re.match(r"^[\w\.-]+@[\w\.-]+\.\w{2,}$", email))

    @staticmethod
    def validate_ticket_id(ticket_id: str) -> bool:
        """Valida formato de ID de ticket (TKT-YYYY-NNNNNN o 6-10 chars alfanuméricos)."""
        clean = ticket_id.strip().upper()
        # Aceptar formato TKT-2026-000001 o legacy ABCD1234
        return bool(
            re.match(r"^TKT-\d{4}-\d{6}$", clean)
            or re.match(r"^[A-Z0-9]{6,10}$", clean)
        )

    @staticmethod
    def validate_date(date_str: str) -> Tuple[bool, Optional[str]]:
        """Valida formato de fecha (DD/MM/YYYY o YYYY-MM-DD)."""
        patterns = [
            r"^\d{1,2}[/-]\d{1,2}[/-]\d{2,4}$",
            r"^\d{4}[/-]\d{1,2}[/-]\d{1,2}$",
        ]
        for pattern in patterns:
            if re.match(pattern, date_str.strip()):
                return True, date_str.strip()
        return False, None

    @staticmethod
    def sanitize_input(text: str, max_length: int = 1000) -> str:
        """Elimina caracteres peligrosos y limita la longitud del input."""
        if not text:
            return ""
        # Eliminar caracteres que podrían causar inyección
        text = re.sub(r"[<>\"';\\]", "", text)
        # Normalizar espacios
        text = re.sub(r"\s+", " ", text).strip()
        return text[:max_length]

    @staticmethod
    def validate_intent(intent: str) -> bool:
        """Valida que la intención sea una de las permitidas."""
        valid_intents = {
            "saludo", "faq", "crear_ticket", "consultar_estado",
            "queja", "escalar_humano", "despedida", "sin_intencion",
        }
        return intent in valid_intents
