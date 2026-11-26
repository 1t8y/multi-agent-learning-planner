# 文件：src/rag/advanced_self_rag.py
# 功能：扩展 Self-RAG，加入正向查询、元数据过滤、Cross-Encoder 重排和质量门控
# 输入：学习目标、基础、偏好和计划；输出：经过重排与质量检查的资源
from __future__ import annotations

import re
from typing import Any

from src.config import config
from src.rag.rag_quality import RAGQualityChecker
from src.rag.reranker import ResourceReranker
from src.rag.self_rag_recommender import RAGState, SelfRAGRecommender


class AdvancedSelfRAGRecommender(SelfRAGRecommender):
    """增强版 Self-RAG，模型或质量检查异常时保留基础检索能力"""

    def __init__(self):
        """读取 RAG 配置并初始化重排器和质量检测器"""
        super().__init__()
        rag = config.get_defaults().get("rag", {})
        self.CANDIDATE_K = int(rag.get("candidate_k", 10))
        self.TOP_K = int(rag.get("top_k", 5))
        self.MIN_TYPES = int(rag.get("min_types", 0))
        # RRF 粗筛（0.15）必须严格低于门控硬线 hard_cosine（0.25）：
        # 粗筛全灭直接联网；落在 [0.15, 0.25) 的候选交给门控硬线判 web。
        # 两者同值时硬线永远拿不到候选，只剩空候选这一条 web 路径。
        self.MIN_DENSE_SIMILARITY = float(rag.get("rrf_min_dense_similarity", 0.15))
        self.MIN_BM25_SCORE = float(rag.get("rrf_min_bm25_score", 1.0))
        self.reranker = ResourceReranker(
            model_name=rag.get("rerank_model", "BAAI/bge-reranker-base"),
            enabled=bool(rag.get("rerank_enabled", True)),
            min_confidence=float(rag.get("rerank_min_confidence", 0.0)),
        )
        self.quality_checker = RAGQualityChecker(
            threshold=float(rag.get("quality_threshold", 0.55))
        )

    def _clean_objective(self, text: str) -> str:
        """输入学习目标，返回移除否定句和评测措辞的正向查询"""
        cleaned = text or ""
        cleaned = re.sub(r"不是[^，,。；;]*[，,。；;]?\s*而是", "", cleaned)
        cleaned = re.sub(r"(应该优先推荐哪条资源|哪条资源最匹配|推荐哪条资源|平台应推荐)[？?]?", "", cleaned)
        cleaned = re.sub(r"(我需要的|我想找的|我想要的)", "", cleaned)
        return re.sub(r"\s+", " ", cleaned).strip(" ，,。；;？?")

    def _map_resource_types(self, preference: str | None) -> list[str] | None:
        """输入学习偏好，返回对应的资源类型过滤列表"""
        return {
            "视频": ["视频教程"],
            "文字": ["文字教程", "文档资料"],
            "实操": ["实战项目"],
        }.get(preference or "")

    def _detect_field(self, query: str) -> str:
        """输入查询，优先识别包含多个数学关键词的数学学习需求"""
        text = (query or "").lower()
        math_terms = ["数学", "微积分", "线性代数", "概率论", "统计", "math"]
        if sum(term in text for term in math_terms) >= 2:
            return "数学"
        return super()._detect_field(query)

    def _map_level_filter(self, foundation: str | None) -> str | None:
        """输入现有基础，返回严格的资源难度过滤值"""
        if foundation == "零基础":
            return "beginner"
        if foundation == "中级":
            return "intermediate"
        return None

    def _build_search_query(self, state: RAGState) -> str:
        """输入 RAG 状态，返回包含目标、基础和时间期望的正向查询"""
        if state.rewritten_query:
            return state.rewritten_query
        parts = [self._clean_objective(state.learning_objective)]
        if state.current_foundation:
            parts.append(state.current_foundation)
        if getattr(state, "learning_preference", None):
            parts.append(getattr(state, "learning_preference"))
        if getattr(state, "time_expectation", None):
            parts.append(getattr(state, "time_expectation"))
        return " ".join(part for part in parts if part)

    def _search_candidates(self, query: str, field: str | None, level: str | None,
                           resource_types: list[str] | None) -> tuple[list[dict[str, Any]], dict[str, Any]]:
        """输入查询和过滤条件，返回逐级降级后的候选资源与最终过滤信息"""
        attempts = [
            {"field": field, "level": level, "resource_types": resource_types},
            {"field": field, "level": None, "resource_types": resource_types},
            {"field": field, "level": None, "resource_types": None},
            {"field": None, "level": None, "resource_types": None},
        ]
        for filters in attempts:
            results = self.retriever.search(
                query=query, field=filters["field"], level=filters["level"],
                top_k=self.CANDIDATE_K, mode="hybrid",
                resource_types=filters["resource_types"],
                min_types=self.MIN_TYPES,
                min_dense_similarity=self.MIN_DENSE_SIMILARITY,
                min_bm25_score=self.MIN_BM25_SCORE,
            )
            if results:
                return results, filters
            if getattr(self.retriever, "last_no_hit_reason", ""):
                # dense 侧绝对没命中：放宽 where 过滤不会凭空变出更相关的候选，
                # 直接停止降级，省掉后面几轮无意义的双路检索。
                break
        return [], attempts[0]

    def _search_kb(self, state: RAGState) -> RAGState:
        """输入 RAG 状态，执行过滤检索、候选重排和质量检测"""
        if not self.retriever or not self.retriever.ready:
            state.kb_results, state.kb_relevance_score = [], 0.0
            return state
        query = self._build_search_query(state)
        field = self._detect_field(query)
        level = self._map_level_filter(state.current_foundation)
        resource_types = self._map_resource_types(getattr(state, "learning_preference", None))
        candidates, filters = self._search_candidates(query, field if field != "其他" else None, level, resource_types)
        reranked = self.reranker.rerank(query, candidates, self.TOP_K)
        # 不再用 sigmoid 置信度覆盖 similarity：旧写法把真实 cosine 0.05 伪造成 0.54，
        # 让 MIN_KB_SIMILARITY 过滤失效、前端相似度变成假值。
        # dense_similarity 由检索层标注，是门控唯一的绝对语义信号。
        report = self.quality_checker.evaluate(
            reranked, field=filters["field"], level=filters["level"],
            resource_types=filters["resource_types"],
        )
        state.field = field
        state.kb_results = reranked
        state.kb_search_count += 1
        state.kb_relevance_score = report["score"]
        state.quality = report
        state.decision = report["decision"]
        state.no_hit_reason = getattr(self.retriever, "last_no_hit_reason", "")
        state.candidate_count = len(candidates)
        state.rerank_used = self.reranker.status()["available"]
        state.filters = filters
        state.search_query = query
        signals = report.get("signals", {})
        print(f"[AdvancedRAG] 候选={len(candidates)} 重排={len(reranked)} "
              f"质量={report['grade']} 分数={report['score']} 决策={report['decision']} "
              f"cos={signals.get('top_dense_similarity')} logit={signals.get('top_rerank_logit')}"
              + (f" 跳过融合={state.no_hit_reason}" if state.no_hit_reason else ""))
        return state

    def _evaluate_results(self, state: RAGState, use_llm: bool = False) -> str:
        """输入 RAG 状态，按质量报告的 decision 决定通过、改写或直接联网。

        web     两路绝对信号同时低于硬线（或 RRF 跳过融合导致无候选）
                → 知识库无覆盖，跳过改写直接联网；
        rewrite 单路偏弱 / 总分未过线 → 改写查询，达到上限后联网；
        pass    两路都够且总分达标 → 直接推荐。
        """
        if not state.kb_results:
            state.decision = "web"
            return "kb_empty"
        report = getattr(state, "quality", None) or self.quality_checker.evaluate(state.kb_results)
        state.quality = report
        state.kb_relevance_score = report["score"]
        decision = report.get("decision", "pass" if report["passed"] else "rewrite")
        state.decision = decision
        if decision == "pass" and report["passed"]:
            return "sufficient"
        if decision == "web" or state.rewrite_count >= self.MAX_REWRITE_TIMES:
            return "kb_empty"
        return "insufficient"

    def _rewrite_query(self, state: RAGState) -> RAGState:
        """输入 RAG 状态，生成更短、更正向的检索查询"""
        topic = self._clean_objective(state.learning_objective)
        strategies = [
            topic,
            f"{topic} 入门 教程",
            f"{topic} 系统学习 推荐资源",
        ]
        state.rewritten_query = strategies[state.rewrite_count % len(strategies)]
        state.rewrite_count += 1
        return state

    def _attach_scores(self, state: RAGState) -> None:
        """把相似度和重排分数附加到最终资源对象"""
        # 优先按 id 精确匹配：只按标题建索引时，同名不同来源的资源会互相覆盖，
        # 把已透传给前端的 id 改成另一条资源，后续反馈就会写到错误的资源上。
        by_id = {item.get("id"): item for item in state.kb_results
                 if isinstance(item, dict) and item.get("id")}
        by_title = {item.get("title", ""): item for item in state.kb_results
                    if isinstance(item, dict)}
        for rank, resource in enumerate(state.final_resources, start=1):
            source = (by_id.get(resource.get("id"))
                      or by_title.get(resource.get("title", ""), {}))
            resource.update({
                # 已透传的 id 不能被覆盖；找不到来源时仍给空串，保持原有输出结构
                "id": resource.get("id") or source.get("id", ""),
                "rank": rank,
                "similarity": source.get("similarity", 0),
                "rerank_score": source.get("rerank_score"),
                "rerank_confidence": source.get("rerank_confidence"),
                "dense_similarity": source.get("dense_similarity"),
            })

    def recommend(self, learning_objective: str, current_foundation: str = "零基础",
                  learning_plan: dict | None = None, learning_preference: str | None = None,
                  time_expectation: str | None = None) -> dict:
        """输入结构化学习需求，执行完整增强版 Self-RAG 流程"""
        state = RAGState(learning_objective=learning_objective, current_foundation=current_foundation)
        state.learning_preference = learning_preference
        state.time_expectation = time_expectation
        state.quality, state.candidate_count = {}, 0
        state.rerank_used, state.filters, state.search_query = False, {}, ""
        state.decision, state.no_hit_reason = "pass", ""
        state = self._search_kb(state)
        decision = self._evaluate_results(state)
        while decision == "insufficient":
            state = self._rewrite_query(state)
            state = self._search_kb(state)
            decision = self._evaluate_results(state)
        if decision == "kb_empty":
            # 硬线判定为「知识库无覆盖」时，不能把那批不相关 KB 结果混进最终推荐。
            # 改写次数耗尽的情况则保留 KB 结果，让联网资源作为补充。
            if getattr(state, "decision", "") == "web":
                state.kb_results = []
                print(f"[AdvancedRAG] 判定知识库无覆盖，跳过改写直接联网"
                      + (f"（{state.no_hit_reason}）" if state.no_hit_reason else ""))
            state = self._search_web(state)
        state = self._merge_and_select(state)
        self._attach_scores(state)
        status_fn = getattr(self.web_search, "status", None)
        web_status = status_fn() if callable(status_fn) else {}

        result = {
            "resources": state.final_resources,
            "source_info": state.source_info,
            "kb_relevance": state.kb_relevance_score,
            "rewrite_count": state.rewrite_count,
            "used_web_search": len(state.web_results) > 0,
            "quality": state.quality,
            "rerank": self.reranker.status(),
            "candidate_count": state.candidate_count,
            "filters": state.filters,
            "search_query": state.search_query,
            "web_error": state.web_error,
            "web_search_status": web_status,
            "decision": state.decision,
            "no_hit_reason": state.no_hit_reason,
        }
        result["rag_info"] = {
            "source_info": state.source_info,
            "kb_relevance": state.kb_relevance_score,
            "rewrite_count": state.rewrite_count,
            "used_web_search": len(state.web_results) > 0,
            "quality": state.quality,
            "rerank": result["rerank"],
            "candidate_count": state.candidate_count,
            "filters": state.filters,
            "search_query": state.search_query,
            "web_error": state.web_error,
            "web_search_status": web_status,
            "decision": state.decision,
            "no_hit_reason": state.no_hit_reason,
        }
        return result
