"""Script tự động đánh giá chất lượng toàn diện của haui-rag-assistant trên bộ 30 câu hỏi benchmark."""

import json
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
) -> None:
    """
    Thực thi đánh giá benchmark trên tập test_questions.json và tính toán KPI.

    Args:
        max_questions: Số lượng câu hỏi tối đa cần đánh giá (mặc định toàn bộ 30 câu).
        output_report_file: Đường dẫn lưu báo cáo JSON kết quả.
        delay_between_calls: Thời gian chờ giữa các câu hỏi để tránh rate limit API (giây).
    """
    input_file = DATA_DIR / "test_data" / "test_questions.json"
    if not input_file.exists():
        logger.error("Không tìm thấy file dữ liệu kiểm thử tại: %s", input_file)
        return

    with open(input_file, "r", encoding="utf-8") as f:
        questions = json.load(f)[:max_questions]

    logger.info("Bắt đầu đánh giá benchmark trên %d câu hỏi quy chế HaUI", len(questions))

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

        logger.info("[%d/%d] [%s] %s", idx, len(questions), q_type.upper(), question)
        start_t = time.perf_counter()

        try:
            res = rag_query(question, top_k=5)
            elapsed = time.perf_counter() - start_t
            latencies.append(elapsed)

            answer = res.get("answer", "")
            sources = res.get("sources", [])
            fallback_used = res.get("fallback_used", False)
            ans_lower = answer.lower()

            # 1. Đánh giá câu hỏi trong phạm vi (factual & procedural)
            has_valid_citation = False
            if q_type in ["factual", "procedural"]:
                in_scope_count += 1
                is_rejected_answer = (
                    "không tìm thấy quy định này" in ans_lower
                    or "đã xảy ra lỗi" in ans_lower
                )
                if sources and not is_rejected_answer:
                    if expected_sources:
                        found_expected = any(
                            any(exp.lower() in str(s.get("citation", "")).lower() for exp in expected_sources)
                            or any(exp.lower() in str(s.get("ma_van_ban", "")).lower() for exp in expected_sources)
                            or any(exp.lower() in ans_lower for exp in expected_sources)
                            for s in sources
                        )
                    else:
                        found_expected = True

                    if found_expected:
                        correct_citations += 1
                        has_valid_citation = True

            # 2. Đánh giá câu hỏi ngoài phạm vi (out_of_scope)
            is_safe_rejection = False
            if q_type == "out_of_scope":
                out_of_scope_count += 1
                is_safe_rejection = bool(
                    "không tìm thấy" in ans_lower
                    or "không có thông tin" in ans_lower
                    or "xin lỗi" in ans_lower
                    or fallback_used
                )
                if is_safe_rejection:
                    correct_out_of_scope += 1

            logger.info(
                " -> Thời gian: %.2fs | Sources: %d | Valid Citation: %s | Fallback: %s",
                elapsed,
                len(sources),
                has_valid_citation,
                fallback_used,
            )

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
            logger.error(" -> Lỗi khi đánh giá câu hỏi %s: %s", q_id, e, exc_info=True)
            results.append({"id": q_id, "error": str(e)})

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

    if output_report_file is None:
        out_path = DATA_DIR / "test_data" / "evaluation_report.json"
    else:
        out_path = Path(output_report_file)
        if not out_path.is_absolute():
            out_path = BASE_DIR / out_path

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w", encoding="utf-8") as f:
        json.dump(report, f, ensure_ascii=False, indent=2)

    logger.info("BÁO CÁO TỔNG KẾT ĐÁNH GIÁ CHẤT LƯỢNG (KPI REPORT)")
    logger.info("- Độ chính xác trích dẫn (Citation Accuracy): %.1f%% (Mục tiêu: >= 95%%)", citation_accuracy)
    logger.info("- Tỷ lệ ảo giác (Hallucination Rate): %.1f%% (Mục tiêu: < 5%%)", hallucination_rate)
    logger.info("- Thời gian phản hồi trung bình: %.2fs", avg_latency)
    logger.info("- Thời gian phản hồi P95: %.2fs (Mục tiêu: < 5.0s)", p95_latency)
    logger.info("- Chi tiết báo cáo đã được lưu tại: %s", out_path)


if __name__ == "__main__":
    run_benchmark(max_questions=30)
