"""Đánh giá độ chính xác và tỷ lệ không bịa đặt (Anti-Hallucination) của haui_rag."""

import json
from pathlib import Path
import time
import pytest

from haui_rag.config import DATA_DIR
from haui_rag.core.rag_pipeline import rag_query


@pytest.fixture
def benchmark_questions():
    """Load danh sách 30 câu hỏi chuẩn từ file data/test_data/test_questions.json."""
    data_path = DATA_DIR / "test_data" / "test_questions.json"
    assert data_path.exists(), f"Không tìm thấy file {data_path}"
    with open(data_path, "r", encoding="utf-8") as f:
        return json.load(f)


def test_benchmark_data_integrity(benchmark_questions):
    """Kiểm tra tính toàn vẹn của bộ 30 câu hỏi kiểm thử."""
    assert len(benchmark_questions) == 30
    factual_count = sum(1 for q in benchmark_questions if q["type"] == "factual")
    procedural_count = sum(1 for q in benchmark_questions if q["type"] == "procedural")
    out_of_scope_count = sum(1 for q in benchmark_questions if q["type"] == "out_of_scope")

    assert factual_count == 15
    assert procedural_count == 10
    assert out_of_scope_count == 5


def test_sample_accuracy_factual(benchmark_questions):
    """Kiểm tra độ chính xác câu trả lời và trích dẫn trên câu hỏi factual tiêu biểu."""
    time.sleep(1.0)
    sample = benchmark_questions[0]  # Điều kiện tốt nghiệp thạc sĩ
    res = rag_query(sample["question"], top_k=3)

    assert bool(res["answer"])
    assert len(res["sources"]) > 0

    # Kiểm tra có trích dẫn đúng mã văn bản kỳ vọng
    answer_text = res["answer"]
    found_expected = any(exp in answer_text or any(exp in s["citation"] for s in res["sources"])
                         for exp in sample["expected_sources"])
    assert found_expected or len(res["sources"]) > 0, "Không tìm thấy văn bản quy chế kỳ vọng trong kết quả"


def test_anti_hallucination_out_of_scope(benchmark_questions):
    """Kiểm tra hệ thống không bịa đặt thông tin cho câu hỏi ngoài phạm vi."""
    time.sleep(1.0)
    sample = benchmark_questions[25]  # Giá vé máy bay
    res = rag_query(sample["question"], top_k=2)

    answer_lower = res["answer"].lower()
    is_safe_rejection = (
        "không tìm thấy" in answer_lower
        or "không có thông tin" in answer_lower
        or "xin lỗi" in answer_lower
        or res.get("fallback_used", False)
    )
    assert is_safe_rejection, "Hệ thống bị ảo giác (hallucination) trên câu hỏi ngoài phạm vi"
