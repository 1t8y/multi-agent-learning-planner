# 文件：evaluate_ragas.py
# 功能：使用已审核资源推荐测试集评测检索，并在配置完整时运行 RAGAS
# 输入：命令行参数；输出：检索指标、RAGAS 分数或结果 CSV
from __future__ import annotations
import argparse, json
from pathlib import Path
ROOT = Path(__file__).resolve().parent
TESTSET = ROOT / "data" / "evaluation" / "ragas_testset_v2.jsonl"
EMBEDDING_MODEL = "BAAI/bge-small-zh-v1.5"
def load_tests() -> list[dict]:
    """输入固定测试集，返回全部 approved 题目"""
    rows = [json.loads(line) for line in TESTSET.read_text(encoding="utf-8").splitlines() if line.strip()]
    if any(row.get("review_status") != "approved" for row in rows):
        raise ValueError("测试集中存在未审核题目")
    return rows
def search_row(store, row: dict, top_k: int, mode: str) -> tuple[dict, dict]:
    """输入向量库和单题，返回 RAGAS 样本与排名详情"""
    items = store.search(row["question"], top_k=top_k, mode=mode)
    ids = [item.get("id", "") for item in items]
    expected = row["expected_source_ids"][0]
    rank = ids.index(expected) + 1 if expected in ids else None
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
    detail = {"id": row["id"], "expected": expected, "rank": rank, "top_ids": ids}
    return data, detail

def summarize(details: list[dict], k: int) -> dict:
    """输入逐题排名详情和 k，返回 Hit@k、MRR@k"""
    total = len(details)
    return {
        "hit_at_1": round(sum(item["rank"] == 1 for item in details) / total, 4),
        f"hit_at_{k}": round(sum(item["rank"] is not None for item in details) / total, 4),
        f"mrr_at_{k}": round(sum(1.0 / item["rank"] for item in details if item["rank"]) / total, 4),
    }
def run_ragas(dataset: list[dict]):
    """输入 RAGAS 数据，返回带 RAGAS 指标的 DataFrame"""
    try:
        from datasets import Dataset
        from langchain_huggingface import HuggingFaceEmbeddings
        from langchain_openai import ChatOpenAI
        from ragas import evaluate
        from ragas.embeddings import LangchainEmbeddingsWrapper
        from ragas.llms import LangchainLLMWrapper
        from ragas.metrics import AnswerRelevancy, ContextPrecision, ContextRecall, Faithfulness
        from config import config
    except ImportError as exc:
        raise RuntimeError("缺少 RAGAS 依赖，请先安装 requirements.txt 中的 ragas 相关包") from exc
    api_key = config.get_api_key()
    if not api_key:
        raise RuntimeError("未配置 DEEPSEEK_API_KEY，无法运行 RAGAS LLM 指标")
    model = config.get_model_config()["model"]
    base_url = config.get_api_base_url().removesuffix("/chat/completions")
    evaluator_llm = LangchainLLMWrapper(ChatOpenAI(model=model, api_key=api_key, base_url=base_url, temperature=0))
    evaluator_embeddings = LangchainEmbeddingsWrapper(HuggingFaceEmbeddings(model_name=EMBEDDING_MODEL))
    metrics = [Faithfulness(llm=evaluator_llm), ContextPrecision(llm=evaluator_llm), ContextRecall(llm=evaluator_llm)]
    metrics.append(AnswerRelevancy(llm=evaluator_llm, embeddings=evaluator_embeddings, strictness=1))
    result = evaluate(Dataset.from_list(dataset), metrics=metrics, llm=evaluator_llm, embeddings=evaluator_embeddings)
    return result.to_pandas()
def main() -> int:
    """解析参数，执行检索评测并按需运行 RAGAS"""
    parser = argparse.ArgumentParser(description="评测学习资源检索与 RAGAS")
    parser.add_argument("--top-k", type=int, default=3)
    parser.add_argument("--mode", choices=("dense", "sparse", "hybrid"), default="hybrid")
    parser.add_argument("--ragas", action="store_true", help="启用 RAGAS LLM 指标")
    parser.add_argument("--output", type=Path, help="RAGAS CSV 输出路径")
    args = parser.parse_args()
    from vector_store import init_vector_store_with_seed_data
    store = init_vector_store_with_seed_data()
    rows = load_tests()
    pairs = [search_row(store, row, args.top_k, args.mode) for row in rows]
    samples, details = zip(*pairs)
    print(json.dumps({"total": len(rows), **summarize(list(details), args.top_k)}, ensure_ascii=False, indent=2))
    if not args.ragas:
        return 0
    frame = run_ragas(list(samples))
    metric_cols = [c for c in ("faithfulness", "answer_relevancy", "context_precision", "context_recall") if c in frame.columns]
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
