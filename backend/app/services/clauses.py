from __future__ import annotations

import re

try:
    from app.models import Clause
except ImportError:  # pragma: no cover - supports both `app.*` and relative imports
    from ..models import Clause

MIN_CLAUSE_CHARS = 10
SOFT_LINE_CHARS = 80
MAX_CLAUSE_CHARS = 420
COMMA_SPLIT_CHARS = 30

_NUMBERED_HEADING_RE = re.compile(
    r"^\s*(?:"
    r"第[一二三四五六七八九十百零〇\d]+[条章节部分]"
    r"|[一二三四五六七八九十]+[、.．]"
    r"|[（(][一二三四五六七八九十\d]+[)）]"
    r"|\d+[、.．)）]"
    r")"
)
_HEADING_RE = _NUMBERED_HEADING_RE
_SENTENCE_END_RE = re.compile(r"[。！？；;]$")
_SENTENCE_CUT_RE = re.compile(r"[。！？；;]")
_COMMA_RE = re.compile(r"[，,]")
_WS_RE = re.compile(r"\s+")

_TYPE_KEYWORDS: dict[str, dict[str, int]] = {
    "training_loan": {
        "培训贷": 9,
        "助学贷": 9,
        "培训贷款": 9,
        "教育分期": 8,
        "分期贷": 8,
        "贷款": 4,
        "分期": 3,
        "利息": 3,
        "服务期": 5,
        "服务期约定": 9,
        "违反服务期": 12,
        "服务期违约金": 13,
        "未满服务期": 10,
        "培训费违约金": 12,
        "竞业限制": 7,
        "竞业禁止": 7,
        "竞业限制约定": 9,
        "竞业禁止约定": 9,
        "竞业限制违约金": 13,
        "竞业禁止违约金": 13,
        "不得从事": 7,
        "同行业": 7,
        "无补偿": 6,
        "不支付补偿": 6,
        "试用期": 5,
        "扣押": 6,
        "押证件": 6,
        "身份证": 3,
        "包就业": 7,
        "推荐就业": 4,
        "不退费": 5,
        "不予退费": 5,
        "退费": 4,
        "退训": 6,
        "学费": 6,
        "培训费": 3,
    },
    "auto_renew": {
        "自动续费": 10,
        "自动续期": 10,
        "自动展期": 10,
        "自动延长": 8,
        "默认续约": 8,
        "自动扣款": 8,
        "续费": 4,
        "续约": 3,
        "到期": 1,
    },
    "unilateral_change": {
        "单方变更": 10,
        "单方面变更": 10,
        "有权变更": 8,
        "随时变更": 9,
        "无需通知": 6,
        "最终解释权": 9,
        "以甲方解释为准": 8,
        "有权调整": 7,
        "单方调整": 9,
        "变更": 2,
    },
    "confidentiality": {
        "保密": 7,
        "商业秘密": 8,
        "机密": 6,
        "不得披露": 6,
        "保密义务": 7,
        "保密信息": 6,
        "保密义务违约金": 13,
        "违反保密义务": 12,
        "保密违约金": 12,
        "永久保密": 8,
    },
    "jurisdiction": {
        "仲裁委员会": 9,
        "仲裁": 6,
        "管辖": 7,
        "人民法院": 6,
        "法院": 5,
        "诉讼": 5,
        "争议解决": 6,
        "管辖法院": 7,
        "异地": 3,
    },
    "ip": {
        "知识产权": 9,
        "著作权": 8,
        "专利": 6,
        "商标": 6,
        "源代码": 5,
        "技术成果": 6,
        "成果归属": 8,
        "所有权": 4,
        "归甲方所有": 6,
        "归乙方所有": 6,
    },
    "deposit": {
        "定金": 8,
        "押金": 7,
        "保证金": 5,
        "订金": 6,
        "不退": 3,
        "不予退还": 6,
        "没收": 5,
        "抵扣": 2,
    },
    "penalty": {
        "违约金": 9,
        "滞纳金": 7,
        "罚款": 6,
        "双倍": 5,
        "三倍": 5,
        "赔偿": 3,
        "逾期": 4,
        "违约": 3,
    },
    "acceptance": {
        "验收": 9,
        "检验": 6,
        "签收": 6,
        "质量异议": 6,
        "验收标准": 9,
        "视为合格": 7,
        "质保": 6,
        "保修": 5,
        "售后": 5,
        "三包": 6,
    },
    "delivery": {
        "交付": 8,
        "交货": 8,
        "发货": 6,
        "到货": 5,
        "送货": 5,
        "运输": 3,
        "物流": 3,
        "交付时间": 9,
        "交货时间": 9,
        "交付日期": 9,
    },
    "termination": {
        "解除": 8,
        "终止": 6,
        "解约": 7,
        "退费": 5,
        "提前终止": 6,
        "合同终止": 7,
        "解除权": 8,
        "已付款项作为违约金": 12,
        "已付款项归": 10,
        "款项不予退还": 10,
    },
    "liability": {
        "赔偿": 5,
        "责任": 4,
        "免责": 8,
        "不可抗力": 9,
        "连带": 8,
        "损失": 4,
        "上限": 3,
        "赔偿上限": 8,
        "一切责任": 6,
        "不承担": 5,
    },
    "payment": {
        "付款": 7,
        "支付": 6,
        "预付款": 9,
        "首付款": 8,
        "首付": 7,
        "价款": 5,
        "货款": 6,
        "结算": 5,
        "账期": 5,
        "扣减": 6,
        "扣除": 6,
        "抵扣": 5,
        "直接扣除": 8,
        "从货款中扣除": 10,
        "发票": 6,
        "税费": 5,
        "含税": 5,
        "尾款": 6,
        "余款": 6,
        "全款": 6,
        "款项": 3,
    },
}


