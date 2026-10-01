"""Module điều phối RAG Pipeline V2: Kết hợp Query Understanding, Hybrid Search, Reranking, Adaptive Prompting và Search Fallback."""

from collections import OrderedDict
import logging
import time
from typing import Any

from haui_rag.config import DEFAULT_TOP_K, ENABLE_QUERY_CACHE, QUERY_CACHE_SIZE
from haui_rag.core.fallback import generate_from_fallback, search_fallback
from haui_rag.core.generation import build_prompt, generate_answer
from haui_rag.core.query_processor import classify_query
from haui_rag.core.retrieval import retrieve_relevant_contexts
from haui_rag.utils.helpers import is_safe_query

logger = logging.getLogger("haui_rag")

# In-memory LRU Cache cho truy vấn câu hỏi
_query_cache: OrderedDict[tuple[str, int], dict[str, Any]] = OrderedDict()


def rag_query(
    query: str,
    top_k: int = DEFAULT_TOP_K,
) -> dict[str, Any]:
    """
    Thực thi RAG Pipeline thông minh thế hệ mới (V2):
    1. Kiểm tra cache câu hỏi để trả lời siêu tốc (< 5ms)
    2. Kiểm tra an toàn query (Prompt Injection)
    3. Phân loại loại câu hỏi (Query Understanding)
    4. Hybrid Search song song (Vector + Keyword) + RRF Fusion
    5. Adaptive Prompting
    6. Sinh câu trả lời có trích dẫn nguồn chuẩn xác

    Args:
        query: Câu hỏi của người dùng.
        top_k: Số chunks tốt nhất cần lấy (mặc định 5).

    Returns:
        dict chứa answer, sources, response_time_ms, query_type, fallback_used.
    """
    start_time = time.perf_counter()

    if not query or not query.strip():
        raise ValueError("Câu hỏi không được để trống")

    if len(query) > 1000:
        raise ValueError("Câu hỏi không được vượt quá 1000 ký tự")

    clean_q = query.strip()
    cache_key = (clean_q.lower(), top_k)

    # Kiểm tra Cache
    if ENABLE_QUERY_CACHE and cache_key in _query_cache:
        cached_result = _query_cache[cache_key].copy()
        _query_cache.move_to_end(cache_key)
        cached_result["response_time_ms"] = int((time.perf_counter() - start_time) * 1000)
        logger.info("Tra cứu từ Cache thành công cho: '%s' (%d ms)", clean_q, cached_result["response_time_ms"])
        return cached_result

    # 1. Kiểm tra Prompt Injection
    if not is_safe_query(query):
        logger.warning("Truy vấn bị từ chối do không an toàn: %s", query)
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        return {
            "answer": "Xin lỗi, câu hỏi của bạn chứa nội dung không phù hợp với quy định của hệ thống.",
            "sources": [],
            "response_time_ms": elapsed_ms,
            "fallback_used": False,
        }

    # 2. Phân tích loại câu hỏi
    q_type = classify_query(query)
    logger.info("Nhận truy vấn: '%s' | Phân loại: %s", query, q_type)

    try:
        # 3 & 4. Hybrid Search + RRF + Reranking
        raw_contexts, formatted_sources = retrieve_relevant_contexts(query, top_k=top_k)

        # Kiểm tra chất lượng kết quả tìm kiếm trong DB
        best_distance = formatted_sources[0]["distance"] if formatted_sources else 1.0
        has_good_match = bool(formatted_sources and best_distance < 0.42)

        # 5. Kích hoạt Search Fallback nếu DB không có hoặc độ tương đồng quá kém
        fallback_used = False
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
                            "distance": 0.0,
                            "content": f"{item['snippet']}\nLink: {item['link']}",
                        }
                        for item in fallback_items
                    ],
                    "response_time_ms": elapsed_ms,
                    "query_type": q_type,
                    "fallback_used": True,
                }

        # 6. Adaptive Prompting V2
        prompt = build_prompt(query, raw_contexts)
        logger.info("Đang gọi LLM với Adaptive Prompt V2...")
        answer = generate_answer(prompt)

        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        logger.info("Hoàn thành truy vấn RAG trong %d ms", elapsed_ms)

        final_response = {
            "answer": answer,
            "sources": formatted_sources,
            "response_time_ms": elapsed_ms,
            "query_type": q_type,
            "fallback_used": fallback_used,
        }

        # Lưu vào cache nếu thành công
        if ENABLE_QUERY_CACHE:
            if len(_query_cache) >= QUERY_CACHE_SIZE:
                _query_cache.popitem(last=False)
            _query_cache[cache_key] = final_response.copy()

        return final_response

    except Exception as e:
        elapsed_ms = int((time.perf_counter() - start_time) * 1000)
        logger.error("Lỗi trong RAG pipeline: %s", e, exc_info=True)
        return {
            "answer": "Xin lỗi, đã xảy ra lỗi trong quá trình xử lý yêu cầu tra cứu của bạn.",
            "sources": formatted_sources if "formatted_sources" in locals() else [],
            "response_time_ms": elapsed_ms,
            "error": str(e),
            "fallback_used": fallback_used if "fallback_used" in locals() else False,
        }

