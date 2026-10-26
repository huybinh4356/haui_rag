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
from haui_rag.db.queries import fetch_chunks_for_article, keyword_search, search_similar_chunks
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
        effective_keyword_lists = [result_list for result_list in keyword_result_lists if result_list]

    keyword_weight_per_list = (
        weight_keyword / len(effective_keyword_lists)
        if effective_keyword_lists
        else 0.0
    )

    for result_list in effective_keyword_lists:
        for rank, chunk in enumerate(result_list, start=1):
            cid = chunk["id"]
            keyword_ids.add(cid)
            chunks_map.setdefault(cid, chunk)
            scores[cid] = scores.get(cid, 0.0) + (keyword_weight_per_list / (k + rank))

    sorted_cids = sorted(scores, key=lambda cid: scores[cid], reverse=True)

    fused_results: list[dict[str, Any]] = []
    for cid in sorted_cids:
        chunk = chunks_map[cid].copy()
        chunk["rrf_score"] = round(scores[cid], 7)
        chunk["has_vector_match"] = cid in vector_ids
        chunk["has_keyword_match"] = cid in keyword_ids
        fused_results.append(chunk)

    logger.info(
        "RRF Fusion hợp nhất %d chunks (Vector: %d, Keyword queries: %d, Keyword unique results: %d)",
        len(fused_results),
        len(vector_results),
        len(effective_keyword_lists),
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
        return list(fused_chunks[:top_k])

    selected = list(fused_chunks[:top_k])
    selected_ids = {chunk["id"] for chunk in selected}

    requirements = [
        (
            "vector",
            lambda chunk: chunk.get("has_vector_match", False),
        ),
        (
            "keyword-only",
            lambda chunk: chunk.get("has_keyword_match", False)
            and not chunk.get("has_vector_match", False),
        ),
    ]

    for _, predicate in requirements:
        if any(predicate(chunk) for chunk in selected):
            continue

        replacement = next(
            (
                chunk
                for chunk in fused_chunks[top_k:]
                if chunk["id"] not in selected_ids and predicate(chunk)
            ),
            None,
        )

        if replacement is not None:
            removed = selected.pop()
            selected_ids.remove(removed["id"])
            selected.append(replacement)
            selected_ids.add(replacement["id"])

    if not any(chunk.get("has_keyword_match", False) for chunk in selected):
        replacement = next(
            (
                chunk
                for chunk in fused_chunks[top_k:]
                if chunk["id"] not in selected_ids and chunk.get("has_keyword_match", False)
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
        snippet = chunk.get("content", "").replace("\n", " ").strip()[:220]
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
            system_prompt=(
                "Bạn là bộ chấm điểm độ liên quan cho hệ thống RAG. "
                "Chấm từng đoạn từ 0 đến 10 theo mức độ hữu ích trực tiếp để trả lời câu hỏi. "
                "Không suy diễn nội dung ngoài đoạn trích. Chỉ trả JSON hợp lệ theo schema được yêu cầu."
            ),
        )
        match = re.search(r"\{.*\}", response_text, flags=re.DOTALL)
        if not match:
            raise ValueError("Mô hình local không trả về JSON hợp lệ")

        payload = json.loads(match.group(0))
        score_map: dict[int, float] = {}
        for item in payload.get("scores", []):
            index = int(item.get("index", 0))
            score = float(item.get("score", -1))
            if 1 <= index <= len(candidates) and 0 <= score <= 10:
                score_map[index] = score

        if len(score_map) != len(candidates):
            raise ValueError("Mô hình local không chấm điểm đầy đủ mọi đoạn ứng viên")

        denominator = max(len(candidates) - 1, 1)
        for index, chunk in enumerate(candidates):
            rank_score = 1.0 - index / denominator
            local_score = score_map.get(index + 1, rank_score * 10) / 10.0
            blended_score = 0.65 * local_score + 0.35 * rank_score
            chunk["local_relevance_score"] = round(local_score * 10, 2)
            chunk["rerank_score"] = round(blended_score * 10, 2)
            chunk["_local_blended_score"] = blended_score

        candidates.sort(key=lambda item: item.get("_local_blended_score", 0.0), reverse=True)
        ranked = candidates[:top_k]
        for chunk in ranked:
            chunk.pop("_local_blended_score", None)
        logger.info("Local reranking bằng %s hoàn tất cho %d chunks", LOCAL_LLM_MODEL, len(candidates))
        return ranked

    except Exception as e:
        logger.warning("Local reranking không thành công; dùng thứ tự RRF: %s", e)
        return select_contexts_for_coverage(chunks, top_k=top_k)



def _article_identity(chunk: dict[str, Any]) -> tuple[str, str, str] | None:
    metadata = chunk.get("metadata")
    if not isinstance(metadata, dict):
        return None

    article_match = re.search(r"\d+", str(metadata.get("dieu", "")).strip())
    if not article_match:
        return None

    for field in ("ten_file", "ma_van_ban", "ten_van_ban"):
        value = str(metadata.get(field, "") or "").strip()
        if value and value.lower() not in {"none", "null", "n/a"}:
            return field, value.casefold(), article_match.group(0)
    return None


def _article_sort_key(chunk: dict[str, Any]) -> tuple[int, int, int, int]:
    metadata = chunk.get("metadata")
    if not isinstance(metadata, dict):
        metadata = {}

    clause = str(metadata.get("khoan", "") or "").strip().casefold()
    sub_index = str(metadata.get("sub_index", "") or "").strip()
    chunk_id = chunk.get("id")
    numeric_clause = int(clause) if clause.isdigit() else 0
    numeric_sub_index = int(sub_index) if sub_index.isdigit() else 0

    if clause in {"mở đầu", "mo dau", ""}:
        clause_group = 0
    elif clause.isdigit():
        clause_group = 1
    else:
        clause_group = 2

    try:
        numeric_id = int(chunk_id)
    except (TypeError, ValueError):
        numeric_id = 0

    return clause_group, numeric_clause, numeric_sub_index, numeric_id


def expand_contexts_by_article(
    chunks: list[dict[str, Any]],
    max_articles: int = 2,
    max_context_chars: int = 7500,
    max_article_chars: int = 5200,
) -> list[dict[str, Any]]:
    if not chunks:
        return []

    original_by_id = {
        chunk.get("id"): chunk
        for chunk in chunks
        if chunk.get("id") is not None
    }
    expanded: list[dict[str, Any]] = []
    seen_ids: set[Any] = set()
    seen_content: set[tuple[tuple[Any, ...], str]] = set()
    processed_articles: set[tuple[str, str, str]] = set()
    expanded_article_count = 0
    total_chars = 0
    any_truncated = False

    for seed in chunks:
        article_key = _article_identity(seed)
        article_chunks: list[dict[str, Any]] = [seed]
        is_expanding = False

        if (
            article_key is not None
            and article_key not in processed_articles
            and expanded_article_count < max_articles
        ):
            processed_articles.add(article_key)
            related = fetch_chunks_for_article(seed, limit=40)
            if related:
                article_chunks = list(related)
                if not any(item.get("id") == seed.get("id") for item in article_chunks):
                    article_chunks.append(seed)
                article_chunks.sort(key=_article_sort_key)
                is_expanding = True
                expanded_article_count += 1

        article_chars = 0
        for item in article_chunks:
            chunk_id = item.get("id")
            if chunk_id is not None and chunk_id in seen_ids:
                continue

            item_metadata = item.get("metadata")
            if not isinstance(item_metadata, dict):
                item_metadata = {}
            identity = _article_identity(item)
            content = str(item.get("content", "") or "")
            normalized_content = re.sub(r"\s+", " ", content).strip().casefold()
            content_scope: tuple[Any, ...] = identity if identity is not None else ("chunk", chunk_id)
            content_key = (content_scope, normalized_content)

            if normalized_content and content_key in seen_content:
                if chunk_id is not None:
                    seen_ids.add(chunk_id)
                continue

            if is_expanding and article_chars + len(content) > max_article_chars:
                any_truncated = True
                logger.warning(
                    "Giới hạn độ dài khi mở rộng Điều %s; phần còn lại không được đưa vào ngữ cảnh",
                    article_key[2] if article_key else "",
                )
                break

            if total_chars + len(content) > max_context_chars:
                any_truncated = True
                logger.warning("Ngữ cảnh truy xuất đạt giới hạn %d ký tự", max_context_chars)
                break

            original = original_by_id.get(chunk_id)
            merged = item.copy()
            if original is not None:
                merged.update(
                    {
                        key: original[key]
                        for key in (
                            "distance",
                            "rrf_score",
                            "rerank_score",
                            "local_relevance_score",
                            "has_vector_match",
                            "has_keyword_match",
                        )
                        if key in original
                    }
                )
                merged["context_expanded"] = False
            else:
                merged["context_expanded"] = bool(is_expanding)

            expanded.append(merged)
            if chunk_id is not None:
                seen_ids.add(chunk_id)
            if normalized_content:
                seen_content.add(content_key)
            total_chars += len(content)
            if is_expanding:
                article_chars += len(content)

        if total_chars >= max_context_chars:
            break

    if any_truncated:
        for chunk in expanded:
            chunk["context_expansion_limited"] = True

    logger.info(
        "Mở rộng ngữ cảnh theo Điều: %d -> %d chunks, %d ký tự, bị giới hạn=%s",
        len(chunks),
        len(expanded),
        total_chars,
        any_truncated,
    )
    return expanded

def retrieve_relevant_contexts(
    query: str,
    top_k: int = DEFAULT_TOP_K,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    requested_top_k = max(1, min(int(top_k), MAX_TOP_K))
    expanded_queries = expand_query(query) or [query.strip()]
    primary_query = expanded_queries[0]
    candidate_limit = min(requested_top_k * 2, MAX_TOP_K)

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

    max_rerank_candidates = 8 if USE_LLM_RERANK else 10
    rerank_candidate_count = min(
        len(fused_chunks),
        max(8, requested_top_k * 2),
        max_rerank_candidates,
    )
    rerank_candidates = select_contexts_for_coverage(
        fused_chunks,
        top_k=rerank_candidate_count,
    )

    if USE_LLM_RERANK:
        final_contexts = rerank_by_llm(query, rerank_candidates, top_k=requested_top_k)
    elif USE_LOCAL_RERANK and LLM_PROVIDER == "ollama":
        final_contexts = rerank_by_local_model(query, rerank_candidates, top_k=requested_top_k)
    else:
        final_contexts = select_contexts_for_coverage(fused_chunks, top_k=requested_top_k)

    initial_context_count = len(final_contexts)
    final_contexts = expand_contexts_by_article(final_contexts)
    logger.info("Context article expansion: %d -> %d chunks", initial_context_count, len(final_contexts))

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
                "distance": round(c["distance"], 4) if isinstance(c.get("distance"), (int, float)) else None,
                "source_type": "database",
                "rrf_score": c.get("rrf_score", 0.0),
                "rerank_score": c.get("rerank_score", None),
                "local_relevance_score": c.get("local_relevance_score", None),
                "has_vector_match": c.get("has_vector_match", False),
                "has_keyword_match": c.get("has_keyword_match", False),
                "context_expanded": c.get("context_expanded", False),
                "context_expansion_limited": c.get("context_expansion_limited", False),
                "content": c.get("content", ""),
            }
        )

    return final_contexts, formatted_sources
