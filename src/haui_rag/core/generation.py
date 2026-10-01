"""Module xử lý tầng Generation: Xây dựng prompt, gọi LLM sinh câu trả lời (hỗ trợ Batch & Real-time Streaming)."""

import json
import logging
import time
from typing import Any, Iterator
import requests
from google.genai import types

from haui_rag.config import (
    FALLBACK_LLM_MODEL,
    GENERATION_TEMPERATURE,
    LLM_MODEL,
    LLM_PROVIDER,
    LOCAL_LLM_MODEL,
    OLLAMA_BASE_URL,
    OLLAMA_NUM_CTX,
    OLLAMA_NUM_GPU,
    OLLAMA_NUM_PREDICT,
    OLLAMA_TIMEOUT_SECONDS,
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


def call_ollama_generate(
    prompt: str,
    model: str = LOCAL_LLM_MODEL,
    temperature: float = GENERATION_TEMPERATURE,
    timeout: int = OLLAMA_TIMEOUT_SECONDS,
    num_ctx: int = OLLAMA_NUM_CTX,
    num_predict: int = OLLAMA_NUM_PREDICT,
    num_gpu: int = OLLAMA_NUM_GPU,
) -> str:
    """
    Gọi Ollama REST API cục bộ để sinh câu trả lời từ mô hình nội bộ.
    Tối ưu hóa VRAM ở mức 3.0 - 3.5 GB trên GPU RTX 3050 bằng cách giới hạn num_ctx và num_gpu.

    Args:
        prompt: Nội dung prompt gửi cho mô hình.
        model: Tên mô hình trong Ollama (ví dụ 'qwen3.5:4b').
        temperature: Độ biến thiên sáng tạo (0.1 cho RAG).
        timeout: Thời gian chờ tối đa (giây).
        num_ctx: Kích thước cửa sổ ngữ cảnh tối đa (tokens).
        num_predict: Số lượng tokens sinh tối đa.
        num_gpu: Số lượng layers offload sang GPU.

    Returns:
        str: Nội dung câu trả lời do mô hình sinh ra.

    Raises:
        ConnectionError: Khi Ollama chưa được bật hoặc không thể kết nối.
        RuntimeError: Khi Ollama trả về mã lỗi hoặc không có text.
    """
    endpoint = f"{OLLAMA_BASE_URL.rstrip('/')}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": False,
        "options": {
            "temperature": temperature,
            "num_ctx": num_ctx,
            "num_predict": num_predict,
            "num_gpu": num_gpu,
        },
    }

    try:
        # connect timeout 1.5s, read timeout float(timeout)
        response = requests.post(endpoint, json=payload, timeout=(1.5, float(timeout)))
        if response.status_code == 200:
            data = response.json()
            answer = data.get("response", "").strip()
            if answer:
                return answer
            raise RuntimeError("Ollama trả về phản hồi rỗng")
        if response.status_code == 404:
            raise RuntimeError(
                f"Mô hình '{model}' chưa được cài đặt trong Ollama. "
                f"Vui lòng chạy lệnh: ollama pull {model}"
            )
        raise RuntimeError(f"Ollama trả về mã lỗi HTTP {response.status_code}: {response.text}")
    except requests.exceptions.ConnectionError as e:
        raise ConnectionError(
            f"Không thể kết nối đến Ollama tại {OLLAMA_BASE_URL}. "
            "Hãy đảm bảo ứng dụng Ollama đang chạy."
        ) from e
    except requests.exceptions.Timeout as e:
        raise TimeoutError(f"Ollama phản hồi quá thời gian quy định ({timeout}s)") from e


