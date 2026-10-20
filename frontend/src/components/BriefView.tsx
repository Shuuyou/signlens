import { useCallback, useEffect, useMemo, useRef, useState, type ReactNode } from 'react'
import { RISK_ORDER, ROLE_OPTIONS, VERDICT_META } from '../constants'
import { buildScenarios, simulate } from '../simulate'
import type { Clause, Fact, Report, Risk, RiskLevel, Verdict } from '../types'

interface BriefViewProps {
  report: Report
  onEdit: () => void
  onRestart: () => void
}

const TOP_RISKS = 3
const LEVEL_LABEL: Record<RiskLevel, string> = { high: '高风险', medium: '中风险', low: '低风险' }
const LEVEL_RANK: Record<RiskLevel, number> = { high: 3, medium: 2, low: 1 }

function formatMoney(value: number | null | undefined): string | null {
  if (value == null || !Number.isFinite(value)) return null
  return `¥${new Intl.NumberFormat('zh-CN', { maximumFractionDigits: 2 }).format(value)}`
}

function gist(text: string): string {
  const first = text.split(/[。；]/)[0].trim()
  return first.length > 52 ? `${first.slice(0, 52)}…` : first
}

function factRank(fact: Fact): number {
  const value = fact.severity.toLowerCase()
  if (value.includes('high')) return 0
  if (value.includes('warn') || value.includes('medium')) return 1
  return 2
}

function sourceHost(url: string): string {
  try {
    return new URL(url).hostname.replace(/^www\./, '')
  } catch {
    return url
  }
}

function buildHeadline(
  verdict: Verdict,
  remaining: Risk[],
  companyAlerts: string[],
): string {
  const opener = verdict === 'reject' ? '先别签。' : verdict === 'negotiate' ? '谈完再签。' : '可以签。'
  if (remaining.length === 0) {
    if (companyAlerts.length > 0) {
      return `条款上的问题都谈妥了。但对方有${companyAlerts.slice(0, 2).join('和')}，付款前建议再要一份担保。`
    }
    return verdict === 'sign' ? '可以签。没有发现需要先改的条款。' : '条款上的问题都谈妥了，签之前把约定写进合同。'
  }
  if (verdict === 'sign') {
    return `${opener}还剩 ${remaining.length} 处小问题，不影响推进。`
  }
  const top = remaining.slice(0, 2).map((risk) => risk.title).join('和')
  const alert =
    companyAlerts.length > 0 ? `，而且对方有${companyAlerts.slice(0, 2).join('和')}` : ''
  return `${opener}最要紧的是${top}${alert}。`
}

interface DrawerProps {
  report: Report
  focusClauseId: string | null
  resolvedClauseIds: ReadonlySet<string>
  riskByClause: ReadonlyMap<string, Risk>
  onClose: () => void
  onPick: (riskId: string) => void
}

