import time
import asyncio
import logging
from backend.app.transport.connection_manager import connection_manager

logger = logging.getLogger(__name__)

class AudioSender:
    def __init__(self, session_id: str, ws_lock: asyncio.Lock, maxsize: int = 200) -> None:
        self.session_id = session_id
        self.ws_lock = ws_lock
        
        self.queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=maxsize)
        self._is_running = True
        self.paused = False
        
        self.interrupt_event = asyncio.Event()
        self.speaking_until = 0.0  # Epoch time watermark
        self.sample_rate_hz = 22050
        self.bytes_per_sample = 2

    def clear_interrupt(self) -> None:
        """Resets the interrupt flag to allow audio packet transmission."""
        self.interrupt_event.clear()

    async def queue_output_chunk(self, chunk: bytes) -> None:
        """Pushes synthesised AI audio bytes into the output queue with backpressure."""
        await self.queue.put(chunk)

    async def send_loop(self) -> None:
        """Continuous background worker loop that pulls from the queue and sends to the client."""
        logger.info(f"[{self.session_id}] Outbound audio sender loop started.")
        
        try: 
            while self._is_running:
                # If paused, wait/sleep instead of getting from queue
                while self.paused and self._is_running:
                    await asyncio.sleep(0.05)
                if not self._is_running:
                    break
                    
                audio_chunk = await self.queue.get()

                # Sanity Check: Ensure chunk is cleanly divisible by 2 (16-bit mono PCM sample alignment)
                if len(audio_chunk) % 2 != 0:
                    logger.warning(f"[{self.session_id}] AudioSender: Received odd-length chunk ({len(audio_chunk)} bytes). Aligning to even boundary.")
                    audio_chunk = audio_chunk[:-1]

                if not audio_chunk:
                    self.queue.task_done()
                    continue

                # Double check to prevent race conditions during barge-in flushes
                if self.interrupt_event.is_set():
                    self.queue.task_done()
                    continue

                websocket = await connection_manager.get_connection(self.session_id)
                if websocket:
                    if self.interrupt_event.is_set():
                        self.queue.task_done()
                        continue
                    try:
                        async with self.ws_lock:
                            if self.interrupt_event.is_set():
                                self.queue.task_done()
                                continue
                            await websocket.send_bytes(audio_chunk)
                        
                        # Update speaking watermark dynamically
                        chunk_duration = len(audio_chunk) / (self.sample_rate_hz * self.bytes_per_sample)
                        now = time.time()
                        if self.speaking_until < now:
                            self.speaking_until = now
                        self.speaking_until += chunk_duration
                        
                    except Exception as e:
                        logger.error(f"[{self.session_id}] Failed to send audio chunk: {e}")
                        self._is_running = False
                else:
                    logger.warning(f"[{self.session_id}] WebSocket connection not found, stopping audio sender.")
                    self._is_running = False

                self.queue.task_done()
        
        except asyncio.CancelledError:
            logger.info(f"[{self.session_id}] Audio sender loop stopped via cancellation.")
        except Exception as e:
            logger.error(f"[{self.session_id}] Error in audio sender loop: {e}")

    def stop(self) -> None:
        """Stops the loop execution safely."""
        self._is_running = False

    async def flush(self) -> int:
        """Silences active AI playback and resets queues."""
        self.interrupt_event.set()
        drained = 0
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
                drained += 1
                self.queue.task_done()
            except asyncio.QueueEmpty:
                break
        
        # Reset the speaking watermark
        self.speaking_until = 0.0
        
        if drained > 0:
            logger.info(f"[{self.session_id}] Flushed {drained} queued audio chunks.")
        return drained

    async def wait_until_drained(self) -> None:
        """Blocks until all queued chunks are dispatched and finished playout."""
        await self.queue.join()
        now = time.time()
        if self.speaking_until > now:
            await asyncio.sleep(self.speaking_until - now)

    def pause(self) -> None:
        """Pauses outbound chunk dispatching."""
        self.paused = True
        logger.info(f"[{self.session_id}] AudioSender paused.")

    def resume(self) -> None:
        """Resumes outbound chunk dispatching."""
        self.paused = False
        logger.info(f"[{self.session_id}] AudioSender resumed.")