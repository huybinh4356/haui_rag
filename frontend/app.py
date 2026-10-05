"""Ứng dụng Trợ lý Tra cứu Quy chế và Văn bản Học vụ HaUI (HAUI Regulation Assistant).

Bố cục 3 cột học thuật chuẩn mực:
- Cột Trái (Left Nav): Điều hướng và quản lý các phiên hội thoại (kết nối PostgreSQL).
- Cột Giữa (Main Chat): Dòng hội thoại Markdown và thanh nhập câu hỏi cố định.
- Cột Phải (Evidence Panel): Bảng nguồn chứng cứ đối chiếu và thông tin văn bản.
"""

from datetime import datetime
import logging
from pathlib import Path
import sys
import time
from typing import Any
import uuid
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
    init_session_state,
    refresh_conversations_list,
    reload_active_conversation_messages,
    set_active_citation,
)
from frontend.styles.theme import apply_theme

logger = logging.getLogger("haui_rag.frontend")
BASE_API_URL = f"http://{BACKEND_HOST}:{BACKEND_PORT}"
HEALTH_URL = f"{BASE_API_URL}/"

# 1. Cấu hình trang Streamlit chuẩn mực
st.set_page_config(
    page_title="Trợ lý Quy chế HaUI",
    page_icon="frontend/assets/haui_logo.png",
    layout="wide",
    initial_sidebar_state="expanded",
)

# 2. Khởi tạo trạng thái phiên làm việc từ PostgreSQL
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


def send_message_to_pipeline(
    conversation_id: str,
    question: str,
    top_k: int,
) -> dict[str, Any]:
    """
    Gửi câu hỏi tới FastAPI Backend hoặc Direct Mode nếu Backend chưa khởi động.

    Args:
        conversation_id: UUID cuộc trò chuyện.
        question: Câu hỏi quy chế cần tra cứu.
        top_k: Số lượng tài liệu trích dẫn cần lấy.

    Returns:
        dict: Kết quả phản hồi chứa message, citations, latency_ms.
    """
    # 1. Thử gọi qua HTTP REST API trước
    try:
        url = f"{BASE_API_URL}/conversations/{conversation_id}/messages"
        resp = requests.post(
            url,
            json={"content": question, "top_k": top_k},
            timeout=120,
        )
        if resp.status_code == 200:
            return resp.json()
    except Exception as e:
        logger.warning("Không thể gọi Backend API /messages, chuyển sang Direct DB Mode: %s", e)

    # 2. Chế độ Fallback trực tiếp vào cơ sở dữ liệu và Core RAG
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    start_time = time.perf_counter()

    try:
        from haui_rag.core.rag_pipeline import rag_query
        from haui_rag.db.conversation_queries import (
            save_assistant_message,
            save_request_log,
            save_user_message,
        )

        # Lưu tin nhắn người dùng trước khi gọi RAG
        save_user_message(
            conversation_id=conversation_id,
            content=question,
            request_id=request_id,
        )

        # Gọi RAG pipeline
        rag_result = rag_query(query=question, top_k=top_k)
        total_latency_ms = int((time.perf_counter() - start_time) * 1000)

        answer_text = rag_result.get("answer", "")
        sources_raw = rag_result.get("sources", [])
        citations_data = [
            {
                "chunk_id": s.get("chunk_id"),
                "citation": s.get("citation", "Quy chế HaUI"),
                "ma_van_ban": s.get("ma_van_ban"),
                "ten_van_ban": s.get("ten_van_ban"),
                "dieu": s.get("dieu"),
                "khoan": s.get("khoan"),
                "distance": s.get("distance"),
                "source_type": s.get("source_type", "database"),
                "content": s.get("content"),
            }
            for s in sources_raw
        ]

        # Lưu tin nhắn Assistant vào DB
        ast_msg = save_assistant_message(
            conversation_id=conversation_id,
            content=answer_text,
            request_id=request_id,
            query_type=rag_result.get("query_type"),
            latency_ms=total_latency_ms,
            fallback_used=rag_result.get("fallback_used", False),
            citations=citations_data,
            metadata={"citation_audit": rag_result.get("citation_audit")},
        )

        save_request_log(
            request_id=request_id,
            conversation_id=conversation_id,
            endpoint="/direct_mode",
            status_code=200,
            latencies={"total_latency_ms": total_latency_ms},
            fallback_used=rag_result.get("fallback_used", False),
        )

        return {
            "message": ast_msg,
            "citations": citations_data,
            "request_id": request_id,
            "latency_ms": total_latency_ms,
            "fallback_used": rag_result.get("fallback_used", False),
        }
    except Exception as e:
        logger.error("Lỗi khi xử lý truy vấn: %s", e, exc_info=True)
        return {
            "message": {
                "id": "err",
                "role": "assistant",
                "content": f"Không thể xử lý yêu cầu: {str(e)}",
                "created_at": datetime.now().isoformat(),
            },
            "citations": [],
            "request_id": request_id,
            "latency_ms": 0,
            "fallback_used": False,
        }


