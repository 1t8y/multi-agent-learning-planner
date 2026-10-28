# 文件：evaluate_ragas.py
# 功能：使用已审核资源推荐测试集评测检索，并在配置完整时运行 RAGAS
# 输入：命令行参数；输出：检索指标、RAGAS 分数或结果 CSV
from __future__ import annotations
import argparse, json
from pathlib import Path
from retrieval_metrics import precision_at_k, rank_of_first_hit
from retrieval_metrics import summarize as retrieval_summarize
ROOT = Path(__file__).resolve().parent
TESTSET_V3 = ROOT / "data" / "evaluation" / "ragas_testset_v3.jsonl"
TESTSET_V2 = ROOT / "data" / "evaluation" / "ragas_testset_v2.jsonl"
EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"
def load_tests(path: Path | None = None) -> list[dict]:
    """输入测试集路径（默认优先 v3），返回全部 approved 题目"""
    target = path or (TESTSET_V3 if TESTSET_V3.exists() else TESTSET_V2)
    rows = [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines() if line.strip()]
    if any(row.get("review_status") != "approved" for row in rows):
        raise ValueError("测试集中存在未审核题目")
    return rows
def search_row(store, row: dict, top_k: int, mode: str) -> tuple[dict, dict]:
    """输入向量库和单题，返回 RAGAS 样本与排名详情"""
    items = store.search(row["question"], top_k=top_k, mode=mode)
    ids = [item.get("id", "") for item in items]
    expected = row["expected_source_ids"]
    rank = rank_of_first_hit(ids, expected)
    contexts = [
        f"标题：{item.get('title', '')}；描述：{item.get('description', '')}；"
        f"类型：{item.get('resource_type', '')}；领域：{item.get('field', '')}；"
        f"难度：{item.get('level', '')}；URL：{item.get('url', '')}"
        for item in items
    ]
    answer = "建议优先选择以下学习资源：" + "；".join(
        f"《{item.get('title', '')}》{item.get('description', '')}，"
        f"类型：{item.get('resource_type', '')}，难度：{item.get('level', '')}，"
        f"链接：{item.get('url', '')}" for item in items
    )
    data = {
        "user_input": row["question"], "retrieved_contexts": contexts, "response": answer,
        "reference": row["ground_truth"], "reference_contexts": row["reference_contexts"],
    }
    detail = {"id": row["id"], "expected": expected[0] if expected else "",
              "rank": rank, "top_ids": ids,
              "precision": precision_at_k(ids, expected, min(3, top_k))}
    return data, detail

def summarize(details: list[dict], k: int) -> dict:
    """输入逐题排名详情和 k，返回 Hit@1、Hit@k、MRR@k（复用统一指标实现）"""
    return retrieval_summarize(details, k)
def run_ragas(dataset: list[dict], workers: int = 8):
    """输入 RAGAS 数据，返回带 RAGAS 指标的 DataFrame"""
    try:
        from datasets import Dataset
        from langchain_huggingface import HuggingFaceEmbeddings
        from langchain_openai import ChatOpenAI
        from ragas import evaluate
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from ragas.llms import LangchainLLMWrapper
        from ragas.metrics import AnswerRelevancy, ContextPrecision, ContextRecall, Faithfulness
        from ragas.run_config import RunConfig
        from config import config
    except ImportError as exc:
        raise RuntimeError("缺少 RAGAS 依赖，请先安装 requirements-ragas.txt") from exc
    api_key = config.get_api_key()
    if not api_key:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY，无法运行 RAGAS LLM 指标")
    model = config.get_model_config()["model"]
    base_url = config.get_api_base_url().removesuffix("/chat/completions")
    evaluator_llm = LangchainLLMWrapper(ChatOpenAI(model=model, api_key=api_key, base_url=base_url, temperature=0))
    evaluator_embeddings = LangchainEmbeddingsWrapper(HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL))
    metrics = [Faithfulness(llm=evaluator_llm), ContextPrecision(llm=evaluator_llm), ContextRecall(llm=evaluator_llm)]
    metrics.append(AnswerRelevancy(llm=evaluator_llm, embeddings=evaluator_embeddings, strictness=1))
    run_config = RunConfig(max_workers=workers, timeout=600, max_retries=3)
    result = evaluate(Dataset.from_list(dataset), metrics=metrics, llm=evaluator_llm,
                      embeddings=evaluator_embeddings, run_config=run_config)
    return result.to_pandas()
