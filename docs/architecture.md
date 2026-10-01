# Kiến Trúc Hệ Thống (Clean Architecture) - haui-rag-assistant

## 1. Giới thiệu tổng quan

Dự án được xây dựng theo nguyên lý Clean Architecture, phân tách rõ ràng trách nhiệm giữa các tầng:

```text
                            [User / Client]
                                   │
                     ┌──────────────┴──────────────┐
                     ▼                             ▼
          [Streamlit Frontend]           [FastAPI Backend]
          (frontend/app.py)              (backend/main.py)
                     │                             │
                     └──────────────┬──────────────┘
                                    │ (POST /api/chat)
                                    ▼
                     [RAG Core Orchestrator]
                     (haui_rag.core.rag_pipeline)
                      │                    │
         ┌────────────┴────────┐   ┌───────┴────────────┐
         ▼                     ▼   ▼                    ▼
[Retrieval Layer]        [Database Queries]     [Generation Layer]
(core/retrieval.py)      (db/queries.py)        (core/generation.py)
         │                     │                        │
         ▼                     ▼                        ▼
[Embedding Service]   [PostgreSQL + pgvector]   [Gemini 3.8 Flash]
(core/embedding.py)   (HNSW halfvec index)      (Temperature 0.1)
```

## 2. Chi tiết các tầng trong `src/haui_rag/`

### 2.1. Tầng Core (`haui_rag.core`)

- `embedding.py`: Kết nối SDK `google-genai` tạo vector 3072 chiều (`gemini-embedding-001`, `task_type="RETRIEVAL_QUERY"`).
- `retrieval.py`: Nhận vector và lấy top chunks từ database, format metadata.
- `generation.py`: Ghép context vào template chống bịa, gọi LLM `gemini-3.8-flash` với cơ chế retry exponential backoff.
- `rag_pipeline.py`: Orchestrator điều phối toàn bộ luồng, kiểm tra prompt injection, đo latency.

### 2.2. Tầng Database (`haui_rag.db`)

- `connection.py`: Tạo kết nối PostgreSQL và đăng ký `pgvector`.
- `queries.py`: Thực thi truy vấn chỉ đọc (READ-ONLY) sử dụng index HNSW `halfvec_cosine_ops` và toán tử `<=>`.

### 2.3. Tầng Prompts & Utils

- `prompts/templates.py`: Prompt template chặt chẽ, buộc trích dẫn nguồn `[Mã văn bản] - Điều X, Khoản Y`.
- `utils/helpers.py`: Lọc prompt injection (`is_safe_query`), che giấu PII (`mask_pii`), định dạng trích dẫn (`format_citation`).
- `config.py`: Đọc cấu hình từ `.env`.
- `logger.py`: Xoay vòng file log lưu tại `data/logs/haui_rag.log`.

## 3. Backend & Frontend

- `backend/`: FastAPI REST API exposes endpoint `POST /api/chat` với Pydantic schemas.
- `frontend/`: Streamlit web app hỗ trợ chat tương tác, mở rộng nguồn trích dẫn, câu hỏi gợi ý một chạm.
