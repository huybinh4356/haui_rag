"""Module quản lý Trạng thái Phiên làm việc (Session State) cho giao diện Streamlit.

TOÀN BỘ LỊCH SỬ HỘI THOẠI ĐƯỢC LƯU TRỮ VÀ TRUY XUẤT TỪ CƠ SỞ DỮ LIỆU POSTGRESQL:
- Danh sách hội thoại được tải từ bảng `conversations`.
- Lịch sử tin nhắn được tải từ bảng `messages`.
- Khi người dùng chuyển đổi hoặc mở lại cuộc trò chuyện cũ:
  TUYỆT ĐỐI KHÔNG gọi RAG, KHÔNG embedding, KHÔNG gọi LLM.
- Hỗ trợ lưu trữ query param URL (?c=<conversation_id>) để phục hồi chính xác khi tải lại trang (Refresh).
"""

from datetime import datetime, timezone
import logging
import os
from typing import Any, Optional
import requests
import streamlit as st

from haui_rag.config import BACKEND_HOST, BACKEND_PORT
from haui_rag.db.conversation_queries import (
    create_conversation as db_create_conversation,
    delete_conversation as db_delete_conversation,
    generate_title_from_question,
    get_conversation as db_get_conversation,
    get_conversation_messages as db_get_conversation_messages,
    list_conversations as db_list_conversations,
    save_assistant_message as db_save_assistant_message,
    save_request_log as db_save_request_log,
    save_user_message as db_save_user_message,
)

logger = logging.getLogger("haui_rag.frontend.session")
BASE_API_URL = f"http://{BACKEND_HOST}:{BACKEND_PORT}"


# =========================================================================
# HELPER GIAO TIẾP VỚI BACKEND API / DIRECT DATABASE FALLBACK
# =========================================================================


def _is_backend_available() -> bool:
    """Kiểm tra nhanh xem Backend API có đang chạy trên localhost hay không."""
    try:
        resp = requests.get(f"{BASE_API_URL}/", timeout=0.15)
        return resp.status_code == 200
    except Exception:
        return False


def api_list_conversations() -> list[dict[str, Any]]:
    """
    Lấy danh sách tóm tắt các cuộc trò chuyện từ FastAPI Backend hoặc trực tiếp từ DB.

    Returns:
        list[dict]: Danh sách tóm tắt hội thoại sắp xếp updated_at DESC.
    """
    if _is_backend_available():
        try:
            url = f"{BASE_API_URL}/conversations"
            resp = requests.get(url, timeout=1.0)
            if resp.status_code == 200:
                return resp.json()
        except Exception as e:
            logger.debug("Lỗi kết nối Backend API, chuyển sang truy vấn DB: %s", e)

    return db_list_conversations(limit=100)


def api_get_messages(conversation_id: str) -> list[dict[str, Any]]:
    """
    Lấy toàn bộ tin nhắn thuộc một cuộc trò chuyện (Đọc thuần cơ sở dữ liệu).
    TUYỆT ĐỐI KHÔNG GỌI RAG / EMBEDDING / LLM.

    Args:
        conversation_id: UUID cuộc trò chuyện.

    Returns:
        list[dict]: Danh sách tin nhắn kèm trích dẫn đã lưu.
    """
    if _is_backend_available():
        try:
            url = f"{BASE_API_URL}/conversations/{conversation_id}/messages"
            resp = requests.get(url, timeout=1.5)
            if resp.status_code == 200:
                msgs = resp.json()
                for m in msgs:
                    if "citations" in m and not m.get("sources"):
                        m["sources"] = m["citations"]
                return msgs
        except Exception as e:
            logger.debug("Lỗi kết nối Backend API /messages: %s", e)

    raw_msgs = db_get_conversation_messages(conversation_id)
    for m in raw_msgs:
        m["sources"] = m.get("citations") or []
    return raw_msgs


def api_create_conversation(title: str = "Cuộc trò chuyện mới") -> dict[str, Any]:
    """
    Tạo một cuộc trò chuyện mới trong cơ sở dữ liệu.

    Args:
        title: Tiêu đề cuộc trò chuyện.

    Returns:
        dict: Cuộc trò chuyện vừa tạo.
    """
    if _is_backend_available():
        try:
            url = f"{BASE_API_URL}/conversations"
            resp = requests.post(url, json={"title": title}, timeout=1.5)
            if resp.status_code in (200, 201):
                return resp.json()
        except Exception as e:
            logger.debug("Lỗi kết nối Backend API create_conversation: %s", e)

    return db_create_conversation(title=title)


