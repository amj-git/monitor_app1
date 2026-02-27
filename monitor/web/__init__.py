from __future__ import annotations

from flask import Flask

from .routes import bp


def create_app(config: dict) -> Flask:
    """Flask app factory.

    config keys:
        secret_key     — Flask session secret
        username       — login username
        password_hash  — werkzeug password hash
        db             — shared HistoryDB instance
        sensor_names   — dict[sensor_id, display_name]
    """
    app = Flask(__name__, template_folder="templates", static_folder="static")
    app.secret_key = config["secret_key"]
    app.config["AUTH_USERNAME"] = config["username"]
    app.config["AUTH_PASSWORD_HASH"] = config["password_hash"]
    app.config["HISTORY_DB"] = config["db"]
    app.config["SENSOR_NAMES"] = config.get("sensor_names", {})
    app.config["PHOTO_DIR"] = config.get("photo_dir", "data/photos")
    app.config["CAMERA"] = config.get("camera")
    app.register_blueprint(bp)
    return app
