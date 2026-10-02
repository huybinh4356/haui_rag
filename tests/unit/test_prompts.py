"""Unit tests kiểm tra prompt templates và định dạng prompt."""

from haui_rag.core.generation import build_prompt
from haui_rag.prompts.templates import PROMPT_TEMPLATE, RAG_PROMPT_V2


def test_prompt_template_structure():
    """Kiểm tra cấu trúc template chứa đầy đủ 4 trường hợp."""
    assert "{context}" in PROMPT_TEMPLATE
    assert "{question}" in PROMPT_TEMPLATE
    assert "Trường hợp 1" in RAG_PROMPT_V2
    assert "Trường hợp 2" in RAG_PROMPT_V2
    assert "Trường hợp 3" in RAG_PROMPT_V2
    assert "Trường hợp 4" in RAG_PROMPT_V2


def test_build_prompt_with_contexts(sample_chunks):
    """Kiểm tra hàm build_prompt ghép đúng ngữ cảnh và câu hỏi."""
    question = "Điều kiện tốt nghiệp thạc sĩ?"
    prompt = build_prompt(question, sample_chunks)
    assert question in prompt
    assert "41/QĐ-ĐHCN" in prompt
    assert "630/QĐ-ĐHCN" in prompt


def test_build_prompt_empty_contexts():
    """Kiểm tra build_prompt khi contexts rỗng."""
    prompt = build_prompt("Câu hỏi?", [])
    assert "Không có tài liệu liên quan" in prompt


def test_generate_answer_mocked(monkeypatch):
    """Kiểm tra generate_answer hoạt động đúng qua mock — không phụ thuộc provider thật."""
    from unittest.mock import MagicMock
    from haui_rag.core import generation

    expected = "Đây là câu trả lời kiểm thử"

    # Mock Ollama để test không cần Ollama đang chạy
    monkeypatch.setattr(generation, "call_ollama_generate", lambda prompt, **kw: expected)

    # Mock Gemini để test không cần API key thật
    mock_client = MagicMock()
    mock_resp = MagicMock()
    mock_resp.text = expected
    mock_client.models.generate_content.return_value = mock_resp
    monkeypatch.setattr(generation, "get_genai_client", lambda: mock_client)

    res = generation.generate_answer("Prompt test")
    assert res == expected

