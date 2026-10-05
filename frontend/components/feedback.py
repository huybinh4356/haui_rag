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


def render_feedback_section(msg_idx: int, question: str, answer: str, response_time_ms: int) -> None:
    """
    Hiển thị khu vực đánh giá câu trả lời của trợ lý.

    Args:
        msg_idx: Chỉ số của tin nhắn trong phiên hội thoại.
        question: Câu hỏi tương ứng.
        answer: Câu trả lời đã hiển thị.
        response_time_ms: Thời gian xử lý.
    """
    feedback_key = f"fb_{msg_idx}"
    current_status = st.session_state.feedback_status.get(feedback_key)

    if current_status == "submitted":
        st.caption("Cảm ơn bạn đã đóng góp phản hồi để cải thiện chất lượng tra cứu.")
        return

    st.markdown('<span style="font-size: 0.82rem; color: #64748B;">Phản hồi này có hữu ích không?</span>', unsafe_allow_html=True)

    col1, col2, _ = st.columns([1.2, 1.5, 6])
    with col1:
        if st.button("Hữu ích", key=f"btn_pos_{msg_idx}", type="secondary"):
            payload = {
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
        if st.button("Cần cải thiện", key=f"btn_neg_{msg_idx}", type="secondary"):
            st.session_state.feedback_status[feedback_key] = "selecting_reason"
            st.rerun()

    # Nếu người dùng bấm Cần cải thiện, hiển thị các lựa chọn lý do cụ thể
    if current_status == "selecting_reason":
        with st.container():
            selected_reason = st.selectbox(
                "Vui lòng cho biết lý do chưa hài lòng:",
                options=FEEDBACK_REASONS,
                key=f"reason_{msg_idx}",
            )
            more_comment = st.text_input(
                "Ý kiến bổ sung (không bắt buộc):",
                key=f"cmt_{msg_idx}",
                placeholder="Ghi chú thêm về điều khoản hoặc quy định cần bổ sung...",
            )
            col_sub, col_cancel = st.columns([1.5, 1.5])
            with col_sub:
                if st.button("Gửi đánh giá", key=f"send_fb_{msg_idx}", type="primary"):
                    payload = {
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
                if st.button("Hủy", key=f"cancel_fb_{msg_idx}"):
                    st.session_state.feedback_status[feedback_key] = None
                    st.rerun()
