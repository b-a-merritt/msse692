import asyncio
import json
from unittest.mock import Mock
from uuid import UUID

import pytest
from fastapi import Request
from fastapi.exceptions import RequestValidationError

from normative_conformance.errors import NotFound
from normative_conformance.errors import NotReady
from normative_conformance.errors import ObservationExists
from normative_conformance.errors import StorageUnavailable
from normative_conformance.routes.errors import register_error_handlers
from normative_conformance.routes.errors import service_error
from normative_conformance.routes.errors import validation_error


@pytest.mark.parametrize(
    "error,status,code",
    [
        (NotFound("Missing record"), 404, "NOT_FOUND"),
        (ObservationExists("Already stored"), 409, "OBSERVATION_EXISTS"),
        (NotReady("Not running"), 503, "NOT_READY"),
        (StorageUnavailable("Unavailable"), 503, "STORAGE_UNAVAILABLE"),
    ],
)
def test_domain_errors_use_stable_status_code_and_request_identity(*, error, status, code):
    request = Request({"type": "http", "method": "GET", "path": "/example", "headers": []})
    request.state.request_id = UUID(int=1)
    response = asyncio.run(service_error(request, error))
    assert response.status_code == status
    assert json.loads(response.body) == {
        "error": {"code": code, "message": str(error), "request_id": str(UUID(int=1))}
    }


def test_validation_errors_preserve_framework_field_details():
    request = Request({"type": "http", "method": "POST", "path": "/example", "headers": []})
    request.state.request_id = UUID(int=1)
    details = [
        {"type": "missing", "loc": ("body", "case_id"), "msg": "Field required", "input": {}}
    ]
    response = asyncio.run(validation_error(request, RequestValidationError(details)))
    assert response.status_code == 422
    assert json.loads(response.body) == {
        "detail": [
            {"type": "missing", "loc": ["body", "case_id"], "msg": "Field required", "input": {}}
        ]
    }


def test_registers_domain_and_validation_handlers():
    application = Mock()
    register_error_handlers(application=application)
    registered = {
        call.args[0]: call.args[1] for call in application.add_exception_handler.call_args_list
    }
    assert registered == {
        RequestValidationError: validation_error,
        NotFound: service_error,
        ObservationExists: service_error,
        NotReady: service_error,
        StorageUnavailable: service_error,
    }
