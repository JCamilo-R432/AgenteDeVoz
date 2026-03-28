import logging
from typing import Dict, Optional

from config.settings import settings


class TwilioVoiceIntegration:
    """
    Integración con Twilio Voice para llamadas telefónicas.

    Maneja webhooks entrantes, control de llamadas y transferencias.
    """

    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.account_sid = settings.TWILIO_ACCOUNT_SID
        self.auth_token = settings.TWILIO_AUTH_TOKEN
        self.phone_number = settings.TWILIO_PHONE_NUMBER
        self._client = None

    def _get_client(self):
        """Obtiene el cliente Twilio de forma lazy."""
        if self._client is None:
            try:
                from twilio.rest import Client
                self._client = Client(self.account_sid, self.auth_token)
            except ImportError:
                self.logger.error("twilio no instalado. Ejecuta: pip install twilio")
                raise
        return self._client

    def validate_webhook(self, url: str, params: Dict, signature: str) -> bool:
        """
        Valida la firma HMAC de un webhook entrante de Twilio.

        Args:
            url: URL completa del webhook.
            params: Parámetros POST del webhook.
            signature: Header X-Twilio-Signature.

        Returns:
            True si la firma es válida.
        """
        try:
            from twilio.request_validator import RequestValidator

            validator = RequestValidator(self.auth_token)
            is_valid = validator.validate(url, params, signature)

            if not is_valid:
                self.logger.warning(f"Firma Twilio inválida para URL: {url}")

            return is_valid

        except ImportError:
            self.logger.error("twilio no instalado.")
            return False
        except Exception as e:
            self.logger.error(f"Error validando webhook: {e}")
            return False

    def generate_initial_twiml(self, webhook_url: str, session_id: str) -> str:
        """
        Genera el TwiML para iniciar el stream de audio bidireccional.

        Args:
            webhook_url: URL del WebSocket del sistema.
            session_id: ID de la sesión de conversación.

        Returns:
            String XML con las instrucciones TwiML.
        """
        return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Connect>
        <Stream url="{webhook_url}/api/v1/voice/stream">
            <Parameter name="session_id" value="{session_id}"/>
        </Stream>
    </Connect>
</Response>"""

    def transfer_call(self, call_sid: str, transfer_to: str) -> bool:
        """
        Transfiere una llamada activa a otro número.

        Args:
            call_sid: SID de la llamada en Twilio.
            transfer_to: Número de destino de la transferencia.

        Returns:
            True si la transferencia se inició correctamente.
        """
        try:
            client = self._get_client()
            client.calls(call_sid).update(
                twiml=f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
    <Dial timeout="30" action="/api/v1/voice/transfer-complete">
        <Number>{transfer_to}</Number>
    </Dial>
</Response>"""
            )
            self.logger.info(f"Transferencia iniciada: {call_sid} → {transfer_to}")
            return True

        except Exception as e:
            self.logger.error(f"Error transfiriendo llamada {call_sid}: {e}")
            return False

    def end_call(self, call_sid: str) -> bool:
        """
        Finaliza una llamada activa.

        Args:
            call_sid: SID de la llamada en Twilio.

        Returns:
            True si la llamada fue finalizada correctamente.
        """
        try:
            client = self._get_client()
            client.calls(call_sid).update(status="completed")
            self.logger.info(f"Llamada {call_sid} finalizada.")
            return True

        except Exception as e:
            self.logger.error(f"Error finalizando llamada {call_sid}: {e}")
            return False

    def get_call_info(self, call_sid: str) -> Optional[Dict]:
        """
        Obtiene información de una llamada activa.

        Args:
            call_sid: SID de la llamada.

        Returns:
            Dict con información de la llamada o None.
        """
        try:
            client = self._get_client()
            call = client.calls(call_sid).fetch()
            return {
                "sid": call.sid,
                "status": call.status,
                "from": call.from_formatted,
                "to": call.to_formatted,
                "duration": call.duration,
                "start_time": str(call.start_time),
            }
        except Exception as e:
            self.logger.error(f"Error obteniendo info de llamada {call_sid}: {e}")
            return None
