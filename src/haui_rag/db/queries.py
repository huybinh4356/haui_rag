"""Module thực hiện các truy vấn dữ liệu Vector và Keyword trong PostgreSQL."""

import logging
import re
from typing import Any
import psycopg2

from haui_rag.config import (
    DEFAULT_TOP_K,
    MAX_TOP_K,
)
from haui_rag.db.connection import connect_db

logger = logging.getLogger("haui_rag")


def search_similar_chunks(
    query_embedding: list[float],
    top_k: int = DEFAULT_TOP_K,
) -> list[dict[str, Any]]:
    """
    Tìm kiếm vector tương đồng (Semantic Search) bằng toán tử cosine <=> trên HNSW index.

    Args:
        query_embedding: Vector 3072 chiều của câu hỏi.
        top_k: Số lượng chunks cần lấy.

    Returns:
        list[dict]: Danh sách chunks kèm distance cosine.
    """
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
    """
    Tìm kiếm từ khóa (Keyword/BM25 Search) sử dụng PostgreSQL Full-Text Search.
    Tuân thủ tuyệt đối quy tắc READ-ONLY.

    Args:
        query: Câu hỏi hoặc cụm từ khóa của người dùng.
        top_k: Số lượng chunks cần lấy.

    Returns:
        list[dict]: Danh sách chunks khớp từ khóa kèm rank score.
    """
    if not query or not query.strip():
        return []

    # Làm sạch chuỗi từ khóa cho plainto_tsquery
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

    conn = None
    try:
        conn = connect_db()
        with conn.cursor() as cur:
            cur.execute(query_sql, (clean_kw, clean_kw, limit))
            rows = cur.fetchall()

            results: list[dict[str, Any]] = []
            for row in rows:
                results.append(
                    {
                        "id": row[0],
                        "content": row[1],
                        "metadata": row[2] if isinstance(row[2], dict) else {},
                        "rank_score": float(row[3]),
                    }
                )

            # Fallback ILIKE nếu tsquery không trả về kết quả
            if not results:
                tokens = [t for t in clean_kw.split() if len(t) > 2][:3]
                if tokens:
                    like_patterns = [f"%{tok}%" for tok in tokens]
                    like_sql = """
                        SELECT id, content, metadata, 0.5 AS rank_score
                        FROM documents
                        WHERE content ILIKE %s
                        LIMIT %s;
                    """
                    cur.execute(like_sql, (like_patterns[0], limit))
                    for row in cur.fetchall():
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
