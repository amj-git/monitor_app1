from __future__ import annotations

import logging

from .base import BaseCamera

logger = logging.getLogger(__name__)

try:
    from picamera2 import Picamera2
    _PICAMERA2_AVAILABLE = True
except ImportError:
    _PICAMERA2_AVAILABLE = False


class PiCSICamera(BaseCamera):
    """Captures a still image using the Raspberry Pi CSI camera via picamera2."""

    def __init__(self):
        if not _PICAMERA2_AVAILABLE:
            raise RuntimeError(
                "picamera2 not available — install it on the Pi"
            )

    def capture(self, filepath: str) -> bool:
        try:
            cam = Picamera2()
            cam.configure(cam.create_still_configuration())
            cam.start()
            cam.capture_file(filepath)
            cam.close()
            return True
        except Exception as exc:
            logger.error("PiCSICamera: capture failed: %s", exc)
            return False

    def close(self) -> None:
        pass
