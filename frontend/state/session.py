"""Module khởi tạo và quản lý Session State cho ứng dụng haui_rag.

Quản lý:
- Danh sách hội thoại phân nhóm (Hôm nay, Trước đó).
- Tự động đặt tên hội thoại theo câu hỏi đầu tiên.
- Trạng thái chọn và đối chiếu trích dẫn nguồn (Active Citation).
- Chuyển đổi giao diện Sáng / Tối (Theme Mode: light / dark).
- Tùy chọn hiển thị (View Mode, Diagnostics, Simple/Advanced).
"""

from datetime import datetime, date
import logging
from typing import Any, Optional
import uuid
import streamlit as st

logger = logging.getLogger(__name__)

# Danh sách hội thoại mẫu hiển thị chuẩn theo thiết kế
INITIAL_PRESET_CONVERSATIONS = [
    {
        "id": "c_today_1",
        "title": "Điều kiện tốt nghiệp",
        "time_label": "2 phút trước",
        "group": "today",
        "messages": [],
    },
    {
        "id": "c_today_2",
        "title": "Quy định học phí",
        "time_label": "15 phút trước",
        "group": "today",
        "messages": [],
    },
    {
        "id": "c_today_3",
        "title": "Thời gian đào tạo thạc sĩ",
        "time_label": "42 phút trước",
        "group": "today",
        "messages": [],
    },
    {
        "id": "c_prev_1",
        "title": "Bảo lưu kết quả học tập",
        "time_label": "1 ngày trước",
        "group": "previous",
        "messages": [],
    },
    {
        "id": "c_prev_2",
        "title": "Chính sách tuyển sinh",
        "time_label": "2 ngày trước",
        "group": "previous",
        "messages": [],
    },
    {
        "id": "c_prev_3",
        "title": "Quy định đào tạo",
        "time_label": "3 ngày trước",
        "group": "previous",
        "messages": [],
    },
]


def init_session_state() -> None:
    """Khởi tạo toàn bộ các biến trạng thái cần thiết nếu chưa có trong session_state."""
    if "theme_mode" not in st.session_state:
        st.session_state.theme_mode = "light"  # "light" hoặc "dark"

    if "conversations" not in st.session_state:
        # Nạp các hội thoại mẫu theo đúng bản thiết kế
        convs = {}
        today_str = date.today().isoformat()
        for p in INITIAL_PRESET_CONVERSATIONS:
            convs[p["id"]] = {
                "id": p["id"],
                "title": p["title"],
                "time_label": p["time_label"],
                "group": p["group"],
                "date": today_str if p["group"] == "today" else "2026-10-01",
                "created_at": datetime.now().isoformat(),
                "messages": p["messages"].copy(),
            }
        st.session_state.conversations = convs
        st.session_state.active_conv_id = "c_today_1"

    if "active_conv_id" not in st.session_state:
        st.session_state.active_conv_id = next(iter(st.session_state.conversations.keys()))

    if "active_citation_index" not in st.session_state:
        st.session_state.active_citation_index = None

    if "view_mode" not in st.session_state:
        st.session_state.view_mode = "chat"  # "chat", "settings", "about"

    if "show_evidence_panel" not in st.session_state:
        st.session_state.show_evidence_panel = True

    if "user_mode" not in st.session_state:
        st.session_state.user_mode = "simple"  # "simple" hoặc "advanced"

    if "top_k" not in st.session_state:
        st.session_state.top_k = 5

    if "pending_question" not in st.session_state:
        st.session_state.pending_question = None

    if "feedback_status" not in st.session_state:
        st.session_state.feedback_status = {}


def toggle_theme_mode() -> None:
    """Chuyển đổi qua lại giữa chế độ Sáng (light) và Tối (dark)."""
    if st.session_state.theme_mode == "light":
        st.session_state.theme_mode = "dark"
    else:
        st.session_state.theme_mode = "light"


