"""Module quản lý kết nối và Connection Pool tới cơ sở dữ liệu PostgreSQL + pgvector."""

import atexit
import logging
import threading
from typing import Optional
import psycopg2
from psycopg2.pool import ThreadedConnectionPool
from pgvector.psycopg2 import register_vector

from haui_rag.config import (
    DB_HOST,
    DB_PORT,
    DB_NAME,
    DB_USER,
    DB_PASSWORD,
)

logger = logging.getLogger("haui_rag")

_pool: Optional[ThreadedConnectionPool] = None
_pool_lock = threading.Lock()
MIN_CONN = 2
MAX_CONN = 10


def init_connection_pool(minconn: int = MIN_CONN, maxconn: int = MAX_CONN) -> ThreadedConnectionPool:
    """
    Khởi tạo ThreadedConnectionPool cho ứng dụng.

    Args:
        minconn: Số lượng kết nối tối thiểu trong pool.
        maxconn: Số lượng kết nối tối đa trong pool.

    Returns:
        ThreadedConnectionPool: Đối tượng quản lý pool kết nối.
    """
    global _pool
    with _pool_lock:
        if _pool is None:
            try:
                _pool = ThreadedConnectionPool(
                    minconn=minconn,
                    maxconn=maxconn,
                    host=DB_HOST,
                    port=DB_PORT,
                    database=DB_NAME,
                    user=DB_USER,
                    password=DB_PASSWORD,
                    connect_timeout=10,
                )
                logger.info(
                    "Đã khởi tạo ThreadedConnectionPool (min=%d, max=%d) tới database %s",
                    minconn,
                    maxconn,
                    DB_NAME,
                )
            except psycopg2.OperationalError as e:
                logger.error("Lỗi khởi tạo connection pool: %s", e, exc_info=True)
                raise ConnectionError("Không thể khởi tạo pool kết nối PostgreSQL") from e
    return _pool


def close_connection_pool() -> None:
    """Đóng tất cả kết nối trong connection pool khi shutdown."""
    global _pool
    with _pool_lock:
        if _pool is not None:
            try:
                _pool.closeall()
            except Exception:
                pass
            _pool = None


atexit.register(close_connection_pool)


class PooledConnectionWrapper:
    """
    Wrapper thông minh cho connection lấy từ ThreadedConnectionPool.
    Khi gọi conn.close(), đối tượng được trả lại (putconn) thay vì ngắt kết nối vật lý.
    """

    def __init__(self, raw_conn: psycopg2.extensions.connection, pool: ThreadedConnectionPool):
        self._raw_conn = raw_conn
        self._pool = pool
        self._returned = False

    def close(self) -> None:
        """Trả connection về pool một cách an toàn."""
        if not self._returned:
            self._returned = True
            try:
                if not self._raw_conn.closed:
                    self._pool.putconn(self._raw_conn)
            except Exception as e:
                logger.warning("Lỗi khi trả connection về pool: %s", e)

    @property
    def closed(self) -> int:
        return 1 if self._returned else self._raw_conn.closed

    def __getattr__(self, name: str):
        return getattr(self._raw_conn, name)

    def __enter__(self):
        return self._raw_conn

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


def connect_db() -> psycopg2.extensions.connection:
    """
    Lấy kết nối từ Connection Pool và đăng ký kiểu dữ liệu vector.
    Hỗ trợ cả conn.close() và context manager.

    Returns:
        PooledConnectionWrapper: Connection proxy an toàn cho đa luồng.
    """
    global _pool
    if _pool is None:
        init_connection_pool()

    try:
        raw_conn = _pool.getconn()
        register_vector(raw_conn)
        return PooledConnectionWrapper(raw_conn, _pool)
    except Exception as e:
        logger.error("Lỗi khi lấy connection từ pool: %s", e, exc_info=True)
        raise ConnectionError("Không thể lấy kết nối từ pool PostgreSQL") from e
