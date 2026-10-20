import { useEffect, useMemo, useState } from 'react'
import { RISK_ORDER, ROLE_OPTIONS, VERDICT_META } from '../constants'
import { buildScenarios, simulate } from '../simulate'
import type { Report, RiskLevel } from '../types'
import ClauseDocument from './ClauseDocument'
import RiskCard from './RiskCard'
import WhatIf from './WhatIf'

interface ReportViewProps {
  report: Report
  onEdit: () => void
  onRestart: () => void
}

type RiskFilter = 'all' | RiskLevel

const RISK_FILTERS: { key: RiskFilter; label: string }[] = [
  { key: 'all', label: '全部' },
  { key: 'high', label: '高' },
  { key: 'medium', label: '中' },
  { key: 'low', label: '低' },
]

function formatDateTime(value: string): string {
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value || '—'
  const pad = (input: number) => String(input).padStart(2, '0')
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}`
}

function formatMoney(value: number | null | undefined): string | null {
  if (value == null || !Number.isFinite(value)) return null
  return `¥${new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(value)}`
}

function sourceLabel(source: string): string {
  if (!/^https?:\/\//i.test(source)) return source
  try {
    const url = new URL(source)
    const host = url.hostname.replace(/^www\./, '')
    return url.pathname === '/' ? host : `${host}${url.pathname}`
  } catch {
    return source
  }
}

function severityClass(severity: string): string {
  const value = severity.toLowerCase()
  if (value.includes('high') || value.includes('danger') || value.includes('严重')) return 'high'
  if (value.includes('medium') || value.includes('warn')) return 'medium'
  if (value.includes('low')) return 'low'
  return 'info'
}

function cleanSheetItem(item: string): string {
  return item.replace(/^\s*(?:\d+\s*[.、)．]|[-•])\s*/, '')
}

type SheetPriority = 'P0' | 'P1' | 'P2'

interface SheetEntry {
  priority: SheetPriority | null
  label: string
  text: string
}

function parseSheetItem(item: string): SheetEntry {
  const tagged = item.match(/^\s*(P[0-2])\s*([^｜|]*?)\s*[｜|]\s*([\s\S]+)$/)
  if (tagged) {
    return {
      priority: tagged[1] as SheetPriority,
      label: tagged[2].trim(),
      text: cleanSheetItem(tagged[3]),
    }
  }

  const bare = item.match(/^\s*(P[0-2])\s*[·:：-]?\s*([\s\S]*)$/)
  if (bare) {
    return {
      priority: bare[1] as SheetPriority,
      label: '',
      text: cleanSheetItem(bare[2]),
    }
  }

  return { priority: null, label: '', text: cleanSheetItem(item) }
}

export default function ReportView({ report, onEdit, onRestart }: ReportViewProps) {
  const [activeIds, setActiveIds] = useState<Set<string>>(() => new Set())
  const [filter, setFilter] = useState<RiskFilter>('all')
  const [showAllRisks, setShowAllRisks] = useState(false)

  useEffect(() => {
    setActiveIds(new Set())
    setFilter('all')
    setShowAllRisks(false)
    const reset = () => window.scrollTo({ top: 0, left: 0, behavior: 'auto' })
    reset()
    const first = window.setTimeout(reset, 80)
    const second = window.setTimeout(reset, 500)
    return () => {
      window.clearTimeout(first)
      window.clearTimeout(second)
    }
  }, [report.case_id])

  const risks = report.risks ?? []
  const clauses = report.clauses ?? []
  const decision = report.decision
  const company = report.company
  const meta = VERDICT_META[decision.verdict] ?? VERDICT_META.negotiate
  const confidence = Math.round(Math.max(0, Math.min(1, decision.confidence ?? 0)) * 100)

  const scenarios = useMemo(() => buildScenarios(report), [report])
  const simulation = useMemo(
    () => simulate(report, activeIds, scenarios),
    [report, activeIds, scenarios],
  )
  const mitigatedIds = useMemo(
    () => new Set(simulation.resolvedRiskIds),
    [simulation.resolvedRiskIds],
  )

  const sortedRisks = useMemo(
    () =>
      [...risks].sort(
        (a, b) => RISK_ORDER[a.level] - RISK_ORDER[b.level],
      ),
    [risks],
  )
  const riskOrdinal = useMemo(() => {
    const map = new Map<string, number>()
    sortedRisks.forEach((risk, index) => map.set(risk.id, index + 1))
    return map
  }, [sortedRisks])
  const visibleRisks =
    filter === 'all' ? sortedRisks : sortedRisks.filter((risk) => risk.level === filter)
  const displayedRisks =
    filter === 'all' && !showAllRisks ? visibleRisks.slice(0, 3) : visibleRisks

  const counts = useMemo(
    () => ({
      high: risks.filter((risk) => risk.level === 'high').length,
      medium: risks.filter((risk) => risk.level === 'medium').length,
      low: risks.filter((risk) => risk.level === 'low').length,
    }),
    [risks],
  )

  const clauseById = useMemo(
    () => new Map(clauses.map((clause) => [clause.id, clause])),
    [clauses],
  )

  const sourceItems = useMemo(() => {
    const set = new Set<string>()
    ;(report.sources ?? []).forEach((source) => source && set.add(source))
    ;(company.sources ?? []).forEach((source) => source && set.add(source))
    risks.forEach((risk) => {
      if (risk.law?.source_url) set.add(risk.law.source_url)
    })
    return Array.from(set)
  }, [report.sources, company.sources, risks])

  const sheetItems = useMemo(() => {
    if (report.negotiation_sheet?.length) return report.negotiation_sheet
    return risks.slice(0, 6).map((risk) => risk.suggestion)
  }, [report.negotiation_sheet, risks])

  const reasons = decision.reasons ?? []
  const conditions = decision.conditions ?? []
  const flags = company.flags ?? []
  const facts = company.facts ?? []
  const money = formatMoney(report.input?.deal_value)
  const roleLabel =
    ROLE_OPTIONS.find((option) => option.value === report.input?.user_role)?.label ?? '未填写'

  const toggleScenario = (id: string) => {
    setActiveIds((current) => {
      const nextSet = new Set(current)
      if (nextSet.has(id)) nextSet.delete(id)
      else nextSet.add(id)
      return nextSet
    })
  }

  const handlePrint = () => {
    const folds = Array.from(document.querySelectorAll<HTMLDetailsElement>('.law-fold'))
    const states = folds.map((fold) => fold.open)
    folds.forEach((fold) => {
      fold.open = true
    })
    const restore = () => {
      folds.forEach((fold, index) => {
        fold.open = states[index] ?? false
      })
    }
    window.addEventListener('afterprint', restore, { once: true })
    window.print()
  }

  return (
    <div className="page report-page">
      <div className="container">
        <div className="print-only print-head">
          <div>
            <strong>SignLens · 签前体检</strong>
            <span>合同决策体检报告</span>
          </div>
          <span>
            案例 {report.case_id} · {formatDateTime(report.generated_at)}
          </span>
        </div>

        <div className="report-toolbar no-print">
          <div className="toolbar-left">
            <button type="button" className="back-link" onClick={onEdit}>
              ← 修改输入
            </button>
            <span className="toolbar-case mono">案例 {report.case_id}</span>
          </div>
          <nav className="report-anchors" aria-label="报告导航">
            <a href="#verdict">结论</a>
            <a href="#risks">风险</a>
            <a href="#whatif">推演</a>
            <a href="#negotiation">谈判单</a>
          </nav>
          <div className="toolbar-actions">
            <button type="button" className="btn btn-ghost btn-sm" onClick={onRestart}>
              重新体检
            </button>
            <button
              type="button"
              className="btn btn-primary btn-sm"
              onClick={handlePrint}
            >
              打印报告
            </button>
          </div>
        </div>

        <section id="verdict" className={`verdict-banner verdict-${decision.verdict}`}>
          <div className="verdict-seal" aria-hidden="true">
            {meta.word}
          </div>
          <div className="verdict-main">
            <div className="verdict-kicker">
              <span>{meta.label}</span>
              <span className="confidence-chip">置信度 {confidence}%</span>
            </div>
            <h1>{decision.headline}</h1>
            <p className="verdict-caption">{meta.caption}</p>

            <div className="verdict-counts" aria-label="风险计数">
              <span className="verdict-count count-high">高风险 {counts.high}</span>
              <span className="verdict-count count-medium">中风险 {counts.medium}</span>
              <span className="verdict-count count-low">低风险 {counts.low}</span>
            </div>

            {reasons.length > 0 && (
              <ul className="verdict-reasons">
                {reasons.map((reason, index) => (
                  <li key={`${index}-${reason}`}>
                    <span aria-hidden="true">{String(index + 1).padStart(2, '0')}</span>
                    {reason}
                  </li>
                ))}
              </ul>
            )}

            {conditions.length > 0 && (
              <div className="verdict-conditions">
                <strong>继续推进的前提</strong>
                <ul>
                  {conditions.map((condition, index) => (
                    <li key={`${index}-${condition}`}>{condition}</li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        </section>

        <div className="report-meta">
          <div className="meta-block">
            <span>对方主体</span>
            <strong>{company.matched_name || company.name || '未填写'}</strong>
            {company.demo && <em className="demo-badge">演示数据</em>}
          </div>
          <div className="meta-block">
            <span>交易金额</span>
            <strong>{money ?? '未填写'}</strong>
          </div>
          <div className="meta-block">
            <span>你的身份</span>
            <strong>{roleLabel}</strong>
          </div>
          <div className="meta-block">
            <span>生成时间</span>
            <strong>{formatDateTime(report.generated_at)}</strong>
          </div>
        </div>

        <p className="print-only print-cover-note">
          本报告包含关键风险 {risks.length} 项、条款原文 {clauses.length} 条、谈判推演{' '}
          {scenarios.length} 项、谈判清单 {sheetItems.length} 条。以下为完整内容。
        </p>

        <div className="report-layout">
          <div className="report-main">
            <section className="panel report-section" id="risks">
              <div className="section-title-row">
                <div>
                  <span className="eyebrow">风险清单</span>
                  <h2>
                    关键风险
                    <span className="count-badge">{risks.length}</span>
                  </h2>
                  <p className="section-sub">
                    按等级排序。展开「法条依据」可查看对应法律条文，点击对应条款可回到原文定位。
                  </p>
                </div>
                <div className="risk-filters no-print" role="group" aria-label="按风险等级筛选">
                  {RISK_FILTERS.map((item) => {
                    const count =
                      item.key === 'all' ? risks.length : counts[item.key as RiskLevel]
                    return (
                      <button
                        key={item.key}
                        type="button"
                        className={`filter-chip ${filter === item.key ? 'is-active' : ''}`}
                        onClick={() => setFilter(item.key)}
                      >
                        {item.label}
                        <span>{count}</span>
                      </button>
                    )
                  })}
                </div>
              </div>

              <div className="risk-list">
                {displayedRisks.length > 0 ? (
                  displayedRisks.map((risk) => (
                    <RiskCard
                      key={risk.id}
                      risk={risk}
                      index={riskOrdinal.get(risk.id)}
                      clause={risk.clause_id ? clauseById.get(risk.clause_id) : undefined}
                      mitigated={mitigatedIds.has(risk.id)}
                    />
                  ))
                ) : (
                  <p className="empty-note">
                    {risks.length === 0
                      ? '未发现明显高风险条款，仍建议核对对方主体与付款路径。'
                      : '当前筛选下没有风险条款。'}
                  </p>
                )}
              </div>
              {filter === 'all' && visibleRisks.length > 3 && (
                <button
                  type="button"
                  className="risk-show-more"
                  onClick={() => setShowAllRisks((value) => !value)}
                >
                  {showAllRisks
                    ? '收起，只看最关键的 3 条'
                    : `展开全部 ${visibleRisks.length} 条风险`}
                </button>
              )}
            </section>

            <section className="panel report-section" id="clauses">
              <div className="section-title-row">
                <div>
                  <span className="eyebrow">合同原文</span>
                  <h2>条款原文</h2>
                  <p className="section-sub">
                    已按风险等级高亮命中条款。打印时会展开全文，便于逐条核对。
                  </p>
                </div>
              </div>
              <ClauseDocument report={report} />
            </section>

            <WhatIf
              report={report}
              activeIds={activeIds}
              simulation={simulation}
              onToggle={toggleScenario}
              onReset={() => setActiveIds(new Set())}
              onAcceptAll={() => setActiveIds(new Set(scenarios.map((scenario) => scenario.id)))}
            />

            <section className="panel report-section sheet-panel" id="negotiation">
              <div className="sheet-header">
                <div>
                  <span className="sheet-kicker">NEGOTIATION SHEET / 一页纸</span>
                  <h2>谈判清单</h2>
                  <p>按优先级排序。先谈底线条款，再谈金额与期限。</p>
                </div>
                <div className="sheet-meta">
                  <strong>{company.matched_name || company.name}</strong>
                  <span>{formatDateTime(report.generated_at)}</span>
                </div>
              </div>

              {sheetItems.length > 0 ? (
                <ol className="sheet-list">
                  {sheetItems.map((item, index) => {
                    const entry = parseSheetItem(item)
                    return (
                      <li
                        key={`${index}-${item}`}
                        className={entry.priority ? `priority-${entry.priority.toLowerCase()}` : undefined}
                      >
                        <span className="sheet-num">{String(index + 1).padStart(2, '0')}</span>
                        <div className="sheet-body">
                          {entry.priority && (
                            <span className="sheet-priority">
                              {entry.priority}
                              {entry.label ? ` ${entry.label}` : ''}
                            </span>
                          )}
                          <p>{entry.text}</p>
                        </div>
                      </li>
                    )
                  })}
                </ol>
              ) : (
                <p className="empty-note">暂无需要谈判的条款。</p>
              )}

              <div className="sheet-footer">
                <span>SignLens · 签前体检</span>
                <span>本清单不构成法律意见</span>
              </div>
            </section>
          </div>

          <aside className="report-aside">
            <section className="panel company-panel">
              <div className="panel-head">
                <h2>主体核查</h2>
                {company.demo && <span className="demo-badge">演示数据</span>}
              </div>
              <div className="company-name">{company.matched_name || company.name}</div>
              {company.name && company.matched_name && company.name !== company.matched_name && (
                <p className="company-alias">输入名称：{company.name}</p>
              )}

              {flags.length > 0 && (
                <div className="flag-list">
                  {flags.map((flag) => (
                    <span className="flag-chip" key={flag}>
                      {flag}
                    </span>
                  ))}
                </div>
              )}

              {facts.length > 0 ? (
                <dl className="fact-list">
                  {facts.map((fact, index) => (
                    <div className="fact-item" key={`${fact.key}-${index}`}>
                      <span
                        className={`fact-dot severity-${severityClass(fact.severity)}`}
                        aria-hidden="true"
                      />
                      <div>
                        <dt>{fact.label}</dt>
                        <dd>{fact.value}</dd>
                        <div className="fact-meta">
                          {fact.retrieved_at && <span>获取于 {fact.retrieved_at}</span>}
                          {fact.source_url && (
                            <a href={fact.source_url} target="_blank" rel="noreferrer">
                              来源 ↗
                            </a>
                          )}
                        </div>
                      </div>
                    </div>
                  ))}
                </dl>
              ) : (
                <p className="muted">未获取到公开主体记录。</p>
              )}
            </section>

            <section className="panel source-panel">
              <div className="panel-head">
                <h2>来源与口径</h2>
                <span>{sourceItems.length} 条</span>
              </div>
              {sourceItems.length > 0 ? (
                <ul className="source-list">
                  {sourceItems.map((source) => (
                    <li key={source}>
                      {/^https?:\/\//i.test(source) ? (
                        <a href={source} target="_blank" rel="noreferrer" title={source}>
                          {sourceLabel(source)}
                        </a>
                      ) : (
                        <span>{source}</span>
                      )}
                    </li>
                  ))}
                </ul>
              ) : (
                <p className="muted">本报告基于合同文本与本地规则库生成。</p>
              )}
              <p className="source-note">
                {company.demo
                  ? '主体核查使用脱敏演示数据；真实模式对接官方公开源。'
                  : '主体数据来自公开渠道，检索时间见主体核查。'}
              </p>
            </section>

            <section className="panel disclaimer-panel">
              <h2>不构成法律意见</h2>
              <p>
                本报告由规则引擎自动生成，仅用于交易决策参考，不构成法律意见，也不能替代执业律师的审查。涉及重大金额、担保、股权或诉讼风险时，请咨询专业律师。
              </p>
            </section>

            <div className="aside-actions no-print">
              <button
                type="button"
                className="btn btn-primary btn-block"
                onClick={handlePrint}
              >
                打印 / 导出 PDF
              </button>
              <button type="button" className="btn btn-ghost btn-block" onClick={onEdit}>
                修改输入重新体检
              </button>
            </div>
          </aside>
        </div>

        <footer className="report-footer">
          <span>SignLens · 签前体检</span>
          <p>
            演示数据已脱敏。报告基于你提供的合同文本与本地规则引擎生成，不构成法律意见。
          </p>
        </footer>
      </div>
    </div>
  )
}
