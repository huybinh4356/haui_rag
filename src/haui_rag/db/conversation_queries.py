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


def get_system_evaluation_metrics() -> dict[str, Any]:
    """
    Tổng hợp số liệu vận hành thực tế từ các bảng messages,
    feedback, request_logs và documents (chỉ đọc).

    Returns:
        dict: Bộ thông số vận hành và thống kê biểu đồ từ PostgreSQL.
    """
    summary: dict[str, Any] = {
        "total_documents": 0,
        "total_files": 0,
        "total_conversations": 0,
        "total_user_queries": 0,
        "total_assistant_answers": 0,
        "avg_latency_ms": 0,
        "p95_latency_ms": 0,
        "grounded_count": 0,
        "ungrounded_count": 0,
        "audited_count": 0,
        "grounded_rate_percent": 0.0,
        "avg_verification_score": 0.0,
        "avg_sources_per_answer": 0.0,
        "fallback_count": 0,
        "fallback_rate_percent": 0.0,
        "query_type_breakdown": {},
        "docs_by_file": [],
        "recent_latencies": [],
        "feedback_total": 0,
        "feedback_helpful": 0,
        "feedback_unhelpful": 0,
        "satisfaction_rate_percent": 0.0,
    }

    conn = None
    try:
        conn = connect_db()
        with conn.cursor() as cur:
            # 1. Thống kê kho tri thức documents (READ-ONLY)
            cur.execute(
                """
                SELECT COUNT(*), COUNT(DISTINCT metadata->>'ten_file')
                FROM documents;
                """
            )
            doc_row = cur.fetchone()
            if doc_row:
                summary["total_documents"] = int(doc_row[0] or 0)
                summary["total_files"] = int(doc_row[1] or 0)

            cur.execute(
                """
                SELECT COALESCE(metadata->>'ma_van_ban', metadata->>'ten_file', 'Chưa rõ') AS doc_label,
                       COUNT(*) AS chunk_cnt
                FROM documents
                GROUP BY doc_label
                ORDER BY chunk_cnt DESC;
                """
            )
            summary["docs_by_file"] = [
                {"Văn bản": str(r[0]), "Số chunks": int(r[1] or 0)}
                for r in cur.fetchall()
            ]

            # 2. Tổng số hội thoại
            cur.execute("SELECT COUNT(*) FROM conversations;")
            conv_row = cur.fetchone()
            if conv_row:
                summary["total_conversations"] = int(conv_row[0] or 0)

            # 3. Thống kê tin nhắn và chất lượng trích dẫn
            cur.execute(
                """
                SELECT role, query_type, latency_ms, fallback_used, citations, metadata, created_at
                FROM messages
                ORDER BY created_at ASC;
                """
            )
            rows = cur.fetchall()

            latencies: list[int] = []
            recent_latencies: list[dict[str, Any]] = []
            verification_scores: list[float] = []
            grounded_count = 0
            audited_count = 0
            sources_counts: list[int] = []
            fallback_count = 0
            q_breakdown: dict[str, int] = {}
            ans_seq = 0

            for role, q_type, lat_ms, fb_used, cites, meta, _ in rows:
                if role == "user":
                    summary["total_user_queries"] += 1
                elif role == "assistant":
                    summary["total_assistant_answers"] += 1
                    ans_seq += 1
                    q_label = str(q_type or "factual").lower()
                    q_breakdown[q_label] = q_breakdown.get(q_label, 0) + 1

                    src_len = 0
                    if isinstance(cites, list):
                        src_len = len(cites)
                        sources_counts.append(src_len)
                    elif isinstance(cites, str):
                        try:
                            parsed_c = json.loads(cites)
                            if isinstance(parsed_c, list):
                                src_len = len(parsed_c)
                                sources_counts.append(src_len)
                        except Exception:
                            pass

                    if isinstance(lat_ms, (int, float)) and lat_ms > 0:
                        lat_int = int(lat_ms)
                        latencies.append(lat_int)
                        recent_latencies.append(
                            {
                                "Lượt": f"#{ans_seq}",
                                "Độ trễ (ms)": lat_int,
                                "Số chunks": src_len,
                                "Loại": q_label,
                            }
                        )
                    if fb_used:
                        fallback_count += 1

                    meta_dict = meta if isinstance(meta, dict) else {}
                    if isinstance(meta, str):
                        try:
                            meta_dict = json.loads(meta)
                        except Exception:
                            meta_dict = {}
                    audit = meta_dict.get("citation_audit") if isinstance(meta_dict, dict) else None
                    if isinstance(audit, dict):
                        audited_count += 1
                        if audit.get("is_grounded", True):
                            grounded_count += 1
                        v_score = audit.get("verification_score")
                        if isinstance(v_score, (int, float)):
                            verification_scores.append(float(v_score) * 100.0)

            ans_total = summary["total_assistant_answers"]
            if latencies:
                sorted_lat = sorted(latencies)
                summary["avg_latency_ms"] = int(sum(sorted_lat) / len(sorted_lat))
                p95_idx = min(len(sorted_lat) - 1, max(0, int(len(sorted_lat) * 0.95) - 1))
                summary["p95_latency_ms"] = int(sorted_lat[p95_idx])
            summary["recent_latencies"] = recent_latencies[-25:]
            summary["audited_count"] = audited_count
            summary["grounded_count"] = grounded_count
            summary["ungrounded_count"] = max(0, audited_count - grounded_count)
            if audited_count > 0:
                summary["grounded_rate_percent"] = round(grounded_count / audited_count * 100.0, 1)
            if verification_scores:
                summary["avg_verification_score"] = round(
                    sum(verification_scores) / len(verification_scores),
                    1,
                )
            if sources_counts:
                summary["avg_sources_per_answer"] = round(
                    sum(sources_counts) / len(sources_counts),
                    1,
                )
            summary["fallback_count"] = fallback_count
            if ans_total > 0:
                summary["fallback_rate_percent"] = round(fallback_count / ans_total * 100.0, 1)
            summary["query_type_breakdown"] = q_breakdown

            # 4. Thống kê phản hồi người dùng (feedback)
            cur.execute("SELECT rating, COUNT(*) FROM feedback GROUP BY rating;")
            fb_rows = cur.fetchall()
            helpful = 0
            unhelpful = 0
            for r_name, cnt in fb_rows:
                r_clean = str(r_name or "").lower()
                if r_clean in ("helpful", "positive"):
                    helpful += int(cnt or 0)
                else:
                    unhelpful += int(cnt or 0)
            total_fb = helpful + unhelpful
            summary["feedback_total"] = total_fb
            summary["feedback_helpful"] = helpful
            summary["feedback_unhelpful"] = unhelpful
            if total_fb > 0:
                summary["satisfaction_rate_percent"] = round(helpful / total_fb * 100.0, 1)

    except Exception as e:
        logger.warning("Không thể lấy thống kê đánh giá hệ thống: %s", e)
    finally:
        if conn and not conn.closed:
            conn.close()

    return summary


