"""Module chứa các hàm tiện ích bảo mật và định dạng nguồn trích dẫn."""

import logging
import re
from typing import Any
import unicodedata

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
    Sử dụng chuẩn hóa Unicode và strip dấu phân tách để chống bypass qua ký tự chèn.

    Args:
        query: Câu hỏi cần kiểm tra.

    Returns:
        True nếu an toàn, False nếu chứa pattern nguy hiểm.
    """
    if not query or not isinstance(query, str):
        return False

    # Chuẩn hóa Unicode NFKC và loại bỏ khoảng trắng/dấu phân tách nhân tạo
    normalized_q = unicodedata.normalize("NFKC", query).lower()
    cleaned_q = re.sub(r"[\s\-_.,*+=/]+", "", normalized_q)

    for pattern in DANGEROUS_PATTERNS:
        clean_pattern = re.sub(r"[\s\-_.,*+=/]+", "", pattern.lower())
        if pattern in normalized_q or clean_pattern in cleaned_q:
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


def verify_citations_against_sources(
    answer: str,
    sources: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Xác thực tính trung thực của các trích dẫn mà LLM sinh ra đối với các chunks lấy từ DB.
    Kiểm tra xem mã văn bản LLM nêu có thực sự nằm trong danh sách ngữ cảnh đã cấp.

    Args:
        answer: Câu trả lời văn bản từ LLM.
        sources: Danh sách các nguồn chunks đã được cung cấp trong ngữ cảnh.

    Returns:
        dict: Kết quả thẩm định gồm {is_grounded, verified_citations, unverified_citations, verification_score}
    """
    if not answer or not sources:
        return {
            "is_grounded": True,
            "verified_citations": [],
            "unverified_citations": [],
            "verification_score": 1.0,
        }

    # Trích xuất các mã văn bản có trong sources
    known_docs: set[str] = set()
    for s in sources:
        mvb = s.get("ma_van_ban") or ""
        if mvb:
            clean_mvb = re.sub(r"[^\w\d]", "", mvb.lower())
            if clean_mvb:
                known_docs.add(clean_mvb)

    # Tìm các pattern trích dẫn dạng [Mã văn bản] trong câu trả lời
    found_citations = re.findall(r"\[([A-Za-z0-9\/\-\.]+)\]", answer)

    verified: list[str] = []
    unverified: list[str] = []

    for doc_code in found_citations:
        clean_code = re.sub(r"[^\w\d]", "", doc_code.lower())
        if not clean_code or clean_code in ("web", "webhaui"):
            continue

        cite_label = f"[{doc_code}]"
        # Kiểm tra xem mã văn bản có nằm trong các chunk DB không
        if any(clean_code in kd or kd in clean_code for kd in known_docs):
            if cite_label not in verified:
                verified.append(cite_label)
        else:
            if cite_label not in unverified:
                unverified.append(cite_label)

    total = len(verified) + len(unverified)
    score = (len(verified) / total) if total > 0 else 1.0

    return {
        "is_grounded": len(unverified) == 0,
        "verified_citations": verified,
        "unverified_citations": unverified,
        "verification_score": round(score, 2),
    }
