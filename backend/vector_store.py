# 文件：vector_store.py
# 功能：向量库对外统一入口，直接复用 vector_store_core 的实现
# 说明：v2.4.0 起过滤、RRF 融合和分数语义已在 vector_store_core 内实现，
#       本模块不再通过运行期 monkey-patch 覆盖 core 方法，只做导出与兼容。

from __future__ import annotations

from vector_store_core import (  # noqa: F401
    BM25_AVAILABLE,
    CHROMA_AVAILABLE,
    JIEBA_AVAILABLE,
    PREDEFINED_RESOURCES,
    LearningResource,
    VectorStoreManager,
    _tokenize_for_bm25,
    get_cache_stats,
    init_vector_store_with_seed_data,
    load_catalog_seed_resources,
    seed_catalog_resources,
)

__all__ = [
    "BM25_AVAILABLE",
    "CHROMA_AVAILABLE",
    "JIEBA_AVAILABLE",
    "PREDEFINED_RESOURCES",
    "LearningResource",
    "VectorStoreManager",
    "get_cache_stats",
    "init_vector_store_with_seed_data",
    "load_catalog_seed_resources",
    "seed_catalog_resources",
]
