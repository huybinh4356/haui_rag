---
name: rag-query-pipeline
description: Kỹ năng xây dựng pipeline RAG hoàn chỉnh - tìm kiếm vector trong PostgreSQL, xây dựng prompt và gọi Gemini sinh câu trả lời có trích dẫn. Dùng khi cần trả lời câu hỏi từ dữ liệu đã embedding.
---

# RAG Query Pipeline

## Khi nào dùng skill này

- Xây dựng chức năng trả lời câu hỏi từ database
- Tìm kiếm chunks liên quan bằng vector similarity
- Sinh câu trả lời có trích dẫn nguồn
- Test RAG pipeline

## Quy trình RAG

```text
Câu hỏi → Embedding (task_type=RETRIEVAL_QUERY) → Tìm kiếm pgvector
→ Top K chunks → Xây dựng prompt → Gemini sinh câu trả lời
→ Trả về câu trả lời + trích dẫn
```

## Hàm tìm kiếm

```python
import logging

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

```python
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

TRẢ LỜI:"""


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

## Sinh câu trả lời

```python
import time
import logging

LLM_MODEL = "gemini-2.0-flash"


def generate_answer(prompt: str, max_retries: int = 3) -> str | None:
    """Gọi Gemini sinh câu trả lời."""
    for attempt in range(max_retries):
        try:
            response = client.models.generate_content(
                model=LLM_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=0.1,        # Ít sáng tạo
                    max_output_tokens=2048,
                ),
            )
            return response.text
        
        except Exception as e:
            error_msg = str(e)
            logging.warning(f"Lỗi lần {attempt + 1}: {error_msg[:150]}")
            
            if "429" in error_msg or "quota" in error_msg.lower():
                wait = 30 * (attempt + 1)
                logging.info(f"Rate limit. Chờ {wait}s...")
                time.sleep(wait)
    
    return None
```

## Hàm RAG chính

```python
def rag_query(query: str, top_k: int = TOP_K, verbose: bool = True) -> dict:
    """
    Hàm RAG hoàn chỉnh.
    
    Returns:
        {
            "answer": str,
            "sources": list[dict]
        }
    """
    if verbose:
        logging.info(f"Câu hỏi: {query}")
    
    # Bước 1: Tìm kiếm
    contexts = search_documents(query, top_k=top_k)
    
    if not contexts:
        return {
            "answer": "Không tìm thấy tài liệu liên quan.",
            "sources": []
        }
    
    # Bước 2: Xây dựng prompt
    prompt = build_prompt(query, contexts)
    
    # Bước 3: Sinh câu trả lời
    answer = generate_answer(prompt)
    
    if answer is None:
        return {
            "answer": "Xin lỗi, không thể sinh câu trả lời.",
            "sources": contexts
        }
    
    return {
        "answer": answer,
        "sources": contexts
    }
```

## Test RAG

```python
if __name__ == "__main__":
    test_questions = [
        "Điều kiện tốt nghiệp thạc sĩ là gì?",
        "Thời gian đào tạo thạc sĩ là bao lâu?",
        "Học viên bị kỷ luật khi nào?",
    ]
    
    for question in test_questions:
        result = rag_query(question)
        print(f"\n{'='*60}")
        print(f"Q: {question}")
        print(f"A: {result['answer']}")
        print(f"Nguồn: {len(result['sources'])} chunks")
```

## Lưu ý quan trọng

### Temperature
- Phải đặt `temperature=0.1` để AI trả lời chính xác.
- Temperature cao → AI sáng tạo → dễ bịa.

### Prompt
- Bắt buộc có quy tắc "không bịa".
- Phải yêu cầu trích dẫn nguồn.
- Phải có fallback khi không tìm thấy.

### Top K
- Mặc định: 5 chunks.
- Tăng lên 10 nếu câu hỏi phức tạp.
- Giảm xuống 3 nếu prompt quá dài (vượt 32k token).

### Xử lý lỗi
- Phải retry khi gặp 429.
- Phải có timeout cho API call.
- Phải log mọi lỗi để debug.