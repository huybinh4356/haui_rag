"""Script kiểm tra kết nối cơ sở dữ liệu PostgreSQL + pgvector ở chế độ READ-ONLY."""

import logging
import os
from pathlib import Path

from dotenv import load_dotenv
from pgvector.psycopg2 import register_vector
import psycopg2

PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(PROJECT_ROOT / ".env")

logger = logging.getLogger(__name__)


def verify_database_connection() -> int:
    """
    Kiểm tra kết nối tới bảng documents trong PostgreSQL ở chế độ READ-ONLY.

    Returns:
        Tổng số bản ghi hiện có trong bảng documents.

    Raises:
        ConnectionError: Khi không thể kết nối tới cơ sở dữ liệu.
    """
    conn = None
    try:
        conn = psycopg2.connect(
            host=os.getenv("DB_HOST", "localhost"),
            port=os.getenv("DB_PORT", "5432"),
            database=os.getenv("DB_NAME", "rag_haui"),
            user=os.getenv("DB_USER", "postgres"),
            password=os.getenv("DB_PASSWORD", ""),
        )
        register_vector(conn)
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM documents;")
            row = cur.fetchone()
            total_docs = int(row[0]) if row else 0
        logger.info("Kết nối DB thành công. Tổng số chunks trong bảng documents: %d", total_docs)
        return total_docs
    except psycopg2.Error as e:
        logger.error("Không kết nối được cơ sở dữ liệu: %s", e, exc_info=True)
        raise ConnectionError("Database không khả dụng") from e
    finally:
        if conn is not None and not conn.closed:
            conn.close()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    verify_database_connection()
