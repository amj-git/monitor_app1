from __future__ import annotations

from datetime import datetime, timedelta

ALARM_COOLDOWN = timedelta(days=1)


class AlarmManager:
    """
    Tracks per-sensor alarm state and decides when to trigger an email.

    Rules:
    - Alarm clears (alarming=False)  → clear in_alarm flag, no email
    - Alarm sustained (already in_alarm) → no email (already sent)
    - Alarm newly triggered → send email only if last_email is None
      OR (now - last_email) >= 1 day; update last_email on send
    """

    def __init__(self):
        # {sensor_id: {'in_alarm': bool, 'last_email': datetime | None}}
        self._state: dict[str, dict] = {}

    def _get(self, sensor_id: str) -> dict:
        if sensor_id not in self._state:
            self._state[sensor_id] = {"in_alarm": False, "last_email": None}
        return self._state[sensor_id]

    def update(self, sensor_id: str, alarming: bool) -> bool:
        """
        Update alarm state for a sensor.
        Returns True if an email should be sent.
        """
        state = self._get(sensor_id)

        if not alarming:
            state["in_alarm"] = False
            return False

        # Alarm is active
        if state["in_alarm"]:
            # Already in alarm — no repeat email
            return False

        # Newly triggered alarm
        state["in_alarm"] = True
        now = datetime.now()
        if state["last_email"] is None or (now - state["last_email"]) >= ALARM_COOLDOWN:
            state["last_email"] = now
            return True

        return False
