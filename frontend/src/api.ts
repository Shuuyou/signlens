import type {
  AnalyzeResponse,
  CaseInput,
  CreateCaseResponse,
  DemoCase,
  DemoRunResponse,
  Job,
  Report,
} from './types'

export class ApiError extends Error {
  status: number | null

  constructor(message: string, status: number | null = null) {
    super(message)
    this.name = 'ApiError'
    this.status = status
  }
}

function readError(data: unknown): string | null {
  if (data && typeof data === 'object' && 'error' in data) {
    const value = (data as { error?: unknown }).error
    if (typeof value === 'string' && value.trim()) return value
  }
  return null
}

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  let response: Response
  try {
    response = await fetch(path, init)
  } catch {
    throw new ApiError('无法连接分析服务，请确认后端已在 127.0.0.1:8000 启动。')
  }

  const raw = await response.text()
  let data: unknown = null
  if (raw) {
    try {
      data = JSON.parse(raw)
    } catch {
      data = raw
    }
  }

  if (!response.ok) {
    const message = readError(data) ?? `请求失败（HTTP ${response.status}）`
    throw new ApiError(message, response.status)
  }

  if (data === null && response.status !== 204) {
    throw new ApiError('服务返回了空响应。', response.status)
  }

  return data as T
}

function postJson<T>(path: string, body?: unknown): Promise<T> {
  return request<T>(path, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: body === undefined ? undefined : JSON.stringify(body),
  })
}

export function getDemoCases(): Promise<DemoCase[]> {
  return request<DemoCase[]>('/api/demo/cases')
}

export function getDemoInput(demoId: string): Promise<CaseInput> {
  return request<CaseInput>(`/api/demo/${encodeURIComponent(demoId)}`)
}

export function runDemo(demoId: string): Promise<DemoRunResponse> {
  return postJson<DemoRunResponse>(`/api/demo/${encodeURIComponent(demoId)}/run`)
}

export function createCase(input: CaseInput): Promise<CreateCaseResponse> {
  return postJson<CreateCaseResponse>('/api/cases', input)
}

export function analyzeCase(caseId: string): Promise<AnalyzeResponse> {
  return postJson<AnalyzeResponse>(`/api/cases/${encodeURIComponent(caseId)}/analyze`)
}

export function getJob(jobId: string): Promise<Job> {
  return request<Job>(`/api/jobs/${encodeURIComponent(jobId)}`, { cache: 'no-store' })
}

export function getReport(caseId: string): Promise<Report> {
  return request<Report>(`/api/cases/${encodeURIComponent(caseId)}`, { cache: 'no-store' })
}
