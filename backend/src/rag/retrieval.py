# 文件：src/rag/retrieval.py
# 功能：检索策略层——把存储层召回的两路原始候选，融合、去重、约束成最终结果
# 说明：本层只决定「怎么组合结果」，不决定「怎么存、怎么取原始候选」。
#       Chroma 读写、BM25 索引维护都在 src/memory/，两边职责不重叠。
#
# 一次检索的概念流程（与下方 HybridRetriever.search 的编号步骤一一对应）：
#   1. 就绪检查        没初始化就直接返回空，不抛异常
#   2. 确定候选池大小  池子要 ≥ top_k，否则后面过滤完不够数
#   3. 查缓存          键里带数据版本号，写库后自然不命中
#   4. 双路召回        dense（语义）+ sparse（BM25 关键词）
#   4.5 绝对分数过滤   可选；低于阈值的候选不参与融合，dense 全灭则跳过融合
#   5. 融合            hybrid 用 RRF；单路则用各自的分数
#   6. 去重            同一 URL 只留一条
#   7. 多样性约束      可选，保证至少覆盖 N 种资源类型
#   8. 截断 + 写缓存 + 记耗时

from __future__ import annotations

import threading
import time
from collections import OrderedDict
from typing import Any, Dict, List, Optional, Tuple

from src.memory.vector_store_core import VectorStoreManager

# ----------------------------------------------------------------------
# RRF 融合参数
#
#   score = Σ wᵢ / (K + rankᵢ)
#
# K 是平滑常数：越小，头几名之间的分差越大（第 1 名优势更明显）。
# w 是两路各自的话语权：调大 dense 更看重语义，调大 sparse 更看重关键词命中。
# 默认 60 / 1.0 / 1.0 是业界常用值。本项目的十档消融没有做过权重档，
# 所以调 w 之前请先跑 `python -m eval.bench_retrieval` 看 Hit@1 / MRR@5 是否真的变好。
# ----------------------------------------------------------------------
RRF_K = 60
RRF_DENSE_WEIGHT = 1.0
RRF_SPARSE_WEIGHT = 1.0

# 单实例的检索结果 LRU 容量
DEFAULT_CACHE_SIZE = 256


def _copy_result(item: Dict) -> Dict:
    """复制一条检索结果；tags 这类嵌套列表也要断开与缓存本体的引用。"""
    copied = dict(item)
    tags = copied.get("tags")
    if isinstance(tags, list):
        copied["tags"] = list(tags)
    return copied


def _safe_score(value: Any) -> float:
    """把可能为 None / 字符串的分数安全转成 float，脏数据按 0 处理。"""
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


# ======================================================================
# 一、四个纯算法函数：只吃列表、只吐列表，不碰数据库，便于单测
# ======================================================================

def normalize_sparse(sparse_results: List[Dict]) -> List[Dict]:
    """把 BM25 分数按本批次最大值缩放到 0~1。

    下游（质量检测、相似度展示）统一按 0~1 理解 similarity，
    而 BM25 原始分是无上界的，所以纯稀疏模式必须做这一步归一化。
    """
    if not sparse_results:
        return []
    top = max(item.get("bm25_score", 0.0) for item in sparse_results) or 1.0
    return [{**item, "similarity": round(item.get("bm25_score", 0.0) / top, 5)}
            for item in sparse_results]


