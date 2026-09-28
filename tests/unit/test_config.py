"""Unit tests kiểm tra module cấu hình config.py."""

from pathlib import Path
from haui_rag.config import (
    BASE_DIR,
    DATA_DIR,
    DB_HOST,
    DB_PORT,
    DB_NAME,
    DB_USER,
    EMBEDDING_MODEL,
    LLM_MODEL,
    validate_config,
)


def test_config_paths():
    """Kiểm tra đường dẫn thư mục gốc và thư mục data."""
    assert BASE_DIR.exists()
    assert DATA_DIR.exists()


def test_config_constants():
    """Kiểm tra các hằng số cấu hình hệ thống."""
    assert DB_HOST == "localhost"
    assert DB_PORT == "5432"
    assert DB_NAME == "rag_haui"
    assert DB_USER == "postgres"
    assert "gemini" in EMBEDDING_MODEL
    assert "gemini" in LLM_MODEL


def test_validate_config():
    """Kiểm tra hàm validate_config không gây lỗi khi đủ biến."""
    validate_config()
