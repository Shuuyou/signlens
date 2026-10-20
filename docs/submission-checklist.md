# SignLens 提交清单（截止 2026-10-20 23:00）

> 当前状态：产品与本地服务已完成；**GitHub 仓库、魔搭部署、BP、Demo 视频尚未完成**。
> 本地入口：http://127.0.0.1:8010/（后端 + 已构建前端）

## 0. 先确认（10 分钟）

- [ ] 两位队员都已在 10-17 23:59 前用同一队名报名（官网“报名已截止”）
- [ ] 队伍满足“含校外成员至少 1 名浙大学生”（手册原文；杭电队伍必须确认）
- [ ] 队长账号能打开提交页：https://tuotuzju.com/hackathon/2/challenges?track=campus&stage=initial

## 1. GitHub 公开仓库（15:00 前）

仓库根目录：`D:\Contests\ZJUHackthon\TmallOPC\signlens`

```bash
cd /d/Contests/ZJUHackthon/TmallOPC/signlens
git init
git add .
git commit -m "SignLens: contract decision check for student founders"
gh repo create signlens --public --source=. --remote=origin --push
```

注意：
- `.gitignore` 已排除 `.venv/`、`node_modules/`、`backend/static/`、`.env`、`.shots/`；
- `frontend/dist/` 需要入库（`Dockerfile.static` 依赖它），已从 ignore 移除；
- 推送后无痕模式打开仓库确认可读；README 已含本地运行、Docker、魔搭说明。

## 2. 魔搭创空间（16:30 前）

1. 登录 https://modelscope.cn → 创空间 → 创建 → **Docker** 类型。
2. 关联刚推的 GitHub 仓库；Dockerfile 选 `deploy/Dockerfile.static`（若平台只认根目录 Dockerfile，把该文件复制为根目录 `Dockerfile`）。
3. 端口 **7860**；环境变量 `DEMO_MODE=true`、`PORT=7860`（无需 LLM key）。
4. 等待构建；打开 HTTPS 域名，确认：
   - `/api/health` 返回 `{"ok":true}`
   - 首页能打开，3 个演示案例可点
   - 跑一次 `supplier-deposit`，报告能出
5. 演示前 30 分钟预热：`curl https://<space-host>/api/health` 与 `/api/demo/cases`。
6. 若构建失败：看日志是拉 `python:3.12-slim` 失败还是 `frontend/dist` 缺失；前者换平台镜像源/重试，后者确认 dist 已入库。

## 3. BP（20:30 前，PDF ≤30MB）

建议 10–12 页，按官方要求：

1. 一句话：签合同/付预付款之前，先做一次决策体检。
2. 场景与用户：大学生创业者/OPC（钱塘湃/HDU 优先）；供应商预付、培训贷、租房。
3. 痛点：合同看不懂、条款陷阱、对方主体风险；现有工具给数据不给判断。
4. 方案与使用流程：合同 + 对方公司名 → 签/谈/不签 + 条款风险 + 法条依据 + 谈判单。
5. 3 分钟 Demo 截图/链接。
6. 技术：40 条规则、30 组法条、5 阶段流水线、引用绑定；Mingcha 引擎复用与本次新增。
7. 竞品：企查查/天眼查（数据层）、通义/秘塔（问答层）、法大大（电子签）；我们做决策层。
8. 验证：3 个设计伙伴 + N 份真实合同（如实写；没有就写“演示数据脱敏 + 待试点”）。
9. 商业模式：按套 99–299 元 / 基地与高校订阅 / 后续天猫服务市场。
10. 落地路径：钱塘湃/高校创业基地 → 杭州 OPC 社区 → 天猫校园商家服务。
11. 团队：Shuuyou、6TDooo（杭电具身智能实验室）；分工。
12. 风险与合规：不构成法律意见、官方公开源、AI 生成标识、数据最小化。

诚实底线：**不写“已接官方数据”“已有付费用户”“准确率 95%”**；演示数据已脱敏。

## 4. Demo 视频（20:30 前，2–3 分钟）

按 `docs/demo-script.md` 录屏：
- 首页 → 供应商案例 → 分析 → 结论/风险卡 → 「如果…会怎样」全部让步翻转 → 谈判单 → 打印。
- 旁白重点：每条结论可点回条款/法条；改一个事实结论会变。
- 准备离线备份：本地 MP4 + 报告 HTML 打印件。

## 5. 正式提交（22:00 前，留 1 小时缓冲）

- 项目名称、GitHub 链接、魔搭链接（均 HTTPS）、BP、Demo 文件。
- 点“正式提交”（草稿不进入评审）。
- 无痕窗口逐个点开链接；手机 4G 再开一次魔搭链接。
- 记录提交回执截图。

## 6. 最后检查

- [ ] 魔搭链接评委无需登录可打开
- [ ] GitHub 仓库 public，README 能看懂
- [ ] BP 里没有无法核实的数字
- [ ] 视频能在本地播放
- [ ] 答辩备份：离线报告、截图、3 分钟讲稿
