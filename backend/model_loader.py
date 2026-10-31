# 文件：model_loader.py
# 功能：统一管理本地模型加载，优先读本地缓存，避免每次启动都访问 HuggingFace
# 输入：模型名；输出：已就绪的 SentenceTransformer / CrossEncoder 实例

from __future__ import annotations

import os
import threading
from typing import Any, Dict

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DISABLE_TELEMETRY", "1")
os.environ.setdefault("HF_HUB_DISABLE_SSL_VERIFY", "1")

_LOCK = threading.RLock()
_CACHE: Dict[str, Any] = {}
_STATS: Dict[str, Any] = {"local_hits": 0, "network_downloads": 0, "failures": 0}


def _load(kind: str, model_name: str):
    """按类型加载模型：先 local_files_only，失败再联网，结果进程内缓存"""
    key = f"{kind}:{model_name}"
    with _LOCK:
        if key in _CACHE:
            return _CACHE[key]

    if kind == "cross_encoder":
        from sentence_transformers import CrossEncoder as Factory
    else:
        from sentence_transformers import SentenceTransformer as Factory

    try:
        model = Factory(model_name, local_files_only=True)
        with _LOCK:
            _STATS["local_hits"] += 1
        print(f"[model_loader] {kind} 从本地缓存加载: {model_name}")
    except Exception:
        # 本地缺失或版本不兼容时才联网，外部无网络时会快速失败并抛给调用方
        model = Factory(model_name)
        with _LOCK:
            _STATS["network_downloads"] += 1
        print(f"[model_loader] {kind} 联网加载: {model_name}")

    with _LOCK:
        _CACHE[key] = model
    return model


def get_sentence_transformer(model_name: str):
    """输入模型名，返回共享的 SentenceTransformer 实例"""
    return _load("sentence_transformer", model_name)


def get_cross_encoder(model_name: str):
    """输入模型名，返回共享的 CrossEncoder 实例"""
    return _load("cross_encoder", model_name)


def get_loader_stats() -> Dict[str, Any]:
    """返回模型加载统计，供健康检查与基准脚本使用"""
    with _LOCK:
        return {"cached_models": sorted(_CACHE.keys()), **dict(_STATS)}
