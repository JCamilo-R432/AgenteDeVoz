from typing import Dict, List, Any
"""
WebSocket para streaming de audio en tiempo real.
Soporta el protocolo de Twilio Media Streams y clientes web directos.
"""

import json
import base64
import asyncio
from typing import Optional
from fastapi import WebSocket, WebSocketDisconnect
from utils.logger import setup_logger

logger = setup_logger("websocket")


class ConnectionManager:
    """Gestiona conexiones WebSocket activas."""

    def __init__(self):
        self.active: dict[str, WebSocket] = {}   # session_id -> ws

    async def connect(self, session_id: str, ws: WebSocket):
        await ws.accept()
        self.active[session_id] = ws
        logger.info(f"WS conectado: {session_id} total={len(self.active)}")

    def disconnect(self, session_id: str):
        self.active.pop(session_id, None)
        logger.info(f"WS desconectado: {session_id}")

    async def send_text(self, session_id: str, message: str):
        ws = self.active.get(session_id)
        if ws:
            await ws.send_text(message)

    async def send_json(self, session_id: str, data: dict):
        ws = self.active.get(session_id)
        if ws:
            await ws.send_json(data)

    async def broadcast(self, data: dict):
        for ws in list(self.active.values()):
            try:
                await ws.send_json(data)
            except Exception:
                pass


manager = ConnectionManager()


# ── Handler para Twilio Media Streams ─────────────────────────────────────────

async def handle_twilio_media_stream(websocket: WebSocket):
    """
    Maneja el WebSocket de Twilio Media Streams.
    Protocolo: recibe audio mulaw 8kHz, retorna audio base64.

    Flujo:
      1. connected  -> guardar stream_sid
      2. start      -> inicializar sesion de transcripcion
      3. media      -> acumular chunks de audio y transcribir
      4. stop       -> cerrar sesion
    """
    call_sid: Optional[str] = None
    stream_sid: Optional[str] = None
    audio_buffer: list = []
    session_id: Optional[str] = None

    await websocket.accept()
    logger.info("Twilio Media Stream WS abierto")

    try:
        from core.agent import CustomerServiceAgent
        agent: Optional[CustomerServiceAgent] = None

        async for raw in websocket.iter_text():
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                continue

            event = msg.get("event")

            if event == "connected":
                logger.info("Twilio: connected")

            elif event == "start":
                start = msg.get("start", {})
                call_sid = start.get("callSid", "")
                stream_sid = start.get("streamSid", "")
                session_id = f"twilio_{call_sid[:12]}"

                import uuid
                if not call_sid:
                    session_id = f"twilio_{uuid.uuid4().hex[:8]}"

                agent = CustomerServiceAgent(session_id=session_id)
                greeting = agent.start_call()
                logger.info(f"Twilio stream iniciado: {stream_sid}")

                # Enviar saludo como audio
                tts_audio = _synthesize(agent, greeting)
                if tts_audio and stream_sid:
                    await _send_audio_to_twilio(websocket, stream_sid, tts_audio)

            elif event == "media":
                if not agent:
                    continue
                payload = msg.get("media", {}).get("payload", "")
                if payload:
                    chunk = base64.b64decode(payload)
                    audio_buffer.append(chunk)

                    # Procesar cada ~0.5s de audio (4000 bytes a 8kHz mulaw)
                    if len(audio_buffer) >= 10:
                        audio_data = b"".join(audio_buffer)
                        audio_buffer.clear()

                        # Transcribir (no bloqueante)
                        text = await asyncio.get_event_loop().run_in_executor(
                            None, agent.stt.transcribe_stream, audio_data
                        )
                        if text and len(text.strip()) > 2:
                            logger.info(f"[{session_id}] STT: {text}")
                            response = await asyncio.get_event_loop().run_in_executor(
                                None, agent.process_input, None, text
                            )
                            if response and stream_sid:
                                tts_audio = _synthesize(agent, response)
                                if tts_audio:
                                    await _send_audio_to_twilio(
                                        websocket, stream_sid, tts_audio
                                    )

            elif event == "stop":
                logger.info(f"Twilio stream detenido: {stream_sid}")
                if agent and agent.is_active:
                    agent.end_call()
                break

    except WebSocketDisconnect:
        logger.info(f"Twilio WS desconectado: {session_id}")
    except Exception as e:
        logger.error(f"Error en Twilio Media Stream: {e}")
    finally:
        if session_id:
            manager.disconnect(session_id)


# ── Handler para clientes web directos ───────────────────────────────────────

async def handle_web_client(websocket: WebSocket, session_id: str):
    """
    WebSocket para el dashboard web y clientes SPA.
    Protocolo JSON bidireccional.

    Mensajes del cliente:
      {"type": "text", "content": "texto del usuario"}
      {"type": "ping"}
      {"type": "end"}

    Mensajes del servidor:
      {"type": "response", "content": "...", "intent": "...", "state": "..."}
      {"type": "error", "message": "..."}
      {"type": "pong"}
    """
    await manager.connect(session_id, websocket)

    from core.agent import CustomerServiceAgent
    agent = CustomerServiceAgent(session_id=session_id)
    greeting = agent.start_call()
    await manager.send_json(session_id, {
        "type": "response",
        "content": greeting,
        "intent": "saludo",
        "state": agent.conversation.get_state(),
    })

    try:
        while True:
            raw = await websocket.receive_text()
            try:
                msg = json.loads(raw)
            except json.JSONDecodeError:
                await manager.send_json(session_id, {
                    "type": "error",
                    "message": "JSON invalido",
                })
                continue

            msg_type = msg.get("type")

            if msg_type == "ping":
                await manager.send_json(session_id, {"type": "pong"})

            elif msg_type == "text":
                content = msg.get("content", "").strip()
                if not agent.is_active:
                    await manager.send_json(session_id, {
                        "type": "error",
                        "message": "La sesion ha finalizado",
                    })
                    break
                response = await asyncio.get_event_loop().run_in_executor(
                    None, agent.process_input, None, content
                )
                await manager.send_json(session_id, {
                    "type": "response",
                    "content": response,
                    "intent": agent.conversation.get_context("last_intent", ""),
                    "state": agent.conversation.get_state(),
                })

            elif msg_type == "end":
                farewell = agent.end_call()
                await manager.send_json(session_id, {
                    "type": "response",
                    "content": farewell,
                    "state": "FIN",
                })
                break

    except WebSocketDisconnect:
        logger.info(f"Cliente web desconectado: {session_id}")
    except Exception as e:
        logger.error(f"Error en WS cliente web {session_id}: {e}")
    finally:
        manager.disconnect(session_id)
        if agent and agent.is_active:
            agent.end_call()


# ── Helpers ───────────────────────────────────────────────────────────────────

def _synthesize(agent, text: str) -> Optional[bytes]:
    """Sintetiza texto a audio con el TTS del agente."""
    try:
        return agent.tts.synthesize_to_bytes(text)
    except Exception as e:
        logger.error(f"TTS error: {e}")
        return None


async def _send_audio_to_twilio(ws: WebSocket, stream_sid: str, audio: bytes):
    """Envía audio al cliente Twilio Media Stream en formato base64."""
    msg = {
        "event": "media",
        "streamSid": stream_sid,
        "media": {
            "payload": base64.b64encode(audio).decode("utf-8"),
        },
    }
    await ws.send_text(json.dumps(msg))
