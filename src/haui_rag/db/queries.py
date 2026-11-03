"""Module thực hiện các truy vấn dữ liệu Vector và Keyword trong PostgreSQL."""

import logging
import re
from typing import Any

import psycopg2

from haui_rag.config import DEFAULT_TOP_K, MAX_TOP_K
from haui_rag.db.connection import connect_db
from haui_rag.utils.helpers import enrich_chunk_metadata

logger = logging.getLogger("haui_rag")


def _content_fingerprint(content: str, metadata: dict[str, Any]) -> tuple[str, str, str, str]:
    """Tạo khóa nhận diện nội dung chuẩn hóa để loại bỏ các dòng trùng lặp hoặc OCR lặp trong DB."""
    ten_file = str(metadata.get("ten_file") or metadata.get("ma_van_ban") or "").strip().casefold()
    dieu = str(metadata.get("dieu") or "").strip().casefold()
    khoan = str(metadata.get("khoan") or "").strip().casefold()
    sub_idx = str(metadata.get("sub_index") or "").strip().casefold()
    body = re.sub(r"^điều\s*\d+\s*[\.\:]?\s*(?:\d+\s*[\.\:]?\s*)?", "", str(content or "").strip(), flags=re.IGNORECASE)
    alnum_prefix = re.sub(r"[^\w]", "", body.casefold())[:12]
    return (ten_file, dieu, f"{khoan}:{sub_idx}", alnum_prefix)


def _is_cover_decision_boilerplate(content: str) -> bool:
    """Kiểm tra chunk có phải là Điều 1, 2, 3 của tờ Quyết định ban hành đính kèm ở trang bìa hay không."""
    text_lower = re.sub(r"\s+", " ", str(content or "")).strip().lower()
    if len(text_lower) > 450:
        return False
    boilerplate_markers = (
        "ban hành kèm theo quyết định này",
        "quyết định này có hiệu lực",
        "chịu trách nhiệm thi hành quyết định",
        "chịu trách nhiệm thi hành định này",
        "thay thế quyết định số",
    )
    return any(marker in text_lower for marker in boilerplate_markers)


def search_similar_chunks(
    query_embedding: list[float],
    top_k: int = DEFAULT_TOP_K,
) -> list[dict[str, Any]]:
    """
    Tìm kiếm các chunks có vector gần nhất theo khoảng cách cosine (halfvec).
    Tự động khử trùng lặp nội dung và làm giàu metadata chuẩn hóa.

    Args:
        query_embedding: Vector câu hỏi 3072 chiều.
        top_k: Số lượng kết quả tối đa cần lấy.

    Returns:
        Danh sách các dict chứa id, content, metadata, distance.

    Raises:
        ValueError: Khi query_embedding không đủ 3072 chiều.
        ConnectionError: Khi truy vấn cơ sở dữ liệu thất bại.
    """
    if not query_embedding or len(query_embedding) != 3072:
        raise ValueError(
            f"query_embedding phải có độ dài 3072 (nhận được {len(query_embedding) if query_embedding else 0})"
        )

    limit = max(1, min(int(top_k), MAX_TOP_K))
    fetch_limit = min(max(limit * 3, 24), 60)

    query_sql = """
        SELECT id, content, metadata,
               (embedding::halfvec(3072) <=> %s::halfvec(3072)) AS distance
        FROM documents
        ORDER BY embedding::halfvec(3072) <=> %s::halfvec(3072) ASC, id ASC
        LIMIT %s;
    """

    conn = None
    try:
        conn = connect_db()
        with conn.cursor() as cur:
            cur.execute(query_sql, (query_embedding, query_embedding, fetch_limit))
            rows = cur.fetchall()

            results: list[dict[str, Any]] = []
            seen_fingerprints: set[tuple[str, str, str]] = set()
            for row in rows:
                raw_meta = row[2] if isinstance(row[2], dict) else {}
                enriched_meta = enrich_chunk_metadata(raw_meta)
                fp = _content_fingerprint(row[1], enriched_meta)
                if fp in seen_fingerprints:
                    continue
                seen_fingerprints.add(fp)
                results.append(
                    {
                        "id": row[0],
                        "content": row[1],
                        "metadata": enriched_meta,
                        "distance": float(row[3]),
                    }
                )
                if len(results) >= limit:
                    break

            logger.info("Vector Search tìm thấy %d chunks (đã khử trùng lặp)", len(results))
            return results
    except psycopg2.Error as e:
        logger.error("Lỗi khi truy vấn vector trong database: %s", e, exc_info=True)
        raise ConnectionError("Lỗi truy vấn cơ sở dữ liệu vector") from e
    finally:
        if conn is not None and not conn.closed:
            conn.close()


