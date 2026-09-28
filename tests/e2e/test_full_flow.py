"""E2E tests kiểm tra toàn bộ luồng hệ thống từ API đến RAG."""

from fastapi.testclient import TestClient
from backend.main import app

client = TestClient(app)


def test_full_system_flow():
    """Kiểm tra toàn bộ luồng từ HTTP Client đến RAG và response."""
    response = client.post(
        "/api/chat",
        json={"question": "Điều kiện tốt nghiệp thạc sĩ là gì?", "top_k": 3},
    )
    assert response.status_code == 200
    data = response.json()
    assert bool(data["answer"])
    assert isinstance(data["sources"], list)
    assert len(data["sources"]) > 0
    assert data["response_time_ms"] > 0
    assert "query_type" in data
