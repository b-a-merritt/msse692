import sqlite3
from pathlib import Path

from persistqueue import SQLiteAckQueue
from persistqueue.serializers import json

from normative_conformance.errors import StorageUnavailable


def create_assessment_queue(*, path: Path) -> SQLiteAckQueue:
    """Open the persistent queue shared by request threads."""
    try:
        return SQLiteAckQueue(
            path=str(path),
            multithreading=True,
            auto_resume=False,
            serializer=json,
        )
    except (sqlite3.Error, OSError) as error:
        raise StorageUnavailable("The assessment queue could not be opened") from error
