"""Module thao tác cơ sở dữ liệu cho Miền Ứng Dụng (Application Domain).

Quản lý:
- conversations: Các phiên hội thoại học thuật của người dùng.
- messages: Lịch sử tin nhắn trao đổi và trích dẫn chuẩn hóa.
- request_logs: Nhật ký kỹ thuật và độ trễ phục vụ giám sát hệ thống.
- feedback: Đánh giá chất lượng câu trả lời từ người dùng.

NGUYÊN TẮC BẤT BIẾN:
- Tuyệt đối KHÔNG đưa dữ liệu trò chuyện, tin nhắn vào embedding pipeline hoặc pgvector.
- Phân tách rõ ràng giữa Application Data và RAG Knowledge Data.
"""

from datetime import datetime, timezone
import json
import logging
import re
from typing import Any, Optional
import uuid
import psycopg2

from haui_rag.db.connection import connect_db

logger = logging.getLogger("haui_rag.db.conversations")


def generate_title_from_question(question: str, max_length: int = 48) -> str:
    """
    Sinh tiêu đề hội thoại tất định (deterministic) từ câu hỏi đầu tiên của người dùng.
    Không gọi mô hình AI/LLM để tiết kiệm chi phí và đảm bảo tốc độ phản hồi tức thì.

    Args:
        question: Câu hỏi đầu tiên của người dùng.
        max_length: Độ dài ký tự tối đa của tiêu đề.

    Returns:
        str: Tiêu đề hội thoại ngắn gọn, chuẩn mực.
    """
    if not question or not question.strip():
        return "Cuộc trò chuyện mới"

    clean = re.sub(r"\s+", " ", question.strip())

    # Loại bỏ các từ thưa gửi không mang nhiều nghĩa ở đầu câu
    patterns_to_strip = [
        r"^(cho\s+em\s+hỏi|cho\s+tôi\s+hỏi|thầy\s+cô\s+cho\s+em\s+hỏi|admin\s+cho\s+hỏi|hỏi\s+về)\s*[:,]?\s*",
        r"^(xin\s+hỏi|em\s+muốn\s+hỏi|tôi\s+muốn\s+hỏi)\s*[:,]?\s*",
    ]
    for pat in patterns_to_strip:
        clean = re.sub(pat, "", clean, flags=re.IGNORECASE)

    clean = clean.strip()
    if not clean:
        return "Cuộc trò chuyện mới"

    # Viết hoa chữ cái đầu tiên
    clean = clean[0].upper() + clean[1:] if len(clean) > 1 else clean.upper()

    if len(clean) <= max_length:
        return clean

    # Cắt ngắn ở ranh giới từ nguyên vẹn
    truncated = clean[:max_length].rsplit(" ", 1)[0]
    return f"{truncated}..."


def create_conversation(title: str = "Cuộc trò chuyện mới") -> dict[str, Any]:
    """
    Tạo một phiên hội thoại mới trong cơ sở dữ liệu.

    Args:
        title: Tiêu đề ban đầu của hội thoại.

    Returns:
        dict: Bản ghi hội thoại vừa tạo.
    """
    conn = None
    try:
        conn = connect_db()
        sql = """
        INSERT INTO conversations (title, created_at, updated_at, message_count)
        VALUES (%s, NOW(), NOW(), 0)
        RETURNING id, title, created_at, updated_at, message_count;
        """
        with conn.cursor() as cur:
            cur.execute(sql, (title.strip(),))
            row = cur.fetchone()
            conn.commit()

        return {
            "id": str(row[0]),
            "title": row[1],
            "created_at": row[2].isoformat(),
            "updated_at": row[3].isoformat(),
            "message_count": row[4],
        }
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error("Lỗi khi tạo cuộc trò chuyện mới: %s", e, exc_info=True)
        raise ConnectionError("Không thể tạo phiên hội thoại trong cơ sở dữ liệu") from e
    finally:
        if conn and not conn.closed:
            conn.close()


def list_conversations(limit: int = 50, offset: int = 0) -> list[dict[str, Any]]:
    """
    Lấy danh sách tóm tắt các cuộc hội thoại phục vụ thanh điều hướng Sidebar.
    Sắp xếp theo thời gian cập nhật giảm dần (updated_at DESC).
    Chỉ lấy thông tin tóm tắt (không tải toàn bộ tin nhắn).

    Args:
        limit: Số lượng hội thoại tối đa cần lấy.
        offset: Vị trí bắt đầu phân trang.

    Returns:
        list[dict]: Danh sách tóm tắt các cuộc trò chuyện.
    """
    conn = None
    try:
        conn = connect_db()
        sql = """
        SELECT id, title, created_at, updated_at, message_count
        FROM conversations
        ORDER BY updated_at DESC
        LIMIT %s OFFSET %s;
        """
        with conn.cursor() as cur:
            cur.execute(sql, (max(1, limit), max(0, offset)))
            rows = cur.fetchall()

        results: list[dict[str, Any]] = []
        for r in rows:
            results.append(
                {
                    "id": str(r[0]),
                    "title": r[1],
                    "created_at": r[2].isoformat(),
                    "updated_at": r[3].isoformat(),
                    "message_count": r[4],
                }
            )
        return results
    except Exception as e:
        logger.error("Lỗi khi lấy danh sách cuộc trò chuyện: %s", e, exc_info=True)
        return []
    finally:
        if conn and not conn.closed:
            conn.close()


