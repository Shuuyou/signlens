import { VERDICT_META } from '../constants'
import type { Simulation } from '../simulate'
import type { Report } from '../types'

interface WhatIfProps {
  report: Report
  activeIds: ReadonlySet<string>
  simulation: Simulation
  onToggle: (id: string) => void
  onReset: () => void
  onAcceptAll: () => void
}

export default function WhatIf({
  report,
  activeIds,
  simulation,
  onToggle,
  onReset,
  onAcceptAll,
}: WhatIfProps) {
  const base = VERDICT_META[report.decision.verdict]
  const next = VERDICT_META[simulation.verdict]
  const hasScenarios = simulation.scenarios.length > 0
  const allActive =
    hasScenarios && simulation.activeCount === simulation.scenarios.length

  return (
    <section className="panel whatif-panel">
      <div className="section-title-row">
        <div>
          <span className="eyebrow">谈判推演</span>
          <h2>如果…会怎样</h2>
          <p className="section-sub">
            勾选对方可能做出的让步，前端按风险权重即时重算结论。此推演不会再次请求后端，仅供谈判准备。
          </p>
        </div>
        <div className="whatif-actions no-print">
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={onAcceptAll}
            disabled={allActive}
          >
            模拟全部让步
          </button>
          <button
            type="button"
            className="btn btn-ghost btn-sm"
            onClick={onReset}
            disabled={simulation.activeCount === 0}
          >
            重置推演
          </button>
        </div>
      </div>

      {hasScenarios ? (
        <div className="whatif-layout">
          <div className="scenario-list">
            {simulation.scenarios.map((scenario) => {
              const active = activeIds.has(scenario.id)
              return (
                <label
                  key={scenario.id}
                  className={`scenario ${active ? 'is-active' : ''}`}
                >
                  <input
                    type="checkbox"
                    checked={active}
                    onChange={() => onToggle(scenario.id)}
                  />
                  <span className="scenario-check" aria-hidden="true">
                    {active ? '✓' : ''}
                  </span>
                  <span className="scenario-copy">
                    <strong>{scenario.label}</strong>
                    <small>{scenario.detail}</small>
                    <em>覆盖 {scenario.riskIds.length} 项风险</em>
                  </span>
                </label>
              )
            })}
          </div>

          <div className={`sim-card ${simulation.changed ? 'is-flipped' : ''}`}>
            <span className="sim-eyebrow">
              {simulation.activeCount === 0 ? '原始结论' : '推演结论'}
            </span>
            <div className={`sim-verdict sim-${simulation.verdict}`}>
              <span className="sim-word" aria-hidden="true">
                {next.word}
              </span>
              <div>
                <strong>{next.label}</strong>
                <small>
                  {simulation.changed
                    ? '结论已翻转'
                    : simulation.activeCount > 0
                      ? simulation.highRemaining > 0
                        ? `仍有 ${simulation.highRemaining} 项高风险未消除`
                        : '风险敞口下降，结论维持'
                      : '尚未勾选让步项'}
                </small>
              </div>
            </div>

            <p className="sim-compare">
              原始结论：{base.label}
              {simulation.changed && (
                <>
                  <span aria-hidden="true">→</span>
                  {next.label}
                </>
              )}
            </p>

            <dl className="sim-stats">
              <div>
                <dt>剩余高风险</dt>
                <dd>{simulation.highRemaining}</dd>
              </div>
              <div>
                <dt>剩余中风险</dt>
                <dd>{simulation.mediumRemaining}</dd>
              </div>
              <div>
                <dt>风险敞口</dt>
                <dd>{simulation.exposure}%</dd>
              </div>
            </dl>

            <div className="exposure-track" aria-hidden="true">
              <span style={{ width: `${simulation.exposure}%` }} />
            </div>
            <p className="sim-note">
              已消除 {simulation.resolvedRiskIds.length} 项风险，上方风险卡片会同步标记“推演中已缓释”。
            </p>
          </div>
        </div>
      ) : (
        <p className="empty-note">未发现需要推演的风险条款，当前结论可直接参考。</p>
      )}
    </section>
  )
}
