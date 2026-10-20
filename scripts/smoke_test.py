#!/usr/bin/env python3
"""SignLens 部署冒烟测试。

对已经在运行的服务做端到端 HTTP 校验（本脚本不启动、不重启服务）：

    GET /api/health          -> {ok: true}
    GET /api/demo/cases      -> 至少 3 条演示案例，且包含 supplier-deposit
    POST /api/demo/{id}/run  -> {case_id, job_id}
    GET /api/jobs/{job_id}   -> 轮询到 done（默认最多 90 秒）
    report.risks >= 5；带 law 的风险 >= 3；decision.verdict in {negotiate, reject}

用法：
    python scripts/smoke_test.py
    BASE_URL=http://127.0.0.1:7860 python scripts/smoke_test.py
    SMOKE_JOB_TIMEOUT=120 python scripts/smoke_test.py

可选环境变量：BASE_URL、SMOKE_DEMO_ID、SMOKE_JOB_TIMEOUT、
SMOKE_POLL_INTERVAL、SMOKE_HTTP_TIMEOUT。
退出码：0 全部通过，1 失败，130 中断。
"""

from __future__ import annotations

import json
import os
import sys
import time
from typing import Any, Callable

import httpx

BASE_URL = os.getenv("BASE_URL", "http://127.0.0.1:7860").rstrip("/")
DEMO_ID = os.getenv("SMOKE_DEMO_ID", "supplier-deposit")
JOB_TIMEOUT = float(os.getenv("SMOKE_JOB_TIMEOUT", "90"))
POLL_INTERVAL = float(os.getenv("SMOKE_POLL_INTERVAL", "1.0"))
HTTP_TIMEOUT = float(os.getenv("SMOKE_HTTP_TIMEOUT", "30"))

MIN_CASES = 3
MIN_RISKS = 5
MIN_RISKS_WITH_LAW = 3
EXPECTED_VERDICTS = {"negotiate", "reject"}

LIST_KEYS = ("cases", "items", "data", "demos", "results")


class SmokeFailure(Exception):
    """单步校验失败，携带给人看的原因。"""


def brief(payload: Any, limit: int = 300) -> str:
    try:
        text = json.dumps(payload, ensure_ascii=False)
    except (TypeError, ValueError):
        text = repr(payload)
    return text if len(text) <= limit else text[:limit] + "…"


def request_json(
    client: httpx.Client, method: str, path: str, **kwargs: Any
) -> Any:
    url = f"{BASE_URL}{path}"
    try:
        resp = client.request(method, url, **kwargs)
    except httpx.HTTPError as exc:
        raise SmokeFailure(f"{method} {path} 请求失败：{exc!r}") from exc

    if resp.status_code >= 400:
        raise SmokeFailure(
            f"{method} {path} -> HTTP {resp.status_code}：{resp.text[:300] or '<空响应>'}"
        )

    try:
        return resp.json()
    except ValueError as exc:
        raise SmokeFailure(
            f"{method} {path} 返回的不是 JSON：{resp.text[:300] or '<空响应>'}"
        ) from exc


def extract_cases(payload: Any) -> list[Any]:
    if isinstance(payload, list):
        return payload
    if isinstance(payload, dict):
        for key in LIST_KEYS:
            value = payload.get(key)
            if isinstance(value, list):
                return value
    raise SmokeFailure(f"无法解析 /api/demo/cases 的案例列表：{brief(payload)}")


def check_health(client: httpx.Client) -> str:
    payload = request_json(client, "GET", "/api/health")
    if not isinstance(payload, dict) or payload.get("ok") is not True:
        raise SmokeFailure(f"/api/health 期望 {{'ok': true}}，实际：{brief(payload)}")
    return "ok=true"


def check_demo_cases(client: httpx.Client) -> str:
    payload = request_json(client, "GET", "/api/demo/cases")
    cases = extract_cases(payload)
    if len(cases) < MIN_CASES:
        raise SmokeFailure(
            f"演示案例只有 {len(cases)} 条，期望至少 {MIN_CASES} 条：{brief(payload)}"
        )

    ids = [
        str(case.get("id"))
        for case in cases
        if isinstance(case, dict) and case.get("id")
    ]
    if DEMO_ID not in ids:
        raise SmokeFailure(f"演示案例缺少 {DEMO_ID}，实际 id={ids}")
    return f"{len(cases)} 条，id={ids}"


def run_demo(client: httpx.Client) -> tuple[str, str]:
    payload = request_json(client, "POST", f"/api/demo/{DEMO_ID}/run")
    if not isinstance(payload, dict):
        raise SmokeFailure(f"POST /api/demo/{DEMO_ID}/run 期望对象：{brief(payload)}")

    case_id = payload.get("case_id")
    job_id = payload.get("job_id")
    if not isinstance(case_id, str) or not case_id:
        raise SmokeFailure(f"响应缺少 case_id：{brief(payload)}")
    if not isinstance(job_id, str) or not job_id:
        raise SmokeFailure(f"响应缺少 job_id：{brief(payload)}")
    return case_id, job_id


