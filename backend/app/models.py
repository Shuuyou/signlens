from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, Field

RiskLevel = Literal["high", "medium", "low"]
Verdict = Literal["sign", "negotiate", "reject"]
JobStatus = Literal["queued", "running", "done", "error"]


class CompanyInput(BaseModel):
    name: str
    credit_code: Optional[str] = None


class CaseInput(BaseModel):
    company: CompanyInput
    contract_text: str
    chat_text: Optional[str] = None
    user_role: str = "founder"
    deal_value: Optional[float] = None
    stage: str = "prepay"


class Clause(BaseModel):
    id: str
    type: str
    text: str
    start: int = 0
    end: int = 0
    summary: str = ""


class LawRef(BaseModel):
    name: str
    article: str
    text: str
    source_url: str


class Risk(BaseModel):
    id: str
    clause_id: Optional[str] = None
    title: str
    level: RiskLevel
    why: str
    law: Optional[LawRef] = None
    suggestion: str
    confidence: float = 0.8


class Fact(BaseModel):
    key: str
    label: str
    value: str
    source_url: str
    retrieved_at: str
    severity: str = "info"


class CompanyEvidence(BaseModel):
    name: str
    matched_name: str
    demo: bool = True
    facts: list[Fact] = Field(default_factory=list)
    flags: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)


class Decision(BaseModel):
    verdict: Verdict
    confidence: float
    headline: str
    reasons: list[str] = Field(default_factory=list)
    conditions: list[str] = Field(default_factory=list)
    change_my_mind: list[str] = Field(default_factory=list)


class Report(BaseModel):
    case_id: str
    input: CaseInput
    company: CompanyEvidence
    clauses: list[Clause] = Field(default_factory=list)
    risks: list[Risk] = Field(default_factory=list)
    decision: Decision
    negotiation_sheet: list[str] = Field(default_factory=list)
    sources: list[str] = Field(default_factory=list)
    generated_at: str


class Job(BaseModel):
    job_id: str
    case_id: str
    status: JobStatus = "queued"
    stage: str = "queued"
    progress: int = 0
    error: Optional[str] = None
    report: Optional[Report] = None
