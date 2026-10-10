import sqlite3
from pathlib import Path
from unittest.mock import Mock

import pytest
from persistqueue.serializers import json

from normative_conformance import queue
from normative_conformance.errors import StorageUnavailable


def test_queue_is_configured_for_shared_durable_requests(*, monkeypatch):
    constructor = Mock()
    monkeypatch.setattr(queue, "SQLiteAckQueue", constructor)
    assert queue.create_assessment_queue(path=Path("queue")) is constructor.return_value
    constructor.assert_called_once_with(
        path="queue", multithreading=True, auto_resume=False, serializer=json
    )


@pytest.mark.parametrize(
    "failure", [sqlite3.OperationalError("Driver details"), OSError("Filesystem details")]
)
def test_queue_open_failures_are_translated(*, monkeypatch, failure):
    monkeypatch.setattr(queue, "SQLiteAckQueue", Mock(side_effect=failure))
    with pytest.raises(
        StorageUnavailable, match=r"^The assessment queue could not be opened$"
    ) as caught:
        queue.create_assessment_queue(path=Path("queue"))
    assert caught.value.__cause__ is failure
