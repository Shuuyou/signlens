import { useEffect, useState } from 'react'
import { getJob } from '../api'
import { PIPELINE_STAGES } from '../constants'
import { SubXiaocha } from '../mascot/SubXiaocha'
import type { Job, Report } from '../types'

interface AnalyzingProps {
  jobId: string
  caseId: string
  companyName: string
  onDone: (report: Report | null) => void
  onRetry: () => Promise<void>
  onEdit: () => void
}

function messageOf(error: unknown): string {
  return error instanceof Error && error.message
    ? error.message
    : '发生了未知错误，请重试。'
}

export default function Analyzing({
  jobId,
  caseId,
  companyName,
  onDone,
  onRetry,
  onEdit,
}: AnalyzingProps) {
  const [job, setJob] = useState<Job | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [netError, setNetError] = useState<string | null>(null)
  const [retrying, setRetrying] = useState(false)

  useEffect(() => {
    let cancelled = false
    let timer: number | undefined
    let failures = 0

    setJob(null)
    setError(null)
    setNetError(null)

    const tick = async () => {
      try {
        const next = await getJob(jobId)
        if (cancelled) return
        failures = 0
        setNetError(null)
        setJob(next)

        if (next.status === 'done') {
          onDone(next.report ?? null)
          return
        }

        if (next.status === 'error') {
          setError(next.error?.trim() || '分析过程中出现错误，请重新分析。')
          return
        }

        timer = window.setTimeout(tick, 1000)
      } catch (err) {
        if (cancelled) return
        failures += 1
        if (failures >= 5) {
          setError(messageOf(err))
          return
        }
        setNetError(`连接中断，正在第 ${failures} / 5 次重试…`)
        timer = window.setTimeout(tick, 1200)
      }
    }

    void tick()

    return () => {
      cancelled = true
      if (timer !== undefined) window.clearTimeout(timer)
    }
  }, [jobId, onDone])

  const progress = error
    ? Math.max(0, Math.min(100, job?.progress ?? 0))
    : job?.status === 'done'
      ? 100
      : Math.max(0, Math.min(100, job?.progress ?? 0))

  const stageIndex = (() => {
    const stage = job?.stage ?? ''
    const found = PIPELINE_STAGES.findIndex((item) => item.key === stage)
    if (found >= 0) return found
    return Math.min(
      PIPELINE_STAGES.length - 1,
      Math.floor(progress / (100 / PIPELINE_STAGES.length)),
    )
  })()

  const finished = job?.status === 'done'
  const currentTitle = PIPELINE_STAGES[stageIndex]?.title ?? '解析条款'

  const handleRetry = async () => {
    if (retrying) return
    setRetrying(true)
    setError(null)
    try {
      await onRetry()
    } catch (err) {
      setError(messageOf(err))
      setRetrying(false)
    }
  }

  return (
    <div className="page analyzing-page">
      <div className="container page-container">
        <div className="page-head analyzing-head">
          <span className="eyebrow">第二步 / 共三步</span>
          <h1>正在体检这份合同</h1>
          <p>
            {companyName}
            <span className="dot-sep">·</span>
            案例 {caseId}
          </p>
          <div className="analyzing-mascot" aria-hidden="true">
            <SubXiaocha role="legal" size={64} state="thinking" decorative />
          </div>
        </div>

        <div className="analyzing-layout">
          <section className="panel analysis-panel">
            <div className="analysis-status">
              <div className="analysis-status-top">
                <div>
                  <span className="analysis-stage-label">
                    {error ? '分析中断' : finished ? '报告已生成' : `正在${currentTitle}`}
                  </span>
                  <div className="analysis-sub">
                    <span>
                      {error
                        ? '可以重新分析，或返回修改合同'
                        : `第 ${stageIndex + 1} / ${PIPELINE_STAGES.length} 阶段`}
                    </span>
                    {netError && !error && <span className="network-note">{netError}</span>}
                  </div>
                </div>
                <strong className="analysis-percent">
                  {progress}
                  <small>%</small>
                </strong>
              </div>
              <div
                className={`progress-track ${error ? 'is-error' : ''}`}
                role="progressbar"
                aria-valuemin={0}
                aria-valuemax={100}
                aria-valuenow={progress}
                aria-label="分析进度"
              >
                <span style={{ width: `${progress}%` }} />
              </div>
            </div>

            {error && (
              <div className="alert alert-error analysis-error" role="alert">
                <div>
                  <strong>分析没有完成</strong>
                  <p>{error}</p>
                </div>
                <div className="alert-actions">
                  <button
                    type="button"
                    className="btn btn-primary btn-sm"
                    onClick={handleRetry}
                    disabled={retrying}
                  >
                    {retrying ? '正在重试…' : '重新分析'}
                  </button>
                  <button type="button" className="btn btn-ghost btn-sm" onClick={onEdit}>
                    修改合同
                  </button>
                </div>
              </div>
            )}

            <ol className="pipeline">
              {PIPELINE_STAGES.map((stage, index) => {
                const isDone = finished || index < stageIndex
                const isActive = !finished && !error && index === stageIndex
                return (
                  <li
                    key={stage.key}
                    className={`pipeline-row ${isDone ? 'is-done' : ''} ${
                      isActive ? 'is-active' : ''
                    }`}
                  >
                    <span className="pipeline-marker">
                      {isDone ? '✓' : String(index + 1).padStart(2, '0')}
                    </span>
                    <div className="pipeline-copy">
                      <strong>{stage.title}</strong>
                      <p>{stage.description}</p>
                    </div>
                    <span className="pipeline-state">
                      {isDone ? '完成' : isActive ? '进行中' : '等待'}
                    </span>
                  </li>
                )
              })}
            </ol>
          </section>

          <aside className="analyzing-aside">
            <section className="panel panel-soft">
              <h2>本次体检包含</h2>
              <ul className="check-list">
                <li>合同条款切分与风险定位</li>
                <li>对方主体公开记录核查</li>
                <li>逐条风险的法条依据</li>
                <li>「签 / 谈 / 不签」结论与置信度</li>
                <li>一页纸谈判清单</li>
              </ul>
            </section>

            <section className="panel">
              <h2>案例信息</h2>
              <dl className="meta-list">
                <div>
                  <dt>对方主体</dt>
                  <dd>{companyName}</dd>
                </div>
                <div>
                  <dt>案例编号</dt>
                  <dd className="mono">{caseId}</dd>
                </div>
                <div>
                  <dt>进度同步</dt>
                  <dd>每 1 秒自动刷新</dd>
                </div>
              </dl>
            </section>

            <div className="aside-actions">
              <button type="button" className="btn btn-ghost btn-block" onClick={onEdit}>
                返回修改合同
              </button>
              <p>分析期间请保持页面打开。完成后会自动进入报告页。</p>
            </div>
          </aside>
        </div>
      </div>
    </div>
  )
}
