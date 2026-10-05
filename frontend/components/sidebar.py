"""Component Sidebar điều hướng bên trái kết nối cơ sở dữ liệu PostgreSQL.

Tính năng:
- Tạo cuộc trò chuyện mới (+ Cuộc trò chuyện mới).
- Hiển thị danh sách hội thoại phân nhóm theo 4 mốc thời gian:
  1. HÔM NAY
  2. HÔM QUA
  3. 7 NGÀY TRƯỚC
  4. CŨ HƠN
- Đánh dấu phiên hội thoại đang chọn.
- Xóa cuộc trò chuyện kèm hộp thoại xác nhận hủy bỏ/thực hiện.
"""

from typing import Any
import streamlit as st

from frontend.state.session import (
    create_new_conversation,
    delete_current_conversation,
    format_relative_time,
    group_conversations_by_date,
    switch_conversation,
)
from frontend.styles.theme import get_logo_base64


def render_sidebar() -> None:
    """Hiển thị sidebar điều hướng, quản lý danh sách phiên hội thoại và liên kết điều hướng."""
    with st.sidebar:
        # Biểu trưng và tiêu đề nhà trường
        logo_src = get_logo_base64()
        logo_img = (
            f'<img src="{logo_src}" alt="HaUI Logo" '
            f'style="width: 38px; height: 38px; object-fit: contain; border-radius: 4px;" />'
            if logo_src
            else '<div style="font-weight: 800; color: #1E40AF;">HaUI</div>'
        )
        st.markdown(
            f"""
            <div style="display: flex; align-items: center; gap: 10px; padding: 2px 0 14px 0; border-bottom: 1px solid var(--border-color); margin-bottom: 14px;">
                {logo_img}
                <div>
                    <div style="font-weight: 700; font-size: 0.85rem; color: var(--text-main); line-height: 1.2;">ĐH CÔNG NGHIỆP HÀ NỘI</div>
                    <div style="font-size: 0.72rem; color: var(--text-subtle);">Trợ lý Quy chế Học vụ</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Nút tạo cuộc trò chuyện mới
        if st.button("+ Cuộc trò chuyện mới", use_container_width=True, type="primary"):
            create_new_conversation()
            st.rerun()

        conversations = st.session_state.get("conversations", {})
        active_id = st.session_state.get("active_conv_id", "")

        # Phân loại hội thoại theo 4 mốc thời gian chuẩn
        grouped = group_conversations_by_date(conversations)

        # Thứ tự các nhóm hiển thị
        group_order = ["HÔM NAY", "HÔM QUA", "7 NGÀY TRƯỚC", "CŨ HƠN"]
        has_any_item = False

        for group_name in group_order:
            items = grouped.get(group_name, [])
            if not items:
                continue
            has_any_item = True

            st.markdown(
                f'<div class="sidebar-section-heading">{group_name}</div>',
                unsafe_allow_html=True,
            )

            for conv in items:
                cid = conv.get("id")
                title = conv.get("title") or "Cuộc trò chuyện mới"
                time_lbl = format_relative_time(conv.get("updated_at") or conv.get("created_at"))

                is_active = (cid == active_id) and (st.session_state.view_mode == "chat")
                label = f"{title} ({time_lbl})" if time_lbl else title
                btn_type = "primary" if is_active else "secondary"

                if st.button(label, key=f"s_conv_{cid}", use_container_width=True, type=btn_type):
                    if cid != active_id:
                        switch_conversation(cid)
        if not has_any_item:
            st.markdown(
                '<div style="font-size: 0.8rem; color: var(--text-subtle); '
                'padding: 18px 4px; text-align: center;">'
                'Chưa có cuộc trò chuyện nào'
                '</div>',
                unsafe_allow_html=True,
            )

        st.markdown("<div style='height: 30px;'></div>", unsafe_allow_html=True)

        # Chân trang Sidebar: Cài đặt và Trợ giúp
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            if st.button("Cài đặt", use_container_width=True):
                st.session_state.view_mode = "settings"
                st.rerun()
        with col_c2:
            if st.button("Trợ giúp", use_container_width=True):
                st.session_state.view_mode = "about"
                st.rerun()

        # Khu vực Xóa cuộc trò chuyện kèm xác nhận an toàn
        if st.session_state.view_mode == "chat" and active_id:
            st.markdown("<div style='height: 10px;'></div>", unsafe_allow_html=True)

            if not st.session_state.get("confirm_delete", False):
                if st.button("Xóa cuộc trò chuyện", use_container_width=True):
                    st.session_state.confirm_delete = True
                    st.rerun()
            else:
                st.warning("Xóa cuộc trò chuyện này? Toàn bộ tin nhắn trong cuộc trò chuyện sẽ bị xóa.")
                col_del1, col_del2 = st.columns(2)
                with col_del1:
                    if st.button("Hủy", key="btn_cancel_delete", use_container_width=True):
                        st.session_state.confirm_delete = False
                        st.rerun()
                with col_del2:
                    if st.button(
                        "Xác nhận",
                        key="btn_confirm_delete",
                        type="primary",
                        use_container_width=True,
                    ):
                        delete_current_conversation()
                        st.rerun()
