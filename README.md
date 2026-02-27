# Equipment Monitor

A Raspberry Pi sensor monitoring application. Polls temperature sensors on a configurable
interval, tracks alarm states, and (in future) sends email alerts and serves a web GUI.

---

## Requirements

- Python 3.7 or later
- No third-party packages are needed at this stage — the sensor framework is stdlib-only

---

## Installation — Windows (development)

Use Windows for development and testing with the simulated sensor. No hardware is required.

**1. Clone the repository**

```
git clone git@github.com:amj-git/monitor_app1.git
cd monitor_app1
```

**2. Create and activate a virtual environment**

```
python -m venv venv
venv\Scripts\activate
```

**3. Install dependencies**

```
pip install -r requirements-dev.txt
```

*(The file is currently empty — no packages to install. This step will matter once Flask is added.)*

---

## Installation — Raspberry Pi (production)

**1. Clone the repository**

```
git clone git@github.com:amj-git/monitor_app1.git
cd monitor_app1
```

**2. Enable the DS18B20 1-wire interface**

Run `sudo raspi-config`, go to **Interface Options → 1-Wire → Enable**, then reboot.
Alternatively, add the following line to `/boot/config.txt` and reboot:

```
dtoverlay=w1-gpio
```

After rebooting, plug in the DS18B20 and confirm the device appears:

```
ls /sys/bus/w1/devices/
```

You should see a folder named `28-xxxxxxxxxxxx`. Copy that ID into `config.json` (see
Configuration below).

**3. Create and activate a virtual environment**

The `--system-site-packages` flag gives access to any Pi system packages (e.g. picamera2)
that can't be pip-installed:

```
python3 -m venv venv --system-site-packages
source venv/bin/activate
```

**4. Install dependencies**

```
pip install -r requirements.txt
```

*(The file is currently empty — no packages to install. This step will matter once Flask is added.)*

---

## Configuration

Edit `config.json` to set the polling interval and configure your sensors:

```json
{
  "polling_interval": 30,
  "sensors": [
    {
      "id": "sim_temp_1",
      "name": "Simulated Temp 1",
      "type": "simulated_temperature",
      "alarm_min": 10.0,
      "alarm_max": 30.0,
      "sim_min": 15.0,
      "sim_max": 35.0
    },
    {
      "id": "ds18b20_1",
      "name": "Server Room Temp",
      "type": "ds18b20",
      "device_id": "28-000000000000",
      "alarm_min": 5.0,
      "alarm_max": 40.0
    }
  ]
}
```

| Field | Description |
|---|---|
| `polling_interval` | Seconds between sensor reads |
| `id` | Unique identifier for this sensor |
| `name` | Display name shown in output |
| `type` | `simulated_temperature` or `ds18b20` |
| `alarm_min` / `alarm_max` | Reading outside this range triggers an alarm |
| `sim_min` / `sim_max` | *(simulated only)* Range of randomly generated values |
| `device_id` | *(DS18B20 only)* Device folder name from `/sys/bus/w1/devices/` |

### On Windows

- Keep or add a `simulated_temperature` sensor for testing — it needs no hardware
- The DS18B20 entry will log a read error each cycle (expected; no `/sys/bus/w1/` path on Windows)
- Remove the DS18B20 entry if you don't want to see those errors

### On the Raspberry Pi

- Update the DS18B20 `device_id` to match the actual device found in `/sys/bus/w1/devices/`
- Remove or comment out the `simulated_temperature` sensor if not needed

---

## Running

With the virtual environment active, run from the project root:

```
python main.py
```

Example output:

```
Equipment Monitor started. Polling every 30s. Ctrl+C to stop.

[14:23:01] Simulated Temp 1: 31.4°C  [ALARM]
  → Email alert would be sent: Simulated Temp 1
[14:23:01] Server Room Temp: 22.1°C
[14:23:31] Simulated Temp 1: 27.8°C
[14:23:31] Server Room Temp: 22.3°C
```

Press **Ctrl+C** to stop.

**Notes:**
- `[ALARM]` appears when a reading is outside its configured `alarm_min`/`alarm_max` range
- `→ Email alert would be sent` prints when an alarm first triggers; it does not repeat while
  the alarm is sustained (actual email sending will be added in a future task)
- DS18B20 read errors on Windows are logged to the console and do not crash the application

---

## Project Structure

```
monitor_app1/
├── monitor/
│   ├── sensors/
│   │   ├── base.py          # BaseSensor ABC + SensorReading dataclass
│   │   ├── simulated.py     # SimulatedTemperatureSensor
│   │   └── ds18b20.py       # DS18B20Sensor (1-wire, Pi only)
│   ├── alarm_manager.py     # Alarm state tracking + email cooldown logic
│   └── sensor_manager.py    # Loads config, polls sensors, drives alarms
├── config.json              # Sensor list and polling interval
├── main.py                  # CLI entry point
├── requirements.txt         # Pi production dependencies
├── requirements-dev.txt     # Windows dev dependencies
└── REQUIREMENTS.md          # Full project requirements document
```

## License

TBD
