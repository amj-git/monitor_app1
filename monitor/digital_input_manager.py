from __future__ import annotations

import logging
import threading
from datetime import datetime, timedelta

from .digital_inputs.base import BaseDigitalInput
from .digital_inputs.gpio_input import GPIODigitalInput
from .digital_inputs.simulated import SimulatedDigitalInput
from .sensors.base import SensorReading

logger = logging.getLogger(__name__)
COOLDOWN = timedelta(days=1)

_INPUT_TYPES = {
    "gpio":      GPIODigitalInput,
    "simulated": SimulatedDigitalInput,
}


def _build_input(cfg: dict) -> BaseDigitalInput:
    t = cfg.get("type", "gpio")
    cls = _INPUT_TYPES.get(t)
    if cls is None:
        raise ValueError(f"Unknown digital input type: '{t}'")
    kwargs = {
        "input_id": cfg["id"],
        "name": cfg["name"],
        "active_state": cfg.get("active_state", "high"),
    }
    if cls is GPIODigitalInput:
        kwargs["gpio_pin"] = cfg["gpio_pin"]
        kwargs["pull"] = cfg.get("pull", "down")
    elif cls is SimulatedDigitalInput:
        kwargs["sim_interval_seconds"] = cfg.get("sim_interval_seconds", 90)
    return cls(**kwargs)


class DigitalInputManager:
    def __init__(self, config: dict, db, camera, emailer):
        self._db = db
        self._camera = camera
        self._emailer = emailer
        self._inputs: list[BaseDigitalInput] = []
        self._names: dict[str, str] = {}
        self._last_email: dict[str, datetime] = {}
        self._lock = threading.Lock()

        for cfg in config.get("digital_inputs", []):
            try:
                inp = _build_input(cfg)
                self._inputs.append(inp)
                self._names[cfg["id"]] = cfg["name"]
            except Exception as exc:
                logger.error("Failed to init digital input %s: %s",
                             cfg.get("id", "?"), exc)

    @property
    def input_names(self) -> dict[str, str]:
        return dict(self._names)

    def start(self) -> None:
        for inp in self._inputs:
            try:
                inp.start(self._on_trigger)
            except Exception as exc:
                logger.error("Failed to start digital input %s: %s",
                             inp.input_id, exc)

    def stop(self) -> None:
        for inp in self._inputs:
            try:
                inp.stop()
            except Exception as exc:
                logger.error("Failed to stop digital input %s: %s",
                             inp.input_id, exc)

    def _on_trigger(self, input_id: str) -> None:
        now = datetime.now()
        name = self._names.get(input_id, input_id)

        # Log event to DB
        reading = SensorReading(
            sensor_id=input_id, value=1.0, unit="triggered",
            timestamp=now, alarming=True,
        )
        try:
            self._db.insert_readings([reading])
        except Exception as exc:
            logger.error("DB write failed for digital input %s: %s", input_id, exc)

        ts = now.strftime("%H:%M:%S")
        print(f"[{ts}] {name}: TRIGGERED  [ALARM]")

        # 1-day email cooldown
        should_email = False
        with self._lock:
            last = self._last_email.get(input_id)
            if last is None or (now - last) >= COOLDOWN:
                self._last_email[input_id] = now
                should_email = True

        if should_email:
            print(f"  -> Alert: {name}")
            photo_path = self._camera.capture(trigger="alarm", sensor_id=input_id)
            self._emailer.send_digital_alert(name, input_id, now,
                                             photo_path=photo_path)
