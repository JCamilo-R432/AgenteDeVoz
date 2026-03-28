from typing import Dict, List, Any
"""
OTP Manager — generación, verificación y rate limiting de códigos OTP.
In-memory con interfaz compatible con Redis.
"""
import secrets
import logging
from datetime import datetime, timedelta, timezone
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger(__name__)


@dataclass
class OTPRecord:
    code: str
    phone: str
    expires_at: datetime
    attempts: int = 0
    verified: bool = False


class OTPManager:
    """
    Gestor de OTP en memoria.
    Rate limiting: máx 3 envíos por teléfono cada 10 minutos.
    Máx 5 intentos de verificación por OTP.
    Expiración: 10 minutos.
    """
    MAX_ATTEMPTS = 5
    EXPIRY_MINUTES = 10
    MAX_SENDS_PER_WINDOW = 3
    WINDOW_MINUTES = 10

    def __init__(self):
        self._store: dict[str, OTPRecord] = {}        # phone → OTPRecord
        self._send_log: dict[str, List[float]] = {}   # phone → [timestamps]

    def generate_otp(self, phone: str) -> Optional[str]:
        """Genera OTP de 6 dígitos. Retorna None si está rate-limitado."""
        import time

        if self.is_rate_limited(phone):
            logger.warning(f"OTP rate-limit alcanzado para {phone}")
            return None

        # Limpiar OTPs expirados
        self._cleanup()

        code = f"{secrets.randbelow(1000000):06d}"
        now = datetime.now(timezone.utc)
        self._store[phone] = OTPRecord(
            code=code,
            phone=phone,
            expires_at=now + timedelta(minutes=self.EXPIRY_MINUTES),
        )

        # Registrar envío para rate limiting
        self._send_log.setdefault(phone, []).append(time.time())
        logger.info(f"OTP generado para {phone} (expira en {self.EXPIRY_MINUTES}min)")
        return code

    def verify_otp(self, phone: str, code: str) -> bool:
        """Verifica OTP. Incrementa intentos en fallo. True si válido."""
        record = self._store.get(phone)

        if not record:
            logger.info(f"OTP no encontrado para {phone}")
            return False

        now = datetime.now(timezone.utc)
        if now > record.expires_at:
            logger.info(f"OTP expirado para {phone}")
            del self._store[phone]
            return False

        if record.attempts >= self.MAX_ATTEMPTS:
            logger.warning(f"Máximo de intentos OTP para {phone}")
            return False

        if record.code != code:
            record.attempts += 1
            logger.info(f"OTP incorrecto para {phone} (intento {record.attempts}/{self.MAX_ATTEMPTS})")
            return False

        record.verified = True
        logger.info(f"OTP verificado exitosamente para {phone}")
        return True

    def create_session_token(self, phone: str, customer_id: str) -> str:
        """Crea JWT de sesión temporal (30 min) tras verificación OTP."""
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

    def is_rate_limited(self, phone: str) -> bool:
        """True si el teléfono excedió el límite de envíos."""
        import time
        window_start = time.time() - (self.WINDOW_MINUTES * 60)
        sends = [t for t in self._send_log.get(phone, []) if t > window_start]
        self._send_log[phone] = sends
        return len(sends) >= self.MAX_SENDS_PER_WINDOW

    def get_remaining_attempts(self, phone: str) -> int:
        """Intentos de verificación restantes."""
        record = self._store.get(phone)
        if not record:
            return self.MAX_ATTEMPTS
        return max(0, self.MAX_ATTEMPTS - record.attempts)

    def invalidate(self, phone: str) -> None:
        """Invalida el OTP del teléfono."""
        self._store.pop(phone, None)

    def get_retry_after(self, phone: str) -> int:
        """Segundos hasta el próximo envío permitido."""
        import time
        window_start = time.time() - (self.WINDOW_MINUTES * 60)
        sends = sorted([t for t in self._send_log.get(phone, []) if t > window_start])
        if not sends:
            return 0
        oldest_in_window = sends[0]
        return max(0, int(oldest_in_window + self.WINDOW_MINUTES * 60 - time.time()))

    def _cleanup(self) -> None:
        """Elimina OTPs expirados."""
        now = datetime.now(timezone.utc)
        expired = [phone for phone, rec in self._store.items() if now > rec.expires_at]
        for phone in expired:
            del self._store[phone]


# Singleton global
otp_manager = OTPManager()
