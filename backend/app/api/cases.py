from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse, JSONResponse
from pydantic import ValidationError
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core import orchestrator, store
from app.models import CaseInput, Job, Report

log = logging.getLogger(__name__)

router = APIRouter()

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_ROOT_DIR = _BACKEND_DIR.parent


class ApiError(Exception):
    def __init__(self, message: str, status_code: int = 400) -> None:
        super().__init__(message)
        self.message = message
        self.status_code = status_code


def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return JSONResponse({"error": exc.message}, status_code=exc.status_code)


def http_error_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    detail = exc.detail
    message = detail.get("error", str(detail)) if isinstance(detail, dict) else str(detail)
    return JSONResponse(
        {"error": message},
        status_code=exc.status_code,
        headers=getattr(exc, "headers", None),
    )


def _demo_dirs() -> list[Path]:
    return [_ROOT_DIR / "data" / "cases", _BACKEND_DIR / "data" / "cases"]


def _meta(doc: dict[str, Any], key: str) -> Any:
    if key in doc:
        return doc[key]
    meta = doc.get("meta")
    return meta.get(key) if isinstance(meta, dict) else None


def _company_name(value: Any) -> str:
    if isinstance(value, str):
        return value.strip()
    if isinstance(value, dict):
        return str(value.get("name") or "").strip()
    return ""


def _to_case_input(doc: dict[str, Any]) -> CaseInput:
    raw: dict[str, Any] | None = None
    for key in ("input", "case", "case_input"):
        nested = doc.get(key)
        if isinstance(nested, dict):
            raw = dict(nested)
            break
    if raw is None:
        raw = {key: value for key, value in doc.items() if key in CaseInput.model_fields}

    company = raw.get("company")
    if not _company_name(company):
        company = _meta(doc, "company")
    if isinstance(company, str):
        raw["company"] = {"name": company}
    elif isinstance(company, dict):
        raw["company"] = dict(company)

    if not raw.get("contract_text"):
        raw["contract_text"] = str(_meta(doc, "contract_text") or "")
    return CaseInput.model_validate(raw)


def _load_demo_docs() -> dict[str, dict[str, Any]]:
    docs: dict[str, dict[str, Any]] = {}
    for directory in _demo_dirs():
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.json")):
            try:
                doc = json.loads(path.read_text(encoding="utf-8"))
            except (OSError, json.JSONDecodeError) as exc:
                log.warning("skip demo case %s: %s", path, exc)
                continue
            if not isinstance(doc, dict):
                continue
            demo_id = str(_meta(doc, "id") or path.stem)
            docs.setdefault(demo_id, doc)
    return docs


def _demo_item(demo_id: str, doc: dict[str, Any], case: CaseInput) -> dict[str, Any]:
    return {
        "id": demo_id,
        "title": str(_meta(doc, "title") or demo_id),
        "summary": str(_meta(doc, "summary") or ""),
        "company": _company_name(_meta(doc, "company")) or case.company.name,
        "expected_verdict": str(_meta(doc, "expected_verdict") or ""),
    }


def _get_demo_case(demo_id: str) -> CaseInput:
    doc = _load_demo_docs().get(demo_id)
    if doc is None:
        raise ApiError(f"demo case not found: {demo_id}", 404)
    try:
        return _to_case_input(doc)
    except ValidationError as exc:
        log.warning("invalid demo case %s: %s", demo_id, exc)
        raise ApiError(f"invalid demo case data: {demo_id}", 500) from exc


@router.get("/health")
def health() -> dict[str, bool]:
    return {"ok": True}


@router.get("/demo/cases")
def list_demo_cases() -> list[dict[str, Any]]:
    docs = _load_demo_docs()
    items: list[dict[str, Any]] = []
    for demo_id in sorted(docs):
        doc = docs[demo_id]
        try:
            case = _to_case_input(doc)
        except ValidationError as exc:
            log.warning("skip invalid demo case %s: %s", demo_id, exc)
            continue
        items.append(_demo_item(demo_id, doc, case))
    return items


@router.get("/demo/{demo_id}", response_model=CaseInput)
def get_demo_case(demo_id: str) -> CaseInput:
    return _get_demo_case(demo_id)


@router.post("/demo/{demo_id}/run")
def run_demo_case(demo_id: str) -> dict[str, str]:
    case = _get_demo_case(demo_id)
    case_id = store.create_case(case)
    job = store.create_job(case_id)
    orchestrator.start_analysis(case_id, job.job_id)
    return {"case_id": case_id, "job_id": job.job_id}


@router.post("/demo/{demo_id}/analyze", response_model=Report)
def analyze_demo_case(demo_id: str) -> Report:
    """Serverless-safe: load the demo and return the finished report in one request."""
    case = _get_demo_case(demo_id)
    case_id = store.create_case(case)
    return orchestrator.analyze_sync(case_id, case)


@router.post("/cases")
def submit_case(case_input: CaseInput) -> dict[str, str]:
    case_id = store.create_case(case_input)
    return {"case_id": case_id}


@router.post("/analyze", response_model=Report)
def analyze_input(case_input: CaseInput) -> Report:
    """Serverless-safe: run the whole pipeline and return the report synchronously."""
    case_id = store.create_case(case_input)
    return orchestrator.analyze_sync(case_id, case_input)


@router.post("/cases/{case_id}/analyze")
def analyze_case(case_id: str) -> dict[str, str]:
    if store.get_case(case_id) is None:
        raise ApiError(f"case not found: {case_id}", 404)
    job = store.create_job(case_id)
    orchestrator.start_analysis(case_id, job.job_id)
    return {"job_id": job.job_id}


@router.get("/jobs/{job_id}", response_model=Job)
def get_job(job_id: str) -> Job:
    job = store.get_job(job_id)
    if job is None:
        raise ApiError(f"job not found: {job_id}", 404)
    return job


@router.get("/cases/{case_id}", response_model=Report)
def get_case_report(case_id: str) -> Report:
    if store.get_case(case_id) is None:
        raise ApiError(f"case not found: {case_id}", 404)
    report = store.get_latest_report(case_id)
    if report is None:
        raise ApiError(f"report not ready for case: {case_id}", 409)
    return report


@router.get("/cases/{case_id}/report.html", response_class=HTMLResponse)
def get_case_report_html(case_id: str) -> HTMLResponse:
    if store.get_case(case_id) is None:
        raise ApiError(f"case not found: {case_id}", 404)
    report = store.get_latest_report(case_id)
    if report is None:
        raise ApiError(f"report not ready for case: {case_id}", 409)
    try:
        from app.services.report import render_html
    except Exception as exc:
        raise ApiError(f"report service unavailable: {exc}", 500) from exc
    try:
        html = render_html(report)
    except Exception as exc:
        log.exception("render_html failed: case=%s", case_id)
        raise ApiError(f"failed to render report: {exc}", 500) from exc
    return HTMLResponse(content=html)


@router.post("/report/html", response_class=HTMLResponse)
def render_report_html(report: Report) -> HTMLResponse:
    """Render a posted report to HTML (stateless; safe on serverless instances)."""
    try:
        from app.services.report import render_html
    except Exception as exc:
        raise ApiError(f"report service unavailable: {exc}", 500) from exc
    try:
        html = render_html(report)
    except Exception as exc:
        log.exception("render_html failed for posted report")
        raise ApiError(f"failed to render report: {exc}", 500) from exc
    return HTMLResponse(content=html)
