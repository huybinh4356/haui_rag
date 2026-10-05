"""Router xử lý API chat tra cứu quy chế HaUI."""

import logging
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

        return ChatResponse(
            answer=result.get("answer", ""),
            sources=sources,
            response_time_ms=result.get("response_time_ms", 0),
            query_type=result.get("query_type"),
            fallback_used=result.get("fallback_used", False),
            citation_audit=result.get("citation_audit"),
            error=result.get("error"),
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
        request: Thông tin đánh giá gồm rating, reason, comment, question, answer.

    Returns:
        dict: Trạng thái tiếp nhận thành công.
    """
    rating = request.get("rating", "helpful")
    reason = request.get("reason", "")
    comment = request.get("comment", "")
    logger.info("Nhận phản hồi người dùng: rating=%s, reason=%s, comment=%s",
                rating, reason, comment)
    return {"status": "success", "message": "Cảm ơn bạn đã gửi phản hồi đóng góp ý kiến."}