def _trim(text: str, start: int, end: int) -> tuple[int, int]:
    while start < end and text[start].isspace():
        start += 1
    while end > start and text[end - 1].isspace():
        end -= 1
    return start, end


def _line_units(text: str) -> list[tuple[int, int]]:
    units: list[tuple[int, int]] = []
    buf_start: int | None = None
    buf_end: int | None = None

    def flush() -> None:
        nonlocal buf_start, buf_end
        if buf_start is not None and buf_end is not None and buf_end > buf_start:
            units.append((buf_start, buf_end))
        buf_start = None
        buf_end = None

    offset = 0
    for raw in text.splitlines(keepends=True):
        line_start = offset
        offset += len(raw)
        stripped = raw.strip()
        if not stripped:
            flush()
            continue

        leading = len(raw) - len(raw.lstrip())
        start = line_start + leading
        end = line_start + len(raw.rstrip())

        if buf_start is not None and _HEADING_RE.match(stripped):
            flush()
        if buf_start is None:
            if (
                _NUMBERED_HEADING_RE.match(stripped)
                and len(stripped) <= 30
                and not _SENTENCE_END_RE.search(stripped)
            ):
                continue
            buf_start = start
        buf_end = end

        if len(stripped) >= MAX_CLAUSE_CHARS:
            flush()
        elif _SENTENCE_END_RE.search(stripped) and (buf_end - buf_start) >= MIN_CLAUSE_CHARS:
            flush()
        elif len(stripped) >= SOFT_LINE_CHARS:
            flush()

    flush()
    return units


def _split_sentences(text: str, start: int, end: int) -> list[tuple[int, int]]:
    if end - start <= MIN_CLAUSE_CHARS:
        return [(start, end)]

    segment = text[start:end]
    parts: list[tuple[int, int]] = []
    cursor = 0
    for match in _SENTENCE_CUT_RE.finditer(segment):
        cut = match.end()
        if cut - cursor >= MIN_CLAUSE_CHARS:
            parts.append((start + cursor, start + cut))
            cursor = cut
    if cursor < len(segment):
        parts.append((start + cursor, end))
    return parts or [(start, end)]


def _split_commas(text: str, start: int, end: int) -> list[tuple[int, int]]:
    if end - start <= COMMA_SPLIT_CHARS:
        return [(start, end)]

    segment = text[start:end]
    scores = clause_type_scores(segment)
    if sum(1 for score in scores.values() if score >= 8) < 2:
        return [(start, end)]

    parts: list[tuple[int, int]] = []
    cursor = 0
    for match in _COMMA_RE.finditer(segment):
        cut = match.end()
        if cut - cursor >= MIN_CLAUSE_CHARS:
            parts.append((start + cursor, start + cut))
            cursor = cut
    if cursor < len(segment):
        parts.append((start + cursor, end))
    return parts or [(start, end)]