def get_conversation(conversation_id: str) -> Optional[dict[str, Any]]:
    """
    Lấy thông tin chi tiết một cuộc trò chuyện theo UUID.

    Args:
        conversation_id: UUID của cuộc trò chuyện.

    Returns:
        Optional[dict]: Thông tin cuộc trò chuyện hoặc None nếu không tìm thấy.
    """
    conn = None
    try:
        conn = connect_db()
        sql = """
        SELECT id, title, created_at, updated_at, message_count
        FROM conversations
        WHERE id = %s;
        """
        with conn.cursor() as cur:
            cur.execute(sql, (conversation_id,))
            row = cur.fetchone()

        if not row:
            return None

        return {
            "id": str(row[0]),
            "title": row[1],
            "created_at": row[2].isoformat(),
            "updated_at": row[3].isoformat(),
            "message_count": row[4],
        }
    except Exception as e:
        logger.error("Lỗi khi lấy thông tin cuộc trò chuyện %s: %s", conversation_id, e)
        return None
    finally:
        if conn and not conn.closed:
            conn.close()


def delete_conversation(conversation_id: str) -> bool:
    """
    Xóa một cuộc trò chuyện khỏi cơ sở dữ liệu.
    Nhờ thiết lập ON DELETE CASCADE, toàn bộ tin nhắn liên quan sẽ tự động bị xóa.

    Args:
        conversation_id: UUID của cuộc trò chuyện cần xóa.

    Returns:
        bool: True nếu xóa thành công, False nếu không tồn tại hoặc lỗi.
    """
    conn = None
    try:
        conn = connect_db()
        sql = "DELETE FROM conversations WHERE id = %s RETURNING id;"
        with conn.cursor() as cur:
            cur.execute(sql, (conversation_id,))
            deleted = cur.fetchone()
            conn.commit()
            return deleted is not None
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error("Lỗi khi xóa cuộc trò chuyện %s: %s", conversation_id, e, exc_info=True)
        return False
    finally:
        if conn and not conn.closed:
            conn.close()


def get_conversation_messages(conversation_id: str) -> list[dict[str, Any]]:
    """
    Lấy toàn bộ tin nhắn thuộc một cuộc trò chuyện theo thứ tự thời gian tăng dần.
    ĐÂY LÀ THAO TÁC ĐỌC THUẦN CƠ SỞ DỮ LIỆU.
    TUYỆT ĐỐI KHÔNG GỌI RAG, KHÔNG EMBEDDING, KHÔNG GỌI LLM.

    Args:
        conversation_id: UUID của cuộc trò chuyện.

    Returns:
        list[dict]: Danh sách tin nhắn kèm trích dẫn đã lưu.
    """
    conn = None
    try:
        conn = connect_db()
        sql = """
        SELECT id, conversation_id, role, content, created_at,
               request_id, query_type, latency_ms, fallback_used,
               citations, metadata
        FROM messages
        WHERE conversation_id = %s
        ORDER BY created_at ASC;
        """
        with conn.cursor() as cur:
            cur.execute(sql, (conversation_id,))
            rows = cur.fetchall()

        messages: list[dict[str, Any]] = []
        for r in rows:
            cites = r[9]
            if isinstance(cites, str):
                try:
                    cites = json.loads(cites)
                except Exception:
                    cites = []
            elif cites is None:
                cites = []

            meta = r[10]
            if isinstance(meta, str):
                try:
                    meta = json.loads(meta)
                except Exception:
                    meta = {}
            elif meta is None:
                meta = {}

            messages.append(
                {
                    "id": str(r[0]),
                    "conversation_id": str(r[1]),
                    "role": r[2],
                    "content": r[3],
                    "created_at": r[4].isoformat() if hasattr(r[4], "isoformat") else str(r[4]),
                    "request_id": r[5],
                    "query_type": r[6],
                    "latency_ms": r[7],
                    "fallback_used": bool(r[8]),
                    "citations": cites,
                    "metadata": meta,
                }
            )
        return messages
    except Exception as e:
        logger.error("Lỗi khi đọc tin nhắn của cuộc trò chuyện %s: %s", conversation_id, e)
        return []
    finally:
        if conn and not conn.closed:
            conn.close()


