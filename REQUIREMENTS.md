# Equipment Monitor – Requirements Document

> **Status:** Living document. Decisions marked TBD are to be resolved in future sessions.
> **Last updated:** 2026-02-27

---

## 1. Overview

| Field    | Value                                                        |
|----------|--------------------------------------------------------------|
| App name | Equipment Monitor                                            |
| Purpose  | Monitor sensors, capture photos, provide web-based control and history |
| Language | Python 3                                                     |
| Target   | Raspberry Pi 1 B+ (or better)                               |

---

## 2. Platform & Environment

- **Hardware:** Raspberry Pi 1 B+ minimum (single-core ARM11 700 MHz, 512 MB RAM)
- **OS:** Raspberry Pi OS (Linux)
- **Language:** Python 3
- Must be resource-conscious given Pi 1 B+ constraints (low CPU and RAM footprint)

### 2.1 Development Environment

| Environment | Setup |
|---|---|
| Windows PC (dev) | `python -m venv venv` → `venv\Scripts\activate` → `pip install -r requirements-dev.txt` |
| Raspberry Pi | `python3 -m venv venv --system-site-packages` → `source venv/bin/activate` → `apt` for compiled libs → `pip install -r requirements.txt` |

**Library strategy:**
- `requirements.txt` — Pi production dependencies
- `requirements-dev.txt` — Windows dev dependencies (excludes Pi-only libs)
- Pi-only libraries (RPi.GPIO, picamera2) are wrapped with `try/except ImportError` so the app imports cleanly on Windows; sensors/subsystems that need them raise a clear error if called without the library
- The sensor framework uses stdlib only — no pip installs needed to run with simulated sensors

---

## 3. Core Application Architecture

- Runs as a background service / daemon
- Continuous sensor polling loop
- Lightweight web server for GUI (e.g. Flask)
- Camera capture subsystem
- Email alert subsystem

---

## 4. Sensor Monitoring

### 4.1 General

- Maximum of **10 sensors** in total (any mix of types)
- Sensor configuration stored in settings — sensors can be added or removed without code changes

### 4.2 Temperature Sensors

- **DS18B20** (1-wire) confirmed as the first real sensor type
  - Reads from `/sys/bus/w1/devices/{device_id}/w1_slave` on Pi
  - Requires `w1-gpio` and `w1-therm` kernel modules (via `raspi-config` or `/boot/config.txt`)
  - Additional sensor types (DHT11, DHT22, etc.) are TBD
- **Simulated temperature sensor** available for Windows development and testing (no hardware required)
- Individual sensors added/removed via configuration (`config.json`)
- Each sensor assigned a user-defined name

### 4.3 Digital Input Sensors

- Monitored via Raspberry Pi GPIO pins
- Each digital input is:
  - Named by the user
  - Assigned a specific GPIO pin
  - Configured as active-high or active-low
- Individual inputs added/removed via configuration

### 4.4 Sensor Reading & History

- Sensor values polled at a **configurable interval** (default: 30 seconds)
- All readings saved to persistent storage (SQLite database)
- Live readings viewable in the Web GUI

---

## 5. Data Storage

### 5.1 Sensor History Database

- **SQLite** database stored locally on the Pi
- Each record: timestamp, sensor ID, value
- Retained indefinitely unless trimmed

### 5.2 Data Management

- Configurable maximum database size or age threshold (default: **50 MB**)
- Oldest records trimmed automatically when limit is reached
- Trim controls also available in the Web GUI settings

---

## 6. Camera & Photo Capture

### 6.1 Hardware

- Raspberry Pi Camera Module (CSI interface)
- **Still photographs only** — no streaming video

### 6.2 Capture Triggers

Three trigger modes (all configurable):

| Mode       | Description                                                    |
|------------|----------------------------------------------------------------|
| On demand  | Triggered manually via "Capture Now" button on the Photos page |
| Periodic   | Captured on a regular time interval (default: **6 hours**)     |
| Alarm      | Triggered automatically when a sensor alarm threshold is breached |

### 6.3 Photo Storage

- Photos saved to a designated folder on the Pi filesystem
- Filename includes a timestamp for chronological ordering

### 6.4 Photo Management

- Configurable maximum photo folder size (default: **100 MB**)
- Oldest photos automatically deleted when limit is reached
- Manual deletion available in the Web GUI

---

## 7. Web GUI

### 7.1 Authentication

- Username and password login required
- **Single user account** (minimum)
- Session maintained after login

### 7.2 Live Sensor View

- Displays current reading of all configured sensors
- Auto-refreshes without full page reload
- Indicates alarm state visually

### 7.3 Settings

Configurable items available in the settings area:

- Add / remove / rename sensors
- Configure sensor GPIO pins and active-high/low for digital inputs
- Sensor polling interval
- Alarm thresholds per sensor
- Camera capture intervals and trigger modes
- Database and photo storage size limits
- Email alert settings (SMTP server, port, credentials, recipient address)

### 7.4 History Browser

- Browse sensor reading history with date/time filtering
- Download history data (e.g. CSV export)

### 7.5 Photo Browser

- View captured photos in the GUI
- Download individual photos
- Delete photos

---

## 8. Alerting & Notifications

- Email sent when a sensor reading breaches a configured alarm threshold
- Email includes:
  - Sensor name
  - Reading value
  - Timestamp
  - Latest captured photograph (if available)
- **SMTP-based** email (configurable server, port, credentials, recipient)
- Cooldown/de-bounce rules:
  - An alarm email is sent when a sensor first breaches its threshold
  - No further email is sent while the alarm is sustained (already-notified state)
  - If the alarm clears and then re-triggers, a new email is sent only if at least **1 day** has elapsed since the last email for that sensor
  - No "all clear" email is sent when an alarm clears

---

## 9. Non-Functional Requirements

- Operates within Pi 1 B+ resource limits (low CPU and RAM footprint)
- Web server accessible on the local network (no internet exposure required)
- All configuration persisted across restarts
- Application recovers gracefully from sensor read errors without crashing

---

## 10. Decided Defaults

| Setting                      | Default value                            |
|------------------------------|------------------------------------------|
| User accounts                | Single user account only                 |
| Sensor polling interval      | 30 seconds                               |
| Periodic photo capture interval | 6 hours                               |
| Maximum photo folder size    | 100 MB (oldest photos deleted when exceeded) |
| Maximum sensor database size | 50 MB (oldest records trimmed when exceeded) |
| Alarm email cooldown         | 1 day (fault must clear and re-occur before another email is sent) |

---

## 11. Open Items (TBD)

| # | Item                                                                   |
|---|------------------------------------------------------------------------|
| 1 | Specific temperature sensor types beyond DS18B20 (DHT11, DHT22, etc.) |
