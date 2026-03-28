# Distributed Tracing (Gap #23)

## Descripcion
Trazabilidad end-to-end de la pipeline de voz: STT -> NLP -> LLM -> TTS -> CRM.
Compatible con OpenTelemetry y Jaeger.

## Uso basico
```python
from src.observability.distributed_tracing import DistributedTracing

tracer = DistributedTracing(
    service_name="agentevoz",
    exporter_url="http://jaeger:14268/api/traces"
)

# Con context manager (recomendado)
with tracer.trace("voice.process", tags={"session_id": "sess_001"}) as root:
    with tracer.trace("stt.transcribe", parent_span=root) as stt_span:
        transcript = transcribe_audio(audio)
        stt_span.set_tag("language", "es-CO")

    with tracer.trace("llm.generate", parent_span=root) as llm_span:
        response = generate_response(transcript)
        llm_span.set_tag("model", "gpt-4o-mini")
```

## Jaeger
```bash
scripts/setup_jaeger.sh
```
UI disponible en: http://localhost:16686

## Variables de entorno
```env
JAEGER_COLLECTOR_URL=http://localhost:14268/api/traces
TRACING_SERVICE_NAME=agentevoz
TRACING_SAMPLE_RATE=1.0
```

## Propagacion de contexto
El `trace_id` debe propagarse entre microservicios via headers:
- `X-Trace-ID: {trace_id}`
- `X-Span-ID: {span_id}`

## SLOs monitoreados via tracing
| Operacion | SLO |
|-----------|-----|
| voice.process total | < 3000ms |
| stt.transcribe | < 1500ms |
| llm.generate | < 1000ms |
| tts.synthesize | < 500ms |
