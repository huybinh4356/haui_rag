# Tài Liệu API Reference - haui-rag-assistant

## Base URL

`http://127.0.0.1:8000`

---

## 1. Health Check

Kiểm tra trạng thái hoạt động của Backend và cơ sở dữ liệu PostgreSQL.

- **Method:** `GET`
- **Path:** `/`
- **Response 200 OK:**

```json
{
  "project": "haui_rag",
  "status": "online",
  "database": "connected",
  "total_documents": 1714,
  "embedding_model": "gemini-embedding-001",
  "llm_model": "gemini-3.8-flash"
}
```

---

## 2. Chat Tra Cứu Quy Chế

Tra cứu các văn bản quy chế HaUI và sinh câu trả lời có trích dẫn.

- **Method:** `POST`
- **Path:** `/api/chat`
- **Headers:** `Content-Type: application/json`
- **Request Body:**

```json
{
  "question": "Điều kiện tốt nghiệp thạc sĩ là gì?",
  "top_k": 5
}
```

- **Response 200 OK:**

```json
{
  "answer": "Điều kiện tốt nghiệp trình độ thạc sĩ bao gồm...\n\n📚 Nguồn tham khảo:\n- [630/QĐ-ĐHCN] - Điều 7, Khoản 1",
  "sources": [
    {
      "chunk_id": 12,
      "citation": "[630/QĐ-ĐHCN] - Điều 7, Khoản 1",
      "ma_van_ban": "630/QĐ-ĐHCN",
      "ten_van_ban": "Quy chế đào tạo thạc sĩ",
      "dieu": "7",
      "khoan": "1",
      "distance": 0.2057,
      "content": "Điều 7. 1. Hoàn thành chương trình đào tạo..."
    }
  ],
  "response_time_ms": 3200,
  "error": null
}
```

- **Response 422 Unprocessable Entity:** Khi câu hỏi để trống (`""`).
- **Response 500 Internal Server Error:** Khi máy chủ gặp sự cố không thể xử lý.
