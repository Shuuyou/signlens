# SignLens · 签前体检 — 工程契约

> 产品：大学生创业者/OPC 在签合同、付预付款前的“决策体检”。
> 输入合同文本 + 对方公司名（可选聊天记录），输出「签 / 谈 / 不签」+ 条款风险 + 法条依据 + 谈判单。
> 约束：63 小时 MVP；演示不依赖外网/付费 API；单容器部署到魔搭创空间（端口 7860）。

## 1. 仓库结构与归属

```
signlens/
  README.md
  docs/contracts.md              # 本文件，主 Agent 维护
  backend/
    requirements.txt
    app/
      main.py                    # Agent A：FastAPI 入口、静态托管、路由注册
      models.py                  # 主 Agent：共享 Pydantic 模型（不要改字段）
      api/cases.py               # Agent A：所有 /api 路由
      core/store.py              # Agent A：内存 job/case 存储
      core/orchestrator.py       # Agent A：流水线编排
      services/
        clauses.py               # Agent B：条款抽取
        rules.py                 # Agent B：规则匹配
        company.py               # Agent C：主体证据
        decision.py              # Agent E：决策 rubric
        report.py                # Agent E：HTML 报告
  data/
    rules/rules.json             # Agent B：30-40 条硬规则 + 法条
    companies/*.json             # Agent C：8-10 个演示主体
    cases/*.json                 # Agent C：3 个演示案例
    templates/report.html        # Agent E：Jinja2 报告模板
  frontend/                      # Agent D：Vite + React + TS
  deploy/Dockerfile              # Agent F
  scripts/smoke_test.py          # Agent F
  tests/                         # Agent F
```

**所有权规则**：每个 Agent 只写自己名下的文件；需要改别人的文件时，在自己的交付说明里写清楚，不要直接改。

## 2. 数据模型（以 `backend/app/models.py` 为准）

- `CaseInput`: company{name, credit_code?}, contract_text, chat_text?, user_role, deal_value?, stage
- `Clause`: id, type, text, start, end, summary
- `LawRef`: name, article, text, source_url
- `Risk`: id, clause_id?, title, level(high|medium|low), why, law?, suggestion, confidence
- `Fact`: key, label, value, source_url, retrieved_at, severity
- `CompanyEvidence`: name, matched_name, demo, facts[], flags[], sources[]
- `Decision`: verdict(sign|negotiate|reject), confidence, headline, reasons[], conditions[], change_my_mind[]
- `Report`: case_id, input, company, clauses[], risks[], decision, negotiation_sheet[], sources[], generated_at
- `Job`: job_id, case_id, status(queued|running|done|error), stage, progress, error?, report?

## 3. 流水线

`parse` → `company` → `rules` → `decide` → `report`

- `parse`：`clauses.extract_clauses(text) -> list[Clause]`
- `company`：`company.get_company_evidence(name) -> CompanyEvidence`
- `rules`：`rules.match_risks(clauses, company) -> list[Risk]`
- `decide`：`decision.decide(clauses, risks, company) -> Decision`
- `report`：`report.build_report(case_id, input, company, clauses, risks, decision) -> Report`；`report.render_html(report) -> str`

所有 service 函数必须**纯本地、确定性**，不依赖网络；可选 LLM 增强只能作为 fallback 之外的加分项。

## 4. API

| 方法 | 路径 | 说明 |
|---|---|---|
| GET | `/api/health` | `{ok: true}` |
| GET | `/api/demo/cases` | 演示案例列表 `{id,title,summary,company,expected_verdict}` |
| GET | `/api/demo/{demo_id}` | 返回 `CaseInput`（用于前端预填） |
| POST | `/api/demo/{demo_id}/run` | 载入案例并启动分析，返回 `{case_id, job_id}` |
| POST | `/api/cases` | body `CaseInput`，返回 `{case_id}` |
| POST | `/api/cases/{case_id}/analyze` | 返回 `{job_id}` |
| GET | `/api/jobs/{job_id}` | 返回 `Job`；done 时带 `report` |
| GET | `/api/cases/{case_id}` | 返回 `Report` |
| GET | `/api/cases/{case_id}/report.html` | 返回打印友好的 HTML |

- 全部 JSON；统一 `{error: string}` 错误体。
- 长任务用 `job_id` + 前端轮询（1 秒一次），不要依赖 SSE。
- 演示模式必须在无 API key、无外网时可用。

## 5. 演示案例（Agent C 负责）

1. `supplier-deposit`：1688 供应商，30% 预付款，无交付日期，异地仲裁，对方有被执行记录 → `negotiate/reject`
2. `training-loan`：校园培训合同，培训贷、违约金过高、不退费 → `reject`
3. `rental-clean`：租房合同，条款基本正常，仅押金略高 → `sign/negotiate`

案例数据必须标注 `demo: true`，并在 README 写明“演示数据已脱敏，真实模式接官方公开源”。

## 6. 前端（Agent D）

- 单页流程：首页（产品主张 + 3 个演示案例）→ 输入页 → 分析中（阶段进度）→ 报告页。
- 报告页必须有：结论横幅、风险卡片（等级/为什么/法条/改法）、条款原文高亮、“如果…会怎样”事实切换（结论翻转）、谈判清单一页纸、来源列表、打印按钮。
- 只用 CSS，不引入 UI 库；中文界面；桌面优先，窄屏可读。
- 所有请求走相对路径 `/api`；Vite dev proxy 到 `http://127.0.0.1:8000`。

## 7. 部署（Agent F）

- 多阶段 Docker：node:20 构建前端 → python:3.11-slim 运行；`EXPOSE 7860`；`uvicorn app.main:app --host 0.0.0.0 --port 7860`。
- 前端产物放 `backend/static`，FastAPI `StaticFiles` 托管；`/` 返回 `index.html`。
- SQLite 可不用；job/case 存内存即可，重启丢失可接受。
- 健康检查 `/api/health`；容器内不装 GPU 依赖。

## 8. 验收

- `python -m py_compile` 全部通过。
- `GET /api/health` 200；`GET /api/demo/cases` 返回 3 条。
- 跑 `supplier-deposit`：job 60 秒内 done，report 至少 5 条风险、3 条带法条、verdict 为 negotiate/reject。
- 前端能完成一次完整流程并打印报告。
- Docker 构建成功，7860 可访问。
