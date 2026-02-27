import logging
import time

from monitor.sensor_manager import SensorManager

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
)


def main():
    manager = SensorManager(config_path="config.json")
    interval = manager.polling_interval

    # Build a lookup of sensor_id -> name for alert messages
    sensor_names = {s.sensor_id: s.name for s in manager._sensors}

    print(f"Equipment Monitor started. Polling every {interval}s. Ctrl+C to stop.\n")

    try:
        while True:
            readings, alert_ids = manager.poll()

            for r in readings:
                alarm_tag = "  [ALARM]" if r.alarming else ""
                ts = r.timestamp.strftime("%H:%M:%S")
                print(f"[{ts}] {sensor_names.get(r.sensor_id, r.sensor_id)}: "
                      f"{r.value}{r.unit}{alarm_tag}")

            for sid in alert_ids:
                name = sensor_names.get(sid, sid)
                print(f"  -> Email alert would be sent: {name}")

            time.sleep(interval)

    except KeyboardInterrupt:
        print("\nStopped.")


if __name__ == "__main__":
    main()
