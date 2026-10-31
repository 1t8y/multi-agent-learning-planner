# 文件：reranker.py
# 功能：使用 Cross-Encoder 对混合检索候选做精排
# 输入：用户查询和候选资源；输出：按重排置信度排序的资源
from __future__ import annotations

import math
import os
from typing import Any

from model_loader import get_cross_encoder

os.environ.setdefault("HF_ENDPOINT", "https://hf-mirror.com")
os.environ.setdefault("HF_HUB_DISABLE_SSL_VERIFY", "1")


class ResourceReranker:
    """Cross-Encoder 重排器，模型加载失败时自动退回原排序"""

    def __init__(
        self,
        model_name: str = "BAAI/bge-reranker-base",
        enabled: bool = True,
        min_confidence: float = 0.0,
    ):
        """
        输入模型名、开关和门控阈值，初始化懒加载重排器。

        min_confidence 为 0 表示不做门控（全量重排）。
        大于 0 时，若首位候选的重排置信度低于该阈值，则保留融合顺序，
        但仍把重排分数回填到结果上，供下游质量门控继续使用。
        """
        self.model_name = model_name
        self.enabled = enabled
        self.min_confidence = float(min_confidence)
        self.last_gate_fallback = False
        self._model = None
        self._load_attempted = False

    def _ensure_model(self) -> None:
        """首次调用时加载 Cross-Encoder 模型（本地缓存优先，进程内共享）"""
        if self._load_attempted or not self.enabled:
            return
        self._load_attempted = True
        try:
            self._model = get_cross_encoder(self.model_name)
            print(f"[reranker] Cross-Encoder 已就绪: {self.model_name}")
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
        annotated = [
            {
                **item,
                "rerank_score": round(float(score), 5),
                "rerank_confidence": self._confidence(float(score)),
            }
            for item, score in zip(resources, scores)
        ]
        ranked = sorted(annotated, key=lambda item: item["rerank_score"], reverse=True)
        if self.min_confidence > 0 and ranked[0]["rerank_confidence"] < self.min_confidence:
            # 首位候选都拿不到足够置信度，说明模型对这题没有判断力，
            # 此时按融合顺序返回更安全（实测该区间重排会净掉分）
            self.last_gate_fallback = True
            return annotated[:top_k]
        self.last_gate_fallback = False
        return ranked[:top_k]

    def status(self) -> dict[str, Any]:
        """返回重排器当前配置和可用状态"""
        self._ensure_model()
        return {
            "enabled": self.enabled,
            "available": self._model is not None,
            "model": self.model_name,
            "min_confidence": self.min_confidence,
        }
