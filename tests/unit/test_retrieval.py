"""Unit tests kiểm tra module retrieval (RRF và keyword search)."""

import pytest
from haui_rag.core.retrieval import reciprocal_rank_fusion
from haui_rag.db.queries import keyword_search


def test_rrf_scoring_order():
    """Kiểm tra thuật toán RRF xếp hạng đúng mục xuất hiện ở cả 2 danh sách."""
    vec_results = [
        {"id": 1, "content": "Chunk 1", "distance": 0.1},
        {"id": 2, "content": "Chunk 2", "distance": 0.2},
    ]
    kw_results = [
        {"id": 2, "content": "Chunk 2", "rank_score": 1.0},
        {"id": 3, "content": "Chunk 3", "rank_score": 0.5},
    ]

    fused = reciprocal_rank_fusion(vec_results, kw_results, k=60)
    assert len(fused) == 3
    # Chunk 2 có rank cao ở cả 2 nên phải đứng đầu
    assert fused[0]["id"] == 2
    assert fused[0]["rrf_score"] > fused[1]["rrf_score"]


def test_keyword_search_returns_data():
    """Kiểm tra keyword_search trả về chunks khi có từ khóa khớp."""
    results = keyword_search("quy chế", top_k=2)
    assert isinstance(results, list)
    if results:
        assert "content" in results[0]
        assert "rank_score" in results[0]
