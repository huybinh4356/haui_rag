"""Unit tests cho các cải tiến Giai đoạn 2: Query Processor, Hybrid Search, RRF, Fallback."""

import pytest
from haui_rag.core.fallback import search_fallback
from haui_rag.core.query_processor import classify_query, extract_entities
from haui_rag.core.retrieval import reciprocal_rank_fusion
from haui_rag.db.queries import keyword_search


def test_classify_query():
    """Kiểm tra phân loại câu hỏi."""
    assert classify_query("Điều kiện tốt nghiệp thạc sĩ là gì?") == "factual"
    assert classify_query("Thủ tục xin bảo lưu kết quả học tập gồm các bước nào?") == "procedural"
    assert classify_query("So sánh chương trình đào tạo thạc sĩ chính quy và vừa làm vừa học?") == "comparative"
    assert classify_query("Giá vé máy bay đi Đà Nẵng hôm nay?") == "out_of_scope"


def test_extract_entities():
    """Kiểm tra trích xuất thực thể."""
    res1 = extract_entities("Theo Điều 5 Quyết định 41 trình độ thạc sĩ")
    assert res1["dieu"] == "5"
    assert res1["bac_dao_tao"] == "thạc sĩ"
    assert res1["ma_van_ban"] == "41"

    res2 = extract_entities("Khoản 2 Điều 10 quy chế tiến sĩ")
    assert res2["dieu"] == "10"
    assert res2["khoan"] == "2"
    assert res2["bac_dao_tao"] == "tiến sĩ"


def test_keyword_search_db():
    """Kiểm tra tìm kiếm keyword/full-text trong database."""
    results = keyword_search("thạc sĩ", top_k=3)
    assert isinstance(results, list)
    assert len(results) > 0
    assert "content" in results[0]
    assert "rank_score" in results[0]


def test_reciprocal_rank_fusion():
    """Kiểm tra thuật toán hợp nhất RRF."""
    vec_results = [
        {"id": 101, "content": "Chunk A", "distance": 0.2},
        {"id": 102, "content": "Chunk B", "distance": 0.3},
    ]
    kw_results = [
        {"id": 102, "content": "Chunk B", "rank_score": 0.9},
        {"id": 103, "content": "Chunk C", "rank_score": 0.8},
    ]

    fused = reciprocal_rank_fusion(vec_results, kw_results, k=60)
    assert len(fused) == 3
    # Chunk B (102) xuất hiện ở cả 2 danh sách nên điểm RRF phải cao nhất
    assert fused[0]["id"] == 102
    assert "rrf_score" in fused[0]


def test_search_fallback():
    """Kiểm tra module tìm kiếm ngoài website haui.edu.vn."""
    results = search_fallback("học phí", top_k=2)
    assert isinstance(results, list)
    for r in results:
        assert "link" in r
        assert "snippet" in r


def test_generate_from_fallback_empty():
    """Kiểm tra sinh câu trả lời khi fallback_results rỗng hoặc lỗi."""
    from haui_rag.core.fallback import generate_from_fallback
    ans = generate_from_fallback("câu hỏi test", [])
    assert "https://www.haui.edu.vn" in ans or "không tìm thấy" in ans


def test_rerank_by_llm_empty():
    """Kiểm tra rerank_by_llm trả về nguyên mẫu khi danh sách rỗng."""
    from haui_rag.core.retrieval import rerank_by_llm
    res = rerank_by_llm("query", [], top_k=3)
    assert res == []