def api_delete_conversation(conversation_id: str) -> bool:
    """
    Xóa một cuộc trò chuyện khỏi cơ sở dữ liệu.

    Args:
        conversation_id: UUID cuộc trò chuyện cần xóa.

    Returns:
        bool: Trạng thái xóa thành công.
    """
    if _is_backend_available():
        try:
            url = f"{BASE_API_URL}/conversations/{conversation_id}"
            resp = requests.delete(url, timeout=1.5)
            if resp.status_code == 200:
                return True
        except Exception as e:
            logger.debug("Lỗi kết nối Backend API delete_conversation: %s", e)

    return db_delete_conversation(conversation_id)


# =========================================================================
# KHỞI TẠO VÀ ĐIỀU HƯỚNG TRẠNG THÁI STREAMLIT SESSION
# =========================================================================


def init_session_state() -> None:
    """
    Khởi tạo toàn bộ trạng thái phiên làm việc Streamlit từ PostgreSQL:
    1. Cấu hình theme mode, view mode, evidence panel, user mode.
    2. Nạp danh sách hội thoại từ database vào `st.session_state.conversations` (Dict mapping).
    3. Đọc query param `?c=<id>` để khôi phục chính xác hội thoại khi reload trang.
    4. Tải danh sách tin nhắn của hội thoại hiện tại (Pure DB read).
    """
    if "theme_mode" not in st.session_state:
        st.session_state.theme_mode = "dark"

    if "view_mode" not in st.session_state:
        st.session_state.view_mode = "chat"

    if "show_evidence_panel" not in st.session_state:
        st.session_state.show_evidence_panel = True

    if "user_mode" not in st.session_state:
        st.session_state.user_mode = "simple"

    if "top_k" not in st.session_state:
        st.session_state.top_k = 5

    if "active_citation_index" not in st.session_state:
        st.session_state.active_citation_index = None

    if "feedback_status" not in st.session_state:
        st.session_state.feedback_status = {}

    if "confirm_delete" not in st.session_state:
        st.session_state.confirm_delete = False

    if "pending_question" not in st.session_state:
        st.session_state.pending_question = None

    # 1. Nạp danh sách hội thoại từ PostgreSQL
    if "conversations" not in st.session_state:
        refresh_conversations_list()

    # 2. Xử lý khôi phục cuộc trò chuyện qua Query Parameter (?c=UUID)
    url_conv_id = st.query_params.get("c")
    conv_dict = st.session_state.get("conversations", {})

    if url_conv_id and url_conv_id in conv_dict:
        target_id = url_conv_id
    elif conv_dict:
        target_id = next(iter(conv_dict.keys()))
    else:
        target_id = None

    st.session_state.active_conv_id = target_id
    if target_id:
        st.query_params["c"] = target_id
    else:
        if "c" in st.query_params:
            del st.query_params["c"]

    # 3. Tải tin nhắn của cuộc trò chuyện hiện tại (Pure DB read)
    if target_id and (
        "messages" not in st.session_state
        or st.session_state.get("current_loaded_cid") != target_id
    ):
        reload_active_conversation_messages()
    elif not target_id:
        st.session_state.messages = []
        st.session_state.current_loaded_cid = None


def refresh_conversations_list() -> None:
    """Tải lại danh sách tóm tắt hội thoại từ database vào session_state (lưu dạng dict ID -> Object)."""
    convs_list = api_list_conversations()
    if not convs_list:
        st.session_state.conversations = {}
        return

    conv_dict: dict[str, dict[str, Any]] = {}
    for c in convs_list:
        cid = c["id"]
        # Bảo toàn messages nếu đã nạp trong bộ nhớ
        existing_msgs = []
        if "conversations" in st.session_state and cid in st.session_state.conversations:
            existing_msgs = st.session_state.conversations[cid].get("messages", [])

        conv_dict[cid] = {
            "id": cid,
            "title": c.get("title") or "Cuộc trò chuyện mới",
            "updated_at": c.get("updated_at"),
            "created_at": c.get("created_at"),
            "message_count": c.get("message_count", 0),
            "messages": existing_msgs,
        }

    st.session_state.conversations = conv_dict


def reload_active_conversation_messages() -> None:
    """
    Nạp tin nhắn cho cuộc trò chuyện đang chọn từ PostgreSQL (ĐỌC THUẦN CƠ SỞ DỮ LIỆU).
    TUYỆT ĐỐI KHÔNG GỌI RAG, KHÔNG TIÊU TỐN QUOTA AI.
    """
    active_id = st.session_state.get("active_conv_id")
    if not active_id:
        return

    messages = api_get_messages(active_id)
    st.session_state.messages = messages
    st.session_state.current_loaded_cid = active_id
    st.session_state.active_citation_index = None

    # Đồng bộ vào dict conversations
    if "conversations" in st.session_state and active_id in st.session_state.conversations:
        st.session_state.conversations[active_id]["messages"] = messages
        st.session_state.conversations[active_id]["message_count"] = len(messages)


