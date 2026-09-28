"""Module chứa các hàm tiện ích bảo mật và định dạng nguồn trích dẫn."""

import logging
from typing import Any

logger = logging.getLogger("haui_rag")

DANGEROUS_PATTERNS: list[str] = [
    "ignore previous instructions",
    "ignore all previous",
    "bỏ qua hướng dẫn",
    "bỏ qua tất cả",
    "system prompt",
    "you are now",
    "act as",
    "pretend to be",
    "đóng vai",
    "quên đi",
    "forget everything",
]


def is_safe_query(query: str) -> bool:
    """
    Kiểm tra câu hỏi của người dùng có chứa prompt injection nguy hiểm hay không.

    Args:
        query: Câu hỏi cần kiểm tra.

    Returns:
        True nếu an toàn, False nếu chứa pattern nguy hiểm.
    """
    if not query or not isinstance(query, str):
        return False

    query_lower = query.lower()
    for pattern in DANGEROUS_PATTERNS:
        if pattern in query_lower:
            logger.warning("Phát hiện pattern không an toàn trong query: '%s'", pattern)
            return False
    return True


def format_citation(metadata: dict[str, Any]) -> str:
    """
    Định dạng chuỗi trích dẫn nguồn theo format: [Mã văn bản] - Điều X, Khoản Y.

    Args:
        metadata: Dict metadata của chunk lấy từ database.

    Returns:
        Chuỗi nguồn trích dẫn thân thiện với người dùng.
    """
    if not isinstance(metadata, dict):
        return "Quy chế HaUI"

    ma_van_ban = (metadata.get("ma_van_ban") or "").strip()
    if not ma_van_ban:
        ten_file = metadata.get("ten_file", "").replace(".pdf", "").strip()
        ma_van_ban = ten_file if ten_file else metadata.get("ten_van_ban", "Quy chế HaUI")

    dieu = metadata.get("dieu")
    khoan = metadata.get("khoan")

    citation_parts = [f"[{ma_van_ban}]"]

    clause_parts: list[str] = []
    if dieu:
        clause_parts.append(f"Điều {dieu}")
    if khoan and khoan != "Mở đầu":
        clause_parts.append(f"Khoản {khoan}")

    if clause_parts:
        citation_parts.append(", ".join(clause_parts))

    return " - ".join(citation_parts)