def keyword_search(
    query: str,
    top_k: int = DEFAULT_TOP_K,
) -> list[dict[str, Any]]:
    """
    Tìm kiếm từ khóa kết hợp Full-Text Search, cụm khái niệm mở rộng (phrase matching)
    và chấm điểm từ khóa thông minh, có khử trùng lặp.

    Args:
        query: Chuỗi câu hỏi hoặc biến thể truy vấn.
        top_k: Số lượng kết quả tối đa cần lấy.

    Returns:
        Danh sách các dict chứa id, content, metadata, rank_score.
    """
    if not query or not query.strip():
        return []

    clean_kw = re.sub(r"[^\w\s/]", " ", query.strip())
    limit = max(1, min(int(top_k), MAX_TOP_K))
    fetch_limit = min(max(limit * 3, 24), 60)

    query_sql = """
        SELECT id, content, metadata,
               ts_rank(to_tsvector('simple', content), plainto_tsquery('simple', %s)) AS rank_score
        FROM documents
        WHERE to_tsvector('simple', content) @@ plainto_tsquery('simple', %s)
        ORDER BY rank_score DESC, id ASC
        LIMIT %s;
    """

    stop_words = {
        "và", "của", "là", "các", "những", "cho", "được", "trong", "theo",
        "có", "từ", "một", "về", "với", "khi", "thì", "để", "hoặc", "này",
        "đó", "như", "tại", "đến", "nào", "thế", "gì", "sao", "hay",
    }
    generic_words = {
        "điều", "kiện", "khoản", "quy", "định", "chế", "trường", "học",
        "viên", "sinh", "người", "bao", "nhiêu", "lâu", "mấy", "gồm",
        "trình", "thời", "gian", "công", "tác", "tổ", "chức", "cấp",
    }

    conn = None
    try:
        conn = connect_db()
        with conn.cursor() as cur:
            cur.execute(query_sql, (clean_kw, clean_kw, fetch_limit))
            rows = cur.fetchall()

            results_map: dict[int, dict[str, Any]] = {}
            seen_fingerprints: set[tuple[str, str, str]] = set()

            for row in rows:
                raw_meta = row[2] if isinstance(row[2], dict) else {}
                enriched_meta = enrich_chunk_metadata(raw_meta)
                fp = _content_fingerprint(row[1], enriched_meta)
                if fp in seen_fingerprints:
                    continue
                seen_fingerprints.add(fp)
                results_map[row[0]] = {
                    "id": row[0],
                    "content": row[1],
                    "metadata": enriched_meta,
                    "rank_score": float(row[3]) + 5.0,
                }

            from haui_rag.core.query_processor import extract_entities, extract_search_phrases

            phrases = extract_search_phrases(query)
            entities = extract_entities(query)

            specific_tokens: list[str] = []
            fallback_tokens: list[str] = []
            for token in clean_kw.split():
                normalized_token = token.lower().strip("/")
                if len(normalized_token) <= 2 or normalized_token in stop_words:
                    continue
                if normalized_token in generic_words:
                    if normalized_token not in fallback_tokens:
                        fallback_tokens.append(normalized_token)
                else:
                    if normalized_token not in specific_tokens:
                        specific_tokens.append(normalized_token)

            tokens = (specific_tokens + fallback_tokens)[:8]

            score_parts: list[str] = []
            score_params: list[Any] = []
            where_parts: list[str] = []
            where_params: list[Any] = []

            for phrase in phrases[:6]:
                pattern = f"%{phrase}%"
                score_parts.append("CASE WHEN content ILIKE %s THEN 3.0 ELSE 0.0 END")
                score_params.append(pattern)
                where_parts.append("content ILIKE %s")
                where_params.append(pattern)

            for token in tokens:
                weight = 1.2 if token in specific_tokens else 0.4
                pattern = f"%{token}%"
                score_parts.append(f"CASE WHEN content ILIKE %s THEN {weight} ELSE 0.0 END")
                score_params.append(pattern)
                where_parts.append("content ILIKE %s")
                where_params.append(pattern)

            if entities.get("dieu"):
                score_parts.append(
                    "CASE WHEN regexp_replace(COALESCE(metadata->>'dieu', ''), '[^0-9]', '', 'g') = %s THEN 4.0 ELSE 0.0 END"
                )
                score_params.append(str(entities["dieu"]))

            if entities.get("ma_van_ban"):
                qd_pattern = f"%{entities['ma_van_ban']}%"
                score_parts.append(
                    "CASE WHEN COALESCE(metadata->>'ten_file', '') ILIKE %s OR COALESCE(metadata->>'ma_van_ban', '') ILIKE %s THEN 3.5 ELSE 0.0 END"
                )
                score_params.extend([qd_pattern, qd_pattern])

            if where_parts:
                score_expression = " + ".join(score_parts)
                conditions = " OR ".join(where_parts)
                like_sql = f"""
                    SELECT id, content, metadata,
                           ({score_expression}) AS rank_score
                    FROM documents
                    WHERE {conditions}
                    ORDER BY rank_score DESC, id ASC
                    LIMIT %s;
                """
                cur.execute(like_sql, score_params + where_params + [fetch_limit])

                for row in cur.fetchall():
                    raw_meta = row[2] if isinstance(row[2], dict) else {}
                    enriched_meta = enrich_chunk_metadata(raw_meta)
                    fp = _content_fingerprint(row[1], enriched_meta)
                    if row[0] in results_map:
                        results_map[row[0]]["rank_score"] = max(
                            results_map[row[0]]["rank_score"],
                            float(row[3]),
                        )
                        continue
                    if fp in seen_fingerprints:
                        continue
                    seen_fingerprints.add(fp)
                    results_map[row[0]] = {
                        "id": row[0],
                        "content": row[1],
                        "metadata": enriched_meta,
                        "rank_score": float(row[3]),
                    }

            results = sorted(
                results_map.values(),
                key=lambda item: (item.get("rank_score", 0.0), -int(item.get("id", 0))),
                reverse=True,
            )[:limit]

            logger.info("Keyword Search tìm thấy %d chunks (đã khử trùng lặp)", len(results))
            return results
    except psycopg2.Error as e:
        logger.error("Lỗi khi tìm kiếm keyword trong database: %s", e, exc_info=True)
        return []
    finally:
        if conn is not None and not conn.closed:
            conn.close()


