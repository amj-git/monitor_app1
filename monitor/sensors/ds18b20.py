from datetime import datetime

from .base import BaseSensor, SensorReading


class DS18B20Sensor(BaseSensor):
    def __init__(self, sensor_id, name, device_id, alarm_min=None, alarm_max=None):
        super().__init__(sensor_id, name, unit="°C",
                         alarm_min=alarm_min, alarm_max=alarm_max)
        self.device_id = device_id
        self._device_path = f"/sys/bus/w1/devices/{device_id}/w1_slave"

    def read(self) -> SensorReading:
        try:
            with open(self._device_path, "r") as f:
                lines = f.readlines()
        except OSError as e:
            raise RuntimeError(
                f"DS18B20 '{self.sensor_id}': cannot read {self._device_path}: {e}"
            )

        # Find the line containing "t=XXXXX"
        for line in lines:
            if "t=" in line:
                t_str = line.split("t=")[-1].strip()
                try:
                    value = round(int(t_str) / 1000.0, 1)
                except ValueError:
                    raise RuntimeError(
                        f"DS18B20 '{self.sensor_id}': unexpected format in {self._device_path}"
                    )
                return SensorReading(
                    sensor_id=self.sensor_id,
                    value=value,
                    unit=self.unit,
                    timestamp=datetime.now(),
                    alarming=self.is_alarming(value),
                )

        raise RuntimeError(
            f"DS18B20 '{self.sensor_id}': 't=' not found in {self._device_path}"
        )
