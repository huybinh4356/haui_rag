"""Script kiểm tra kết nối Database PostgreSQL và HNSW vector index."""

import sys
from pathlib import Path

# Thêm src vào sys.path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from haui_rag.config import DB_HOST, DB_PORT, DB_NAME, DB_USER, EMBEDDING_DIMENSION
from haui_rag.db.connection import connect_db
from haui_rag.db.queries import search_similar_chunks

def main():
    print("=" * 60)
    print("🔍 KIỂM TRA KẾT NỐI DATABASE VÀ PGVECTOR")
    print("=" * 60)
    print(f"• Host: {DB_HOST}:{DB_PORT}")
    print(f"• Database: {DB_NAME}")
    print(f"• User: {DB_USER}")

    try:
        conn = connect_db()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM documents;")
            count = cur.fetchone()[0]
            print(f"✅ Kết nối PostgreSQL thành công! Tổng số chunks: {count}")

            cur.execute("""
                SELECT indexname, indexdef 
                FROM pg_indexes 
                WHERE tablename = 'documents' AND indexname LIKE '%embedding%';
            """)
            indexes = cur.fetchall()
            for idx_name, idx_def in indexes:
                print(f"✅ Index: {idx_name}")
        conn.close()

        # Test vector search
        print("\n🔍 Kiểm tra truy vấn HNSW cosine distance...")
        dummy_vec = [0.01] * EMBEDDING_DIMENSION
        results = search_similar_chunks(dummy_vec, top_k=2)
        print(f"✅ Truy vấn vector thành công! Trả về {len(results)} chunks.")
        print(f"• Chunk mẫu ID: {results[0]['id']}, Khoảng cách: {results[0]['distance']:.4f}")

        print("\n🎉 TOÀN BỘ KẾT NỐI DATABASE HOẠT ĐỘNG HOÀN HẢO!")
    except Exception as e:
        print(f"❌ LỖI KẾT NỐI: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
