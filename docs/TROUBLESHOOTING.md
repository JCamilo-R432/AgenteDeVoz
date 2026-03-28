# Solucion de Problemas - AgenteDeVoz

## Indice

1. [Problemas de inicio](#1-problemas-de-inicio)
2. [STT no transcribe](#2-stt-no-transcribe)
3. [TTS no genera audio](#3-tts-no-genera-audio)
4. [Twilio no conecta](#4-twilio-no-conecta)
5. [Base de datos](#5-base-de-datos)
6. [Redis](#6-redis)
7. [Dashboard no carga](#7-dashboard-no-carga)
8. [Tests fallando](#8-tests-fallando)

---

## 1. Problemas de inicio

### Error: "ModuleNotFoundError: No module named 'X'"

```bash
# Asegurar que el entorno virtual esta activo
source venv/bin/activate

# Reinstalar dependencias
pip install -r requirements.txt

# Verificar PYTHONPATH
export PYTHONPATH=/opt/agentevoz/src
python -c "import fastapi; print('OK')"
```

### Error: "Address already in use"

```bash
# Ver quien usa el puerto 8000
lsof -i :8000

# Matar el proceso
kill -9 $(lsof -t -i:8000)
```

### Error al importar en Windows

En Windows, usar rutas con separadores correctos y variables de entorno:

```powershell
$env:PYTHONPATH = "C:\Users\jrive\Documents\AgenteDeVoz\src"
cd C:\Users\jrive\Documents\AgenteDeVoz
python src\main.py
```

---

## 2. STT no transcribe

### Sintoma: STTEngine retorna None siempre

**Causa 1:** Credenciales de Google Cloud no configuradas

```bash
# Verificar variable
echo $GOOGLE_APPLICATION_CREDENTIALS
# Verificar que el archivo existe
ls -la $GOOGLE_APPLICATION_CREDENTIALS

# Test de autenticacion
python -c "
from google.cloud import speech
client = speech.SpeechClient()
print('Google Cloud STT: OK')
"
```

**Causa 2:** PyAudio no instalado (error silencioso)

```bash
# En Linux
sudo apt install portaudio19-dev
pip install pyaudio

# En Windows (requiere Visual C++)
pip install pyaudio
# Si falla: descargar wheel desde https://www.lfd.uci.edu/~gohlke/pythonlibs/#pyaudio
```

**Solucion temporal:** Forzar uso de motor de texto (para pruebas):

```python
# En src/config/settings.py o .env
STT_ENGINE=pyttsx3  # (desactivara STT real, solo para pruebas)
```

---

## 3. TTS no genera audio

### Sintoma: speak() retorna False

**Verificar pyttsx3 (fallback):**

```python
import pyttsx3
engine = pyttsx3.init()
engine.say("Prueba")
engine.runAndWait()
```

**En Windows:** pyttsx3 requiere SAPI. Si falla:

```bash
pip uninstall pyttsx3
pip install pyttsx3==2.90
```

**Google Cloud TTS no disponible:**

```bash
# Verificar credenciales
python -c "
from google.cloud import texttospeech
client = texttospeech.TextToSpeechClient()
print('Google TTS: OK')
"
```

---

## 4. Twilio no conecta

### Sintoma: Las llamadas no llegan al webhook

1. **Verificar que la URL es HTTPS y accesible desde internet**

```bash
curl -X POST https://tu-dominio.com/api/v1/webhooks/twilio/voice \
  -d "From=+573001234567&CallSid=CAtest"
```

Debe retornar XML (TwiML), no un error.

2. **Para desarrollo local usar ngrok:**

```bash
# Instalar ngrok: https://ngrok.com
ngrok http 8000

# Usar la URL HTTPS de ngrok en Twilio Console
# Ejemplo: https://abc123.ngrok.io/api/v1/webhooks/twilio/voice
```

3. **Verificar firma de Twilio:**

Si el webhook retorna 403, revisar `TWILIO_AUTH_TOKEN` en .env.

### Sintoma: Audio cortado o con ruido

- Verificar que el audio TTS esta en formato correcto (MULAW 8kHz)
- Verificar latencia de red: el WebSocket de Twilio tiene timeout de 5s
- Reducir la longitud de las respuestas del agente

---

## 5. Base de datos

### Error: "could not connect to server"

```bash
# Verificar que PostgreSQL esta corriendo
pg_isready -h localhost -p 5432

# En Docker
docker ps | grep postgres
docker logs agentevoz_postgres

# Conectar manualmente
psql -h localhost -U agentevoz -d agentevoz
```

### Error: "permission denied for table X"

```bash
# Conceder permisos manualmente
psql -U postgres -d agentevoz -c "
GRANT ALL PRIVILEGES ON ALL TABLES IN SCHEMA public TO agentevoz;
GRANT ALL PRIVILEGES ON ALL SEQUENCES IN SCHEMA public TO agentevoz;
"
```

### La tabla no existe

```bash
# Re-ejecutar schema
bash scripts/setup_database.sh --env prod
```

---

## 6. Redis

### Error: "Connection refused"

```bash
# Verificar que Redis esta corriendo
redis-cli ping

# En Docker
docker ps | grep redis
docker logs agentevoz_redis

# Con password
redis-cli -a "mi_password" ping
```

### El sistema usa memoria en lugar de Redis

Esto es el comportamiento esperado de fallback. Ver logs:

```
[WARNING] Redis no disponible (...). Usando cache en memoria.
```

Para forzar Redis:

```bash
# Verificar credenciales en .env
grep REDIS config/production.env
```

---

## 7. Dashboard no carga

### Error 404 en /dashboard

```bash
# Verificar que los templates existen
ls src/dashboard/templates/

# Ejecutar el servidor y verificar logs
uvicorn src.server:app --reload
```

### CSS/JS no carga (404 en /dashboard/static/)

```bash
# Verificar directorio static
ls src/dashboard/static/css/
ls src/dashboard/static/js/

# En Docker, verificar que el volume esta montado correctamente
docker exec agentevoz_app ls /app/src/dashboard/static/
```

### WebSocket del dashboard no conecta

El dashboard usa WS para actualizaciones en tiempo real. Si falla:

1. Verificar que Nginx permite upgrade de conexion (ver `nginx.conf`)
2. Revisar la consola del navegador (F12) para errores de WS
3. El fallback es polling manual con el boton "Actualizar"

---

## 8. Tests fallando

### Correr tests

```bash
cd C:\Users\jrive\Documents\AgenteDeVoz
set PYTHONPATH=src
pytest src/tests/ -v
```

### Error: "No module named 'speech.stt_engine'"

```bash
# Asegurar PYTHONPATH correcto
export PYTHONPATH=$(pwd)/src
pytest src/tests/ -v
```

### Test de STT falla por PyAudio

PyAudio requiere dispositivos de audio. En CI/CD sin audio:

```bash
# Los tests de STT/TTS tienen fallback (retornan None gracefully)
# Si el test falla, verificar que el mensaje de error es el esperado
pytest src/tests/test_stt.py -v -s
```

### Obtener reporte de cobertura

```bash
pytest src/tests/ --cov=src --cov-report=html
# Ver htmlcov/index.html
```

---

## Contacto y Soporte

- **Issues:** https://github.com/tuempresa/agentevoz/issues
- **Logs de produccion:** `docker logs agentevoz_app -f`
- **Health check:** `bash scripts/health_check.sh`