def save_user_message(
    conversation_id: str,
    content: str,
    request_id: Optional[str] = None,
) -> dict[str, Any]:
    """
    Lưu tin nhắn của người dùng TRƯỚC KHI tiến hành gọi RAG.
    Đảm bảo nếu quá trình sinh câu trả lời bị lỗi thì yêu cầu người dùng vẫn được bảo toàn.
    Đồng thời cập nhật tiêu đề hội thoại nếu đây là câu hỏi đầu tiên.

    Args:
        conversation_id: UUID cuộc trò chuyện.
        content: Nội dung câu hỏi của người dùng.
        request_id: Mã định danh truy vấn.

    Returns:
        dict: Bản ghi tin nhắn đã lưu.
    """
    conn = None
    try:
        conn = connect_db()
        with conn.cursor() as cur:
            # 1. Kiểm tra cuộc trò chuyện tồn tại và lấy số lượng tin nhắn hiện có
            cur.execute(
                "SELECT message_count, title FROM conversations WHERE id = %s FOR UPDATE;",
                (conversation_id,),
            )
            conv_row = cur.fetchone()
            if not conv_row:
                raise ValueError(f"Không tìm thấy cuộc trò chuyện với id={conversation_id}")

            current_count = conv_row[0]

            # 2. Thêm tin nhắn user vào bảng messages
            msg_sql = """
            INSERT INTO messages (conversation_id, role, content, created_at, request_id)
            VALUES (%s, 'user', %s, NOW(), %s)
            RETURNING id, conversation_id, role, content, created_at, request_id;
            """
            cur.execute(msg_sql, (conversation_id, content.strip(), request_id))
            saved_msg = cur.fetchone()

            # 3. Cập nhật conversations (tăng message_count, cập nhật updated_at)
            # Nếu là tin nhắn đầu tiên, tự động tạo tiêu đề từ câu hỏi
            if current_count == 0:
                new_title = generate_title_from_question(content)
                cur.execute(
                    """
                    UPDATE conversations
                    SET title = %s, message_count = message_count + 1, updated_at = NOW()
                    WHERE id = %s;
                    """,
                    (new_title, conversation_id),
                )
            else:
                cur.execute(
                    """
                    UPDATE conversations
                    SET message_count = message_count + 1, updated_at = NOW()
                    WHERE id = %s;
                    """,
                    (conversation_id,),
                )

            conn.commit()

        return {
            "id": str(saved_msg[0]),
            "conversation_id": str(saved_msg[1]),
            "role": saved_msg[2],
            "content": saved_msg[3],
            "created_at": saved_msg[4].isoformat(),
            "request_id": saved_msg[5],
        }
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error("Lỗi khi lưu tin nhắn người dùng: %s", e, exc_info=True)
        raise
    finally:
        if conn and not conn.closed:
            conn.close()


def save_assistant_message(
    conversation_id: str,
    content: str,
    request_id: Optional[str] = None,
    query_type: Optional[str] = None,
    latency_ms: Optional[int] = None,
    fallback_used: bool = False,
    citations: Optional[list[dict[str, Any]]] = None,
    metadata: Optional[dict[str, Any]] = None,
) -> dict[str, Any]:
    """
    Lưu phản hồi từ trợ lý kèm trích dẫn nguồn có cấu trúc vào bảng messages.
    Cập nhật số lượng tin nhắn và thời gian của cuộc trò chuyện.

    Args:
        conversation_id: UUID cuộc trò chuyện.
        content: Nội dung câu trả lời.
        request_id: Mã truy vấn.
        query_type: Phân loại câu hỏi.
        latency_ms: Độ trễ phản hồi (ms).
        fallback_used: Có sử dụng fallback ngoài hay không.
        citations: Danh sách các trích dẫn nguồn.
        metadata: Dữ liệu mở rộng khác.

    Returns:
        dict: Bản ghi tin nhắn assistant đã lưu.
    """
    conn = None
    try:
        conn = connect_db()
        with conn.cursor() as cur:
            citations_json = json.dumps(citations or [])
            metadata_json = json.dumps(metadata or {})

            sql = """
            INSERT INTO messages (
                conversation_id, role, content, created_at, request_id,
                query_type, latency_ms, fallback_used, citations, metadata
            )
            VALUES (%s, 'assistant', %s, NOW(), %s, %s, %s, %s, %s::jsonb, %s::jsonb)
            RETURNING id, conversation_id, role, content, created_at,
                      request_id, query_type, latency_ms, fallback_used, citations, metadata;
            """
            cur.execute(
                sql,
                (
                    conversation_id,
                    content,
                    request_id,
                    query_type,
                    latency_ms,
                    fallback_used,
                    citations_json,
                    metadata_json,
                ),
            )
            row = cur.fetchone()

            # Cập nhật conversations
            cur.execute(
                """
                UPDATE conversations
                SET message_count = message_count + 1, updated_at = NOW()
                WHERE id = %s;
                """,
                (conversation_id,),
            )
            conn.commit()

        cites_out = row[9]
        if isinstance(cites_out, str):
            try:
                cites_out = json.loads(cites_out)
            except Exception:
                cites_out = []

        return {
            "id": str(row[0]),
            "conversation_id": str(row[1]),
            "role": row[2],
            "content": row[3],
            "created_at": row[4].isoformat(),
            "request_id": row[5],
            "query_type": row[6],
            "latency_ms": row[7],
            "fallback_used": bool(row[8]),
            "citations": cites_out,
            "metadata": row[10] if isinstance(row[10], dict) else {},
        }
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error("Lỗi khi lưu tin nhắn trợ lý: %s", e, exc_info=True)
        raise
    finally:
        if conn and not conn.closed:
            conn.close()


