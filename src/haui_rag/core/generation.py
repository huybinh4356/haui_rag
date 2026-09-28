"""Module xử lý tầng Generation: Xây dựng prompt và gọi LLM sinh câu trả lời."""

import logging
import time
from typing import Any
from google.genai import types

from haui_rag.config import (
    GENERATION_TEMPERATURE,
    LLM_MODEL,
)
from haui_rag.core.embedding import get_genai_client
from haui_rag.prompts.templates import PROMPT_TEMPLATE
from haui_rag.utils.helpers import format_citation

logger = logging.getLogger("haui_rag")


def build_prompt(query: str, contexts: list[dict[str, Any]]) -> str:
    """
    Tạo prompt hoàn chỉnh từ câu hỏi và danh sách ngữ cảnh.

    Args:
        query: Câu hỏi của người dùng.
        contexts: Danh sách chunks lấy từ PostgreSQL.

    Returns:
        str: Prompt hoàn chỉnh gửi cho LLM.
    """
    if not contexts:
        context_str = "Không có tài liệu liên quan."
    else:
        context_blocks: list[str] = []
        for idx, chunk in enumerate(contexts, start=1):
            citation = format_citation(chunk.get("metadata", {}))
            content = chunk.get("content", "").strip()
            block = f"--- [Đoạn {idx}] {citation} ---\n{content}"
            context_blocks.append(block)
        context_str = "\n\n".join(context_blocks)

    return PROMPT_TEMPLATE.format(context=context_str, question=query.strip())


def generate_answer(prompt: str) -> str:
    """
    Gọi Gemini LLM để sinh câu trả lời với temperature thấp (0.1).
    Có retry exponential backoff tự động khi gặp lỗi 503 hoặc 429.

    Args:
        prompt: Prompt hoàn chỉnh chứa câu hỏi và ngữ cảnh.

    Returns:
        str: Câu trả lời từ LLM.

    Raises:
        RuntimeError: Khi gọi API Gemini thất bại sau các lần thử lại.
    """
    client = get_genai_client()
    delay = 2.0
    max_retries = 3

    for attempt in range(1, max_retries + 1):
        try:
            logger.debug("Gọi LLM sinh câu trả lời (lần %d/%d)...", attempt, max_retries)
            response = client.models.generate_content(
                model=LLM_MODEL,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=GENERATION_TEMPERATURE,
                ),
            )
            if response and response.text:
                return response.text.strip()
            raise RuntimeError("API không trả về nội dung text nào")

        except Exception as e:
            err_str = str(e)
            logger.warning(
                "Lỗi khi gọi Gemini LLM (%s) lần %d/%d: %s",
                LLM_MODEL,
                attempt,
                max_retries,
                e,
            )
            if attempt == max_retries:
                logger.error("Hết số lần retry LLM: %s", e, exc_info=True)
                raise RuntimeError(f"Lỗi khi sinh câu trả lời sau {max_retries} lần: {e}") from e

            # Nếu gặp rate limit 429, trích xuất thời gian chờ từ thông báo lỗi hoặc chờ 25s
            if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                import re
                match = re.search(r"retry in ([\d\.]+)s", err_str)
                sleep_time = float(match.group(1)) + 2.0 if match else 25.0
                logger.info("Gặp 429 Rate Limit, tạm dừng %.1fs để hồi quota Gemini...", sleep_time)
            else:
                sleep_time = delay
                delay *= 2.0

            time.sleep(sleep_time)

    return "Xin lỗi, tôi không thể xử lý câu trả lời lúc này."
