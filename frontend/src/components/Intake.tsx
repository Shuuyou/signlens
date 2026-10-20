import { useRef, useState, type ChangeEvent, type FormEvent } from 'react'
import { ROLE_OPTIONS } from '../constants'
import { SubXiaocha } from '../mascot/SubXiaocha'
import type { CaseInput } from '../types'

interface IntakeProps {
  initial: CaseInput | null
  prefilled: boolean
  onSubmit: (input: CaseInput) => Promise<void>
  onBack: () => void
}

export default function Intake({ initial, prefilled, onSubmit, onBack }: IntakeProps) {
  const [company, setCompany] = useState(initial?.company.name ?? '')
  const [creditCode, setCreditCode] = useState(initial?.company.credit_code ?? '')
  const [contract, setContract] = useState(initial?.contract_text ?? '')
  const [chat, setChat] = useState(initial?.chat_text ?? '')
  const [dealValue, setDealValue] = useState(
    initial?.deal_value != null ? String(initial.deal_value) : '',
  )
  const [role, setRole] = useState(initial?.user_role ?? 'founder')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const [fileNote, setFileNote] = useState<string | null>(null)
  const fileInput = useRef<HTMLInputElement>(null)

  const validate = (): string | null => {
    if (company.trim().length < 2) return '请填写对方公司的完整名称。'
    if (contract.trim().length < 40) return '合同正文太短，请粘贴完整合同（至少 40 字）。'
    if (dealValue.trim()) {
      const value = Number(dealValue)
      if (!Number.isFinite(value) || value < 0) return '交易金额需要填写为非负数字。'
    }
    return null
  }

  const handleSubmit = async (event: FormEvent<HTMLFormElement>) => {
    event.preventDefault()
    if (submitting) return

    const message = validate()
    if (message) {
      setError(message)
      return
    }

    setError(null)
    setSubmitting(true)
    try {
      await onSubmit({
        company: {
          name: company.trim(),
          credit_code: creditCode.trim() || null,
        },
        contract_text: contract,
        chat_text: chat.trim() || null,
        user_role: role,
        deal_value: dealValue.trim() ? Number(dealValue) : null,
        stage: 'prepay',
      })
    } catch (err) {
      setError(err instanceof Error ? err.message : '提交失败，请稍后重试。')
      setSubmitting(false)
    }
  }

  const handleFile = async (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    event.target.value = ''
    if (!file) return

    if (file.name.toLowerCase().endsWith('.txt')) {
      try {
        const text = await file.text()
        setContract(text)
        setFileNote(`已读取 ${file.name}，共 ${text.length} 字。请检查是否完整。`)
      } catch {
        setFileNote('文件读取失败，请改为直接粘贴合同正文。')
      }
      return
    }

    setFileNote('PDF 暂不支持自动解析，请打开 PDF 后复制正文并粘贴到这里。')
  }

  return (
    <div className="page intake-page">
      <div className="container page-container">
        <div className="page-head">
          <button type="button" className="back-link" onClick={onBack}>
            ← 返回首页
          </button>
          <span className="eyebrow">第一步 / 共三步</span>
          <h1>把合同放进来，先体检再决定</h1>
          <p>
            只需要合同全文和对方公司名。聊天记录可选，但它能帮助我们识别口头承诺与合同文本之间的落差。
          </p>
          <div className="intake-mascot" aria-hidden="true">
            <SubXiaocha role="legal" size={64} state="reading" decorative />
          </div>
        </div>

        {prefilled && (
          <div className="notice notice-info">
            已载入演示案例，所有字段都可以修改。确认无误后直接开始体检。
          </div>
        )}

        {error && (
          <div className="alert alert-error" role="alert">
            {error}
          </div>
        )}

        <form className="intake-layout" onSubmit={handleSubmit} noValidate>
          <div className="intake-main">
            <section className="panel">
              <div className="panel-head">
                <h2>对方主体</h2>
                <span>用于核查公开记录</span>
              </div>
              <div className="field-grid company-grid">
                <div className="field">
                  <label htmlFor="company-name">
                    对方公司全称 <span className="req">必填</span>
                  </label>
                  <input
                    id="company-name"
                    type="text"
                    value={company}
                    onChange={(event) => setCompany(event.target.value)}
                    placeholder="例如：深圳市恒锐五金制品有限公司"
                    autoComplete="organization"
                    required
                  />
                  <p className="field-help">写合同上盖章的主体全称，不是品牌名或店铺名。</p>
                </div>
                <div className="field">
                  <label htmlFor="credit-code">
                    统一社会信用代码 <span>选填</span>
                  </label>
                  <input
                    id="credit-code"
                    type="text"
                    value={creditCode}
                    onChange={(event) => setCreditCode(event.target.value)}
                    placeholder="18 位代码"
                  />
                  <p className="field-help">有代码时主体匹配更准确。</p>
                </div>
              </div>
            </section>

            <section className="panel">
              <div className="panel-head">
                <h2>合同正文</h2>
                <span className="char-count">{contract.length} 字</span>
              </div>
              <div className="field">
                <label htmlFor="contract-text" className="sr-only">
                  合同全文
                </label>
                <textarea
                  id="contract-text"
                  className="contract-input"
                  value={contract}
                  onChange={(event) => setContract(event.target.value)}
                  rows={17}
                  placeholder={
                    '粘贴合同全文，尽量包含付款、交付、验收、违约、退费和争议解决条款。\n\n例如：\n第一条 采购标的……\n第二条 付款方式……\n第三条 交付……'
                  }
                  required
                />
                <div className="field-foot">
                  <span>支持直接从 Word / PDF 中复制文字。</span>
                  <span className="file-actions">
                    <button
                      type="button"
                      className="link-btn"
                      onClick={() => fileInput.current?.click()}
                    >
                      上传 .txt
                    </button>
                    <span className="file-hint">PDF 暂不解析</span>
                  </span>
                </div>
                <input
                  ref={fileInput}
                  type="file"
                  accept=".txt,.pdf,text/plain,application/pdf"
                  onChange={handleFile}
                  className="sr-only"
                  tabIndex={-1}
                />
                {fileNote && (
                  <p className="file-note" role="status">
                    {fileNote}
                  </p>
                )}
              </div>
            </section>

            <section className="panel">
              <div className="panel-head">
                <h2>聊天记录</h2>
                <span>选填 · 帮助识别口头承诺</span>
              </div>
              <div className="field">
                <label htmlFor="chat-text" className="sr-only">
                  聊天记录
                </label>
                <textarea
                  id="chat-text"
                  value={chat}
                  onChange={(event) => setChat(event.target.value)}
                  rows={5}
                  placeholder={
                    '例如销售说：“先付 30% 我们马上排产，交期肯定没问题”“合同就是走个流程，不用写太死”。'
                  }
                />
                <p className="field-help">
                  不用整理格式。只贴与付款、交付、退费、承诺有关的片段即可。
                </p>
              </div>
            </section>
          </div>

          <aside className="intake-side">
            <section className="panel">
              <div className="panel-head">
                <h2>交易信息</h2>
                <span>用于校准建议</span>
              </div>
              <div className="field">
                <label htmlFor="deal-value">
                  交易金额 <span>选填 · 元</span>
                </label>
                <div className="input-suffix">
                  <input
                    id="deal-value"
                    type="number"
                    min="0"
                    step="0.01"
                    inputMode="decimal"
                    value={dealValue}
                    onChange={(event) => setDealValue(event.target.value)}
                    placeholder="116000"
                  />
                  <span>元</span>
                </div>
                <p className="field-help">预付款、违约金是否“值得较真”，取决于金额。</p>
              </div>

              <fieldset className="field role-field">
                <legend>你的身份</legend>
                <div className="role-grid">
                  {ROLE_OPTIONS.map((option) => (
                    <label
                      key={option.value}
                      className={`role-option ${role === option.value ? 'is-selected' : ''}`}
                    >
                      <input
                        type="radio"
                        name="user-role"
                        value={option.value}
                        checked={role === option.value}
                        onChange={(event) => setRole(event.target.value)}
                      />
                      <strong>{option.label}</strong>
                      <small>{option.hint}</small>
                    </label>
                  ))}
                </div>
              </fieldset>
            </section>

            <section className="panel panel-soft tips-panel">
              <h2>填写提示</h2>
              <ul className="tips-list">
                <li>主体名称写错，会导致核查结果偏掉，先对一遍营业执照。</li>
                <li>合同附件、补充协议里的条款也要一起粘贴。</li>
                <li>演示环境数据存放在内存中，服务重启即清空。</li>
              </ul>
            </section>

            <div className="submit-block">
              <button type="submit" className="btn btn-primary btn-block" disabled={submitting}>
                {submitting ? '正在提交…' : '开始体检'}
                {!submitting && <span aria-hidden="true">→</span>}
              </button>
              <p>提交后约 10–30 秒生成报告。所有分析在本地服务完成。</p>
            </div>
          </aside>
        </form>
      </div>
    </div>
  )
}
