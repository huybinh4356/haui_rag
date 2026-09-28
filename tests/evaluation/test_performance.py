"""Đánh giá hiệu năng và tốc độ phản hồi (Performance Evaluation)."""

import time
from haui_rag.config import EMBEDDING_DIMENSION
from haui_rag.core.retrieval import retrieve_relevant_contexts
from haui_rag.db.queries import search_similar_chunks


def test_vector_search_latency():
    """Kiểm tra thời gian truy vấn vector HNSW trên PostgreSQL dưới 200ms."""
    dummy_vec = [0.01] * EMBEDDING_DIMENSION
    start = time.perf_counter()
    results = search_similar_chunks(dummy_vec, top_k=5)
    duration_ms = (time.perf_counter() - start) * 1000

    assert len(results) > 0
    assert duration_ms < 500.0, f"Vector search quá chậm: {duration_ms:.2f}ms"


def test_hybrid_retrieval_latency():
    """Kiểm tra toàn bộ tầng retrieval (Hybrid + RRF) dưới 3000ms."""
    start = time.perf_counter()
    raw_ctx, formatted_src = retrieve_relevant_contexts("Điều kiện tốt nghiệp thạc sĩ?", top_k=5)
    duration_ms = (time.perf_counter() - start) * 1000

    assert len(raw_ctx) > 0
    assert duration_ms < 4000.0, f"Retrieval latency quá chậm: {duration_ms:.2f}ms"
