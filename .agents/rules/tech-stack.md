---
trigger: always_on
---

# Tech Stack

## Ngôn ngữ & Runtime

- **Python:** 3.11.9 (bắt buộc, không dùng 3.13 vì xung đột thư viện)
- **Virtual environment:** `venv` (không dùng conda)
- **Package manager:** `pip`

## Database

- **PostgreSQL:** 18
- **pgvector:** 0.8.2
- **Index:** HNSW với `halfvec` (hỗ trợ tối đa 4000 chiều)
- **Kích thước vector:** 3072 chiều (Gemini gemini-embedding-001)
- **Driver:** `psycopg2-binary`

## AI & LLM

- **SDK:** `google-genai` (KHÔNG dùng `google-generativeai` đã deprecated)
- **Model Embedding:** `gemini-embedding-001`
- **Model LLM:** `gemini-2.0-flash`
- **Framework:** LangChain (cho agent routing - giai đoạn sau)

## Backend

- **Framework:** FastAPI 0.100+
- **Server:** uvicorn
- **Validation:** Pydantic v2

## Frontend

- **Framework:** Streamlit 1.30+
- **HTTP Client:** `requests`

## Thư viện bổ trợ

- **Xử lý số:** `numpy` 1.26.4 (không dùng 2.x)
- **Biến môi trường:** `python-dotenv`
- **Kiểm thử:** `pytest`

## Cấm sử dụng

- `google-generativeai` (deprecated)
- `PaddleOCR` / `paddlepaddle` (lỗi oneDNN trên Windows)
- `pdf2image` + Poppler (khó cài trên Windows)
- `ChromaDB` (đã thay bằng PostgreSQL + pgvector)
- `numpy` 2.x (xung đột với nhiều thư viện)