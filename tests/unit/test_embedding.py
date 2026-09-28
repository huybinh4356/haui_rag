"""Test module embedding theo chuẩn pytest."""

import pytest
from haui_rag.config import EMBEDDING_DIMENSION
from haui_rag.core.embedding import get_embedding


class TestGetEmbedding:
    def test_returns_correct_dimension(self):
        """Vector phải có 3072 chiều."""
        result = get_embedding("test")
        assert isinstance(result, list)
        assert len(result) == EMBEDDING_DIMENSION

    def test_retrieval_document_task_type(self):
        """Task type có thể dùng RETRIEVAL_DOCUMENT."""
        result = get_embedding("test", task_type="RETRIEVAL_DOCUMENT")
        assert result is not None
        assert len(result) == EMBEDDING_DIMENSION

    def test_empty_string(self):
        """Chuỗi rỗng phải ném ValueError."""
        with pytest.raises(ValueError):
            get_embedding("")

    def test_whitespace_string(self):
        """Chuỗi khoảng trắng phải ném ValueError."""
        with pytest.raises(ValueError):
            get_embedding("   ")