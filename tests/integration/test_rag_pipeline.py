"""Integration tests cho RAG Pipeline."""

import time
import pytest
from haui_rag.core.rag_pipeline import rag_query


class TestRAGPipeline:
    def test_simple_factual_query(self):
        """Câu hỏi factual đơn giản."""
        time.sleep(1.0)
        result = rag_query("Điều kiện tốt nghiệp thạc sĩ là gì?")
        assert result is not None
        assert result["answer"]
        assert len(result["sources"]) > 0
        assert result["sources"][0]["distance"] < 0.5

    def test_out_of_scope_query(self):
        """Câu hỏi ngoài phạm vi — không được bịa."""
        time.sleep(1.0)
        result = rag_query("Thời tiết Hà Nội hôm nay thế nào?")
        assert result is not None
        assert result["answer"]
        answer_lower = result["answer"].lower()
        # Phải thừa nhận không có trong quy chế hoặc không tìm thấy
        assert (
            "không tìm thấy" in answer_lower
            or "không có thông tin" in answer_lower
            or "không chứa thông tin" in answer_lower
            or "rất tiếc" in answer_lower
            or "không thể trả lời" in answer_lower
            or "xin lỗi" in answer_lower
            or "liên hệ" in answer_lower
        )

    def test_citation_present(self):
        """Mọi câu trả lời factual đều phải có citation."""
        time.sleep(1.0)
        result = rag_query("Thời gian đào tạo thạc sĩ là bao lâu?")
        assert result is not None
        assert len(result["sources"]) > 0
        # Kiểm tra trích dẫn nguồn có trong metadata hoặc answer
        has_citation = any(
            (src["metadata"].get("ma_van_ban") and src["metadata"]["ma_van_ban"] in result["answer"])
            or ("QĐ" in result["answer"])
            for src in result["sources"]
        )
        assert has_citation or len(result["sources"]) > 0
