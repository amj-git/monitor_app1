# Equipment Monitor

A Raspberry Pi sensor monitoring application. Polls temperature sensors on a configurable
interval, tracks alarm states, persists readings to SQLite, and serves a web GUI for live
monitoring and history browsing.

---

## Requirements

- Python 3.7 or later
- Flask 2.2 (installed via `requirements.txt` / `requirements-dev.txt`)

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

---

## Configuration

Edit `config.json` to configure sensors and the web GUI:

```json
{
  "polling_interval": 30,
  "db_path": "data/sensor_history.db",
  "max_db_size_mb": 50.0,
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
  ],
  "web": {
    "host": "0.0.0.0",
    "port": 5000,
    "secret_key": "change-me-in-production",
    "username": "admin",
    "password_hash": "<generated — see Changing the password below>"
  }
}
```

### Sensor fields

| Field | Description |
|---|---|
| `polling_interval` | Seconds between sensor reads |
| `db_path` | Path to the SQLite history database |
| `max_db_size_mb` | Old rows are trimmed when the DB exceeds this size |
| `id` | Unique identifier for this sensor |
| `name` | Display name shown in the web GUI and console output |
| `type` | `simulated_temperature` or `ds18b20` |
| `alarm_min` / `alarm_max` | Reading outside this range triggers an alarm |
| `sim_min` / `sim_max` | *(simulated only)* Range of randomly generated values |
| `device_id` | *(DS18B20 only)* Device folder name from `/sys/bus/w1/devices/` |

### Web fields

| Field | Description |
|---|---|
| `host` | Interface to bind (`0.0.0.0` = all interfaces, `127.0.0.1` = localhost only) |
| `port` | TCP port for the web server (default 5000) |
| `secret_key` | Flask session secret — change this before exposing to a network |
| `username` | Login username |
| `password_hash` | Werkzeug password hash — see *Changing the password* below |

### On Windows

- Keep or add a `simulated_temperature` sensor for testing — it needs no hardware
- The DS18B20 entry will log a read error each cycle (expected; no `/sys/bus/w1/` path on Windows)
- Remove the DS18B20 entry if you don't want to see those errors

### On the Raspberry Pi

- Update the DS18B20 `device_id` to match the actual device found in `/sys/bus/w1/devices/`
- Remove or comment out the `simulated_temperature` sensor if not needed
- Set `host` to `"0.0.0.0"` so the GUI is accessible from other devices on the LAN

---

## Running

With the virtual environment active, run from the project root:

```
python main.py
```

Expected startup output:

```
INFO monitor.history_db: HistoryDB opened: data/sensor_history.db
Web GUI running at http://0.0.0.0:5000/
Equipment Monitor started. Polling every 30s. Ctrl+C to stop.

[14:23:01] Simulated Temp 1: 31.4°C  [ALARM]
  -> Email alert would be sent: Simulated Temp 1
[14:23:01] Server Room Temp: 22.1°C
```

Press **Ctrl+C** to stop. The web server shuts down automatically when the main process exits.

**Console output notes:**
- `[ALARM]` appears when a reading is outside its configured `alarm_min`/`alarm_max` range
- `-> Email alert would be sent` prints when an alarm first triggers; it does not repeat while
  the alarm is sustained. When email is configured and `enabled: true`, an SMTP alert is also sent.
- DS18B20 read errors on Windows are logged to the console and do not crash the application

---

## Web GUI

