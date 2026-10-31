# 文件：tools/experiment_quality_signal.py
# 功能：验证用「双路排名共识」替代 rerank_confidence 后，质量门控能否维持
# 输入：test_rag_pipeline 的 10 个场景
# 输出：控制台对比表（不修改生产代码）

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from rag_quality import RAGQualityChecker  # noqa: E402
from test_rag_pipeline import CASES  # noqa: E402


class RankConsensusQuality(RAGQualityChecker):
    """
    用检索阶段的名次共识打分，替代 Cross-Encoder 置信度。

    单条资源置信度 = 0.5/dense排名 + 0.5/BM25排名（缺失记 0），落在 0 到 1。

    注意：这只是实验实现，**没有进生产代码**。后续用
    tools/experiment_quality_negative.py 验证发现，它只反映「两路排序是否一致」，
    无法识别知识库外的查询（「想学萨克斯风」拿到 0.85），不能单独替代重排信号。
    """

    def _score(self, item: dict) -> float:
        """输入单条资源，返回双路排名共识分"""
        dense_rank = item.get("rank_dense")
        sparse_rank = item.get("rank_sparse")
        score = 0.0
        if dense_rank:
            score += 0.5 / float(dense_rank)
        if sparse_rank:
            score += 0.5 / float(sparse_rank)
        return max(0.0, min(score, 1.0))


def main() -> int:
    """在关闭重排的前提下，对比两套质量信号的判定结果"""
    from advanced_self_rag import AdvancedSelfRAGRecommender

    recommender = AdvancedSelfRAGRecommender()
    recommender.reranker.enabled = False

    print("\n| 场景 | 期望资源 | 检索首位 | 旧信号(max rerank) | 新信号(名次共识) |")
    print("|---|---|---|---:|---:|")

    old_scores, new_scores = [], []
    old_top1 = new_top1 = 0

    for expected_id, objective, foundation, preference in CASES:
        # 必须显式用原始类重建：上一轮已经把 quality_checker 换成了子类，
        # 写成 type(recommender.quality_checker) 会从第二轮起污染「旧信号」基线。
        recommender.quality_checker = RAGQualityChecker(threshold=0.55)
        baseline = recommender.recommend(
            learning_objective=objective, current_foundation=foundation,
            learning_preference=preference,
        )
        old_quality = baseline.get("quality", {})
        top_id = (baseline.get("resources") or [{}])[0].get("id")

        recommender.quality_checker = RankConsensusQuality(threshold=0.55)
        upgraded = recommender.recommend(
            learning_objective=objective, current_foundation=foundation,
            learning_preference=preference,
        )
        new_quality = upgraded.get("quality", {})
        new_top = (upgraded.get("resources") or [{}])[0].get("id")

        old_scores.append(old_quality.get("score", 0.0))
        new_scores.append(new_quality.get("score", 0.0))
        old_top1 += top_id == expected_id
        new_top1 += new_top == expected_id

        print(f"| {objective[:16]} | {expected_id} | {top_id} | "
              f"{old_quality.get('score', 0):.4f} {old_quality.get('grade')} | "
              f"{new_quality.get('score', 0):.4f} {new_quality.get('grade')} |")

    total = len(CASES)
    print(f"\n- 关闭重排 + 旧信号：通过 {sum(s >= 0.55 for s in old_scores)}/{total}，"
          f"均分 {sum(old_scores)/total:.4f}，首位正确 {old_top1}/{total}")
    print(f"- 关闭重排 + 名次共识：通过 {sum(s >= 0.55 for s in new_scores)}/{total}，"
          f"均分 {sum(new_scores)/total:.4f}，首位正确 {new_top1}/{total}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
