"""Unit tests kiểm tra module retrieval (RRF và keyword search)."""

import pytest
import haui_rag.core.retrieval as retrieval
from haui_rag.core.retrieval import (
    reciprocal_rank_fusion,
    select_contexts_for_coverage,
    rerank_by_local_model,
)
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
    assert scores[2] == round((0.3 / 2) / 61 + (0.3 / 2) / 61, 7)
    assert by_id[1]["has_vector_match"] is True
    assert by_id[3]["has_keyword_match"] is True
    assert by_id[3]["has_vector_match"] is False


def test_context_selection_preserves_keyword_coverage():
    candidates = [
        {"id": 1, "has_vector_match": True, "has_keyword_match": False},
        {"id": 2, "has_vector_match": True, "has_keyword_match": False},
        {"id": 3, "has_vector_match": True, "has_keyword_match": False},
        {"id": 4, "has_vector_match": False, "has_keyword_match": True},
    ]

    selected = select_contexts_for_coverage(candidates, top_k=3)

    assert [item["id"] for item in selected] == [1, 2, 4]
    assert any(item["has_keyword_match"] for item in selected)


def test_local_reranker_scores_candidates_without_cloud_api(monkeypatch):
    candidates = [
        {"id": 1, "content": "Đoạn A", "metadata": {}, "has_vector_match": True, "has_keyword_match": False},
        {"id": 2, "content": "Đoạn B", "metadata": {}, "has_vector_match": False, "has_keyword_match": True},
        {"id": 3, "content": "Đoạn C", "metadata": {}, "has_vector_match": True, "has_keyword_match": False},
    ]

    def fake_generate(prompt, **kwargs):
        assert "Câu hỏi:" in prompt
        assert kwargs["temperature"] == 0.0
        assert kwargs["num_predict"] == 180
        assert "chấm điểm độ liên quan" in kwargs["system_prompt"]
        return '{"scores":[{"index":1,"score":2},{"index":2,"score":9},{"index":3,"score":6}]}'

    monkeypatch.setattr(retrieval, "call_ollama_generate", fake_generate)
    ranked = rerank_by_local_model("Trách nhiệm sinh viên là gì?", candidates, top_k=2)

    assert [item["id"] for item in ranked] == [2, 1]
    assert ranked[0]["local_relevance_score"] == 9.0
    assert "rerank_score" in ranked[0]


def test_local_reranker_falls_back_when_model_output_is_invalid(monkeypatch):
    candidates = [
        {"id": 1, "content": "Đoạn A", "has_vector_match": True, "has_keyword_match": False},
        {"id": 2, "content": "Đoạn B", "has_vector_match": False, "has_keyword_match": True},
    ]

    monkeypatch.setattr(retrieval, "call_ollama_generate", lambda *args, **kwargs: "not json")
    ranked = rerank_by_local_model("Câu hỏi", candidates, top_k=2)

    assert [item["id"] for item in ranked] == [1, 2]



def test_article_expansion_includes_sibling_clauses_and_preserves_seed_score(monkeypatch):
    seed = {
        "id": 7,
        "content": "Điều 7. 1. Nội dung khoản một.",
        "metadata": {"ten_file": "630.pdf", "ma_van_ban": "630/QĐ-ĐHCN", "dieu": "7", "khoan": "1"},
        "distance": 0.12,
        "has_vector_match": True,
        "has_keyword_match": True,
    }
    related = [
        {
            "id": 9,
            "content": "Điều 7. 3. Nội dung khoản ba.",
            "metadata": {"ten_file": "630.pdf", "ma_van_ban": "630/QĐ-ĐHCN", "dieu": "7", "khoan": "3"},
            "distance": None,
            "context_expanded": True,
        },
        {
            "id": 7,
            "content": "Điều 7. 1. Nội dung khoản một.",
            "metadata": {"ten_file": "630.pdf", "ma_van_ban": "630/QĐ-ĐHCN", "dieu": "7", "khoan": "1"},
            "distance": None,
            "context_expanded": True,
        },
        {
            "id": 8,
            "content": "Điều 7. 2. Nội dung khoản hai.",
            "metadata": {"ten_file": "630.pdf", "ma_van_ban": "630/QĐ-ĐHCN", "dieu": "7", "khoan": "2"},
            "distance": None,
            "context_expanded": True,
        },
    ]
    calls = []
    monkeypatch.setattr(
        retrieval,
        "fetch_chunks_for_article",
        lambda chunk, limit=40: calls.append((chunk["id"], limit)) or related,
    )

    expanded = retrieval.expand_contexts_by_article(
        [seed],
        max_articles=1,
        max_context_chars=4000,
        max_article_chars=3000,
    )

    assert [chunk["id"] for chunk in expanded] == [7, 8, 9]
    assert expanded[0]["distance"] == 0.12
    assert expanded[0]["context_expanded"] is False
    assert expanded[1]["context_expanded"] is True
    assert calls == [(7, 40)]