def save_request_log(
    request_id: str,
    conversation_id: Optional[str],
    endpoint: str,
    status_code: int,
    latencies: Optional[dict[str, Any]] = None,
    fallback_used: bool = False,
    metadata: Optional[dict[str, Any]] = None,
) -> None:
    """
    Ghi nhật ký vận hành kỹ thuật vào bảng request_logs.
    Không lưu trữ nội dung chat thô nhạy cảm.

    Args:
        request_id: Mã truy vấn request_id.
        conversation_id: UUID cuộc trò chuyện nếu có.
        endpoint: Endpoint phục vụ.
        status_code: Mã HTTP response.
        latencies: Dict chứa các loại độ trễ (total, embedding, retrieval, generation).
        fallback_used: Có dùng fallback hay không.
        metadata: Metadata bổ sung.
    """
    latencies = latencies or {}
    total_ms = latencies.get("total_latency_ms")
    embed_ms = latencies.get("embedding_latency_ms")
    retrieval_ms = latencies.get("retrieval_latency_ms")
    rerank_ms = latencies.get("rerank_latency_ms")
    gen_ms = latencies.get("generation_latency_ms")

    conn = None
    try:
        conn = connect_db()
        sql = """
        INSERT INTO request_logs (
            request_id, conversation_id, endpoint, status_code,
            embedding_latency_ms, retrieval_latency_ms, rerank_latency_ms,
            generation_latency_ms, total_latency_ms, fallback_used,
            created_at, metadata
        )
        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), %s::jsonb);
        """
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    request_id,
                    conversation_id,
                    endpoint,
                    status_code,
                    embed_ms,
                    retrieval_ms,
                    rerank_ms,
                    gen_ms,
                    total_ms,
                    fallback_used,
                    json.dumps(metadata or {}),
                ),
            )
            conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        logger.warning("Không thể ghi request_log: %s", e)
    finally:
        if conn and not conn.closed:
            conn.close()


def save_feedback(
    message_id: str,
    rating: str,
    reason: Optional[str] = None,
    comment: Optional[str] = None,
) -> dict[str, Any]:
    """
    Lưu trữ đánh giá phản hồi của người dùng cho một tin nhắn cụ thể.

    Args:
        message_id: UUID tin nhắn được đánh giá.
        rating: "positive", "negative", "helpful", hoặc "unhelpful".
        reason: Lý do chi tiết nếu chưa hài lòng.
        comment: Nhận xét bổ sung.

    Returns:
        dict: Bản ghi feedback vừa lưu.
    """
    clean_rating = rating.lower().strip()
    if clean_rating not in ("positive", "negative", "helpful", "unhelpful"):
        clean_rating = "helpful" if "help" in clean_rating or "pos" in clean_rating else "unhelpful"

    conn = None
    try:
        conn = connect_db()
        sql = """
        INSERT INTO feedback (message_id, rating, reason, comment, created_at)
        VALUES (%s, %s, %s, %s, NOW())
        RETURNING id, message_id, rating, reason, comment, created_at;
        """
        with conn.cursor() as cur:
            cur.execute(sql, (message_id, clean_rating, reason, comment))
            row = cur.fetchone()
            conn.commit()

        return {
            "id": str(row[0]),
            "message_id": str(row[1]),
            "rating": row[2],
            "reason": row[3],
            "comment": row[4],
            "created_at": row[5].isoformat(),
        }
    except Exception as e:
        if conn:
            conn.rollback()
        logger.error("Lỗi khi lưu feedback: %s", e, exc_info=True)
        raise ConnectionError("Không thể lưu feedback vào cơ sở dữ liệu") from e
    finally:
        if conn and not conn.closed:
            conn.close()
