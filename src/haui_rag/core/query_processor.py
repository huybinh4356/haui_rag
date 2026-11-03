"""Module xử lý và phân tích ngữ nghĩa câu hỏi người dùng (Query Understanding)."""

import logging
import re
from typing import Any
from haui_rag.config import LLM_MODEL  # noqa: F401 - giữ sẵn cho expand_query với LLM trong tương lai

logger = logging.getLogger("haui_rag")


def classify_query(query: str) -> str:
    """
    Phân loại câu hỏi người dùng theo nhóm mục đích truy vấn.

    Args:
        query: Câu hỏi của người dùng.

    Returns:
        Nhãn phân loại gồm procedural, comparative, out_of_scope, hoặc factual.
    """
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


SYNONYM_MAP: dict[str, list[str]] = {
    "công nhận tốt nghiệp": ["nhận tốt nghiệp và cấp bằng", "điều kiện công nhận tốt nghiệp"],
    "tốt nghiệp": ["công nhận tốt nghiệp", "xét tốt nghiệp", "nhận tốt nghiệp"],
    "gia hạn": ["kéo dài thời gian", "thời gian tối đa hoàn thành"],
    "thạc sĩ": ["cao học", "trình độ thạc sĩ"],
    "cao học": ["thạc sĩ", "trình độ thạc sĩ"],
    "tiến sĩ": ["nghiên cứu sinh", "trình độ tiến sĩ"],
    "bảo lưu": ["nghỉ học tạm thời", "bảo lưu kết quả học tập"],
    "nghỉ học tạm thời": ["nghỉ học tam thời", "bảo lưu kết quả"],
    "học phí": ["mức thu học phí", "kinh phí đào tạo"],
    "giao đề tài": ["đề tài luận văn và người hướng dẫn", "đề tài luận văn"],
    "hội đồng đánh giá luận văn": ["hội đồng đánh giá luận văn có năm thành viên", "hội đánh luận văn"],
    "luận văn": ["đề án tốt nghiệp", "bảo vệ luận văn"],
    "cảnh báo": ["cảnh báo học tập", "buộc thôi học"],
    "khen thưởng": ["học bổng khuyến khích học tập", "xét cấp học bổng"],
    "nhiệm vụ": ["nghĩa vụ", "bổn phận"],
    "trách nhiệm": ["nghĩa vụ", "bổn phận"],
    "nghĩa vụ": ["trách nhiệm", "bổn phận"],
    "sinh viên": ["người học", "người học đại học"],
    "người học": ["sinh viên", "người học đại học"],
    "quyền lợi": ["quyền của sinh viên", "chế độ của sinh viên"],
    "quy định": ["quy chế", "nội quy"],
    "học tập": ["quá trình học tập", "hoạt động học tập"],
}

# Ánh xạ khái niệm mở rộng và biến thể OCR thực tế trong DB để tăng độ phủ keyword search
CONCEPT_PHRASE_MAP: list[tuple[tuple[str, ...], list[str]]] = [
    (
        ("tốt nghiệp",),
        [
            "công nhận tốt nghiệp",
            "nhận tốt nghiệp",
            "tốtnghiệp",
            "điều kiện để học viên được",
            "cấp bằng thạc sĩ",
            "bảo vệ luận văn",
            "nộp luận văn",
        ],
    ),
    (
        ("gia hạn", "kéo dài"),
        [
            "kéo dài thời gian",
            "thời gian tối đa hoàn thành",
            "không quá 02 năm",
            "không quá 12 tháng",
            "thời gian đào tạo",
        ],
    ),
    (
        ("bảo lưu", "nghỉ học tạm thời", "tạm thời"),
        [
            "nghỉ học tạm thời",
            "nghỉ học tam thời",
            "bảo lưu kết quả",
            "được phép nghỉ học",
        ],
    ),
    (
        ("hội đồng", "thành viên"),
        [
            "hội đồng đánh giá luận văn",
            "hội đánh luận văn",
            "năm thành viên",
            "03 thành viên",
            "05 thành viên",
            "chủ tịch",
            "phản biện",
        ],
    ),
    (
        ("giao đề tài", "hướng dẫn luận văn", "đề tài luận văn"),
        [
            "đề tài luận văn",
            "đềtài juận văn",
            "người hướng dẫn",
            "tập thể hướng dẫn",
            "giao đề tài",
        ],
    ),
    (
        ("bảo vệ luận văn", "đánh giá luận văn"),
        [
            "điều kiện bảo vệ luận văn",
            "bảo vệ luận văn",
            "đánh giá luận văn",
            "bảo vệ đề án",
        ],
    ),
    (
        ("cảnh báo", "thôi học"),
        [
            "cảnh báo học tập",
            "buộc thôi học",
            "điểm trung bình",
        ],
    ),
    (
        ("khen thưởng", "học bổng"),
        [
            "học bổng khuyến khích học tập",
            "xét cấp học bổng",
            "khen thưởng",
        ],
    ),
    (
        ("ngoại ngữ", "chuẩn đầu ra"),
        [
            "chuẩn đầu ra ngoại ngữ",
            "chứng chỉ ngoại ngữ",
            "bậc 3/6",
            "bậc 4/6",
            "năng lực ngoại ngữ",
        ],
    ),
    (
        ("chuyển trường", "chuyển cơ sở", "chuyển ngành"),
        [
            "chuyển cơ sở đào tạo",
            "chuyển ngành đào tạo",
            "chuyển nơi học",
        ],
    ),
    (
        ("nhiệm vụ", "trách nhiệm", "nghĩa vụ", "bổn phận", "cần làm", "phải làm"),
        [
            "trách nhiệm và quyền hạn của sinh viên",
            "nhiệm vụ và của học viên",
            "nhiệm vụ và quyền của học viên",
            "trách nhiệm và quyền hạn của học viên",
            "sinh viên đủ điều kiện làm đồ",
            "điều kiện để sinh viên được bảo vệ",
            "sinh viên trình bày đa/kltn",
            "sinh viên dùng tiếng việt",
            "sinh viên phải đăng ký",
        ],
    ),
    (
        ("tiêu chuẩn", "giảng viên"),
        [
            "tiêu chuẩn giảng viên",
            "tiêu chuẩn của giảng viên",
            "tiêu chuẩn của giảng víên",
            "tiêu chuẩn của người hướng dẫn",
            "giảng viên đào tạo trình độ",
            "trách nhiệm và quyền hạn của giảng viên",
        ],
    ),
]


