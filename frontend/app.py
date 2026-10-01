"""Giao diện người dùng Streamlit cho Trợ lý AI Tra cứu Quy chế HaUI (haui_rag)."""

import json
import os
import sys
import time
from pathlib import Path
from typing import Any

import requests
import streamlit as st

# Thêm thư mục gốc vào sys.path để có thể import haui_rag
ROOT_DIR = Path(__file__).resolve().parent.parent
if str(ROOT_DIR) not in sys.path:
    sys.path.insert(0, str(ROOT_DIR))

from haui_rag.config import (
    BACKEND_HOST,
    BACKEND_PORT,
    DEFAULT_TOP_K,
    EMBEDDING_MODEL,
    LLM_MODEL,
)

API_URL = f"http://{BACKEND_HOST}:{BACKEND_PORT}/api/chat"
HEALTH_URL = f"http://{BACKEND_HOST}:{BACKEND_PORT}/"

# Cấu hình trang Streamlit
st.set_page_config(
    page_title="HaUI Regulation Assistant - haui_rag",
    layout="wide",
    initial_sidebar_state="expanded",
)

# Custom CSS cho giao diện hiện đại, chuyên nghiệp
st.markdown(
    """
    <style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 700;
        color: #1E3A8A;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        font-size: 1.05rem;
        color: #4B5563;
        margin-bottom: 1.5rem;
    }
    .source-box {
        background-color: #F8FAFC;
        border-left: 4px solid #3B82F6;
        padding: 10px 14px;
        margin-top: 8px;
        border-radius: 4px;
        font-size: 0.9rem;
    }
    .badge-status {
        display: inline-block;
        padding: 4px 10px;
        border-radius: 9999px;
        font-size: 0.8rem;
        font-weight: 600;
    }
    .badge-online {
        background-color: #DCFCE7;
        color: #166534;
    }
    .badge-offline {
        background-color: #FEE2E2;
        color: #991B1B;
    }
    </style>
    """,
    unsafe_allow_html=True,
)


def check_backend_health() -> tuple[bool, dict[str, Any]]:
    """Kiểm tra tình trạng kết nối tới Backend server."""
    try:
        res = requests.get(HEALTH_URL, timeout=5)
        if res.status_code == 200:
            return True, res.json()
        return False, {}
    except Exception:
        return False, {}


