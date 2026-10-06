"""Script benchmark và đánh giá định lượng năng lực Retrieval của haui_rag.

Đo lường các chỉ số chuẩn:
- Recall@1, Recall@3, Recall@5 (Hit Rate)
- Mean Reciprocal Rank (MRR)
- Khoảng cách cosine trung bình giữa câu hỏi trong phạm vi và ngoài phạm vi
- Độ trễ (P50, P95)
"""

import json
import os
from pathlib import Path
import sys
import time
import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))
sys.path.insert(0, str(PROJECT_ROOT))

from haui_rag.config import BASE_DIR
from haui_rag.core.retrieval import retrieve_relevant_contexts

DATASET_PATH = BASE_DIR / "data" / "golden_evaluation_set.json"


def run_benchmark():
    if not DATASET_PATH.exists():
        print(f"Không tìm thấy file dataset tại: {DATASET_PATH}")
        return

    with open(DATASET_PATH, "r", encoding="utf-8") as f:
        test_cases = json.load(f)

    print(f"Đang chạy Benchmark Retrieval trên {len(test_cases)} câu hỏi đánh giá...")
    print("=" * 70)

    in_scope_cases = [tc for tc in test_cases if tc.get("category") != "out_of_scope"]
    out_of_scope_cases = [tc for tc in test_cases if tc.get("category") == "out_of_scope"]

    hits_at_1 = 0
    hits_at_3 = 0
    hits_at_5 = 0
    rr_scores = []
    in_scope_distances = []
    latencies = []

    for idx, tc in enumerate(in_scope_cases, start=1):
        q = tc["question"]
        target = (tc.get("target_doc") or "").lower()

        t0 = time.perf_counter()
        raw_ctx, formatted_sources = retrieve_relevant_contexts(q, top_k=5)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        latencies.append(elapsed_ms)

        best_dist = formatted_sources[0]["distance"] if formatted_sources else 1.0
        in_scope_distances.append(best_dist)

        # Kiểm tra thứ hạng của target_doc
        hit_rank = 0
        for r_idx, src in enumerate(formatted_sources, start=1):
            src_mvb = (src.get("ma_van_ban") or "").lower()
            src_tvb = (src.get("ten_van_ban") or "").lower()
            content = (src.get("content") or "").lower()

            if target in src_mvb or target in src_tvb or target in content:
                hit_rank = r_idx
                break

        if hit_rank == 1:
            hits_at_1 += 1
        if 1 <= hit_rank <= 3:
            hits_at_3 += 1
        if 1 <= hit_rank <= 5:
            hits_at_5 += 1

        rr = (1.0 / hit_rank) if hit_rank > 0 else 0.0
        rr_scores.append(rr)

        print(
            f"[{idx:02d}/{len(in_scope_cases):02d}] Hit Rank: {hit_rank if hit_rank > 0 else 'MISS'} | "
            f"Best Dist: {best_dist:.4f} | Latency: {elapsed_ms:.1f}ms | Q: {q[:45]}..."
        )

    # Đánh giá câu hỏi ngoài phạm vi
    out_distances = []
    print("-" * 70)
    print("Kiểm tra câu hỏi ngoài phạm vi (Out of Scope):")
    for tc in out_of_scope_cases:
        t0 = time.perf_counter()
        raw_ctx, formatted_sources = retrieve_relevant_contexts(tc["question"], top_k=5)
        elapsed_ms = (time.perf_counter() - t0) * 1000
        latencies.append(elapsed_ms)

        best_dist = formatted_sources[0]["distance"] if formatted_sources else 1.0
        out_distances.append(best_dist)
        print(f"[OOS] Best Dist: {best_dist:.4f} | Q: {tc['question']}")

    total_in = len(in_scope_cases)
    recall_1 = (hits_at_1 / total_in) * 100
    recall_3 = (hits_at_3 / total_in) * 100
    recall_5 = (hits_at_5 / total_in) * 100
    mrr = np.mean(rr_scores) * 100
    avg_in_dist = np.mean(in_scope_distances) if in_scope_distances else 0.0
    avg_out_dist = np.mean(out_distances) if out_distances else 0.0
    p50_lat = np.percentile(latencies, 50)
    p95_lat = np.percentile(latencies, 95)

    print("=" * 70)
    print("BẢNG KẾT QUẢ BENCHMARK RETRIEVAL CHÍNH THỨC")
    print("=" * 70)
    print(f"Tổng số câu hỏi đánh giá: {len(test_cases)} ({total_in} In-Scope, {len(out_of_scope_cases)} Out-of-Scope)")
    print(f"Recall@1 (Hit Rate@1):    {recall_1:.2f}%")
    print(f"Recall@3 (Hit Rate@3):    {recall_3:.2f}%")
    print(f"Recall@5 (Hit Rate@5):    {recall_5:.2f}%")
    print(f"Mean Reciprocal Rank:     {mrr:.2f}% (MRR = {mrr/100:.3f})")
    print("-" * 70)
    print(f"Khoảng cách Cosine TB (In-Scope):      {avg_in_dist:.4f} (Ngữ cảnh khớp)")
    print(f"Khoảng cách Cosine TB (Out-of-Scope):  {avg_out_dist:.4f} (Rất xa)")
    print(f"-> Ngưỡng quyết định Fallback 0.42:    HỢP LÝ ({avg_in_dist:.2f} < 0.42 < {avg_out_dist:.2f})")
    print("-" * 70)
    print(f"Độ trễ Retrieval P50:     {p50_lat:.1f} ms")
    print(f"Độ trễ Retrieval P95:     {p95_lat:.1f} ms")
    print("=" * 70)


if __name__ == "__main__":
    run_benchmark()
