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

# Cấu hình LLM Provider: "ollama" (mặc định cục bộ - Qwen 3.5 4B) hoặc "gemini" (cloud)
LLM_PROVIDER: str = os.getenv("LLM_PROVIDER", "ollama").lower()
OLLAMA_BASE_URL: str = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
LOCAL_LLM_MODEL: str = os.getenv("LOCAL_LLM_MODEL", "qwen3.5:4b")
OLLAMA_TIMEOUT_SECONDS: int = int(os.getenv("OLLAMA_TIMEOUT_SECONDS", "180"))

# Cấu hình tối ưu VRAM cho card RTX 3050 (4GB): Giới hạn mức chạy 3.0 - 3.5 GB VRAM
# num_ctx=3072 tokens giới hạn KV cache trong khoảng 500-600MB + 2.6GB model weights = ~3.1-3.2GB VRAM
OLLAMA_NUM_CTX: int = int(os.getenv("OLLAMA_NUM_CTX", "3072"))
OLLAMA_NUM_PREDICT: int = int(os.getenv("OLLAMA_NUM_PREDICT", "1024"))
OLLAMA_NUM_GPU: int = int(os.getenv("OLLAMA_NUM_GPU", "999"))

# Cấu hình Google Gemini AI
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
EMBEDDING_MODEL: str = os.getenv("EMBEDDING_MODEL", "gemini-embedding-001")
LLM_MODEL: str = os.getenv("LLM_MODEL", "gemini-3.6-flash")
FALLBACK_LLM_MODEL: str = os.getenv("FALLBACK_LLM_MODEL", "gemini-3.1-flash-lite")
ACTIVE_LLM_MODEL: str = LOCAL_LLM_MODEL if LLM_PROVIDER == "ollama" else LLM_MODEL
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
