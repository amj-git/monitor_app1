from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class SensorReading:
    sensor_id: str
    value: float
    unit: str
    timestamp: datetime
    alarming: bool


class BaseSensor(ABC):
    def __init__(self, sensor_id, name, unit, alarm_min=None, alarm_max=None):
        self.sensor_id = sensor_id
        self.name = name
        self.unit = unit
        self.alarm_min = alarm_min
        self.alarm_max = alarm_max

    @abstractmethod
    def read(self) -> SensorReading:
        pass

    def is_alarming(self, value: float) -> bool:
        if self.alarm_min is not None and value < self.alarm_min:
            return True
        if self.alarm_max is not None and value > self.alarm_max:
            return True
        return False
