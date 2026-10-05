"""Unit tests cho các hàm nghiệp vụ hội thoại trong haui_rag.db.conversation_queries."""

import pytest
from haui_rag.db.conversation_queries import (
    create_conversation,
    delete_conversation,
    generate_title_from_question,
    get_conversation,
    get_conversation_messages,
    list_conversations,
    save_assistant_message,
    save_feedback,
    save_request_log,
    save_user_message,
)


def test_generate_deterministic_title_basic():
    """Kiểm tra sinh tiêu đề tất định không dùng AI/LLM."""
    # Test case 1: Câu hỏi bình thường
    q1 = "Điều kiện để được xét tốt nghiệp đối với sinh viên năm cuối là gì?"
    t1 = generate_title_from_question(q1)
    assert len(t1) <= 52
    assert "tốt nghiệp" in t1.lower()

    # Test case 2: Cắt bỏ lời thưa gửi
    q2 = "Thầy cô cho em hỏi quy định học phí kỳ 2?"
    t2 = generate_title_from_question(q2)
    assert not t2.lower().startswith("thầy cô cho em hỏi")
    assert "quy định học phí" in t2.lower()

    # Test case 3: Câu hỏi ngắn
    q3 = "Học phí?"
    t3 = generate_title_from_question(q3)
    assert t3 == "Học phí?"

    # Test case 4: Rỗng
    assert generate_title_from_question("") == "Cuộc trò chuyện mới"
    assert generate_title_from_question("   ") == "Cuộc trò chuyện mới"


def test_conversation_crud_and_cascade_lifecycle():
    """Kiểm tra chu trình tạo, lưu tin nhắn, đọc và xóa cascade của hội thoại trong DB."""
    # 1. Tạo conversation
    conv = create_conversation("Phiên kiểm thử tự động")
    conv_id = conv["id"]
    assert conv_id is not None
    assert conv["title"] == "Phiên kiểm thử tự động"
    assert conv["message_count"] == 0

    try:
        # 2. Lưu tin nhắn User đầu tiên -> Tự động sinh tiêu đề mới
        req_id = "req_test_001"
        u_msg = save_user_message(
            conversation_id=conv_id,
            content="Cho em hỏi điều kiện bảo lưu kết quả học tập tại HaUI?",
            request_id=req_id,
        )
        assert u_msg["id"] is not None
        assert u_msg["role"] == "user"
        assert u_msg["request_id"] == req_id

        # Kiểm tra tiêu đề và message_count được cập nhật
        updated_conv = get_conversation(conv_id)
        assert updated_conv["message_count"] == 1
        assert "bảo lưu kết quả học tập" in updated_conv["title"].lower()

        # 3. Lưu tin nhắn Assistant kèm trích dẫn cấu trúc
        citations = [
            {
                "chunk_id": 101,
                "citation": "630/QĐ-ĐHCN - Điều 7, Khoản 2",
                "ma_van_ban": "630/QĐ-ĐHCN",
                "ten_van_ban": "Quy chế đào tạo",
                "dieu": "7",
                "khoan": "2",
                "source_type": "database",
            }
        ]
        a_msg = save_assistant_message(
            conversation_id=conv_id,
            content="Theo quy chế 630/QĐ-ĐHCN, sinh viên được bảo lưu tối đa 2 học kỳ.",
            request_id=req_id,
            query_type="factual",
            latency_ms=1250,
            fallback_used=False,
            citations=citations,
            metadata={"audit": "passed"},
        )
        assert a_msg["id"] is not None
        assert a_msg["role"] == "assistant"
        assert len(a_msg["citations"]) == 1
        assert a_msg["citations"][0]["ma_van_ban"] == "630/QĐ-ĐHCN"
        assert a_msg["latency_ms"] == 1250
        assert a_msg["fallback_used"] is False

        # Kiểm tra message_count = 2
        conv_after_ast = get_conversation(conv_id)
        assert conv_after_ast["message_count"] == 2

        # 4. Đọc lại danh sách tin nhắn (Pure DB Read)
        msgs = get_conversation_messages(conv_id)
        assert len(msgs) == 2
        assert msgs[0]["role"] == "user"
        assert msgs[1]["role"] == "assistant"
        assert msgs[1]["citations"][0]["dieu"] == "7"

        # 5. Lưu feedback cho tin nhắn trợ lý
        fb = save_feedback(
            message_id=a_msg["id"],
            rating="positive",
            comment="Câu trả lời rất rõ ràng",
        )
        assert fb["id"] is not None
        assert fb["rating"] == "helpful" or fb["rating"] == "positive"

        # 6. Ghi request log
        save_request_log(
            request_id=req_id,
            conversation_id=conv_id,
            endpoint="/conversations/{id}/messages",
            status_code=200,
            latencies={"total_latency_ms": 1250},
            fallback_used=False,
        )

    finally:
        # 7. Xóa hội thoại và kiểm tra CASCADE DELETE
        deleted = delete_conversation(conv_id)
        assert deleted is True

        # Đảm bảo conversation không còn tồn tại
        assert get_conversation(conv_id) is None

        # Đảm bảo toàn bộ tin nhắn liên quan cũng bị xóa cascade
        remaining_msgs = get_conversation_messages(conv_id)
        assert len(remaining_msgs) == 0


def test_reject_invalid_conversation_id():
    """Kiểm tra xử lý lỗi khi thao tác với ID cuộc trò chuyện không tồn tại."""
    fake_uuid = "00000000-0000-0000-0000-000000000000"
    assert get_conversation(fake_uuid) is None
    assert delete_conversation(fake_uuid) is False

    with pytest.raises(ValueError):
        save_user_message(fake_uuid, "Câu hỏi lỗi")
