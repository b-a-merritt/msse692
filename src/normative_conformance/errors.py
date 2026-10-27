from normative_conformance.schemas.capture import CaptureErrorCode


class StorageUnavailable(RuntimeError):
    """A database operation failed; its active transaction must roll back."""


class NotFound(LookupError):
    """An explicitly requested case or record does not exist."""


class ObservationExists(RuntimeError):
    """The case/observation identity already exists; no new work is requested."""


class NotReady(RuntimeError):
    """A required runtime resource is not available to process requests."""


class CaptureFailure(RuntimeError):
    """Capture ended early; the code selects fixed browser text."""

    def __init__(self, code: CaptureErrorCode) -> None:
        super().__init__(code)
        self.code = code


class CaptureDisconnected(RuntimeError):
    """The browser left before capture completed; nothing can be reported to it."""
