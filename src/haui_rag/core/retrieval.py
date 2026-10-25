"""Module xử lý tầng Retrieval: Hybrid Search (Vector + Keyword), RRF Fusion và LLM Reranking."""

import json
import logging
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from google.genai import types

from haui_rag.config import DEFAULT_TOP_K, MAX_TOP_K, LLM_MODEL, USE_LLM_RERANK
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
    keyword_result_lists: list[list[dict[str, Any]]] | None = None,
) -> list[dict[str, Any]]:
    scores: dict[int, float] = {}
    chunks_map: dict[int, dict[str, Any]] = {}
    vector_ids = {chunk["id"] for chunk in vector_results}
    keyword_ids: set[int] = set()

    for rank, chunk in enumerate(vector_results, start=1):
        cid = chunk["id"]
        chunks_map[cid] = chunk
        scores[cid] = scores.get(cid, 0.0) + (weight_vector / (k + rank))

    if keyword_result_lists is None:
        effective_keyword_lists = [keyword_results] if keyword_results else []
    else:
        effective_keyword_lists = [items for items in keyword_result_lists if items]

    keyword_weight_per_list = weight_keyword / len(effective_keyword_lists) if effective_keyword_lists else 0.0

    for result_list in effective_keyword_lists:
        for rank, chunk in enumerate(result_list, start=1):
            cid = chunk["id"]
            keyword_ids.add(cid)
            chunks_map.setdefault(cid, chunk)
            scores[cid] = scores.get(cid, 0.0) + (keyword_weight_per_list / (k + rank))

    sorted_cids = sorted(scores.keys(), key=lambda cid: scores[cid], reverse=True)

    fused_results: list[dict[str, Any]] = []
    for cid in sorted_cids:
        chunk = chunks_map[cid].copy()
        chunk["rrf_score"] = round(scores[cid], 5)
        chunk["has_vector_match"] = cid in vector_ids
        chunk["has_keyword_match"] = cid in keyword_ids
        fused_results.append(chunk)

    logger.info(
        "RRF Fusion hợp nhất %d chunks (Vector: %d, Keyword queries: %d, Keyword results: %d)",
        len(fused_results),
        len(vector_results),
        len(effective_keyword_lists),
        len(keyword_ids),
    )
    return fused_results


def rerank_by_llm(
    query: str,
    chunks: list[dict[str, Any]],
    top_k: int = DEFAULT_TOP_K,
) -> list[dict[str, Any]]:
    if not chunks or len(chunks) <= 1:
        return chunks[:top_k]

    candidates = chunks[: min(len(chunks), 8)]
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

            for i, c in enumerate(candidates, start=1):
                c["rerank_score"] = score_map.get(i, c.get("rrf_score", 0.5))

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
    expanded_queries = expand_query(query) or [query.strip()]
    primary_query = expanded_queries[0]
    candidate_limit = min(max(int(top_k) * 2, int(top_k), 1), MAX_TOP_K)

    with ThreadPoolExecutor(max_workers=1 + len(expanded_queries)) as executor:
        fut_embed = executor.submit(get_embedding, primary_query, "RETRIEVAL_QUERY")
        keyword_futures = [
            executor.submit(keyword_search, expanded_query, candidate_limit)
            for expanded_query in expanded_queries
        ]
        query_vector = fut_embed.result()
        keyword_result_lists = [future.result() for future in keyword_futures]

    vector_results = search_similar_chunks(query_vector, top_k=candidate_limit)

    fused_chunks = reciprocal_rank_fusion(
        vector_results=vector_results,
        keyword_results=[],
        keyword_result_lists=keyword_result_lists,
        k=60,
    )

    if USE_LLM_RERANK:
        final_contexts = rerank_by_llm(query, fused_chunks, top_k=top_k)
    else:
        final_contexts = fused_chunks[:top_k]

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
                "has_vector_match": c.get("has_vector_match", False),
                "has_keyword_match": c.get("has_keyword_match", False),
                "content": c.get("content", ""),
            }
        )

    return final_contexts, formatted_sources
