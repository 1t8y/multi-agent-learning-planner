"""需求提取五字段完整性（默认值推断）回归测试

对应任务清单 T8：用户没提时间/基础/偏好时，五字段不能留 null。
这里只测关键词提取 + 默认值填充（不调用 LLM），保证可离线、可秒级运行。
"""

import pytest

from requirement_extractor import RequirementExtractorAgent

FIELDS = (
    "learning_objective",
    "current_foundation",
    "daily_available_time",
    "learning_preference",
    "time_expectation",
)

# 10 组典型输入：覆盖「什么都没说」「说了部分字段」「用不同时间说法」三类
TYPICAL_INPUTS = [
    "我想学 Python 编程",
    "我是零基础，每天能学2小时，想用视频学 Python，希望一个月内入门",
    "有 Java 基础，想三个月内转 Go 后端",
    "准备考研数学，每天3小时，看文字资料，长期系统学习",
    "想尽快学会 Docker",
    "想学机器学习，一学期内掌握",
    "零基础想学前端开发，喜欢看视频",
    "我是中级水平，想做实战项目练手，每天1小时",
    "想学数据分析，短期突击一下",
    "计划半年内精通 C++",
]


@pytest.fixture(scope="module")
def agent():
    """构造需求提取 Agent（不触发任何网络调用）"""
    return RequirementExtractorAgent()


@pytest.mark.parametrize("user_input", TYPICAL_INPUTS)
def test_typical_inputs_fill_all_five_fields(agent, user_input):
    """10 组典型输入都必须给出非 null 的五字段，且枚举值合法"""
    result = agent._apply_defaults(agent._extract_by_keywords(user_input))

    for field in FIELDS:
        assert result.get(field) is not None, f"{user_input!r} 的 {field} 仍为 null"

    assert result["current_foundation"] in {"零基础", "初级", "中级"}
    assert result["learning_preference"] in {"视频", "文字", "实操"}
    assert result["time_expectation"] in {"快速入门", "短期学习", "标准学习", "长期学习"}
    assert len(result["learning_objective"]) >= 2


@pytest.mark.parametrize(
    "user_input,expected",
    [
        ("我想学 Python，一周内搞定", "快速入门"),
        ("想尽快上手 Docker", "快速入门"),
        ("希望一个月内学完机器学习", "短期学习"),
        ("计划三个月内掌握 Go", "标准学习"),
        ("准备花半年时间系统学算法", "长期学习"),
        ("这学期想学好线性代数", "长期学习"),
    ],
)
def test_time_expectation_keyword_mapping(agent, user_input, expected):
    """时间词表到四档时间期望的映射（含本轮新增的尽快/一学期等说法）"""
    assert agent._extract_time_expectation(user_input) == expected


def test_unmentioned_time_falls_back_to_long_term(agent):
    """完全没提时间时默认长期学习，并标记为推断字段"""
    result = agent._apply_defaults(agent._extract_by_keywords("我想学 Python 编程"))

    assert result["time_expectation"] == "长期学习"
    assert "time_expectation" in result["_inferred_fields"]


def test_non_learning_input_stays_null(agent):
    """非学习类输入不能被补出需求（不替用户编造学习目标）"""
    for text in ("今天天气怎么样", "帮我订个会议室"):
        result = agent._apply_defaults(agent._extract_by_keywords(text))

        assert result["learning_objective"] is None
        assert all(result[field] is None for field in FIELDS)
        assert result["_inferred_fields"] == []


def test_defaults_do_not_overwrite_user_input(agent):
    """用户明确说过的字段不能被默认值覆盖"""
    text = "我是零基础，每天能学2小时，想用视频学 Python，希望一个月内入门"
    result = agent._apply_defaults(agent._extract_by_keywords(text))

    assert result["current_foundation"] == "零基础"
    assert result["daily_available_time"] == "2小时"
    assert result["learning_preference"] == "视频"
    assert result["time_expectation"] == "短期学习"
    # 四项都是用户自己说的，不应出现在推断清单里
    assert result["_inferred_fields"] == []


def test_empty_input_returns_all_null(agent):
    """空输入走默认结果，不触发推断"""
    result = agent.extract("   ")

    assert all(result[field] is None for field in FIELDS)
    assert result["_inferred_fields"] == []


RAW_CLAUSE_CASES = [
    ("5小时，想系统学概率论与数理统计，为后面学机器学习打底，喜欢看文字资料", True),
    ("每天能学2小时", True),
    ("我是零基础想学 Python", True),
    ("，想学数据分析", True),
    ("能做出一个小项目", False),
    ("用视频学 Python", False),
    ("Python编程", False),
]


@pytest.mark.parametrize("value,expected", RAW_CLAUSE_CASES)
def test_raw_clause_detection(agent, value, expected):
    """关键词抓到的目标串是否只是原句残片（决定要不要让位给 LLM 结果）"""
    assert agent._looks_like_raw_clause(value) is expected


def test_llm_objective_wins_over_raw_keyword_clause(agent, monkeypatch):
    """LLM 抽对了目标时不能被关键词残片以「更长」为由覆盖

    真实事故：输入「我有微积分和线性代数基础，每天能学1.5小时，想系统学概率论与数理统计…」
    LLM 给出「系统学习概率论与数理统计，为机器学习打底」，关键词却抓到以「5小时，」开头的残片，
    旧逻辑取更长的一方，结果页面上显示的是残片。
    """
    monkeypatch.setattr(
        agent,
        "_call_api",
        lambda _text: {
            "learning_objective": "系统学习概率论与数理统计，为机器学习打底",
            "current_foundation": "中级",
            "daily_available_time": "1.5小时",
            "learning_preference": "文字",
            "time_expectation": "长期学习",
        },
    )

    result = agent.extract("我有微积分和线性代数基础，每天能学1.5小时，想系统学概率论与数理统计，为后面学机器学习打底，喜欢看文字资料")

    assert result["learning_objective"] == "系统学习概率论与数理统计，为机器学习打底"
    assert result["daily_available_time"] == "1.5小时"


def test_keyword_objective_used_when_llm_missing(agent, monkeypatch):
    """LLM 没给出目标时，仍然用关键词结果兜底"""
    monkeypatch.setattr(
        agent,
        "_call_api",
        lambda _text: {"learning_objective": None, "current_foundation": "零基础"},
    )

    result = agent.extract("零基础想学前端开发，喜欢看视频")

    assert result["learning_objective"] is not None
    assert "前端" in result["learning_objective"]