def get_current_conversation() -> dict[str, Any]:
    """
    Lấy đối tượng hội thoại đang kích hoạt.

    Returns:
        dict: Thông tin hội thoại hiện tại.
    """
    cid = st.session_state.active_conv_id
    if cid not in st.session_state.conversations:
        return create_new_conversation()
    return st.session_state.conversations[cid]


def create_new_conversation(title: str = "Cuộc trò chuyện mới") -> dict[str, Any]:
    """
    Tạo một phiên hội thoại mới và đặt làm phiên làm việc hiện tại.

    Args:
        title: Tiêu đề hội thoại.

    Returns:
        dict: Hội thoại mới được tạo.
    """
    new_id = f"c_{str(uuid.uuid4())[:8]}"
    today_str = date.today().isoformat()
    new_conv = {
        "id": new_id,
        "title": title,
        "time_label": "Vừa tạo",
        "group": "today",
        "date": today_str,
        "created_at": datetime.now().isoformat(),
        "messages": [],
    }
    # Đưa lên đầu danh sách hội thoại
    new_dict = {new_id: new_conv}
    new_dict.update(st.session_state.conversations)
    st.session_state.conversations = new_dict
    st.session_state.active_conv_id = new_id
    st.session_state.active_citation_index = None
    st.session_state.view_mode = "chat"
    return new_conv


def switch_conversation(conv_id: str) -> None:
    """
    Chuyển đổi phiên làm việc sang một hội thoại khác.

    Args:
        conv_id: ID của hội thoại đích.
    """
    if conv_id in st.session_state.conversations:
        st.session_state.active_conv_id = conv_id
        st.session_state.active_citation_index = None
        st.session_state.view_mode = "chat"


def delete_conversation(conv_id: str) -> None:
    """
    Xóa một phiên hội thoại khỏi danh sách.

    Args:
        conv_id: ID của hội thoại cần xóa.
    """
    if conv_id in st.session_state.conversations:
        del st.session_state.conversations[conv_id]
        if not st.session_state.conversations:
            create_new_conversation()
        else:
            st.session_state.active_conv_id = next(iter(st.session_state.conversations.keys()))
        st.session_state.active_citation_index = None


def add_message_to_current(
    role: str,
    content: str,
    sources: Optional[list[dict[str, Any]]] = None,
    response_time_ms: int = 0,
    query_type: Optional[str] = None,
    fallback_used: bool = False,
    citation_audit: Optional[dict[str, Any]] = None,
    error: Optional[str] = None,
) -> None:
    """
    Thêm tin nhắn mới vào phiên hội thoại hiện tại.
    Tự động cập nhật tiêu đề hội thoại nếu là tin nhắn đầu tiên của người dùng.

    Args:
        role: "user" hoặc "assistant".
        content: Nội dung tin nhắn.
        sources: Danh sách các nguồn trích dẫn.
        response_time_ms: Thời gian xử lý.
        query_type: Loại câu hỏi.
        fallback_used: Có sử dụng fallback hay không.
        citation_audit: Kết quả thẩm định trích dẫn.
        error: Thông báo lỗi nếu có.
    """
    conv = get_current_conversation()
    msg = {
        "role": role,
        "content": content,
        "sources": sources or [],
        "response_time_ms": response_time_ms,
        "query_type": query_type,
        "fallback_used": fallback_used,
        "citation_audit": citation_audit,
        "error": error,
        "timestamp": datetime.now().isoformat(),
    }
    conv["messages"].append(msg)

    # Nếu đây là câu hỏi đầu tiên của người dùng, đặt lại tiêu đề ngắn gọn
    if role == "user" and len(conv["messages"]) == 1:
        clean_title = content.strip().replace("\n", " ")
        if len(clean_title) > 30:
            clean_title = clean_title[:30] + "..."
        conv["title"] = clean_title
        conv["time_label"] = "Vừa xong"


def set_active_citation(index: Optional[int]) -> None:
    """
    Thiết lập chỉ mục trích dẫn đang được người dùng nhấn chọn để xem đối chiếu.

    Args:
        index: Vị trí của nguồn trong danh sách sources (0-indexed) hoặc None để bỏ chọn.
    """
    st.session_state.active_citation_index = index
