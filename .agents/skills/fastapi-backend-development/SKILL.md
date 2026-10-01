---
name: fastapi-backend-development
description: Kỹ năng xây dựng API backend với FastAPI. Tạo endpoint, xử lý request/response, tích hợp RAG pipeline, và cấu hình CORS. Dùng khi cần expose API cho frontend.
---

# FastAPI Backend Development

## Khi nào dùng skill này

- Tạo API endpoint cho frontend gọi
- Xử lý request/response
- Tích hợp RAG pipeline vào API
- Cấu hình CORS, middleware, error handling

## Cấu trúc dự án

```text
backend/
├── main.py              # Entry point
├── api/
│   ├── __init__.py
│   ├── chat.py          # Endpoint /chat
│   └── admin.py         # Endpoint admin
├── core/
│   ├── config.py        # Cấu hình
│   └── security.py      # Auth, RBAC
├── models/
│   └── schemas.py       # Pydantic models
├── services/
│   └── rag.py           # RAG service
└── requirements.txt
```

## Code chính

### main.py

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from api import chat, admin

app = FastAPI(
    title="Trợ lý AI HaUI",
    description="API tra cứu quy chế",
    version="1.0.0"
)

# CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:8501"],  # Streamlit
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)

# Routes
app.include_router(chat.router, prefix="/api", tags=["chat"])
app.include_router(admin.router, prefix="/api/admin", tags=["admin"])

@app.get("/")
async def root():
    return {"status": "ok", "message": "Trợ lý AI HaUI đang chạy"}
```

### api/chat.py

```python
import logging
from fastapi import APIRouter, HTTPException
from models.schemas import ChatRequest, ChatResponse
from services.rag import rag_query

router = APIRouter()


@router.post("/chat", response_model=ChatResponse)
async def chat(request: ChatRequest):
    """
    Endpoint chính: nhận câu hỏi, trả câu trả lời + nguồn.
    """
    try:
        # Validate
        if not request.question.strip():
            raise HTTPException(status_code=400, detail="Câu hỏi không được rỗng")
        
        if len(request.question) > 1000:
            raise HTTPException(status_code=400, detail="Câu hỏi quá dài (tối đa 1000 ký tự)")
        
        # Gọi RAG
        result = rag_query(request.question, verbose=False)
        
        # Format response
        sources = [
            {
                "ma_van_ban": c["metadata"].get("ma_van_ban"),
                "ten_van_ban": c["metadata"].get("ten_van_ban"),
                "dieu": c["metadata"].get("dieu"),
                "khoan": c["metadata"].get("khoan"),
                "distance": round(c["distance"], 4),
            }
            for c in result["sources"]
        ]
        
        return ChatResponse(
            answer=result["answer"],
            sources=sources
        )
    
    except HTTPException:
        raise
    except Exception as e:
        logging.error(f"Lỗi xử lý chat: {e}")
        raise HTTPException(status_code=500, detail="Lỗi server nội bộ")
```

### models/schemas.py

```python
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    question: str = Field(..., min_length=1, max_length=1000)
    
    class Config:
        json_schema_extra = {
            "example": {
                "question": "Điều kiện tốt nghiệp thạc sĩ là gì?"
            }
        }


class Source(BaseModel):
    ma_van_ban: str | None = None
    ten_van_ban: str | None = None
    dieu: str | None = None
    khoan: str | None = None
    distance: float | None = None


class ChatResponse(BaseModel):
    answer: str
    sources: list[Source]
    
    class Config:
        json_schema_extra = {
            "example": {
                "answer": "Theo quy định...",
                "sources": [
                    {
                        "ma_van_ban": "41/QĐ-ĐHCN",
                        "dieu": "12",
                        "khoan": "1"
                    }
                ]
            }
        }
```

### core/config.py

```python
import os
from dotenv import load_dotenv

load_dotenv()


class Settings:
    # Gemini
    GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
    
    # Database
    DB_HOST: str = os.getenv("DB_HOST", "localhost")
    DB_PORT: str = os.getenv("DB_PORT", "5432")
    DB_NAME: str = os.getenv("DB_NAME", "rag_haui")
    DB_USER: str = os.getenv("DB_USER", "postgres")
    DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")
    
    # RAG
    TOP_K: int = 5
    LLM_MODEL: str = "gemini-2.0-flash"
    EMBEDDING_MODEL: str = "gemini-embedding-001"
    
    # API
    CORS_ORIGINS: list[str] = ["http://localhost:8501"]


settings = Settings()
```

### Chạy server

```bash
pip install fastapi uvicorn[standard] pydantic
uvicorn main:app --reload --port 8000
```

### Test API

**Với curl:**

```bash
curl -X POST http://localhost:8000/api/chat \
  -H "Content-Type: application/json" \
  -d '{"question": "Điều kiện tốt nghiệp thạc sĩ là gì?"}'
```

**Với Python:**

```python
import requests

response = requests.post(
    "http://localhost:8000/api/chat",
    json={"question": "Điều kiện tốt nghiệp thạc sĩ là gì?"}
)
data = response.json()
print(data["answer"])
```

**Với Swagger UI:**

Mở `http://localhost:8000/docs` để test trực tiếp.

### Middleware

**Logging middleware:**

```python
import time
import logging
from fastapi import Request

@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.time()
    response = await call_next(request)
    duration = time.time() - start
    
    logging.info(
        f"{request.method} {request.url.path} "
        f"- {response.status_code} - {duration:.2f}s"
    )
    return response
```

## Lưu ý quan trọng

### Timeout
- Bắt buộc set timeout dài cho Gemini call.
- Mặc định uvicorn timeout 30s, cần tăng lên:

```bash
uvicorn main:app --timeout-keep-alive 300
```

### CORS
- Phải cấu hình CORS cho frontend.
- Production: chỉ cho phép domain trường.
- Dev: cho phép `http://localhost:*`.

### Error handling
- Phải có try/except cho mọi endpoint.
- Phải log lỗi chi tiết.
- Không trả về stack trace cho client.

### Validation
- Dùng Pydantic để validate input.
- Giới hạn độ dài câu hỏi (1000 ký tự).
- Kiểm tra prompt injection.