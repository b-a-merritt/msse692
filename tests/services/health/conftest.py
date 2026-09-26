from threading import Thread

import pytest


@pytest.fixture
def worker(*, scheduler):
    worker = Thread(target=scheduler.stopped.wait, name="health-test-worker")
    worker.start()
    try:
        yield worker
    finally:
        scheduler.stopped.set()
        worker.join(timeout=5)
        assert not worker.is_alive()
