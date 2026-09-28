---
trigger: always_on
---

# Ràng buộc kiến trúc

## Luồng truy vấn BẤT BIẾN
```
Câu hỏi người dùng
↓ [Gemini Embedding với task_type=RETRIEVAL_QUERY]
Query vector (3072 chiều)
↓ [pgvector cosine distance]
Top K chunks liên quan từ PostgreSQL
↓ [Prompt template]
Prompt hoàn chỉnh
↓ [Gemini 2.0 Flash]
Câu trả lời + Trích dẫn
↓
Trả về người dùng
```

## Quy tắc thiết kế

### 1. Embedding câu hỏi
- **Bắt buộc** dùng `task_type="RETRIEVAL_QUERY"` (KHÁC với document)
- **Bắt buộc** dùng cùng model `gemini-embedding-001` như khi nạp data
- **Phải** set timeout 300s cho Gemini call

### 2. Retrieval
- **Bắt buộc** dùng cosine distance (`<=>` operator)
- Top K mặc định: **5 chunks**
- **Phải** trả về metadata kèm theo để trích dẫn
- **Phải** sort theo distance tăng dần (gần nhất trước)

### 3. Generation
- **Bắt buộc** dùng prompt template có quy tắc "không bịa"
- Temperature: **0.1** (thấp để tăng độ chính xác)
- **Phải** trích dẫn nguồn theo format: `[Mã văn bản] - Điều X, Khoản Y`
- Nếu không có thông tin → trả lời: "Xin lỗi, tôi không tìm thấy quy định này trong hệ thống."

### 4. API
- Endpoint chính: `POST /api/chat`
- Request body: `{"question": "string"}`
- Response body: `{"answer": "string", "sources": [...]}`
- **Phải** có timeout 300s
- **Phải** có try/except và logging

### 5. Database
- **Chỉ ĐỌC** từ bảng `documents` (SELECT), không INSERT/UPDATE/DELETE
- **Bắt buộc** dùng index HNSW `halfvec_cosine_ops`
- **Phải** dùng parameterized query (chống SQL injection)
- **Phải** đóng connection sau mỗi query

## Ràng buộc bảo mật
- **Không** hard-code API key, mật khẩu trong code
- **Không** ghi log PII
- **Phải** validate input để chống prompt injection

## Ràng buộc hiệu năng
- Response time < 5 giây cho 95% request
- Không query quá 10 chunks/lần
- Cache các câu hỏi phổ biến (giai đoạn sau)

## KHÔNG được làm (giai đoạn này)
- ❌ Không xử lý lại PDF, OCR, chunking
- ❌ Không thêm dữ liệu mới vào DB
- ❌ Không dùng ChromaDB hoặc vector DB khác
- ❌ Không dùng google-generativeai (đã deprecated)