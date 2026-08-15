#inbound buffer to receive audios and queue them and pass them accordningly without breaking user sentence.
import asyncio
import logging
import contextlib

logger = logging.getLogger(__name__)

class AudioReceiver:
    def __init__(self, session_id: str, maxsize: int = 100) -> None:
        self.session_id = session_id
        # inititialse asynchrous FIFO queue for raw audio bytes
        self.queue: asyncio.Queue[bytes] = asyncio.Queue(maxsize=maxsize)

    async def enqueue_chunk(self, chunk:bytes):
        """Receives raw audio bytes from the WebSocket gateway and buffers them."""
        #put the chunk into queue asynchronoiuly
        #await self.queue.put(chunk)
        try: 
            self.queue.put_nowait(chunk)
        except asyncio.QueueFull:
            #drop the oldest chunk if the queue is full
            with contextlib.suppress(asyncio.QueueEmpty):
                self.queue.get_nowait()
            self.queue.put_nowait(chunk)
            logger.warning(f"[{self.session_id}] Receiver queue full — dropped oldest chunk.")

       # logger.debug(f"{self.session_id}] Enqueued {len(chunk)} bytes. Queuesize: {self.queue.qsize()}")

    async def get_next_chunk(self) -> bytes:
        """Pulls the oldest audio chunk out of the queue for transcription"""
        # get the next chunk from the queue and return it
        chunk = await self.queue.get()

        logger.debug(f"{self.session_id}] Dequeued {len(chunk)} bytes. Queuesize: {self.queue.qsize()}")
        return chunk
    
    def flush(self) -> int:
        drained = 0
        while not self.queue.empty():
            try:
                self.queue.get_nowait()
                drained += 1
            except asyncio.QueueEmpty:
                break
        return drained
