"""Fixtures dùng chung cho toàn bộ test suite."""

import sys
from pathlib import Path
import pytest

# Đảm bảo src luôn có trong sys.path
SRC_PATH = Path(__file__).resolve().parent.parent / "src"
if str(SRC_PATH) not in sys.path:
    sys.path.insert(0, str(SRC_PATH))

from haui_rag.core.embedding import get_embedding


@pytest.fixture
def sample_chunks():
    """Sample chunks chuẩn cho unit/integration testing."""
    return [
        {
            "id": 1,
            "content": "Điều 5. Đối tượng và điều kiện dự tuyển đào tạo trình độ thạc sĩ...",
            "metadata": {
                "ma_van_ban": "41/QĐ-ĐHCN",
                "dieu": "5",
                "khoan": "1",
                "ten_van_ban": "Quy chế tuyển sinh và đào tạo thạc sĩ",
            },
            "distance": 0.15,
        },
        {
            "id": 2,
            "content": "Điều 7. Điều kiện tốt nghiệp và công nhận tốt nghiệp...",
            "metadata": {
                "ma_van_ban": "630/QĐ-ĐHCN",
                "dieu": "7",
                "khoan": "1",
                "ten_van_ban": "Quy chế đào tạo thạc sĩ",
            },
            "distance": 0.20,
        },
    ]


@pytest.fixture
def sample_questions():
    """Danh sách các câu hỏi mẫu đại diện cho 3 nhóm."""
    return [
        {"q": "Điều kiện tốt nghiệp thạc sĩ là gì?", "type": "factual"},
        {"q": "Thời gian đào tạo thạc sĩ là bao lâu?", "type": "factual"},
        {"q": "Quy trình xin nghỉ học tạm thời và bảo lưu kết quả?", "type": "procedural"},
        {"q": "Giá vé máy bay hôm nay bao nhiêu?", "type": "out_of_scope"},
    ]
