"""Package db quản lý kết nối và truy vấn PostgreSQL pgvector."""

from haui_rag.db.connection import connect_db
from haui_rag.db.queries import search_similar_chunks

__all__ = ["connect_db", "search_similar_chunks"]
