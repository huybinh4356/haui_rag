"""Component thanh điều hướng trên cùng (Top Navigation Bar) theo chuẩn thiết kế."""

from typing import Any
import streamlit as st

from frontend.state.session import toggle_theme_mode
from frontend.styles.theme import get_logo_base64


def render_topbar(is_online: bool, health_data: dict[str, Any]) -> None:
    """
    Hiển thị thanh tiêu đề tối giản và chỉ báo trạng thái hoạt động của hệ thống kèm nút đổi theme.

    Args:
        is_online: Trạng thái kết nối với Backend API.
        health_data: Dữ liệu phản hồi từ endpoint kiểm tra sức khỏe.
    """
    current_theme = st.session_state.get("theme_mode", "light")
    status_text = "Hệ thống hoạt động tốt" if is_online else "Chế độ trực tiếp"
    logo_src = get_logo_base64()

    col_brand, col_status, col_theme = st.columns([6, 3, 2])

    with col_brand:
        logo_html = (
            f'<img src="{logo_src}" alt="HaUI Logo" style="width: 36px; height: 36px; object-fit: contain; border-radius: 4px;" />'
            if logo_src
            else '<div style="font-weight: 800; color: #1E40AF;">HaUI</div>'
        )
        st.markdown(
            f"""
            <div class="topbar-left">
                <div class="topbar-crest" style="background: transparent; border: none; padding: 0;">
                    {logo_html}
                </div>
                <div>
                    <h1 class="topbar-brand-title">TRỢ LÝ QUY CHẾ <span>HAUI</span></h1>
                    <div class="topbar-brand-sub">Hệ thống tra cứu quy chế và văn bản học vụ nhà trường</div>
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