def test_article_expansion_deduplicates_identical_content_within_same_article(monkeypatch):
    seed = {
        "id": 1,
        "content": "Nội dung giống nhau",
        "metadata": {"ten_file": "630.pdf", "dieu": "7", "khoan": "1"},
        "distance": 0.1,
    }
    related = [
        {"id": 1, "content": "Nội dung giống nhau", "metadata": {"ten_file": "630.pdf", "dieu": "7", "khoan": "1"}},
        {"id": 2, "content": "  Nội dung   giống nhau  ", "metadata": {"ten_file": "630.pdf", "dieu": "7", "khoan": "2"}},
    ]
    monkeypatch.setattr(retrieval, "fetch_chunks_for_article", lambda chunk, limit=40: related)

    expanded = retrieval.expand_contexts_by_article(
        [seed],
        max_articles=1,
        max_context_chars=4000,
        max_article_chars=3000,
    )

    assert len(expanded) == 1
    assert expanded[0]["id"] == 1


def test_article_identity_does_not_merge_same_article_number_across_documents():
    first = {"id": 1, "metadata": {"ten_file": "630.pdf", "dieu": "7"}}
    second = {"id": 2, "metadata": {"ten_file": "41.pdf", "dieu": "7"}}

    assert retrieval._article_identity(first) != retrieval._article_identity(second)



def test_article_expansion_keeps_ranked_retrieval_chunks_first(monkeypatch):
    first = {
        "id": 20,
        "content": "Khoản ba đã truy xuất tốt nhất.",
        "metadata": {"ten_file": "630.pdf", "dieu": "7", "khoan": "3"},
        "distance": 0.11,
        "rrf_score": 0.02,
        "has_vector_match": True,
        "has_keyword_match": True,
    }
    second = {
        "id": 21,
        "content": "Khoản hai đã được truy xuất.",
        "metadata": {"ten_file": "630.pdf", "dieu": "7", "khoan": "2"},
        "distance": 0.15,
        "rrf_score": 0.01,
        "has_vector_match": True,
        "has_keyword_match": False,
    }
    related = [
        {"id": 10, "content": "Khoản một bổ sung.", "metadata": {"ten_file": "630.pdf", "dieu": "7", "khoan": "1"}},
        {"id": 21, "content": second["content"], "metadata": second["metadata"]},
        {"id": 20, "content": first["content"], "metadata": first["metadata"]},
        {"id": 22, "content": "Khoản bốn bổ sung.", "metadata": {"ten_file": "630.pdf", "dieu": "7", "khoan": "4"}},
    ]
    monkeypatch.setattr(retrieval, "fetch_chunks_for_article", lambda chunk, limit=40: related)

    expanded = retrieval.expand_contexts_by_article(
        [first, second],
        max_articles=1,
        max_context_chars=4000,
        max_article_chars=3000,
    )

    assert [chunk["id"] for chunk in expanded[:2]] == [20, 21]
    assert expanded[0]["distance"] == 0.11
    assert expanded[1]["distance"] == 0.15
    assert all(chunk["context_expanded"] is False for chunk in expanded[:2])
    assert {chunk["id"] for chunk in expanded[2:]} == {10, 22}
    assert all(chunk.get("distance") is None for chunk in expanded[2:])


