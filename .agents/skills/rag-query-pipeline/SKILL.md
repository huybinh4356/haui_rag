```
name: rag-query-pipeline
description: Kỹ năng xây dựng pipeline RAG hoàn chỉnh - tìm kiếm vector trong PostgreSQL, xây dựng prompt và gọi Gemini sinh câu trả lời có trích dẫn. Dùng khi cần trả lời câu hỏi từ dữ liệu đã embedding.
```
# RAG Query Pipeline

## Khi nào dùng skill này
- Xây dựng chức năng trả lời câu hỏi từ database
- Tìm kiếm chunks liên quan bằng vector similarity
- Sinh câu trả lời có trích dẫn nguồn
- Test RAG pipeline

## Quy trình RAG

```
Câu hỏi → Embedding (task_type=QUERY) → Tìm kiếm pgvector
→ Top K chunks → Xây dựng prompt → Gemini sinh câu trả lời
→ Trả về câu trả lời + trích dẫn
```

## Hàm tìm kiếm

```python
TOP_K = 5

def search_documents(query: str, top_k: int = TOP_K) -> list[dict]:
    """
    Tìm top_k chunks liên quan nhất trong PostgreSQL.
    
    Args:
        query: Câu hỏi của người dùng
        top_k: Số lượng chunks cần lấy
        
    Returns:
        List các dict: {content, metadata, distance}
    """
    conn = connect_db()
    
    # Tạo embedding cho câu hỏi
    query_embedding = get_embedding(query, task_type="RETRIEVAL_QUERY")
    
    if query_embedding is None:
        logging.error("Không thể tạo embedding cho câu hỏi")
        conn.close()
        return []
    
    # Tìm kiếm bằng cosine distance
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
    
    conn.close()
    
    return [
        {"content": r[0], "metadata": r[1], "distance": float(r[2])}
        for r in rows
    ]
```

## Xây dựng prompt 

RAG_PROMPT_TEMPLATE = """Bạn là trợ lý AI của Trường Đại học Công nghiệp Hà Nội.
Nhiệm vụ: Trả lời câu hỏi dựa CHÍNH XÁC vào ngữ cảnh được cung cấp.

QUY TẮC BẮT BUỘC:
1. Chỉ sử dụng thông tin trong phần NGỮ CẢNH bên dưới.
2. KHÔNG tự bịa, KHÔNG suy đoán, KHÔNG thêm thông tin ngoài ngữ cảnh.
3. Nếu ngữ cảnh không đủ thông tin, trả lời: "Xin lỗi, tôi không tìm thấy quy định này trong hệ thống."
4. Trả lời ngắn gọn, rõ ràng, dễ hiểu cho sinh viên.
5. Ở cuối câu trả lời, liệt kê nguồn theo format:
   📚 Nguồn tham khảo:
   - [Mã văn bản] - Điều X, Khoản Y
6. Nếu có nhiều văn bản liên quan, ưu tiên văn bản còn hiệu lực.

NGỮ CẢNH:
{context}

CÂU HỎI: {question}

TRẢ LỜI:

```

def build_prompt(query: str, contexts: list[dict]) -> str:
    """Xây dựng prompt từ câu hỏi và các chunks."""
    context_text = ""
    for i, ctx in enumerate(contexts, 1):
        meta = ctx["metadata"]
        ma_vb = meta.get("ma_van_ban", "N/A")
        dieu = meta.get("dieu", "N/A")
        khoan = meta.get("khoan", "N/A")
        
        context_text += f"\n--- Nguồn {i} [Mã: {ma_vb}, Điều {dieu}, Khoản {khoan}] ---\n"
        context_text += ctx["content"] + "\n"
    
    return RAG_PROMPT_TEMPLATE.format(context=context_text, question=query)
```
