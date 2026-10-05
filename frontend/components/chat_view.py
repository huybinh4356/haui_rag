"""Component hiển thị dòng hội thoại, định dạng Markdown học thuật và trích dẫn tương tác."""

import re
from typing import Any
import streamlit as st

from frontend.components.feedback import render_feedback_section
from frontend.state.session import set_active_citation
from frontend.styles.theme import get_logo_base64


def render_chat_history(messages: list[dict[str, Any]]) -> None:
    """
    Hiển thị toàn bộ lịch sử trao đổi của phiên hội thoại hiện tại.

    Args:
        messages: Danh sách các tin nhắn gồm role, content, sources, v.v.
    """
    logo_src = get_logo_base64()
    logo_img = (
        f'<img src="{logo_src}" alt="HaUI Logo" '
        f'style="width: 20px; height: 20px; object-fit: contain; border-radius: 3px;" />'
        if logo_src
        else ""
    )

    for idx, msg in enumerate(messages):
        role = msg.get("role")
        content = msg.get("content", "")
        sources = msg.get("sources") or msg.get("citations") or []
        resp_time = msg.get("response_time_ms") or msg.get("latency_ms") or 0
        fallback_used = msg.get("fallback_used", False)

        if role == "user":
            # Tin nhắn của người dùng: Nhỏ gọn, căn phải, nền Slate nhẹ nhàng
            st.markdown(
                f"""
                <div class="message-bubble-user">
                    <div class="message-role-label">Bạn</div>
                    <div>{content}</div>
                </div>
                """,
                unsafe_allow_html=True,
            )
        else:
            # Tin nhắn của Trợ lý AI: Tối giản, không đóng hộp, kiểu chữ học thuật dễ đọc
            st.markdown(
                f"""
                <div style="margin-top: 14px; margin-bottom: 4px; display: flex; align-items: center; gap: 8px;">
                    {logo_img}
                    <span style="font-size: 0.78rem; font-weight: 700; color: var(--text-main); letter-spacing: 0.02em;">
                        TRỢ LÝ QUY CHẾ HAUI
                    </span>
                </div>
                """,
                unsafe_allow_html=True,
            )

            # Thông báo tìm kiếm mở rộng nếu có kích hoạt fallback
            if fallback_used:
                st.markdown(
                    """
                    <div class="fallback-banner">
                        Không tìm thấy đủ thông tin trong kho tài liệu nội bộ.
                        Hệ thống đã tham khảo thêm nguồn chính thức từ Cổng thông tin HaUI (haui.edu.vn).
                    </div>
                    """,
                    unsafe_allow_html=True,
                )

            # Nội dung câu trả lời chính
            st.markdown(f'<div class="message-assistant-body">{content}</div>', unsafe_allow_html=True)

            # Thanh trích dẫn tương tác (Interactive Citation Bar)
            if sources:
                st.markdown(
                    '<div style="font-size: 0.78rem; font-weight: 600; color: #64748B; margin-top: 8px; margin-bottom: 4px;">TÀI LIỆU TRÍCH DẪN:</div>',
                    unsafe_allow_html=True,
                )
                cite_cols = st.columns(min(len(sources), 4))
                for s_idx, src in enumerate(sources[:4]):
                    col = cite_cols[s_idx]
                    mvb = src.get("ma_van_ban") or "Quy chế"
                    label = f"[{s_idx + 1}] {mvb}"
                    with col:
                        if st.button(label, key=f"cite_btn_{idx}_{s_idx}", use_container_width=True):
                            set_active_citation(s_idx)
                            st.rerun()

            # Thông tin thời gian xử lý và đánh giá phản hồi
            foot_col1, _ = st.columns([3, 7])
            with foot_col1:
                if resp_time > 0:
                    st.caption(f"Thời gian tra cứu & tổng hợp: {resp_time} ms")

            # Khu vực phản hồi người dùng
            user_question = messages[idx - 1]["content"] if idx > 0 and messages[idx - 1]["role"] == "user" else ""
            render_feedback_section(
                msg_idx=idx,
                question=user_question,
                answer=content,
                response_time_ms=resp_time,
            )

            st.markdown("<hr style='border: none; border-top: 1px solid #F1F5F9; margin: 20px 0;'>", unsafe_allow_html=True)
