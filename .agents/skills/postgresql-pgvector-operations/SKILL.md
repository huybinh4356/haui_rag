---
name: postgresql-pgvector-operations
description: Kỹ năng truy vấn dữ liệu vector trong PostgreSQL + pgvector. Tìm kiếm chunks liên quan, kiểm tra dữ liệu, và tối ưu truy vấn. Dùng khi làm việc với vector database ở chế độ READ-ONLY
---

# PostgreSQL + pgvector Operations (READ-ONLY)

## Khi nào dùng skill này

- Kết nối PostgreSQL từ Python
- Truy vấn vector similarity (tìm chunks liên quan)
- Kiểm tra chất lượng dữ liệu đã có
- Tối ưu truy vấn với index HNSW

## LƯU Ý QUAN TRỌNG

**Giai đoạn này CHỈ ĐỌC dữ liệu, KHÔNG ghi.**

- Được phép: `SELECT`, `EXPLAIN`
- KHÔNG được: `INSERT`, `UPDATE`, `DELETE`, `DROP`

## Kết nối database

```python
import os
import psycopg2
from pgvector.psycopg2 import register_vector
from dotenv import load_dotenv

load_dotenv()


def connect_db():
    """
    Kết nối PostgreSQL và đăng ký kiểu vector.
    
    Returns:
        Connection object đã đăng ký pgvector
    """
    conn = psycopg2.connect(
        host=os.getenv("DB_HOST", "localhost"),
        port=os.getenv("DB_PORT", "5432"),
        database=os.getenv("DB_NAME", "rag_haui"),
        user=os.getenv("DB_USER", "postgres"),
        password=os.getenv("DB_PASSWORD"),
    )
    register_vector(conn)
    return conn
```

## Truy vấn vector (hàm chính)

```python
def search_similar_chunks(query_embedding: list[float], top_k: int = 5) -> list[dict]:
    """
    Tìm top_k chunks gần nhất với query vector.
    
    Args:
        query_embedding: Vector 3072 chiều của câu hỏi
        top_k: Số lượng chunks cần lấy
        
    Returns:
        List các dict: {content, metadata, distance}
    """
    conn = connect_db()
    
    try:
        with conn.cursor() as cur:
            cur.execute("""
                SELECT 
                    content,
                    metadata,
                    embedding <=> %s::vector AS distance
                FROM documents
                ORDER BY embedding <=> %s::vector
                LIMIT %s
            """, (query_embedding, query_embedding, top_k))
            
            rows = cur.fetchall()
        
        return [
            {
                "content": row[0],
                "metadata": row[1],
                "distance": float(row[2])
            }
            for row in rows
        ]
    finally:
        conn.close()
```

## Kiểm tra dữ liệu (chỉ đọc)

### Đếm tổng số chunks

```sql
SELECT COUNT(*) AS tong FROM documents;
```

### Kiểm tra số chiều vector

```sql
SELECT vector_dims(embedding) AS so_chieu 
FROM documents 
LIMIT 1;
```

### Đếm chunks theo văn bản

```sql
SELECT 
    metadata->>'ma_van_ban' AS ma_van_ban,
    metadata->>'ten_van_ban' AS ten_van_ban,
    COUNT(*) AS so_chunk
FROM documents
GROUP BY metadata->>'ma_van_ban', metadata->>'ten_van_ban'
ORDER BY so_chunk DESC;
```

### Kiểm tra vector NULL

```sql
SELECT COUNT(*) AS vector_null
FROM documents
WHERE embedding IS NULL;
```

### Xem mẫu dữ liệu

```sql
SELECT 
    id,
    LEFT(content, 150) AS noi_dung,
    metadata->>'ma_van_ban' AS ma_van_ban,
    metadata->>'dieu' AS dieu,
    metadata->>'khoan' AS khoan,
    vector_dims(embedding) AS so_chieu
FROM documents
ORDER BY id
LIMIT 10;
```

### Kiểm tra index

**Xem tất cả index của bảng:**

```sql
SELECT indexname, indexdef 
FROM pg_indexes 
WHERE tablename = 'documents';
```

**Kiểm tra index có hoạt động không:**

```sql
EXPLAIN ANALYZE
SELECT content, metadata
FROM documents
ORDER BY embedding <=> (
    SELECT embedding FROM documents WHERE id = 1
)
LIMIT 5;
```

*Kết quả mong đợi:* Thấy dòng `Index Scan using documents_embedding_idx`.

## Tối ưu truy vấn

### 1. Luôn set LIMIT

```python
# ĐÚNG - Chỉ lấy 5 chunks
cur.execute("... LIMIT 5")

# SAI - Lấy tất cả, rất chậm
cur.execute("SELECT * FROM documents ORDER BY embedding <=> %s")
```

### 2. Dùng parameterized query

```python
# ĐÚNG - An toàn SQL injection
cur.execute("SELECT * FROM documents WHERE id = %s", (doc_id,))

# SAI - Có thể bị SQL injection
cur.execute(f"SELECT * FROM documents WHERE id = {doc_id}")
```

### 3. Đóng connection sau khi dùng

```python
conn = connect_db()
try:
    # ... query ...
finally:
    conn.close()  # Bắt buộc
```

## Lưu ý quan trọng

### Kích thước vector
- Cột embedding là `vector(3072)` (3072 chiều).
- Phải dùng cùng model embedding cho query và document.
- Nếu sai kích thước → lỗi `expected 3072 dimensions`.

### Distance operator
- `<=>`: Cosine distance (dùng cho text) - Khuyến nghị
- `<->`: L2 distance
- `<#>`: Inner product

### Hiệu năng
- Index HNSW giúp query nhanh hơn 10-100 lần.
- Với 1064 chunks → query < 100ms.
- Với 100k chunks → query < 500ms.

### Backup (chỉ khi cần)

```bash
pg_dump -U postgres -d rag_haui -F c -f rag_haui_backup.dump
```
