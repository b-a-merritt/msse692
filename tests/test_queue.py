"""Persistent queue creation and reopening."""

import sqlite3
from contextlib import closing

import pytest

from normative_conformance.errors import StorageUnavailable
from normative_conformance.queue import create_assessment_queue
from normative_conformance.services.scheduler.request_assessment import request_assessment


def test_queued_request_survives_reopening(*, tmp_path):
    path = tmp_path / "queue"
    with closing(create_assessment_queue(path=path)) as queue:
        request_assessment(case_id="case", queue=queue)
        task = queue.queue()[0]["data"]

    with closing(create_assessment_queue(path=path)) as reopened:
        assert reopened.get(block=False) == task
        assert reopened.empty()


def test_queue_open_failure_has_fixed_message_and_preserves_cause(*, tmp_path):
    path = tmp_path / "file"
    path.write_text("not a directory", encoding="utf-8")

    with pytest.raises(StorageUnavailable) as caught:
        create_assessment_queue(path=path)

    assert str(caught.value) == "The assessment queue could not be opened"
    assert isinstance(caught.value.__cause__, sqlite3.Error)
