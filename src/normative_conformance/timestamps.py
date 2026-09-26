from datetime import datetime
from datetime import timedelta
from datetime import timezone


def to_microseconds(*, value: datetime) -> int:
    return (value - datetime(1970, 1, 1, tzinfo=timezone.utc)) // timedelta(microseconds=1)


def from_microseconds(*, value: int) -> datetime:
    return datetime(1970, 1, 1, tzinfo=timezone.utc) + timedelta(microseconds=value)