function ContractDrawer({
  report,
  focusClauseId,
  resolvedClauseIds,
  riskByClause,
  onClose,
  onPick,
}: DrawerProps) {
  const text = report.input?.contract_text ?? ''
  const bodyRef = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const onKey = (event: KeyboardEvent) => {
      if (event.key === 'Escape') onClose()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])

  useEffect(() => {
    if (!focusClauseId) return
    const timer = window.setTimeout(() => {
      const el = bodyRef.current?.querySelector(`[data-clause="${focusClauseId}"]`)
      el?.scrollIntoView({ block: 'center', behavior: 'smooth' })
    }, 120)
    return () => window.clearTimeout(timer)
  }, [focusClauseId])

  const ranges = useMemo(() => {
    const list: { clause: Clause; start: number; end: number }[] = []
    for (const clause of report.clauses ?? []) {
      const start = Number(clause.start)
      const end = Number(clause.end)
      if (Number.isFinite(start) && Number.isFinite(end) && start >= 0 && end > start && end <= text.length) {
        list.push({ clause, start, end })
      }
    }
    return list.sort((a, b) => a.start - b.start)
  }, [report.clauses, text])

  const nodes: ReactNode[] = []
  let cursor = 0
  for (const range of ranges) {
    if (range.start < cursor) continue
    if (range.start > cursor) nodes.push(<span key={`p${cursor}`}>{text.slice(cursor, range.start)}</span>)
    const risk = riskByClause.get(range.clause.id)
    const slice = text.slice(range.start, range.end)
    if (risk) {
      const resolved = resolvedClauseIds.has(range.clause.id)
      nodes.push(
        <mark
          key={range.clause.id}
          data-clause={range.clause.id}
          className={`bf-mark bf-mark-${risk.level} ${resolved ? 'is-resolved' : ''} ${
            focusClauseId === range.clause.id ? 'is-focus' : ''
          }`}
          title={risk.title}
          onClick={() => onPick(risk.id)}
        >
          {slice}
        </mark>,
      )
    } else {
      nodes.push(<span key={range.clause.id}>{slice}</span>)
    }
    cursor = range.end
  }
  if (cursor < text.length) nodes.push(<span key="tail">{text.slice(cursor)}</span>)

  return (
    <div className="bf-drawer-layer no-print">
      <div className="bf-scrim" onClick={onClose} />
      <aside className="bf-drawer" role="dialog" aria-label="合同原文">
        <header>
          <div>
            <strong>合同原文</strong>
            <span>标色的是命中风险的条款，点一下回到对应风险。</span>
          </div>
          <button type="button" className="bf-icon-btn" onClick={onClose} aria-label="关闭">
            ✕
          </button>
        </header>
        <div className="bf-drawer-body" ref={bodyRef}>
          <div className="bf-contract">{nodes.length > 0 ? nodes : text}</div>
        </div>
      </aside>
    </div>
  )
}

