"""Module quản lý kết nối tới cơ sở dữ liệu PostgreSQL + pgvector."""

import logging
import psycopg2
from pgvector.psycopg2 import register_vector

from haui_rag.config import (
    DB_HOST,
    DB_PORT,
    DB_NAME,
    DB_USER,
    DB_PASSWORD,
)

logger = logging.getLogger("haui_rag")


def connect_db() -> psycopg2.extensions.connection:
    """
    Tạo kết nối tới PostgreSQL database và đăng ký kiểu dữ liệu vector.

    Returns:
        psycopg2.extensions.connection: Đối tượng kết nối cơ sở dữ liệu.

    Raises:
        ConnectionError: Nếu không kết nối được tới PostgreSQL.
    """
    try:
        conn = psycopg2.connect(
            host=DB_HOST,
            port=DB_PORT,
            database=DB_NAME,
            user=DB_USER,
            password=DB_PASSWORD,
            connect_timeout=10,
        )
        register_vector(conn)
        return conn
    except psycopg2.OperationalError as e:
        logger.error("Lỗi kết nối tới cơ sở dữ liệu PostgreSQL: %s", e, exc_info=True)
        raise ConnectionError("Không thể kết nối tới cơ sở dữ liệu PostgreSQL") from e
