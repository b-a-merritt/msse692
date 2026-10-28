from datetime import UTC
from datetime import datetime
from datetime import timedelta
from datetime import timezone

import pytest

from normative_conformance.timestamps import from_microseconds
from normative_conformance.timestamps import to_microseconds
from normative_conformance.timestamps import utc_now


@pytest.mark.parametrize(
    "value,microseconds",
    [
        (datetime(1970, 1, 1, tzinfo=UTC), 0),
        (datetime(1969, 12, 31, 23, 59, 59, 999999, tzinfo=UTC), -1),
        (datetime(1970, 1, 1, 3, 0, 0, 1, tzinfo=timezone(timedelta(hours=3))), 1),
        (datetime(9999, 12, 31, 23, 59, 59, 999999, tzinfo=UTC), 253402300799999999),
    ],
)
def test_signed_microseconds_round_trip_without_float_rounding(*, value, microseconds):
    assert to_microseconds(value=value) == microseconds
    assert from_microseconds(value=microseconds) == value.astimezone(UTC)


def test_runtime_clock_is_timezone_aware_utc():
    assert utc_now().tzinfo is UTC