def _has_heading_between(text: str, left_end: int, right_start: int) -> bool:
    if right_start <= left_end:
        return False
    return bool(_NUMBERED_HEADING_RE.search(text[left_end:right_start]))


def _merge_short(units: list[tuple[int, int]], text: str) -> list[tuple[int, int]]:
    merged: list[tuple[int, int]] = []
    pending: tuple[int, int] | None = None

    for start, end in units:
        start, end = _trim(text, start, end)
        if end <= start:
            continue
        if pending is not None:
            pending_start, pending_end = pending
            if _has_heading_between(text, pending_end, start):
                merged.append(pending)
            else:
                start = pending_start
            pending = None

        if merged and (end - start) < MIN_CLAUSE_CHARS:
            prev_start, prev_end = merged[-1]
            if _has_heading_between(text, prev_end, start):
                merged.append((start, end))
            else:
                merged[-1] = (prev_start, end)
        elif (end - start) < MIN_CLAUSE_CHARS:
            pending = (start, end)
        else:
            merged.append((start, end))

    if pending is not None:
        if merged:
            prev_start, prev_end = merged[-1]
            if _has_heading_between(text, prev_end, pending[0]):
                merged.append(pending)
            else:
                merged[-1] = (prev_start, pending[1])
        else:
            merged.append(pending)

    return merged


def _split_long(text: str, start: int, end: int) -> list[tuple[int, int]]:
    if end - start <= MAX_CLAUSE_CHARS:
        return [(start, end)]

    segment = text[start:end]
    parts: list[tuple[int, int]] = []
    cursor = 0
    for match in _SENTENCE_CUT_RE.finditer(segment):
        cut = match.end()
        if cut - cursor >= MIN_CLAUSE_CHARS:
            parts.append((start + cursor, start + cut))
            cursor = cut
    if cursor < len(segment):
        parts.append((start + cursor, end))

    if not parts:
        parts = [(start, end)]

    hard: list[tuple[int, int]] = []
    for part_start, part_end in parts:
        while part_end - part_start > MAX_CLAUSE_CHARS:
            hard.append((part_start, part_start + MAX_CLAUSE_CHARS))
            part_start += MAX_CLAUSE_CHARS
        if part_end > part_start:
            hard.append((part_start, part_end))

    return hard


def clause_type_scores(text: str) -> dict[str, int]:
    scores: dict[str, int] = {}
    for clause_type, keywords in _TYPE_KEYWORDS.items():
        scores[clause_type] = sum(
            weight for keyword, weight in keywords.items() if keyword in text
        )
    return scores


def _classify(text: str) -> str:
    best_type = "other"
    best_score = 0
    for clause_type, score in clause_type_scores(text).items():
        if score > best_score:
            best_score = score
            best_type = clause_type
    return best_type if best_score >= 3 else "other"


def _summary(text: str) -> str:
    return _WS_RE.sub(" ", text).strip()[:40]


def extract_clauses(text: str) -> list[Clause]:
    text = text or ""
    units = _line_units(text)

    split_units: list[tuple[int, int]] = []
    for start, end in units:
        for sentence_start, sentence_end in _split_sentences(text, start, end):
            for comma_start, comma_end in _split_commas(text, sentence_start, sentence_end):
                split_units.extend(_split_long(text, comma_start, comma_end))

    units = _merge_short(split_units, text)
    if not units:
        units = [(0, len(text))]

    clauses: list[Clause] = []
    for index, (start, end) in enumerate(units, start=1):
        segment = text[start:end]
        if not segment.strip():
            continue
        clauses.append(
            Clause(
                id=f"c{index}",
                type=_classify(segment),
                text=segment,
                start=start,
                end=end,
                summary=_summary(segment),
            )
        )

    if clauses:
        return clauses

    return [
        Clause(
            id="c1",
            type="other",
            text=text,
            start=0,
            end=len(text),
            summary=_summary(text),
        )
    ]
