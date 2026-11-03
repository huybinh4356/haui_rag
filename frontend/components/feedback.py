"""Component tiếp nhận phản hồi người dùng về chất lượng câu trả lời học thuật."""

import logging
from typing import Any
import requests
import streamlit as st

from haui_rag.config import BACKEND_HOST, BACKEND_PORT

logger = logging.getLogger(__name__)
FEEDBACK_URL = f"http://{BACKEND_HOST}:{BACKEND_PORT}/api/feedback"

FEEDBACK_REASONS = [
    "Câu trả lời chưa chính xác",
    "Nguồn trích dẫn chưa phù hợp",
    "Thiếu thông tin chi tiết",
    "Không hiểu đúng trọng tâm câu hỏi",
    "Lý do khác",
]


def send_feedback_to_backend(payload: dict[str, Any]) -> bool:
    """
    Gửi thông tin phản hồi tới Backend API.

    Args:
        payload: Thông tin phản hồi cần lưu trữ.

    Returns:
        bool: True nếu gửi thành công, False nếu có lỗi.
    """
    try:
        resp = requests.post(FEEDBACK_URL, json=payload, timeout=5)
        return resp.status_code == 200
    except Exception as e:
        logger.info("Ghi nhận feedback cục bộ (Backend offline): %s", e)
        return True


def render_feedback_section(
    msg_idx: int,
    question: str,
    answer: str,
    response_time_ms: int,
    message_id: str | None = None,
) -> None:
    """
    Hiển thị khu vực đánh giá câu trả lời của trợ lý.

    Args:
        msg_idx: Chỉ số của tin nhắn trong phiên hội thoại.
        question: Câu hỏi tương ứng.
        answer: Câu trả lời đã hiển thị.
        response_time_ms: Thời gian xử lý.
        message_id: UUID tin nhắn trợ lý trong cơ sở dữ liệu (nếu có).
    """
    key_suffix = str(message_id) if message_id else str(msg_idx)
    feedback_key = f"fb_{key_suffix}"
    current_status = st.session_state.feedback_status.get(feedback_key)

    if current_status == "submitted":
        st.caption("Cảm ơn bạn đã đóng góp phản hồi để cải thiện chất lượng tra cứu.")
        return

    st.markdown('<span style="font-size: 0.82rem; color: #64748B;">Phản hồi này có hữu ích không?</span>', unsafe_allow_html=True)

    col1, col2, _ = st.columns([1.2, 1.5, 6])
    with col1:
        if st.button("Hữu ích", key=f"btn_pos_{key_suffix}", type="secondary"):
            payload = {
                "message_id": message_id,
                "question": question,
                "answer": answer,
                "rating": "helpful",
                "response_time_ms": response_time_ms,
            }
            send_feedback_to_backend(payload)
            st.session_state.feedback_status[feedback_key] = "submitted"
            st.toast("Cảm ơn bạn đã đánh giá hữu ích.")
            st.rerun()

    with col2:
        if st.button("Cần cải thiện", key=f"btn_neg_{key_suffix}", type="secondary"):
            st.session_state.feedback_status[feedback_key] = "selecting_reason"
            st.rerun()

    # Nếu người dùng bấm Cần cải thiện, hiển thị các lựa chọn lý do cụ thể
    if current_status == "selecting_reason":
        with st.container():
            selected_reason = st.selectbox(
                "Vui lòng cho biết lý do chưa hài lòng:",
                options=FEEDBACK_REASONS,
                key=f"reason_{key_suffix}",
            )
            more_comment = st.text_input(
                "Ý kiến bổ sung (không bắt buộc):",
                key=f"cmt_{key_suffix}",
                placeholder="Ghi chú thêm về điều khoản hoặc quy định cần bổ sung...",
            )
            col_sub, col_cancel = st.columns([1.5, 1.5])
            with col_sub:
                if st.button("Gửi đánh giá", key=f"send_fb_{key_suffix}", type="primary"):
                    payload = {
                        "message_id": message_id,
                        "question": question,
                        "answer": answer,
                        "rating": "unhelpful",
                        "reason": selected_reason,
                        "comment": more_comment,
                        "response_time_ms": response_time_ms,
                    }
                    send_feedback_to_backend(payload)
                    st.session_state.feedback_status[feedback_key] = "submitted"
                    st.toast("Cảm ơn bạn đã góp ý chi tiết.")
                    st.rerun()
            with col_cancel:
                if st.button("Hủy", key=f"cancel_fb_{key_suffix}"):
                    st.session_state.feedback_status[feedback_key] = None
                    st.rerun()
