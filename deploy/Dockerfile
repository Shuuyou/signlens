# SignLens 单容器镜像：Node 构建前端 -> Python 运行 FastAPI（含静态前端）
# 构建上下文为仓库根目录：
#   docker build -f deploy/Dockerfile -t signlens .

# ---------- stage 1: 前端构建 ----------
FROM node:20-slim AS build

WORKDIR /app/frontend

# 单独复制依赖清单，命中 Docker 层缓存；有 lock 走 npm ci，没有则 npm install
COPY frontend/package*.json ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY frontend/ ./
RUN npm run build

# ---------- stage 2: 运行时 ----------
FROM python:3.11-slim AS runtime

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    DEMO_MODE=true \
    PORT=7860

WORKDIR /app

COPY backend/requirements.txt ./requirements.txt
RUN pip install --no-cache-dir -r ./requirements.txt

COPY backend /app/backend
COPY data /app/data
COPY --from=build /app/frontend/dist /app/backend/static

# 兼容两种 data 目录定位方式：
#   - 绝对/仓库根布局：backend/app/**/*.py 的 Path(__file__).parents[3] / "data" -> /app/data
#   - 以 CWD 为基准的相对路径 "data" -> /app/backend/data
RUN ln -sfn /app/data /app/backend/data

WORKDIR /app/backend

EXPOSE 7860

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
    CMD python -c "import sys, urllib.request; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:7860/api/health', timeout=3).status == 200 else 1)"

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]
