# 文件：tests/test_data_integrity.py
# 功能：校验知识库与评测测试集的字段完备性、枚举合法性和引用一致性
# 输入：data/knowledge_base、data/evaluation；输出：断言结果

from __future__ import annotations

import re

REQUIRED_FIELDS = {
    "id", "title", "description", "resource_type", "field", "level",
    "url", "tags", "source", "rating", "feedback_count", "created_at", "review_status",
}
FIELDS = {"AI", "编程", "数学"}
LEVELS = {"beginner", "intermediate", "advanced"}
RESOURCE_TYPES = {"视频教程", "文字教程", "文档资料", "实战项目"}


def test_kb_has_enough_resources(kb_rows):
    """知识库规模要足以让 top-k 检索有区分度，过小会让 Hit@5 失真"""
    approved = [r for r in kb_rows if r["review_status"] == "approved"]
    assert len(approved) >= 50, f"已审核资源仅 {len(approved)} 条"


def test_kb_records_have_all_fields(kb_rows):
    """每条资源必须字段齐全"""
    for row in kb_rows:
        missing = REQUIRED_FIELDS - set(row)
        assert not missing, f"{row.get('id')} 缺字段 {missing}"


def test_kb_ids_are_unique(kb_rows):
    """资源 id 必须唯一，否则写入 Chroma 会互相覆盖"""
    ids = [row["id"] for row in kb_rows]
    assert len(ids) == len(set(ids))


def test_kb_enums_are_valid(kb_rows):
    """领域、难度、资源类型必须落在枚举内，否则过滤条件永远命中不到"""
    for row in kb_rows:
        assert row["field"] in FIELDS, f"{row['id']} 领域非法: {row['field']}"
        assert row["level"] in LEVELS, f"{row['id']} 难度非法: {row['level']}"
        assert row["resource_type"] in RESOURCE_TYPES, f"{row['id']} 类型非法: {row['resource_type']}"


def test_kb_urls_are_http_and_unique(kb_rows):
    """URL 必须可访问形式且不重复，重复会在检索结果里去重后偷偷变少"""
    urls = [row["url"] for row in kb_rows]
    assert all(re.match(r"^https?://", url) for url in urls)
    assert len(urls) == len(set(urls))


def test_kb_descriptions_are_retrievable(kb_rows):
    """描述过短会导致 BM25 与向量都缺少检索信号"""
    for row in kb_rows:
        assert len(row["description"]) >= 20, f"{row['id']} 描述过短"
        assert row["title"] not in row["description"], f"{row['id']} 描述重复了标题"


def test_kb_covers_all_levels_and_types(kb_rows):
    """三个难度和四种资源类型都要有样本，否则过滤后无资源可选"""
    assert {row["level"] for row in kb_rows} == LEVELS
    assert {row["resource_type"] for row in kb_rows} == RESOURCE_TYPES


def test_testsets_reference_existing_resources(testset_rows, kb_rows):
    """评测题目的期望资源必须在知识库中存在，否则题目永远无法命中"""
    known = {row["id"] for row in kb_rows}
    for row in testset_rows:
        for rid in row["expected_source_ids"]:
            assert rid in known, f"{row['id']} 引用了不存在的资源 {rid}"


def test_testsets_cover_most_of_kb(testset_rows, kb_rows):
    """测试集应覆盖大部分资源，否则指标只反映局部"""
    covered = {rid for row in testset_rows for rid in row["expected_source_ids"]}
    known = {row["id"] for row in kb_rows if row["review_status"] == "approved"}
    assert len(covered) / len(known) >= 0.9


def test_testsets_are_approved_and_complete(testset_rows):
    """每道题都要有参考答案、参考上下文和期望资源"""
    for row in testset_rows:
        assert row["review_status"] == "approved"
        assert row["question"].strip()
        assert row["ground_truth"].strip()
        assert row["reference_contexts"]
        assert row["expected_source_ids"]


def test_testset_ids_are_unique(testset_rows):
    """题目 id 唯一，便于评测结果逐条回溯"""
    ids = [row["id"] for row in testset_rows]
    assert len(ids) == len(set(ids))


def test_testset_ground_truth_quotes_expected_title(testset_rows, kb_rows):
    """参考答案应指向期望资源本身，避免答案与检索目标错位"""
    by_id = {row["id"]: row for row in kb_rows}
    for row in testset_rows:
        first = row["expected_source_ids"][0]
        assert by_id[first]["title"] in row["ground_truth"], f"{row['id']} 答案与期望资源不一致"
