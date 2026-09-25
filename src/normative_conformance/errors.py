class StorageUnavailable(RuntimeError):
    """A database operation failed; its active transaction must roll back."""


class NotFound(LookupError):
    """An explicitly requested case or record does not exist."""


class ObservationExists(RuntimeError):
    """The case/observation identity already exists; no new work is requested."""


class NotReady(RuntimeError):
    """A required runtime resource has not been initialized."""
