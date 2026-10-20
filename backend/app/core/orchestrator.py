from __future__ import annotations

import logging
import threading

from app.core import store

log = logging.getLogger(__name__)

STAGES: tuple[tuple[str, int], ...] = (
    ("parse", 10),
    ("company", 30),
    ("rules", 55),
    ("decide", 75),
    ("report", 90),
)


def start_analysis(case_id: str, job_id: str) -> threading.Thread:
    thread = threading.Thread(
        target=run_analysis,
        args=(case_id, job_id),
        name=f"signlens-{job_id}",
        daemon=True,
    )
    thread.start()
    return thread


def _set_stage(job_id: str, stage: str, progress: int) -> None:
    store.update_job(job_id, status="running", stage=stage, progress=progress)


def run_analysis(case_id: str, job_id: str) -> None:
    store.update_job(job_id, status="running", stage="parse", progress=0)
    try:
        case = store.get_case(case_id)
        if case is None:
            raise ValueError(f"case not found: {case_id}")

        # 延迟 import：其他 Agent 的 service 尚未落地时，应用仍可启动
        from app.services.clauses import extract_clauses
        from app.services.company import get_company_evidence
        from app.services.decision import decide
        from app.services.report import build_report, render_html
        from app.services.rules import match_risks

        _set_stage(job_id, "parse", 10)
        clauses = extract_clauses(case.contract_text)

        _set_stage(job_id, "company", 30)
        company = get_company_evidence(case.company.name)

        _set_stage(job_id, "rules", 55)
        risks = match_risks(clauses, company)

        _set_stage(job_id, "decide", 75)
        decision = decide(clauses, risks, company)

        _set_stage(job_id, "report", 90)
        report = build_report(case_id, case, company, clauses, risks, decision)
        try:
            render_html(report)
        except Exception:
            # 模板渲染失败不阻断 job，/report.html 会再暴露具体错误
            log.exception("render_html failed: case=%s job=%s", case_id, job_id)

        store.update_job(job_id, status="done", stage="done", progress=100, report=report)
    except Exception as exc:
        log.exception("analysis failed: case=%s job=%s", case_id, job_id)
        store.update_job(job_id, status="error", error=str(exc) or exc.__class__.__name__)
