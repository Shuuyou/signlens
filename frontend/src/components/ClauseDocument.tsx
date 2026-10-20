import type { ReactNode } from 'react'
import { RISK_META } from '../constants'
import type { Clause, Report, RiskLevel } from '../types'

interface ClauseDocumentProps {
  report: Report
}

interface ClauseRange {
  clause: Clause
  start: number
  end: number
}

const SEVERITY_RANK: Record<RiskLevel, number> = {
  high: 3,
  medium: 2,
  low: 1,
}

function rangeTitle(clause: Clause): string {
  const summary = clause.summary?.trim()
  if (summary) return summary
  const text = clause.text?.trim().replace(/\s+/g, ' ') ?? ''
  return text.length > 36 ? `${text.slice(0, 36)}…` : text || '合同条款'
}

export default function ClauseDocument({ report }: ClauseDocumentProps) {
  const text = report.input?.contract_text ?? ''
  const clauses = report.clauses ?? []
  const risks = report.risks ?? []

  const severityByClause = new Map<string, RiskLevel>()

  for (const risk of risks) {
    if (!risk.clause_id) continue
    const current = severityByClause.get(risk.clause_id)
    if (!current || SEVERITY_RANK[risk.level] > SEVERITY_RANK[current]) {
      severityByClause.set(risk.clause_id, risk.level)
    }
  }

  const ranges: ClauseRange[] = []
  for (const clause of clauses) {
    const start = Number(clause.start)
    const end = Number(clause.end)
    if (
      Number.isFinite(start) &&
      Number.isFinite(end) &&
      start >= 0 &&
      end > start &&
      end <= text.length
    ) {
      ranges.push({ clause, start, end })
    }
  }
  ranges.sort((a, b) => a.start - b.start)

  const nodes: ReactNode[] = []
  let cursor = 0
  let skipped = 0

  for (const range of ranges) {
    if (range.start < cursor) {
      skipped += 1
      continue
    }
    if (range.start > cursor) {
      nodes.push(<span key={`plain-${cursor}`}>{text.slice(cursor, range.start)}</span>)
    }
    const level = severityByClause.get(range.clause.id)
    nodes.push(
      <mark
        key={`mark-${range.clause.id}`}
        id={`clause-${range.clause.id}`}
        className={`clause-mark ${level ? `clause-${level}` : 'clause-plain'}`}
        title={rangeTitle(range.clause)}
      >
        {text.slice(range.start, range.end)}
      </mark>,
    )
    cursor = range.end
  }

  if (cursor < text.length) {
    nodes.push(<span key={`tail-${cursor}`}>{text.slice(cursor)}</span>)
  }

  const riskyClauses = ranges
    .filter((range) => severityByClause.has(range.clause.id))
    .sort((a, b) => {
      const aLevel = severityByClause.get(a.clause.id) as RiskLevel
      const bLevel = severityByClause.get(b.clause.id) as RiskLevel
      return SEVERITY_RANK[bLevel] - SEVERITY_RANK[aLevel] || a.start - b.start
    })

  const jumpTo = (clauseId: string) => {
    const element = document.getElementById(`clause-${clauseId}`)
    if (!element) return
    element.scrollIntoView({ behavior: 'smooth', block: 'center' })
    element.classList.add('is-flash')
    window.setTimeout(() => element.classList.remove('is-flash'), 1500)
  }

  const validRanges = ranges.length - skipped

  return (
    <div className="clause-document">
      <div className="clause-toolbar">
        <div className="legend">
          <span>
            <i className="legend-swatch swatch-high" />
            高风险条款
          </span>
          <span>
            <i className="legend-swatch swatch-medium" />
            中风险
          </span>
          <span>
            <i className="legend-swatch swatch-low" />
            低风险
          </span>
        </div>
        <span className="clause-count">
          共定位 {validRanges} 条 · 滚动查看全文，打印时自动展开
        </span>
      </div>

      {riskyClauses.length > 0 && (
        <div className="clause-index">
          <span className="clause-index-title">风险条款索引</span>
          <div className="clause-index-list">
            {riskyClauses.map((range) => {
              const level = severityByClause.get(range.clause.id) as RiskLevel
              return (
                <button
                  key={range.clause.id}
                  type="button"
                  className="clause-jump"
                  onClick={() => jumpTo(range.clause.id)}
                >
                  <span className={`chip chip-${level}`}>{RISK_META[level].short}</span>
                  <span>{rangeTitle(range.clause)}</span>
                </button>
              )
            })}
          </div>
        </div>
      )}

      {text ? (
        <div className="contract-scroll" tabIndex={0} aria-label="合同原文">
          <div className="contract-doc">
            {nodes.length > 0 ? nodes : text}
          </div>
        </div>
      ) : (
        <p className="muted">没有提供合同原文。</p>
      )}
    </div>
  )
}
