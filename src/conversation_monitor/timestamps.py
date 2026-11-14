from datetime import UTC
from datetime import datetime
from datetime import timedelta


def to_microseconds(*, value: datetime) -> int:
    return (value - datetime(1970, 1, 1, tzinfo=UTC)) // timedelta(microseconds=1)


def utc_now() -> datetime:
    return datetime.now(UTC)


def from_microseconds(*, value: int) -> datetime:
    return datetime(1970, 1, 1, tzinfo=UTC) + timedelta(microseconds=value)
