"""Integration tests kiểm tra tầng kết nối và truy vấn PostgreSQL pgvector."""

from haui_rag.config import EMBEDDING_DIMENSION
from haui_rag.db.connection import connect_db
from haui_rag.db.queries import keyword_search, search_similar_chunks


def test_db_connection_live():
    """Kiểm tra kết nối sống tới PostgreSQL."""
    conn = connect_db()
    assert not conn.closed
    with conn.cursor() as cur:
        cur.execute("SELECT COUNT(*) FROM documents;")
        count = cur.fetchone()[0]
        assert count > 0
    conn.close()


def test_db_vector_and_keyword_queries():
    """Kiểm tra thực thi đồng thời vector search và keyword search trên DB thật."""
    dummy_vec = [0.01] * EMBEDDING_DIMENSION
    vec_results = search_similar_chunks(dummy_vec, top_k=2)
    assert len(vec_results) > 0

    kw_results = keyword_search("thạc sĩ", top_k=2)
    assert len(kw_results) > 0
