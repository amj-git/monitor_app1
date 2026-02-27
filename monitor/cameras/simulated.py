from __future__ import annotations

import logging

from .base import BaseCamera

logger = logging.getLogger(__name__)

# Minimal valid JPEG: Start Of Image + End Of Image markers
_PLACEHOLDER_JPEG = b'\xff\xd8\xff\xd9'


class SimulatedCamera(BaseCamera):
    """Writes a minimal JPEG placeholder — no hardware required."""

    def capture(self, filepath: str) -> bool:
        try:
            with open(filepath, 'wb') as f:
                f.write(_PLACEHOLDER_JPEG)
            logger.info("Simulated capture saved: %s", filepath)
            return True
        except Exception as exc:
            logger.error("SimulatedCamera: failed to write %s: %s", filepath, exc)
            return False