def test_article_expansion_keeps_seed_when_expansion_limit_is_small(monkeypatch):
    seed = {
        "id": 5,
        "content": "Đây là chunk được retrieval tìm thấy.",
        "metadata": {"ten_file": "630.pdf", "dieu": "7", "khoan": "1"},
        "distance": 0.08,
        "has_vector_match": True,
    }
    related = [
        seed,
        {"id": 6, "content": "Nội dung bổ sung dài.", "metadata": {"ten_file": "630.pdf", "dieu": "7", "khoan": "2"}},
    ]
    monkeypatch.setattr(retrieval, "fetch_chunks_for_article", lambda chunk, limit=40: related)

    expanded = retrieval.expand_contexts_by_article(
        [seed],
        max_articles=1,
        max_context_chars=4000,
        max_article_chars=10,
    )

    assert [chunk["id"] for chunk in expanded] == [5]
    assert expanded[0]["distance"] == 0.08
    assert expanded[0]["context_expansion_limited"] is True


def test_keyword_search_returns_data():
    results = keyword_search("quy chế", top_k=2)
    assert isinstance(results, list)
    if results:
        assert "content" in results[0]
        assert "rank_score" in results[0]


def test_retrieval_embeds_once_for_multiple_query_variants(monkeypatch):
    embedding_calls = []
    keyword_calls = []

    def fake_expand(query):
        return [query, "biến thể hai", "biến thể ba"]

    def fake_embedding(query, task_type):
        embedding_calls.append((query, task_type))
        return [0.0] * 3072

    def fake_keyword_search(query, top_k):
        keyword_calls.append(query)
        chunk_id = {"Câu hỏi gốc": 5, "biến thể hai": 3, "biến thể ba": 4}[query]
        return [{
            "id": chunk_id,
            "content": f"Đoạn {chunk_id}",
            "metadata": {"ma_van_ban": "QD-A", "dieu": str(chunk_id)},
            "rank_score": 1.0,
        }]

    def fake_vector_search(vector, top_k):
        assert vector == [0.0] * 3072
        return [
            {"id": 1, "content": "Đoạn 1", "metadata": {"ma_van_ban": "QD-A", "dieu": "1"}, "distance": 0.1},
            {"id": 2, "content": "Đoạn 2", "metadata": {"ma_van_ban": "QD-A", "dieu": "2"}, "distance": 0.2},
        ]

    monkeypatch.setattr(retrieval, "expand_query", fake_expand)
    monkeypatch.setattr(retrieval, "get_embedding", fake_embedding)
    monkeypatch.setattr(retrieval, "keyword_search", fake_keyword_search)
    monkeypatch.setattr(retrieval, "search_similar_chunks", fake_vector_search)
    monkeypatch.setattr(retrieval, "fetch_chunks_for_article", lambda chunk, limit=40: [])
    monkeypatch.setattr(retrieval, "USE_LLM_RERANK", False)
    monkeypatch.setattr(retrieval, "USE_LOCAL_RERANK", False)

    contexts, sources = retrieval.retrieve_relevant_contexts("Câu hỏi gốc", top_k=2)

    assert len(embedding_calls) == 1
    assert embedding_calls[0][0] == "Câu hỏi gốc"
    assert sorted(keyword_calls) == ["Câu hỏi gốc", "biến thể ba", "biến thể hai"]
    assert len(contexts) == 2
    assert len(sources) == 2
    assert any(source["has_keyword_match"] for source in sources)
    assert any(source["has_keyword_match"] and not source["has_vector_match"] for source in sources)


def test_single_context_keeps_highest_ranked_candidate():
    candidates = [
        {"id": 1, "has_vector_match": True, "has_keyword_match": False},
        {"id": 2, "has_vector_match": False, "has_keyword_match": True},
    ]

    selected = select_contexts_for_coverage(candidates, top_k=1)

    assert [item["id"] for item in selected] == [1]
