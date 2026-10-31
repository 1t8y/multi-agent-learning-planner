# 文件：tests/test_tokenize_and_config.py
# 功能：验证 BM25 分词行为和配置加载、环境变量覆盖
# 输入：无；输出：断言结果

from __future__ import annotations

import importlib

from vector_store_core import _tokenize_for_bm25


def test_tokenize_returns_list_for_text():
    """正常中文文本应切出多个 token"""
    tokens = _tokenize_for_bm25("线性代数 特征值")
    assert isinstance(tokens, list)
    assert len(tokens) >= 2


def test_tokenize_handles_empty_and_none():
    """空输入不能抛异常，否则 BM25 检索会整条链路失败"""
    assert _tokenize_for_bm25("") == []
    assert _tokenize_for_bm25(None) == []


def test_tokenize_normalizes_newlines():
    """换行不应把标题和描述粘成一个 token"""
    tokens = _tokenize_for_bm25("Python基础\n变量与函数")
    assert all("\n" not in token for token in tokens)


def test_tokenize_splits_english_terms():
    """英文术语应保留完整单词，便于关键词命中"""
    tokens = _tokenize_for_bm25("Transformer 自注意力")
    assert any("Transformer" in token for token in tokens)


def test_config_exposes_rag_defaults():
    """配置必须提供完整的 rag 参数，缺一个会让下游取到意外的默认值"""
    from config import config

    rag = config.get_defaults().get("rag", {})
    for key in ("similarity_threshold", "min_kb_similarity", "candidate_k", "top_k",
                "rerank_enabled", "rerank_model", "quality_threshold",
                "regeneration_threshold", "max_regeneration_rounds"):
        assert key in rag, f"缺少配置项 {key}"


def test_config_singleton_reused():
    """配置管理器是单例，重复导入不应重新读盘"""
    from config import ConfigManager

    assert ConfigManager() is ConfigManager()


def test_config_env_override(monkeypatch):
    """环境变量应能覆盖 RAG 阈值，便于线上调参"""
    monkeypatch.setenv("RAG_TOP_K", "9")
    monkeypatch.setenv("RAG_QUALITY_THRESHOLD", "0.81")
    import config as config_module

    fresh = importlib.reload(config_module)
    try:
        rag = fresh.ConfigManager().get_defaults()["rag"]
        assert rag["top_k"] == 9
        assert abs(rag["quality_threshold"] - 0.81) < 1e-6
    finally:
        monkeypatch.undo()
        importlib.reload(config_module)


def test_model_config_has_required_keys():
    """模型配置要提供调用外部接口所需的全部字段"""
    from config import config

    model_config = config.get_model_config()
    for key in ("model", "max_tokens", "temperature", "timeout", "retry_count"):
        assert key in model_config


def test_model_loader_prefers_local_cache_then_falls_back(monkeypatch):
    """本地缓存缺失时才联网，且同一模型只加载一次"""
    import sys
    import types

    import model_loader

    calls: list[tuple[str, bool]] = []

    class FakeSentenceTransformer:
        def __init__(self, name, local_files_only=False, **kwargs):
            calls.append((name, local_files_only))
            if local_files_only:
                raise RuntimeError("本地无缓存")

    monkeypatch.setitem(sys.modules, "sentence_transformers",
                        types.SimpleNamespace(SentenceTransformer=FakeSentenceTransformer))
    monkeypatch.setattr(model_loader, "_CACHE", {})

    model = model_loader.get_sentence_transformer("fake/model-under-test")
    again = model_loader.get_sentence_transformer("fake/model-under-test")

    assert model is again, "第二次获取应命中进程内缓存"
    assert calls == [("fake/model-under-test", True), ("fake/model-under-test", False)]

