from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

try:
    from app.models import Clause, LawRef, Risk
    from app.services.clauses import clause_type_scores
except ImportError:  # pragma: no cover - supports both `app.*` and relative imports
    from ..models import Clause, LawRef, Risk
    from .clauses import clause_type_scores

_LEVEL_ORDER = {"high": 0, "medium": 1, "low": 2}
_LEVEL_BASE = {"high": 0.86, "medium": 0.80, "low": 0.76}
_MAX_RISKS = 12
_SECONDARY_TYPE_MIN = 8
_SECONDARY_TYPE_GAP = 4
_PRIMARY_ONLY_RULES = frozenset(
    {
        "R-PAY-NO-DATE",
        "R-DELIVERY-NO-DATE",
        "R-DELIVERY-VAGUE",
        "R-ACCEPT-SHORT",
    }
)

_CN_DIGITS = {
    "零": 0,
    "〇": 0,
    "一": 1,
    "二": 2,
    "两": 2,
    "三": 3,
    "四": 4,
    "五": 5,
    "六": 6,
    "七": 7,
    "八": 8,
    "九": 9,
}
_PERCENT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[%％]")
_CN_PERCENT_RE = re.compile(r"百分之\s*([零〇一二三四五六七八九十百两\d]+)")
_CHENG_RE = re.compile(r"([一二三四五六七八九十两]+)\s*成")
_DAILY_RATE_RE = re.compile(
    r"(?:(?:每日|按日|每天)[^。；;]{0,24}?|日)\s*"
    r"(千分之|万分之|百分之)\s*"
    r"([零〇一二三四五六七八九十百两\d.]+)"
)
_DAILY_PERCENT_RE = re.compile(r"(\d+(?:\.\d+)?)\s*[%％]\s*(?:/|每)\s*日")

_EXPLICIT_DATE_RE = re.compile(
    r"(?:\d{4}\s*年\s*\d{1,2}\s*月"
    r"|\d{1,2}\s*月\s*\d{1,2}\s*[日号]"
    r"|\d{4}\s*[-/.]\s*\d{1,2}\s*[-/.]\s*\d{1,2}"
    r"|\d{1,4}\s*(?:个)?\s*(?:工作日|日|天|周|月)\s*(?:内|以内|之内)"
    r"|每(?:月|季度|年))"
)
_PAYMENT_TIMING_RE = re.compile(
    _EXPLICIT_DATE_RE.pattern
    + r"|货到付款|验收(?:合格)?后付款|交付(?:后)?付款|见票付款|月结|款到发货"
)
_VAGUE_DELIVERY = (
    "另行通知",
    "另行约定",
    "另行协商",
    "尽快",
    "视情况",
    "待定",
    "暂定",
    "以实际为准",
    "具体时间",
    "甲方通知",
)


def _rules_path() -> Path:
    path = Path(__file__).resolve().parents[3] / "data" / "rules" / "rules.json"
    if path.exists():
        return path
    fallback = Path.cwd() / "data" / "rules" / "rules.json"
    return fallback if fallback.exists() else path


@lru_cache(maxsize=1)
def load_rules() -> tuple[dict[str, Any], ...]:
    with _rules_path().open("r", encoding="utf-8") as handle:
        data = json.load(handle)
    if isinstance(data, dict):
        data = data.get("rules", [])
    if not isinstance(data, list):
        return ()
    return tuple(rule for rule in data if isinstance(rule, dict) and rule.get("id"))


def _cn_number(raw: str) -> float:
    raw = raw.strip()
    if not raw:
        return 0.0
    try:
        return float(raw)
    except ValueError:
        pass

    if "点" in raw:
        whole, fraction = raw.split("点", 1)
        whole_value = _cn_number(whole) if whole else 0.0
        fraction_value = 0.0
        scale = 1.0
        for char in fraction:
            if char not in _CN_DIGITS:
                continue
            scale /= 10
            fraction_value += _CN_DIGITS[char] * scale
        return whole_value + fraction_value

    total = 0
    number = 0
    for char in raw:
        if char in _CN_DIGITS:
            number = _CN_DIGITS[char]
        elif char == "十":
            total += (number or 1) * 10
            number = 0
        elif char == "百":
            total += (number or 1) * 100
            number = 0
    return float(total + number)


