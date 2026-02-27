from __future__ import annotations

import csv
import functools
import io
import logging
import os
import re
from datetime import datetime

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
