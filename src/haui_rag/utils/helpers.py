"""Module chứa các hàm tiện ích bảo mật và định dạng nguồn trích dẫn."""

import logging
import re
from typing import Any
import unicodedata

logger = logging.getLogger("haui_rag")

# Danh mục ánh xạ tên file PDF trong DB sang metadata chuẩn hóa (READ-ONLY enrichment)
DOCUMENT_CATALOG: list[tuple[str, dict[str, str]]] = [
    (
        "quyết định 41",
        {
            "ma_van_ban": "41/QĐ-ĐHCN",
            "ten_van_ban": "Quy chế tuyển sinh và đào tạo trình độ thạc sĩ (QĐ 41)",
            "bac_dao_tao": "thạc sĩ",
        },
    ),
    (
        "quy định 630",
        {
            "ma_van_ban": "630/QĐ-ĐHCN",
            "ten_van_ban": "Quy định đào tạo trình độ thạc sĩ (QĐ 630)",
            "bac_dao_tao": "thạc sĩ",
        },
    ),
    (
        "qđ 139",
        {
            "ma_van_ban": "139/QĐ-ĐHCN",
            "ten_van_ban": "Quy định công tác quản lý lớp học trình độ thạc sĩ (QĐ 139)",
            "bac_dao_tao": "thạc sĩ",
        },
    ),
    (
        "qđ154",
        {
            "ma_van_ban": "154/QĐ-ĐHCN",
            "ten_van_ban": "Quy định tổ chức đánh giá học phần sau đại học (QĐ 154)",
            "bac_dao_tao": "thạc sĩ, tiến sĩ",
        },
    ),
    (
        "qđ508",
        {
            "ma_van_ban": "508/QĐ-ĐHCN",
            "ten_van_ban": "Quy định mở ngành đào tạo trình độ thạc sĩ và tiến sĩ (QĐ 508)",
            "bac_dao_tao": "thạc sĩ, tiến sĩ",
        },
    ),
    (
        "quyet-dinh-721",
        {
            "ma_van_ban": "721/QĐ-ĐHCN",
            "ten_van_ban": "Quy định tổ chức đánh giá kết quả học tập của người học (QĐ 721)",
            "bac_dao_tao": "chung",
        },
    ),
    (
        "qd dao tao tien si",
        {
            "ma_van_ban": "QĐ-ĐTTS-2018",
            "ten_van_ban": "Quy định đào tạo trình độ tiến sĩ",
            "bac_dao_tao": "tiến sĩ",
        },
    ),
    (
        "1202",
        {
            "ma_van_ban": "1202/QĐ-ĐHCN",
            "ten_van_ban": "Quy chế tuyển sinh và đào tạo trình độ tiến sĩ (QĐ 1202)",
            "bac_dao_tao": "tiến sĩ",
        },
    ),
    (
        "sửa đổi bổ sung quy chế đào tạo trình độ tiến sĩ",
        {
            "ma_van_ban": "1202/QĐ-ĐHCN",
            "ten_van_ban": "Quyết định sửa đổi bổ sung Quy chế đào tạo trình độ tiến sĩ",
            "bac_dao_tao": "tiến sĩ",
        },
    ),
    (
        "943.pdf",
        {
            "ma_van_ban": "943/QĐ-ĐHCN",
            "ten_van_ban": "Quy định xét cấp học bổng khuyến khích học tập cao học và NCS (QĐ 943)",
            "bac_dao_tao": "thạc sĩ, tiến sĩ",
        },
    ),
    (
        "29675",
        {
            "ma_van_ban": "QĐ-CĐRNN",
            "ten_van_ban": "Quy định chuẩn đầu ra ngoại ngữ tại ĐHCN",
            "bac_dao_tao": "chung",
        },
    ),
    (
        "29811",
        {
            "ma_van_ban": "744/QĐ-ĐHCN",
            "ten_van_ban": "Quy định đào tạo trình độ đại học theo hệ thống tín chỉ",
            "bac_dao_tao": "đại học",
        },
    ),
    (
        "29868",
        {
            "ma_van_ban": "QĐ-ĐATN",
            "ten_van_ban": "Quy định thực hiện đồ án, khóa luận tốt nghiệp đại học",
            "bac_dao_tao": "đại học",
        },
    ),
]


def enrich_chunk_metadata(metadata: dict[str, Any] | None) -> dict[str, Any]:
    """
    Làm giàu metadata của chunk dựa trên tên file PDF trong DB mà không cần sửa DB.

    Args:
        metadata: Dict metadata gốc từ bảng documents.

    Returns:
        Dict metadata đã được bổ sung ma_van_ban, ten_van_ban và bac_dao_tao.
    """
    if not isinstance(metadata, dict):
        return {}

    enriched = dict(metadata)
    ten_file = str(enriched.get("ten_file") or "").strip().lower()
    if not ten_file:
        return enriched

    for pattern, info in DOCUMENT_CATALOG:
        if pattern in ten_file:
            if not (enriched.get("ma_van_ban") or "").strip():
                enriched["ma_van_ban"] = info["ma_van_ban"]
            if not (enriched.get("ten_van_ban") or "").strip():
                enriched["ten_van_ban"] = info["ten_van_ban"]
            if not (enriched.get("bac_dao_tao") or "").strip():
                enriched["bac_dao_tao"] = info["bac_dao_tao"]
            break

    return enriched


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

    enriched = enrich_chunk_metadata(metadata)
    ma_van_ban = (enriched.get("ma_van_ban") or "").strip()
    if not ma_van_ban:
        ten_file = str(enriched.get("ten_file") or "").replace(".pdf", "").strip()
        ma_van_ban = ten_file if ten_file else str(enriched.get("ten_van_ban") or "Quy chế HaUI")

    dieu = enriched.get("dieu")
    khoan = enriched.get("khoan")

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
    Kiểm tra xem mã văn bản hoặc tên văn bản LLM nêu có thực sự nằm trong ngữ cảnh đã cấp.

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

    known_docs: set[str] = set()
    for s in sources:
        meta = enrich_chunk_metadata(s.get("metadata") if isinstance(s.get("metadata"), dict) else s)
        candidates = [
            s.get("ma_van_ban"),
            s.get("ten_van_ban"),
            s.get("citation"),
            meta.get("ma_van_ban"),
            meta.get("ten_van_ban"),
            str(meta.get("ten_file") or "").replace(".pdf", ""),
        ]
        for candidate in candidates:
            if candidate:
                clean_cand = re.sub(r"[^\w\d]", "", str(candidate).lower())
                if clean_cand:
                    known_docs.add(clean_cand)

    found_citations = re.findall(r"\[([^\[\]\n]{2,90})\]", answer)

    verified: list[str] = []
    unverified: list[str] = []

    for doc_code in found_citations:
        raw_lower = doc_code.strip().lower()
        if raw_lower.startswith("đoạn ") or raw_lower in ("mã văn bản", "web", "web haui"):
            continue
        clean_code = re.sub(r"[^\w\d]", "", raw_lower)
        if not clean_code or clean_code in ("web", "webhaui"):
            continue

        cite_label = f"[{doc_code.strip()}]"
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
