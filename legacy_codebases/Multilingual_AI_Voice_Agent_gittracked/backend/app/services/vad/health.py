_silero_healthy = False

def set_silero_healthy(status: bool) -> None:
    global _silero_healthy
    _silero_healthy = status
    
def is_silero_healthy() -> bool:
    global _silero_healthy
    return _silero_healthy
