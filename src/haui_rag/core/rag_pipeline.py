"""Module điều phối RAG Pipeline V2: Kết hợp Query Understanding, Hybrid Search, Reranking, Adaptive Prompting và Search Fallback."""

from collections import OrderedDict
import logging
import time
from typing import Any, Iterator

from haui_rag.config import DEFAULT_TOP_K, ENABLE_QUERY_CACHE, QUERY_CACHE_SIZE
from haui_rag.core.fallback import build_fallback_prompt, generate_from_fallback, search_fallback
from haui_rag.core.generation import build_prompt, generate_answer, generate_answer_stream
from haui_rag.core.query_processor import classify_query
from haui_rag.core.retrieval import retrieve_relevant_contexts
from haui_rag.db.conversation_queries import (
    get_cached_query_response,
    normalize_cache_query,
    save_cached_query_response,
)
from haui_rag.utils.helpers import is_safe_query, verify_citations_against_sources

logger = logging.getLogger("haui_rag")

_query_cache: OrderedDict[tuple[str, int], dict[str, Any]] = OrderedDict()


def clear_in_memory_cache() -> None:
    """Xóa bộ nhớ đệm câu hỏi trong RAM (L1 Cache)."""
    _query_cache.clear()


def rag_query(
    query: str,
    top_k: int = DEFAULT_TOP_K,
) -> dict[str, Any]:
    """
    Thực thi truy vấn RAG hoàn chỉnh và trả về câu trả lời kèm danh sách trích dẫn nguồn.

    Args:
        query: Câu hỏi của người dùng.
        top_k: Số lượng chunks hạt giống cần truy xuất.

    Returns:
        Dict chứa answer, sources, response_time_ms, query_type, fallback_used, citation_audit.

    Raises:
        ValueError: Khi câu hỏi rỗng hoặc vượt quá 1000 ký tự.
    """
    start_time = time.perf_counter()

    if not query or not query.strip():
        raise ValueError("Câu hỏi không được để trống")

    if len(query) > 1000:
        raise ValueError("Câu hỏi không được vượt quá 1000 ký tự")

    clean_q = query.strip()
    norm_q = normalize_cache_query(clean_q) or clean_q.lower()
    cache_key = (norm_q, top_k)

    # L1 Cache: Bộ nhớ đệm LRU trong RAM
    if ENABLE_QUERY_CACHE and cache_key in _query_cache:
        cached_result = _query_cache[cache_key].copy()
        _query_cache.move_to_end(cache_key)
        cached_result["response_time_ms"] = int((time.perf_counter() - start_time) * 1000)
        cached_result["cache_hit"] = True
        cached_result["cache_layer"] = "memory"
        logger.info("Tra cứu từ L1 RAM Cache thành công cho: '%s' (%d ms)", clean_q, cached_result["response_time_ms"])
        return cached_result

    # L2 Cache: Bảng query_cache bền vững trong PostgreSQL (không cần gọi lại Gemini Embedding + LLM)
    if ENABLE_QUERY_CACHE:
        db_cached = get_cached_query_response(clean_q, top_k=top_k)
        if db_cached and db_cached.get("answer"):
            db_cached["response_time_ms"] = int((time.perf_counter() - start_time) * 1000)
            if len(_query_cache) >= QUERY_CACHE_SIZE:
                _query_cache.popitem(last=False)
            _query_cache[cache_key] = db_cached.copy()
            logger.info(
                "Tra cứu từ L2 PostgreSQL Cache thành công cho: '%s' (%d ms, hit_count=%d)",
                clean_q,
                db_cached["response_time_ms"],
                db_cached.get("hit_count", 1),
            )
            return db_cached

    if not is_safe_query(query):
        logger.warning("Truy vấn bị từ chối do không an toàn: %s", query)
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        return {
            "answer": "Xin lỗi, câu hỏi của bạn chứa nội dung không phù hợp với quy định của hệ thống.",
            "sources": [],
            "response_time_ms": elapsed_ms,
            "fallback_used": False,
        }

    q_type = classify_query(query)
    logger.info("Nhận truy vấn: '%s' | Phân loại: %s", query, q_type)

    formatted_sources: list[dict[str, Any]] = []
    fallback_used = False

    try:
        raw_contexts, formatted_sources = retrieve_relevant_contexts(query, top_k=top_k)

        vector_distances = [
            source["distance"]
            for source in formatted_sources
            if source.get("has_vector_match", True)
            and isinstance(source.get("distance"), (int, float))
        ]
        best_distance = min(vector_distances, default=1.0)
        has_keyword_match = any(source.get("has_keyword_match", False) for source in formatted_sources)
        local_scores = [
            float(source["local_relevance_score"])
            for source in formatted_sources
            if isinstance(source.get("local_relevance_score"), (int, float))
        ]
        if local_scores:
            has_good_match = bool(
                formatted_sources
                and (best_distance < 0.42 or max(local_scores) >= 5.5)
            )
        else:
            has_good_match = bool(
                formatted_sources and (best_distance < 0.42 or has_keyword_match)
            )

        if not has_good_match and q_type != "out_of_scope":
            logger.info("Độ tương đồng DB thấp (best_dist=%.4f), thử kích hoạt Search Fallback haui.edu.vn...", best_distance)
            fallback_items = search_fallback(query, top_k=3)
            if fallback_items:
                fallback_answer = generate_from_fallback(query, fallback_items)
                elapsed_ms = int((time.perf_counter() - start_time) * 1000)
                logger.info("Đã trả lời thành công qua Search Fallback trong %d ms", elapsed_ms)
                return {
                    "answer": fallback_answer,
                    "sources": [
                        {
                            "chunk_id": None,
                            "citation": f"[Web HaUI] {item['title']}",
                            "distance": None,
                            "source_type": "web",
                            "content": f"{item['snippet']}\nLink: {item['link']}",
                        }
                        for item in fallback_items
                    ],
                    "response_time_ms": elapsed_ms,
                    "query_type": q_type,
                    "fallback_used": True,
                    "citation_audit": {"is_grounded": True, "verified_citations": [], "unverified_citations": [], "verification_score": 1.0},
                }

        prompt = build_prompt(query, raw_contexts)
        logger.info("Đang gọi LLM với Adaptive Prompt V2...")
        answer = generate_answer(prompt)

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        logger.info("Hoàn thành truy vấn RAG trong %d ms", elapsed_ms)

        citation_audit = verify_citations_against_sources(answer, formatted_sources)
        if not citation_audit.get("is_grounded", True):
            logger.warning(
                "Phát hiện trích dẫn chưa được kiểm chứng trong câu trả lời: %s",
                citation_audit.get("unverified_citations"),
            )

        final_response = {
            "answer": answer,
            "sources": formatted_sources,
            "response_time_ms": elapsed_ms,
            "query_type": q_type,
            "fallback_used": fallback_used,
            "citation_audit": citation_audit,
            "cache_hit": False,
        }

        if ENABLE_QUERY_CACHE and answer and "không thể xử lý" not in answer and "đã xảy ra lỗi" not in answer:
            if len(_query_cache) >= QUERY_CACHE_SIZE:
                _query_cache.popitem(last=False)
            _query_cache[cache_key] = final_response.copy()
            save_cached_query_response(clean_q, top_k=top_k, response_data=final_response)

        return final_response

    except Exception as e:
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        logger.error("Lỗi trong RAG pipeline: %s", e, exc_info=True)
        return {
            "answer": "Xin lỗi, đã xảy ra lỗi trong quá trình xử lý yêu cầu tra cứu của bạn.",
            "sources": formatted_sources,
            "response_time_ms": elapsed_ms,
            "error": str(e),
            "fallback_used": fallback_used,
        }


