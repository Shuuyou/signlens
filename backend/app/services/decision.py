"""Deterministic sign / negotiate / reject rubric.

Scoring is intentionally simple so the demo is reproducible offline:

* risk level: high = 3, medium = 2, low = 1
* company red flag (被执行 / 异常 / 处罚 / 频繁变更): +3 each
* company verification flag (未收录 / 需核验): +1 each
* total >= 8 -> reject, 4-7 -> negotiate, < 4 -> sign
"""

from __future__ import annotations

try:
    from app.models import Clause, CompanyEvidence, Decision, Risk
except ModuleNotFoundError:  # support running with backend/app as the import root
    from models import Clause, CompanyEvidence, Decision, Risk

LEVEL_SCORE = {"high": 3, "medium": 2, "low": 1}
LEVEL_ORDER = {"high": 0, "medium": 1, "low": 2}

RED_FLAGS = (
    ("被执行", "对方有被执行记录"),
    ("异常", "对方存在经营异常"),
    ("处罚", "对方有行政处罚记录"),
    ("频繁变更", "对方近期频繁变更"),
)
WATCH_FLAGS = (
    ("未收录", "对方主体信息未收录"),
    ("需核验", "对方主体信息需核验"),
)
RISK_FLAG_KEYWORDS = tuple(keyword for keyword, _phrase in RED_FLAGS + WATCH_FLAGS)


def is_risk_flag(flag: str) -> bool:
    """True when a company flag carries one of the rubric's risk keywords."""
    return any(keyword in (flag or "") for keyword in RISK_FLAG_KEYWORDS)

VERDICT_LABEL = {"reject": "不签", "negotiate": "可谈", "sign": "可签"}

HEADLINE_PREFIX = {
    "reject": "不建议现在签",
    "negotiate": "可以谈，但别按现在的版本签",
    "sign": "风险可控，可以签",
}


def _clip(text: str, limit: int) -> str:
    text = " ".join((text or "").split()).strip()
    if len(text) <= limit:
        return text
    return text[: limit - 1].rstrip("，。；;、 ") + "…"


def _clean_sentence(text: str) -> str:
    return " ".join((text or "").split()).strip().rstrip("。；;，, ")


def _score(risks: list[Risk], company: CompanyEvidence) -> int:
    total = sum(LEVEL_SCORE.get(risk.level, 0) for risk in risks)
    flags = " ".join(company.flags or [])
    for keyword, _phrase in RED_FLAGS:
        if keyword in flags:
            total += 3
    for keyword, _phrase in WATCH_FLAGS:
        if keyword in flags:
            total += 1
    return total


def _verdict(total: int) -> str:
    if total >= 8:
        return "reject"
    if total >= 4:
        return "negotiate"
    return "sign"


def _company_phrases(flags: list[str]) -> list[str]:
    text = " ".join(flags or [])
    phrases: list[str] = []
    for keyword, phrase in RED_FLAGS + WATCH_FLAGS:
        if keyword in text and phrase not in phrases:
            phrases.append(phrase)
    return phrases


def _risk_flag_texts(flags: list[str]) -> list[str]:
    """Only flags that actually carry a red/watch keyword are risk reasons."""
    texts: list[str] = []
    for flag in flags or []:
        text = _clean_sentence(flag)
        if text and is_risk_flag(text) and text not in texts:
            texts.append(text)
    return texts


def _headline(verdict: str, risks: list[Risk], company: CompanyEvidence) -> str:
    high = sum(1 for risk in risks if risk.level == "high")
    medium = sum(1 for risk in risks if risk.level == "medium")
    company_phrases = _company_phrases(company.flags)

    if high:
        risk_part = f"{high} 条高风险条款"
    elif medium:
        risk_part = f"{medium} 条中风险条款"
    elif risks:
        risk_part = f"{len(risks)} 条低风险条款"
    elif company_phrases:
        risk_part = "条款层面未发现明显风险"
    else:
        risk_part = "未发现明显风险条款"

    parts = [risk_part]
    parts.extend(company_phrases[:2])
    prefix = HEADLINE_PREFIX[verdict]
    if verdict == "sign" and (high or company_phrases):
        prefix = "可以签，但有一个前提"
    return f"{prefix}：" + " + ".join(parts)