METRIC_COLS = ("faithfulness", "answer_relevancy", "context_precision", "context_recall")


def patch_missing(output: Path, samples: list[dict], workers: int) -> None:
    """输入已有结果 CSV 与全量样本，只补跑存在 NaN 的题目并把有效值回填"""
    import pandas as pd

    frame = pd.read_csv(output, encoding="utf-8-sig")
    cols = [c for c in METRIC_COLS if c in frame.columns]
    missing = frame[cols].isna().any(axis=1)
    todo = frame[missing].copy()
    if todo.empty:
        print("结果文件已完整，无需补跑")
        return
    print(f"待补跑 {len(todo)}/{len(frame)} 题（并发 {workers}）")

    by_question = {sample["user_input"]: sample for sample in samples}
    dataset = [by_question[q] for q in todo["user_input"] if q in by_question]
    if len(dataset) != len(todo):
        raise RuntimeError(f"有 {len(todo) - len(dataset)} 道题在测试集中找不到对应样本")

    refilled = run_ragas(dataset, workers=workers)
    lookup = {row["user_input"]: row for _, row in refilled.iterrows()}
    filled = 0
    for idx, question in todo["user_input"].items():
        fresh = lookup.get(question)
        if fresh is None:
            continue
        for col in cols:
            value = fresh.get(col)
            if pd.notna(value) and pd.isna(frame.at[idx, col]):
                frame.at[idx, col] = value
                filled += 1
    frame.to_csv(output, index=False, encoding="utf-8-sig")
    remain = int(frame[cols].isna().any(axis=1).sum())
    print(f"回填 {filled} 个指标值，仍有 {remain} 题存在缺失")
    print(json.dumps({c: round(float(frame[c].mean()), 4) for c in cols}, ensure_ascii=False, indent=2))


def main() -> int:
    """解析参数，执行检索评测并按需运行 RAGAS"""
    parser = argparse.ArgumentParser(description="评测学习资源检索与 RAGAS")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--mode", choices=("dense", "sparse", "hybrid"), default="hybrid")
    parser.add_argument("--ragas", action="store_true", help="启用 RAGAS LLM 指标")
    parser.add_argument("--output", type=Path, help="RAGAS CSV 输出路径")
    parser.add_argument("--limit", type=int, default=0,
                        help="只跑前 N 题，用于冒烟验证（0 表示全量）")
    parser.add_argument("--workers", type=int, default=8,
                        help="RAGAS 并发度，过高容易触发接口限流")
    parser.add_argument("--testset", type=Path, help="指定测试集，默认优先 v3")
    parser.add_argument("--resume", action="store_true",
                        help="只补跑 --output 文件中存在缺失指标的题目，并回填原文件")
    args = parser.parse_args()
    from vector_store import init_vector_store_with_seed_data
    store = init_vector_store_with_seed_data()
    rows = load_tests(args.testset)
    if args.limit > 0:
        rows = rows[:args.limit]
    pairs = [search_row(store, row, args.top_k, args.mode) for row in rows]
    samples, details = zip(*pairs)
    print(json.dumps({"total": len(rows), **summarize(list(details), args.top_k)}, ensure_ascii=False, indent=2))
    if args.resume:
        if not args.output or not args.output.exists():
            raise SystemExit("--resume 需要指定已存在的 --output 文件")
        patch_missing(args.output, list(samples), args.workers)
        return 0
    if not args.ragas:
        return 0
    frame = run_ragas(list(samples), workers=args.workers)
    metric_cols = [c for c in METRIC_COLS if c in frame.columns]
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        frame.to_csv(args.output, index=False, encoding="utf-8-sig")
        print(f"结果已写入：{args.output}")
        print(json.dumps({c: round(float(frame[c].mean()), 4) for c in metric_cols}, ensure_ascii=False, indent=2))
    else:
        print(frame.to_string(index=False))
    return 0
if __name__ == "__main__":
    raise SystemExit(main())