def call_ollama_generate_stream(
    prompt: str,
    model: str = LOCAL_LLM_MODEL,
    temperature: float = GENERATION_TEMPERATURE,
    timeout: int = OLLAMA_TIMEOUT_SECONDS,
    num_ctx: int = OLLAMA_NUM_CTX,
    num_predict: int = OLLAMA_NUM_PREDICT,
    num_gpu: int = OLLAMA_NUM_GPU,
) -> Iterator[str]:
    """
    Gọi Ollama REST API cục bộ để stream câu trả lời theo thời gian thực (Real-time Token Streaming).

    Args:
        prompt: Nội dung prompt gửi cho mô hình.
        model: Tên mô hình trong Ollama.
        temperature: Nhiệt độ sinh từ.
        timeout: Thời gian chờ tối đa.
        num_ctx: Giới hạn context tokens.
        num_predict: Giới hạn token sinh tối đa.
        num_gpu: Số lượng GPU layers.

    Yields:
        str: Từng đoạn token văn bản khi vừa được mô hình sinh ra.
    """
    endpoint = f"{OLLAMA_BASE_URL.rstrip('/')}/api/generate"
    payload = {
        "model": model,
        "prompt": prompt,
        "stream": True,
        "options": {
            "temperature": temperature,
            "num_ctx": num_ctx,
            "num_predict": num_predict,
            "num_gpu": num_gpu,
        },
    }

    try:
        response = requests.post(endpoint, json=payload, stream=True, timeout=(1.5, float(timeout)))
        if response.status_code == 200:
            for line in response.iter_lines():
                if line:
                    chunk = json.loads(line.decode("utf-8"))
                    text = chunk.get("response", "")
                    if text:
                        yield text
                    if chunk.get("done", False):
                        break
        else:
            raise RuntimeError(f"Ollama trả về mã lỗi HTTP {response.status_code}")
    except requests.exceptions.ConnectionError as e:
        raise ConnectionError(f"Không thể kết nối đến Ollama tại {OLLAMA_BASE_URL}") from e


def _generate_gemini_answer(prompt: str) -> str:
    """
    Gọi Gemini LLM đám mây để sinh câu trả lời với cơ chế tự động chuyển model dự phòng và retry.
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


def _generate_gemini_answer_stream(prompt: str) -> Iterator[str]:
    """
    Stream câu trả lời từ Gemini API theo thời gian thực (giảm Time-To-First-Token xuống dưới 500ms).
    """
    client = get_genai_client()
    candidate_models = [LLM_MODEL]
    if FALLBACK_LLM_MODEL and FALLBACK_LLM_MODEL != LLM_MODEL:
        candidate_models.append(FALLBACK_LLM_MODEL)

    for current_model in candidate_models:
        try:
            logger.debug("Gọi Gemini LLM Stream %s...", current_model)
            response = client.models.generate_content_stream(
                model=current_model,
                contents=prompt,
                config=types.GenerateContentConfig(
                    temperature=GENERATION_TEMPERATURE,
                ),
            )
            for chunk in response:
                if chunk and chunk.text:
                    yield chunk.text
            return
        except Exception as e:
            logger.warning("Lỗi khi stream từ Gemini LLM (%s): %s", current_model, e)
            if current_model == candidate_models[-1]:
                yield f"\n[Lỗi kết nối API: {e}]"


def generate_answer(prompt: str) -> str:
    """
    Sinh toàn bộ câu trả lời từ prompt hoàn chỉnh (Batch Mode).
    Tự động chọn Ollama hoặc fallback sang Gemini.

    Args:
        prompt: Prompt hoàn chỉnh chứa câu hỏi và ngữ cảnh.

    Returns:
        str: Câu trả lời từ LLM.
    """
    if LLM_PROVIDER == "ollama":
        try:
            logger.info("Đang gọi Local LLM (%s) qua Ollama...", LOCAL_LLM_MODEL)
            return call_ollama_generate(prompt)
        except Exception as e:
            logger.warning(
                "Không gọi được Ollama (%s): %s. Tự động chuyển sang fallback Gemini...",
                LOCAL_LLM_MODEL,
                e,
            )
            return _generate_gemini_answer(prompt)
    else:
        return _generate_gemini_answer(prompt)


def generate_answer_stream(prompt: str) -> Iterator[str]:
    """
    Sinh câu trả lời dạng stream từng token theo thời gian thực (Streaming Mode).
    Giúp giảm cảm giác chờ đợi từ 7000ms xuống hiển thị tức thì (<500ms).

    Args:
        prompt: Prompt hoàn chỉnh chứa câu hỏi và ngữ cảnh.

    Yields:
        str: Từng từ/token theo thời gian thực.
    """
    if LLM_PROVIDER == "ollama":
        try:
            logger.info("Đang stream câu trả lời từ Local LLM (%s)...", LOCAL_LLM_MODEL)
            yield from call_ollama_generate_stream(prompt)
            return
        except Exception as e:
            logger.warning(
                "Không stream được từ Ollama (%s): %s. Tự động chuyển sang fallback Gemini stream...",
                LOCAL_LLM_MODEL,
                e,
            )
            yield from _generate_gemini_answer_stream(prompt)
    else:
        yield from _generate_gemini_answer_stream(prompt)
