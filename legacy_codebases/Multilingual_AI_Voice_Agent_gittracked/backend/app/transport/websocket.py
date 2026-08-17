import uuid
import logging
import asyncio
import contextlib
import json
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from backend.app.transport.connection_manager import connection_manager
from backend.app.transport.audio_receiver import AudioReceiver
from backend.app.transport.audio_sender import AudioSender
from backend.app.orchestration.session import SessionOrchestrator
from backend.app.services.vad.health import is_silero_healthy

router = APIRouter()
logger = logging.getLogger(__name__)

@router.websocket("/ws/audio")
async def audio_endpoint(websocket: WebSocket):
    session_id = str(uuid.uuid4())
    ws_lock = asyncio.Lock()
    
    # 1. Perform startup VAD health check
    if not is_silero_healthy():
        logger.error(f"[{session_id}] Connection rejected: Silero VAD is unhealthy.")
        await websocket.accept()
        await websocket.send_text(json.dumps({"type": "error", "message": "VAD engine is currently unhealthy. Connection rejected."}))
        await websocket.close()
        return

    audio_receiver = AudioReceiver(session_id)
    audio_sender = AudioSender(session_id, ws_lock)

    await connection_manager.connect(session_id, websocket)
    sender_task = asyncio.create_task(audio_sender.send_loop())
    orchestrator = SessionOrchestrator(session_id, websocket, audio_receiver, audio_sender, ws_lock)
    pipeline_task = asyncio.create_task(orchestrator.run())

    # Proactively trigger greeting
    greeting_task = asyncio.create_task(orchestrator.trigger_greeting())

    # 20-second keepalive heartbeat ping loop
    async def heartbeat_ping_loop():
        try:
            while True:
                await asyncio.sleep(20)
                async with ws_lock:
                    await websocket.send_text(json.dumps({"type": "control", "action": "ping"}))
        except asyncio.CancelledError:
            pass
        except Exception as e:
            logger.error(f"[{session_id}] Keepalive ping failed: {e}")

    heartbeat_task = asyncio.create_task(heartbeat_ping_loop())

    try:
        logger.info(f"[{session_id}] Full-duplex streaming connection established.")
        while True:  
            # Fail fast if background processing tasks crashed (e.g. Gladia API exhaustion)
            for t_name, task in [("Pipeline", pipeline_task), ("AudioSender", sender_task)]:
                if task.done() and not task.cancelled():
                    exc = task.exception()
                    if not exc and t_name == "Pipeline":
                        exc = orchestrator.get_last_error()
                    if exc:
                        logger.error(f"[{session_id}] Background {t_name} task failed: {exc}")
                        raise exc
                    else:
                        logger.error(f"[{session_id}] Background {t_name} task exited unexpectedly.")
                        raise RuntimeError(f"Background {t_name} task exited unexpectedly.")

            data = await websocket.receive_bytes()
            # 1. Feed the audio data to VAD for real-time barge-in detection
            await orchestrator.process_client_audio(data)
            # 2. Feed the audio receiver queue for STT processing
            await audio_receiver.enqueue_chunk(data)

    except WebSocketDisconnect:
        logger.info(f"[{session_id}] Client disconnected gracefully.")
    except Exception as e:
        logger.error(f"[{session_id}] Error in Websocket gateway: {e}")
        # Send a helpful error message to the client before closing
        with contextlib.suppress(Exception):
            error_msg = str(e)
            if "free audio transcription" in error_msg.lower() or "402" in error_msg:
                user_msg = "Gladia STT transcription limit reached (402 Payment Required). Please visit app.gladia.io to upgrade or change your API key."
            elif "401" in error_msg or "unauthorized" in error_msg.lower() or "forbidden" in error_msg.lower():
                user_msg = "Invalid or unauthorized Gladia STT API Key. Please check your .env file."
            else:
                user_msg = f"System Error: {error_msg}"
            
            async with ws_lock:
                await websocket.send_text(json.dumps({"type": "error", "message": user_msg}))

    finally:
        # Cancel background tasks safely
        for task in (heartbeat_task, greeting_task, pipeline_task, sender_task):
            if task and not task.done():
                task.cancel()

        for task in (heartbeat_task, greeting_task, pipeline_task, sender_task):
            if task:
                with contextlib.suppress(Exception):
                    await task

        with contextlib.suppress(Exception):
            await orchestrator.shutdown()

        audio_sender.stop()
        with contextlib.suppress(Exception):
            await connection_manager.disconnect(session_id)
        logger.info(f"[{session_id}] Connection closed and cleaned up.")