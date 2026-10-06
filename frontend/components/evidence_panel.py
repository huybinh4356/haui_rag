"""Component Evidence Panel hiển thị các nguồn chứng cứ văn bản HaUI chuẩn thiết kế."""

from typing import Any, Optional
import streamlit as st

# Dữ liệu nguồn mẫu hiển thị khi ở trạng thái mở đầu
DEFAULT_PRESET_SOURCES = [
    {
        "chunk_id": 1,
        "ma_van_ban": "QĐ 630/QĐ-ĐHCN",
        "ten_van_ban": "Quyết định 630/QĐ-ĐHCN",
        "doc_type": "QĐ",
        "dieu": "7",
        "khoan": "2",
        "content": "...Sinh viên phải hoàn thành đầy đủ các học phần bắt buộc và đáp ứng các điều kiện tốt nghiệp theo quy định hiện hành...",
    },
    {
        "chunk_id": 2,
        "ma_van_ban": "Quy chế đào tạo đại học",
        "ten_van_ban": "Quy chế đào tạo đại học",
        "doc_type": "Quy chế",
        "dieu": "12",
        "khoan": "1",
        "content": "...Thời gian đào tạo được tính theo chương trình đào tạo và được quy định cụ thể trong từng ngành...",
    },
    {
        "chunk_id": 3,
        "ma_van_ban": "Thông tư 15/2019/TT-BGDĐT",
        "ten_van_ban": "Thông tư 15/2019/TT-BGDĐT",
        "doc_type": "Thông tư",
        "dieu": "5",
        "khoan": "",
        "content": "...Quy định về việc công nhận kết quả học tập, chuyển đổi tín chỉ và bảo lưu kết quả học tập...",
    },
]


def render_evidence_panel(
    sources: list[dict[str, Any]],
    active_idx: Optional[int] = None,
    citation_audit: Optional[dict[str, Any]] = None,
) -> None:
    """
    Hiển thị bảng nguồn chứng cứ tài liệu văn bản HaUI bám theo màn hình khi cuộn.

    Args:
        sources: Danh sách các tài liệu trích dẫn của câu trả lời gần nhất.
        active_idx: Không còn sử dụng (giữ để tương thích tham số gọi hàm).
        citation_audit: Dữ liệu thẩm định nguồn tự động từ backend.
    """
    display_sources = sources if sources else DEFAULT_PRESET_SOURCES
    count_label = f"{len(display_sources)} tài liệu được sử dụng"

    st.markdown(
        f"""
        <div>
            <div class="evidence-header-row">
                <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                    <path d="M2 3h6a4 4 0 0 1 4 4v14a3 3 0 0 0-3-3H2z"/>
                    <path d="M22 3h-6a4 4 0 0 0-4 4v14a3 3 0 0 1 3-3h7z"/>
                </svg>
                <span>Nguồn tham khảo</span>
            </div>
            <div class="evidence-count-sub">{count_label}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Hiển thị toàn bộ danh sách các thẻ chứng cứ trực quan, không cần nút bấm chuyển đổi
    for idx, src in enumerate(display_sources):
        mvb = src.get("ma_van_ban") or src.get("ten_van_ban") or "Quy chế HaUI"
        tvb = src.get("ten_van_ban") or mvb
        dieu = src.get("dieu") or ""
        khoan = src.get("khoan") or ""
        content = (src.get("content") or "").strip()
        doc_type = src.get("doc_type") or ("QĐ" if "QĐ" in mvb else "Quy chế")

        clause_parts = []
        if dieu:
            clause_parts.append(f"Điều {dieu}")
        if khoan and khoan != "Mở đầu":
            clause_parts.append(f"Khoản {khoan}")
        clause_str = " · ".join(clause_parts) if clause_parts else "Toàn văn"

        clean_snippet = content.replace("\n", " ")
        if len(clean_snippet) > 160:
            snippet = clean_snippet[:160] + "..."
            details_html = f"""
            <details class="evidence-details">
                <summary>Toàn văn trích đoạn</summary>
                <div class="evidence-full-text">{content}</div>
            </details>
            """
        else:
            snippet = clean_snippet
            details_html = ""

        st.markdown(
            f"""
            <div class="evidence-card">
                <div class="card-header-line">
                    <span class="num-circle">{idx + 1}</span>
                    <span class="card-doc-title">{tvb}</span>
                </div>
                <div class="card-tags-row">
                    <span class="pill-tag">{doc_type}</span>
                    <span class="pill-clause">{clause_str}</span>
                </div>
                <div class="card-quote-snippet">
                    "{snippet}"
                </div>
                {details_html}
            </div>
            """,
            unsafe_allow_html=True,
        )

    # Khung thông báo hỗ trợ ở đáy bảng
    st.markdown(
        """
        <div class="info-footer-box">
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="flex-shrink: 0; margin-top: 2px;">
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="16" x2="12" y2="12"/>
                <line x1="12" y1="8" x2="12.01" y2="8"/>
            </svg>
            <div>
                <div class="info-footer-title">
                    Cơ sở dữ liệu quy chế chính thức HaUI
                </div>
                <div class="info-footer-sub">
                    Bảng nguồn tự động di chuyển theo mạch hội thoại để tiện đối chiếu.
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
