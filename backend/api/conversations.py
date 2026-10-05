"""API Router quản lý phiên hội thoại và tin nhắn lưu trữ cơ sở dữ liệu.

Phân tách rạch ròi:
- Dữ liệu hội thoại (conversations, messages, feedback, request_logs) thuộc Application Domain.
- Dữ liệu tri thức (documents, embeddings, pgvector) thuộc RAG Knowledge Domain.
- Thao tác mở/đọc lịch sử hội thoại là ĐỌC THUẦN DB: KHÔNG gọi RAG, KHÔNG embedding, KHÔNG gọi LLM.
"""

from datetime import datetime
import logging
import time
from typing import Any, Optional
import uuid

from fastapi import APIRouter, HTTPException, status

from backend.models.schemas import (
    ConversationCreateRequest,
    ConversationResponse,
    ConversationSummary,
    FeedbackRequest,
    FeedbackResponse,
    MessageItem,
    SendMessageRequest,
    SendMessageResponse,
)
from haui_rag.core.rag_pipeline import rag_query
from haui_rag.db.conversation_queries import (
    create_conversation,
    delete_conversation,
    get_conversation,
    get_conversation_messages,
    list_conversations,
    save_assistant_message,
    save_feedback,
    save_request_log,
    save_user_message,
)

logger = logging.getLogger("haui_rag.api.conversations")
router = APIRouter(tags=["Conversations"])


# 1. TẠO CUỘC TRÒ CHUYỆN MỚI
@router.post(
    "/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Tạo phiên hội thoại mới",
)
@router.post(
    "/api/conversations",
    response_model=ConversationResponse,
    status_code=status.HTTP_201_CREATED,
    include_in_schema=False,
)
def create_conversation_endpoint(
    req: Optional[ConversationCreateRequest] = None,
) -> ConversationResponse:
    """Tạo cuộc trò chuyện mới trong cơ sở dữ liệu."""
    title = (req.title if req and req.title else "Cuộc trò chuyện mới").strip()
    try:
        conv = create_conversation(title=title)
        return ConversationResponse(**conv)
    except Exception as e:
        logger.error("Lỗi khi tạo cuộc trò chuyện: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Không thể khởi tạo cuộc trò chuyện: {str(e)}",
        ) from e


# 2. LẤY DANH SÁCH TÓM TẮT CUỘC TRÒ CHUYỆN (CHO SIDEBAR)
@router.get(
    "/conversations",
    response_model=list[ConversationSummary],
    status_code=status.HTTP_200_OK,
    summary="Lấy danh sách tóm tắt hội thoại",
)
@router.get(
    "/api/conversations",
    response_model=list[ConversationSummary],
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def list_conversations_endpoint(
    limit: int = 50,
    offset: int = 0,
) -> list[ConversationSummary]:
    """
    Lấy danh sách tóm tắt các cuộc hội thoại, sắp xếp updated_at DESC.
    Không tải tin nhắn để tối ưu hiệu năng.
    """
    try:
        convs = list_conversations(limit=limit, offset=offset)
        return [
            ConversationSummary(
                id=c["id"],
                title=c["title"],
                updated_at=c["updated_at"],
                message_count=c["message_count"],
            )
            for c in convs
        ]
    except Exception as e:
        logger.error("Lỗi khi lấy danh sách cuộc trò chuyện: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Không thể tải danh sách cuộc trò chuyện: {str(e)}",
        ) from e


# 3. LẤY THÔNG TIN CHI TIẾT CUỘC TRÒ CHUYỆN
@router.get(
    "/conversations/{conversation_id}",
    response_model=ConversationResponse,
    status_code=status.HTTP_200_OK,
    summary="Lấy metadata cuộc trò chuyện",
)
@router.get(
    "/api/conversations/{conversation_id}",
    response_model=ConversationResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def get_conversation_endpoint(conversation_id: str) -> ConversationResponse:
    """Lấy thông tin chi tiết của một cuộc trò chuyện theo UUID."""
    conv = get_conversation(conversation_id)
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy cuộc trò chuyện: {conversation_id}",
        )
    return ConversationResponse(**conv)


# 4. LẤY LỊCH SỬ TIN NHẮN (ĐỌC THUẦN CƠ SỞ DỮ LIỆU)
@router.get(
    "/conversations/{conversation_id}/messages",
    response_model=list[MessageItem],
    status_code=status.HTTP_200_OK,
    summary="Lấy danh sách tin nhắn của cuộc trò chuyện",
)
@router.get(
    "/api/conversations/{conversation_id}/messages",
    response_model=list[MessageItem],
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def get_conversation_messages_endpoint(conversation_id: str) -> list[MessageItem]:
    """
    Lấy toàn bộ tin nhắn thuộc cuộc trò chuyện theo thứ tự created_at ASC.
    ĐÂY LÀ THAO TÁC ĐỌC THUẦN CƠ SỞ DỮ LIỆU:
    - KHÔNG chạy RAG pipeline
    - KHÔNG sinh embedding
    - KHÔNG gọi Gemini / LLM
    - KHÔNG tiêu tốn quota AI
    """
    conv = get_conversation(conversation_id)
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy cuộc trò chuyện: {conversation_id}",
        )

    try:
        messages = get_conversation_messages(conversation_id)
        return [
            MessageItem(
                id=m["id"],
                role=m["role"],
                content=m["content"],
                created_at=m["created_at"],
                citations=m.get("citations") or [],
                query_type=m.get("query_type"),
                latency_ms=m.get("latency_ms"),
                fallback_used=m.get("fallback_used", False),
                metadata=m.get("metadata") or {},
            )
            for m in messages
        ]
    except Exception as e:
        logger.error("Lỗi khi đọc tin nhắn hội thoại %s: %s", conversation_id, e)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Không thể đọc tin nhắn hội thoại: {str(e)}",
        ) from e


