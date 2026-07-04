"""Uniform error handling for the API.

Every error response has the same envelope so web and mobile clients can
handle failures with a single code path:

    {
        "success": false,
        "error": {"code": "DISTRICT_NOT_FOUND", "message": "..."}
    }
"""

import logging
import traceback

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("floodsense.api")


class APIError(Exception):
    """Application error carrying an HTTP status and a machine-readable code."""

    def __init__(self, status_code: int, code: str, message: str):
        self.status_code = status_code
        self.code = code
        self.message = message
        super().__init__(message)


# ── Convenience constructors ────────────────────────────────────────────────
def not_found(code: str, message: str) -> APIError:
    return APIError(404, code, message)


def bad_request(code: str, message: str) -> APIError:
    return APIError(400, code, message)


def unauthorized(message: str = "Invalid or missing authentication token.") -> APIError:
    return APIError(401, "UNAUTHORIZED", message)


def conflict(code: str, message: str) -> APIError:
    return APIError(409, code, message)


def service_unavailable(code: str, message: str) -> APIError:
    return APIError(503, code, message)


def _error_body(code: str, message: str, details=None) -> dict:
    error = {"code": code, "message": message}
    if details is not None:
        error["details"] = details
    return {"success": False, "error": error}


def register_exception_handlers(app: FastAPI) -> None:
    """Attach the uniform error envelope to every failure mode."""

    @app.exception_handler(APIError)
    async def handle_api_error(request: Request, exc: APIError):
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body(exc.code, exc.message),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(request: Request, exc: RequestValidationError):
        details = [
            {"field": ".".join(str(p) for p in err.get("loc", [])), "message": err.get("msg", "")}
            for err in exc.errors()
        ]
        return JSONResponse(
            status_code=422,
            content=_error_body(
                "VALIDATION_ERROR", "Request data failed validation.", details
            ),
        )

    @app.exception_handler(StarletteHTTPException)
    async def handle_http_exception(request: Request, exc: StarletteHTTPException):
        return JSONResponse(
            status_code=exc.status_code,
            content=_error_body("HTTP_ERROR", str(exc.detail)),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected(request: Request, exc: Exception):
        logger.error(
            "Unhandled error on %s %s\n%s",
            request.method,
            request.url.path,
            traceback.format_exc(),
        )
        return JSONResponse(
            status_code=500,
            content=_error_body(
                "INTERNAL_ERROR",
                f"Unexpected server error: {exc.__class__.__name__}: {exc}",
            ),
        )
