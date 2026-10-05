"""Integration tests cho toàn bộ hệ thống API lưu trữ hội thoại và tin nhắn.

Bao gồm:
1. Tạo cuộc trò chuyện (POST /conversations)
2. Lấy danh sách tóm tắt (GET /conversations)
3. Lưu tin nhắn người dùng và trợ lý qua pipeline (POST /conversations/{id}/messages)
4. Tải tin nhắn (GET /conversations/{id}/messages)
5. Xóa cuộc trò chuyện và cascade delete (DELETE /conversations/{id})
6. Từ chối ID không hợp lệ (404 Not Found)
7. ĐẶC BIỆT QUAN TRỌNG: Thao tác tải lịch sử hội thoại (GET /conversations/{id}/messages)
   TUYỆT ĐỐI KHÔNG GỌI RAG / EMBEDDING / LLM.
"""

from unittest.mock import MagicMock, patch
from fastapi.testclient import TestClient
import pytest

from backend.main import app

client = TestClient(app)


def test_create_and_list_conversations():
    """Kiểm tra API tạo và liệt kê danh sách tóm tắt cuộc trò chuyện."""
    # 1. Tạo conversation mới
    resp_create = client.post("/conversations", json={"title": "Hội thoại API Test"})
    assert resp_create.status_code == 201
    created_data = resp_create.json()
    conv_id = created_data["id"]
    assert conv_id is not None
    assert created_data["title"] == "Hội thoại API Test"
    assert created_data["message_count"] == 0

    try:
        # 2. Liệt kê danh sách hội thoại
        resp_list = client.get("/conversations")
        assert resp_list.status_code == 200
        convs = resp_list.json()
        assert any(c["id"] == conv_id for c in convs)

        # 3. Lấy chi tiết conversation theo ID
        resp_detail = client.get(f"/conversations/{conv_id}")
        assert resp_detail.status_code == 200
        assert resp_detail.json()["id"] == conv_id
    finally:
        # Dọn dẹp
        client.delete(f"/conversations/{conv_id}")


def test_reject_invalid_conversation_id():
    """Kiểm tra hệ thống trả về 404 cho conversation ID không hợp lệ."""
    invalid_id = "00000000-0000-0000-0000-000000000000"
    resp = client.get(f"/conversations/{invalid_id}")
    assert resp.status_code == 404

    resp_msgs = client.get(f"/conversations/{invalid_id}/messages")
    assert resp_msgs.status_code == 404

    resp_send = client.post(
        f"/conversations/{invalid_id}/messages",
        json={"content": "Câu hỏi thử nghiệm"},
    )
    assert resp_send.status_code == 404


def test_send_message_flow_and_persistence():
    """Kiểm tra toàn bộ luồng gửi tin nhắn, lưu trữ RAG và trích dẫn citations."""
    # 1. Tạo conversation
    resp_create = client.post("/conversations", json={"title": "Cuộc trò chuyện mới"})
    conv_id = resp_create.json()["id"]

    mock_rag_result = {
        "answer": "Sinh viên cần hoàn thành tối thiểu 130 tín chỉ để được xét tốt nghiệp.",
        "sources": [
            {
                "chunk_id": 42,
                "citation": "630/QĐ-ĐHCN - Điều 7, Khoản 1",
                "ma_van_ban": "630/QĐ-ĐHCN",
                "ten_van_ban": "Quy chế đào tạo đại học",
                "dieu": "7",
                "khoan": "1",
                "distance": 0.12,
                "source_type": "database",
                "content": "Điều kiện tốt nghiệp đại học...",
            }
        ],
        "response_time_ms": 1100,
        "query_type": "factual",
        "fallback_used": False,
        "citation_audit": {"status": "verified"},
    }

    try:
        # Mock rag_query để test độc lập không phụ thuộc vào network Gemini ngoài
        with patch("backend.api.conversations.rag_query", return_value=mock_rag_result):
            send_resp = client.post(
                f"/conversations/{conv_id}/messages",
                json={"content": "Cho em hỏi điều kiện tốt nghiệp đại học?", "top_k": 5},
            )

        assert send_resp.status_code == 200
        data = send_resp.json()

        # Kiểm tra dữ liệu phản hồi
        assert "message" in data
        assert data["message"]["role"] == "assistant"
        assert "130 tín chỉ" in data["message"]["content"]
        assert len(data["citations"]) == 1
        assert data["citations"][0]["ma_van_ban"] == "630/QĐ-ĐHCN"
        assert data["fallback_used"] is False
        assert data["request_id"].startswith("req_")
        assert data["latency_ms"] >= 0

        # Kiểm tra tiêu đề hội thoại được cập nhật tự động từ câu hỏi đầu tiên
        detail_resp = client.get(f"/conversations/{conv_id}")
        assert detail_resp.status_code == 200
        conv_meta = detail_resp.json()
        assert conv_meta["message_count"] == 2
        assert "tốt nghiệp" in conv_meta["title"].lower()

        # Kiểm tra gửi feedback cho tin nhắn trợ lý
        ast_msg_id = data["message"]["id"]
        fb_resp = client.post(
            f"/conversations/{conv_id}/messages/{ast_msg_id}/feedback",
            json={"rating": "positive", "comment": "Chính xác"},
        )
        assert fb_resp.status_code == 200

    finally:
        client.delete(f"/conversations/{conv_id}")


