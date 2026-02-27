from __future__ import annotations

import logging
import smtplib
from datetime import datetime
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


class Emailer:
    """Send alarm alert emails via SMTP (stdlib only — no extra dependencies)."""

    def __init__(self, config: dict):
        self._enabled = config.get("enabled", False)
        self._host = config.get("smtp_host", "")
        self._port = config.get("smtp_port", 587)
        self._use_tls = config.get("use_tls", True)
        self._use_ssl = config.get("use_ssl", False)
        self._username = config.get("username", "")
        self._password = config.get("password", "")
        self._from = config.get("from_address", "")
        self._to = config.get("to_address", "")

    def is_enabled(self) -> bool:
        return self._enabled

    def send_alert(
        self,
        sensor_name: str,
        reading,
        alarm_min=None,
        alarm_max=None,
    ) -> bool:
        """
        Build and send an alarm alert email.

        Parameters
        ----------
        sensor_name : str
            Human-readable sensor name.
        reading : SensorReading
            The reading that triggered the alarm.
        alarm_min : float | None
            Configured minimum threshold (for breach description).
        alarm_max : float | None
            Configured maximum threshold (for breach description).

        Returns
        -------
        bool
            True on success, False if disabled / misconfigured / send failed.
        """
        if not self._enabled:
            return False

        if not self._host or not self._to or not self._from:
            logger.warning(
                "Emailer: smtp_host, from_address, and to_address must all be set"
            )
            return False

        # Determine which threshold was breached
        value = reading.value
        unit = reading.unit
        if alarm_max is not None and value > alarm_max:
            breach_desc = f"above maximum {alarm_max}{unit}"
        elif alarm_min is not None and value < alarm_min:
            breach_desc = f"below minimum {alarm_min}{unit}"
        else:
            breach_desc = "outside configured thresholds"

        ts = reading.timestamp.strftime("%Y-%m-%d %H:%M:%S")
        subject = f"[ALARM] {sensor_name}: {value}{unit}"
        body = (
            f"Alarm triggered\n"
            f"\n"
            f"Sensor : {sensor_name}\n"
            f"ID     : {reading.sensor_id}\n"
            f"Value  : {value}{unit}\n"
            f"Time   : {ts}\n"
            f"Reason : {breach_desc}\n"
        )

        msg = MIMEText(body)
        msg["Subject"] = subject
        msg["From"] = self._from
        msg["To"] = self._to

        try:
            if self._use_ssl:
                conn = smtplib.SMTP_SSL(self._host, self._port)
            else:
                conn = smtplib.SMTP(self._host, self._port)
                if self._use_tls:
                    conn.starttls()

            with conn:
                if self._username:
                    conn.login(self._username, self._password)
                conn.sendmail(self._from, [self._to], msg.as_string())

            logger.info("Alert email sent for sensor '%s'", sensor_name)
            return True

        except Exception as exc:
            logger.error("Failed to send alert email for sensor '%s': %s", sensor_name, exc)
            return False
