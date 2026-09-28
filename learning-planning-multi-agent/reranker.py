# 文件：reranker.py
# 功能：使用 Cross-Encoder 对混合检索候选做精排
# 输入：用户查询和候选资源；输出：按重排置信度排序的资源
from __future__ import annotations

import math
import os
from typing import Any

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DISABLE_SSL_VERIFY", "1")


class ResourceReranker:
    """Cross-Encoder 重排器，模型加载失败时自动退回原排序"""

    def __init__(self, model_name: str = "BAAI/bge-reranker-base", enabled: bool = True):
        """输入模型名和开关，初始化懒加载重排器"""
        self.model_name = model_name
        self.enabled = enabled
        self._model = None
        self._load_attempted = False

    def _ensure_model(self) -> None:
        """首次调用时加载 Cross-Encoder 模型"""
        if self._load_attempted or not self.enabled:
            return
        self._load_attempted = True
        try:
            from sentence_transformers import CrossEncoder

            self._model = CrossEncoder(self.model_name)
            print(f"[reranker] Cross-Encoder 已加载: {self.model_name}")
        except Exception as exc:
            self._model = None
            print(f"[reranker] 重排模型不可用，使用原排序: {exc}")

    def _confidence(self, score: float) -> float:
        """输入重排原始分，返回 0 到 1 的置信度"""
        return round(1.0 / (1.0 + math.exp(-float(score))), 5)

    def rerank(self, query: str, resources: list[dict[str, Any]], top_k: int = 5) -> list[dict[str, Any]]:
        """输入查询、候选和数量，返回重排后的资源列表"""
        if not resources:
            return []
        self._ensure_model()
        if not self._model:
            return resources[:top_k]
        pairs = [
            (query, f"{item.get('title', '')}\n{item.get('description', '')}")
            for item in resources
        ]
        scores = self._model.predict(pairs, convert_to_numpy=True)
        ranked = []
        for item, score in zip(resources, scores):
            ranked.append({
                **item,
                "rerank_score": round(float(score), 5),
                "rerank_confidence": self._confidence(float(score)),
            })
        ranked.sort(key=lambda item: item["rerank_score"], reverse=True)
        return ranked[:top_k]

    def status(self) -> dict[str, Any]:
        """返回重排器当前配置和可用状态"""
        self._ensure_model()
        return {
            "enabled": self.enabled,
            "available": self._model is not None,
            "model": self.model_name,
        }
