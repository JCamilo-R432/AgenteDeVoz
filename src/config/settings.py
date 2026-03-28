import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    """Configuración centralizada del Agente de Voz."""

    # Voice Configuration
    STT_ENGINE: str = os.getenv("STT_ENGINE", "google")
    TTS_ENGINE: str = os.getenv("TTS_ENGINE", "pyttsx3")
    LANGUAGE: str = os.getenv("LANGUAGE", "es-CO")

    # API Keys
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")
    ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
    GOOGLE_APPLICATION_CREDENTIALS: str = os.getenv("GOOGLE_APPLICATION_CREDENTIALS", "")

    # Twilio
    TWILIO_ACCOUNT_SID: str = os.getenv("TWILIO_ACCOUNT_SID", "")
    TWILIO_AUTH_TOKEN: str = os.getenv("TWILIO_AUTH_TOKEN", "")
    TWILIO_PHONE_NUMBER: str = os.getenv("TWILIO_PHONE_NUMBER", "")
    TWILIO_WEBHOOK_URL: str = os.getenv("TWILIO_WEBHOOK_URL", "")

    # Database
    DATABASE_URL: str = os.getenv(
        "DATABASE_URL", "postgresql://postgres:postgres@localhost:5432/agentevoz"
    )

    # Redis
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379/0")
    REDIS_SESSION_TTL: int = int(os.getenv("REDIS_SESSION_TTL", "1800"))

    # Business Rules
    MAX_CALL_DURATION: int = int(os.getenv("MAX_CALL_DURATION", "1800"))
    ESCALATION_NUMBER: str = os.getenv("ESCALATION_NUMBER", "+573001234567")
    MAX_FALLBACK_ATTEMPTS: int = int(os.getenv("MAX_FALLBACK_ATTEMPTS", "3"))
    SILENCE_TIMEOUT_SECONDS: int = int(os.getenv("SILENCE_TIMEOUT_SECONDS", "5"))

    # Security
    JWT_SECRET_KEY: str = os.getenv("JWT_SECRET_KEY", "dev-secret-change-in-prod")
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = int(os.getenv("ACCESS_TOKEN_EXPIRE_MINUTES", "15"))

    # Logging
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    RECORD_CALLS: bool = os.getenv("RECORD_CALLS", "false").lower() == "true"

    # ElevenLabs TTS
    ELEVENLABS_API_KEY: str = os.getenv("ELEVENLABS_API_KEY", "")
    ELEVENLABS_VOICE_ID: str = os.getenv("ELEVENLABS_VOICE_ID", "XB0fDUnXU5powFXDhCwa")  # Charlotte multilingual

    # CRM
    CRM_BASE_URL: str = os.getenv("CRM_BASE_URL", "")
    CRM_API_KEY: str = os.getenv("CRM_API_KEY", "")

    # Email (SendGrid)
    SENDGRID_API_KEY: str = os.getenv("SENDGRID_API_KEY", "")
    EMAIL_FROM: str = os.getenv("EMAIL_FROM", "noreply@agentevoz.com")
    EMAIL_FROM_NAME: str = os.getenv("EMAIL_FROM_NAME", "Agente de Voz - Soporte")

    def validate(self) -> bool:
        """Valida que las variables críticas estén configuradas."""
        warnings = []

        if not self.OPENAI_API_KEY and not self.ANTHROPIC_API_KEY:
            warnings.append("OPENAI_API_KEY o ANTHROPIC_API_KEY (se necesita al menos una)")

        if "localhost" in self.DATABASE_URL and os.getenv("ENV") == "production":
            warnings.append("DATABASE_URL apunta a localhost en producción")

        if self.JWT_SECRET_KEY == "dev-secret-change-in-prod":
            warnings.append("JWT_SECRET_KEY usa el valor por defecto (inseguro en producción)")

        for msg in warnings:
            print(f"WARNING: {msg}")

        return True


settings = Settings()
