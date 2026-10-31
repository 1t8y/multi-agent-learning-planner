# 文件：rebuild_knowledge_base.py
# 功能：读取已审核的学习资源 JSONL，校验后重建 ChromaDB 知识库
# 输入：命令行 --check 或 --rebuild；输出：校验统计或重建结果

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


PROJECT_ROOT = Path(__file__).resolve().parent
CATALOG_PATH = PROJECT_ROOT / "data" / "knowledge_base" / "learning_resources.jsonl"
REQUIRED_FIELDS = {
    "id",
    "title",
    "description",
    "resource_type",
    "field",
    "level",
    "url",
    "tags",
    "source",
    "rating",
    "feedback_count",
    "created_at",
    "review_status",
}


def load_approved_resources(path: Path = CATALOG_PATH) -> list[dict[str, Any]]:
    """输入资源 JSONL 路径，返回校验通过的 approved 资源列表"""
    if not path.is_file():
        raise FileNotFoundError(f"资源目录不存在：{path}")

    resources: list[dict[str, Any]] = []
    seen_ids: set[str] = set()
    for line_number, raw_line in enumerate(
        path.read_text(encoding="utf-8").splitlines(),
        start=1,
    ):
        line = raw_line.strip()
        if not line:
            continue
        try:
            item = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"第 {line_number} 行 JSON 无效：{exc}") from exc

        missing = REQUIRED_FIELDS - set(item)
        if missing:
            raise ValueError(
                f"第 {line_number} 行缺少字段：{', '.join(sorted(missing))}"
            )
        resource_id = str(item["id"]).strip()
        if not resource_id:
            raise ValueError(f"第 {line_number} 行 id 为空")
        if resource_id in seen_ids:
            raise ValueError(f"第 {line_number} 行 id 重复：{resource_id}")
        seen_ids.add(resource_id)

        if item["review_status"] != "approved":
            continue
        if not isinstance(item["tags"], list):
            raise ValueError(f"第 {line_number} 行 tags 必须是数组")
        resources.append(item)

    if not resources:
        raise ValueError("没有可入库的 approved 资源")
    return resources


def rebuild_chroma(resources: list[dict[str, Any]]) -> dict[str, Any]:
    """输入 approved 资源列表，清空并重建 ChromaDB，返回统计信息"""
    from vector_store import VectorStoreManager, seed_catalog_resources

    store = VectorStoreManager()
    if not store._initialized:
        raise RuntimeError("ChromaDB 初始化失败，未执行重建")

    store.reset_database()
    # 批量写入：一次性编码，避免逐条触发 embedding
    seed_catalog_resources(store, resources)
    store._bm25_stale = True
    return store.get_stats()


def main() -> int:
    """解析命令行参数，执行知识库检查或重建"""
    parser = argparse.ArgumentParser(description="检查或重建学习资源知识库")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true", help="只校验资源目录")
    mode.add_argument("--rebuild", action="store_true", help="清空并重建 ChromaDB")
    args = parser.parse_args()

    resources = load_approved_resources()
    print(f"[knowledge_base] approved resources: {len(resources)}")
    if args.check:
        print("[knowledge_base] 校验通过，未修改 ChromaDB")
        return 0

    stats = rebuild_chroma(resources)
    print(json.dumps(stats, ensure_ascii=False, indent=2))

    total_count = int(stats.get("total_count", 0))
    if total_count != len(resources):
        print(
            f"[knowledge_base] 重建数量不一致："
            f"expected={len(resources)}, actual={total_count}"
        )
        return 1

    print("[knowledge_base] ChromaDB 重建完成")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
