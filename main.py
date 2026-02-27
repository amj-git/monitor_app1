import json
import logging
import threading
import time

from monitor.sensor_manager import SensorManager
from monitor.web import create_app

logging.basicConfig(
    level=logging.INFO,
    format="%(levelname)s %(name)s: %(message)s",
)


def main():
    with open("config.json") as f:
        config = json.load(f)

    manager = SensorManager(config_path="config.json")
    interval = manager.polling_interval

    sensor_names = {s.sensor_id: s.name for s in manager._sensors}

    web_cfg = config.get("web", {})
    flask_config = {
        "secret_key": web_cfg.get("secret_key", "change-me"),
        "username": web_cfg.get("username", "admin"),
        "password_hash": web_cfg.get("password_hash", ""),
        "db": manager._db,
        "sensor_names": sensor_names,
    }
    app = create_app(flask_config)
    host = web_cfg.get("host", "0.0.0.0")
    port = web_cfg.get("port", 5000)

    threading.Thread(
        target=lambda: app.run(host=host, port=port, use_reloader=False, debug=False),
        daemon=True,
        name="flask-web",
    ).start()
    print(f"Web GUI running at http://{host}:{port}/")

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
    finally:
        manager.close()


if __name__ == "__main__":
    main()
