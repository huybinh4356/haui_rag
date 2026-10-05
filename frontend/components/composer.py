"""Component thanh soạn thảo câu hỏi và chỉ báo quy trình RAG đa giai đoạn."""

import time
from typing import Any, Callable, Optional
import streamlit as st


def render_composer(on_submit: Callable[[str], None]) -> None:
    """
    Hiển thị khung nhập câu hỏi lớn ở chân trang cùng gợi ý phím tắt.

    Args:
        on_submit: Hàm callback khi người dùng gửi câu hỏi.
    """
    user_query = st.chat_input("Hỏi về quy chế đào tạo, tốt nghiệp, học phí HaUI...")

    # Nếu có câu hỏi được chọn từ thẻ gợi ý ở Empty State
    pending = st.session_state.get("pending_question")
    if pending:
        user_query = pending
        st.session_state.pending_question = None

    if user_query and user_query.strip():
        on_submit(user_query.strip())


def render_rag_progress() -> Any:
    """
    Tạo chỉ báo tiến trình RAG đa giai đoạn tinh tế, minh bạch và chuyên nghiệp.

    Returns:
        Đối tượng Streamlit status context manager.
    """
    return st.status("Đang tra cứu cơ sở dữ liệu quy chế HaUI...", expanded=True)
