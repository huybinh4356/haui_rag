"""Module xử lý tầng Retrieval: Hybrid Search (Vector + Keyword), RRF Fusion và LLM Reranking."""

import json
import logging
import re
from concurrent.futures import ThreadPoolExecutor
from typing import Any

from google.genai import types

from haui_rag.config import (
    DEFAULT_TOP_K,
    MAX_TOP_K,
    LLM_MODEL,
    LLM_PROVIDER,
    LOCAL_LLM_MODEL,
    OLLAMA_NUM_CTX,
    OLLAMA_NUM_GPU,
    OLLAMA_TIMEOUT_SECONDS,
    USE_LLM_RERANK,
    USE_LOCAL_RERANK,
)
from haui_rag.core.embedding import get_embedding, get_genai_client
from haui_rag.core.generation import call_ollama_generate
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
        merged_keyword_results = keyword_results
    else:
        keyword_query_scores: dict[int, float] = {}
        keyword_chunks: dict[int, dict[str, Any]] = {}
        for result_list in keyword_result_lists:
            for rank, chunk in enumerate(result_list, start=1):
                cid = chunk["id"]
                keyword_chunks.setdefault(cid, chunk)
                keyword_query_scores[cid] = keyword_query_scores.get(cid, 0.0) + (1.0 / (k + rank))

        merged_ids = sorted(
            keyword_query_scores,
            key=lambda cid: keyword_query_scores[cid],
            reverse=True,
        )
        merged_keyword_results = [keyword_chunks[cid] for cid in merged_ids]

    for rank, chunk in enumerate(merged_keyword_results, start=1):
        cid = chunk["id"]
        keyword_ids.add(cid)
        chunks_map.setdefault(cid, chunk)
        scores[cid] = scores.get(cid, 0.0) + (weight_keyword / (k + rank))

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
        len(keyword_result_lists) if keyword_result_lists is not None else int(bool(keyword_results)),
        len(keyword_ids),
    )
    return fused_results


def select_contexts_for_coverage(
    fused_chunks: list[dict[str, Any]],
    top_k: int,
) -> list[dict[str, Any]]:
    if top_k <= 0:
        return []
    if len(fused_chunks) <= top_k or top_k < 2:
        return fused_chunks[:top_k]

    selected = list(fused_chunks[:top_k])
    selected_ids = {chunk["id"] for chunk in selected}

    for match_flag in ("has_vector_match", "has_keyword_match"):
        if any(chunk.get(match_flag, False) for chunk in selected):
            continue

        replacement = next(
            (
                chunk
                for chunk in fused_chunks[top_k:]
                if chunk["id"] not in selected_ids and chunk.get(match_flag, False)
            ),
            None,
        )
        if replacement is not None:
            removed = selected.pop()
            selected_ids.remove(removed["id"])
            selected.append(replacement)
            selected_ids.add(replacement["id"])

    rank_by_id = {chunk["id"]: index for index, chunk in enumerate(fused_chunks)}
    selected.sort(key=lambda chunk: rank_by_id.get(chunk["id"], len(fused_chunks)))
    return selected


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


def rerank_by_local_model(
    query: str,
    chunks: list[dict[str, Any]],
    top_k: int = DEFAULT_TOP_K,
) -> list[dict[str, Any]]:
    if not chunks or len(chunks) <= 1:
        return chunks[:top_k]

    candidates = chunks[: min(len(chunks), 10)]
    context_summaries = []
    for index, chunk in enumerate(candidates, start=1):
        citation = format_citation(chunk.get("metadata", {}))
        snippet = chunk.get("content", "").replace("\\n", " ").strip()[:220]
        context_summaries.append(f"[{index}] {citation}: {snippet}")

    prompt = f"""Bạn đang xếp hạng các đoạn trích quy chế đại học để tìm nguồn trả lời câu hỏi.
Chấm điểm từng đoạn từ 0 đến 10 theo mức độ trực tiếp hữu ích để trả lời câu hỏi.
Ưu tiên nội dung nêu đúng chủ thể, quyền/nghĩa vụ, điều kiện hoặc quy định được hỏi. Không chấm cao chỉ vì đoạn có từ khóa chung.
Không suy diễn nội dung không xuất hiện trong đoạn. Chỉ trả JSON, không giải thích.

Câu hỏi: {query}

Các đoạn:
{chr(10).join(context_summaries)}

Định dạng:
{{"scores":[{{"index":1,"score":9}},{{"index":2,"score":3}}]}}
Hãy trả điểm cho mọi chỉ mục từ 1 đến {len(candidates)}.
"""

    try:
        response_text = call_ollama_generate(
            prompt,
            model=LOCAL_LLM_MODEL,
            temperature=0.0,
            timeout=min(60, OLLAMA_TIMEOUT_SECONDS),
            num_ctx=min(2048, OLLAMA_NUM_CTX),
            num_predict=180,
            num_gpu=OLLAMA_NUM_GPU,
        )
        match = re.search(r"\\{.*\\}", response_text, flags=re.DOTALL)
        if not match:
            raise ValueError("Mô hình local không trả về JSON hợp lệ")

        payload = json.loads(match.group(0))
        score_map: dict[int, float] = {}
        for item in payload.get("scores", []):
            index = int(item.get("index", 0))
            score = float(item.get("score", -1))
            if 1 <= index <= len(candidates) and 0 <= score <= 10:
                score_map[index] = score

        if not score_map:
            raise ValueError("Mô hình local không trả điểm hợp lệ")

        denominator = max(len(candidates) - 1, 1)
        for index, chunk in enumerate(candidates):
            rank_score = 1.0 - index / denominator
            local_score = score_map.get(index + 1, rank_score * 10) / 10.0
            blended_score = 0.65 * local_score + 0.35 * rank_score
            chunk["local_relevance_score"] = round(local_score * 10, 2)
            chunk["rerank_score"] = round(blended_score * 10, 2)
            chunk["_local_blended_score"] = blended_score

        candidates.sort(key=lambda item: item.get("_local_blended_score", 0.0), reverse=True)
        ranked = select_contexts_for_coverage(candidates, top_k=top_k)
        for chunk in ranked:
            chunk.pop("_local_blended_score", None)
        logger.info("Local reranking bằng %s hoàn tất cho %d chunks", LOCAL_LLM_MODEL, len(candidates))
        return ranked

    except Exception as e:
        logger.warning("Local reranking không thành công; dùng thứ tự RRF: %s", e)
        return select_contexts_for_coverage(chunks, top_k=top_k)


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
    elif USE_LOCAL_RERANK and LLM_PROVIDER == "ollama":
        final_contexts = rerank_by_local_model(query, fused_chunks, top_k=top_k)
    else:
        final_contexts = select_contexts_for_coverage(fused_chunks, top_k=top_k)

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
                "local_relevance_score": c.get("local_relevance_score", None),
                "has_vector_match": c.get("has_vector_match", False),
                "has_keyword_match": c.get("has_keyword_match", False),
                "content": c.get("content", ""),
            }
        )

    return final_contexts, formatted_sources
