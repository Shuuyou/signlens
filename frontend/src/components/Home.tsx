import { useEffect, useState } from 'react'
import { getDemoCases } from '../api'
import { FALLBACK_DEMOS } from '../demoData'
import { VERDICT_META } from '../constants'
import { SubXiaocha } from '../mascot/SubXiaocha'
import type { DemoCase } from '../types'

interface HomeProps {
  onStart: () => void
  onDemoSelect: (demo: DemoCase) => void
  loadingDemoId: string | null
  error: string | null
}

const HOW_IT_WORKS = [
  {
    title: '粘贴合同',
    description: '合同全文 + 对方公司名。聊天记录可选，用来对照口头承诺。',
  },
  {
    title: '核查主体',
    description: '比对公开主体记录，标记被执行、失信、经营异常等信号。',
  },
  {
    title: '规则体检',
    description: '逐条匹配 30+ 条硬规则与法条，给出可解释的风险判断。',
  },
  {
    title: '拿走清单',
    description: '得到「签 / 谈 / 不签」的结论，以及一页可直接开谈的清单。',
  },
]

export default function Home({ onStart, onDemoSelect, loadingDemoId, error }: HomeProps) {
  const [demos, setDemos] = useState<DemoCase[]>(FALLBACK_DEMOS)
  const [source, setSource] = useState<'loading' | 'api' | 'fallback'>('loading')

  useEffect(() => {
    let alive = true
    getDemoCases()
      .then((data) => {
        if (!alive) return
        if (Array.isArray(data) && data.length > 0) {
          setDemos(data)
          setSource('api')
        } else {
          setSource('fallback')
        }
      })
      .catch(() => {
        if (alive) setSource('fallback')
      })
    return () => {
      alive = false
    }
  }, [])

  return (
    <div className="home">
      <section className="home-hero">
        <div className="container hero-grid">
          <div className="hero-copy">
            <div className="hero-mascot" aria-hidden="true">
              <SubXiaocha role="legal" size={120} decorative />
            </div>
            <div className="hero-kicker">
              <span className="hero-dot" />
              合同决策体检
            </div>
            <h1>
              签合同、付预付款之前，
              <br />
              先做一次<span className="hero-mark">决策体检</span>。
            </h1>
            <p className="hero-lead">
              把合同全文和对方公司名交给 SignLens，几分钟内得到「签 / 谈 / 不签」的结论、逐条风险、法条依据，以及一份能直接拿去谈的清单。
            </p>
            <div className="hero-actions">
              <button type="button" className="btn btn-primary" onClick={onStart}>
                开始体检
                <span aria-hidden="true">→</span>
              </button>
              <a className="btn btn-ghost" href="#demo-cases">
                先看演示案例
              </a>
            </div>
            <ul className="hero-points">
              <li>条款逐条定位</li>
              <li>结论有据可查</li>
              <li>报告可打印带走</li>
            </ul>
          </div>

          <div className="hero-preview" aria-hidden="true">
            <div className="preview-top">
              <span>体检报告 / 供应商采购</span>
            </div>
            <div className="preview-verdict">
              <span className="preview-seal">谈</span>
              <div>
                <strong>先谈再签</strong>
                <small>3 处关键条款需要修改</small>
              </div>
            </div>
            <div className="preview-risks">
              <div>
                <span className="chip chip-high">高风险</span>
                <p>30% 预付款，未约定交货日期</p>
              </div>
              <div>
                <span className="chip chip-high">高风险</span>
                <p>异地仲裁，维权成本不可控</p>
              </div>
              <div>
                <span className="chip chip-medium">中风险</span>
                <p>双方违约金比例相差 20 倍</p>
              </div>
            </div>
            <div className="preview-foot">
              <span>主体核查</span>
              <span>法条依据</span>
              <span>谈判清单</span>
            </div>
          </div>
        </div>
      </section>

      <section className="section" id="demo-cases">
        <div className="container">
          <div className="section-head">
            <div>
              <span className="eyebrow">演示案例</span>
              <h2>先从一个典型场景开始</h2>
              <p>三个已脱敏的合同场景，覆盖供应商预付、校园培训贷与房屋租赁。载入后可修改任何内容。</p>
            </div>
            <span className="section-note">
              {source === 'api' && '数据已脱敏 · 来自演示库'}
              {source === 'loading' && '正在载入演示案例…'}
              {source === 'fallback' && '后端未连接 · 当前为内置演示数据'}
            </span>
          </div>

          {error && (
            <div className="alert alert-error" role="alert">
              {error}
            </div>
          )}

          <div className="case-grid">
            {demos.map((demo) => {
              const safeVerdict =
                demo.expected_verdict === 'sign' ||
                demo.expected_verdict === 'negotiate' ||
                demo.expected_verdict === 'reject'
                  ? demo.expected_verdict
                  : 'negotiate'
              const meta = VERDICT_META[safeVerdict]
              const loading = loadingDemoId === demo.id
              return (
                <button
                  key={demo.id}
                  type="button"
                  className="case-card"
                  onClick={() => onDemoSelect(demo)}
                  disabled={loadingDemoId !== null}
                >
                  <span className="case-top">
                    <span className="case-company">{demo.company}</span>
                    <span className={`verdict-chip verdict-${safeVerdict}`}>
                      {meta.label}
                    </span>
                  </span>
                  <strong className="case-title">{demo.title}</strong>
                  <span className="case-summary">{demo.summary}</span>
                  <span className="case-foot">
                    <span>{loading ? '正在载入…' : '载入此案例'}</span>
                    <span aria-hidden="true">→</span>
                  </span>
                </button>
              )
            })}
          </div>

          <p className="section-footnote">
            演示数据已脱敏，结论由本地规则引擎生成。真实模式对接国家企业信用信息公示系统、中国裁判文书网、信用中国等公开来源。
          </p>
        </div>
      </section>

      <section className="section section-tinted">
        <div className="container">
          <div className="section-head compact">
            <div>
              <span className="eyebrow">工作方式</span>
              <h2>四个步骤，一份可执行的结论</h2>
            </div>
            <p className="section-note">不依赖外网与付费 API · 单机可演示</p>
          </div>

          <ol className="steps-grid">
            {HOW_IT_WORKS.map((step, index) => (
              <li key={step.title}>
                <span className="step-number">0{index + 1}</span>
                <h3>{step.title}</h3>
                <p>{step.description}</p>
              </li>
            ))}
          </ol>

          <div className="value-strip">
            <div>
              <strong>可解释</strong>
              <p>每项风险都写清「为什么」和对应法条，不给你一个无法追问的黑箱结论。</p>
            </div>
            <div>
              <strong>可执行</strong>
              <p>改法建议写成可以直接发给对方的句子，而不是“注意风险”这类空话。</p>
            </div>
            <div>
              <strong>可带走</strong>
              <p>一页谈判清单和完整报告均可打印，带去见合伙人、房东或供应商。</p>
            </div>
          </div>
        </div>
      </section>
    </div>
  )
}
