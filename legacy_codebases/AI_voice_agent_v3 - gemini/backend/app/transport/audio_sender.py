from backend.app.transport.connection_manager import connection_manager
import asyncio
import time
import logging

logger = logging.getLogger(__name__)

class AudioSender:
    #maxsize to bound the queue and prevent memory leaks
    def __init__(self, session_id: str, ws_lock: asyncio.Lock, interrupt_event: asyncio.Event, maxsize: int = 200):
        self.session_id = session_id
        self.ws_lock = ws_lock
        self._interrupt_event = interrupt_event

        # queue holding outgoing AI data chunks (capped at 200 chunks)
        self.queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=maxsize)
        
        # a control flag to stop the bg running loop (keep it alive or kill it)
        self._is_running = True

    async def queue_output_chunk(self, chunk: bytes):
        """Pushes synthesised AI audio bytes into the output queue."""
        # Because we added maxsize, this 'await' now acts as blocking backpressure 
        # so TTS doesn't overload the server memory if the network is slow.
        await self.queue.put(chunk)

    async def send_loop(self):
        """Continous background worker loop that pulls from the queue and send to the client."""
        logger.info(f"[{self.session_id}] Outbound audio sender loop started.")
        
        seq = 0
        while self._is_running:
            try:
                # wait until there are outbound audio bytes in the queue
                audio_chunk = await self.queue.get()
                seq += 1

                # CRITICAL: Even though this chunk was already dequeued, we must
                # still check the interrupt flag before sending it down the wire.
                # This closes the race window where flush() runs but the in-flight
                # chunk has already left the queue.
                if self._interrupt_event.is_set():
                    logger.info(f"[{self.session_id}] SEND-LOOP dropped chunk #{seq} (interrupt active)")
                    self.queue.task_done()
                    continue

                # get the active Websocketline from the connection_manager
                websocket = await connection_manager.get_connection(self.session_id)

                # if the connection exists push the raw bytes down the pipe
                if websocket:
                    async with self.ws_lock:
                        await websocket.send_bytes(audio_chunk)
                    logger.debug(f"[{self.session_id}] SEND-LOOP sent chunk #{seq} ({len(audio_chunk)}B) at t={time.time():.3f}")

                # tell the queue that this chunk has been successfully processed
                self.queue.task_done()
            except asyncio.CancelledError:
                logger.info(f"[{self.session_id}] Audio sender loop stopped via cancellation.")
                break
            except Exception as e:
                logger.error(f"[{self.session_id}] Error in audio sender loop processing chunk #{seq}: {e}")
                try:
                    self.queue.task_done()
                except ValueError:
                    pass

    def stop(self):
        """Stops the loop execution safely."""
        self._is_running = False

    #flush method so the Orchestrator can instantly silence the AI on barge-in
    async def flush(self) -> int:
        drained = 0
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
                self.queue.task_done()
                drained += 1
            except asyncio.QueueEmpty:
                break
        if drained > 0:
            logger.info(f"[{self.session_id}] Flushed {drained} queued audio chunks.")
        return drained

    async def wait_until_drained(self) -> None:
        """Blocks until the outgoing queue has been fully drained and sent to the client."""
        await self.queue.join()