def rrf_merge(dense_results: List[Dict], sparse_results: List[Dict],
              top_k: int = 5, *,
              k: int = RRF_K,
              dense_weight: float = RRF_DENSE_WEIGHT,
              sparse_weight: float = RRF_SPARSE_WEIGHT) -> List[Dict]:
    """Reciprocal Rank Fusion：按名次融合两路候选。

    score = Σ wᵢ / (k + rankᵢ)

    只使用名次，不使用原始分数，因此不需要把余弦相似度和 BM25 放在同一量纲上比较。
    原始分数仍保留在 similarity / bm25_score 里，融合分单独记在 fused_score，
    两路名次记在 rank_dense / rank_sparse —— 排查排序问题时看这三个字段。

    只被 sparse 命中的文档没有余弦相似度，这里用「本批 BM25 最大值」归一化后填入，
    保证下游读 similarity 时不会拿到 None。
    """
    fused: Dict[str, Dict[str, Any]] = {}

    # dense 侧：按名次累加权重分
    for rank, item in enumerate(dense_results, start=1):
        doc_id = item.get("id") or f"dense-{rank}"
        entry = fused.setdefault(doc_id, {**item, "rank_dense": rank, "rank_sparse": None})
        entry["rrf_score"] = entry.get("rrf_score", 0.0) + dense_weight / (k + rank)

    # sparse 侧：先算本批最大 BM25，供「只在稀疏侧出现」的文档补 similarity
    top_bm25 = max((item.get("bm25_score", 0.0) for item in sparse_results), default=1.0) or 1.0
    for rank, item in enumerate(sparse_results, start=1):
        doc_id = item.get("id") or f"sparse-{rank}"
        entry = fused.get(doc_id)
        if entry is None:
            entry = {**item, "rank_dense": None, "rank_sparse": rank,
                     "similarity": round(item.get("bm25_score", 0.0) / top_bm25, 5)}
            fused[doc_id] = entry
        else:
            entry["rank_sparse"] = rank
            entry["bm25_score"] = item.get("bm25_score")
        entry["rrf_score"] = entry.get("rrf_score", 0.0) + sparse_weight / (k + rank)

    # 收尾：分数四舍五入、按融合分排序（同分时 dense 名次靠前者优先）
    merged = list(fused.values())
    for item in merged:
        item["fused_score"] = round(item.get("rrf_score", 0.0), 6)
        item["similarity"] = round(float(item.get("similarity", 0.0) or 0.0), 5)
    merged.sort(key=lambda x: (-x.get("fused_score", 0.0),
                               x.get("rank_dense") or 10 ** 6))
    return merged[:top_k]


def dedupe(results: List[Dict]) -> List[Dict]:
    """按 URL 去重；URL 为空时回退到标题。

    同一条资源可能同时被两路召回，融合后仍是同一条（id 相同已在 rrf_merge 合并），
    但不同 id 指向同一 URL 的情况也真实存在（同一门课的不同来源），这里兜住。
    """
    seen, unique = set(), []
    for item in results:
        key = (item.get("url") or "").strip() or (item.get("title") or "").strip()
        if not key or key in seen:
            continue
        seen.add(key)
        unique.append(item)
    return unique


def diversify(results: List[Dict], min_types: int) -> List[Dict]:
    """在保持第一名不变的前提下，让结果至少覆盖 min_types 种资源类型。

    做法：先按原顺序挑出「首次出现的新类型」，直到够数，再把剩余项按原顺序接回去。
    注意这只会调整顺序、不会增加或删除条目。
    """
    if len(results) < 2:
        return results
    chosen, used = [], set()
    chosen.append(results[0])
    used.add(results[0].get("resource_type", ""))
    for item in results[1:]:
        rtype = item.get("resource_type", "")
        if rtype not in used:
            chosen.append(item)
            used.add(rtype)
            if len(used) >= min_types:
                break
    picked = {id(x) for x in chosen}
    chosen.extend(item for item in results if id(item) not in picked)
    return chosen


# ======================================================================
# 二、检索器：持有存储层，负责所有排序与筛选决策
# ======================================================================

