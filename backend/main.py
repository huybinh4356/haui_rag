from contextlib import asynccontextmanager
import logging
import os
import time
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from backend.api.chat import router as chat_router
from backend.api.conversations import router as conversations_router
from haui_rag.config import (
    ACTIVE_LLM_MODEL,
    BACKEND_HOST,
    BACKEND_PORT,
    DB_NAME,
    EMBEDDING_MODEL,
    LLM_MODEL,
    LLM_PROVIDER,
    validate_config,
)
from haui_rag.db.connection import connect_db
from haui_rag.db.migrator import run_migrations
from haui_rag.logger import setup_logger

logger = setup_logger("haui_rag")

# Kiểm tra cấu hình môi trường trước khi khởi động server
try:
    validate_config()
    logger.info("Cấu hình môi trường hợp lệ.")
except ValueError as e:
    logger.critical("Lỗi cấu hình khởi động: %s. Dừng ứng dụng ngay lập tức.", e)
    raise SystemExit(f"Lỗi cấu hình môi trường: {e}") from e


@asynccontextmanager
async def lifespan(fastapi_app: FastAPI):
    """Quản lý vòng đời khởi động và dừng ứng dụng."""
    try:
        logger.info("Kiểm tra và áp dụng cơ sở dữ liệu migrations cho Application Domain...")
        run_migrations()
        logger.info("Hoàn tất kiểm tra migrations.")
    except Exception as e:
        logger.warning("Không thể tự động áp dụng migrations khi khởi động: %s", e)
    yield


# Khởi tạo ứng dụng FastAPI
app = FastAPI(
    title="haui_rag API",
    description="Hệ thống Trợ lý AI hỗ trợ tra cứu quy chế, quy định và văn bản HaUI",
    version="1.2.0",
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# Cấu hình CORS chặt chẽ: chỉ cho phép các cổng Frontend được ủy quyền
cors_env = os.getenv("CORS_ORIGINS", "")
allowed_origins = [
    "http://localhost:8501",
    "http://127.0.0.1:8501",
    "http://localhost:3000",
    "http://127.0.0.1:3000",
]
if cors_env:
    allowed_origins.extend([orig.strip() for orig in cors_env.split(",") if orig.strip()])

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    """Middleware ghi log thời gian phản hồi cho từng request."""
    start_time = time.perf_counter()
    response = await call_next(request)
    duration_ms = (time.perf_counter() - start_time) * 1000
    logger.info(
        "HTTP %s %s - Status: %d - %.2fms",
        request.method,
        request.url.path,
        response.status_code,
        duration_ms,
    )
    return response


# Đăng ký các router
app.include_router(chat_router)
app.include_router(conversations_router)


@app.get("/", summary="Health Check")
async def health_check() -> JSONResponse:
    """Kiểm tra trạng thái hoạt động của Backend và kết nối PostgreSQL."""
    db_status = "connected"
    doc_count = 0
    conv_count = 0
    try:
        conn = connect_db()
        with conn.cursor() as cur:
            cur.execute("SELECT COUNT(*) FROM documents;")
            doc_count = cur.fetchone()[0]
            cur.execute("SELECT COUNT(*) FROM conversations;")
            conv_count = cur.fetchone()[0]
        conn.close()
    except Exception as e:
        logger.error("Không thể kết nối DB trong health check: %s", e)
        db_status = f"error: {str(e)}"

    return JSONResponse(
        content={
            "project": "haui_rag",
            "status": "online",
            "database": db_status,
            "total_documents": doc_count,
            "total_conversations": conv_count,
            "embedding_model": EMBEDDING_MODEL,
            "llm_provider": LLM_PROVIDER,
            "llm_model": ACTIVE_LLM_MODEL,
        }
    )


if __name__ == "__main__":
    import uvicorn

    logger.info("Đang khởi động haui_rag server tại %s:%d", BACKEND_HOST, BACKEND_PORT)
    uvicorn.run("backend.main:app", host=BACKEND_HOST, port=BACKEND_PORT, reload=True)