_cache_table_ready = False


def _ensure_query_cache_table(conn: psycopg2.extensions.connection) -> None:
    """Đảm bảo bảng query_cache đã tồn tại trong PostgreSQL."""
    global _cache_table_ready
    if _cache_table_ready:
        return
    with conn.cursor() as cur:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS query_cache (
                cache_key VARCHAR(64) PRIMARY KEY,
                normalized_query TEXT NOT NULL,
                original_query TEXT NOT NULL,
                top_k INTEGER NOT NULL DEFAULT 5,
                answer TEXT NOT NULL,
                sources JSONB NOT NULL DEFAULT '[]'::jsonb,
                query_type VARCHAR(50),
                fallback_used BOOLEAN NOT NULL DEFAULT FALSE,
                citation_audit JSONB,
                hit_count INTEGER NOT NULL DEFAULT 0,
                created_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                last_hit_at TIMESTAMPTZ NOT NULL DEFAULT NOW()
            );
            CREATE INDEX IF NOT EXISTS idx_query_cache_normalized ON query_cache(normalized_query, top_k);
            CREATE INDEX IF NOT EXISTS idx_query_cache_hit_count ON query_cache(hit_count DESC, last_hit_at DESC);
            """
        )
    conn.commit()
    _cache_table_ready = True


def normalize_cache_query(query: str) -> str:
    """
    Chuẩn hóa câu hỏi để tra cứu Cache chính xác ngay cả khi khác dấu câu,
    chữ hoa/thường hoặc các từ đệm mở đầu ('cho em hỏi', 'xin hỏi'...).

    Args:
        query: Câu hỏi gốc của người dùng.

    Returns:
        str: Chuỗi câu hỏi đã chuẩn hóa.
    """
    if not query:
        return ""
    clean = query.strip().lower()
    clean = re.sub(
        r"^(cho\s+em\s+hỏi|cho\s+tôi\s+hỏi|thầy\s+cô\s+cho\s+em\s+hỏi|xin\s+hỏi|em\s+muốn\s+hỏi|tôi\s+muốn\s+hỏi)\s*[:,]?\s*",
        "",
        clean,
        flags=re.IGNORECASE,
    )
    clean = re.sub(r"[?!.,;:]+$", "", clean)
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean


def make_query_cache_key(query: str, top_k: int = 5) -> tuple[str, str]:
    """Tạo khóa băm SHA-256 duy nhất từ câu hỏi đã chuẩn hóa và top_k."""
    import hashlib

    norm = normalize_cache_query(query)
    raw = f"{norm}|top_k={int(top_k)}"
    digest = hashlib.sha256(raw.encode("utf-8")).hexdigest()
    return digest, norm


def get_cached_query_response(query: str, top_k: int = 5) -> Optional[dict[str, Any]]:
    """
    Tra cứu câu hỏi trong bảng query_cache của PostgreSQL.
    Nếu tìm thấy, tự động tăng bộ đếm hit_count và cập nhật last_hit_at.

    Args:
        query: Câu hỏi của người dùng.
        top_k: Số lượng chunks hạt giống.

    Returns:
        Optional[dict]: Dữ liệu phản hồi đã cache hoặc None nếu chưa có.
    """
    cache_key, norm_q = make_query_cache_key(query, top_k)
    if not norm_q:
        return None

    conn = None
    try:
        conn = connect_db()
        _ensure_query_cache_table(conn)
        sql = """
        UPDATE query_cache
        SET hit_count = hit_count + 1,
            last_hit_at = NOW()
        WHERE cache_key = %s
        RETURNING answer, sources, query_type, fallback_used, citation_audit, hit_count;
        """
        with conn.cursor() as cur:
            cur.execute(sql, (cache_key,))
            row = cur.fetchone()
            conn.commit()

        if not row:
            return None

        sources_val = row[1]
        if isinstance(sources_val, str):
            try:
                sources_val = json.loads(sources_val)
            except Exception:
                sources_val = []
        elif sources_val is None:
            sources_val = []

        audit_val = row[4]
        if isinstance(audit_val, str):
            try:
                audit_val = json.loads(audit_val)
            except Exception:
                audit_val = None

        return {
            "answer": row[0],
            "sources": sources_val,
            "query_type": row[2] or "factual",
            "fallback_used": bool(row[3]),
            "citation_audit": audit_val,
            "cache_hit": True,
            "cache_layer": "postgresql",
            "hit_count": int(row[5] or 1),
        }
    except Exception as e:
        if conn:
            conn.rollback()
        logger.warning("Không thể đọc query_cache từ PostgreSQL: %s", e)
        return None
    finally:
        if conn and not conn.closed:
            conn.close()


def save_cached_query_response(
    query: str,
    top_k: int,
    response_data: dict[str, Any],
) -> None:
    """
    Lưu trữ câu hỏi và câu trả lời hoàn chỉnh vào bảng query_cache trong PostgreSQL.

    Args:
        query: Câu hỏi gốc của người dùng.
        top_k: Tham số top_k.
        response_data: Kết quả trả về từ RAG pipeline.
    """
    cache_key, norm_q = make_query_cache_key(query, top_k)
    answer = str(response_data.get("answer") or "").strip()
    if not norm_q or not answer:
        return

    conn = None
    try:
        conn = connect_db()
        _ensure_query_cache_table(conn)
        sql = """
        INSERT INTO query_cache (
            cache_key, normalized_query, original_query, top_k,
            answer, sources, query_type, fallback_used, citation_audit,
            hit_count, created_at, last_hit_at
        )
        VALUES (%s, %s, %s, %s, %s, %s::jsonb, %s, %s, %s::jsonb, 0, NOW(), NOW())
        ON CONFLICT (cache_key) DO UPDATE SET
            answer = EXCLUDED.answer,
            sources = EXCLUDED.sources,
            query_type = EXCLUDED.query_type,
            fallback_used = EXCLUDED.fallback_used,
            citation_audit = EXCLUDED.citation_audit,
            last_hit_at = NOW();
        """
        with conn.cursor() as cur:
            cur.execute(
                sql,
                (
                    cache_key,
                    norm_q,
                    query.strip(),
                    int(top_k),
                    answer,
                    json.dumps(response_data.get("sources") or [], ensure_ascii=False),
                    response_data.get("query_type") or "factual",
                    bool(response_data.get("fallback_used", False)),
                    json.dumps(response_data.get("citation_audit") or {}, ensure_ascii=False),
                ),
            )
            conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        logger.warning("Không thể lưu vào bảng query_cache: %s", e)
    finally:
        if conn and not conn.closed:
            conn.close()


def list_cached_queries(limit: int = 50) -> list[dict[str, Any]]:
    """
    Lấy danh sách các câu hỏi đã được lưu trong query_cache để hiển thị và quản lý trên UI.
    """
    conn = None
    try:
        conn = connect_db()
        _ensure_query_cache_table(conn)
        sql = """
        SELECT cache_key, original_query, normalized_query, top_k,
               query_type, jsonb_array_length(sources) AS sources_cnt,
               hit_count, created_at, last_hit_at
        FROM query_cache
        ORDER BY hit_count DESC, last_hit_at DESC
        LIMIT %s;
        """
        with conn.cursor() as cur:
            cur.execute(sql, (max(1, int(limit)),))
            rows = cur.fetchall()
        return [
            {
                "cache_key": r[0],
                "original_query": r[1],
                "normalized_query": r[2],
                "top_k": int(r[3] or 5),
                "query_type": r[4] or "factual",
                "sources_count": int(r[5] or 0),
                "hit_count": int(r[6] or 0),
                "created_at": r[7].isoformat() if hasattr(r[7], "isoformat") else str(r[7]),
                "last_hit_at": r[8].isoformat() if hasattr(r[8], "isoformat") else str(r[8]),
            }
            for r in rows
        ]
    except Exception as e:
        logger.warning("Không thể đọc danh sách query_cache: %s", e)
        return []
    finally:
        if conn and not conn.closed:
            conn.close()


def clear_query_cache_db() -> int:
    """Xóa toàn bộ các bản ghi trong bảng query_cache khi quản trị viên cần làm mới."""
    conn = None
    try:
        conn = connect_db()
        _ensure_query_cache_table(conn)
        with conn.cursor() as cur:
            cur.execute("DELETE FROM query_cache;")
            deleted = cur.rowcount or 0
            conn.commit()
        return int(deleted)
    except Exception as e:
        if conn:
            conn.rollback()
        logger.warning("Không thể xóa bảng query_cache: %s", e)
        return 0
    finally:
        if conn and not conn.closed:
            conn.close()
