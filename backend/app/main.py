from __future__ import annotations

import logging
from pathlib import Path

from fastapi import FastAPI, Request, Response
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.api.cases import (
    ApiError,
    api_error_handler,
    http_error_handler,
    router as api_router,
)

log = logging.getLogger(__name__)

BACKEND_DIR = Path(__file__).resolve().parents[1]
STATIC_DIR = BACKEND_DIR / "static"

app = FastAPI(
    title="SignLens API",
    version="0.1.0",
    description="签前体检：合同风险 + 主体证据 + 决策建议",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api")
app.add_exception_handler(ApiError, api_error_handler)
app.add_exception_handler(StarletteHTTPException, http_error_handler)


@app.exception_handler(RequestValidationError)
async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    parts: list[str] = []
    for error in exc.errors():
        location = ".".join(
            str(part) for part in error.get("loc", ()) if part != "body"
        )
        message = str(error.get("msg", "invalid"))
        parts.append(f"{location}: {message}" if location else message)
    return JSONResponse(
        {"error": "invalid request: " + "; ".join(parts)},
        status_code=422,
    )


@app.exception_handler(Exception)
async def unhandled_error_handler(request: Request, exc: Exception) -> JSONResponse:
    log.exception("unhandled error: %s %s", request.method, request.url.path)
    return JSONResponse({"error": "internal server error"}, status_code=500)


@app.get("/", include_in_schema=False)
def index() -> Response:
    index_file = STATIC_DIR / "index.html"
    if index_file.is_file():
        return FileResponse(index_file)
    return JSONResponse(
        {"service": "SignLens API", "ok": True, "docs": "/docs"}
    )


if STATIC_DIR.is_dir():
    app.mount("/", StaticFiles(directory=STATIC_DIR, html=True), name="static")
