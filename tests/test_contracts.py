"""部署契约的纯静态检查：不启动服务、不发网络请求。

运行：python -m pytest tests/test_contracts.py -q
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[1]
DOCKERFILE = ROOT / "deploy" / "Dockerfile"
SMOKE_TEST = ROOT / "scripts" / "smoke_test.py"
ENV_EXAMPLE = ROOT / ".env.example"
README = ROOT / "README.md"

DEMO_CASES = ("supplier-deposit", "training-loan", "rental-clean")
ENV_KEYS = {
    "DEMO_MODE": "true",
    "LLM_API_KEY": "",
    "LLM_BASE_URL": "",
    "PORT": "7860",
}


def read_text(path: Path) -> str:
    assert path.is_file(), f"缺少文件：{path.relative_to(ROOT)}"
    return path.read_text(encoding="utf-8")


def find_key(payload: Any, key: str) -> Any:
    """在嵌套 JSON 中递归查找第一个同名 key（案例文件结构允许扁平或嵌套）。"""
    if isinstance(payload, dict):
        if key in payload:
            return payload[key]
        for value in payload.values():
            found = find_key(value, key)
            if found is not None:
                return found
    elif isinstance(payload, list):
        for item in payload:
            found = find_key(item, key)
            if found is not None:
                return found
    return None


# ---------- Dockerfile ----------


def test_dockerfile_builds_frontend_with_node():
    text = read_text(DOCKERFILE)

    assert "FROM node:20-slim AS build" in text
    assert "WORKDIR /app/frontend" in text
    assert "COPY frontend/package*.json" in text
    assert "npm ci" in text and "npm install" in text
    assert "COPY frontend/" in text
    assert "npm run build" in text


def test_dockerfile_runtime_layout():
    text = read_text(DOCKERFILE)

    assert "FROM python:3.11-slim" in text
    assert "WORKDIR /app" in text
    assert "COPY backend/requirements.txt" in text
    assert "pip install --no-cache-dir -r" in text
    assert "COPY backend /app/backend" in text
    assert "COPY data /app/data" in text
    assert "COPY --from=build /app/frontend/dist /app/backend/static" in text
    assert "WORKDIR /app/backend" in text


def test_dockerfile_exposes_7860_and_healthcheck():
    text = read_text(DOCKERFILE)

    assert "EXPOSE 7860" in text
    assert "HEALTHCHECK" in text
    assert "/api/health" in text
    assert "urllib.request" in text
    assert 'CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "7860"]' in text


def test_dockerfile_makes_data_resolvable_from_both_layouts():
    text = read_text(DOCKERFILE)

    # /app/data 对应 backend/app/**/*.py 中 Path(__file__).parents[3] / "data"
    assert "COPY data /app/data" in text
    # /app/backend/data 兜底以 CWD 为基准的 "data" 相对路径
    assert "ln -sfn /app/data /app/backend/data" in text


# ---------- 冒烟脚本 ----------


def test_smoke_test_compiles_and_targets_contract_endpoints():
    source = read_text(SMOKE_TEST)
    compile(source, str(SMOKE_TEST), "exec")

    assert "http://127.0.0.1:7860" in source
    assert "BASE_URL" in source
    for endpoint in ("/api/health", "/api/demo/cases", "/api/jobs/"):
        assert endpoint in source
    assert "supplier-deposit" in source
    assert "90" in source

    # 冒烟脚本只测已运行的服务，不负责启动
    assert "subprocess" not in source
    assert "uvicorn" not in source


# ---------- 环境变量 ----------


def test_env_example_contains_required_keys():
    text = read_text(ENV_EXAMPLE)
    values: dict[str, str] = {}

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip()

    for key, expected in ENV_KEYS.items():
        assert key in values, f".env.example 缺少 {key}"
        assert values[key] == expected, f"{key} 期望 {expected!r}，实际 {values[key]!r}"


# ---------- 演示数据 ----------


def test_demo_case_files_exist_and_are_valid_json():
    cases_dir = ROOT / "data" / "cases"
    if not cases_dir.is_dir():
        pytest.skip("data/cases 尚未生成")

    for demo_id in DEMO_CASES:
        path = cases_dir / f"{demo_id}.json"
        assert path.is_file(), f"缺少演示案例 {path.relative_to(ROOT)}"

        payload = json.loads(path.read_text(encoding="utf-8"))
        assert isinstance(payload, dict) and payload, f"{path.name} 内容为空"
        assert find_key(payload, "contract_text"), f"{path.name} 缺少 contract_text"

    supplier = json.loads(
        (cases_dir / "supplier-deposit.json").read_text(encoding="utf-8")
    )
    verdict = find_key(supplier, "expected_verdict")
    assert verdict in {"negotiate", "reject"}, f"supplier-deposit 期望结论异常：{verdict!r}"


# ---------- README ----------


def test_readme_documents_deploy_modelscope_and_smoke_test():
    text = read_text(README)

    assert "docker build -f deploy/Dockerfile" in text
    assert "7860" in text
    assert "魔搭" in text
    assert "scripts/smoke_test.py" in text
    assert "休眠" in text or "预热" in text
