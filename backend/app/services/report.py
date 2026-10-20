"""Assembly of the final Report and rendering of the print-friendly HTML."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

from jinja2 import Environment, FileSystemLoader, select_autoescape

try:
    from app.models import (
        CaseInput,
        Clause,
        CompanyEvidence,
        Decision,
        Report,
        Risk,
    )
except ModuleNotFoundError:  # support running with backend/app as the import root
    from models import (
        CaseInput,
        Clause,
        CompanyEvidence,
        Decision,
        Report,
        Risk,
    )

try:
    from app.services.decision import is_risk_flag
except ModuleNotFoundError:  # support running with backend/app as the import root
    from services.decision import is_risk_flag

TEMPLATE_DIR = Path(__file__).resolve().parents[3] / "data" / "templates"

LEVEL_ORDER = {"high": 0, "medium": 1, "low": 2}
LEVEL_LABEL = {"high": "高风险", "medium": "中风险", "low": "低风险"}

VERDICT_META = {
    "reject": {
        "key": "reject",
        "label": "不建议现在签",
        "advice": "当前条款或对方主体风险过高，不建议现在付款或签约；除非对方接受核心修改。",
    },
    "negotiate": {
        "key": "negotiate",
        "label": "先谈再签",
        "advice": "不要按当前版本直接签。先按下面的清单谈判，把高风险条款改到位再签。",
    },
    "sign": {
        "key": "sign",
        "label": "可以签",
        "advice": "风险未达到否决阈值；完成签前核对，并处理谈判清单中的条款后再推进。",
    },
}

CLAUSE_TYPE_LABEL = {
    "payment": "付款",
    "deposit": "预付款/押金",
    "delivery": "交付",
    "acceptance": "验收",
    "liability": "违约责任",
    "penalty": "违约金",
    "termination": "解除与退出",
    "refund": "退款",
    "dispute": "争议解决",
    "jurisdiction": "管辖",
    "confidentiality": "保密",
    "ip": "知识产权",
    "term": "期限",
    "renewal": "续约",
    "loan": "贷款",
    "other": "其他",
}

SEVERITY_LABEL = {
    "info": "提示",
    "warning": "注意",
    "high": "高",
    "medium": "中",
    "low": "低",
    "risk": "风险",
}

DEFAULT_NEGOTIATION_ITEMS = (
    "签约前核对对方营业执照名称、统一社会信用代码与合同主体是否一致",
    "所有款项只走对公账户，备注合同编号，拒绝向个人账户付款",
    "把交付时间、验收标准与逾期违约金写进合同正文",
    "约定争议由本地法院或仲裁委管辖，删除异地管辖条款",
    "保留盖章合同、付款凭证与关键聊天记录，交付节点书面确认",
    "预付款不超过合同总额的 30%，并与交付节点绑定",
)


def _clean(text: str) -> str:
    return " ".join((text or "").split()).strip().rstrip("。；;，, ")


def _sorted_risks(risks: list[Risk]) -> list[Risk]:
    return sorted(risks, key=lambda risk: LEVEL_ORDER.get(risk.level, 9))


def _negotiation_sheet(risks: list[Risk]) -> list[str]:
    items: list[str] = []
    seen: set[str] = set()

    for level, tag in (
        ("high", "P0 必须改"),
        ("medium", "P1 建议改"),
        ("low", "P2 留意"),
    ):
        for risk in risks:
            if risk.level != level:
                continue
            suggestion = _clean(risk.suggestion) or f"重新协商“{risk.title}”相关条款"
            if suggestion in seen:
                continue
            seen.add(suggestion)
            items.append(f"{tag}｜{risk.title}：{suggestion}")
            if len(items) >= 8:
                return items

    for item in DEFAULT_NEGOTIATION_ITEMS:
        if len(items) >= 5:
            break
        if item in seen:
            continue
        seen.add(item)
        items.append(f"P2 留意｜{item}")

    return items


def _sources(company: CompanyEvidence, risks: list[Risk]) -> list[str]:
    sources: list[str] = []
    raw = list(company.sources or [])
    for risk in risks:
        if risk.law and risk.law.source_url:
            raw.append(risk.law.source_url)

    for source in raw:
        source = (source or "").strip()
        if source and source not in sources:
            sources.append(source)
    return sources


def _format_generated_at(value: str) -> str:
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return value or ""
    offset = parsed.strftime("%z")
    suffix = f" UTC{offset[:3]}:{offset[3:]}" if offset else ""
    return parsed.strftime("%Y-%m-%d %H:%M") + suffix


def build_report(
    case_id: str,
    input: CaseInput,
    company: CompanyEvidence,
    clauses: list[Clause],
    risks: list[Risk],
    decision: Decision,
) -> Report:
    """Assemble the persisted Report payload for one case."""
    generated_at = datetime.now().astimezone().replace(microsecond=0).isoformat()
    return Report(
        case_id=case_id,
        input=input,
        company=company,
        clauses=clauses,
        risks=risks,
        decision=decision,
        negotiation_sheet=_negotiation_sheet(risks),
        sources=_sources(company, risks),
        generated_at=generated_at,
    )


def _clause_type_label(clause_type: str) -> str:
    return CLAUSE_TYPE_LABEL.get(clause_type, clause_type or "其他")


def _build_context(report: Report) -> dict:
    decision = report.decision
    risks = _sorted_risks(report.risks)
    clause_map = {clause.id: clause for clause in report.clauses}

    counts = {
        "high": sum(1 for risk in risks if risk.level == "high"),
        "medium": sum(1 for risk in risks if risk.level == "medium"),
        "low": sum(1 for risk in risks if risk.level == "low"),
    }

    risk_rows = []
    for index, risk in enumerate(risks, start=1):
        risk_rows.append(
            {
                "n": index,
                "id": risk.id,
                "title": risk.title,
                "level": risk.level,
                "level_label": LEVEL_LABEL.get(risk.level, risk.level),
                "why": risk.why,
                "suggestion": risk.suggestion,
                "confidence_pct": f"{round(risk.confidence * 100)}%",
                "law": risk.law,
                "clause": clause_map.get(risk.clause_id),
            }
        )

    clause_rows = [
        {
            "id": clause.id,
            "type": clause.type,
            "type_label": _clause_type_label(clause.type),
            "summary": clause.summary,
            "text": clause.text,
        }
        for clause in report.clauses
    ]

    facts = [
        {
            "label": fact.label,
            "value": fact.value,
            "source_url": fact.source_url,
            "retrieved_at": fact.retrieved_at,
            "severity": fact.severity,
            "severity_label": SEVERITY_LABEL.get(
                fact.severity, fact.severity or "提示"
            ),
        }
        for fact in report.company.facts
    ]

    meta = VERDICT_META.get(
        decision.verdict,
        {
            "key": decision.verdict,
            "label": decision.verdict,
            "advice": "",
        },
    )

    return {
        "report": report,
        "decision": decision,
        "company": report.company,
        "verdict": meta,
        "confidence_pct": f"{round(decision.confidence * 100)}%",
        "counts": counts,
        "risk_rows": risk_rows,
        "clause_rows": clause_rows,
        "facts": facts,
        "flags": [
            {"text": flag, "risk": is_risk_flag(flag)}
            for flag in (report.company.flags or [])
        ],
        "negotiation_sheet": report.negotiation_sheet,
        "sources": report.sources,
        "generated_at_display": _format_generated_at(report.generated_at),
    }


def render_html(report: Report) -> str:
    """Render a self-contained, A4-printable Chinese HTML report."""
    if isinstance(report, dict):
        report = Report.model_validate(report)
    env = Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(
            enabled_extensions=("html", "xml"),
            default_for_string=True,
        ),
        trim_blocks=True,
        lstrip_blocks=True,
    )
    template = env.get_template("report.html")
    return template.render(**_build_context(report))
