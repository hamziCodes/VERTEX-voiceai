"""Official UCVE Python Voice Client SDK."""

from __future__ import annotations

from sdk.python.ucve.client import UCVEVoiceClient
from sdk.python.ucve.version import SDK_VERSION_MANIFEST, __version__

__all__ = ["UCVEVoiceClient", "SDK_VERSION_MANIFEST", "__version__"]
