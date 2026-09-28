import time
from haui_rag.core.rag_pipeline import rag_query
from haui_rag.utils.helpers import format_citation


def test_format_citation_syntax():
    """Kiểm tra cú pháp định dạng citation chuẩn."""
    meta1 = {"ma_van_ban": "41/QĐ-ĐHCN", "dieu": "5", "khoan": "1"}
    assert format_citation(meta1) == "[41/QĐ-ĐHCN] - Điều 5, Khoản 1"

    meta2 = {"ma_van_ban": "630/QĐ-ĐHCN", "dieu": "3"}
    assert format_citation(meta2) == "[630/QĐ-ĐHCN] - Điều 3"


def test_citation_present_in_query():
    """Kiểm tra câu hỏi quy chế bắt buộc có trích dẫn nguồn trong kết quả."""
    time.sleep(1.0)
    res = rag_query("Thời gian đào tạo thạc sĩ là bao lâu?", top_k=3)
    assert len(res["sources"]) > 0
    for s in res["sources"]:
        assert "citation" in s
        assert s["citation"].startswith("[")
        assert "]" in s["citation"]

