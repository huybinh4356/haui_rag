"""Router xử lý API chat tra cứu quy chế HaUI."""

import logging
import uuid
from fastapi import APIRouter, HTTPException, status

from backend.models.schemas import ChatRequest, ChatResponse, Source
from haui_rag.core.rag_pipeline import rag_query

logger = logging.getLogger("haui_rag")
router = APIRouter(prefix="/api", tags=["Chat"])


@router.post(
    "/chat",
    response_model=ChatResponse,
    status_code=status.HTTP_200_OK,
    summary="Tra cứu quy chế và sinh câu trả lời",
    description="Nhận câu hỏi, tìm kiếm chunks tương đồng trong PostgreSQL và sinh câu trả lời qua Gemini.",
)
def chat_endpoint(request: ChatRequest) -> ChatResponse:
    """
    Xử lý truy vấn câu hỏi người dùng qua RAG pipeline.

    Args:
        request: Dữ liệu câu hỏi và top_k cần lấy.

    Returns:
        ChatResponse: Câu trả lời kèm trích dẫn nguồn văn bản.

    Raises:
        HTTPException: Nếu có lỗi không mong muốn trong quá trình xử lý.
    """
    question = request.question.strip()
    if not question:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Câu hỏi không được để trống.",
        )

    conversation_id = request.conversation_id
    request_id = f"req_{uuid.uuid4().hex[:12]}"
    user_msg_id = None
    assistant_msg_id = None

    # Nếu có conversation_id, lưu tin nhắn người dùng TRƯỚC KHI gọi RAG
    if conversation_id:
        from haui_rag.db.conversation_queries import (
            get_conversation,
            save_assistant_message,
            save_request_log,
            save_user_message,
        )
        conv = get_conversation(conversation_id)
        if not conv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Không tìm thấy cuộc trò chuyện: {conversation_id}",
            )
        try:
            u_msg = save_user_message(
                conversation_id=conversation_id,
                content=question,
                request_id=request_id,
            )
            user_msg_id = u_msg.get("id")
        except Exception as e:
            logger.error("Lỗi khi lưu tin nhắn user trong /chat: %s", e)

    try:
        logger.info("Nhận yêu cầu tra cứu từ API: '%s' (top_k=%d)", question, request.top_k)
        result = rag_query(query=question, top_k=request.top_k)

        # Chuyển đổi danh sách sources thành pydantic Source models
        sources = [
            Source(
                chunk_id=s.get("chunk_id"),
                citation=s.get("citation", "Quy chế HaUI"),
                ma_van_ban=s.get("ma_van_ban"),
                ten_van_ban=s.get("ten_van_ban"),
                dieu=s.get("dieu"),
                khoan=s.get("khoan"),
                distance=s.get("distance"),
                source_type=s.get("source_type", "database"),
                content=s.get("content"),
                metadata=s.get("metadata", {}),
            )
            for s in result.get("sources", [])
        ]

        answer_text = result.get("answer", "")
        resp_time_ms = result.get("response_time_ms", 0)

        # Nếu có conversation_id, lưu tin nhắn assistant
        if conversation_id:
            try:
                citations_data = [s.model_dump() for s in sources]
                a_msg = save_assistant_message(
                    conversation_id=conversation_id,
                    content=answer_text,
                    request_id=request_id,
                    query_type=result.get("query_type"),
                    latency_ms=resp_time_ms,
                    fallback_used=result.get("fallback_used", False),
                    citations=citations_data,
                    metadata={"citation_audit": result.get("citation_audit")},
                )
                assistant_msg_id = a_msg.get("id")

                save_request_log(
                    request_id=request_id,
                    conversation_id=conversation_id,
                    endpoint="/api/chat",
                    status_code=200,
                    latencies={"total_latency_ms": resp_time_ms},
                    fallback_used=result.get("fallback_used", False),
                    metadata={"query_type": result.get("query_type")},
                )
            except Exception as e:
                logger.error("Lỗi khi lưu tin nhắn assistant trong /chat: %s", e)

        return ChatResponse(
            answer=answer_text,
            sources=sources,
            response_time_ms=resp_time_ms,
            query_type=result.get("query_type"),
            fallback_used=result.get("fallback_used", False),
            citation_audit=result.get("citation_audit"),
            error=result.get("error"),
            conversation_id=conversation_id,
            message_id=assistant_msg_id,
        )
    except Exception as e:
        logger.error("Lỗi khi xử lý endpoint /api/chat: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi máy chủ khi xử lý tra cứu: {str(e)}",
        ) from e


@router.post(
    "/feedback",
    response_model=dict,
    status_code=status.HTTP_200_OK,
    summary="Tiếp nhận phản hồi người dùng",
    description="Ghi nhận đánh giá chất lượng câu trả lời để cải thiện hệ thống tra cứu quy chế.",
)
def feedback_endpoint(request: dict) -> dict:
    """
    Tiếp nhận và ghi nhận đánh giá của người dùng vào nhật ký kiểm toán (Audit Log).

    Args:
        request: Thông tin đánh giá gồm rating, reason, comment, question, answer, message_id.

    Returns:
        dict: Trạng thái tiếp nhận thành công.
    """
    message_id = request.get("message_id")
    rating = request.get("rating", "helpful")
    reason = request.get("reason", "")
    comment = request.get("comment", "")
    logger.info(
        "Nhận phản hồi người dùng: msg_id=%s, rating=%s, reason=%s, comment=%s",
        message_id,
        rating,
        reason,
        comment,
    )

    if message_id:
        try:
            from haui_rag.db.conversation_queries import save_feedback
            save_feedback(message_id=message_id, rating=rating, reason=reason, comment=comment)
        except Exception as e:
            logger.warning("Không thể lưu feedback vào DB: %s", e)

    return {"status": "success", "message": "Cảm ơn bạn đã gửi phản hồi đóng góp ý kiến."}