class HybridRetriever:
    """混合检索器：双路召回 → RRF 融合 → 去重 → 多样性 → 缓存。

    它只调用存储层的两个「取原始候选」方法（_dense_search / _sparse_search），
    不直接碰 Chroma，也不管 BM25 索引是怎么建的。
    """

    RRF_K = RRF_K
    RRF_DENSE_WEIGHT = RRF_DENSE_WEIGHT
    RRF_SPARSE_WEIGHT = RRF_SPARSE_WEIGHT

    def __init__(self, store: VectorStoreManager, cache_size: int = DEFAULT_CACHE_SIZE):
        """绑定一个存储层实例，并初始化查询缓存与调用统计。

        参数：
            store       已完成初始化的 VectorStoreManager
            cache_size  查询结果 LRU 容量，按 (版本, 查询, 过滤条件) 缓存
        """
        self.store = store
        self.cache_size = cache_size
        # /api/plan 走线程池，多个请求会并发命中同一个检索器；缓存与计数必须加锁
        self._lock = threading.Lock()
        self._cache: "OrderedDict[Tuple, List[Dict]]" = OrderedDict()
        self._stats = {
            "dense_calls": 0, "sparse_calls": 0, "hybrid_calls": 0,
            "cache_hits": 0, "cache_misses": 0, "latency_ms_total": 0.0,
        }
        # 最近一次「跳过融合」的原因，供上层日志与排障读取；空串表示正常融合
        self.last_no_hit_reason = ""

    @property
    def ready(self) -> bool:
        """存储层是否可用；上层用它决定要不要走检索分支。"""
        return bool(self.store and self.store._initialized)

    def clear_cache(self) -> None:
        """主动清空缓存（一般不需要，写库会自动让版本号变化）。"""
        with self._lock:
            self._cache.clear()

    def search(self,
               query: str,
               field: Optional[str] = None,
               level: Optional[str] = None,
               top_k: int = 5,
               mode: str = "hybrid",
               resource_types: Optional[List[str]] = None,
               candidate_k: Optional[int] = None,
               min_types: int = 0,
               min_dense_similarity: Optional[float] = None,
               min_bm25_score: Optional[float] = None) -> List[Dict]:
        """执行一次检索，返回按相关度排好序的资源列表。

        参数：
            query                   查询文本
            field                   领域过滤（AI / 编程 / 数学）
            level                   难度过滤（beginner / intermediate / advanced）
            top_k                   最终返回条数
            mode                    检索模式：dense / sparse / hybrid
            resource_types          资源类型过滤
            candidate_k             每路召回数量，默认等于 top_k
            min_types               结果至少覆盖几种资源类型，0 表示不约束
            min_dense_similarity    RRF 融合前的绝对余弦下限，None 表示不过滤
            min_bm25_score          RRF 融合前的 BM25 绝对下限，None 表示不过滤

        绝对分数过滤只在显式传入阈值时启用（评测链路保持历史行为）。
        hybrid 模式下若 dense 侧过滤后为空，说明语义上完全没命中，直接跳过
        融合返回空列表，让上层判「知识库无覆盖」并走联网兜底 —— BM25 靠
        「学习 / 基础 / 概念」这类通用词凑出的命中不算有效命中。

        返回的每条结果包含：
            similarity        相似度（稀疏命中时为本批归一化的 BM25）
            dense_similarity  真实稠密余弦（仅 dense 命中的条目带，供门控使用）
            bm25_score        原始 BM25 分（仅稀疏命中）
            fused_score       RRF 融合分（hybrid 排序依据）
            rank_dense / rank_sparse  两路各自的名次，未命中为 None
        """
        # ── 第 1 步：就绪检查。没初始化或空查询直接返回空，不让上层处理异常 ──
        if not self.ready or not query:
            return []

        # ── 第 2 步：候选池大小。池子必须 ≥ top_k，否则过滤后可能凑不满 ──
        pool = max(int(candidate_k or top_k), top_k)

        # ── 第 3 步：查缓存。键里带 store.data_version，写库后旧键自然不再命中 ──
        # 版本号只在本次检索开始时取一次，避免与写库交错时同一个请求的键前后不一致
        cache_key = (self.store.data_version, query, field, level, int(top_k), mode,
                     tuple(sorted(resource_types or ())), pool, int(min_types),
                     min_dense_similarity, min_bm25_score)
        with self._lock:
            cached = self._cache.get(cache_key)
            if cached is not None:
                self._stats["cache_hits"] += 1
                self._cache.move_to_end(cache_key)
                # 缓存里只存结果列表，不存历史诊断原因，命中时清空避免误报
                self.last_no_hit_reason = ""
                return [_copy_result(item) for item in cached]
            self._stats["cache_misses"] += 1
        self.last_no_hit_reason = ""
        started = time.perf_counter()

        # ── 第 4 步：双路召回。dense 走语义，sparse 走 BM25 关键词 ──
        # 慢 IO 放在锁外，计数先记局部变量，收尾时一次性合并，避免并发丢更新
        dense_calls = sparse_calls = hybrid_calls = 0
        dense_results: List[Dict] = []
        if mode in ("dense", "hybrid"):
            dense_results = self.store._dense_search(query, field, level, resource_types, pool)
            dense_calls = 1

        sparse_results: List[Dict] = []
        if mode in ("sparse", "hybrid"):
            sparse_results = self.store._sparse_search(query, pool, field, level, resource_types)
            sparse_calls = 1

        # ── 第 4.5 步：标注真实余弦 + 绝对分数过滤（阈值由调用方显式传入）──
        # RRF 只按名次融合、不看原始分数，库外查询也会被 top-k 最近邻凑满候选，
        # 再被 BM25 的「学习 / 基础 / 概念」等通用词命中送进重排。这里在融合前
        # 先按绝对分过滤；dense_similarity 单独标注，因为 sparse-only 条目的
        # similarity 是批内归一化 BM25，不能冒充语义余弦给门控用。
        for item in dense_results:
            item["dense_similarity"] = _safe_score(item.get("similarity"))
        if min_dense_similarity is not None:
            dense_results = [r for r in dense_results
                             if r["dense_similarity"] >= min_dense_similarity]
        if min_bm25_score is not None:
            sparse_results = [r for r in sparse_results
                              if _safe_score(r.get("bm25_score")) >= min_bm25_score]

        # dense 全灭 = 语义上完全没命中，跳过融合直接返回空，交给上层联网兜底。
        # BM25 的通用词命中不算有效命中，不能让它独自把不相关资源凑成候选。
        skip_fusion = (mode == "hybrid" and min_dense_similarity is not None
                       and not dense_results)
        if skip_fusion:
            self.last_no_hit_reason = (
                f"dense 侧无候选达到绝对相似度下限 {min_dense_similarity}")

        # ── 第 5 步：融合。hybrid 用 RRF；单路模式各自成结果 ──
        if skip_fusion:
            results = []
        elif mode == "hybrid":
            hybrid_calls = 1
            results = rrf_merge(dense_results, sparse_results, pool,
                                k=self.RRF_K,
                                dense_weight=self.RRF_DENSE_WEIGHT,
                                sparse_weight=self.RRF_SPARSE_WEIGHT)
        elif mode == "sparse":
            results = normalize_sparse(sparse_results)
        else:
            results = dense_results

        # ── 第 6 步：去重。同一 URL 只保留排名最靠前的那条 ──
        results = dedupe(results)[:pool]

        # ── 第 7 步：多样性约束（默认关闭）。只调整顺序，不增删条目 ──
        if min_types > 0:
            results = diversify(results, min_types)
        results = results[:top_k]

        # ── 第 8 步：写缓存 + 记耗时。缓存按 LRU 淘汰最久未用的键 ──
        with self._lock:
            self._stats["dense_calls"] += dense_calls
            self._stats["sparse_calls"] += sparse_calls
            self._stats["hybrid_calls"] += hybrid_calls
            self._stats["latency_ms_total"] += (time.perf_counter() - started) * 1000
            self._cache[cache_key] = [_copy_result(item) for item in results]
            while len(self._cache) > self.cache_size:
                self._cache.popitem(last=False)
        return results

    def get_retrieval_stats(self) -> Dict[str, Any]:
        """返回检索侧的调用计数与命中率，供 /api/stats 与评测脚本使用。

        这些数字描述的是「检索策略执行了多少次」，
        与存储层的资源分布统计（get_stats）不是一回事，所以分开提供。
        """
        with self._lock:
            stats = dict(self._stats)
        total_calls = stats["cache_hits"] + stats["cache_misses"]
        return {
            **stats,
            "cache_hit_rate": round(stats["cache_hits"] / total_calls, 4)
            if total_calls else 0.0,
            "avg_latency_ms": round(
                stats["latency_ms_total"] / max(stats["cache_misses"], 1), 2),
        }
