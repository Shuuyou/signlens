import type { RiskLevel, Verdict } from './types'

export const VERDICT_META: Record<
  Verdict,
  { word: string; label: string; caption: string }
> = {
  sign: {
    word: '签',
    label: '建议签署',
    caption: '条款风险整体可控，可以按现有条件推进。',
  },
  negotiate: {
    word: '谈',
    label: '先谈再签',
    caption: '合同可以签，但必须先改掉几处关键条款。',
  },
  reject: {
    word: '不签',
    label: '建议不签',
    caption: '现有条款下的风险与收益不匹配，建议终止或重谈。',
  },
}

export const RISK_META: Record<RiskLevel, { label: string; short: string }> = {
  high: { label: '高风险', short: '高' },
  medium: { label: '中风险', short: '中' },
  low: { label: '低风险', short: '低' },
}

export const RISK_ORDER: Record<RiskLevel, number> = {
  high: 0,
  medium: 1,
  low: 2,
}

export const ROLE_OPTIONS = [
  { value: 'founder', label: '创业者', hint: '个体创业 / OPC' },
  { value: 'student', label: '学生', hint: '校园项目 / 首次签约' },
  { value: 'merchant', label: '商家', hint: '采购 / 供货 / 租赁' },
]

export const PIPELINE_STAGES = [
  {
    key: 'parse',
    title: '解析条款',
    description: '切分合同结构，定位付款、交付、违约、退费等关键条款。',
  },
  {
    key: 'company',
    title: '核查主体',
    description: '比对对方公司名称与公开主体记录，标记被执行、经营异常等信号。',
  },
  {
    key: 'rules',
    title: '匹配法条',
    description: '用本地规则库逐条匹配风险，并为每项风险附上法律依据。',
  },
  {
    key: 'decide',
    title: '生成建议',
    description: '按风险权重与主体信号，给出「签 / 谈 / 不签」及置信度。',
  },
  {
    key: 'report',
    title: '出报告',
    description: '生成谈判清单、来源列表与可打印的体检报告。',
  },
] as const

export const SOURCE_TIPS =
  '演示数据已脱敏。真实模式对接国家企业信用信息公示系统、中国裁判文书网、信用中国等公开来源。'