def query_chat_api(question: str, top_k: int) -> dict[str, Any]:
    """
    Gửi câu hỏi tới FastAPI backend, nếu backend không chạy thì fallback trực tiếp gọi rag_query.
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
    except Exception:
        pass

    # 2. Fallback trực tiếp gọi haui_rag.core.rag_pipeline
    try:
        from haui_rag.core.rag_pipeline import rag_query
        return rag_query(query=question, top_k=top_k)
    except Exception as e:
        return {
            "answer": f"Không thể xử lý yêu cầu: {str(e)}",
            "sources": [],
            "response_time_ms": 0,
            "error": str(e),
        }


# Khởi tạo session state
if "messages" not in st.session_state:
    st.session_state.messages = [
        {
            "role": "assistant",
            "content": (
                "Xin chào! Tôi là Trợ lý AI hỗ trợ tra cứu văn bản, quy chế và quy định của "
                "Trường Đại học Công nghiệp Hà Nội (HaUI).\n\n"
                "Tôi có thể giúp bạn giải đáp các quy định về tuyển sinh, đào tạo đại học, "
                "thạc sĩ, điều kiện tốt nghiệp, bảo lưu, chuyển ngành...\n\n"
                "Bạn có câu hỏi gì cần tra cứu hôm nay?"
            ),
            "sources": [],
            "response_time_ms": 0,
        }
    ]

if "pending_question" not in st.session_state:
    st.session_state.pending_question = None

# Khu vực Sidebar cấu hình và câu hỏi gợi ý
with st.sidebar:
    st.image(
        "https://upload.wikimedia.org/wikipedia/vi/2/23/Logo_%C4%90%E1%BA%A1i_h%E1%BB%8Dc_C%C3%B4ng_nghi%E1%BB%87p_H%C3%A0_N%E1%BB%99i.png",
        width=120,
    )
    st.title("HaUI RAG Assistant")
    st.caption("Dự án: **haui_rag v0.1.0**")

    # Kiểm tra trạng thái Backend
    is_online, health_data = check_backend_health()
    if is_online:
        st.markdown(
            '<span class="badge-status badge-online">Backend: Online (Port 8000)</span>',
            unsafe_allow_html=True,
        )
        st.caption(f"DB: {health_data.get('total_documents', '1714+')} chunks")
    else:
        st.markdown(
            '<span class="badge-status badge-offline">Backend: Offline (Che do Direct Mode)</span>',
            unsafe_allow_html=True,
        )

    st.markdown("---")
    st.subheader("Cấu hình truy vấn")
    top_k_val = st.slider(
        "Số lượng văn bản tham chiếu (Top K):",
        min_value=1,
        max_value=10,
        value=DEFAULT_TOP_K,
        step=1,
    )


    st.markdown("---")
    st.subheader("Câu hỏi gợi ý")
    sample_questions = [
        "Điều kiện tốt nghiệp thạc sĩ là gì?",
        "Thời gian đào tạo trình độ thạc sĩ là bao lâu?",
        "Quy định về bảo lưu kết quả học tập?",
        "Học viên bị cảnh báo học tập trong trường hợp nào?",
        "Chuẩn đầu ra ngoại ngữ bậc thạc sĩ yêu cầu gì?",
    ]

    for sq in sample_questions:
        if st.button(sq, key=f"sq_{sq}", use_container_width=True):
            st.session_state.pending_question = sq

    st.markdown("---")
    if st.button("Xóa lịch sử trò chuyện", use_container_width=True, type="secondary"):
        st.session_state.messages = [
            {
                "role": "assistant",
                "content": "Lịch sử trò chuyện đã được làm mới. Bạn muốn tra cứu quy chế nào?",
                "sources": [],
                "response_time_ms": 0,
            }
        ]
        st.rerun()

# Khu vực hội thoại chính
st.markdown('<div class="main-title">Trợ lý AI Tra Cứu Quy Chế HaUI</div>', unsafe_allow_html=True)
st.markdown(
    '<div class="sub-title">Hệ thống hỏi đáp chính xác dựa trên cơ sở dữ liệu các Quyết định và Quy chế chính thức của Trường Đại học Công nghiệp Hà Nội.</div>',
    unsafe_allow_html=True,
)

# Hiển thị lịch sử tin nhắn
for idx, msg in enumerate(st.session_state.messages):
    with st.chat_message(msg["role"]):
        st.markdown(msg["content"])

        # Nếu có sources và là tin nhắn của assistant
        if msg.get("sources"):
            with st.expander(f"Xem {len(msg['sources'])} nguồn văn bản trích dẫn", expanded=False):
                for s_idx, src in enumerate(msg["sources"], start=1):
                    citation = src.get("citation", "Quy chế HaUI")
                    distance = src.get("distance")
                    source_type = src.get("source_type") or ("web" if distance is None else "database")
                    content = src.get("content", "")
                    ten_vb = src.get("ten_van_ban") or ""

                    if source_type == "web" or distance is None:
                        st.markdown(f"**{s_idx}. {citation}** *(Nguồn: Cổng thông tin HaUI)*")
                    else:
                        st.markdown(f"**{s_idx}. {citation}** *(Khoảng cách vector: `{distance}`)*")
                    if ten_vb:
                        st.caption(f"Tên văn bản: {ten_vb}")
                    if content:
                        st.text_area(
                            label=f"Nội dung trích đoạn ({citation}):",
                            value=content.strip(),
                            height=100,
                            key=f"content_{idx}_{s_idx}",
                            disabled=True,
                        )
                    st.divider()

        if msg.get("response_time_ms"):
            st.caption(f"Thời gian phản hồi: {msg['response_time_ms']} ms")

# Xử lý input từ chat box hoặc nút câu hỏi gợi ý
user_input = st.chat_input("Nhập câu hỏi của bạn về quy chế, quy định HaUI...")
if st.session_state.pending_question:
    user_input = st.session_state.pending_question
    st.session_state.pending_question = None

if user_input:
    # 1. Thêm tin nhắn người dùng vào lịch sử
    st.session_state.messages.append({"role": "user", "content": user_input})
    with st.chat_message("user"):
        st.markdown(user_input)

    # 2. Xử lý câu trả lời từ Assistant
    with st.chat_message("assistant"):
        with st.spinner("Đang tra cứu cơ sở dữ liệu quy chế và tổng hợp câu trả lời..."):
            response_data = query_chat_api(user_input, top_k_val)

        answer_text = response_data.get("answer", "Xin lỗi, không nhận được phản hồi.")
        sources_list = response_data.get("sources", [])
        resp_time = response_data.get("response_time_ms", 0)
        fallback_used = response_data.get("fallback_used", False)
        q_type = response_data.get("query_type")

        if fallback_used:
            st.info("Đã kích hoạt Search Fallback: Tra cứu bổ sung từ Cổng thông tin haui.edu.vn")

        st.markdown(answer_text)

        if sources_list:
            expander_title = "Nguồn từ Cổng thông tin HaUI" if fallback_used else f"Xem {len(sources_list)} nguồn văn bản trích dẫn"
            with st.expander(expander_title, expanded=False):
                for s_idx, src in enumerate(sources_list, start=1):
                    citation = src.get("citation", "Quy chế HaUI")
                    distance = src.get("distance", 0.0)
                    content = src.get("content", "")
                    st.markdown(f"**{s_idx}. {citation}** *(Khoảng cách: `{distance}`)*")
                    if content:
                        st.caption(content[:300] + ("..." if len(content) > 300 else ""))
                    st.divider()

        if resp_time:
            st.caption(f"Thời gian phản hồi: {resp_time} ms")

        # Nút đánh giá phản hồi
        col_fb1, col_fb2, _ = st.columns([1, 1, 8])
        with col_fb1:
            if st.button("Hữu ích", key=f"like_{len(st.session_state.messages)}"):
                st.toast("Cảm ơn bạn đã phản hồi tích cực.")
        with col_fb2:
            if st.button("Chưa đúng", key=f"dislike_{len(st.session_state.messages)}"):
                st.toast("Cảm ơn bạn. Chúng tôi sẽ cải thiện nguồn trích dẫn.")

    # 3. Lưu vào lịch sử
    st.session_state.messages.append(
        {
            "role": "assistant",
            "content": answer_text,
            "sources": sources_list,
            "response_time_ms": resp_time,
        }
    )
