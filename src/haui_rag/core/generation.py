"""Module xử lý tầng Generation: Xây dựng prompt và gọi LLM sinh câu trả lời."""

import logging
import time
from typing import Any
from google.genai import types

from haui_rag.config import (
    FALLBACK_LLM_MODEL,
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
    Có cơ chế tự động chuyển model dự phòng và retry ngắn khi gặp lỗi 503 hoặc 429.

    Args:
        prompt: Prompt hoàn chỉnh chứa câu hỏi và ngữ cảnh.

    Returns:
        str: Câu trả lời từ LLM.

    Raises:
        RuntimeError: Khi gọi API Gemini thất bại sau các lần thử lại.
    """
    client = get_genai_client()
    candidate_models = [LLM_MODEL]
    if FALLBACK_LLM_MODEL and FALLBACK_LLM_MODEL != LLM_MODEL:
        candidate_models.append(FALLBACK_LLM_MODEL)

    delay = 1.0
    max_retries = 3

    for current_model in candidate_models:
        for attempt in range(1, max_retries + 1):
            try:
                logger.debug("Gọi LLM %s (lần %d/%d)...", current_model, attempt, max_retries)
                response = client.models.generate_content(
                    model=current_model,
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
                    current_model,
                    attempt,
                    max_retries,
                    e,
                )

                # Nếu là lỗi 503 quá tải và còn model dự phòng, đổi model ngay
                if ("503" in err_str or "UNAVAILABLE" in err_str) and current_model != candidate_models[-1]:
                    logger.info("Chuyển ngay sang model dự phòng %s do 503", candidate_models[-1])
                    break

                if attempt == max_retries:
                    if current_model == candidate_models[-1]:
                        logger.error("Hết số lần retry LLM cho tất cả models: %s", e, exc_info=True)
                        raise RuntimeError(f"Lỗi khi sinh câu trả lời sau {max_retries} lần: {e}") from e
                    break

                if "429" in err_str or "RESOURCE_EXHAUSTED" in err_str:
                    import re
                    match = re.search(r"retry in ([\d\.]+)s", err_str)
                    sleep_time = float(match.group(1)) + 1.0 if match else 5.0
                    logger.info("Gặp 429 Rate Limit, tạm dừng %.1fs để hồi quota Gemini...", sleep_time)
                else:
                    sleep_time = delay
                    delay *= 1.5

                time.sleep(sleep_time)

    return "Xin lỗi, tôi không thể xử lý câu trả lời lúc này."