def _percentages(text: str) -> list[float]:
    values = [float(match.group(1)) for match in _PERCENT_RE.finditer(text)]
    values.extend(_cn_number(match.group(1)) for match in _CN_PERCENT_RE.finditer(text))
    values.extend(_cn_number(match.group(1)) * 10 for match in _CHENG_RE.finditer(text))
    return values


def _daily_rates(text: str) -> list[float]:
    rates: list[float] = []
    for match in _DAILY_RATE_RE.finditer(text):
        unit, raw = match.group(1), match.group(2)
        value = _cn_number(raw)
        if unit == "千分之":
            value /= 10
        elif unit == "万分之":
            value /= 100
        rates.append(value)
    rates.extend(float(match.group(1)) for match in _DAILY_PERCENT_RE.finditer(text))
    return rates


def _percentage_near(
    text: str, keywords: tuple[str, ...], before: int = 12, after: int = 24
) -> float | None:
    for keyword in keywords:
        for match in re.finditer(re.escape(keyword), text):
            start = max(0, match.start() - before)
            end = min(len(text), match.end() + after)
            values = _percentages(text[start:end])
            if values:
                return values[0]
    return None


def _check_prepay(text: str, hits: list[str]) -> bool:
    if any(keyword in text for keyword in ("全额预付", "先付全款", "款到发货", "预付100%")):
        return True
    value = _percentage_near(text, ("预付款", "首付款", "首付", "预付"))
    return value is not None and value >= 30


def _check_payment_no_date(text: str, hits: list[str]) -> bool:
    return not bool(_PAYMENT_TIMING_RE.search(text))


def _check_delivery_no_date(text: str, hits: list[str]) -> bool:
    if _EXPLICIT_DATE_RE.search(text):
        return False
    if any(
        keyword in text
        for keyword in ("风险", "毁损", "灭失", "转移", "交付地点", "交货地点", "运费", "运输方式")
    ):
        return False
    return not any(phrase in text for phrase in _VAGUE_DELIVERY)


def _check_delivery_vague(text: str, hits: list[str]) -> bool:
    if any(
        keyword in text
        for keyword in ("交付地点", "交货地点", "送货地址", "运输方式", "运费")
    ) and not any(keyword in text for keyword in ("时间", "日期", "期限")):
        return False
    return True


def _check_deposit_over_20(text: str, hits: list[str]) -> bool:
    value = _percentage_near(text, ("定金", "订金"))
    return value is not None and value > 20


def _check_penalty_high(text: str, hits: list[str]) -> bool:
    value = _percentage_near(text, ("违约金", "滞纳金", "罚款"))
    if value is not None and value >= 20:
        return True
    if any(value >= 0.1 for value in _daily_rates(text)):
        return True
    return any(keyword in text for keyword in ("双倍", "三倍", "全部损失", "惩罚性"))


def _check_penalty_low(text: str, hits: list[str]) -> bool:
    value = _percentage_near(text, ("违约金", "滞纳金", "罚款"))
    if value is not None and value <= 5:
        return True
    if any(value <= 0.05 for value in _daily_rates(text)):
        return True
    return any(
        keyword in text
        for keyword in ("不超过", "以合同总额为限", "以合同金额为限", "封顶", "上限为")
    )


def _check_juris_court(text: str, hits: list[str]) -> bool:
    neutral = any(
        keyword in text
        for keyword in ("房屋所在地", "不动产所在地", "合同履行地", "被告住所地", "原告住所地")
    )
    one_sided = any(
        keyword in text
        for keyword in ("乙方所在地", "甲方所在地", "我方所在地", "对方所在地", "公司所在地")
    )
    return not (neutral and not one_sided)


def _check_train_probation(text: str, hits: list[str]) -> bool:
    if "试用期" not in text:
        return False
    return any(
        keyword in text
        for keyword in ("工资", "80%", "百分之八十", "最低工资", "个月", "期限")
    )


def _check_auto_cancel(text: str, hits: list[str]) -> bool:
    if not any(keyword in text for keyword in ("自动续费", "自动续期", "自动展期", "自动延长", "默认续约")):
        return False
    if "不得取消" in text or "无法取消" in text:
        return True
    if "取消" not in text:
        return True
    return bool(re.search(r"提前\s*(?:60|90|120|180)\s*(?:日|天)", text))


