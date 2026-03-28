"""
CustomerVerifier — verifica identidad del cliente por múltiples métodos.
Usado por el agente de voz antes de revelar info de pedidos.
"""
import logging
from datetime import datetime, timedelta, timezone
from typing import Optional

logger = logging.getLogger(__name__)


class CustomerVerifier:
    """
    Verifica identidad del cliente mediante:
    - Teléfono + número de orden
    - Email + nombre (fuzzy)
    - Pregunta de seguridad (últimos 4 dígitos del total)
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)

    async def verify_by_phone_and_order(self, phone: str, order_number: str) -> bool:
        """Verifica que el teléfono coincida con el cliente del pedido."""
        try:
            from database import AsyncSessionLocal
            from services.order_service import OrderService
            import re

            clean_phone = re.sub(r"[^\d]", "", phone)

            async with AsyncSessionLocal() as session:
                service = OrderService(session)
                order = await service.get_by_order_number(order_number)
                if not order or not order.customer:
                    return False

                customer_phone = re.sub(r"[^\d]", "", order.customer.phone or "")
                # Comparar con y sin código de país
                match = (
                    clean_phone == customer_phone
                    or clean_phone == customer_phone[-10:]
                    or clean_phone[-10:] == customer_phone[-10:]
                )
                if match:
                    self.logger.info(f"Verificación por teléfono+orden exitosa: {order_number}")
                return match
        except Exception as e:
            self.logger.error(f"Error en verify_by_phone_and_order: {e}")
            return False

    async def verify_by_email_and_name(self, email: str, full_name: str) -> bool:
        """Verifica email exacto + nombre con fuzzy matching (>=80% similitud)."""
        try:
            from database import AsyncSessionLocal
            from sqlalchemy import select
            from models.customer import Customer

            async with AsyncSessionLocal() as session:
                result = await session.execute(
                    select(Customer).where(Customer.email == email.lower().strip())
                )
                customer = result.scalar_one_or_none()
                if not customer:
                    return False

                # Fuzzy name comparison
                score = self._name_similarity(full_name, customer.full_name)
                self.logger.info(f"Name similarity score: {score:.2f} for '{full_name}' vs '{customer.full_name}'")
                return score >= 0.75
        except Exception as e:
            self.logger.error(f"Error en verify_by_email_and_name: {e}")
            return False

    async def verify_security_question(self, phone: str, answer: str) -> bool:
        """
        Pregunta de seguridad: últimos 4 dígitos del total del pedido más reciente,
        o últimas 4 cifras del número de orden.
        """
        try:
            from database import AsyncSessionLocal
            from services.order_service import OrderService

            async with AsyncSessionLocal() as session:
                service = OrderService(session)
                orders = await service.get_by_customer_phone(phone)
                if not orders:
                    return False

                latest = orders[0]
                # Comparar con últimos 4 dígitos del total (sin decimales)
                total_digits = str(int(latest.total_amount))[-4:]
                # O con últimos 6 del número de orden
                order_digits = latest.order_number[-6:]

                clean_answer = answer.strip().replace(".", "").replace(",", "")
                return clean_answer in (total_digits, order_digits, latest.order_number)
        except Exception as e:
            self.logger.error(f"Error en verify_security_question: {e}")
            return False

    def generate_session_token(self, customer_id: str, phone: str) -> str:
        """JWT de sesión con {customer_id, phone, verified: True, exp: +30min}."""
        from jose import jwt
        from config.settings import settings
        import uuid

        payload = {
            "sub": customer_id,
            "phone": phone,
            "verified": True,
            "type": "customer_session",
            "jti": str(uuid.uuid4()),
            "exp": datetime.now(timezone.utc) + timedelta(minutes=30),
        }
        return jwt.encode(payload, settings.JWT_SECRET_KEY, algorithm=settings.JWT_ALGORITHM)

    def validate_session_token(self, token: str) -> Optional[dict]:
        """Decodifica y valida token de sesión. Retorna payload o None."""
        try:
            from jose import jwt, JWTError
            from config.settings import settings

            payload = jwt.decode(token, settings.JWT_SECRET_KEY, algorithms=[settings.JWT_ALGORITHM])
            if payload.get("type") != "customer_session":
                return None
            if not payload.get("verified"):
                return None
            return payload
        except Exception:
            return None

    def _name_similarity(self, name1: str, name2: str) -> float:
        """Calcula similitud entre nombres (0.0 - 1.0) usando SequenceMatcher."""
        from difflib import SequenceMatcher

        n1 = name1.lower().strip()
        n2 = name2.lower().strip()
        return SequenceMatcher(None, n1, n2).ratio()

    def mask_email(self, email: str) -> str:
        """Enmascara email: j***@gmail.com."""
        if not email or "@" not in email:
            return "****@****.com"
        local, domain = email.split("@", 1)
        masked_local = local[0] + "***" if len(local) > 1 else "***"
        return f"{masked_local}@{domain}"
