"""Component Sidebar điều hướng bên trái chuẩn theo thiết kế yêu cầu."""

import streamlit as st

from frontend.state.session import (
    create_new_conversation,
    delete_conversation,
    switch_conversation,
)


def render_sidebar() -> None:
    """Hiển thị sidebar điều hướng, quản lý danh sách phiên hội thoại và liên kết điều hướng."""
    with st.sidebar:
        # Nút tạo cuộc trò chuyện mới
        if st.button("+ Cuộc trò chuyện mới", use_container_width=True, type="primary"):
            create_new_conversation()
            st.rerun()

        conversations = st.session_state.conversations
        active_id = st.session_state.active_conv_id

        # Phân loại nhóm hội thoại
        today_convs = []
        prev_convs = []

        for cid, conv in conversations.items():
            if conv.get("group") == "today":
                today_convs.append((cid, conv))
            else:
                prev_convs.append((cid, conv))

        # 1. Nhóm HÔM NAY
        st.markdown('<div class="sidebar-section-heading">HÔM NAY</div>', unsafe_allow_html=True)
        for cid, conv in today_convs:
            is_active = (cid == active_id) and (st.session_state.view_mode == "chat")
            title = conv.get("title", "Cuộc trò chuyện")
            time_lbl = conv.get("time_label", "Hôm nay")

            # Hiển thị tiêu đề hội thoại và thời gian sạch sẽ, không dùng ký tự >
            label = f"{title} ({time_lbl})"
            btn_type = "primary" if is_active else "secondary"
            if st.button(label, key=f"s_conv_{cid}", use_container_width=True, type=btn_type):
                switch_conversation(cid)
                st.rerun()

        # 2. Nhóm TRƯỚC ĐÓ
        st.markdown('<div class="sidebar-section-heading">TRƯỚC ĐÓ</div>', unsafe_allow_html=True)
        for cid, conv in prev_convs:
            is_active = (cid == active_id) and (st.session_state.view_mode == "chat")
            title = conv.get("title", "Cuộc trò chuyện")
            time_lbl = conv.get("time_label", "Trước đó")

            label = f"{title} ({time_lbl})"
            btn_type = "primary" if is_active else "secondary"
            if st.button(label, key=f"s_conv_{cid}", use_container_width=True, type=btn_type):
                switch_conversation(cid)
                st.rerun()

        st.markdown("<div style='height: 40px;'></div>", unsafe_allow_html=True)

        # 3. Chân trang Sidebar: Cài đặt và Trợ giúp
        col_c1, col_c2 = st.columns(2)
        with col_c1:
            if st.button("Cài đặt", use_container_width=True):
                st.session_state.view_mode = "settings"
                st.rerun()
        with col_c2:
            if st.button("Trợ giúp", use_container_width=True):
                st.session_state.view_mode = "about"
                st.rerun()

        if st.session_state.view_mode == "chat" and len(conversations) > 1:
            if st.button("Xóa cuộc trò chuyện này", use_container_width=True):
                delete_conversation(active_id)
                st.rerun()
