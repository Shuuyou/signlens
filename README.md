# SignLens · 签前体检

大学生创业者 / OPC 在签合同、付预付款前的决策体检：合同文本 + 对方公司名 → 「签 / 谈 / 不签」+ 条款风险 + 法条依据 + 谈判单。

## 本地运行

```bash
# backend
cd backend
python -m venv .venv && source .venv/Scripts/activate  # Windows Git Bash
pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000

# frontend
cd frontend
npm install
npm run dev
```

前端 dev server 通过 Vite proxy 访问 `/api`。

本地默认端口是 `8000`；容器与魔搭创空间统一用 `7860`。演示模式无需任何 key：
`DEMO_MODE=true` 时流水线完全本地、确定性运行，不访问外网。需要可选 LLM 增强时：

```bash
cp .env.example .env   # 填入 LLM_API_KEY / LLM_BASE_URL，留空则走本地规则
```

## 部署

多阶段构建：`node:20-slim` 构建 Vite 前端，`python:3.11-slim` 运行 FastAPI，
前端产物复制到 `backend/static` 由 FastAPI 托管，单容器监听 `7860`。

```bash
# 在仓库根目录构建（构建上下文必须是根目录，deploy/Dockerfile 里 COPY 的是 frontend/、backend/、data/）
docker build -f deploy/Dockerfile -t signlens .

# 运行
docker run --rm -p 7860:7860 signlens

# 可选：注入环境变量（演示模式默认已开启）
docker run --rm -p 7860:7860 --env-file .env signlens
```

构建上下文是整个仓库，根目录 `.dockerignore` 已排除 `.venv/`、`node_modules/`、`backend/static/` 等。
**若本机无法访问 Docker Hub**（`docker build` 卡在拉取 `node:20-slim` / `python:3.11-slim`），
用静态镜像方案：先在 `frontend/` 执行 `npm run build`，再构建只依赖 `python:3.12-slim` 的镜像：

```bash
docker build -f deploy/Dockerfile.static -t signlens:static .
docker run --rm -p 7860:7860 signlens:static
```

`Dockerfile.static` 不拉 Node 镜像，直接复制已构建的 `frontend/dist`；魔搭创空间如果只能选一个
Dockerfile，优先用它（仓库需包含 `frontend/dist`）。

容器内路径布局（与后端 `data/` 定位方式对齐）：

| 容器内路径 | 来源 | 作用 |
|---|---|---|
| `/app/backend` | `backend/` | FastAPI 代码，运行时 `WORKDIR` |
| `/app/backend/static` | `frontend/dist`（构建产物） | 前端静态文件，`StaticFiles` 托管 |
| `/app/data` | `data/` | `rules/`、`companies/`、`cases/`、`templates/` |
| `/app/backend/data` | 指向 `/app/data` 的软链接 | 兼容以 CWD 为基准的相对路径 `data/` |

后端若用 `Path(__file__).parents[3] / "data"` 定位数据（`backend/app/<pkg>/*.py`），
在容器里正好解析成 `/app/data`；镜像同时保留 `/app/backend/data` 软链接，避免相对路径写法失效。

健康检查与排障：

```bash
curl -s http://127.0.0.1:7860/api/health          # 期望 {"ok":true}
curl -s http://127.0.0.1:7860/api/demo/cases | head

docker inspect --format '{{.State.Health.Status}}' <container>   # healthy
docker logs -f <container>
```

镜像内置 `HEALTHCHECK`（30s 间隔、20s 启动宽限），请求 `http://127.0.0.1:7860/api/health`。
job/case 存在内存中，容器重启后丢失，属预期行为。

## 魔搭创空间

- 空间类型选 **Docker**；优先用 `deploy/Dockerfile.static`（只依赖 `python:3.12-slim`，需仓库包含 `frontend/dist`）；
  若平台能拉 Docker Hub，也可用 `deploy/Dockerfile` 的多阶段构建。**单容器**，不要拆前后端。
- 必须监听 `0.0.0.0:7860`（平台只暴露这一个端口），`EXPOSE 7860` 已在镜像中声明。
- 环境变量在创空间设置页配置：`DEMO_MODE=true`、`PORT=7860`；`LLM_API_KEY` / `LLM_BASE_URL` 可留空。
- 免费实例会**休眠**：一段时间无请求后容器被回收，下次访问需要冷启动（数十秒）。
  演示前先**预热**一次，避免评委看到首次请求超时：

  ```bash
  curl -s https://<space-host>/api/health
  curl -s https://<space-host>/api/demo/cases
  ```

- 预热后再打开页面或跑冒烟测试；镜像不装 GPU 依赖，纯 CPU 即可。
- 演示数据已脱敏，报告不构成法律意见。

## 测试

```bash
# 1) 语法检查（不需要依赖安装）
python -m py_compile scripts/smoke_test.py

# 2) 部署契约静态检查（不联网、不启动服务）
python -m pytest tests/test_contracts.py -q

# 3) 冒烟测试：服务已在 7860 运行后执行，脚本不会自己启动服务
python scripts/smoke_test.py
BASE_URL=http://127.0.0.1:7860 python scripts/smoke_test.py
SMOKE_JOB_TIMEOUT=120 python scripts/smoke_test.py
```

冒烟脚本依赖 `httpx`（已在 `backend/requirements.txt` 中，装完后端依赖即可）；
契约测试需要 `pytest`（不在运行时依赖里，按需安装或跳过第 2 项）。

冒烟测试覆盖：`/api/health` → `/api/demo/cases`（≥3 条，含 `supplier-deposit`）→
`POST /api/demo/supplier-deposit/run` → 轮询 `/api/jobs/{job_id}`（最多 90 秒，可用
`SMOKE_JOB_TIMEOUT` 调整）→ 校验 `report.risks >= 5`、带 `law` 的风险 `>= 3`、
`decision.verdict in {negotiate, reject}`，并打印每步 PASS/FAIL 与总耗时，退出码 0/1。

`BASE_URL` 默认 `http://127.0.0.1:7860`，可直接指向魔搭空间地址做线上验证。

## 演示数据

`data/cases/*.json` 为脱敏演示案例；真实模式接官方公开源（国家企业信用信息公示系统、裁判文书网、信用中国）。演示结果不构成法律意见。
