import { RISK_META } from '../constants'
import type { Clause, Risk } from '../types'

interface RiskCardProps {
  risk: Risk
  index?: number
  clause?: Clause
  mitigated: boolean
}

function clauseLabel(clause: Clause): string {
  const summary = clause.summary?.trim()
  if (summary) return summary
  const text = clause.text?.trim().replace(/\s+/g, ' ') ?? ''
  return text.length > 42 ? `${text.slice(0, 42)}…` : text || '查看对应条款'
}

export default function RiskCard({ risk, index, clause, mitigated }: RiskCardProps) {
  const law = risk.law
  const confidence = Math.round(Math.max(0, Math.min(1, risk.confidence ?? 0.8)) * 100)

  const jumpToClause = () => {
    if (!risk.clause_id) return
    const element = document.getElementById(`clause-${risk.clause_id}`)
    if (!element) return
    element.scrollIntoView({ behavior: 'smooth', block: 'center' })
    element.classList.add('is-flash')
    window.setTimeout(() => element.classList.remove('is-flash'), 1500)
  }

  return (
    <article
      className={`risk-card risk-${risk.level} ${mitigated ? 'is-mitigated' : ''}`}
    >
      <header className="risk-head">
        {typeof index === 'number' && (
          <span className="risk-index" aria-hidden="true">
            {String(index).padStart(2, '0')}
          </span>
        )}
        <span className={`chip chip-${risk.level}`}>{RISK_META[risk.level].label}</span>
        <h3>{risk.title}</h3>
        {mitigated && <span className="chip chip-mitigated">推演中已缓释</span>}
        <span className="risk-confidence">规则置信 {confidence}%</span>
      </header>

      <div className="risk-body">
        <div className="risk-block">
          <span className="risk-label">为什么</span>
          <p>{risk.why}</p>
        </div>

        {clause && risk.clause_id && (
          <p className="risk-clause">
            对应条款：
            <button type="button" className="inline-link" onClick={jumpToClause}>
              {clauseLabel(clause)}
            </button>
          </p>
        )}

        <div className="risk-suggestion">
          <span className="risk-label">改法</span>
          <p>{risk.suggestion}</p>
        </div>

        {law && (law.name || law.text) ? (
          <details className="law-fold">
            <summary>
              法条依据
              <span>
                {law.name}
                {law.article ? ` ${law.article}` : ''}
              </span>
            </summary>
            <div className="law-body">
              {law.text && <blockquote className="law-quote">{law.text}</blockquote>}
              {law.source_url && (
                <a href={law.source_url} target="_blank" rel="noreferrer">
                  查看来源 ↗
                </a>
              )}
            </div>
          </details>
        ) : (
          <p className="risk-no-law">暂无直接法条依据，按交易常识与行业惯例判断。</p>
        )}
      </div>
    </article>
  )
}
