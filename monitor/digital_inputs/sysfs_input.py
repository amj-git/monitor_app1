import logging
import os
import select
import threading
import time

from .base import BaseDigitalInput

logger = logging.getLogger(__name__)
_SYSFS_GPIO = "/sys/class/gpio"


class SysfsDigitalInput(BaseDigitalInput):
    """
    GPIO edge-detection via the Linux kernel sysfs interface.

    No external library required — works on all Raspberry Pi hardware,
    including Pi 1 B+ where newer RPi.GPIO versions are incompatible.

    Pull-up / pull-down resistors are NOT configurable via sysfs.
    Set them in /boot/config.txt using the gpio DT parameter, e.g.:

        gpio=17=ip,pd    # pin 17, input, pull-down
        gpio=17=ip,pu    # pin 17, input, pull-up

    or use an external resistor on the PCB.
    """

    def __init__(self, input_id, name, gpio_pin, active_state="high"):
        super().__init__(input_id, name, active_state)
        self._pin = gpio_pin
        self._stop = threading.Event()

    def _path(self, attr):
        return os.path.join(_SYSFS_GPIO, f"gpio{self._pin}", attr)

    def _export(self):
        gpio_dir = os.path.join(_SYSFS_GPIO, f"gpio{self._pin}")
        if not os.path.exists(gpio_dir):
            with open(os.path.join(_SYSFS_GPIO, "export"), "w") as f:
                f.write(str(self._pin))
            # Give the kernel a moment to create the sysfs entries
            time.sleep(0.1)

    def _unexport(self):
        gpio_dir = os.path.join(_SYSFS_GPIO, f"gpio{self._pin}")
        if os.path.exists(gpio_dir):
            try:
                with open(os.path.join(_SYSFS_GPIO, "unexport"), "w") as f:
                    f.write(str(self._pin))
            except Exception:
                pass

    def start(self, callback):
        self._stop.clear()
        self._export()

        with open(self._path("direction"), "w") as f:
            f.write("in")

        edge = "rising" if self.active_state == "high" else "falling"
        with open(self._path("edge"), "w") as f:
            f.write(edge)

        def _run():
            try:
                with open(self._path("value"), "rb") as vf:
                    vf.read()  # clear any pending interrupt on open
                    while not self._stop.is_set():
                        # Passing vf in the "exceptional" set maps to POLLPRI
                        # on Linux, which fires on GPIO edge interrupts.
                        _, _, x = select.select([], [], [vf], 1.0)
                        if x and not self._stop.is_set():
                            vf.seek(0)
                            vf.read()  # acknowledge the interrupt
                            callback(self.input_id)
            except Exception as exc:
                logger.error("Sysfs GPIO thread error for pin %d: %s",
                             self._pin, exc)

        threading.Thread(target=_run, daemon=True,
                         name=f"sysfs-{self.input_id}").start()

    def stop(self):
        self._stop.set()
        self._unexport()
