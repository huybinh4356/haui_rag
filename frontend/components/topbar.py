"""Component thanh điều hướng trên cùng (Top Navigation Bar) theo chuẩn thiết kế."""

from typing import Any
import streamlit as st

from frontend.state.session import toggle_theme_mode


def render_topbar(is_online: bool, health_data: dict[str, Any]) -> None:
    """
    Hiển thị thanh tiêu đề tối giản và chỉ báo trạng thái hoạt động của hệ thống kèm nút đổi theme.

    Args:
        is_online: Trạng thái kết nối với Backend API.
        health_data: Dữ liệu phản hồi từ endpoint kiểm tra sức khỏe.
    """
    current_theme = st.session_state.get("theme_mode", "light")
    status_text = "Hệ thống hoạt động tốt" if is_online else "Chế độ trực tiếp"

    col_brand, col_status, col_theme = st.columns([6, 3, 2])

    with col_brand:
        st.markdown(
            """
            <div class="topbar-left">
                <div class="topbar-crest">
                    <svg width="24" height="24" viewBox="0 0 24 24" fill="none" stroke="#FACC15" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M12 2L3 7v6c0 5.55 3.84 10.74 9 12 5.16-1.26 9-6.45 9-12V7l-9-5z"/>
                        <path d="M12 11l4 2-4 2-4-2 4-2z"/>
                    </svg>
                </div>
                <div>
                    <h1 class="topbar-brand-title">HAUI <span>Regulation Assistant</span></h1>
                    <div class="topbar-brand-sub">Trợ lý quy chế và văn bản học vụ HaUI</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_status:
        st.markdown(
            f"""
            <div style="display: flex; justify-content: flex-end; align-items: center; height: 100%;">
                <span class="status-badge-good">
                    <span class="status-badge-dot"></span>
                    {status_text}
                </span>
            </div>
            """,
            unsafe_allow_html=True,
        )

    with col_theme:
        theme_label = "Giao diện: Tối" if current_theme == "light" else "Giao diện: Sáng"
        if st.button(theme_label, key="btn_toggle_theme", use_container_width=True):
            toggle_theme_mode()
            st.rerun()
