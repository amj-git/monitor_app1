from __future__ import annotations

import copy
import csv
import functools
import io
import json
import logging
import os
import re
import tempfile
from datetime import datetime

import markdown as md_lib
from markupsafe import Markup

from monitor.emailer import Emailer

from flask import (
    Blueprint,
    Response,
    abort,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
    send_from_directory,
    session,
    url_for,
)
from werkzeug.security import check_password_hash

logger = logging.getLogger(__name__)

bp = Blueprint("main", __name__)


def login_required(f):
    @functools.wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("logged_in"):
            return redirect(url_for("main.login"))
        return f(*args, **kwargs)
    return decorated


# ---------------------------------------------------------------------------
# Auth
# ---------------------------------------------------------------------------

@bp.route("/login", methods=["GET", "POST"])
def login():
    error = None
    if request.method == "POST":
        username = request.form.get("username", "")
        password = request.form.get("password", "")
        expected_user = current_app.config["AUTH_USERNAME"]
        password_hash = current_app.config["AUTH_PASSWORD_HASH"]
        if username == expected_user and check_password_hash(password_hash, password):
            session["logged_in"] = True
            return redirect(url_for("main.live"))
        else:
            logger.warning("Failed login attempt for user %r", username)
            error = "Invalid username or password."
    return render_template("login.html", error=error)


@bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("main.login"))


# ---------------------------------------------------------------------------
# Live view
# ---------------------------------------------------------------------------

@bp.route("/")
@login_required
def live():
    sensor_names = current_app.config["SENSOR_NAMES"]
    return render_template("live.html", sensor_names=sensor_names)


@bp.route("/api/live")
@login_required
def api_live():
    db = current_app.config["HISTORY_DB"]
    sensor_names = current_app.config["SENSOR_NAMES"]
    rows = db.get_latest_readings()
    for row in rows:
        row["name"] = sensor_names.get(row["sensor_id"], row["sensor_id"])
    return jsonify(rows)


_PHOTO_RE = re.compile(
    r'^photo_(\d{8}_\d{6})_([^_]+)(?:_(.+))?\.jpe?g$', re.IGNORECASE
)


def _parse_photo_name(filename):
    """Return dict with trigger/sensor_id/timestamp, or None if unrecognised."""
    m = _PHOTO_RE.match(filename)
    if not m:
        return None
    ts_str, trigger, sensor_id = m.group(1), m.group(2), m.group(3)
    try:
        ts = datetime.strptime(ts_str, "%Y%m%d_%H%M%S")
        timestamp = ts.strftime("%Y-%m-%d %H:%M:%S")
    except ValueError:
        timestamp = ts_str
    return {"trigger": trigger, "sensor_id": sensor_id or "", "timestamp": timestamp}


# ---------------------------------------------------------------------------
# History
# ---------------------------------------------------------------------------

@bp.route("/history")
@login_required
def history():
    sensor_names = current_app.config["SENSOR_NAMES"]
    return render_template("history.html", sensor_names=sensor_names)


def _history_params():
    sensor_id = request.args.get("sensor_id") or None
    start = request.args.get("start") or None
    end = request.args.get("end") or None
    return sensor_id, start, end


@bp.route("/api/history")
@login_required
def api_history():
    db = current_app.config["HISTORY_DB"]
    sensor_names = current_app.config["SENSOR_NAMES"]
    sensor_id, start, end = _history_params()
    rows = db.get_history(sensor_id=sensor_id, start=start, end=end)
    for row in rows:
        row["name"] = sensor_names.get(row["sensor_id"], row["sensor_id"])
    return jsonify(rows)


@bp.route("/api/history/csv")
@login_required
def api_history_csv():
    db = current_app.config["HISTORY_DB"]
    sensor_names = current_app.config["SENSOR_NAMES"]
    sensor_id, start, end = _history_params()
    rows = db.get_history(sensor_id=sensor_id, start=start, end=end)

    def generate():
        buf = io.StringIO()
        writer = csv.writer(buf)
        writer.writerow(["timestamp", "sensor_id", "name", "value", "unit", "alarming"])
        yield buf.getvalue()
        for row in rows:
            buf = io.StringIO()
            writer = csv.writer(buf)
            writer.writerow([
                row["timestamp"],
                row["sensor_id"],
                sensor_names.get(row["sensor_id"], row["sensor_id"]),
                row["value"],
                row["unit"],
                row["alarming"],
            ])
            yield buf.getvalue()

    return Response(
        generate(),
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=history.csv"},
    )


