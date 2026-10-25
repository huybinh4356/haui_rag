"""Unit tests kiểm tra module retrieval (RRF và keyword search)."""

import pytest
from haui_rag.core.retrieval import reciprocal_rank_fusion
from haui_rag.db.queries import keyword_search


def test_rrf_scoring_order():
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
    assert fused[0]["id"] == 2
    assert fused[0]["rrf_score"] > fused[1]["rrf_score"]
    assert fused[0]["has_vector_match"] is True
    assert fused[0]["has_keyword_match"] is True


def test_rrf_uses_multiple_keyword_queries():
    vec_results = [{"id": 1, "content": "Chunk 1", "distance": 0.1}]
    keyword_lists = [
        [
            {"id": 2, "content": "Chunk 2"},
            {"id": 1, "content": "Chunk 1"},
        ],
        [
            {"id": 2, "content": "Chunk 2"},
            {"id": 3, "content": "Chunk 3"},
        ],
    ]

    fused = reciprocal_rank_fusion(
        vector_results=vec_results,
        keyword_results=[],
        keyword_result_lists=keyword_lists,
        k=60,
    )
    scores = {item["id"]: item["rrf_score"] for item in fused}
    by_id = {item["id"]: item for item in fused}

    assert len(fused) == 3
    assert scores[2] > scores[3]
    assert by_id[1]["has_vector_match"] is True
    assert by_id[3]["has_keyword_match"] is True
    assert by_id[3]["has_vector_match"] is False


def test_keyword_search_returns_data():
    results = keyword_search("quy chế", top_k=2)
    assert isinstance(results, list)
    if results:
        assert "content" in results[0]
        assert "rank_score" in results[0]
