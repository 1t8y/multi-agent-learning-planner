"""Agent 提示词来源回归测试

对应任务清单 T9：代码里不再引用不存在的外置提示词目录，
四个 Agent 的系统提示词只有一个来源——各自的 `_get_default_prompt`。
"""

from pathlib import Path

import pytest

from base_agent import BaseAgent

PACKAGE_ROOT = Path(__file__).resolve().parent.parent
# 拆开拼是为了不让自己出现在「全仓搜索该路径」的结果里（这个字符串是搜索模式，不是引用）
DEAD_PROMPT_DIR = ".trae" + "/agents"
AGENT_FILES = [
    "requirement_extractor.py",
    "course_planner.py",
    "resource_recommender.py",
    "assessment_feedback.py",
    "base_agent.py",
]


class _DummyAgent(BaseAgent):
    """最小可实例化的 Agent，用于验证基类的提示词加载路径"""

    AGENT_NAME = "dummy"

    def _get_default_prompt(self) -> str:
        return "DUMMY_PROMPT"

    def _get_default_result(self) -> dict:
        return {}

    def process(self, user_input: str) -> str:
        return user_input


def test_base_agent_uses_default_prompt_without_file_lookup():
    """基类直接返回子类实现的默认提示词，不再尝试读文件"""
    agent = _DummyAgent()

    assert agent.system_prompt == "DUMMY_PROMPT"
    assert agent._load_system_prompt() == "DUMMY_PROMPT"
    assert not hasattr(agent, "_parse_markdown_prompt")


@pytest.mark.parametrize("filename", AGENT_FILES)
def test_no_dead_prompt_path_reference(filename):
    """五个文件里都不能再出现外置提示词目录 / PROMPT_FILE 常量"""
    source = (PACKAGE_ROOT / filename).read_text(encoding="utf-8")

    assert ".trae" not in source
    assert "PROMPT_FILE" not in source
    assert "_get_prompt_path" not in source


def test_package_has_no_dead_prompt_directory_reference():
    """全包扫描：除测试自身外，没有任何 .py 指向不存在的提示词目录"""
    offenders = [
        path.name
        for path in PACKAGE_ROOT.glob("*.py")
        if DEAD_PROMPT_DIR in path.read_text(encoding="utf-8").replace("\\", "/")
    ]

    assert offenders == []
