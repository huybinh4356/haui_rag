"""Module tạo vector nhúng (embedding) cho câu hỏi sử dụng Gemini API."""

import logging
import time
from typing import Optional
from google import genai
from google.genai import types
from google.genai.errors import APIError

from haui_rag.config import (
    GEMINI_API_KEY,
    EMBEDDING_MODEL,
    GEMINI_TIMEOUT_SECONDS,
    MAX_EMBEDDING_RETRIES,
    INITIAL_RETRY_DELAY,
)

logger = logging.getLogger("haui_rag")

# Singleton Gemini Client
_client: Optional[genai.Client] = None


def get_genai_client() -> genai.Client:
    """
    Lấy đối tượng genai.Client (singleton).

    Returns:
        genai.Client: Client đã được cấu hình API key.

    Raises:
        ValueError: Nếu chưa cấu hình GEMINI_API_KEY.
    """
    global _client
    if _client is None:
        if not GEMINI_API_KEY:
            raise ValueError("GEMINI_API_KEY chưa được thiết lập trong biến môi trường")
        _client = genai.Client(
            api_key=GEMINI_API_KEY,
            http_options=types.HttpOptions(timeout=GEMINI_TIMEOUT_SECONDS * 1000),
        )
    return _client


def get_embedding(
    text: str,
    task_type: str = "RETRIEVAL_QUERY",
) -> list[float]:
    """
    Tạo vector embedding 3072 chiều từ văn bản sử dụng Gemini Embedding API.
    Bắt buộc dùng task_type="RETRIEVAL_QUERY" cho câu hỏi tra cứu.

    Args:
        text: Nội dung văn bản hoặc câu hỏi cần tạo embedding.
        task_type: Loại tác vụ embedding (mặc định "RETRIEVAL_QUERY").

    Returns:
        list[float]: Vector 3072 chiều đại diện ngữ nghĩa của text.

    Raises:
        ValueError: Nếu text rỗng hoặc không hợp lệ.
        RuntimeError: Nếu gọi API thất bại sau các lần retry.
    """
    if not text or not isinstance(text, str) or not text.strip():
        raise ValueError("Văn bản cần tạo embedding không được để trống")

    client = get_genai_client()
    delay = INITIAL_RETRY_DELAY

    for attempt in range(1, MAX_EMBEDDING_RETRIES + 1):
        try:
            logger.debug("Gọi API embedding lần %d/%d", attempt, MAX_EMBEDDING_RETRIES)
            response = client.models.embed_content(
                model=EMBEDDING_MODEL,
                contents=text.strip(),
                config=types.EmbedContentConfig(
                    task_type=task_type,
                ),
            )
            if response.embeddings and len(response.embeddings) > 0:
                values = response.embeddings[0].values
                if values and len(values) == 3072:
                    return list(values)
                raise RuntimeError(
                    f"Kích thước vector không đúng: {len(values) if values else 0} (yêu cầu 3072)"
                )
            raise RuntimeError("API không trả về vector embedding nào")

        except (APIError, Exception) as e:
            logger.warning(
                "Lỗi gọi Gemini Embedding API (lần %d/%d): %s",
                attempt,
                MAX_EMBEDDING_RETRIES,
                e,
            )
            if attempt == MAX_EMBEDDING_RETRIES:
                logger.error("Hết số lần retry embedding: %s", e, exc_info=True)
                raise RuntimeError(f"Tạo embedding thất bại sau {MAX_EMBEDDING_RETRIES} lần: {e}") from e
            time.sleep(delay)
            delay *= 2.0

    raise RuntimeError("Tạo embedding thất bại không xác định")
