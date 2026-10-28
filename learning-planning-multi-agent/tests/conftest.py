# 文件：tests/conftest.py
# 功能：pytest 共享夹具与路径配置

from __future__ import annotations

import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
if str(PROJECT_ROOT) not in sys.path:
    sys.path.insert(0, str(PROJECT_ROOT))


@pytest.fixture(scope="session")
def project_root() -> Path:
    """返回后端项目根目录"""
    return PROJECT_ROOT


@pytest.fixture(scope="session")
def kb_rows() -> list[dict]:
    """返回已审核知识库的全部记录"""
    import json

    path = PROJECT_ROOT / "data" / "knowledge_base" / "learning_resources.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


@pytest.fixture(scope="session")
def testset_rows() -> list[dict]:
    """返回 v3 评测测试集记录"""
    import json

    path = PROJECT_ROOT / "data" / "evaluation" / "ragas_testset_v3.jsonl"
    if not path.exists():
        pytest.skip("评测测试集尚未构建，先运行 tools/build_testset.py")
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
