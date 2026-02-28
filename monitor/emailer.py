from __future__ import annotations

import email.encoders
import logging
import os
import smtplib
from datetime import datetime
from email.mime.base import MIMEBase
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText

logger = logging.getLogger(__name__)


class Emailer:
    """Send alarm alert emails via SMTP (stdlib only — no extra dependencies)."""

    def __init__(self, config: dict):
        self._app_name = config.get("app_name", "Equipment Monitor")
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

    def send_test(self) -> tuple[bool, str]:
        """Send a plain test email. Returns (success, error_message)."""
        if not self._host or not self._to or not self._from:
            return False, "smtp_host, from_address, and to_address must all be set"

        msg = MIMEText(f"This is a test email from {self._app_name}.")
        msg["Subject"] = f"[{self._app_name}] Test Email"
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
            logger.info("Test email sent to %s", self._to)
            return True, ""
        except Exception as exc:
            logger.warning("Test email failed: %s", exc)
            return False, str(exc)

    def send_alert(
        self,
        sensor_name: str,
        reading,
        alarm_min=None,
        alarm_max=None,
        photo_path=None,
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
        photo_path : str | None
            Optional path to a JPEG to attach to the email.

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
        subject = f"[{self._app_name} ALARM] {sensor_name}: {value}{unit}"
        body = (
            f"Alarm triggered\n"
            f"\n"
            f"Sensor : {sensor_name}\n"
            f"ID     : {reading.sensor_id}\n"
            f"Value  : {value}{unit}\n"
            f"Time   : {ts}\n"
            f"Reason : {breach_desc}\n"
        )

        attach_photo = photo_path and os.path.isfile(photo_path)

        if attach_photo:
            msg = MIMEMultipart("mixed")
            msg.attach(MIMEText(body))
            with open(photo_path, "rb") as img_f:
                img_data = img_f.read()
            img_part = MIMEBase("image", "jpeg")
            img_part.set_payload(img_data)
            email.encoders.encode_base64(img_part)
            img_part.add_header(
                "Content-Disposition",
                f'attachment; filename="{os.path.basename(photo_path)}"',
            )
            msg.attach(img_part)
        else:
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