def switch_conversation(conv_id: str) -> None:
    """
    Chuyển sang xem một cuộc trò chuyện khác.
    Thao tác đọc thuần từ DB, cập nhật URL param.

    Args:
        conv_id: UUID cuộc trò chuyện đích.
    """
    st.session_state.active_conv_id = conv_id
    st.query_params["c"] = conv_id
    st.session_state.view_mode = "chat"
    st.session_state.confirm_delete = False
    reload_active_conversation_messages()


def create_new_conversation(title: str = "Cuộc trò chuyện mới") -> dict[str, Any]:
    """
    Tạo cuộc trò chuyện mới, lưu vào PostgreSQL và chuyển giao diện sang trạng thái rỗng.

    Args:
        title: Tiêu đề cuộc trò chuyện.

    Returns:
        dict: Cuộc trò chuyện mới tạo.
    """
    new_conv = api_create_conversation(title=title)
    new_id = new_conv["id"]
    new_obj = {
        "id": new_id,
        "title": new_conv.get("title") or title,
        "updated_at": new_conv.get("updated_at") or datetime.now().isoformat(),
        "created_at": new_conv.get("created_at") or datetime.now().isoformat(),
        "message_count": 0,
        "messages": [],
    }

    if "conversations" not in st.session_state:
        st.session_state.conversations = {}

    # Đưa lên đầu dict
    updated_dict = {new_id: new_obj}
    updated_dict.update(st.session_state.conversations)
    st.session_state.conversations = updated_dict

    st.session_state.active_conv_id = new_id
    st.query_params["c"] = new_id
    st.session_state.messages = []
    st.session_state.current_loaded_cid = new_id
    st.session_state.active_citation_index = None
    st.session_state.view_mode = "chat"
    st.session_state.confirm_delete = False
    return new_obj


def get_current_conversation() -> dict[str, Any]:
    """
    Lấy thông tin cuộc trò chuyện hiện tại kèm danh sách tin nhắn.

    Returns:
        dict: Thông tin cuộc trò chuyện hiện tại.
    """
    cid = st.session_state.get("active_conv_id")
    conv_dict = st.session_state.get("conversations", {})
    if cid and cid in conv_dict:
        target = conv_dict[cid]
        target["messages"] = st.session_state.get("messages", [])
        return target

    return {
        "id": None,
        "title": "Cuộc trò chuyện mới",
        "messages": st.session_state.get("messages", []),
    }


def delete_conversation(conv_id: str) -> None:
    """
    Xóa một phiên hội thoại cụ thể theo ID.

    Args:
        conv_id: UUID cuộc trò chuyện cần xóa.
    """
    api_delete_conversation(conv_id)
    if "conversations" in st.session_state and conv_id in st.session_state.conversations:
        del st.session_state.conversations[conv_id]

    remaining_ids = (
        list(st.session_state.conversations.keys())
        if "conversations" in st.session_state
        else []
    )
    if remaining_ids:
        if st.session_state.get("active_conv_id") == conv_id:
            st.session_state.active_conv_id = remaining_ids[0]
            st.query_params["c"] = remaining_ids[0]
            reload_active_conversation_messages()
    else:
        st.session_state.active_conv_id = None
        st.session_state.messages = []
        st.session_state.current_loaded_cid = None
        if "c" in st.query_params:
            del st.query_params["c"]

    st.session_state.confirm_delete = False


