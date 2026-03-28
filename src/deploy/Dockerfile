# ============================================================
# Agente de Voz - Dockerfile
# Python 3.11 slim con todas las dependencias del sistema
# ============================================================

FROM python:3.11-slim AS base

LABEL maintainer="agentevoz@empresa.com"
LABEL description="Agente de Voz Customer Service"
LABEL version="1.0.0"

# Variables de entorno de Python
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app/src \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    portaudio19-dev \
    libportaudio2 \
    libportaudiocpp0 \
    ffmpeg \
    libsndfile1 \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Crear usuario no-root
RUN groupadd -r agentevoz && useradd -r -g agentevoz agentevoz

# Directorio de trabajo
WORKDIR /app

# ── Dependencias Python ───────────────────────────────────────────────────────

FROM base AS dependencies

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ── Imagen final ──────────────────────────────────────────────────────────────

FROM dependencies AS final

# Copiar código fuente
COPY src/ ./src/
COPY config/ ./config/

# Directorios de datos
RUN mkdir -p /app/logs /app/data /app/temp && \
    chown -R agentevoz:agentevoz /app

# Cambiar a usuario no-root
USER agentevoz

# Puerto de la aplicación
EXPOSE 8000

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD curl -f http://localhost:8000/api/v1/ping || exit 1

# Comando de inicio (usar gunicorn en producción, uvicorn en dev)
CMD ["uvicorn", "src.server:app", "--host", "0.0.0.0", "--port", "8000", \
     "--workers", "2", "--log-level", "info"]
