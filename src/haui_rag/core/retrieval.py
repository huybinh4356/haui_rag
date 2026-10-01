"""Module xử lý tầng Retrieval: Hybrid Search (Vector + Keyword), RRF Fusion và LLM Reranking."""

import json
import logging
import re
from typing import Any
from google.genai import types

from haui_rag.config import DEFAULT_TOP_K, LLM_MODEL, USE_LLM_RERANK
from haui_rag.core.embedding import get_embedding, get_genai_client
from haui_rag.core.query_processor import expand_query
from haui_rag.db.queries import keyword_search, search_similar_chunks
from haui_rag.utils.helpers import format_citation

logger = logging.getLogger("haui_rag")


def reciprocal_rank_fusion(
    vector_results: list[dict[str, Any]],
    keyword_results: list[dict[str, Any]],
    k: int = 60,
    weight_vector: float = 0.7,
    weight_keyword: float = 0.3,
) -> list[dict[str, Any]]:
    """
    Kết hợp kết quả tìm kiếm Vector và Keyword sử dụng thuật toán Reciprocal Rank Fusion (RRF).

    Formula:
        RRF_Score = weight_vector / (k + rank_vector) + weight_keyword / (k + rank_keyword)

    Args:
        vector_results: Danh sách kết quả từ vector search.
        keyword_results: Danh sách kết quả từ keyword search.
        k: Hằng số làm mượt rank (mặc định 60).
        weight_vector: Trọng số vector search (0.7).
        weight_keyword: Trọng số keyword search (0.3).

    Returns:
        list[dict]: Danh sách chunks hợp nhất và sắp xếp theo điểm RRF giảm dần.
    """
    scores: dict[int, float] = {}
    chunks_map: dict[int, dict[str, Any]] = {}

    # Chấm điểm từ Vector Search
    for rank, chunk in enumerate(vector_results, start=1):
        cid = chunk["id"]
        chunks_map[cid] = chunk
        scores[cid] = scores.get(cid, 0.0) + (weight_vector / (k + rank))

    # Chấm điểm từ Keyword Search
    for rank, chunk in enumerate(keyword_results, start=1):
        cid = chunk["id"]
        if cid not in chunks_map:
            chunks_map[cid] = chunk
        scores[cid] = scores.get(cid, 0.0) + (weight_keyword / (k + rank))

    # Sắp xếp kết quả theo RRF score
    sorted_cids = sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)

    fused_results: list[dict[str, Any]] = []
    for cid in sorted_cids:
        chunk = chunks_map[cid].copy()
        chunk["rrf_score"] = round(scores[cid], 5)
        fused_results.append(chunk)

    logger.info("RRF Fusion hợp nhất %d chunks (Vector: %d, Keyword: %d)",
                len(fused_results), len(vector_results), len(keyword_results))
    return fused_results


def rerank_by_llm(
    query: str,
    chunks: list[dict[str, Any]],
    top_k: int = DEFAULT_TOP_K,
) -> list[dict[str, Any]]:
    """
    Sử dụng LLM để chấm điểm lại (Reranking) mức độ liên quan ngữ nghĩa của từng chunk với câu hỏi.

    Args:
        query: Câu hỏi của người dùng.
        chunks: Danh sách chunks ứng viên từ Hybrid search.
        top_k: Số chunks tốt nhất cần giữ lại sau khi rerank.

    Returns:
        list[dict]: Danh sách top_k chunks đã được xếp hạng lại theo độ liên quan thực tế.
    """
    if not chunks or len(chunks) <= 1:
        return chunks[:top_k]

    candidates = chunks[: min(len(chunks), 8)]

    # Tạo tóm tắt ngữ cảnh cho batch reranking
    context_summaries = []
    for i, c in enumerate(candidates, start=1):
        citation = format_citation(c.get("metadata", {}))
        snippet = c.get("content", "").replace("\n", " ").strip()[:250]
        context_summaries.append(f"[{i}] {citation}: {snippet}")

    prompt = f"""Bạn là giám khảo đánh giá thông tin tra cứu quy chế đại học.
Hãy chấm điểm mức độ liên quan của các đoạn văn bản sau đối với câu hỏi người dùng theo thang điểm từ 0 đến 10 (10 = trực tiếp trả lời câu hỏi, 0 = không liên quan).

Câu hỏi: {query}

Danh sách đoạn văn:
{chr(10).join(context_summaries)}

Định dạng trả về duy nhất là JSON list gồm các cặp (chỉ mục số nguyên, điểm số):
Ví dụ: {{"scores": [{{"index": 1, "score": 9.5}}, {{"index": 2, "score": 4.0}}]}}
Chỉ trả về JSON, không thêm bất kỳ văn bản nào khác.
"""

    try:
        client = get_genai_client()
        response = client.models.generate_content(
            model=LLM_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.0,
                response_mime_type="application/json",
            ),
        )
        if response and response.text:
            data = json.loads(response.text.strip())
            score_map: dict[int, float] = {}
            for item in data.get("scores", []):
                idx = int(item.get("index", 0))
                sc = float(item.get("score", 0.0))
                score_map[idx] = sc

            # Gán điểm rerank cho candidates
            for i, c in enumerate(candidates, start=1):
                c["rerank_score"] = score_map.get(i, c.get("rrf_score", 0.5))

            # Sắp xếp theo rerank_score giảm dần
            candidates.sort(key=lambda x: x.get("rerank_score", 0.0), reverse=True)
            logger.info("Reranking bằng LLM hoàn tất thành công cho %d chunks", len(candidates))
            return candidates[:top_k]

    except Exception as e:
        logger.warning("Reranking bằng LLM gặp sự cố, sử dụng thứ tự RRF: %s", e)

    return chunks[:top_k]


