"""Module tìm kiếm dự phòng (Search Fallback) trên cổng thông tin haui.edu.vn."""

import html
import logging
import re
from typing import Any
from urllib.parse import quote_plus, unquote, urlparse
import requests
from google.genai import types

from haui_rag.config import LLM_MODEL
from haui_rag.core.embedding import get_genai_client

logger = logging.getLogger("haui_rag")


def search_fallback(query: str, top_k: int = 3) -> list[dict[str, Any]]:
    """
    Tìm kiếm thông tin bổ sung trên cổng thông tin haui.edu.vn khi database không có dữ liệu.

    Args:
        query: Câu hỏi của người dùng.
        top_k: Số lượng kết quả tìm kiếm cần lấy (mặc định 3).

    Returns:
        list[dict]: Danh sách các kết quả gồm title, snippet, link.
    """
    clean_q = re.sub(r"[^\w\s]", " ", query).strip()
    search_query = f"site:haui.edu.vn {clean_q}"
    url = f"https://html.duckduckgo.com/html/?q={quote_plus(search_query)}"

    headers = {
        "User-Agent": (
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
            "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        ),
        "Accept-Language": "vi-VN,vi;q=0.9,en-US;q=0.8,en;q=0.7",
    }

    results: list[dict[str, Any]] = []

    try:
        resp = requests.get(url, headers=headers, timeout=6)
        if resp.status_code == 200:
            text = resp.text

            # Trích xuất snippet và link từ HTML
            blocks = re.findall(r'<div class="result__body">(.*?)</div>\s*</div>', text, re.DOTALL)
            for block in blocks[:top_k]:
                title_match = re.search(r'<a class="result__snippet[^>]*>(.*?)</a>', block, re.DOTALL)
                snippet_text = html.unescape(title_match.group(1).strip()) if title_match else ""
                snippet_clean = re.sub(r"<.*?>", "", snippet_text)

                url_match = re.search(r'href="([^"]*uddg=([^"&]*)[^"]*)"', block)
                if url_match:
                    raw_link = unquote(url_match.group(2))
                else:
                    link_match = re.search(r'<a class="result__url" href="([^"]*)"', block)
                # Whitelist domain chặt chẽ: chỉ chấp nhận haui.edu.vn hoặc subdomain của haui.edu.vn
                parsed_url = urlparse(raw_link)
                host = (parsed_url.hostname or "").lower()
                is_haui_domain = host == "haui.edu.vn" or host.endswith(".haui.edu.vn")

                if is_haui_domain and snippet_clean:
                    results.append(
                        {
                            "title": "Cổng thông tin ĐH Công nghiệp Hà Nội (HaUI)",
                            "snippet": snippet_clean[:300],
                            "link": raw_link,
                        }
                    )
        logger.info("Search Fallback tìm thấy %d kết quả từ haui.edu.vn", len(results))
    except Exception as e:
        logger.warning("Search Fallback gặp sự cố mạng hoặc timeout: %s", e)

    return results[:top_k]


def generate_from_fallback(query: str, fallback_results: list[dict[str, Any]]) -> str:
    """
    Sinh câu trả lời từ các kết quả tìm kiếm trên cổng thông tin HaUI.

    Args:
        query: Câu hỏi của người dùng.
        fallback_results: Danh sách kết quả tìm kiếm ngoài website HaUI.

    Returns:
        str: Câu trả lời tổng hợp có trích dẫn link nguồn.
    """
    context_parts = []
    for idx, res in enumerate(fallback_results, start=1):
        context_parts.append(
            f"[{idx}] {res.get('title')} ({res.get('link')}):\n{res.get('snippet')}"
        )

    context_str = "\n\n".join(context_parts)

    prompt = f"""Bạn là trợ lý AI của Trường Đại học Công nghiệp Hà Nội.
Câu hỏi của người dùng không có trong cơ sở dữ liệu quy chế nội bộ đã nạp, nhưng tìm thấy thông tin công khai từ cổng thông tin website của trường (haui.edu.vn) dưới đây:

THÔNG TIN TỪ WEBSITE:
{context_str}

CÂU HỎI:
{query}

HƯỚNG DẪN TRẢ LỜI:
1. Thông báo rõ: "Thông tin này không nằm trong tập quy chế đào tạo nội bộ, nhưng theo thông tin tra cứu từ Cổng thông tin Trường Đại học Công nghiệp Hà Nội (haui.edu.vn):"
2. Tóm tắt nội dung chính xác từ kết quả tìm kiếm.
3. Cuối câu trả lời, dẫn link tham khảo đến website HaUI.

TRẢ LỜI:"""

    try:
        client = get_genai_client()
        response = client.models.generate_content(
            model=LLM_MODEL,
            contents=prompt,
            config=types.GenerateContentConfig(
                temperature=0.1,
            ),
        )
        if response and response.text:
            return response.text.strip()
    except Exception as e:
        logger.error("Lỗi khi sinh câu trả lời từ search fallback: %s", e)

    return (
        "Hệ thống không tìm thấy quy định này trong cơ sở dữ liệu quy chế nội bộ. "
        "Bạn vui lòng tra cứu thêm tại Cổng thông tin trường: https://www.haui.edu.vn"
    )