def delete_current_conversation() -> None:
    """Xóa cuộc trò chuyện đang kích hoạt khỏi cơ sở dữ liệu."""
    active_id = st.session_state.get("active_conv_id")
    if active_id:
        delete_conversation(active_id)


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
    Thêm tin nhắn vào cuộc trò chuyện hiện tại (lưu DB và cập nhật state).

    Args:
        role: "user" hoặc "assistant".
        content: Nội dung tin nhắn.
        sources: Danh sách trích dẫn.
        response_time_ms: Thời gian phản hồi tính bằng ms.
        query_type: Loại câu hỏi.
        fallback_used: Có sử dụng search fallback hay không.
        citation_audit: Thẩm định trích dẫn.
        error: Chi tiết lỗi nếu có.
    """
    cid = st.session_state.get("active_conv_id")
    if not cid:
        new_c = create_new_conversation()
        cid = new_c["id"]

    req_id = f"req_{datetime.now().strftime('%H%M%S')}"

    if role == "user":
        try:
            db_save_user_message(conversation_id=cid, content=content, request_id=req_id)
        except Exception as e:
            logger.warning("Không thể lưu user message vào DB trong add_message_to_current: %s", e)
    else:
        try:
            db_save_assistant_message(
                conversation_id=cid,
                content=content,
                request_id=req_id,
                query_type=query_type,
                latency_ms=response_time_ms,
                fallback_used=fallback_used,
                citations=sources or [],
                metadata={"citation_audit": citation_audit, "error": error},
            )
        except Exception as e:
            logger.warning("Không thể lưu assistant message vào DB trong add_message_to_current: %s", e)

    # Cập nhật state nội bộ
    if "messages" not in st.session_state:
        st.session_state.messages = []

    msg_obj = {
        "role": role,
        "content": content,
        "sources": sources or [],
        "citations": sources or [],
        "response_time_ms": response_time_ms,
        "query_type": query_type,
        "fallback_used": fallback_used,
        "citation_audit": citation_audit,
        "error": error,
        "created_at": datetime.now().isoformat(),
    }
    st.session_state.messages.append(msg_obj)

    # Cập nhật vào đối tượng conversation trong dict
    if cid in st.session_state.conversations:
        conv_obj = st.session_state.conversations[cid]
        if "messages" not in conv_obj:
            conv_obj["messages"] = []
        if msg_obj not in conv_obj["messages"]:
            conv_obj["messages"].append(msg_obj)
        conv_obj["message_count"] = len(conv_obj["messages"])

        # Nếu là câu hỏi đầu tiên của người dùng, cập nhật tiêu đề tất định
        if role == "user" and len(conv_obj["messages"]) == 1:
            conv_obj["title"] = generate_title_from_question(content)


def toggle_theme_mode() -> None:
    """Cố định chế độ tối (dark mode) mặc định cho toàn bộ ứng dụng."""
    st.session_state.theme_mode = "dark"


def set_active_citation(index: Optional[int]) -> None:
    """Thiết lập chỉ mục trích dẫn đang chọn để đối chiếu."""
    st.session_state.active_citation_index = index


# =========================================================================
# HELPER PHÂN NHÓM VÀ HIỂN THỊ THỜI GIAN
# =========================================================================


def group_conversations_by_date(
    conversations: Any,
) -> dict[str, list[dict[str, Any]]]:
    """
    Phân nhóm danh sách hội thoại theo 4 mốc thời gian chuẩn yêu cầu:
    1. HÔM NAY
    2. HÔM QUA
    3. 7 NGÀY TRƯỚC
    4. CŨ HƠN

    Args:
        conversations: Danh sách hoặc dict các bản ghi tóm tắt hội thoại.

    Returns:
        dict: Mapping từ tên nhóm sang danh sách cuộc trò chuyện.
    """
    if isinstance(conversations, dict):
        conv_items = list(conversations.values())
    else:
        conv_items = list(conversations)

    groups: dict[str, list[dict[str, Any]]] = {
        "HÔM NAY": [],
        "HÔM QUA": [],
        "7 NGÀY TRƯỚC": [],
        "CŨ HƠN": [],
    }

    now_utc = datetime.now(timezone.utc)
    today = now_utc.date()

    for conv in conv_items:
        time_str = conv.get("updated_at") or conv.get("created_at")
        try:
            if isinstance(time_str, str):
                dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
            else:
                dt = time_str
            conv_date = dt.astimezone(timezone.utc).date()
            diff_days = (today - conv_date).days
        except Exception:
            diff_days = 999

        if diff_days <= 0:
            groups["HÔM NAY"].append(conv)
        elif diff_days == 1:
            groups["HÔM QUA"].append(conv)
        elif 2 <= diff_days <= 7:
            groups["7 NGÀY TRƯỚC"].append(conv)
        else:
            groups["CŨ HƠN"].append(conv)

    return groups


def format_relative_time(time_str: Optional[str]) -> str:
    """
    Định dạng chuỗi thời gian thân thiện (ví dụ: '5m', '2h', '1d', '12/09').

    Args:
        time_str: Chuỗi ISO timestamp.

    Returns:
        str: Chuỗi nhãn thời gian ngắn gọn.
    """
    if not time_str:
        return ""
    try:
        dt = datetime.fromisoformat(time_str.replace("Z", "+00:00"))
        now = datetime.now(timezone.utc)
        diff = now - dt
        total_seconds = int(diff.total_seconds())

        if total_seconds < 60:
            return "Vừa xong"
        if total_seconds < 3600:
            minutes = total_seconds // 60
            return f"{minutes}m"
        if total_seconds < 86400:
            hours = total_seconds // 3600
            return f"{hours}h"
        days = total_seconds // 86400
        if days == 1:
            return "1d"
        if days < 7:
            return f"{days}d"
        return dt.strftime("%d/%m")
    except Exception:
        return ""