def handle_user_query(question: str) -> None:
    """
    Xử lý chu trình nhận câu hỏi, hiển thị tiến trình RAG và lưu phản hồi vào DB.

    Args:
        question: Nội dung câu hỏi người dùng nhập.
    """
    active_id = st.session_state.active_conv_id
    if not active_id:
        from frontend.state.session import create_new_conversation
        conv = create_new_conversation(title="Cuộc trò chuyện mới")
        active_id = conv["id"]
        st.session_state.active_conv_id = active_id

    # Hiển thị tạm thời tin nhắn người dùng trên UI
    st.session_state.messages.append(
        {
            "id": f"tmp_user_{uuid.uuid4().hex[:6]}",
            "role": "user",
            "content": question,
            "created_at": datetime.now().isoformat(),
        }
    )

    # Hiển thị trạng thái tra cứu đa giai đoạn
    with st.status("Đang tra cứu quy chế HaUI...", expanded=True) as status_box:
        st.write("1. Phân tích ngữ nghĩa câu hỏi và trích xuất thực thể điều khoản...")
        time.sleep(0.1)
        st.write("2. Tìm kiếm văn bản quy chế liên quan trong cơ sở dữ liệu...")
        response_data = send_message_to_pipeline(active_id, question, st.session_state.top_k)

        st.write("3. Thẩm định nguồn trích dẫn và đối chiếu tính trung thực...")
        time.sleep(0.1)
        st.write("4. Hoàn tất tổng hợp câu trả lời chính thức.")
        status_box.update(label="Tra cứu hoàn tất", state="complete", expanded=False)

    # Nạp lại tin nhắn chính thức từ cơ sở dữ liệu
    reload_active_conversation_messages()

    # Cập nhật danh sách hội thoại để cập nhật tiêu đề mới và mốc thời gian
    refresh_conversations_list()

    # Tự động chọn xem nguồn trích dẫn đầu tiên nếu có
    citations = response_data.get("citations", [])
    if citations:
        set_active_citation(0)

    st.rerun()


# --- TIẾN TRÌNH RENDER GIAO DIỆN ---
is_online, health_data = check_backend_health()

# 1. Render Top Navigation Bar
render_topbar(is_online, health_data)

# 2. Render Left Sidebar Navigation (Kết nối PostgreSQL)
render_sidebar()

# 3. Phân nhánh giao diện theo chế độ xem (View Mode)
if st.session_state.view_mode == "settings":
    render_settings_view(health_data)
elif st.session_state.view_mode == "about":
    render_about_view()
else:
    # 4. Bố cục 3 cột chính thức trên Desktop (Left Nav đã nằm ở Sidebar)
    # Khu vực chính phân chia 2 cột: Main Chat (7) và Evidence Panel (5)
    messages = st.session_state.get("messages", [])

    col_chat, col_evidence = st.columns([7, 5], gap="large")

    with col_chat:
        if not messages:
            # Trạng thái rỗng chuẩn thiết kế với ô tìm kiếm trung tâm và 4 gợi ý câu hỏi
            render_empty_state(on_submit=handle_user_query)
        else:
            # Hiển thị toàn bộ lịch sử tin nhắn lưu trữ từ PostgreSQL
            render_chat_history(messages)
            # Thanh nhập câu hỏi cố định ở chân trang khi đang trò chuyện
            render_composer(handle_user_query)

    with col_evidence:
        # Lấy danh sách nguồn trích dẫn từ tin nhắn phản hồi gần nhất của trợ lý
        assistant_msgs = [m for m in messages if m.get("role") == "assistant"]
        latest_sources = []
        latest_audit = None
        if assistant_msgs:
            last_m = assistant_msgs[-1]
            latest_sources = last_m.get("sources") or last_m.get("citations") or []
            latest_audit = last_m.get("citation_audit") or (last_m.get("metadata") or {}).get("citation_audit")

        render_evidence_panel(
            sources=latest_sources,
            active_idx=st.session_state.active_citation_index,
            citation_audit=latest_audit,
        )