def _reasons(
    clauses: list[Clause], risks: list[Risk], company: CompanyEvidence
) -> list[str]:
    high = [
        f"高风险｜{risk.title}：{_clip(risk.why, 100)}"
        for risk in risks
        if risk.level == "high"
    ]
    flags = [
        f"主体风险｜{flag}" for flag in _risk_flag_texts(company.flags)
    ]
    medium = [
        f"中风险｜{risk.title}：{_clip(risk.why, 100)}"
        for risk in risks
        if risk.level == "medium"
    ]
    low = [
        f"低风险｜{risk.title}：{_clip(risk.why, 100)}"
        for risk in risks
        if risk.level == "low"
    ]

    if high and flags:
        ordered = high[:3] + flags[:1]
    else:
        ordered = high + flags
    ordered += medium + low

    reasons: list[str] = []
    seen: set[str] = set()
    for line in ordered:
        line = line.strip()
        if line and line not in seen:
            seen.add(line)
            reasons.append(line)
        if len(reasons) >= 4:
            return reasons

    if not reasons:
        if clauses:
            return [
                f"合同共 {len(clauses)} 条条款，未命中已知高风险规则",
                "仍建议核对签约主体、付款路径与交付约定",
            ]
        return [
            "未提供可解析的合同条款，请先确认文本完整",
            "在条款缺失的情况下无法给出可靠的签约判断",
        ]

    return reasons


def _conditions(risks: list[Risk]) -> list[str]:
    """Up to three pre-signing conditions, taken from high-risk fixes only."""
    conditions: list[str] = []
    for risk in risks:
        if risk.level != "high":
            continue
        suggestion = _clean_sentence(risk.suggestion)
        if suggestion and suggestion not in conditions:
            conditions.append(suggestion)
        if len(conditions) >= 3:
            break
    return conditions


def _change_my_mind(risks: list[Risk], verdict: str) -> list[str]:
    pool: list[str] = []
    for level in ("high", "medium", "low"):
        for risk in risks:
            if risk.level != level:
                continue
            suggestion = _clean_sentence(risk.suggestion)
            if suggestion and suggestion not in pool:
                pool.append(suggestion)

    if verdict == "sign":
        items: list[str] = []
        if pool:
            items.append(
                f"如果对方拒绝「{_clip(pool[0], 80)}」，"
                "结论会从“可签”变为“可谈”"
            )
        items.extend(
            (
                "如果对方拒绝把口头承诺（交付时间、退款条件）写进合同，"
                "结论会从“可签”变为“可谈”",
                "如果对方要求预付款超过合同总额的 50%，"
                "结论会从“可签”变为“可谈”",
                "如果签约前发现对方新增被执行、经营异常或行政处罚记录，"
                "结论会从“可签”变为“不签”",
            )
        )
        return items[:3]

    start = VERDICT_LABEL[verdict]
    target = "可谈" if verdict == "reject" else "可签"
    items = [
        f"如果对方接受「{_clip(suggestion, 80)}」，"
        f"结论会从“{start}”变为“{target}”"
        for suggestion in pool[:2]
    ]

    if verdict == "reject":
        defaults = (
            (
                ("预付", "首付"),
                "如果对方同意把预付款降到合同总额的 10% 以内，并接受本地法院或仲裁委管辖，"
                "结论会从“不签”变为“可谈”",
            ),
            (
                ("交付", "验收"),
                "如果对方同意写明交付日期、验收标准与逾期违约金，"
                "结论会从“不签”变为“可谈”",
            ),
            (
                ("担保", "托管"),
                "如果对方愿意提供履约担保或第三方托管付款，"
                "结论会从“不签”变为“可谈”",
            ),
        )
    else:
        defaults = (
            (
                ("预付", "首付"),
                "如果对方同意把预付款降到合同总额的 30% 以内，并与交付节点绑定，"
                "结论会从“可谈”变为“可签”",
            ),
            (
                ("管辖", "仲裁", "争议"),
                "如果对方同意把争议交给本地法院或仲裁委管辖，"
                "结论会从“可谈”变为“可签”",
            ),
            (
                ("交付", "验收", "退款"),
                "如果对方同意补上书面交付、验收与退款条款，"
                "结论会从“可谈”变为“可签”",
            ),
        )

    covered_text = " ".join(items)
    for keywords, text in defaults:
        if len(items) >= 3:
            break
        if text in items or any(keyword in covered_text for keyword in keywords):
            continue
        items.append(text)

    for _keywords, text in defaults:
        if len(items) >= 3:
            break
        if text not in items:
            items.append(text)
    return items[:3]


def _confidence(risks: list[Risk], company: CompanyEvidence) -> float:
    risk_part = min(len(risks), 8) / 8 * 0.12
    fact_part = min(len(company.facts), 5) / 5 * 0.10
    flag_part = 0.04 if company.flags else 0.0
    source_part = 0.04 if company.sources else 0.0
    value = 0.60 + risk_part + fact_part + flag_part + source_part
    return round(min(0.90, max(0.60, value)), 2)


def decide(
    clauses: list[Clause], risks: list[Risk], company: CompanyEvidence
) -> Decision:
    """Return a deterministic, explainable Decision for a case."""
    total = _score(risks, company)
    verdict = _verdict(total)
    return Decision(
        verdict=verdict,
        confidence=_confidence(risks, company),
        headline=_headline(verdict, risks, company),
        reasons=_reasons(clauses, risks, company),
        conditions=_conditions(risks),
        change_my_mind=_change_my_mind(risks, verdict),
    )
