"""Kiểm thử tính sẵn sàng của biến môi trường và file .env."""

import os
from pathlib import Path
from haui_rag.config import BASE_DIR, ENV_PATH, GEMINI_API_KEY, DB_PASSWORD, validate_config


def test_env_file_exists():
    """Kiểm tra file .env có tồn tại trong thư mục gốc không."""
    assert ENV_PATH.exists(), f"File .env không tồn tại tại {ENV_PATH}"


def test_required_environment_variables():
    """Kiểm tra các biến môi trường cốt lõi đã được tải."""
    assert bool(GEMINI_API_KEY), "GEMINI_API_KEY chưa được thiết lập"
    assert bool(DB_PASSWORD), "DB_PASSWORD chưa được thiết lập"


def test_validate_config_success():
    """Kiểm tra hàm validate_config không ném exception khi đủ biến."""
    try:
        validate_config()
    except ValueError as e:
        assert False, f"validate_config thất bại: {e}"