def rag_query_stream(
    query: str,
    top_k: int = DEFAULT_TOP_K,
) -> tuple[list[dict[str, Any]], Iterator[str], dict[str, Any]]:
    """
    Thực thi truy vấn RAG theo chế độ streaming, trả về danh sách nguồn và generator sinh text.

    Args:
        query: Câu hỏi của người dùng.
        top_k: Số lượng chunks hạt giống cần truy xuất.

    Returns:
        Tuple gồm (formatted_sources, stream_generator, metadata_dict).

    Raises:
        ValueError: Khi câu hỏi rỗng.
    """
    start_time = time.perf_counter()

    if not query or not query.strip():
        raise ValueError("Câu hỏi không được để trống")

    if not is_safe_query(query):
        def _unsafe_stream() -> Iterator[str]:
            yield "Xin lỗi, câu hỏi của bạn chứa nội dung không phù hợp với quy định của hệ thống."

        return [], _unsafe_stream(), {"query_type": "unsafe", "retrieval_time_ms": 0, "fallback_used": False}

    clean_q = query.strip()
    norm_q = normalize_cache_query(clean_q) or clean_q.lower()
    cache_key = (norm_q, top_k)

    if ENABLE_QUERY_CACHE:
        cached = _query_cache.get(cache_key) or get_cached_query_response(clean_q, top_k=top_k)
        if cached and cached.get("answer"):
            cached_sources = cached.get("sources", [])

            def _cached_stream() -> Iterator[str]:
                yield str(cached.get("answer", ""))

            meta = {
                "query_type": cached.get("query_type", "factual"),
                "retrieval_time_ms": int((time.perf_counter() - start_time) * 1000),
                "contexts_count": len(cached_sources),
                "fallback_used": bool(cached.get("fallback_used", False)),
                "cache_hit": True,
            }
            return cached_sources, _cached_stream(), meta

    q_type = classify_query(query)
    raw_contexts, formatted_sources = retrieve_relevant_contexts(query, top_k=top_k)
    retrieval_ms = int((time.perf_counter() - start_time) * 1000)

    vector_distances = [
        source["distance"]
        for source in formatted_sources
        if source.get("has_vector_match", True)
        and isinstance(source.get("distance"), (int, float))
    ]
    best_distance = min(vector_distances, default=1.0)
    has_keyword_match = any(source.get("has_keyword_match", False) for source in formatted_sources)
    local_scores = [
        float(source["local_relevance_score"])
        for source in formatted_sources
        if isinstance(source.get("local_relevance_score"), (int, float))
    ]
    if local_scores:
        has_good_match = bool(
            formatted_sources
            and (best_distance < 0.42 or max(local_scores) >= 5.5)
        )
    else:
        has_good_match = bool(
            formatted_sources and (best_distance < 0.42 or has_keyword_match)
        )

    if not has_good_match and q_type != "out_of_scope":
        logger.info("[Stream] Độ tương đồng thấp (best_dist=%.4f), thử Search Fallback...", best_distance)
        fallback_items = search_fallback(query, top_k=3)
        if fallback_items:
            fallback_sources = [
                {
                    "chunk_id": None,
                    "citation": f"[Web HaUI] {item['title']}",
                    "distance": None,
                    "source_type": "web",
                    "content": f"{item['snippet']}\nLink: {item['link']}",
                }
                for item in fallback_items
            ]
            prompt_fallback = build_fallback_prompt(query, fallback_items)

            def _fallback_stream() -> Iterator[str]:
                yield from generate_answer_stream(prompt_fallback)

            meta = {
                "query_type": q_type,
                "retrieval_time_ms": retrieval_ms,
                "contexts_count": len(fallback_items),
                "fallback_used": True,
            }
            return fallback_sources, _fallback_stream(), meta

    prompt = build_prompt(query, raw_contexts)
    stream_generator = generate_answer_stream(prompt)

    meta = {
        "query_type": q_type,
        "retrieval_time_ms": retrieval_ms,
        "contexts_count": len(raw_contexts),
        "fallback_used": False,
    }

    return formatted_sources, stream_generator, meta
