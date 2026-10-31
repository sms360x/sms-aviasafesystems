import json
import os
import time
import uuid
import sys
from typing import Callable

from fastapi import Request, Response
from loguru import logger
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.metrics import record_request


def setup_logging():
    logger.remove()

    # 1. Always log to console (Vercel + Render read this sink)
    logger.add(
        sys.stderr,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level:<7} | {extra[request_id]:<36} | {message}",
        level="INFO",
        colorize=True,
    )

    # 2. Only log to file if NOT on Vercel (Vercel has a read-only file system)
    if os.environ.get("VERCEL") != "1":
        os.makedirs("logs", exist_ok=True)
        logger.add(
            "logs/aviasafe.json",
            format="{time} | {level} | {message}",
            level="INFO",
            rotation="100 MB",
            retention="30 days",
            serialize=True,
        )

    logger.configure(extra={"request_id": "-"})


class RequestLoggingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        request_id = str(uuid.uuid4())
        request.state.request_id = request_id

        start = time.monotonic()
        response = await call_next(request)
        duration_ms = round((time.monotonic() - start) * 1000, 1)

        user_id = None
        tenant_id = None
        role = None
        if hasattr(request.state, "user"):
            u = request.state.user
            if u:
                user_id = u.get("uid")
                tenant_id = u.get("tenant_id")
                role = u.get("role")

        record_request(request.method, request.url.path, response.status_code, duration_ms)

        log = logger.bind(request_id=request_id)
        log_data = {
            "method": request.method,
            "path": request.url.path,
            "status": response.status_code,
            "duration_ms": duration_ms,
        }
        if user_id:
            log_data["user_id"] = user_id
            log_data["tenant_id"] = tenant_id
            log_data["role"] = role

        if response.status_code >= 500:
            log.error("Request failed | {data}", data=log_data)
        elif response.status_code >= 400:
            log.warning("Request warning | {data}", data=log_data)
        else:
            log.info("Request ok | {data}", data=log_data)

        response.headers["X-Request-ID"] = request_id
        return response
