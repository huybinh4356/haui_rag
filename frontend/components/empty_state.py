"""Component trạng thái rỗng (Empty State) sao y bản thiết kế mẫu."""

from typing import Callable, Optional
import streamlit as st

from frontend.styles.theme import get_logo_base64

SUGGESTIONS = [
    "Điều kiện để được xét tốt nghiệp là gì?",
    "Quy định về bảo lưu kết quả học tập?",
    "Thời gian đào tạo chương trình thạc sĩ?",
    "Cách tính học phí theo quy định?",
]


def render_empty_state(on_submit: Optional[Callable[[str], None]] = None) -> None:
    """
    Hiển thị trạng thái mở đầu trang trọng theo thiết kế mẫu kèm logo trường HaUI.

    Args:
        on_submit: Hàm callback khi người dùng nhập câu hỏi hoặc chọn gợi ý.
    """
    logo_src = get_logo_base64()
    logo_elem = (
        f'<img src="{logo_src}" alt="HaUI Logo" style="width: 80px; height: 80px; object-fit: contain; margin-bottom: 14px; border-radius: 8px; box-shadow: 0 4px 12px rgba(0,0,0,0.06);" />'
        if logo_src
        else ""
    )

    # 1. Khối minh họa học thuật ở trung tâm với Logo HaUI chính thức
    st.markdown(
        f"""
        <div class="empty-state-wrapper">
            <div style="display: flex; justify-content: center; align-items: center;">
                {logo_elem}
            </div>
            <h2 class="empty-headline">Bạn đang cần tra cứu điều gì?</h2>
            <div class="empty-subheadline">
                Hỏi về quy chế đào tạo, tốt nghiệp, học phí, tuyển sinh và các văn bản chính thức<br/>
                của Trường Đại học Công nghiệp Hà Nội.
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # 2. Ô tìm kiếm trung tâm lớn
    search_col1, search_col2 = st.columns([11, 1.2])
    with search_col1:
        query_val = st.text_input(
            "Nhập câu hỏi tra cứu quy chế:",
            placeholder="Nhập câu hỏi của bạn về quy chế, quy định HaUI...",
            label_visibility="collapsed",
            key="center_search_input",
        )
    with search_col2:
        send_clicked = st.button("Gửi", key="btn_center_send", type="primary", use_container_width=True)

    st.markdown(
        """
        <div style="text-align: right; font-size: 0.76rem; color: var(--text-subtle); margin-top: -6px; margin-bottom: 24px;">
            Enter gửi &bull; Shift + Enter xuống dòng
        </div>
        """,
        unsafe_allow_html=True,
    )

    if (send_clicked or query_val) and query_val.strip() and on_submit:
        on_submit(query_val.strip())

    # 3. Tiêu đề "Gợi ý câu hỏi"
    st.markdown('<div class="suggestion-title">Gợi ý câu hỏi</div>', unsafe_allow_html=True)

    # 4. Lưới 2x2 các thẻ gợi ý câu hỏi
    col1, col2 = st.columns(2)
    with col1:
        if st.button(SUGGESTIONS[0], key="sug_0", use_container_width=True):
            st.session_state.pending_question = SUGGESTIONS[0]
            st.rerun()
        if st.button(SUGGESTIONS[2], key="sug_2", use_container_width=True):
            st.session_state.pending_question = SUGGESTIONS[2]
            st.rerun()

    with col2:
        if st.button(SUGGESTIONS[1], key="sug_1", use_container_width=True):
            st.session_state.pending_question = SUGGESTIONS[1]
            st.rerun()
        if st.button(SUGGESTIONS[3], key="sug_3", use_container_width=True):
            st.session_state.pending_question = SUGGESTIONS[3]
            st.rerun()

    # 5. Hình minh họa tòa nhà HaUI watermark mờ ở đáy màn hình
    st.markdown(
        """
        <div class="watermark-container">
            <svg width="100%" height="100%" viewBox="0 0 500 120" fill="none" preserveAspectRatio="xMidYMax meet">
                <rect x="180" y="40" width="140" height="75" fill="#3B82F6"/>
                <polygon points="170,40 250,15 330,40" fill="#2563EB"/>
                <text x="250" y="34" font-size="12" font-weight="bold" fill="#FFFFFF" text-anchor="middle">HaUI</text>
                <rect x="235" y="80" width="30" height="35" fill="#FFFFFF"/>
                <line x1="195" y1="55" x2="195" y2="75" stroke="#FFFFFF" stroke-width="6"/>
                <line x1="215" y1="55" x2="215" y2="75" stroke="#FFFFFF" stroke-width="6"/>
                <line x1="285" y1="55" x2="285" y2="75" stroke="#FFFFFF" stroke-width="6"/>
                <line x1="305" y1="55" x2="305" y2="75" stroke="#FFFFFF" stroke-width="6"/>
                <rect x="80" y="60" width="100" height="55" fill="#60A5FA"/>
                <rect x="320" y="60" width="100" height="55" fill="#60A5FA"/>
            </svg>
        </div>
        """,
        unsafe_allow_html=True,
    )
