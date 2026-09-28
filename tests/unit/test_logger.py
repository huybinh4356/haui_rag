"""Unit tests kiểm tra module logging và lọc PII (logger.py)."""

import logging
from haui_rag.logger import PIIMaskingFormatter, mask_pii, setup_logger


def test_mask_pii():
    """Kiểm tra che giấu PII trong log (số điện thoại, email, CCCD)."""
    assert mask_pii(12345) == 12345
    masked_phone = mask_pii("Liên hệ số 0912345678 để được hỗ trợ")
    assert "***PHONE***" in masked_phone
    assert "0912345678" not in masked_phone

    masked_email = mask_pii("Gửi thư về nguyenvana@haui.edu.vn nhé")
    assert "***EMAIL***" in masked_email
    assert "nguyenvana@haui.edu.vn" not in masked_email

    masked_id = mask_pii("Số CCCD: 001201012345")
    assert "***ID***" in masked_id
    assert "001201012345" not in masked_id


def test_pii_formatter():
    """Kiểm tra formatter tự động lọc PII."""
    formatter = PIIMaskingFormatter("%(message)s")
    record = logging.LogRecord(
        name="test",
        level=logging.INFO,
        pathname="test.py",
        lineno=10,
        msg="Email test: sinhvien@gmail.com",
        args=(),
        exc_info=None,
    )
    formatted = formatter.format(record)
    assert "***EMAIL***" in formatted


def test_setup_logger():
    """Kiểm tra hàm setup_logger tạo logger hợp lệ."""
    log = setup_logger("test_unit_logger")
    assert log is not None
    assert log.name == "test_unit_logger"
    # Gọi lại trả về logger cũ
    log2 = setup_logger("test_unit_logger")
    assert log2 is log