# ---------------------------------------------------------------------------
# Photos
# ---------------------------------------------------------------------------

@bp.route("/photos")
@login_required
def photos():
    return render_template("photos.html")


@bp.route("/api/photos")
@login_required
def api_photos():
    photo_dir = current_app.config["PHOTO_DIR"]
    result = []
    try:
        filenames = os.listdir(photo_dir)
    except OSError:
        return jsonify([])
    for filename in filenames:
        if not filename.lower().endswith((".jpg", ".jpeg")):
            continue
        filepath = os.path.join(photo_dir, filename)
        if not os.path.isfile(filepath):
            continue
        info = _parse_photo_name(filename)
        size_kb = round(os.path.getsize(filepath) / 1024, 1)
        result.append({
            "filename": filename,
            "trigger": info["trigger"] if info else "",
            "sensor_id": info["sensor_id"] if info else "",
            "timestamp": info["timestamp"] if info else "",
            "size_kb": size_kb,
            "url": url_for("main.photo_file", filename=filename),
            "download_url": url_for("main.photo_download", filename=filename),
        })
    result.sort(key=lambda p: p["filename"], reverse=True)
    return jsonify(result)


@bp.route("/photos/files/<filename>")
@login_required
def photo_file(filename):
    photo_dir = current_app.config["PHOTO_DIR"]
    if os.path.basename(filename) != filename or \
            not filename.lower().endswith((".jpg", ".jpeg")):
        abort(400)
    return send_from_directory(os.path.abspath(photo_dir), filename)


@bp.route("/photos/files/<filename>/download")
@login_required
def photo_download(filename):
    photo_dir = current_app.config["PHOTO_DIR"]
    if os.path.basename(filename) != filename or \
            not filename.lower().endswith((".jpg", ".jpeg")):
        abort(400)
    return send_from_directory(
        os.path.abspath(photo_dir), filename,
        as_attachment=True, download_name=filename,
    )


@bp.route("/api/photos/capture", methods=["POST"])
@login_required
def capture_photo():
    camera = current_app.config.get("CAMERA")
    if camera is None or not camera.is_enabled():
        return jsonify({"ok": False, "error": "Camera is not enabled"}), 503
    filepath = camera.capture(trigger="manual")
    if filepath is None:
        return jsonify({"ok": False, "error": "Capture failed"}), 500
    filename = os.path.basename(filepath)
    info = _parse_photo_name(filename)
    size_kb = round(os.path.getsize(filepath) / 1024, 1)
    photo = {
        "filename": filename,
        "trigger": info["trigger"] if info else "",
        "sensor_id": info["sensor_id"] if info else "",
        "timestamp": info["timestamp"] if info else "",
        "size_kb": size_kb,
        "url": url_for("main.photo_file", filename=filename),
        "download_url": url_for("main.photo_download", filename=filename),
    }
    logger.info("On-demand photo captured: %s", filepath)
    return jsonify({"ok": True, "photo": photo})


@bp.route("/api/photos/<filename>/delete", methods=["POST"])
@login_required
def delete_photo(filename):
    photo_dir = current_app.config["PHOTO_DIR"]
    safe = os.path.basename(filename)
    if safe != filename or not safe.lower().endswith((".jpg", ".jpeg")):
        return jsonify({"ok": False, "error": "invalid filename"}), 400
    filepath = os.path.join(photo_dir, safe)
    try:
        os.remove(filepath)
        logger.info("Deleted photo: %s", filepath)
        return jsonify({"ok": True})
    except OSError as exc:
        logger.error("Failed to delete photo %s: %s", filepath, exc)
        return jsonify({"ok": False, "error": str(exc)}), 500


# ---------------------------------------------------------------------------
# Settings
# ---------------------------------------------------------------------------

def _read_config():
    with open(current_app.config["CONFIG_PATH"]) as f:
        return json.load(f)


def _write_config(data):
    path = current_app.config["CONFIG_PATH"]
    dir_ = os.path.dirname(os.path.abspath(path))
    fd, tmp = tempfile.mkstemp(dir=dir_, suffix=".tmp")
    try:
        with os.fdopen(fd, "w") as f:
            json.dump(data, f, indent=2)
        os.replace(tmp, path)
    except Exception:
        os.unlink(tmp)
        raise