# 5. XÓA CUỘC TRÒ CHUYỆN
@router.delete(
    "/conversations/{conversation_id}",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    summary="Xóa cuộc trò chuyện",
)
@router.delete(
    "/api/conversations/{conversation_id}",
    response_model=dict[str, Any],
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def delete_conversation_endpoint(conversation_id: str) -> dict[str, Any]:
    """
    Xóa cuộc trò chuyện theo UUID.
    Toàn bộ tin nhắn liên quan sẽ tự động bị xóa nhờ ON DELETE CASCADE.
    """
    conv = get_conversation(conversation_id)
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy cuộc trò chuyện: {conversation_id}",
        )

    success = delete_conversation(conversation_id)
    if not success:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Không thể xóa cuộc trò chuyện khỏi cơ sở dữ liệu",
        )

    return {
        "status": "success",
        "message": "Đã xóa cuộc trò chuyện thành công",
        "id": conversation_id,
    }


# 6. GỬI TIN NHẮN VÀO CUỘC TRÒ CHUYỆN (RUN RAG PIPELINE)
@router.post(
    "/conversations/{conversation_id}/messages",
    response_model=SendMessageResponse,
    status_code=status.HTTP_200_OK,
    summary="Gửi câu hỏi và sinh câu trả lời trong cuộc trò chuyện",
)
@router.post(
    "/api/conversations/{conversation_id}/messages",
    response_model=SendMessageResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def send_message_endpoint(
    conversation_id: str,
    req: SendMessageRequest,
) -> SendMessageResponse:
    """
    Xử lý gửi câu hỏi của người dùng vào cuộc trò chuyện:
    1. Kiểm tra cuộc trò chuyện tồn tại.
    2. Khởi tạo request_id duy nhất.
    3. Lưu tin nhắn người dùng vào PostgreSQL TRƯỚC KHI gọi RAG (bảo toàn yêu cầu nếu RAG lỗi).
    4. Gọi RAG pipeline tìm kiếm và sinh câu trả lời.
    5. Lưu tin nhắn assistant cùng trích dẫn nguồn có cấu trúc vào PostgreSQL.
    6. Ghi nhật ký vận hành request_logs.
    7. Trả về kết quả hoàn chỉnh cho người dùng.
    """
    conv = get_conversation(conversation_id)
    if not conv:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Không tìm thấy cuộc trò chuyện: {conversation_id}",
        )

    content = req.content.strip()
    if not content:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Nội dung câu hỏi không được để trống.",
        )

    request_id = f"req_{uuid.uuid4().hex[:12]}"
    start_time = time.perf_counter()

    # BƯỚC 1: Lưu tin nhắn người dùng trước
    try:
        user_msg = save_user_message(
            conversation_id=conversation_id,
            content=content,
            request_id=request_id,
        )
        logger.info(
            "Đã lưu tin nhắn người dùng: req_id=%s, conv_id=%s, msg_id=%s",
            request_id,
            conversation_id,
            user_msg["id"],
        )
    except Exception as e:
        logger.error("Không thể lưu tin nhắn người dùng vào DB: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi khi lưu câu hỏi: {str(e)}",
        ) from e

    # BƯỚC 2: Gọi RAG pipeline
    rag_error: Optional[str] = None
    rag_result: dict[str, Any] = {}
    try:
        rag_result = rag_query(query=content, top_k=req.top_k or 5)
    except Exception as e:
        rag_error = str(e)
        logger.error(
            "RAG pipeline gặp lỗi cho req_id=%s: %s",
            request_id,
            e,
            exc_info=True,
        )

    total_latency_ms = int((time.perf_counter() - start_time) * 1000)

    # Nếu RAG pipeline gặp lỗi nghiêm trọng
    if rag_error:
        # Ghi request log lỗi
        save_request_log(
            request_id=request_id,
            conversation_id=conversation_id,
            endpoint=f"/conversations/{conversation_id}/messages",
            status_code=500,
            latencies={"total_latency_ms": total_latency_ms},
            fallback_used=False,
            metadata={"error": rag_error},
        )
        # Người dùng vẫn giữ được câu hỏi trong DB, trả về lỗi có request_id
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Lỗi xử lý câu hỏi quy chế (request_id={request_id}): {rag_error}",
        )

    # BƯỚC 3: Trích xuất kết quả RAG và chuẩn hóa citations
    answer_text = rag_result.get("answer", "Xin lỗi, tôi không tìm thấy quy định này trong hệ thống.")
    sources_raw = rag_result.get("sources", [])
    citations_data = [
        {
            "chunk_id": s.get("chunk_id"),
            "citation": s.get("citation", "Quy chế HaUI"),
            "ma_van_ban": s.get("ma_van_ban"),
            "ten_van_ban": s.get("ten_van_ban"),
            "dieu": s.get("dieu"),
            "khoan": s.get("khoan"),
            "distance": s.get("distance"),
            "source_type": s.get("source_type", "database"),
            "content": s.get("content"),
        }
        for s in sources_raw
    ]

    # BƯỚC 4: Lưu tin nhắn Assistant vào PostgreSQL
    try:
        assistant_msg = save_assistant_message(
            conversation_id=conversation_id,
            content=answer_text,
            request_id=request_id,
            query_type=rag_result.get("query_type"),
            latency_ms=total_latency_ms,
            fallback_used=rag_result.get("fallback_used", False),
            citations=citations_data,
            metadata={"citation_audit": rag_result.get("citation_audit")},
        )
    except Exception as e:
        logger.error("Lỗi khi lưu tin nhắn trợ lý vào DB: %s", e, exc_info=True)
        # Vẫn trả về câu trả lời cho người dùng kèm cảnh báo
        assistant_msg = {
            "id": f"tmp_{uuid.uuid4().hex[:8]}",
            "role": "assistant",
            "content": answer_text,
            "created_at": datetime.now().isoformat(),
        }

    # BƯỚC 5: Ghi nhật ký vận hành request_logs
    save_request_log(
        request_id=request_id,
        conversation_id=conversation_id,
        endpoint=f"/conversations/{conversation_id}/messages",
        status_code=200,
        latencies={"total_latency_ms": total_latency_ms},
        fallback_used=rag_result.get("fallback_used", False),
        metadata={
            "query_type": rag_result.get("query_type"),
            "sources_count": len(citations_data),
        },
    )

    msg_item = MessageItem(
        id=assistant_msg["id"],
        role="assistant",
        content=assistant_msg["content"],
        created_at=assistant_msg["created_at"],
        citations=citations_data,
        query_type=rag_result.get("query_type"),
        latency_ms=total_latency_ms,
        fallback_used=rag_result.get("fallback_used", False),
        metadata={"citation_audit": rag_result.get("citation_audit")},
    )

    return SendMessageResponse(
        message=msg_item,
        citations=citations_data,
        request_id=request_id,
        latency_ms=total_latency_ms,
        fallback_used=rag_result.get("fallback_used", False),
    )


# 7. TIẾP NHẬN PHẢN HỒI (FEEDBACK)
@router.post(
    "/conversations/{conversation_id}/messages/{message_id}/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_200_OK,
    summary="Gửi đánh giá cho tin nhắn trợ lý",
)
@router.post(
    "/api/conversations/{conversation_id}/messages/{message_id}/feedback",
    response_model=FeedbackResponse,
    status_code=status.HTTP_200_OK,
    include_in_schema=False,
)
def message_feedback_endpoint(
    conversation_id: str,
    message_id: str,
    req: FeedbackRequest,
) -> FeedbackResponse:
    """Ghi nhận đánh giá phản hồi vào bảng feedback cho mục đích kiểm thử RAG sau này."""
    try:
        fb = save_feedback(
            message_id=message_id,
            rating=req.rating,
            reason=req.reason,
            comment=req.comment,
        )
        return FeedbackResponse(
            status="success",
            message="Cảm ơn bạn đã gửi đánh giá phản hồi.",
            id=fb["id"],
        )
    except Exception as e:
        logger.error("Lỗi khi lưu feedback: %s", e, exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Không thể ghi nhận đánh giá: {str(e)}",
        ) from e
