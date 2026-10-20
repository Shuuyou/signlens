import { useCallback, useState } from 'react'
import * as api from './api'
import { FALLBACK_INPUTS } from './demoData'
import Home from './components/Home'
import Intake from './components/Intake'
import Analyzing from './components/Analyzing'
import ReportView from './components/ReportView'
import type { CaseInput, CompanyEvidence, DemoCase, Report, Verdict } from './types'

type View = 'home' | 'intake' | 'analyzing' | 'report' | 'error'

const EMPTY_COMPANY: CompanyEvidence = {
  name: '',
  matched_name: '',
  demo: true,
  facts: [],
  flags: [],
  sources: [],
}

const FLOW_STEPS = ['输入合同', '分析中', '体检报告']

function messageOf(error: unknown): string {
  return error instanceof Error && error.message
    ? error.message
    : '发生了未知错误，请重试。'
}

function normalizeReport(value: Report): Report {
  if (!value || typeof value !== 'object' || !value.decision || !value.input) {
    throw new Error('报告数据不完整，请重新分析。')
  }

  const verdict: Verdict = ['sign', 'negotiate', 'reject'].includes(value.decision.verdict)
    ? value.decision.verdict
    : 'negotiate'

  return {
    ...value,
    company: value.company ?? EMPTY_COMPANY,
    clauses: Array.isArray(value.clauses) ? value.clauses : [],
    risks: Array.isArray(value.risks) ? value.risks : [],
    decision: {
      ...value.decision,
      verdict,
      reasons: Array.isArray(value.decision.reasons) ? value.decision.reasons : [],
      conditions: Array.isArray(value.decision.conditions) ? value.decision.conditions : [],
      change_my_mind: Array.isArray(value.decision.change_my_mind)
        ? value.decision.change_my_mind
        : [],
    },
    negotiation_sheet: Array.isArray(value.negotiation_sheet) ? value.negotiation_sheet : [],
    sources: Array.isArray(value.sources) ? value.sources : [],
  }
}

