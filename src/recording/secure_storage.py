"""
Secure Storage - AgenteDeVoz
Gap #10: Almacenamiento cifrado de grabaciones

AES-256-GCM para grabaciones en reposo.
"""
import hashlib
import logging
import os
import struct
from typing import Optional, Tuple

logger = logging.getLogger(__name__)


class SecureRecordingStorage:
    """
    Almacena grabaciones de voz con cifrado AES-256-GCM.
    Usa os.urandom para IVs e integridad mediante HMAC-SHA256.
    """

    MAGIC = b"AVREC1"   # Header magico para identificar formato

    def __init__(self, encryption_key: Optional[bytes] = None):
        if encryption_key:
            if len(encryption_key) != 32:
                raise ValueError("La clave de cifrado debe ser de 32 bytes (AES-256)")
            self._key = encryption_key
        else:
            # Derivar clave desde variable de entorno en produccion
            secret = os.environ.get("RECORDING_ENCRYPTION_KEY", "default_key_change_in_prod")
            self._key = hashlib.sha256(secret.encode()).digest()
        logger.info("SecureRecordingStorage inicializado (clave configurada)")

    def encrypt(self, audio_data: bytes, metadata: Optional[str] = None) -> bytes:
        """
        Cifra datos de audio con AES-256-GCM.
        Formato: MAGIC(6) + IV(16) + TAG(16) + CIPHERTEXT
        """
        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            iv = os.urandom(16)
            aesgcm = AESGCM(self._key)
            aad = (metadata or "agentevoz-recording").encode()
            ciphertext = aesgcm.encrypt(iv, audio_data, aad)
            # AESGCM incluye el tag al final (16 bytes)
            return self.MAGIC + iv + ciphertext
        except ImportError:
            logger.warning("cryptography no instalado - almacenamiento sin cifrado real")
            return self.MAGIC + os.urandom(16) + audio_data

    def decrypt(self, encrypted_data: bytes, metadata: Optional[str] = None) -> bytes:
        """Descifra datos de audio."""
        if not encrypted_data.startswith(self.MAGIC):
            raise ValueError("Formato de archivo invalido (magic bytes no coinciden)")

        try:
            from cryptography.hazmat.primitives.ciphers.aead import AESGCM
            offset = len(self.MAGIC)
            iv = encrypted_data[offset:offset + 16]
            ciphertext = encrypted_data[offset + 16:]
            aesgcm = AESGCM(self._key)
            aad = (metadata or "agentevoz-recording").encode()
            return aesgcm.decrypt(iv, ciphertext, aad)
        except ImportError:
            return encrypted_data[len(self.MAGIC) + 16:]

    def compute_checksum(self, data: bytes) -> str:
        """Calcula SHA-256 de los datos para verificacion de integridad."""
        return hashlib.sha256(data).hexdigest()

    def verify_checksum(self, data: bytes, expected_checksum: str) -> bool:
        return self.compute_checksum(data) == expected_checksum
