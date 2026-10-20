import type { Report, Risk, Verdict } from './types'

interface ScenarioTemplate {
  id: string
  label: string
  detail: string
  keywords: string[]
}

const TEMPLATES: ScenarioTemplate[] = [
  {
    id: 'delivery',
    label: '对方书面补充交货日期与验收标准',
    detail: '把“尽快交付”改成具体日期，并约定逾期每日 0.5% 的违约金。',
    keywords: ['交付', '交货', '发货', '验收', '生产', '工期', '排产'],
  },
  {
    id: 'payment',
    label: '预付款降至 10%，尾款验收后支付',
    detail: '把 30% 预付款压到 10%，剩余款项在货物验收合格后支付。',
    keywords: ['预付', '首付', '定金', '付款', '尾款', '账期', '货到'],
  },
  {
    id: 'venue',
    label: '争议解决改到公司所在地法院',
    detail: '删除异地仲裁条款，改为我方所在地有管辖权的法院。',
    keywords: ['仲裁', '管辖', '法院', '争议', '诉讼', '异地'],
  },
  {
    id: 'execution',
    label: '对方补齐执行记录并提供股东连带担保',
    detail: '要求披露被执行案件的履行情况，并由实控人签署连带责任保证。',
    keywords: ['被执行', '失信', '涉诉', '信用', '经营异常', '执行', '担保', '主体'],
  },
  {
    id: 'penalty',
    label: '违约金上限压到合同总额的 10%',
    detail: '删除“日 1%”这类无上限条款，统一设置违约金总额上限。',
    keywords: ['违约金', '滞纳', '罚息', '赔偿', '间接损失', '损失'],
  },
  {
    id: 'refund',
    label: '解除/退款改为按履行比例结算',
    detail: '未履行部分应退还；可扣除已实际发生且可证明的成本，并列明计算依据。',
    keywords: ['退费', '退款', '不退', '冷静期', '解约', '终止', '解除'],
  },
  {
    id: 'deposit',
    label: '押金降为一个月，退租 7 日内返还',
    detail: '押金从两个月租金降为一个月，并约定逾期返还的利息。',
    keywords: ['押金', '保证金', '返还', '租金', '押二'],
  },
  {
    id: 'loan',
    label: '取消培训贷，改为按课时直付',
    detail: '不绑定第三方金融分期，学费按课时进度支付。',
    keywords: ['贷', '分期', '金融', '征信', '还款'],
  },
]

export interface Scenario {
  id: string
  label: string
  detail: string
  riskIds: string[]
}

export interface Simulation {
  scenarios: Scenario[]
  resolvedRiskIds: string[]
  activeCount: number
  verdict: Verdict
  changed: boolean
  highRemaining: number
  mediumRemaining: number
  exposure: number
}

const RISK_WEIGHT = { high: 30, medium: 12, low: 4 } as const
const VERDICT_RANK: Record<Verdict, number> = { sign: 0, negotiate: 1, reject: 2 }
const RANK_VERDICT: Verdict[] = ['sign', 'negotiate', 'reject']

function riskText(risk: Risk): string {
  return `${risk.title} ${risk.why}`
}

function makeScenario(
  id: string,
  label: string,
  detail: string,
  risks: Risk[],
): Scenario {
  return { id, label, detail, riskIds: risks.map((risk) => risk.id) }
}

export function buildScenarios(report: Report): Scenario[] {
  const matched: Scenario[] = []

  for (const template of TEMPLATES) {
    const risks = report.risks.filter((risk) => {
      const text = riskText(risk)
      return template.keywords.some((keyword) => text.includes(keyword))
    })
    if (risks.length > 0) {
      matched.push(makeScenario(template.id, template.label, template.detail, risks))
    }
  }

  const scenarios = matched.slice(0, 6)
  const covered = new Set(scenarios.flatMap((scenario) => scenario.riskIds))

  const uncovered = () => report.risks.filter((risk) => !covered.has(risk.id))

  const addFallback = (
    target: Risk[],
    id: string,
    label: string,
    detail: string,
    limit: number,
  ) => {
    const picked = target.slice(0, limit)
    if (picked.length > 0) {
      scenarios.push(makeScenario(id, label, detail, picked))
      picked.forEach((risk) => covered.add(risk.id))
    }
  }

  if (scenarios.length < 3) {
    addFallback(
      uncovered().filter((risk) => risk.level === 'high'),
      'guarantee',
      '对方提供第三方履约担保，预付款进入共管账户',
      '由担保公司或实控人提供连带责任保证，预付款按交付节点解付。',
      2,
    )
  }

  if (scenarios.length < 3) {
    addFallback(
      uncovered().filter((risk) => risk.level !== 'high'),
      'supplement',
      '双方补签书面补充协议，明确交付与退款标准',
      '把口头承诺写进合同附件，约定触发条件、处理时限与违约责任。',
      2,
    )
  }

  if (scenarios.length < 2) {
    addFallback(
      uncovered(),
      'escrow',
      '引入第三方资金托管，按验收结果分批放款',
      '资金由银行或平台托管，验收合格后放款，避免预付后失去主动权。',
      2,
    )
  }

  return scenarios
}

function verdictFromRisks(risks: Risk[]): Verdict {
  const high = risks.filter((risk) => risk.level === 'high').length
  const medium = risks.filter((risk) => risk.level === 'medium').length
  if (high >= 2) return 'reject'
  if (high === 1) return 'negotiate'
  if (medium >= 2) return 'negotiate'
  return 'sign'
}

export function simulate(
  report: Report,
  activeIds: ReadonlySet<string>,
  scenarios: Scenario[] = buildScenarios(report),
): Simulation {
  const resolvedRiskIds = new Set<string>()
  let activeCount = 0

  for (const scenario of scenarios) {
    if (!activeIds.has(scenario.id)) continue
    activeCount += 1
    scenario.riskIds.forEach((id) => resolvedRiskIds.add(id))
  }

  const remaining = report.risks.filter((risk) => !resolvedRiskIds.has(risk.id))
  const totalWeight = report.risks.reduce((sum, risk) => sum + RISK_WEIGHT[risk.level], 0)
  const remainingWeight = remaining.reduce((sum, risk) => sum + RISK_WEIGHT[risk.level], 0)
  const exposure = totalWeight > 0 ? Math.round((remainingWeight / totalWeight) * 100) : 0

  const baseRank = VERDICT_RANK[report.decision.verdict]
  let verdict = report.decision.verdict

  if (activeCount > 0) {
    const ruleRank = VERDICT_RANK[verdictFromRisks(remaining)]
    const resolvedShare = totalWeight > 0 ? (totalWeight - remainingWeight) / totalWeight : 0
    const improvement = resolvedShare >= 0.15 ? 1 : 0
    const improvedRank = Math.max(baseRank - improvement, Math.min(ruleRank, baseRank))
    verdict = RANK_VERDICT[improvedRank]
  }

  return {
    scenarios,
    resolvedRiskIds: Array.from(resolvedRiskIds),
    activeCount,
    verdict,
    changed: verdict !== report.decision.verdict,
    highRemaining: remaining.filter((risk) => risk.level === 'high').length,
    mediumRemaining: remaining.filter((risk) => risk.level === 'medium').length,
    exposure,
  }
}
