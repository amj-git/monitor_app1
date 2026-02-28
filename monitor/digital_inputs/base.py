from abc import ABC, abstractmethod


class BaseDigitalInput(ABC):
    def __init__(self, input_id: str, name: str, active_state: str = "high"):
        self.input_id = input_id
        self.name = name
        self.active_state = active_state  # "high" or "low"

    @abstractmethod
    def start(self, callback) -> None:
        """Start monitoring. callback(input_id) called on each activation event."""

    @abstractmethod
    def stop(self) -> None:
        """Stop monitoring and release resources."""
