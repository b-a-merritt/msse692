from normative_conformance.schemas.observation import ObservationRecord


class StorageUnavailable(RuntimeError):
    """A database operation failed; its active transaction must roll back."""


class InvalidModel(RuntimeError):
    """A stored model cannot be assessed, so the application must not start."""


class NotFound(LookupError):
    """An explicitly requested case or record does not exist."""


class ObservationExists(RuntimeError):
    """The case/observation identity already exists; no new work is requested."""


class NotReady(RuntimeError):
    """A required runtime resource is not available to process requests."""


class EnqueueFailed(RuntimeError):
    """Assessment could not be requested; an observation may already be committed."""

    def __init__(
        self,
        *,
        message: str,
        committed_observation: ObservationRecord | None = None,
    ) -> None:
        super().__init__(message)
        self.committed_observation = committed_observation
