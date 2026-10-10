from datetime import datetime
from datetime import timedelta
from datetime import timezone

import pytest

from normative_conformance.timestamps import from_microseconds
from normative_conformance.timestamps import to_microseconds


@pytest.mark.parametrize(
    "value,microseconds",
    [
        (datetime(1970, 1, 1, tzinfo=timezone.utc), 0),
        (datetime(1969, 12, 31, 23, 59, 59, 999999, tzinfo=timezone.utc), -1),
        (datetime(1970, 1, 1, 3, 0, 0, 1, tzinfo=timezone(timedelta(hours=3))), 1),
        (datetime(9999, 12, 31, 23, 59, 59, 999999, tzinfo=timezone.utc), 253402300799999999),
    ],
)
def test_signed_microseconds_round_trip_without_float_rounding(*, value, microseconds):
    assert to_microseconds(value=value) == microseconds
    assert from_microseconds(value=microseconds) == value.astimezone(timezone.utc)