_RULE_CHECKS = {
    "R-PAY-PREPAY": _check_prepay,
    "R-PAY-NO-DATE": _check_payment_no_date,
    "R-DELIVERY-NO-DATE": _check_delivery_no_date,
    "R-DELIVERY-VAGUE": _check_delivery_vague,
    "R-DEPOSIT-OVER-20": _check_deposit_over_20,
    "R-PENALTY-HIGH": _check_penalty_high,
    "R-PENALTY-LOW": _check_penalty_low,
    "R-JURIS-COURT": _check_juris_court,
    "R-TRAIN-PROBATION": _check_train_probation,
    "R-AUTO-CANCEL": _check_auto_cancel,
}


def _confidence(level: str, hits: list[str], company: Any = None) -> float:
    value = _LEVEL_BASE.get(level, 0.78) + min(0.06, 0.02 * max(0, len(hits) - 1))
    flags: Any = None
    if company is not None:
        flags = getattr(company, "flags", None)
        if flags is None and isinstance(company, dict):
            flags = company.get("flags")
    if flags and level == "high":
        if any(
            marker in str(flag)
            for flag in flags
            for marker in ("被执行", "失信", "经营异常")
        ):
            value += 0.02
    return round(min(0.95, max(0.75, value)), 2)


def match_risks(clauses: list[Clause], company: Any = None) -> list[Risk]:
    candidates: list[tuple[Clause, dict[str, Any], list[str]]] = []
    seen: set[tuple[str, str]] = set()

    for clause in clauses:
        clause_type = getattr(clause, "type", "other")
        text = getattr(clause, "text", "") or ""
        type_scores = clause_type_scores(text)
        top_score = max(type_scores.values(), default=0)
        for rule in load_rules():
            rule_type = rule.get("type", "other")
            if rule_type not in ("any", "*") and rule_type != clause_type:
                if rule.get("id") in _PRIMARY_ONLY_RULES:
                    continue
                secondary_score = type_scores.get(rule_type, 0)
                if secondary_score < _SECONDARY_TYPE_MIN:
                    continue
                if top_score - secondary_score > _SECONDARY_TYPE_GAP:
                    continue

            keywords = rule.get("keywords") or []
            hits = [keyword for keyword in keywords if keyword and keyword in text]
            if not hits:
                continue

            checker = _RULE_CHECKS.get(rule.get("id", ""))
            if checker is not None and not checker(text, hits):
                continue

            key = (getattr(clause, "id", ""), str(rule.get("id", "")))
            if key in seen:
                continue
            seen.add(key)
            candidates.append((clause, rule, hits))

    deduped: dict[str, tuple[Clause, dict[str, Any], list[str]]] = {}
    for clause, rule, hits in candidates:
        rule_id = str(rule.get("id", ""))
        previous = deduped.get(rule_id)
        if previous is None or _LEVEL_ORDER.get(
            rule.get("level", "low"), 3
        ) < _LEVEL_ORDER.get(previous[1].get("level", "low"), 3):
            deduped[rule_id] = (clause, rule, hits)
    candidates = list(deduped.values())

    candidates.sort(key=lambda item: _LEVEL_ORDER.get(item[1].get("level", "low"), 3))

    risks: list[Risk] = []
    for index, (clause, rule, hits) in enumerate(candidates[:_MAX_RISKS], start=1):
        law = rule.get("law")
        law_ref = None
        if isinstance(law, dict) and law.get("name") and law.get("article"):
            law_ref = LawRef(
                name=str(law["name"]),
                article=str(law["article"]),
                text=str(law.get("text", "")),
                source_url=str(law.get("source_url", "")),
            )

        level = rule.get("level", "medium")
        if level not in _LEVEL_ORDER:
            level = "medium"

        risks.append(
            Risk(
                id=f"r{index}",
                clause_id=getattr(clause, "id", None),
                title=str(rule.get("title", "条款风险")),
                level=level,
                why=str(rule.get("why", "")),
                law=law_ref,
                suggestion=str(rule.get("suggestion", "")),
                confidence=_confidence(level, hits, company),
            )
        )

    return risks