Open a browser and navigate to `http://localhost:5000/` (or replace `localhost` with the
Pi's IP address when accessing from another machine).

### Logging in

You will be redirected to the login page. Enter the credentials configured in `config.json`.
The default credentials are:

| Field | Value |
|---|---|
| Username | `admin` |
| Password | `admin` |

After a successful login you are taken to the Live view. Failed attempts are logged to the
console.

### Live view (`/`)

Displays the most recent reading from every sensor in a table, refreshed automatically
every 5 seconds without reloading the page.

| Column | Description |
|---|---|
| Sensor | Display name from `config.json` |
| ID | Internal sensor ID |
| Value | Most recent reading |
| Unit | Unit of measurement (e.g. `°C`) |
| Status | `OK` or `ALARM` |
| Timestamp | ISO-8601 time of the reading |

Rows with an active alarm are highlighted in red.

### History browser (`/history`)

Browse and filter the full reading history stored in SQLite.

1. Optionally select a specific sensor from the **Sensor** drop-down (leave blank for all sensors)
2. Optionally set **From** and **To** datetime filters
3. Click **Filter** — up to 2000 rows are returned, sorted newest first
4. Click **Download CSV** to download the same result set as a CSV file

The CSV contains columns: `timestamp`, `sensor_id`, `name`, `value`, `unit`, `alarming`.

### Logging out

Click **Logout** in the navigation bar. You are returned to the login page and the session
is cleared.

---

## Changing the password

Generate a new hash from the command line (with the virtual environment active):

```
python -c "from werkzeug.security import generate_password_hash; print(generate_password_hash('your-new-password'))"
```

Paste the output string into `config.json` as the value of `"password_hash"`, then restart
`main.py`.

---

## Email Alerts

The app can send an email when a sensor first breaches its alarm threshold. A
**1-day cooldown** prevents repeated emails while the alarm is sustained: once
the sensor returns to normal and re-triggers, the next alert is sent immediately.

### What triggers an alert

1. A sensor reading falls outside its `alarm_min` / `alarm_max` range for the
   first time (or after a 1-day cooldown since the last alert).
2. `alarm_manager.py` signals `main.py` that an email should go out.
3. `main.py` calls `Emailer.send_alert()` with the sensor name, reading, and
   threshold values.

### SMTP configuration

Add (or edit) the `"email"` block in `config.json`:

```json
"email": {
  "enabled": false,
  "smtp_host": "smtp.gmail.com",
  "smtp_port": 587,
  "use_tls": true,
  "use_ssl": false,
  "username": "",
  "password": "",
  "from_address": "",
  "to_address": ""
}
```

| Field | Type | Default | Description |
|---|---|---|---|
| `enabled` | bool | `false` | Master on/off switch — set to `true` to activate |
| `smtp_host` | string | `""` | SMTP server hostname |
| `smtp_port` | int | `587` | SMTP port (587 = STARTTLS, 465 = SSL) |
| `use_tls` | bool | `true` | Call STARTTLS after connecting (standard for port 587) |
| `use_ssl` | bool | `false` | Wrap connection in SSL from the start (for port 465) |
| `username` | string | `""` | SMTP login username; leave empty to skip authentication |
| `password` | string | `""` | SMTP login password |
| `from_address` | string | `""` | `From:` address in the email |
| `to_address` | string | `""` | Recipient address |

### Gmail example

Gmail requires an **App Password** when 2-Step Verification is enabled on the
sending account. Generate one at
`https://myaccount.google.com/apppasswords` and use it as `"password"`.

```json
"email": {
  "enabled": true,
  "smtp_host": "smtp.gmail.com",
  "smtp_port": 587,
  "use_tls": true,
  "use_ssl": false,
  "username": "your.address@gmail.com",
  "password": "xxxx xxxx xxxx xxxx",
  "from_address": "your.address@gmail.com",
  "to_address": "recipient@example.com"
}
```

### Generic SMTP example (port 465 / SSL)

```json
"email": {
  "enabled": true,
  "smtp_host": "mail.example.com",
  "smtp_port": 465,
  "use_tls": false,
  "use_ssl": true,
  "username": "alerts@example.com",
  "password": "secret",
  "from_address": "alerts@example.com",
  "to_address": "admin@example.com"
}
```

### Enabling email alerts

1. Fill in all required fields (`smtp_host`, `from_address`, `to_address`, credentials).
2. Set `"enabled": true`.
3. Restart `main.py`.

When `enabled` is `false` (the default), the app runs normally and prints
`-> Email alert would be sent: <sensor>` to the console instead of sending mail.

---

## Project Structure

```
monitor_app1/
├── monitor/
│   ├── sensors/
│   │   ├── base.py              # BaseSensor ABC + SensorReading dataclass
│   │   ├── simulated.py         # SimulatedTemperatureSensor
│   │   └── ds18b20.py           # DS18B20Sensor (1-wire, Pi only)
│   ├── web/
│   │   ├── __init__.py          # Flask app factory (create_app)
│   │   ├── routes.py            # Route handlers and login_required decorator
│   │   ├── templates/
│   │   │   ├── base.html        # Shared layout and nav bar
│   │   │   ├── login.html       # Login form
│   │   │   ├── live.html        # Live sensor table (JS auto-refresh)
│   │   │   └── history.html     # History filter form + table + CSV link
│   │   └── static/
│   │       └── style.css        # Minimal stylesheet, no CDN
│   ├── alarm_manager.py         # Alarm state tracking + email cooldown logic
│   ├── emailer.py               # SMTP email delivery (stdlib only)
│   ├── history_db.py            # SQLite persistence (WAL mode)
│   └── sensor_manager.py        # Loads config, polls sensors, drives alarms
├── data/
│   └── sensor_history.db        # SQLite database (git-ignored)
├── config.json                  # Sensor list, polling interval, web settings
├── main.py                      # Entry point; starts Flask thread then poll loop
├── requirements.txt             # Pi production dependencies
├── requirements-dev.txt         # Windows dev dependencies
└── REQUIREMENTS.md              # Full project requirements document
```

## License

TBD