export default function App() {
  const [view, setView] = useState<View>('home')
  const [intake, setIntake] = useState<CaseInput | null>(null)
  const [caseId, setCaseId] = useState<string | null>(null)
  const [jobId, setJobId] = useState<string | null>(null)
  const [syncReport, setSyncReport] = useState<Report | null>(null)
  const [syncError, setSyncError] = useState<string | null>(null)
  const [report, setReport] = useState<Report | null>(null)
  const [reportError, setReportError] = useState<string | null>(null)
  const [loadingReport, setLoadingReport] = useState(false)
  const [prefilled, setPrefilled] = useState(false)
  const [demoLoadingId, setDemoLoadingId] = useState<string | null>(null)
  const [homeError, setHomeError] = useState<string | null>(null)

  const restart = () => {
    setView('home')
    setIntake(null)
    setCaseId(null)
    setJobId(null)
    setReport(null)
    setReportError(null)
    setPrefilled(false)
    setHomeError(null)
    setDemoLoadingId(null)
  }

  const startBlank = () => {
    setIntake(null)
    setPrefilled(false)
    setHomeError(null)
    setReport(null)
    setReportError(null)
    setCaseId(null)
    setJobId(null)
    setView('intake')
  }

  const loadReport = useCallback(async (id: string) => {
    setLoadingReport(true)
    setReportError(null)
    try {
      const fetched = await api.getReport(id)
      const normalized = normalizeReport(fetched)
      setReport(normalized)
      setView('report')
    } catch (error) {
      setReportError(messageOf(error))
      setView('error')
    } finally {
      setLoadingReport(false)
    }
  }, [])

  const handleJobDone = useCallback(
    (incoming: Report | null) => {
      if (incoming) {
        try {
          const normalized = normalizeReport(incoming)
          setReport(normalized)
          setReportError(null)
          setView('report')
          return
        } catch (error) {
          setReportError(messageOf(error))
          setView('error')
          return
        }
      }
      if (!caseId) {
        setReportError('任务已完成，但缺少案例编号，无法读取报告。')
        setView('error')
        return
      }
      void loadReport(caseId)
    },
    [caseId, loadReport],
  )

  const handleRetryAnalysis = useCallback(async () => {
    if (!intake) throw new Error('缺少合同内容，无法重新分析。')
    setSyncReport(null)
    setSyncError(null)
    setJobId(null)
    const result = await api.analyzeNow(intake)
    const normalized = normalizeReport(result)
    setCaseId(normalized.case_id)
    setSyncReport(normalized)
  }, [intake])

  const handleStart = async (input: CaseInput) => {
    setHomeError(null)
    setReportError(null)
    setReport(null)
    setSyncReport(null)
    setSyncError(null)
    setJobId(null)
    setCaseId(null)
    setIntake(input)
    setPrefilled(false)
    const result = await api.analyzeNow(input)
    const normalized = normalizeReport(result)
    setCaseId(normalized.case_id)
    setReport(normalized)
    setView('report')
  }

  const handleDemoSelect = async (demo: DemoCase) => {
    if (demoLoadingId) return
    setDemoLoadingId(demo.id)
    setHomeError(null)
    try {
      let input: CaseInput | undefined = FALLBACK_INPUTS[demo.id]
      try {
        input = await api.getDemoInput(demo.id)
      } catch {
        // Fall back to bundled demo data when the API detail endpoint is unavailable.
      }

      if (!input?.company?.name || !input.contract_text) {
        throw new Error('该演示案例暂时无法载入，请返回首页手动填写。')
      }

      setIntake(input)
      setPrefilled(true)
      setReport(null)
      setReportError(null)
      setCaseId(null)
      setJobId(null)
      setView('intake')
    } catch (error) {
      setHomeError(messageOf(error))
    } finally {
      setDemoLoadingId(null)
    }
  }

  const goEdit = useCallback(() => {
    setIntake(intake ?? report?.input ?? null)
    setPrefilled(false)
    setReportError(null)
    setView('intake')
  }, [intake, report])

  const activeStep =
    view === 'intake' ? 0 : view === 'analyzing' ? 1 : view === 'report' || view === 'error' ? 2 : -1

  return (
    <div className="app">
      <header className="topbar no-print">
        <div className="container topbar-inner">
          <button type="button" className="brand" onClick={restart} aria-label="回到首页">
            <span className="brand-mark">签</span>
            <span className="brand-text">
              <strong>签前体检</strong>
              <small>SignLens</small>
            </span>
          </button>

          {view === 'home' ? (
            <span className="topbar-tagline">签合同前的决策体检</span>
          ) : (
            <nav className="flow-nav" aria-label="体检流程">
              {FLOW_STEPS.map((label, index) => {
                const isActive = activeStep === index
                const isDone = index < activeStep
                const clickable =
                  index === 0 || (index === 2 && report !== null && view !== 'report')
                return (
                  <button
                    key={label}
                    type="button"
                    className={`flow-step ${isActive ? 'is-active' : ''} ${
                      isDone ? 'is-done' : ''
                    }`}
                    onClick={
                      index === 0 ? goEdit : index === 2 ? () => setView('report') : undefined
                    }
                    disabled={!clickable}
                    aria-current={isActive ? 'step' : undefined}
                  >
                    <span className="flow-num">{isDone ? '✓' : index + 1}</span>
                    {label}
                  </button>
                )
              })}
            </nav>
          )}

          <span className="topbar-badge">DEMO</span>
        </div>
      </header>

      <main className="app-main">
        {view === 'home' && (
          <Home
            onStart={startBlank}
            onDemoSelect={handleDemoSelect}
            loadingDemoId={demoLoadingId}
            error={homeError}
          />
        )}

        {view === 'intake' && (
          <Intake
            initial={intake}
            prefilled={prefilled}
            onSubmit={handleStart}
            onBack={restart}
          />
        )}

        {view === 'analyzing' && intake && (
          <Analyzing
            jobId={jobId ?? ''}
            caseId={caseId ?? '同步分析'}
            companyName={intake.company.name || '对方主体'}
            syncMode
            syncReport={syncReport}
            syncError={syncError}
            onDone={handleJobDone}
            onRetry={handleRetryAnalysis}
            onEdit={goEdit}
          />
        )}

        {view === 'report' && report && (
          <ReportView report={report} onEdit={goEdit} onRestart={restart} />
        )}

        {view === 'error' && (
          <div className="page error-page">
            <div className="container page-container narrow-container">
              <div className="panel error-panel">
                <span className="eyebrow">报告不可用</span>
                <h1>报告没能打开</h1>
                <p className="error-message">{reportError ?? '发生了未知错误。'}</p>
                <p className="muted">
                  你的合同输入仍然保留。可以重试读取报告，或返回修改后重新分析。
                </p>
                <div className="error-actions">
                  {caseId && (
                    <button
                      type="button"
                      className="btn btn-primary"
                      onClick={() => void loadReport(caseId)}
                      disabled={loadingReport}
                    >
                      {loadingReport ? '正在读取…' : '重试读取报告'}
                    </button>
                  )}
                  <button type="button" className="btn btn-ghost" onClick={goEdit}>
                    返回修改
                  </button>
                  <button type="button" className="text-btn" onClick={restart}>
                    回到首页
                  </button>
                </div>
              </div>
            </div>
          </div>
        )}
      </main>

      <footer className="site-footer no-print">
        <div className="container footer-inner">
          <div className="footer-brand">
            <span className="brand-mark brand-mark-sm">签</span>
            <div>
              <strong>签前体检 · SignLens</strong>
              <p>合同决策体检，签前十分钟。</p>
            </div>
          </div>
          <p className="footer-note">
            演示数据已脱敏 · 本地规则引擎 · 本产品不构成法律意见
          </p>
        </div>
      </footer>
    </div>
  )
}
