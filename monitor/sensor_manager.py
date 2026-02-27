from __future__ import annotations

import json
import logging

from .alarm_manager import AlarmManager
from .sensors.base import SensorReading
from .sensors.simulated import SimulatedTemperatureSensor
from .sensors.ds18b20 import DS18B20Sensor

logger = logging.getLogger(__name__)

SENSOR_TYPES = {
    "simulated_temperature": SimulatedTemperatureSensor,
    "ds18b20": DS18B20Sensor,
}


def _build_sensor(cfg: dict):
    sensor_type = cfg.get("type")
    cls = SENSOR_TYPES.get(sensor_type)
    if cls is None:
        raise ValueError(f"Unknown sensor type: '{sensor_type}'")

    kwargs = {
        "sensor_id": cfg["id"],
        "name": cfg["name"],
        "alarm_min": cfg.get("alarm_min"),
        "alarm_max": cfg.get("alarm_max"),
    }

    if cls is SimulatedTemperatureSensor:
        kwargs["sim_min"] = cfg.get("sim_min", 0.0)
        kwargs["sim_max"] = cfg.get("sim_max", 100.0)
    elif cls is DS18B20Sensor:
        kwargs["device_id"] = cfg["device_id"]

    return cls(**kwargs)


class SensorManager:
    def __init__(self, config_path: str = "config.json"):
        with open(config_path, "r") as f:
            config = json.load(f)

        self.polling_interval: int = config.get("polling_interval", 30)
        self._sensors = []
        for sensor_cfg in config.get("sensors", []):
            try:
                self._sensors.append(_build_sensor(sensor_cfg))
            except Exception as e:
                logger.error("Failed to initialise sensor %s: %s",
                             sensor_cfg.get("id", "?"), e)

        self._alarm_manager = AlarmManager()

    def poll(self) -> tuple[list[SensorReading], list[str]]:
        """
        Read all sensors.
        Returns (readings, alert_sensor_ids).
        alert_sensor_ids lists sensors that should trigger an email.
        """
        readings: list[SensorReading] = []
        alert_sensor_ids: list[str] = []

        for sensor in self._sensors:
            try:
                reading = sensor.read()
                readings.append(reading)
                if self._alarm_manager.update(sensor.sensor_id, reading.alarming):
                    alert_sensor_ids.append(sensor.sensor_id)
            except Exception as e:
                logger.error("Error reading sensor %s: %s", sensor.sensor_id, e)
                # Sensor in error is not alarming — clear alarm state
                self._alarm_manager.update(sensor.sensor_id, False)

        return readings, alert_sensor_ids
