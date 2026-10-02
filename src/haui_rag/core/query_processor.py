"""Module xử lý và phân tích ngữ nghĩa câu hỏi người dùng (Query Understanding)."""

import logging
import re
from typing import Any
from haui_rag.config import LLM_MODEL  # noqa: F401 - giữ sẵn cho expand_query với LLM trong tương lai

logger = logging.getLogger("haui_rag")


def classify_query(query: str) -> str:
    """
    Phân loại câu hỏi thành các nhóm: factual, procedural, comparative, out_of_scope.

    Args:
        query: Câu hỏi của người dùng.

    Returns:
        str: Một trong các giá trị 'factual', 'procedural', 'comparative', 'out_of_scope'.
    """
    q_lower = query.lower().strip()

    # Rule-based heuristics nhanh trước khi gọi LLM
    if any(k in q_lower for k in ["thủ tục", "quy trình", "các bước", "làm thế nào", "hồ sơ gồm", "xin nghỉ"]):
        return "procedural"
    if any(k in q_lower for k in ["so sánh", "khác nhau", "giống nhau", "phân biệt", "hơn kém"]):
        return "comparative"
    if any(k in q_lower for k in ["vé máy bay", "thời tiết", "visa", "nấu ăn", "phim", "bóng đá", "lái xe b2"]):
        return "out_of_scope"

    # Nhận diện câu hỏi sự thật, điều kiện, thời gian
    if any(k in q_lower for k in ["bao lâu", "bao nhiêu", "điều kiện", "chuẩn", "khi nào", "là gì", "được không"]):
        return "factual"

    return "factual"


SYNONYM_MAP = {
    "tốt nghiệp": ["công nhận tốt nghiệp", "xét tốt nghiệp"],
    "thạc sĩ": ["cao học", "trình độ thạc sĩ"],
    "tiến sĩ": ["nghiên cứu sinh", "trình độ tiến sĩ"],
    "bảo lưu": ["nghỉ học tạm thời", "tạm ngừng học tập"],
    "học phí": ["mức thu học phí", "kinh phí đào tạo"],
    "luận văn": ["đề án tốt nghiệp", "luận văn thạc sĩ"],
    "cảnh báo": ["cảnh báo học tập", "buộc thôi học"],
}


def expand_query(query: str) -> list[str]:
    """
    Mở rộng câu hỏi thành các biến thể ngữ nghĩa khác nhau để tối đa hóa
    khả năng tìm thấy tài liệu liên quan trong vector & keyword search.
    Sử dụng từ điển chuyên ngành kết hợp fallback thông minh, tiết kiệm quota API.

    Args:
        query: Câu hỏi gốc.

    Returns:
        list[str]: Danh sách gồm câu hỏi gốc và các biến thể sinh ra (tổng 2-3 câu).
    """
    clean_q = query.strip()
    q_lower = clean_q.lower()
    results = [clean_q]

    # Mở rộng qua từ điển đồng nghĩa quy chế HaUI
    for key, synonyms in SYNONYM_MAP.items():
        if key in q_lower:
            for syn in synonyms:
                if syn not in q_lower:
                    expanded = q_lower.replace(key, syn)
                    if expanded not in results:
                        results.append(expanded)
            if len(results) >= 3:
                break

    return results[:3]


def extract_entities(query: str) -> dict[str, Any]:
    """
    Trích xuất các thực thể hữu ích từ câu hỏi: số điều, số quyết định, bậc đào tạo.

    Args:
        query: Câu hỏi của người dùng.

    Returns:
        dict chứa: ma_van_ban, dieu, khoan, bac_dao_tao.
    """
    entities: dict[str, Any] = {
        "ma_van_ban": None,
        "dieu": None,
        "khoan": None,
        "bac_dao_tao": None,
    }

    q_lower = query.lower()

    # Nhận diện bậc đào tạo
    if "thạc sĩ" in q_lower or "cao học" in q_lower:
        entities["bac_dao_tao"] = "thạc sĩ"
    elif "tiến sĩ" in q_lower or "ncs" in q_lower or "nghiên cứu sinh" in q_lower:
        entities["bac_dao_tao"] = "tiến sĩ"
    elif "đại học" in q_lower or "sinh viên" in q_lower:
        entities["bac_dao_tao"] = "đại học"

    # Nhận diện số điều: "điều 5", "điều 12"
    dieu_match = re.search(r"điều\s+(\d+)", q_lower)
    if dieu_match:
        entities["dieu"] = dieu_match.group(1)

    # Nhận diện số khoản: "khoản 2", "khoản 1"
    khoan_match = re.search(r"khoản\s+(\d+)", q_lower)
    if khoan_match:
        entities["khoan"] = khoan_match.group(1)

    # Nhận diện mã quyết định: "quyết định 41", "quyết định số 630", "41/qđ", "qđ 721"
    qd_match = re.search(r"(?:quyết định(?:\s+số)?\s+|qđ\s+)(\d+)", q_lower)
    if qd_match:
        entities["ma_van_ban"] = qd_match.group(1)
    else:
        qd_match2 = re.search(r"(\d+)(?:/qđ|[_\s]+qđ)", q_lower)
        if qd_match2:
            entities["ma_van_ban"] = qd_match2.group(1)

    return entities
