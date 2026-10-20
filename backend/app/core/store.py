from __future__ import annotations

import threading
import uuid

from app.models import CaseInput, Job, Report

_CASES: dict[str, CaseInput] = {}
_JOBS: dict[str, Job] = {}
_LOCK = threading.RLock()


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:12]}"


def create_case(case_input: CaseInput) -> str:
    case_id = _new_id("case")
    with _LOCK:
        _CASES[case_id] = case_input.model_copy(deep=True)
    return case_id


def get_case(case_id: str) -> CaseInput | None:
    with _LOCK:
        case = _CASES.get(case_id)
        return case.model_copy(deep=True) if case is not None else None


def create_job(case_id: str) -> Job:
    job = Job(job_id=_new_id("job"), case_id=case_id)
    with _LOCK:
        _JOBS[job.job_id] = job
        return job.model_copy(deep=True)


def update_job(job_id: str, **fields: object) -> Job | None:
    with _LOCK:
        job = _JOBS.get(job_id)
        if job is None:
            return None
        updated = job.model_copy(update=fields)
        _JOBS[job_id] = updated
        return updated.model_copy(deep=True)


def get_job(job_id: str) -> Job | None:
    with _LOCK:
        job = _JOBS.get(job_id)
        return job.model_copy(deep=True) if job is not None else None


def get_latest_report(case_id: str) -> Report | None:
    with _LOCK:
        for job in reversed(list(_JOBS.values())):
            if job.case_id == case_id and job.report is not None:
                return job.report.model_copy(deep=True)
    return None