export default function BriefView({ report, onEdit, onRestart }: BriefViewProps) {
  const risks = report.risks ?? []
  const company = report.company
  const decision = report.decision

  const sortedRisks = useMemo(
    () => [...risks].sort((a, b) => RISK_ORDER[a.level] - RISK_ORDER[b.level]),
    [risks],
  )
  const ordinal = useMemo(() => {
    const map = new Map<string, number>()
    sortedRisks.forEach((risk, index) => map.set(risk.id, index + 1))
    return map
  }, [sortedRisks])
  const clauseById = useMemo(
    () => new Map((report.clauses ?? []).map((clause) => [clause.id, clause])),
    [report.clauses],
  )

  const [checked, setChecked] = useState<Set<string>>(() => new Set())
  const [openRisks, setOpenRisks] = useState<Set<string>>(
    () => new Set(sortedRisks[0] ? [sortedRisks[0].id] : []),
  )
  const [showRest, setShowRest] = useState(false)
  const [drawer, setDrawer] = useState<{ clauseId: string | null } | null>(null)
  const [printing, setPrinting] = useState(false)
  const [copied, setCopied] = useState(false)

  useEffect(() => {
    setChecked(new Set())
    setOpenRisks(new Set(sortedRisks[0] ? [sortedRisks[0].id] : []))
    setShowRest(false)
    setDrawer(null)
    window.scrollTo({ top: 0, left: 0, behavior: 'auto' })
    const timer = window.setTimeout(() => window.scrollTo({ top: 0, left: 0, behavior: 'auto' }), 80)
    return () => window.clearTimeout(timer)
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [report.case_id])

  const scenarios = useMemo(() => buildScenarios(report), [report])
  const sim = useMemo(() => simulate(report, checked, scenarios), [report, checked, scenarios])
  const resolved = useMemo(() => new Set(sim.resolvedRiskIds), [sim.resolvedRiskIds])

  const remaining = useMemo(
    () => sortedRisks.filter((risk) => !resolved.has(risk.id)),
    [sortedRisks, resolved],
  )
  const baseHigh = risks.filter((risk) => risk.level === 'high').length

  const facts = useMemo(
    () => [...(company.facts ?? [])].sort((a, b) => factRank(a) - factRank(b)),
    [company.facts],
  )
  const companyAlerts = useMemo(
    () => facts.filter((fact) => factRank(fact) === 0).map((fact) => fact.label),
    [facts],
  )

  const verdict = sim.verdict
  const meta = VERDICT_META[verdict] ?? VERDICT_META.negotiate
  const baseMeta = VERDICT_META[decision.verdict] ?? VERDICT_META.negotiate
  const headline = buildHeadline(verdict, remaining, companyAlerts)

  const riskByClause = useMemo(() => {
    const map = new Map<string, Risk>()
    for (const risk of sortedRisks) {
      if (!risk.clause_id) continue
      const current = map.get(risk.clause_id)
      if (!current || LEVEL_RANK[risk.level] > LEVEL_RANK[current.level]) map.set(risk.clause_id, risk)
    }
    return map
  }, [sortedRisks])
  const resolvedClauseIds = useMemo(() => {
    const byClause = new Map<string, Risk[]>()
    for (const risk of sortedRisks) {
      if (!risk.clause_id) continue
      byClause.set(risk.clause_id, [...(byClause.get(risk.clause_id) ?? []), risk])
    }
    const done = new Set<string>()
    byClause.forEach((list, id) => {
      if (list.every((risk) => resolved.has(risk.id))) done.add(id)
    })
    return done
  }, [sortedRisks, resolved])

  const sourceCount = useMemo(() => {
    const set = new Set<string>()
    ;(report.sources ?? []).forEach((s) => s && set.add(s))
    ;(company.sources ?? []).forEach((s) => s && set.add(s))
    risks.forEach((risk) => risk.law?.source_url && set.add(risk.law.source_url))
    return set
  }, [report.sources, company.sources, risks])

  const roleLabel = ROLE_OPTIONS.find((option) => option.value === report.input?.user_role)?.label
  const money = formatMoney(report.input?.deal_value)

  const toggleCheck = (id: string) =>
    setChecked((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  const toggleRisk = (id: string) =>
    setOpenRisks((current) => {
      const next = new Set(current)
      if (next.has(id)) next.delete(id)
      else next.add(id)
      return next
    })

  const focusRisk = useCallback(
    (riskId: string) => {
      setDrawer(null)
      setShowRest(true)
      setOpenRisks((current) => new Set(current).add(riskId))
      window.setTimeout(() => {
        const el = document.getElementById(`risk-${riskId}`)
        if (!el) return
        el.scrollIntoView({ behavior: 'smooth', block: 'center' })
        el.classList.add('is-flash')
        window.setTimeout(() => el.classList.remove('is-flash'), 1600)
      }, 60)
    },
    [],
  )

  const copyChecklist = async () => {
    const lines = [
      `【签前体检 · ${company.matched_name || company.name}】`,
      `当前结论：${baseMeta.label}`,
      '签之前，需要对方答应：',
      ...scenarios.map((scenario, index) => `${index + 1}. ${scenario.label}（${scenario.detail}）`),
    ]
    try {
      await navigator.clipboard.writeText(lines.join('\n'))
      setCopied(true)
      window.setTimeout(() => setCopied(false), 1800)
    } catch {
      setCopied(false)
    }
  }

  const handlePrint = () => {
    setPrinting(true)
    const done = () => setPrinting(false)
    window.addEventListener('afterprint', done, { once: true })
    window.setTimeout(() => window.print(), 150)
  }

  const visibleRisks = showRest || printing ? sortedRisks : sortedRisks.slice(0, TOP_RISKS)
  const hiddenCount = sortedRisks.length - visibleRisks.length
  const keyFacts = facts.slice(0, 3)
  const moreFacts = facts.slice(3)

  return (
    <div className="bf-page">
      <div className="bf-wrap">
        <div className="bf-bar no-print">
          <button type="button" className="bf-link" onClick={onEdit}>
            ← 修改输入
          </button>
          <div className="bf-bar-actions">
            <button type="button" className="bf-link" onClick={onRestart}>
              重新体检
            </button>
            <button type="button" className="bf-btn bf-btn-ghost" onClick={handlePrint}>
              导出 PDF
            </button>
          </div>
        </div>

        <section id="verdict" className="bf-lead" aria-live="polite">
          <p className="bf-context">
            {company.matched_name || company.name}
            {money ? ` · ${money}` : ''}
            {roleLabel ? ` · 以${roleLabel}身份` : ''}
          </p>
          <div className="bf-stamp-row">
            <span className={`bf-stamp bf-${verdict}`}>{meta.label}</span>
            {sim.changed && (
              <span className="bf-shift">
                由「{baseMeta.label}」改判，因为你勾选了 {sim.activeCount} 项
              </span>
            )}
          </div>
          <h1 className="bf-headline">{headline}</h1>
          <p className="bf-trace">
            读了 {report.clauses?.length ?? 0} 段条款，命中 {risks.length} 条风险，对照 {sourceCount.size} 个公开来源。
          </p>
        </section>

        <section id="actions" className="bf-section">
          <header className="bf-section-head">
            <div>
              <h2>先让对方答应这几件事</h2>
              <p>勾上一项，下面的风险和上面的结论会跟着变。</p>
            </div>
            <div className="bf-section-tools no-print">
              <button
                type="button"
                className="bf-link"
                onClick={() =>
                  setChecked(
                    checked.size === scenarios.length
                      ? new Set()
                      : new Set(scenarios.map((scenario) => scenario.id)),
                  )
                }
              >
                {checked.size === scenarios.length ? '清空' : '全选'}
              </button>
              <button type="button" className="bf-link" onClick={() => void copyChecklist()}>
                {copied ? '已复制' : '复制成谈判清单'}
              </button>
            </div>
          </header>

          <ul className="bf-checks">
            {scenarios.map((scenario) => {
              const on = checked.has(scenario.id)
              const covers = scenario.riskIds
                .map((id) => ordinal.get(id))
                .filter((n): n is number => typeof n === 'number')
                .sort((a, b) => a - b)
              return (
                <li key={scenario.id}>
                  <label className={`bf-check ${on ? 'is-on' : ''}`}>
                    <input
                      type="checkbox"
                      checked={on}
                      onChange={() => toggleCheck(scenario.id)}
                    />
                    <span className="bf-box" aria-hidden="true">
                      {on ? '✓' : ''}
                    </span>
                    <span className="bf-check-text">
                      <strong>{scenario.label}</strong>
                      <span>{scenario.detail}</span>
                      <em>
                        解决风险 {covers.map((n) => String(n).padStart(2, '0')).join('、')}
                      </em>
                    </span>
                  </label>
                </li>
              )
            })}
          </ul>

          {sim.activeCount > 0 && (
            <p className="bf-delta">
              已采纳 {sim.activeCount}/{scenarios.length} 项，高风险从 {baseHigh} 条降到{' '}
              {sim.highRemaining} 条。
            </p>
          )}
        </section>

        <section id="risks" className="bf-section">
          <header className="bf-section-head">
            <div>
              <h2>
                风险明细 <small>{risks.length}</small>
              </h2>
              <p>按严重程度排。每条都能看到合同里的原话和对应法条。</p>
            </div>
            <div className="bf-section-tools no-print">
              <button type="button" className="bf-link" onClick={() => setDrawer({ clauseId: null })}>
                打开合同原文
              </button>
            </div>
          </header>

          {sortedRisks.length === 0 ? (
            <p className="bf-empty">没有命中明显的风险条款，仍建议核对对方主体和付款路径。</p>
          ) : (
            <div className="bf-risks">
              {visibleRisks.map((risk) => {
                const open = printing || openRisks.has(risk.id)
                const done = resolved.has(risk.id)
                const clause = risk.clause_id ? clauseById.get(risk.clause_id) : undefined
                const law = risk.law
                return (
                  <article
                    key={risk.id}
                    id={`risk-${risk.id}`}
                    className={`bf-risk bf-lvl-${risk.level} ${open ? 'is-open' : ''} ${
                      done ? 'is-done' : ''
                    }`}
                  >
                    <button
                      type="button"
                      className="bf-risk-head"
                      aria-expanded={open}
                      onClick={() => toggleRisk(risk.id)}
                    >
                      <span className="bf-idx">{String(ordinal.get(risk.id)).padStart(2, '0')}</span>
                      <span className="bf-risk-main">
                        <span className="bf-risk-title">
                          {risk.title}
                          {done && <em>清单里已处理</em>}
                        </span>
                        {!open && <span className="bf-risk-gist">{gist(risk.why)}</span>}
                      </span>
                      <span className="bf-level">{LEVEL_LABEL[risk.level]}</span>
                      <span className="bf-chev" aria-hidden="true">
                        {open ? '−' : '+'}
                      </span>
                    </button>

                    {open && (
                      <div className="bf-risk-body">
                        <p className="bf-why">{risk.why}</p>

                        {clause && (
                          <blockquote className="bf-clause">
                            <span className="bf-tag">合同里这样写</span>
                            <p>{clause.text.trim()}</p>
                            <button
                              type="button"
                              className="bf-link no-print"
                              onClick={() => setDrawer({ clauseId: clause.id })}
                            >
                              在合同全文里看 →
                            </button>
                          </blockquote>
                        )}

                        <div className="bf-fix">
                          <span className="bf-tag">建议改成</span>
                          <p>{risk.suggestion}</p>
                        </div>

                        {law && (law.name || law.text) && (
                          <figure className="bf-law">
                            <span className="bf-tag">法律依据</span>
                            {law.text && <blockquote>{law.text}</blockquote>}
                            <figcaption>
                              {law.name}
                              {law.article ? ` ${law.article}` : ''}
                              {law.source_url && (
                                <a href={law.source_url} target="_blank" rel="noreferrer">
                                  原文 ↗
                                </a>
                              )}
                            </figcaption>
                          </figure>
                        )}
                      </div>
                    )}
                  </article>
                )
              })}
            </div>
          )}

          {hiddenCount > 0 && (
            <button
              type="button"
              className="bf-more no-print"
              onClick={() => setShowRest(true)}
            >
              还有 {hiddenCount} 条风险
            </button>
          )}
          {showRest && sortedRisks.length > TOP_RISKS && (
            <button
              type="button"
              className="bf-more no-print"
              onClick={() => setShowRest(false)}
            >
              收起，只看最要紧的 {TOP_RISKS} 条
            </button>
          )}
        </section>

        <section id="company" className="bf-section">
          <header className="bf-section-head">
            <div>
              <h2>对方是谁</h2>
              <p>{company.matched_name || company.name}</p>
            </div>
          </header>

          {facts.length === 0 ? (
            <p className="bf-empty">没有查到这家公司的公开记录，建议签约前让对方出示营业执照和近期信用报告。</p>
          ) : (
            <>
              <ul className="bf-facts">
                {(printing ? facts : keyFacts).map((fact) => (
                  <li key={fact.key} className={`bf-fact bf-sev-${factRank(fact)}`}>
                    <span className="bf-fact-label">{fact.label}</span>
                    <span className="bf-fact-value">{fact.value}</span>
                  </li>
                ))}
              </ul>
              {moreFacts.length > 0 && !printing && (
                <details className="bf-fold no-print">
                  <summary>其余 {moreFacts.length} 项核查</summary>
                  <ul className="bf-facts">
                    {moreFacts.map((fact) => (
                      <li key={fact.key} className={`bf-fact bf-sev-${factRank(fact)}`}>
                        <span className="bf-fact-label">{fact.label}</span>
                        <span className="bf-fact-value">
                          {fact.value}
                          {fact.source_url && (
                            <a href={fact.source_url} target="_blank" rel="noreferrer">
                              {sourceHost(fact.source_url)} ↗
                            </a>
                          )}
                        </span>
                      </li>
                    ))}
                  </ul>
                </details>
              )}
            </>
          )}
        </section>

        <footer className="bf-foot">
          <p>
            由规则引擎对照民法典等法条生成，不构成法律意见。
            {company.demo ? '主体信息为脱敏演示数据。' : ''}
          </p>
          {sourceCount.size > 0 && (
            <details className="bf-fold no-print">
              <summary>来源 {sourceCount.size} 个</summary>
              <ul className="bf-sources">
                {Array.from(sourceCount).map((source) => (
                  <li key={source}>
                    {/^https?:\/\//i.test(source) ? (
                      <a href={source} target="_blank" rel="noreferrer">
                        {sourceHost(source)} ↗
                      </a>
                    ) : (
                      source
                    )}
                  </li>
                ))}
              </ul>
            </details>
          )}
        </footer>
      </div>

      {drawer && (
        <ContractDrawer
          report={report}
          focusClauseId={drawer.clauseId}
          resolvedClauseIds={resolvedClauseIds}
          riskByClause={riskByClause}
          onClose={() => setDrawer(null)}
          onPick={focusRisk}
        />
      )}
    </div>
  )
}
