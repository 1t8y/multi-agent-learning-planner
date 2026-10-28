# 文件：tools/compare_ragas.py
# 功能：对比两轮 RAGAS 结果，并支持「同题对照」以隔离知识库规模变化的影响
# 输入：旧结果 CSV、新结果 CSV；输出：整体对比表 + 同题子集对比表

from __future__ import annotations

import argparse
import json
from pathlib import Path

import pandas as pd

METRICS = ("faithfulness", "answer_relevancy", "context_precision", "context_recall")
ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OLD = ROOT / "data" / "evaluation" / "ragas_results_k5.csv"
DEFAULT_NEW = ROOT / "data" / "evaluation" / "ragas_results_v3_k5.csv"


def load_frame(path: Path) -> pd.DataFrame:
    """读取 RAGAS 结果 CSV，缺失指标统一为 NaN"""
    frame = pd.read_csv(path, encoding="utf-8-sig")
    for metric in METRICS:
        if metric in frame.columns:
            frame[metric] = pd.to_numeric(frame[metric], errors="coerce")
    return frame


def render(old: pd.DataFrame, new: pd.DataFrame, label: str) -> str:
    """输入两帧数据，输出该口径下的 Markdown 对比表"""
    lines = [f"| {label} | 指标 | 旧结果 | 新结果 | Δ | 有效样本(旧/新) |",
             "|---|---|---:|---:|---:|---:|"]
    for metric in METRICS:
        if metric not in old.columns or metric not in new.columns:
            continue
        o, n = old[metric].mean(), new[metric].mean()
        lines.append(
            f"| {label} | {metric} | {o:.4f} | {n:.4f} | {n - o:+.4f} | "
            f"{old[metric].notna().sum()}/{new[metric].notna().sum()} |"
        )
    return "\n".join(lines)


def main() -> int:
    """解析参数并输出对比结果"""
    parser = argparse.ArgumentParser(description="对比两轮 RAGAS 结果")
    parser.add_argument("--old", type=Path, default=DEFAULT_OLD)
    parser.add_argument("--new", type=Path, default=DEFAULT_NEW)
    parser.add_argument("--json-out", type=Path, help="可选，把对比数值写成 JSON")
    args = parser.parse_args()

    old, new = load_frame(args.old), load_frame(args.new)
    print(f"旧结果：{args.old.name}（{len(old)} 题）")
    print(f"新结果：{args.new.name}（{len(new)} 题）")
    print()

    shared = sorted(set(old["user_input"]) & set(new["user_input"]))
    old_shared = old[old["user_input"].isin(shared)].reset_index(drop=True)
    new_shared = new[new["user_input"].isin(shared)].reset_index(drop=True)

    print("## 整体对比\n")
    print(render(old, new, "全量"))
    print()
    print(f"## 同题对照（{len(shared)} 道共同题目）\n")
    print(render(old_shared, new_shared, "同题"))
    print()
    print(f"共同题目数：{len(shared)}；旧独有 {len(set(old['user_input']) - set(shared))} 道；"
          f"新独有 {len(set(new['user_input']) - set(shared))} 道")

    missing = {m: int(new[m].isna().sum()) for m in METRICS if m in new.columns}
    if any(missing.values()):
        print(f"\n新结果缺失指标数：{missing}")

    if args.json_out:
        payload = {
            "old_file": args.old.name, "new_file": args.new.name,
            "old_total": len(old), "new_total": len(new), "shared_questions": len(shared),
            "overall": {m: {"old": round(float(old[m].mean()), 4),
                            "new": round(float(new[m].mean()), 4)} for m in METRICS if m in new.columns},
            "same_questions": {m: {"old": round(float(old_shared[m].mean()), 4),
                                   "new": round(float(new_shared[m].mean()), 4)}
                               for m in METRICS if m in new.columns},
            "missing_new": missing,
        }
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\n对比数据已写入：{args.json_out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