def _job_report(client: httpx.Client, case_id: str, job: Any) -> dict[str, Any]:
    """优先用 job 内嵌 report，缺失时回退到 /api/cases/{case_id}。"""
    if isinstance(job, dict):
        report = job.get("report")
        if isinstance(report, dict) and isinstance(report.get("risks"), list):
            return report

    report = request_json(client, "GET", f"/api/cases/{case_id}")
    if not isinstance(report, dict):
        raise SmokeFailure(f"/api/cases/{case_id} 期望对象：{brief(report)}")
    return report


def wait_for_report(
    client: httpx.Client, case_id: str, job_id: str, timeout: float
) -> dict[str, Any]:
    deadline = time.monotonic() + timeout
    last: Any = None

    while True:
        job = request_json(client, "GET", f"/api/jobs/{job_id}")
        last = job
        status = job.get("status") if isinstance(job, dict) else None

        if status == "done":
            return _job_report(client, case_id, job)

        if status == "error":
            raise SmokeFailure(
                f"job {job_id} 进入 error：{job.get('error')!r} "
                f"stage={job.get('stage')!r}"
            )

        remaining = deadline - time.monotonic()
        if remaining <= 0:
            detail = (
                f"status={status!r} stage={job.get('stage')!r} "
                f"progress={job.get('progress')!r}"
                if isinstance(job, dict)
                else brief(job)
            )
            raise SmokeFailure(f"job {job_id} 在 {timeout:.0f}s 内未完成：{detail}")

        time.sleep(min(POLL_INTERVAL, remaining))


def validate_report(report: dict[str, Any]) -> str:
    risks = report.get("risks")
    if not isinstance(risks, list):
        raise SmokeFailure(f"report.risks 不是数组：{brief(report)}")
    if len(risks) < MIN_RISKS:
        raise SmokeFailure(
            f"report.risks 只有 {len(risks)} 条，期望至少 {MIN_RISKS} 条"
        )

    with_law = [
        risk
        for risk in risks
        if isinstance(risk, dict)
        and isinstance(risk.get("law"), dict)
        and (risk["law"].get("name") or risk["law"].get("article"))
    ]
    if len(with_law) < MIN_RISKS_WITH_LAW:
        raise SmokeFailure(
            f"带 law 的风险只有 {len(with_law)} 条，期望至少 {MIN_RISKS_WITH_LAW} 条"
        )

    decision = report.get("decision")
    if not isinstance(decision, dict):
        raise SmokeFailure(f"report.decision 缺失或不是对象：{brief(report)}")

    verdict = decision.get("verdict")
    if verdict not in EXPECTED_VERDICTS:
        raise SmokeFailure(
            f"decision.verdict={verdict!r}，期望 {sorted(EXPECTED_VERDICTS)}"
        )

    levels: dict[str, int] = {}
    for risk in risks:
        if isinstance(risk, dict):
            level = str(risk.get("level"))
            levels[level] = levels.get(level, 0) + 1

    return (
        f"verdict={verdict} risks={len(risks)} 带法条={len(with_law)} "
        f"等级分布={levels}"
    )


def step(
    index: int,
    total: int,
    name: str,
    func: Callable[..., Any],
    *args: Any,
    show: Callable[[Any], str] | None = None,
) -> Any:
    started = time.monotonic()
    try:
        value = func(*args)
    except SmokeFailure as exc:
        elapsed = time.monotonic() - started
        print(f"[{index}/{total}] {name:<14} FAIL  {elapsed:6.1f}s")
        print(f"         {exc}")
        raise

    elapsed = time.monotonic() - started
    detail = show(value) if show else (value if isinstance(value, str) else "")
    print(f"[{index}/{total}] {name:<14} PASS  {elapsed:6.1f}s  {detail}")
    return value


def main() -> int:
    started = time.monotonic()
    total = 5

    print(
        f"SignLens smoke test -> {BASE_URL} "
        f"(demo={DEMO_ID}, job timeout={JOB_TIMEOUT:.0f}s)"
    )

    try:
        with httpx.Client(
            timeout=HTTP_TIMEOUT, follow_redirects=True, trust_env=False
        ) as client:
            step(1, total, "health", check_health, client)
            step(2, total, "demo cases", check_demo_cases, client)
            case_id, job_id = step(
                3,
                total,
                "run demo",
                run_demo,
                client,
                show=lambda value: f"case_id={value[0]} job_id={value[1]}",
            )
            report = step(
                4,
                total,
                "poll job",
                wait_for_report,
                client,
                case_id,
                job_id,
                JOB_TIMEOUT,
                show=lambda value: f"report.case_id={value.get('case_id')!r}",
            )
            summary = step(5, total, "validate report", validate_report, report)
    except SmokeFailure as exc:
        elapsed = time.monotonic() - started
        print(f"\nFAIL  smoke test 未通过（{elapsed:.1f}s）")
        print(f"      {exc}")
        return 1
    except KeyboardInterrupt:
        print("\nFAIL  smoke test 被中断")
        return 130

    elapsed = time.monotonic() - started
    print(f"\nPASS  {summary}  总耗时 {elapsed:.1f}s")
    return 0


if __name__ == "__main__":
    sys.exit(main())
