"""Ứng dụng Trợ lý Tra cứu Quy chế và Văn bản Học vụ HaUI (HAUI Regulation Assistant).

Bố cục 3 cột học thuật chuẩn mực:
- Cột Trái (Left Nav): Điều hướng và quản lý các phiên hội thoại.
- Cột Giữa (Main Chat): Dòng hội thoại Markdown và thanh nhập câu hỏi cố định.
- Cột Phải (Evidence Panel): Bảng nguồn chứng cứ đối chiếu và thông tin văn bản.
"""

import logging
from pathlib import Path
import sys
import time
from typing import Any
import requests
import streamlit as st

# Đảm bảo đường dẫn gốc dự án và src nằm trong sys.path
ROOT_DIR = Path(__file__).resolve().parent.parent
SRC_DIR = ROOT_DIR / "src"
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))
if str(SRC_DIR) not in sys.path:
    sys.path.insert(0, str(SRC_DIR))

from haui_rag.config import (
    ACTIVE_LLM_MODEL,
    BACKEND_HOST,
    BACKEND_PORT,
    DEFAULT_TOP_K,
    LLM_PROVIDER,
)
from frontend.components.about_view import render_about_view
from frontend.components.chat_view import render_chat_history
from frontend.components.composer import render_composer
from frontend.components.empty_state import render_empty_state
from frontend.components.evidence_panel import render_evidence_panel
from frontend.components.settings_view import render_settings_view
from frontend.components.sidebar import render_sidebar
from frontend.components.topbar import render_topbar
from frontend.state.session import (
    add_message_to_current,
    get_current_conversation,
    init_session_state,
    set_active_citation,
)
from frontend.styles.theme import apply_theme

logger = logging.getLogger("haui_rag.frontend")
API_URL = f"http://{BACKEND_HOST}:{BACKEND_PORT}/api/chat"
HEALTH_URL = f"http://{BACKEND_HOST}:{BACKEND_PORT}/"

# 1. Cấu hình trang Streamlit chuẩn mực
st.set_page_config(
    page_title="HAUI Regulation Assistant",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 2. Khởi tạo trạng thái phiên làm việc (Theme mode, Conversations, v.v.)
init_session_state()

# 3. Áp dụng bảng màu và phong cách CSS theo theme được chọn (Sáng / Tối)
apply_theme(mode=st.session_state.theme_mode)


def check_backend_health() -> tuple[bool, dict[str, Any]]:
    """
    Kiểm tra tình trạng sẵn sàng của Backend server.

    Returns:
        tuple[bool, dict]: Trạng thái kết nối và dữ liệu health check.
    """
    try:
        res = requests.get(HEALTH_URL, timeout=3)
        if res.status_code == 200:
            return True, res.json()
        return False, {}
    except Exception:
        return False, {}


def query_chat_api(question: str, top_k: int) -> dict[str, Any]:
    """
    Gửi câu hỏi tới FastAPI Backend hoặc chuyển sang Direct Mode nếu Backend chưa bật.

    Args:
        question: Câu hỏi quy chế cần tra cứu.
        top_k: Số lượng tài liệu trích dẫn cần lấy.

    Returns:
        dict: Kết quả phản hồi gồm answer, sources, response_time_ms, v.v.
    """
    # 1. Thử gọi qua HTTP API trước
    try:
        resp = requests.post(
            API_URL,
            json={"question": question, "top_k": top_k},
            timeout=120,
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.warning("Không thể kết nối Backend API, chuyển sang Direct Mode: %s", e)

    # 2. Fallback trực tiếp gọi core pipeline
    try:
        from haui_rag.core.rag_pipeline import rag_query
        return rag_query(query=question, top_k=top_k)
    except Exception as e:
        logger.error("Lỗi khi xử lý truy vấn: %s", e, exc_info=True)
        return {
            "answer": f"Không thể xử lý yêu cầu: {str(e)}",
            "sources": [],
            "response_time_ms": 0,
            "error": str(e),
        }


def handle_user_query(question: str) -> None:
    """
    Xử lý chu trình nhận câu hỏi, hiển thị tiến trình RAG và lưu phản hồi.

    Args:
        question: Nội dung câu hỏi người dùng nhập.
    """
    # Ghi nhận tin nhắn người dùng
    add_message_to_current(role="user", content=question)

    # Hiển thị trạng thái tra cứu đa giai đoạn
    with st.status("Đang tra cứu quy chế HaUI...", expanded=True) as status_box:
        st.write("1. Phân tích ngữ nghĩa câu hỏi và trích xuất thực thể điều khoản...")
        time.sleep(0.1)
        st.write("2. Tìm kiếm văn bản quy chế liên quan trong cơ sở dữ liệu...")
        response_data = query_chat_api(question, st.session_state.top_k)

        st.write("3. Thẩm định nguồn trích dẫn và đối chiếu tính trung thực...")
        time.sleep(0.1)
        st.write("4. Hoàn tất tổng hợp câu trả lời chính thức.")
        status_box.update(label="Tra cứu hoàn tất", state="complete", expanded=False)

    # Lưu kết quả trả lời của trợ lý vào phiên làm việc
    answer_text = response_data.get("answer", "Xin lỗi, không tìm thấy thông tin phù hợp.")
    sources_list = response_data.get("sources", [])
    resp_time = response_data.get("response_time_ms", 0)
    q_type = response_data.get("query_type")
    fallback_used = response_data.get("fallback_used", False)
    citation_audit = response_data.get("citation_audit")

    add_message_to_current(
        role="assistant",
        content=answer_text,
        sources=sources_list,
        response_time_ms=resp_time,
        query_type=q_type,
        fallback_used=fallback_used,
        citation_audit=citation_audit,
    )

    # Tự động chọn xem nguồn trích dẫn đầu tiên nếu có
    if sources_list:
        set_active_citation(0)

    st.rerun()


# --- TIẾN TRÌNH RENDER GIAO DIỆN ---
is_online, health_data = check_backend_health()

# 1. Render Top Navigation Bar
render_topbar(is_online, health_data)

# 2. Render Left Sidebar Navigation
render_sidebar()

# 3. Phân nhánh giao diện theo chế độ xem (View Mode)
if st.session_state.view_mode == "settings":
    render_settings_view(health_data)
elif st.session_state.view_mode == "about":
    render_about_view()
else:
    # 4. Bố cục 3 cột chính thức trên Desktop (Left Nav đã nằm ở Sidebar)
    # Khu vực chính phân chia 2 cột: Main Chat (7) và Evidence Panel (5)
    current_conv = get_current_conversation()
    messages = current_conv.get("messages", [])

    col_chat, col_evidence = st.columns([7, 5], gap="large")

    with col_chat:
        if not messages:
            # Trạng thái rỗng chuẩn thiết kế với ô tìm kiếm trung tâm và 4 gợi ý câu hỏi
            render_empty_state(on_submit=handle_user_query)
        else:
            # Hiển thị toàn bộ lịch sử tin nhắn
            render_chat_history(messages)
            # Thanh nhập câu hỏi cố định ở chân trang khi đang trò chuyện
            render_composer(handle_user_query)

    with col_evidence:
        # Lấy danh sách nguồn trích dẫn từ tin nhắn phản hồi gần nhất của trợ lý
        assistant_msgs = [m for m in messages if m.get("role") == "assistant"]
        latest_sources = assistant_msgs[-1].get("sources", []) if assistant_msgs else []
        latest_audit = assistant_msgs[-1].get("citation_audit") if assistant_msgs else None

        render_evidence_panel(
            sources=latest_sources,
            active_idx=st.session_state.active_citation_index,
            citation_audit=latest_audit,
        )
