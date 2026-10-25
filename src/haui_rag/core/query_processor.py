"""Module xử lý và phân tích ngữ nghĩa câu hỏi người dùng (Query Understanding)."""

import logging
import re
from typing import Any
from haui_rag.config import LLM_MODEL  # noqa: F401 - giữ sẵn cho expand_query với LLM trong tương lai

logger = logging.getLogger("haui_rag")


def classify_query(query: str) -> str:
    q_lower = query.lower().strip()

    if any(k in q_lower for k in ["thủ tục", "quy trình", "các bước", "làm thế nào", "hồ sơ gồm", "xin nghỉ"]):
        return "procedural"
    if any(k in q_lower for k in ["so sánh", "khác nhau", "giống nhau", "phân biệt", "hơn kém"]):
        return "comparative"
    if any(k in q_lower for k in ["vé máy bay", "thời tiết", "visa", "nấu ăn", "phim", "bóng đá", "lái xe b2"]):
        return "out_of_scope"
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
    "nhiệm vụ": ["nghĩa vụ", "bổn phận"],
    "trách nhiệm": ["nghĩa vụ", "bổn phận"],
    "nghĩa vụ": ["trách nhiệm", "bổn phận"],
    "sinh viên": ["người học", "người học đại học"],
    "người học": ["sinh viên", "người học đại học"],
    "quyền lợi": ["quyền của sinh viên", "chế độ của sinh viên"],
    "quy định": ["quy chế", "nội quy"],
    "học tập": ["quá trình học tập", "hoạt động học tập"],
}


def expand_query(query: str) -> list[str]:
    clean_q = query.strip()
    if not clean_q:
        return []

    q_lower = clean_q.lower()
    results: list[str] = []

    def add_variant(value: str) -> None:
        value = value.strip()
        if value and value.casefold() not in {item.casefold() for item in results} and len(results) < 3:
            results.append(value)

    add_variant(clean_q)

    learner_terms = ("sinh viên", "người học", "học viên")
    obligation_terms = ("nhiệm vụ", "trách nhiệm", "nghĩa vụ", "bổn phận")
    has_learner = any(term in q_lower for term in learner_terms)
    has_obligation = any(term in q_lower for term in obligation_terms)

    if has_learner and has_obligation:
        learner_label = "sinh viên" if "sinh viên" in q_lower else "người học"
        add_variant(f"quyền và nghĩa vụ của {learner_label}")

        if "sinh viên" in q_lower:
            learner_variant = re.sub(r"sinh viên", "người học", clean_q, flags=re.IGNORECASE)
        else:
            learner_variant = re.sub(r"(người học|học viên)", "sinh viên", clean_q, count=1, flags=re.IGNORECASE)
        add_variant(learner_variant)

    if len(results) < 3:
        for key, synonyms in SYNONYM_MAP.items():
            if key not in q_lower:
                continue
            for synonym in synonyms:
                if synonym in q_lower:
                    continue
                expanded = re.sub(re.escape(key), synonym, clean_q, flags=re.IGNORECASE)
                add_variant(expanded)
                if len(results) >= 3:
                    break
            if len(results) >= 3:
                break

    return results[:3]


def extract_entities(query: str) -> dict[str, Any]:
    entities: dict[str, Any] = {
        "ma_van_ban": None,
        "dieu": None,
        "khoan": None,
        "bac_dao_tao": None,
    }

    q_lower = query.lower()

    if "thạc sĩ" in q_lower or "cao học" in q_lower:
        entities["bac_dao_tao"] = "thạc sĩ"
    elif "tiến sĩ" in q_lower or "ncs" in q_lower or "nghiên cứu sinh" in q_lower:
        entities["bac_dao_tao"] = "tiến sĩ"
    elif "đại học" in q_lower or "sinh viên" in q_lower:
        entities["bac_dao_tao"] = "đại học"

    dieu_match = re.search(r"điều\s+(\d+)", q_lower)
    if dieu_match:
        entities["dieu"] = dieu_match.group(1)

    khoan_match = re.search(r"khoản\s+(\d+)", q_lower)
    if khoan_match:
        entities["khoan"] = khoan_match.group(1)

    qd_match = re.search(r"(?:quyết định(?:\s+số)?\s+|qđ\s+)(\d+)", q_lower)
    if qd_match:
        entities["ma_van_ban"] = qd_match.group(1)
    else:
        qd_match2 = re.search(r"(\d+)(?:/qđ|[_\s]+qđ)", q_lower)
        if qd_match2:
            entities["ma_van_ban"] = qd_match2.group(1)

    return entities