def _build_settings_response(cfg):
    sensors = []
    for s in cfg.get("sensors", []):
        sensors.append({
            "id": s.get("id", ""),
            "type": s.get("type", ""),
            "name": s.get("name", ""),
            "alarm_min": s.get("alarm_min"),
            "alarm_max": s.get("alarm_max"),
        })
    cam = cfg.get("camera", {})
    email_cfg = cfg.get("email", {})
    return {
        "app_name": cfg.get("app_name", "Equipment Monitor"),
        "polling_interval": cfg.get("polling_interval", 30),
        "max_db_size_mb": float(cfg.get("max_db_size_mb", 50.0)),
        "sensors": sensors,
        "camera": {
            "enabled": cam.get("enabled", False),
            "type": cam.get("type", "simulated"),
            "photo_dir": cam.get("photo_dir", "data/photos"),
            "periodic_interval_hours": float(cam.get("periodic_interval_hours", 6.0)),
            "max_photo_dir_size_mb": float(cam.get("max_photo_dir_size_mb", 100.0)),
        },
        "email": {
            "enabled": email_cfg.get("enabled", False),
            "smtp_host": email_cfg.get("smtp_host", ""),
            "smtp_port": int(email_cfg.get("smtp_port", 587)),
            "use_tls": email_cfg.get("use_tls", True),
            "use_ssl": email_cfg.get("use_ssl", False),
            "username": email_cfg.get("username", ""),
            "password": email_cfg.get("password", ""),
            "from_address": email_cfg.get("from_address", ""),
            "to_address": email_cfg.get("to_address", ""),
        },
    }


def _validate_settings(data):
    app_name = data.get("app_name", "")
    if not isinstance(app_name, str) or not app_name.strip():
        return "app_name must be a non-empty string"

    try:
        pi = int(data.get("polling_interval"))
        if not (5 <= pi <= 3600):
            return "polling_interval must be between 5 and 3600"
    except (TypeError, ValueError):
        return "polling_interval must be an integer between 5 and 3600"

    try:
        db_mb = float(data.get("max_db_size_mb", 0))
        if db_mb <= 0:
            return "max_db_size_mb must be > 0"
    except (TypeError, ValueError):
        return "max_db_size_mb must be a number"

    cam = data.get("camera", {})
    try:
        ph = float(cam.get("periodic_interval_hours", 0))
        if ph <= 0:
            return "camera.periodic_interval_hours must be > 0"
    except (TypeError, ValueError):
        return "camera.periodic_interval_hours must be a number"

    try:
        ms = float(cam.get("max_photo_dir_size_mb", 0))
        if ms <= 0:
            return "camera.max_photo_dir_size_mb must be > 0"
    except (TypeError, ValueError):
        return "camera.max_photo_dir_size_mb must be a number"

    email_cfg = data.get("email", {})
    try:
        port = int(email_cfg.get("smtp_port"))
        if not (1 <= port <= 65535):
            return "email.smtp_port must be between 1 and 65535"
    except (TypeError, ValueError):
        return "email.smtp_port must be an integer between 1 and 65535"

    for s in data.get("sensors", []):
        name = s.get("name", "")
        if not isinstance(name, str) or not name.strip():
            return "Sensor name must be a non-empty string"
        alarm_min = s.get("alarm_min")
        alarm_max = s.get("alarm_max")
        if alarm_min is not None and alarm_max is not None:
            try:
                if float(alarm_min) >= float(alarm_max):
                    return f"alarm_min must be less than alarm_max for sensor '{name}'"
            except (TypeError, ValueError):
                return f"alarm values must be numbers for sensor '{name}'"

    return None


def _merge_settings(full, data):
    merged = copy.deepcopy(full)
    merged["app_name"] = data["app_name"].strip()
    merged["polling_interval"] = int(data["polling_interval"])
    merged["max_db_size_mb"] = float(data["max_db_size_mb"])

    sensors_by_id = {s.get("id"): s for s in data.get("sensors", [])}
    for s in merged.get("sensors", []):
        sid = s.get("id")
        if sid in sensors_by_id:
            patch = sensors_by_id[sid]
            s["name"] = patch["name"]
            for key in ("alarm_min", "alarm_max"):
                if key in patch:
                    val = patch[key]
                    s[key] = float(val) if val is not None else None

    cam_data = data.get("camera", {})
    cam = merged.setdefault("camera", {})
    cam["enabled"] = bool(cam_data.get("enabled", False))
    cam["periodic_interval_hours"] = float(cam_data.get("periodic_interval_hours", 6.0))
    cam["max_photo_dir_size_mb"] = float(cam_data.get("max_photo_dir_size_mb", 100.0))

    email_data = data.get("email", {})
    email = merged.setdefault("email", {})
    email["enabled"] = bool(email_data.get("enabled", False))
    email["smtp_host"] = email_data.get("smtp_host", "")
    email["smtp_port"] = int(email_data.get("smtp_port", 587))
    email["use_tls"] = bool(email_data.get("use_tls", True))
    email["use_ssl"] = bool(email_data.get("use_ssl", False))
    email["username"] = email_data.get("username", "")
    email["password"] = email_data.get("password", "")
    email["from_address"] = email_data.get("from_address", "")
    email["to_address"] = email_data.get("to_address", "")

    return merged


