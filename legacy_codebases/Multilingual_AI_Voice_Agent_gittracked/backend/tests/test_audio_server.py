import asyncio
import websockets
import struct
import random
import math

async def handler(ws):
    print("Test client connected!")
    # Generate 200 chunks of a 440Hz tone
    for i in range(200):
        # Generate 2048 samples (16-bit PCM)
        samples = [int(32767 * 0.3 * math.sin(2 * math.pi * 440 * (i * 93 + j) / 22050)) for j in range(2048)]
        # Pack into little-endian 16-bit integers
        await ws.send(struct.pack('<%dh' % len(samples), *samples))
        # Simulate network jitter
        await asyncio.sleep(random.choice([0.09, 0.09, 0.3])) 

async def main():
    async with websockets.serve(handler, 'localhost', 8765):
        print("Test server running on ws://localhost:8765")
        await asyncio.Future()  # run forever

asyncio.run(main())