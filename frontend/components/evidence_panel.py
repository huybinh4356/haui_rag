"""Component Evidence Panel hiển thị các nguồn chứng cứ văn bản HaUI chuẩn thiết kế."""

from typing import Any, Optional
import streamlit as st

from frontend.state.session import set_active_citation

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
    Hiển thị bảng nguồn chứng cứ tài liệu văn bản HaUI đúng chuẩn thiết kế.

    Args:
        sources: Danh sách các tài liệu trích dẫn của câu trả lời gần nhất.
        active_idx: Chỉ số trích dẫn đang được người dùng bấm chọn để xem đối chiếu.
        citation_audit: Dữ liệu thẩm định nguồn tự động từ backend.
    """
    # Nếu chưa có câu hỏi nào, hiển thị danh mục 3 tài liệu quy chế mẫu từ thiết kế
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

    # 1. Chế độ xem chi tiết trích dẫn được chọn
    if active_idx is not None and 0 <= active_idx < len(display_sources):
        src = display_sources[active_idx]
        mvb = src.get("ma_van_ban") or src.get("ten_van_ban") or "Quy chế HaUI"
        tvb = src.get("ten_van_ban") or mvb
        dieu = src.get("dieu") or ""
        khoan = src.get("khoan") or ""
        content = src.get("content") or ""
        doc_type = src.get("doc_type") or ("QĐ" if "QĐ" in mvb else "Quy chế")

        clause_parts = []
        if dieu:
            clause_parts.append(f"Điều {dieu}")
        if khoan and khoan != "Mở đầu":
            clause_parts.append(f"Khoản {khoan}")
        clause_str = " · ".join(clause_parts) if clause_parts else "Toàn văn điều khoản"

        st.markdown(
            f"""
            <div class="evidence-card evidence-card-selected">
                <div class="card-header-line">
                    <span class="num-circle">{active_idx + 1}</span>
                    <span class="card-doc-title">{tvb}</span>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--primary-blue)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;">
                        <polyline points="9 18 15 12 9 6"></polyline>
                    </svg>
                </div>
                <div class="card-tags-row">
                    <span class="pill-tag">{doc_type}</span>
                    <span class="pill-clause">{clause_str}</span>
                </div>
                <div class="card-quote-snippet">
                    "{content.strip()}"
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        if st.button("Xem danh sách tất cả nguồn", key="btn_clear_citation_focus", use_container_width=True):
            set_active_citation(None)
            st.rerun()

        # Thông tin văn bản mở rộng
        with st.expander("Thông tin pháp lý văn bản", expanded=False):
            st.markdown(f"**Mã số văn bản:** `{mvb}`")
            st.markdown(f"**Tên đầy đủ:** {tvb}")
            st.caption("Chức năng tra cứu toàn văn theo chương điều sẽ được kích hoạt ở bản cập nhật tiếp theo.")

        return

    # 2. Chế độ hiển thị danh sách các thẻ chứng cứ
    for idx, src in enumerate(display_sources):
        mvb = src.get("ma_van_ban") or src.get("ten_van_ban") or "Quy chế HaUI"
        tvb = src.get("ten_van_ban") or mvb
        dieu = src.get("dieu") or ""
        khoan = src.get("khoan") or ""
        content = src.get("content") or ""
        doc_type = src.get("doc_type") or ("QĐ" if "QĐ" in mvb else "Quy chế")

        clause_parts = []
        if dieu:
            clause_parts.append(f"Điều {dieu}")
        if khoan and khoan != "Mở đầu":
            clause_parts.append(f"Khoản {khoan}")
        clause_str = " · ".join(clause_parts) if clause_parts else "Toàn văn"

        snippet = content.strip().replace("\n", " ")
        if len(snippet) > 140:
            snippet = snippet[:140] + "..."

        st.markdown(
            f"""
            <div class="evidence-card">
                <div class="card-header-line">
                    <span class="num-circle">{idx + 1}</span>
                    <span class="card-doc-title">{tvb}</span>
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--text-subtle)" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" style="flex-shrink:0;">
                        <polyline points="9 18 15 12 9 6"></polyline>
                    </svg>
                </div>
                <div class="card-tags-row">
                    <span class="pill-tag">{doc_type}</span>
                    <span class="pill-clause">{clause_str}</span>
                </div>
                <div class="card-quote-snippet">
                    "{snippet}"
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Cho phép người dùng bấm để đối chiếu chi tiết
        if st.button(f"Xem chi tiết nguồn #{idx + 1}", key=f"btn_src_detail_{idx}", use_container_width=True):
            set_active_citation(idx)
            st.rerun()

    # 3. Banner xanh thông tin ở đáy Evidence Panel
    st.markdown(
        """
        <div class="info-footer-box">
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" style="flex-shrink: 0; margin-top: 2px;">
                <circle cx="12" cy="12" r="10"/>
                <line x1="12" y1="16" x2="12" y2="12"/>
                <line x1="12" y1="8" x2="12.01" y2="8"/>
            </svg>
            <div>
                <div class="info-footer-title">
                    Bạn đang xem nguồn tham khảo từ kho tài liệu chính thức của HaUI.
                </div>
                <div class="info-footer-sub">
                    Nhấn vào từng nguồn để xem chi tiết hoặc mở toàn văn.
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )
