from abc import ABC, abstractmethod


class BaseCamera(ABC):
    @abstractmethod
    def capture(self, filepath: str) -> bool:
        """Save a JPEG to filepath. Returns True on success."""

    def close(self) -> None:
        pass