def retrieve_relevant_contexts(
    query: str,
    top_k: int = DEFAULT_TOP_K,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    Thực hiện quy trình Retrieval toàn diện:
    1. Query Expansion (sinh biến thể câu hỏi)
    2. Vector Search (Semantic)
    3. Keyword Search (Full-Text)
    4. RRF Fusion (kết hợp vector + keyword)
    5. LLM Reranking (xếp hạng lại)

    Args:
        query: Câu hỏi của người dùng.
        top_k: Số lượng chunks cuối cùng cần lấy.

    Returns:
        tuple[list[dict], list[dict]]: (raw_contexts cho Prompt, formatted_sources cho API)
    """
    # 1. Mở rộng câu hỏi
    expanded_queries = expand_query(query)
    primary_query = expanded_queries[0]

    # 2 & 3. Thực thi song song: Gọi Gemini Embedding và tìm kiếm Keyword trong PostgreSQL
    from concurrent.futures import ThreadPoolExecutor
    with ThreadPoolExecutor(max_workers=2) as executor:
        fut_embed = executor.submit(get_embedding, primary_query, "RETRIEVAL_QUERY")
        fut_kw = executor.submit(keyword_search, primary_query, top_k * 2)

        query_vector = fut_embed.result()
        keyword_results = fut_kw.result()

    vector_results = search_similar_chunks(query_vector, top_k=top_k * 2)

    # Nếu câu hỏi mở rộng có biến thể và keyword_results chưa đủ, tìm thêm
    if len(expanded_queries) > 1 and len(keyword_results) < top_k:
        extra_kw = keyword_search(expanded_queries[1], top_k=top_k)
        seen_ids = {c["id"] for c in keyword_results}
        for ek in extra_kw:
            if ek["id"] not in seen_ids:
                keyword_results.append(ek)

    # 4. RRF Fusion
    fused_chunks = reciprocal_rank_fusion(
        vector_results=vector_results,
        keyword_results=keyword_results,
        k=60,
    )

    # 5. LLM Reranking (Nếu được kích hoạt, mặc định dùng RRF tốc độ cao tiết kiệm quota)
    if USE_LLM_RERANK:
        final_contexts = rerank_by_llm(query, fused_chunks, top_k=top_k)
    else:
        final_contexts = fused_chunks[:top_k]

    # 6. Format sources cho response
    formatted_sources: list[dict[str, Any]] = []
    for c in final_contexts:
        meta = c.get("metadata", {})
        formatted_sources.append(
            {
                "chunk_id": c.get("id"),
                "citation": format_citation(meta),
                "metadata": meta,
                "ma_van_ban": meta.get("ma_van_ban", ""),
                "ten_van_ban": meta.get("ten_van_ban", ""),
                "dieu": meta.get("dieu", ""),
                "khoan": meta.get("khoan", ""),
                "distance": round(c.get("distance", 1.0), 4),
                "source_type": "database",
                "rrf_score": c.get("rrf_score", 0.0),
                "rerank_score": c.get("rerank_score", None),
                "content": c.get("content", ""),
            }
        )

    return final_contexts, formatted_sources
