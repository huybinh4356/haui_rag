---
trigger: always_on
---

# Tổng quan dự án

## Tên dự án

**Trợ lý AI hỗ trợ tra cứu quy chế, quy định và văn bản nhà trường**

## Trạng thái hiện tại

- Đã thu thập và xử lý 10 file PDF quy chế của HaUI
- Đã OCR, chunking, embedding 670+ chunks
- Đã nạp vào PostgreSQL + pgvector (vector 3072 chiều)
- **Đang làm:** Xây dựng RAG query pipeline
- **Tiếp theo:** Backend API, Frontend UI, Search Fallback

## Mục tiêu giai đoạn hiện tại

Xây dựng hệ thống trả lời câu hỏi dựa trên dữ liệu đã có trong PostgreSQL:
1. **RAG Query:** Tìm kiếm chunks + sinh câu trả lời có trích dẫn
2. **Backend API:** Expose endpoint `/chat` cho frontend
3. **Frontend UI:** Giao diện chat với Streamlit
4. **Đánh giá:** Test với 30 câu hỏi, đo độ chính xác

## KHÔNG làm trong giai đoạn này

- Không xử lý lại dữ liệu (OCR, chunking, embedding)
- Không upload file mới vào database
- Không tối ưu hóa retrieval nâng cao (reranking, hybrid search)
- Không triển khai production

→ Những việc trên sẽ làm ở giai đoạn mở rộng sau.

## Kiến trúc hiện tại (chỉ RAG query)

```text
Người dùng
↓
Streamlit (Frontend UI)
↓
FastAPI (Backend API) - endpoint POST /chat
↓
RAG Pipeline
├── Embed câu hỏi (Gemini)
├── Tìm kiếm PostgreSQL + pgvector
├── Lấy Top K chunks
├── Xây dựng prompt
└── Gọi Gemini sinh câu trả lời
↓
Trả về câu trả lời + trích dẫn
Nếu như việc tra cứu trên database không đáp ứng đủ thông tin cho user cho phép truy cập và tra cứu thông qua các cổng khác
```

## Dữ liệu hiện có

- **Database:** PostgreSQL `rag_haui`
- **Bảng:** `documents`
- **Số chunks:** 670+ (sẽ nạp nốt lên ~1064)
- **Cột:**
  - `id` (SERIAL PRIMARY KEY)
  - `content` (TEXT) - nội dung chunk
  - `metadata` (JSONB) - mã văn bản, điều, khoản...
  - `embedding` (vector(3072)) - vector embedding
- **Index:** HNSW với `halfvec(3072)`

## KPI

| Chỉ tiêu | Mục tiêu |
|---|---|
| Độ chính xác trích dẫn | ≥ 95% |
| Tỷ lệ trả lời đúng | ≥ 85% |
| Thời gian phản hồi | < 5 giây |
| Tỷ lệ hallucination | < 5% |

## Nguyên tắc cốt lõi

1. **Chính xác > Sáng tạo:** AI không được bịa, chỉ trả lời từ nguồn có sẵn
2. **Trích dẫn bắt buộc:** Mọi câu trả lời phải có nguồn
3. **Không xử lý lại data:** Chỉ query dữ liệu đã có trong DB