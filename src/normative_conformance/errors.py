from typing import Literal

ComponentName = Literal["models", "database", "queue", "scheduler", "worker"]

class ModelValidationError(ValueError):
    """Invalid or conflicting model content prevents startup."""


class StorageUnavailable(RuntimeError):
    """A database operation failed; its active transaction must roll back."""


class NotFound(LookupError):
    """An explicitly requested case or record does not exist."""


class ObservationExists(RuntimeError):
    """The case/observation identity already exists; no new work is requested."""


class QueueUnavailable(RuntimeError):
    """The queue could not durably accept a task."""


class NotReady(RuntimeError):
    """Required components are unavailable; reject mutations before they start."""

    def __init__(self, components: tuple[ComponentName, ...]) -> None:
        super().__init__("Required runtime components are unavailable.")
        self.components = components
