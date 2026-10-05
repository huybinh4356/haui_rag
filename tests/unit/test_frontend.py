"""Unit tests cho kiến trúc Frontend, Theme Mode và State Management của haui_rag."""

import pytest
import streamlit as st

from frontend.state.session import (
    add_message_to_current,
    create_new_conversation,
    delete_conversation,
    get_current_conversation,
    init_session_state,
    set_active_citation,
    switch_conversation,
    toggle_theme_mode,
)
from frontend.styles.theme import (
    DARK_THEME,
    LIGHT_THEME,
    get_theme_css,
)


@pytest.fixture(autouse=True)
def reset_streamlit_session():
    """Reset session_state trước mỗi test case."""
    st.session_state.clear()
    yield
    st.session_state.clear()


def test_init_session_state():
    """Kiểm tra khởi tạo trạng thái mặc định của ứng dụng."""
    init_session_state()

    assert "conversations" in st.session_state
    assert len(st.session_state.conversations) >= 1
    assert "active_conv_id" in st.session_state
    assert st.session_state.theme_mode == "light"
    assert st.session_state.view_mode == "chat"
    assert st.session_state.top_k == 5
    assert st.session_state.user_mode == "simple"
    assert st.session_state.active_citation_index is None


def test_toggle_theme_mode():
    """Kiểm tra chức năng chuyển đổi qua lại giữa giao diện Sáng và Tối."""
    init_session_state()
    assert st.session_state.theme_mode == "light"

    toggle_theme_mode()
    assert st.session_state.theme_mode == "dark"

    toggle_theme_mode()
    assert st.session_state.theme_mode == "light"


def test_theme_css_generation():
    """Kiểm tra CSS sinh ra cho cả Light Mode và Dark Mode."""
    css_light = get_theme_css("light")
    assert LIGHT_THEME["bg_page"] in css_light
    assert LIGHT_THEME["primary_blue"] in css_light

    css_dark = get_theme_css("dark")
    assert DARK_THEME["bg_page"] in css_dark
    assert DARK_THEME["text_main"] in css_dark
    assert "--bg-page" in css_dark


def test_create_and_switch_conversation():
    """Kiểm tra tạo mới và chuyển đổi giữa các phiên hội thoại."""
    init_session_state()
    initial_id = st.session_state.active_conv_id
    initial_count = len(st.session_state.conversations)

    # Tạo hội thoại mới
    new_conv = create_new_conversation(title="Tra cứu học phí")
    new_id = new_conv["id"]

    assert new_id != initial_id
    assert st.session_state.active_conv_id == new_id
    assert len(st.session_state.conversations) == initial_count + 1

    # Chuyển về hội thoại cũ
    switch_conversation(initial_id)
    assert st.session_state.active_conv_id == initial_id


def test_delete_conversation():
    """Kiểm tra xóa phiên hội thoại và tự động gán phiên kích hoạt mới."""
    init_session_state()
    c1 = create_new_conversation("Hội thoại 1")
    c2 = create_new_conversation("Hội thoại 2")

    delete_conversation(c2["id"])
    assert c2["id"] not in st.session_state.conversations
    assert st.session_state.active_conv_id in st.session_state.conversations


def test_add_message_and_auto_title():
    """Kiểm tra thêm tin nhắn và tự động đặt tên hội thoại theo câu hỏi đầu tiên."""
    init_session_state()
    c = create_new_conversation("Cuộc trò chuyện mới")
    assert len(c["messages"]) == 0

    first_question = "Điều kiện để sinh viên được xét tốt nghiệp ra trường sớm?"
    add_message_to_current(role="user", content=first_question)

    # Tiêu đề phải được cập nhật tự động từ câu hỏi
    assert c["title"].startswith("Điều kiện để sinh viên")
    assert len(c["messages"]) == 1

    # Thêm câu trả lời của trợ lý kèm nguồn trích dẫn
    sample_sources = [
        {
            "chunk_id": 12,
            "citation": "[630/QĐ-ĐHCN] - Điều 7, Khoản 1",
            "ma_van_ban": "630/QĐ-ĐHCN",
            "ten_van_ban": "Quy chế đào tạo thạc sĩ",
            "dieu": "7",
            "khoan": "1",
            "content": "Sinh viên phải hoàn thành toàn bộ khối lượng tín chỉ...",
        }
    ]
    add_message_to_current(
        role="assistant",
        content="Theo quy định tại Quyết định 630...",
        sources=sample_sources,
        response_time_ms=850,
    )

    assert len(c["messages"]) == 2
    assert c["messages"][1]["sources"] == sample_sources
    assert c["messages"][1]["response_time_ms"] == 850


def test_active_citation_selection():
    """Kiểm tra gán và giải phóng trích dẫn nguồn được chọn."""
    init_session_state()
    assert st.session_state.active_citation_index is None

    set_active_citation(2)
    assert st.session_state.active_citation_index == 2

    set_active_citation(None)
    assert st.session_state.active_citation_index is None
