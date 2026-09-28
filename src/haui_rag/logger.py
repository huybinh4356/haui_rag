"""Module cấu hình logging tập trung và che giấu PII cho haui-rag-assistant."""

import logging
import re
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from haui_rag.config import LOG_DIR, LOG_FILE


def mask_pii(text: str) -> str:
    """
    Che giấu thông tin cá nhân nhạy cảm trong log (số điện thoại, email, CCCD).

    Args:
        text: Chuỗi văn bản đầu vào.

    Returns:
        Chuỗi văn bản đã được ẩn thông tin nhạy cảm.
    """
    if not isinstance(text, str):
        return text

    # Che giấu số điện thoại Việt Nam
    text = re.sub(r"\b0\d{9,10}\b", "***PHONE***", text)
    # Che giấu địa chỉ email
    text = re.sub(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b", "***EMAIL***", text)
    # Che giấu số CMND/CCCD
    text = re.sub(r"\b\d{9,12}\b", "***ID***", text)
    return text


class PIIMaskingFormatter(logging.Formatter):
    """Custom Formatter tự động lọc PII trên từng dòng log."""

    def format(self, record: logging.LogRecord) -> str:
        original = super().format(record)
        return mask_pii(original)


def setup_logger(name: str = "haui_rag") -> logging.Logger:
    """
    Khởi tạo và cấu hình logger chuẩn cho dự án.

    Args:
        name: Tên logger (mặc định 'haui_rag').

    Returns:
        Đối tượng Logger hỗ trợ console UTF-8 và rotating file handler trong data/logs/.
    """
    logger = logging.getLogger(name)

    if logger.handlers:
        return logger

    logger.setLevel(logging.INFO)

    log_format = "%(asctime)s - [%(levelname)s] - [%(name)s:%(lineno)d] - %(message)s"
    formatter = PIIMaskingFormatter(log_format)

    # 1. Console Handler hỗ trợ UTF-8
    if hasattr(sys.stdout, "reconfigure"):
        try:
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        except Exception:
            pass

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(formatter)
    console_handler.setLevel(logging.INFO)
    logger.addHandler(console_handler)

    # 2. File Handler (Max 10MB, xoay vòng 5 file) trong data/logs/
    try:
        LOG_DIR.mkdir(parents=True, exist_ok=True)
        file_handler = RotatingFileHandler(
            LOG_FILE,
            maxBytes=10 * 1024 * 1024,
            backupCount=5,
            encoding="utf-8",
        )
        file_handler.setFormatter(formatter)
        file_handler.setLevel(logging.INFO)
        logger.addHandler(file_handler)
    except OSError as e:
        logger.warning("Không thể ghi log ra file %s: %s", LOG_FILE, e)

    return logger
