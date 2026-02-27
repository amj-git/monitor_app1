from __future__ import annotations

import csv
import functools
import io
import logging

from flask import (
    Blueprint,
    Response,
    current_app,
    jsonify,
    redirect,
    render_template,
    request,
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
