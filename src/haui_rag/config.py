"""Module cấu hình ứng dụng và biến môi trường cho haui-rag-assistant."""

import os
from pathlib import Path
from dotenv import load_dotenv

# Xác định đường dẫn thư mục gốc dự án: C:\...\DoAnChuyenNganh (hoặc haui-rag-assistant)
BASE_DIR: Path = Path(__file__).resolve().parent.parent.parent
ENV_PATH: Path = BASE_DIR / ".env"

# Load biến môi trường từ .env
load_dotenv(dotenv_path=ENV_PATH)

# Cấu hình Database PostgreSQL + pgvector
DB_HOST: str = os.getenv("DB_HOST", "localhost")
DB_PORT: str = os.getenv("DB_PORT", "5432")
DB_NAME: str = os.getenv("DB_NAME", "rag_haui")
DB_USER: str = os.getenv("DB_USER", "postgres")
DB_PASSWORD: str = os.getenv("DB_PASSWORD", "")

# Cấu hình Google Gemini AI
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")
LLM_MODEL: str = os.getenv("LLM_MODEL", "gemini-3.5-flash")
FALLBACK_LLM_MODEL: str = os.getenv("FALLBACK_LLM_MODEL", "gemini-3.8-flash")
GEMINI_TIMEOUT_SECONDS: int = 60
MAX_EMBEDDING_RETRIES: int = 3
INITIAL_RETRY_DELAY: float = 1.0

# Cấu hình RAG Pipeline
DEFAULT_TOP_K: int = 5
MAX_TOP_K: int = 10
GENERATION_TEMPERATURE: float = 0.1
EMBEDDING_DIMENSION: int = 3072
USE_LLM_RERANK: bool = os.getenv("USE_LLM_RERANK", "false").lower() == "true"
ENABLE_QUERY_CACHE: bool = os.getenv("ENABLE_QUERY_CACHE", "true").lower() == "true"
QUERY_CACHE_SIZE: int = int(os.getenv("QUERY_CACHE_SIZE", "128"))

# Cấu hình Thư mục dữ liệu, Server & Logs (Lưu trong data/logs/)
DATA_DIR: Path = BASE_DIR / "data"
BACKEND_HOST: str = os.getenv("BACKEND_HOST", "127.0.0.1")
BACKEND_PORT: int = int(os.getenv("BACKEND_PORT", "8000"))
LOG_DIR: Path = DATA_DIR / "logs"
LOG_FILE: Path = LOG_DIR / "haui_rag.log"


def validate_config() -> None:
    """
    Kiểm tra tính hợp lệ của các biến môi trường bắt buộc.

    Raises:
        ValueError: Nếu thiếu GEMINI_API_KEY hoặc DB_PASSWORD.
    """
    if not GEMINI_API_KEY:
        raise ValueError("Chưa thiết lập GEMINI_API_KEY trong file .env")
    if not DB_PASSWORD:
        raise ValueError("Chưa thiết lập DB_PASSWORD trong file .env")
