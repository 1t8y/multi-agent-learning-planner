# 文件：tools/build_testset.py
# 功能：把「只写问题和期望资源」的查询表补全成完整评测集，避免 ground_truth 与知识库漂移
# 输入：data/knowledge_base/learning_resources.jsonl、data/evaluation/testset_queries.jsonl（可选旧测试集）
# 输出：data/evaluation/ragas_testset_v3.jsonl

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
KB_PATH = ROOT / "data" / "knowledge_base" / "learning_resources.jsonl"
QUERY_PATH = ROOT / "data" / "evaluation" / "testset_queries.jsonl"
LEGACY_PATH = ROOT / "data" / "evaluation" / "ragas_testset_v2.jsonl"
OUTPUT_PATH = ROOT / "data" / "evaluation" / "ragas_testset_v3.jsonl"

LEVEL_LABEL = {"beginner": "零基础", "intermediate": "进阶", "advanced": "高阶"}


def load_jsonl(path: Path) -> list[dict]:
    """输入 JSONL 路径，返回非空行解析出的字典列表"""
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def load_kb() -> dict[str, dict]:
    """读取已审核知识库，返回 id 到资源的映射"""
    kb = {}
    for item in load_jsonl(KB_PATH):
        if item.get("review_status") != "approved":
            continue
        kb[str(item["id"])] = item
    return kb


def build_context(resource: dict) -> str:
    """输入知识库记录，返回与旧测试集一致格式的参考上下文"""
    return (
        f"标题：{resource['title']}；描述：{resource['description']}；"
        f"类型：{resource['resource_type']}；领域：{resource['field']}；"
        f"难度：{resource['level']}；URL：{resource['url']}"
    )


def build_ground_truth(resources: list[dict]) -> str:
    """输入答案资源列表，返回由知识库字段直接拼出的参考答案"""
    parts = []
    for resource in resources:
        parts.append(
            f"推荐《{resource['title']}》。{resource['description']}"
            f"该资源类型为{resource['resource_type']}，"
            f"适合{LEVEL_LABEL.get(resource['level'], resource['level'])}阶段学习者。"
        )
    return "".join(parts)


def check(expected_ids: list[str], kb: dict[str, dict], query_id: str) -> list[str]:
    """输入期望资源 id，返回校验错误列表"""
    errors = []
    if not expected_ids:
        errors.append(f"{query_id}: expected_source_ids 为空")
    for rid in expected_ids:
        if rid not in kb:
            errors.append(f"{query_id}: 期望资源 {rid} 不在已审核知识库中")
    if len(set(expected_ids)) != len(expected_ids):
        errors.append(f"{query_id}: expected_source_ids 存在重复项")
    return errors


def expand(queries: list[dict], kb: dict[str, dict], errors: list[str]) -> list[dict]:
    """输入查询表和知识库，返回补全后的完整测试记录"""
    records = []
    for row in queries:
        expected = [str(x) for x in row["expected_source_ids"]]
        errors.extend(check(expected, kb, row["id"]))
        resources = [kb[rid] for rid in expected if rid in kb]
        if not resources:
            continue
        records.append({
            "id": row["id"],
            "question": row["question"],
            "ground_truth": build_ground_truth(resources),
            "reference_contexts": [build_context(r) for r in resources],
            "expected_source_ids": expected,
            "expected_sources": [r["title"] for r in resources],
            "topic": resources[0]["field"],
            "difficulty": LEVEL_LABEL.get(resources[0]["level"], resources[0]["level"]),
            "level": resources[0]["level"],
            "resource_type": resources[0]["resource_type"],
            "query_style": row.get("query_style", "direct"),
            "review_status": "approved",
        })
    return records


def main() -> int:
    """解析参数，合并新查询与旧测试集，写出并打印统计"""
    parser = argparse.ArgumentParser(description="构建完整评测测试集")
    parser.add_argument("--include-legacy", action="store_true", default=True,
                        help="合并旧版 ragas_testset_v2 的 30 条已审核题目（默认开启）")
    parser.add_argument("--no-legacy", dest="include_legacy", action="store_false")
    parser.add_argument("--output", type=Path, default=OUTPUT_PATH)
    args = parser.parse_args()

    kb = load_kb()
    errors: list[str] = []
    queries = load_jsonl(QUERY_PATH)

    if args.include_legacy and LEGACY_PATH.exists():
        for row in load_jsonl(LEGACY_PATH):
            queries.append({
                "id": row["id"],
                "question": row["question"],
                "expected_source_ids": row["expected_source_ids"],
                "query_style": "legacy",
            })

    seen = set()
    unique = []
    for row in queries:
        if row["id"] in seen:
            errors.append(f"重复题目 id: {row['id']}")
            continue
        seen.add(row["id"])
        unique.append(row)

    records = expand(unique, kb, errors)
    if errors:
        print("构建失败，存在以下问题：", file=sys.stderr)
        for err in errors:
            print(f"  - {err}", file=sys.stderr)
        return 1

    covered = {rid for rec in records for rid in rec["expected_source_ids"]}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(
        "\n".join(json.dumps(rec, ensure_ascii=False) for rec in records) + "\n",
        encoding="utf-8",
    )
    print(json.dumps({
        "output": str(args.output.relative_to(ROOT)),
        "questions": len(records),
        "kb_total": len(kb),
        "kb_covered": len(covered),
        "kb_uncovered": sorted(set(kb) - covered),
        "multi_answer_questions": sum(len(r["expected_source_ids"]) > 1 for r in records),
    }, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
