"""Module thực hiện các truy vấn dữ liệu Vector và Keyword trong PostgreSQL."""

import logging
import re
from typing import Any

import psycopg2

from haui_rag.config import DEFAULT_TOP_K, MAX_TOP_K
from haui_rag.db.connection import connect_db

logger = logging.getLogger("haui_rag")


def search_similar_chunks(
    query_embedding: list[float],
    top_k: int = DEFAULT_TOP_K,
) -> list[dict[str, Any]]:
    if not query_embedding or len(query_embedding) != 3072:
        raise ValueError(
            f"query_embedding phải có độ dài 3072 (nhận được {len(query_embedding) if query_embedding else 0})"
        )

    limit = max(1, min(int(top_k), MAX_TOP_K))

    query_sql = """
        SELECT id, content, metadata,
               (embedding::halfvec(3072) <=> %s::halfvec(3072)) AS distance
        FROM documents
        ORDER BY embedding::halfvec(3072) <=> %s::halfvec(3072) ASC
        LIMIT %s;
    """

    conn = None
    try:
        conn = connect_db()
        with conn.cursor() as cur:
            cur.execute(query_sql, (query_embedding, query_embedding, limit))
            rows = cur.fetchall()

            results: list[dict[str, Any]] = []
            for row in rows:
                results.append(
                    {
                        "id": row[0],
                        "content": row[1],
                        "metadata": row[2] if isinstance(row[2], dict) else {},
                        "distance": float(row[3]),
                    }
                )
            logger.info("Vector Search tìm thấy %d chunks", len(results))
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
    if not query or not query.strip():
        return []

    clean_kw = re.sub(r"[^\w\s]", " ", query.strip())
    limit = max(1, min(int(top_k), MAX_TOP_K))

    query_sql = """
        SELECT id, content, metadata,
               ts_rank(to_tsvector('simple', content), plainto_tsquery('simple', %s)) AS rank_score
        FROM documents
        WHERE to_tsvector('simple', content) @@ plainto_tsquery('simple', %s)
        ORDER BY rank_score DESC
        LIMIT %s;
    """

    stop_words = {
        "và", "của", "là", "các", "những", "cho", "được", "trong", "theo",
        "có", "từ", "một", "về", "với", "khi", "thì", "để", "hoặc", "này",
        "đó", "như", "tại", "đến",
    }

    conn = None
    try:
        conn = connect_db()
        with conn.cursor() as cur:
            cur.execute(query_sql, (clean_kw, clean_kw, limit))
            rows = cur.fetchall()

            results: list[dict[str, Any]] = []
            seen_ids: set[int] = set()
            for row in rows:
                seen_ids.add(row[0])
                results.append(
                    {
                        "id": row[0],
                        "content": row[1],
                        "metadata": row[2] if isinstance(row[2], dict) else {},
                        "rank_score": float(row[3]),
                    }
                )

            if len(results) < limit:
                tokens: list[str] = []
                for token in clean_kw.split():
                    normalized_token = token.lower()
                    if len(token) <= 2 or normalized_token in stop_words or normalized_token in tokens:
                        continue
                    tokens.append(normalized_token)
                    if len(tokens) >= 5:
                        break

                if tokens:
                    score_expression = " + ".join(
                        ["CASE WHEN content ILIKE %s THEN 1 ELSE 0 END"] * len(tokens)
                    )
                    conditions = " OR ".join(["content ILIKE %s"] * len(tokens))
                    like_sql = f"""
                        SELECT id, content, metadata,
                               ({score_expression}) AS rank_score
                        FROM documents
                        WHERE {conditions}
                        ORDER BY rank_score DESC
                        LIMIT %s;
                    """
                    patterns = [f"%{token}%" for token in tokens]
                    cur.execute(like_sql, patterns + patterns + [limit])

                    for row in cur.fetchall():
                        if row[0] in seen_ids or len(results) >= limit:
                            continue
                        seen_ids.add(row[0])
                        results.append(
                            {
                                "id": row[0],
                                "content": row[1],
                                "metadata": row[2] if isinstance(row[2], dict) else {},
                                "rank_score": float(row[3]),
                            }
                        )

            logger.info("Keyword Search tìm thấy %d chunks", len(results))
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
        for row in rows:
            results.append(
                {
                    "id": row[0],
                    "content": row[1],
                    "metadata": row[2] if isinstance(row[2], dict) else {},
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
