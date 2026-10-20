export type RiskLevel = 'high' | 'medium' | 'low'
export type Verdict = 'sign' | 'negotiate' | 'reject'
export type JobStatus = 'queued' | 'running' | 'done' | 'error'

export interface CompanyInput {
  name: string
  credit_code?: string | null
}

export interface CaseInput {
  company: CompanyInput
  contract_text: string
  chat_text?: string | null
  user_role: string
  deal_value?: number | null
  stage: string
}

export interface Clause {
  id: string
  type: string
  text: string
  start: number
  end: number
  summary: string
}

export interface LawRef {
  name: string
  article: string
  text: string
  source_url: string
}

export interface Risk {
  id: string
  clause_id?: string | null
  title: string
  level: RiskLevel
  why: string
  law?: LawRef | null
  suggestion: string
  confidence: number
}

export interface Fact {
  key: string
  label: string
  value: string
  source_url: string
  retrieved_at: string
  severity: string
}

export interface CompanyEvidence {
  name: string
  matched_name: string
  demo: boolean
  facts: Fact[]
  flags: string[]
  sources: string[]
}

export interface Decision {
  verdict: Verdict
  confidence: number
  headline: string
  reasons: string[]
  conditions: string[]
  change_my_mind: string[]
}

export interface Report {
  case_id: string
  input: CaseInput
  company: CompanyEvidence
  clauses: Clause[]
  risks: Risk[]
  decision: Decision
  negotiation_sheet: string[]
  sources: string[]
  generated_at: string
}

export interface Job {
  job_id: string
  case_id: string
  status: JobStatus
  stage: string
  progress: number
  error?: string | null
  report?: Report | null
}

export interface DemoCase {
  id: string
  title: string
  summary: string
  company: string
  expected_verdict: Verdict
}

export interface CreateCaseResponse {
  case_id: string
}

export interface AnalyzeResponse {
  job_id: string
}

export interface DemoRunResponse {
  case_id: string
  job_id: string
}