def _apply_settings(data):
    current_app.config["APP_NAME"] = data["app_name"].strip()

    manager = current_app.config.get("SENSOR_MANAGER")
    emailer = current_app.config.get("EMAILER")
    camera = current_app.config.get("CAMERA")

    if manager is not None:
        manager.polling_interval = int(data["polling_interval"])
        manager._db._max_bytes = float(data["max_db_size_mb"]) * 1024 * 1024

        sensors_by_id = {s.get("id"): s for s in data.get("sensors", [])}
        for sensor in manager._sensors:
            sid = sensor.sensor_id
            if sid in sensors_by_id:
                patch = sensors_by_id[sid]
                sensor.name = patch["name"]
                sensor.alarm_min = patch.get("alarm_min")
                sensor.alarm_max = patch.get("alarm_max")
                current_app.config["SENSOR_NAMES"][sid] = patch["name"]

    if camera is not None:
        cam_data = data.get("camera", {})
        camera._enabled = bool(cam_data.get("enabled", False))
        camera._periodic_hours = float(cam_data.get("periodic_interval_hours", 6.0))
        camera._max_size_mb = float(cam_data.get("max_photo_dir_size_mb", 100.0))

    if emailer is not None:
        emailer._app_name = data["app_name"].strip()
        email_data = data.get("email", {})
        emailer._enabled = bool(email_data.get("enabled", False))
        emailer._host = email_data.get("smtp_host", "")
        emailer._port = int(email_data.get("smtp_port", 587))
        emailer._use_tls = bool(email_data.get("use_tls", True))
        emailer._use_ssl = bool(email_data.get("use_ssl", False))
        emailer._username = email_data.get("username", "")
        emailer._password = email_data.get("password", "")
        emailer._from = email_data.get("from_address", "")
        emailer._to = email_data.get("to_address", "")


@bp.route("/help")
@login_required
def help():
    readme_path = os.path.normpath(
        os.path.join(current_app.root_path, "..", "..", "README.md")
    )
    try:
        with open(readme_path, encoding="utf-8") as f:
            raw = f.read()
        content = Markup(md_lib.markdown(raw, extensions=["fenced_code", "tables"]))
    except OSError:
        content = Markup("<p>README.md not found.</p>")
    return render_template("help.html", content=content)


@bp.route("/settings")
@login_required
def settings():
    return render_template("settings.html")


@bp.route("/api/settings")
@login_required
def api_settings_get():
    cfg = _read_config()
    return jsonify(_build_settings_response(cfg))


@bp.route("/api/settings", methods=["POST"])
@login_required
def api_settings_post():
    data = request.get_json(force=True)
    err = _validate_settings(data)
    if err:
        return jsonify({"ok": False, "error": err}), 400
    full = _read_config()
    merged = _merge_settings(full, data)
    _write_config(merged)
    _apply_settings(data)
    logger.info("Settings updated via web UI")
    return jsonify({"ok": True})


@bp.route("/api/settings/test-email", methods=["POST"])
@login_required
def api_settings_test_email():
    data = request.get_json(force=True)
    email_data = data.get("email", {})
    test_emailer = Emailer({
        "app_name":     current_app.config.get("APP_NAME", "Equipment Monitor"),
        "enabled": True,
        "smtp_host":    email_data.get("smtp_host", ""),
        "smtp_port":    email_data.get("smtp_port", 587),
        "use_tls":      email_data.get("use_tls", True),
        "use_ssl":      email_data.get("use_ssl", False),
        "username":     email_data.get("username", ""),
        "password":     email_data.get("password", ""),
        "from_address": email_data.get("from_address", ""),
        "to_address":   email_data.get("to_address", ""),
    })
    ok, err = test_emailer.send_test()
    if ok:
        return jsonify({"ok": True})
    return jsonify({"ok": False, "error": err}), 500