def expand_query(query: str) -> list[str]:
    """
    Mở rộng câu hỏi gốc thành danh sách tối đa 3 biến thể đồng nghĩa và ngữ cảnh.

    Args:
        query: Câu hỏi gốc của người dùng.

    Returns:
        Danh sách các chuỗi truy vấn đã mở rộng (tối đa 3 biến thể).
    """
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
        has_rights = "quyền" in q_lower or "quyền lợi" in q_lower

        if has_rights:
            add_variant(f"quyền và nghĩa vụ của {learner_label}")
        elif "trách nhiệm" in q_lower and "nghĩa vụ" not in q_lower:
            responsibility_variant = re.sub(r"trách nhiệm", "nghĩa vụ", clean_q, count=1, flags=re.IGNORECASE)
            add_variant(responsibility_variant)
        elif "nhiệm vụ" in q_lower and "trách nhiệm" not in q_lower:
            duty_variant = re.sub(r"nhiệm vụ", "trách nhiệm", clean_q, count=1, flags=re.IGNORECASE)
            add_variant(duty_variant)
        else:
            add_variant(f"nghĩa vụ của {learner_label}")

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


def extract_search_phrases(query: str) -> list[str]:
    """
    Trích xuất các cụm từ khóa ghép và cụm khái niệm mở rộng (kể cả biến thể lỗi OCR)
    phục vụ tìm kiếm từ khóa theo ngữ cảnh.

    Args:
        query: Câu hỏi hoặc biến thể truy vấn.

    Returns:
        Danh sách các cụm từ khóa quan trọng (chữ thường).
    """
    if not query or not query.strip():
        return []

    q_lower = query.lower().strip()
    phrases: list[str] = []

    def add_phrase(p: str) -> None:
        p_clean = p.strip().lower()
        if p_clean and p_clean not in phrases:
            phrases.append(p_clean)

    for triggers, mapped_phrases in CONCEPT_PHRASE_MAP:
        if any(trigger in q_lower for trigger in triggers):
            for mp in mapped_phrases:
                add_phrase(mp)

    # Bổ sung các cụm danh từ phổ biến nếu xuất hiện trực tiếp trong câu hỏi
    direct_compound_phrases = [
        "công nhận tốt nghiệp",
        "điều kiện tốt nghiệp",
        "cấp bằng thạc sĩ",
        "bảo vệ luận văn",
        "đề án tốt nghiệp",
        "hội đồng đánh giá",
        "nghỉ học tạm thời",
        "bảo lưu kết quả",
        "chuẩn đầu ra",
        "ngoại ngữ",
        "điểm trung bình",
        "tín chỉ",
        "luận án tiến sĩ",
        "học bổng",
        "buộc thôi học",
        "cảnh báo học tập",
    ]
    for cp in direct_compound_phrases:
        if cp in q_lower:
            add_phrase(cp)

    return phrases[:10]


def extract_entities(query: str) -> dict[str, Any]:
    """
    Trích xuất các thực thể quy chế từ câu hỏi (bậc đào tạo, điều, khoản, mã văn bản).

    Args:
        query: Câu hỏi người dùng.

    Returns:
        Dict chứa ma_van_ban, dieu, khoan, bac_dao_tao.
    """
    entities: dict[str, Any] = {
        "ma_van_ban": None,
        "dieu": None,
        "khoan": None,
        "bac_dao_tao": None,
    }

    q_lower = query.lower()

    if "thạc sĩ" in q_lower or "cao học" in q_lower or "học viên" in q_lower:
        entities["bac_dao_tao"] = "thạc sĩ"
    elif "tiến sĩ" in q_lower or "ncs" in q_lower or "nghiên cứu sinh" in q_lower or "luận án" in q_lower:
        entities["bac_dao_tao"] = "tiến sĩ"
    elif "đại học" in q_lower or "sinh viên" in q_lower or "khóa luận" in q_lower:
        entities["bac_dao_tao"] = "đại học"

    dieu_match = re.search(r"điều\s+(\d+)", q_lower)
    if dieu_match:
        entities["dieu"] = dieu_match.group(1)

    khoan_match = re.search(r"khoản\s+(\d+)", q_lower)
    if khoan_match:
        entities["khoan"] = khoan_match.group(1)

    qd_match = re.search(r"(?:quyết định(?:\s+số)?\s+|quy định(?:\s+số)?\s+|qđ\s*)(\d+)", q_lower)
    if qd_match:
        entities["ma_van_ban"] = qd_match.group(1)
    else:
        qd_match2 = re.search(r"(\d+)(?:/qđ|[_\s]+qđ)", q_lower)
        if qd_match2:
            entities["ma_van_ban"] = qd_match2.group(1)

    return entities
