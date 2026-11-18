# 文件：eval/tools/experiment_quality_negative.py
# 功能：验证名次共识质量信号在知识库外查询上的区分度（不能是恒高分）
# 输入：6 个知识库覆盖不到的查询
# 输出：控制台对比表
# 注意：这是 2026-11-12 门控重构前的历史实验，现行门控规则见 docs/ARCHITECTURE.md

from __future__ import annotations

import sys

# 后端根目录统一由 src.paths 提供；实验脚本按约定用 `python -m` 在 backend/ 下运行。
from src.paths import BACKEND_ROOT

ROOT = BACKEND_ROOT
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
TOOLS_DIR = str(ROOT / "eval" / "tools")
if TOOLS_DIR not in sys.path:
    sys.path.insert(0, TOOLS_DIR)

from experiment_quality_signal import RankConsensusQuality  # noqa: E402
from src.rag.rag_quality import RAGQualityChecker  # noqa: E402

OUT_OF_SCOPE = [
    "想学韩语入门，有推荐的视频课程吗",
    "量子场论里的路径积分怎么理解",
    "想学做戚风蛋糕，需要烤箱和配方",
    "萨克斯风零基础怎么练指法",
]

IN_SCOPE = [
    "想系统学 Python 基础语法，零基础",
    "机器学习入门，想先搞懂过拟合",
]


def main() -> int:
    """对库内与库外查询分别计算两套质量信号"""
    from src.rag.advanced_self_rag import AdvancedSelfRAGRecommender

    recommender = AdvancedSelfRAGRecommender()
    recommender.reranker.enabled = False
    # 历史实验只比较质量信号：关掉 RRF 前置门槛，也不让实验产生外部联网请求
    recommender.MIN_DENSE_SIMILARITY = None
    recommender.web_search = None

    print("\n(重排已关闭，只比较质量信号本身)\n")
    print("| 类型 | 查询 | 候选数 | 旧信号(similarity) | 新信号(名次共识) |")
    print("|---|---|---:|---:|---:|")

    for label, queries in (("库外", OUT_OF_SCOPE), ("库内", IN_SCOPE)):
        for query in queries:
            recommender.quality_checker = RAGQualityChecker(threshold=0.55)
            old = recommender.recommend(learning_objective=query, current_foundation="零基础")
            recommender.quality_checker = RankConsensusQuality(threshold=0.55)
            new = recommender.recommend(learning_objective=query, current_foundation="零基础")
            print(f"| {label} | {query[:20]} | {new.get('candidate_count', 0)} | "
                  f"{old.get('quality', {}).get('score', 0):.4f} | "
                  f"{new.get('quality', {}).get('score', 0):.4f} |")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