def test_opening_existing_conversation_does_not_call_rag():
    """
    KIỂM TRA BẮT BUỘC THEO SECTION 32:
    Khi người dùng mở một cuộc hội thoại cũ (GET /conversations/{id}/messages):
    - ĐỌC THUẦN CƠ SỞ DỮ LIỆU
    - TUYỆT ĐỐI KHÔNG GỌI rag_query
    - TUYỆT ĐỐI KHÔNG GỌI get_embedding
    - TUYỆT ĐỐI KHÔNG TIÊU TỐN QUOTA AI
    """
    # 1. Tạo conversation và nạp dữ liệu tin nhắn mẫu
    resp_create = client.post("/conversations", json={"title": "Lịch sử đã lưu"})
    conv_id = resp_create.json()["id"]

    mock_rag_result = {
        "answer": "Câu trả lời đã được lưu trữ sẵn từ trước.",
        "sources": [
            {
                "chunk_id": 99,
                "citation": "41/QĐ-ĐHCN - Điều 3",
                "ma_van_ban": "41/QĐ-ĐHCN",
                "ten_van_ban": "Quy định",
                "dieu": "3",
                "khoan": "1",
                "distance": 0.15,
                "source_type": "database",
            }
        ],
        "response_time_ms": 900,
        "query_type": "factual",
        "fallback_used": False,
    }

    try:
        # Gửi tin nhắn lần đầu để lưu vào DB
        with patch("backend.api.conversations.rag_query", return_value=mock_rag_result):
            client.post(
                f"/conversations/{conv_id}/messages",
                json={"content": "Câu hỏi lưu trữ mẫu"},
            )

        # 2. Bây giờ giả lập hành vi người dùng click chọn xem lại cuộc trò chuyện từ Sidebar
        # Chúng ta mock RAG pipeline và Embedding model để kiểm chứng
        with patch("backend.api.conversations.rag_query") as mock_rag, \
             patch("haui_rag.core.embedding.get_embedding") as mock_embed:

            # Gọi endpoint GET /conversations/{id}/messages
            get_msgs_resp = client.get(f"/conversations/{conv_id}/messages")

            # Đảm bảo trả về dữ liệu thành công
            assert get_msgs_resp.status_code == 200
            stored_msgs = get_msgs_resp.json()
            assert len(stored_msgs) == 2
            assert stored_msgs[0]["role"] == "user"
            assert stored_msgs[1]["role"] == "assistant"
            assert len(stored_msgs[1]["citations"]) == 1
            assert stored_msgs[1]["citations"][0]["ma_van_ban"] == "41/QĐ-ĐHCN"

            # KHẲNG ĐỊNH: RAG pipeline và Embedding KHÔNG BAO GIỜ được gọi!
            mock_rag.assert_not_called()
            mock_embed.assert_not_called()

    finally:
        client.delete(f"/conversations/{conv_id}")


def test_delete_conversation_cascades_messages():
    """Kiểm tra khi xóa conversation thì toàn bộ tin nhắn liên quan cũng bị xóa sạch."""
    resp_create = client.post("/conversations", json={"title": "Để xóa"})
    conv_id = resp_create.json()["id"]

    mock_rag_result = {
        "answer": "Sẽ bị xóa cùng conversation.",
        "sources": [],
        "response_time_ms": 500,
        "query_type": "factual",
        "fallback_used": False,
    }

    with patch("backend.api.conversations.rag_query", return_value=mock_rag_result):
        client.post(f"/conversations/{conv_id}/messages", json={"content": "Tin nhắn tạm"})

    # Xóa conversation
    resp_del = client.delete(f"/conversations/{conv_id}")
    assert resp_del.status_code == 200

    # Kiểm tra conversation không còn tìm thấy
    assert client.get(f"/conversations/{conv_id}").status_code == 404

    # Kiểm tra endpoint messages cũng trả về 404
    assert client.get(f"/conversations/{conv_id}/messages").status_code == 404
