from __future__ import annotations

import logging
import os
from datetime import datetime, timedelta

from .cameras.simulated import SimulatedCamera
from .cameras.csi import PiCSICamera

logger = logging.getLogger(__name__)

CAMERA_TYPES = {
    "simulated": SimulatedCamera,
    "csi": PiCSICamera,
}


class CameraManager:
    """Orchestrates photo capture: alarm-triggered and periodic."""

    def __init__(self, config: dict):
        self._enabled = config.get("enabled", False)
        self._photo_dir = config.get("photo_dir", "data/photos")
        self._max_size_mb = float(config.get("max_photo_dir_size_mb", 100.0))
        self._periodic_hours = float(config.get("periodic_interval_hours", 6.0))
        self._last_periodic: datetime | None = None

        if self._enabled:
            os.makedirs(self._photo_dir, exist_ok=True)
            camera_type = config.get("type", "simulated")
            cls = CAMERA_TYPES.get(camera_type)
            if cls is None:
                raise ValueError(
                    f"Unknown camera type '{camera_type}'. "
                    f"Valid types: {list(CAMERA_TYPES)}"
                )
            self._camera = cls()
        else:
            self._camera = None

    def is_enabled(self) -> bool:
        return self._enabled

    def capture(self, trigger: str, sensor_id: str | None = None) -> str | None:
        """Capture a photo and return the filepath, or None if disabled/failed."""
        if not self._enabled:
            return None

        ts = datetime.now().strftime("%Y%m%d_%H%M%S")
        if sensor_id:
            filename = f"photo_{ts}_{trigger}_{sensor_id}.jpg"
        else:
            filename = f"photo_{ts}_{trigger}.jpg"

        filepath = os.path.join(self._photo_dir, filename)
        success = self._camera.capture(filepath)
        if success:
            logger.info("Captured photo (%s): %s", trigger, filepath)
            return filepath
        return None

    def maybe_capture_periodic(self) -> str | None:
        """Capture a periodic photo if the interval has elapsed."""
        if not self._enabled or self._periodic_hours <= 0:
            return None

        now = datetime.now()
        if self._last_periodic is None:
            self._last_periodic = now
            return self.capture(trigger="periodic")

        if (now - self._last_periodic) >= timedelta(hours=self._periodic_hours):
            self._last_periodic = now
            return self.capture(trigger="periodic")

        return None

    def cleanup_if_needed(self) -> int:
        """Delete oldest photos until the folder is under the size limit."""
        if not self._enabled:
            return 0

        try:
            entries = [
                os.path.join(self._photo_dir, f)
                for f in os.listdir(self._photo_dir)
                if os.path.isfile(os.path.join(self._photo_dir, f))
            ]
        except OSError as exc:
            logger.error("camera_manager: cannot list photo dir: %s", exc)
            return 0

        total_mb = sum(os.path.getsize(p) for p in entries) / (1024 * 1024)
        if total_mb <= self._max_size_mb:
            return 0

        # Oldest first
        entries.sort(key=lambda p: os.path.getmtime(p))
        deleted = 0
        for path in entries:
            if total_mb <= self._max_size_mb:
                break
            size_mb = os.path.getsize(path) / (1024 * 1024)
            try:
                os.remove(path)
                total_mb -= size_mb
                deleted += 1
            except OSError as exc:
                logger.error("camera_manager: failed to delete %s: %s", path, exc)

        if deleted:
            logger.info(
                "Deleted %d old photo(s) to stay under %.1f MB",
                deleted, self._max_size_mb,
            )
        return deleted

    def close(self) -> None:
        if self._camera is not None:
            self._camera.close()
