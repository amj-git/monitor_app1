import random
from datetime import datetime

from .base import BaseSensor, SensorReading


class SimulatedTemperatureSensor(BaseSensor):
    def __init__(self, sensor_id, name, alarm_min=None, alarm_max=None,
                 sim_min=0.0, sim_max=100.0):
        super().__init__(sensor_id, name, unit="°C",
                         alarm_min=alarm_min, alarm_max=alarm_max)
        self.sim_min = sim_min
        self.sim_max = sim_max

    def read(self) -> SensorReading:
        value = round(random.uniform(self.sim_min, self.sim_max), 1)
        return SensorReading(
            sensor_id=self.sensor_id,
            value=value,
            unit=self.unit,
            timestamp=datetime.now(),
            alarming=self.is_alarming(value),
        )
