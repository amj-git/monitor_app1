try:
    import RPi.GPIO as GPIO
    _GPIO_AVAILABLE = True
except Exception:
    # Catches ImportError (GPIO not installed) and errors raised during import
    # on unsupported hardware (e.g. NotImplementedError on Pi 1 B+ with some
    # RPi.GPIO versions that don't recognise old-style revision codes).
    _GPIO_AVAILABLE = False

from .base import BaseDigitalInput


class GPIODigitalInput(BaseDigitalInput):
    def __init__(self, input_id, name, gpio_pin, active_state="high", pull="down"):
        super().__init__(input_id, name, active_state)
        self._pin = gpio_pin
        self._pull = pull  # "up", "down", or "none"

    def start(self, callback):
        if not _GPIO_AVAILABLE:
            raise RuntimeError(
                "RPi.GPIO unavailable (not installed, or failed to load on this hardware) "
                "— use type 'simulated' for development"
            )
        pull_map = {"up": GPIO.PUD_UP, "down": GPIO.PUD_DOWN, "none": GPIO.PUD_OFF}
        pud = pull_map.get(self._pull, GPIO.PUD_DOWN)
        GPIO.setmode(GPIO.BCM)
        GPIO.setup(self._pin, GPIO.IN, pull_up_down=pud)
        edge = GPIO.RISING if self.active_state == "high" else GPIO.FALLING
        GPIO.add_event_detect(
            self._pin, edge,
            callback=lambda ch: callback(self.input_id),
            bouncetime=200,
        )

    def stop(self):
        if _GPIO_AVAILABLE:
            try:
                GPIO.remove_event_detect(self._pin)
                GPIO.cleanup(self._pin)
            except Exception:
                pass
