"""Offline counterparty evidence lookup for SignLens.

Profiles live in ``data/companies/*.json``. Each profile only records facts that
a user could re-check on an official public entry point (国家企业信用信息公示系统、
中国执行信息公开网、中国裁判文书网、信用中国); the demo never calls the network.

Matching order: exact name -> exact alias -> containment (either direction),
picking the longest matching token so "杭州云采供应链" hits the full profile
instead of a shorter alias. Unknown names get a generic "needs manual check"
profile so the pipeline stays deterministic and always has evidence to show.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.models import CompanyEvidence, Fact

_BACKEND_DIR = Path(__file__).resolve().parents[2]
_ROOT_DIR = _BACKEND_DIR.parent

COMPANY_DIRS: tuple[Path, ...] = (
    _ROOT_DIR / "data" / "companies",
    _BACKEND_DIR / "data" / "companies",
)

GSXT_URL = "https://www.gsxt.gov.cn/"
WENSHU_URL = "https://wenshu.court.gov.cn/"
CREDIT_CHINA_URL = "https://www.creditchina.gov.cn/"
ZHIXING_URL = "https://zxgk.court.gov.cn/"

DEFAULT_RETRIEVED_AT = "2026-10-18"
GENERIC_FLAG = "未收录，需人工核验"

# 输入本身就是这些泛称时，包含匹配没有意义
_GENERIC_TOKENS = frozenset(
    {"公司", "有限公司", "有限责任公司", "股份有限公司", "集团", "企业"}
)

# path -> (mtime, size, profile or None)
_CACHE: dict[Path, tuple[float, int, dict[str, Any] | None]] = {}


def _normalize(text: str) -> str:
    """Lowercase latin, unify brackets and drop whitespace/punctuation noise."""
    text = str(text or "").strip().lower()
    for old, new in (
        ("（", "("),
        ("）", ")"),
        ("　", ""),
        (" ", ""),
        ("\t", ""),
    ):
        text = text.replace(old, new)
    return text


def _read_profile(path: Path) -> dict[str, Any] | None:
    try:
        stat = path.stat()
    except OSError:
        return None
    cached = _CACHE.get(path)
    if cached and cached[0] == stat.st_mtime and cached[1] == stat.st_size:
        return cached[2]
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError):
        raw = None
    profile = raw if isinstance(raw, dict) and str(raw.get("name") or "").strip() else None
    _CACHE[path] = (stat.st_mtime, stat.st_size, profile)
    return profile


def _load_profiles() -> list[dict[str, Any]]:
    profiles: list[dict[str, Any]] = []
    seen: set[str] = set()
    for directory in COMPANY_DIRS:
        if not directory.is_dir():
            continue
        for path in sorted(directory.glob("*.json")):
            profile = _read_profile(path)
            if profile is None:
                continue
            name = str(profile.get("name") or "").strip()
            if name in seen:
                continue
            seen.add(name)
            profiles.append(profile)
    return profiles


def _tokens(profile: dict[str, Any]) -> list[str]:
    raw_tokens = [profile.get("name")]
    aliases = profile.get("aliases")
    if isinstance(aliases, list):
        raw_tokens.extend(aliases)
    tokens: list[str] = []
    for token in raw_tokens:
        normalized = _normalize(str(token or ""))
        if normalized and normalized not in tokens:
            tokens.append(normalized)
    return tokens


def _find_profile(name: str) -> dict[str, Any] | None:
    query = _normalize(name)
    if not query:
        return None

    profiles = _load_profiles()
    for profile in profiles:
        if query in _tokens(profile):
            return profile

    if len(query) < 2 or query in _GENERIC_TOKENS:
        return None

    best: dict[str, Any] | None = None
    best_length = 0
    for profile in profiles:
        for token in _tokens(profile):
            if token in _GENERIC_TOKENS:
                continue
            if (token in query or query in token) and len(token) > best_length:
                best = profile
                best_length = len(token)
    return best


def _fact(raw: Any, default_source: str) -> Fact | None:
    if not isinstance(raw, dict):
        return None
    value = str(raw.get("value") or "").strip()
    if not value:
        return None
    key = str(raw.get("key") or "").strip() or "fact"
    return Fact(
        key=key,
        label=str(raw.get("label") or key),
        value=value,
        source_url=str(raw.get("source_url") or default_source),
        retrieved_at=str(raw.get("retrieved_at") or DEFAULT_RETRIEVED_AT),
        severity=str(raw.get("severity") or "info"),
    )


def _sources(profile: dict[str, Any], facts: list[Fact]) -> list[str]:
    urls: list[str] = []
    raw_sources = profile.get("sources")
    if isinstance(raw_sources, list):
        urls.extend(str(url) for url in raw_sources if str(url or "").strip())
    urls.extend(fact.source_url for fact in facts)
    ordered: list[str] = []
    for url in urls:
        if url and url not in ordered:
            ordered.append(url)
    return ordered


def _from_profile(profile: dict[str, Any], name: str) -> CompanyEvidence:
    canonical = str(profile.get("name") or "").strip()
    default_source = str(profile.get("source_url") or GSXT_URL)
    facts = [fact for fact in (_fact(raw, default_source) for raw in profile.get("facts") or []) if fact]
    flags = [str(flag).strip() for flag in profile.get("flags") or [] if str(flag or "").strip()]
    return CompanyEvidence(
        name=name.strip() or canonical,
        matched_name=canonical,
        demo=bool(profile.get("demo", True)),
        facts=facts,
        flags=flags,
        sources=_sources(profile, facts),
    )


def _fallback(name: str) -> CompanyEvidence:
    display = name.strip() or "未填写公司名称"
    retrieved_at = DEFAULT_RETRIEVED_AT
    facts = [
        Fact(
            key="coverage",
            label="收录情况",
            value=f"演示库未收录「{display}」，无法自动核验工商、涉诉与信用记录",
            source_url=GSXT_URL,
            retrieved_at=retrieved_at,
            severity="warn",
        ),
        Fact(
            key="registry_check",
            label="工商核验",
            value=(
                "建议到国家企业信用信息公示系统核验：营业执照名称、统一社会信用代码、"
                "成立日期、参保人数、经营异常名录与行政处罚"
            ),
            source_url=GSXT_URL,
            retrieved_at=retrieved_at,
            severity="info",
        ),
        Fact(
            key="litigation_check",
            label="涉诉与信用核验",
            value=(
                "建议在中国裁判文书网检索合同纠纷与涉诉记录，"
                "在信用中国查询失信被执行与行政处罚信息"
            ),
            source_url=WENSHU_URL,
            retrieved_at=retrieved_at,
            severity="info",
        ),
    ]
    return CompanyEvidence(
        name=display,
        matched_name=display,
        demo=True,
        facts=facts,
        flags=[GENERIC_FLAG],
        sources=[GSXT_URL, WENSHU_URL, CREDIT_CHINA_URL],
    )


def get_company_evidence(name: str) -> CompanyEvidence:
    """Return the demo profile for ``name``, or a generic verification checklist."""
    profile = _find_profile(name)
    if profile is None:
        return _fallback(name)
    return _from_profile(profile, name)
