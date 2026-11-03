"""Component hiển thị dòng hội thoại, định dạng Markdown học thuật và trích dẫn tương tác."""

import html
from typing import Any
import streamlit as st
import streamlit.components.v1 as components

from frontend.components.feedback import render_feedback_section
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
            # Tin nhắn của người dùng: Nhỏ gọn, căn phải, nền Slate nhẹ nhàng (escape chống XSS)
            safe_user_content = html.escape(str(content)).replace("\n", "<br/>")
            st.markdown(
                f"""
                <div class="message-bubble-user">
                    <div class="message-role-label">Bạn</div>
                    <div>{safe_user_content}</div>
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
                message_id=msg.get("id"),
            )

            st.markdown("<hr style='border: none; border-top: 1px solid var(--border-color); margin: 20px 0;'>", unsafe_allow_html=True)

    # Thẻ neo điểm cuối cuộc hội thoại và kịch bản tự cuộn xuống đáy (đẩy lịch sử lên trên)
    st.markdown('<div id="chat-end-anchor" style="height: 1px;"></div>', unsafe_allow_html=True)
    components.html(
        """
        <script>
            function scrollToBottom() {
                try {
                    const doc = window.parent.document;
                    const anchor = doc.getElementById('chat-end-anchor');
                    if (anchor) {
                        anchor.scrollIntoView({ behavior: 'smooth', block: 'end' });
                        return;
                    }
                    const chatBox = doc.querySelector('.st-key-chat_messages_box');
                    if (chatBox) {
                        chatBox.scrollTop = chatBox.scrollHeight;
                    }
                } catch (e) {}
            }
            scrollToBottom();
            setTimeout(scrollToBottom, 60);
            setTimeout(scrollToBottom, 220);
        </script>
        """,
        height=0,
        width=0,
    )
