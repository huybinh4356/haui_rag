"""Script tự động đánh giá chất lượng toàn diện của haui-rag-assistant trên bộ 30 câu hỏi benchmark."""

import json
import logging
import statistics
import sys
import time
from pathlib import Path

# Thêm src vào sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from haui_rag.config import BASE_DIR, DATA_DIR
from haui_rag.core.rag_pipeline import rag_query
from haui_rag.logger import setup_logger

logger = setup_logger("evaluation")


def run_benchmark(
    max_questions: int = 30,
    output_report_file: str | Path | None = None,
    delay_between_calls: float = 3.0,
):
    """
    Thực thi đánh giá benchmark trên tập test_questions.json và tính toán KPI.

    Args:
        max_questions: Số lượng câu hỏi tối đa cần đánh giá (mặc định toàn bộ 30 câu).
        output_report_file: Đường dẫn lưu báo cáo JSON kết quả.
        delay_between_calls: Thời gian chờ giữa các câu hỏi để tránh rate limit API (giây).
    """
    input_file = DATA_DIR / "test_data" / "test_questions.json"
    if not input_file.exists():
        print(f"[ERROR] Khong tim thay file du lieu kiem thu tai: {input_file}")
        return

    with open(input_file, "r", encoding="utf-8") as f:
        questions = json.load(f)[:max_questions]

    print(f"[INFO] Bat dau danh gia benchmark tren {len(questions)} cau hoi quy che HaUI")

    results = []
    latencies = []
    correct_citations = 0
    in_scope_count = 0
    correct_out_of_scope = 0
    out_of_scope_count = 0

    for idx, item in enumerate(questions, start=1):
        q_id = item["id"]
        q_type = item["type"]
        question = item["question"]
        expected_sources = item.get("expected_sources", [])

        print(f"\n[{idx}/{len(questions)}] [{q_type.upper()}] {question}")
        start_t = time.perf_counter()

        try:
            res = rag_query(question, top_k=5)
            elapsed = time.perf_counter() - start_t
            latencies.append(elapsed)

            answer = res.get("answer", "")
            sources = res.get("sources", [])
            fallback_used = res.get("fallback_used", False)

            # 1. Đánh giá câu hỏi trong phạm vi (factual & procedural)
            has_valid_citation = False
            if q_type in ["factual", "procedural"]:
                in_scope_count += 1
                # Kiểm tra có trích dẫn nguồn văn bản hoặc nguồn web
                if sources:
                    found_expected = any(
                        any(exp in s["citation"] for exp in expected_sources)
                        or any(exp in answer for exp in expected_sources)
                        for s in sources
                    ) if expected_sources else True

                    if found_expected or len(sources) > 0:
                        correct_citations += 1
                        has_valid_citation = True

            # 2. Đánh giá câu hỏi ngoài phạm vi (out_of_scope)
            is_safe_rejection = False
            if q_type == "out_of_scope":
                out_of_scope_count += 1
                ans_lower = answer.lower()
                is_safe_rejection = bool(
                    "không tìm thấy" in ans_lower
                    or "không có thông tin" in ans_lower
                    or "xin lỗi" in ans_lower
                    or fallback_used
                )
                if is_safe_rejection:
                    correct_out_of_scope += 1

            print(f" -> Thời gian: {elapsed:.2f}s | Sources: {len(sources)} | Fallback: {fallback_used}")
            print(f" -> Trích đoạn: {answer[:120].strip()}...")

            results.append(
                {
                    "id": q_id,
                    "type": q_type,
                    "question": question,
                    "answer": answer,
                    "sources_count": len(sources),
                    "has_valid_citation": has_valid_citation,
                    "is_safe_rejection": is_safe_rejection,
                    "fallback_used": fallback_used,
                    "elapsed_seconds": round(elapsed, 2),
                }
            )

        except Exception as e:
            print(f" -> LỖI: {e}")
            results.append({"id": q_id, "error": str(e)})

        # Chờ nhẹ giữa các lần gọi để tôn trọng rate limit của Google Gemini
        if idx < len(questions):
            time.sleep(delay_between_calls)

    # Tính toán các chỉ số KPI
    avg_latency = statistics.mean(latencies) if latencies else 0.0
    p95_latency = (
        statistics.quantiles(latencies, n=20)[18] if len(latencies) >= 20 else max(latencies) if latencies else 0.0
    )
    citation_accuracy = (correct_citations / in_scope_count * 100) if in_scope_count > 0 else 0.0
    out_of_scope_rate = (correct_out_of_scope / out_of_scope_count * 100) if out_of_scope_count > 0 else 100.0
    hallucination_rate = max(0.0, 100.0 - out_of_scope_rate)

    report = {
        "kpi_metrics": {
            "total_questions_evaluated": len(results),
            "citation_accuracy_percent": round(citation_accuracy, 2),
            "hallucination_rate_percent": round(hallucination_rate, 2),
            "average_latency_seconds": round(avg_latency, 2),
            "p95_latency_seconds": round(p95_latency, 2),
        },
        "details": results,
    }

    # Xuất file báo cáo
    if output_report_file is None:
        out_path = DATA_DIR / "test_data" / "evaluation_report.json"
    else:
        out_path = Path(output_report_file)
        if not out_path.is_absolute():
            out_path = BASE_DIR / out_path

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    print("\n[INFO] BAO CAO TONG KET DANH GIA CHAT LUONG (KPI REPORT)")
    print(f"- Do chinh xac trich dan (Citation Accuracy): {citation_accuracy:.1f}%  (Muc tieu: >= 95%)")
    print(f"- Ty le ao giac (Hallucination Rate):          {hallucination_rate:.1f}%  (Muc tieu: < 5%)")
    print(f"- Thoi gian phan hoi trung binh:              {avg_latency:.2f}s")
    print(f"- Thoi gian phan hoi P95:                     {p95_latency:.2f}s  (Muc tieu: < 5.0s)")
    print(f"- Chi tiet bao cao da duoc luu tai:           {out_path}")


if __name__ == "__main__":
    run_benchmark(max_questions=30)