def fetch_chunks_for_article(
    seed_chunk: dict[str, Any],
    limit: int = 40,
) -> list[dict[str, Any]]:
    """
    Lấy toàn bộ các khoản/đoạn thuộc cùng một Điều trong cùng văn bản quy chế.

    Args:
        seed_chunk: Chunk hạt giống dùng để xác định văn bản và số Điều.
        limit: Số lượng chunks tối đa cần lấy cho Điều đó.

    Returns:
        Danh sách các chunks thuộc cùng Điều đã được sắp xếp theo thứ tự Khoản.
    """
    metadata = seed_chunk.get("metadata")
    if not isinstance(metadata, dict):
        return []

    article_match = re.search(r"\d+", str(metadata.get("dieu", "")).strip())
    if not article_match:
        return []
    article_number = article_match.group(0)

    identity_key = None
    identity_value = None
    for metadata_key in ("ten_file", "ma_van_ban", "ten_van_ban"):
        value = str(metadata.get(metadata_key, "") or "").strip()
        if value and value.lower() not in {"none", "null", "n/a"}:
            identity_key = metadata_key
            identity_value = value
            break

    if not identity_key or not identity_value:
        return []

    identity_expression = f"COALESCE(metadata->>'{identity_key}', '')"
    bounded_limit = max(1, min(int(limit), 40))
    query_sql = f"""
        SELECT id, content, metadata
        FROM documents
        WHERE regexp_replace(COALESCE(metadata->>'dieu', ''), '[^0-9]', '', 'g') = %s
          AND {identity_expression} = %s
        ORDER BY
            CASE
                WHEN lower(COALESCE(metadata->>'khoan', '')) IN ('mở đầu', 'mo dau') THEN 0
                WHEN COALESCE(metadata->>'khoan', '') ~ '^[0-9]+$' THEN 1
                ELSE 2
            END,
            CASE
                WHEN COALESCE(metadata->>'khoan', '') ~ '^[0-9]+$'
                THEN (metadata->>'khoan')::integer
                ELSE 0
            END,
            CASE
                WHEN COALESCE(metadata->>'sub_index', '') ~ '^[0-9]+$'
                THEN (metadata->>'sub_index')::integer
                ELSE 0
            END,
            id ASC
        LIMIT %s;
    """

    conn = None
    try:
        conn = connect_db()
        with conn.cursor() as cur:
            cur.execute(query_sql, (article_number, identity_value, bounded_limit))
            rows = cur.fetchall()
        results: list[dict[str, Any]] = []
        seen_fingerprints: set[tuple[str, str, str]] = set()
        seed_is_boilerplate = _is_cover_decision_boilerplate(str(seed_chunk.get("content", "")))
        for row in rows:
            if not seed_is_boilerplate and row[0] != seed_chunk.get("id") and _is_cover_decision_boilerplate(row[1]):
                continue
            raw_meta = row[2] if isinstance(row[2], dict) else {}
            enriched_meta = enrich_chunk_metadata(raw_meta)
            fp = _content_fingerprint(row[1], enriched_meta)
            if fp in seen_fingerprints:
                continue
            seen_fingerprints.add(fp)
            results.append(
                {
                    "id": row[0],
                    "content": row[1],
                    "metadata": enriched_meta,
                    "distance": None,
                    "context_expanded": True,
                }
            )
        logger.info(
            "Mở rộng ngữ cảnh Điều %s theo metadata: %d chunks, tài liệu %s=%s",
            article_number,
            len(results),
            identity_key,
            identity_value,
        )
        return results
    except psycopg2.Error as e:
        logger.warning("Không thể mở rộng ngữ cảnh theo Điều: %s", e)
        return []
    finally:
        if conn is not None and not conn.closed:
            conn.close()
