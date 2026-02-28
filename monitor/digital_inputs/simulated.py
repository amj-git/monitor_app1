import random
import threading

from .base import BaseDigitalInput


class SimulatedDigitalInput(BaseDigitalInput):
    def __init__(self, input_id, name, active_state="high", sim_interval_seconds=90):
        super().__init__(input_id, name, active_state)
        self._interval = sim_interval_seconds
        self._stop = threading.Event()

    def start(self, callback):
        self._stop.clear()

        def _run():
            delay = random.uniform(self._interval * 0.5, self._interval * 1.5)
            while not self._stop.wait(delay):
                callback(self.input_id)
                delay = random.uniform(self._interval * 0.5, self._interval * 1.5)

        threading.Thread(target=_run, daemon=True,
                         name=f"simdi-{self.input_id}").start()

    def stop(self):
        self._stop.set()
