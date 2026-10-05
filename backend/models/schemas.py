"""Pydantic schemas định nghĩa dữ liệu đầu vào và đầu ra cho API chat."""

from typing import Optional
from pydantic import BaseModel, Field


class ChatRequest(BaseModel):
    """Schema request cho endpoint chat."""

    question: str = Field(
        ...,
        min_length=1,
        max_length=1000,
        description="Câu hỏi của người dùng về quy chế HaUI",
        examples=["Điều kiện tốt nghiệp thạc sĩ là gì?"],
    )
    top_k: Optional[int] = Field(
        default=5,
        ge=1,
        le=10,
        description="Số lượng đoạn văn bản trích dẫn liên quan (1 - 10)",
    )
    conversation_id: Optional[str] = Field(
        default=None,
        description="UUID cuộc trò chuyện nếu muốn liên kết lưu trữ tự động",
    )


class Source(BaseModel):
    """Schema thông tin một nguồn trích dẫn quy chế."""

    chunk_id: Optional[int] = Field(None, description="ID của chunk trong database")
    citation: str = Field(..., description="Trích dẫn dạng chuẩn: [Mã văn bản] - Điều X, Khoản Y")
    ma_van_ban: Optional[str] = Field(None, description="Mã số văn bản quy chế")
    ten_van_ban: Optional[str] = Field(None, description="Tên đầy đủ của văn bản")
    dieu: Optional[str] = Field(None, description="Điều số")
    khoan: Optional[str] = Field(None, description="Khoản số")
    distance: Optional[float] = Field(None, description="Khoảng cách cosine (None nếu nguồn từ web fallback)")
    source_type: Optional[str] = Field("database", description="Loại nguồn trích dẫn: database hoặc web")
    content: Optional[str] = Field(None, description="Nội dung trích đoạn từ văn bản")
    metadata: Optional[dict] = Field(default_factory=dict, description="Metadata mở rộng của văn bản")


class FeedbackRequest(BaseModel):
    """Schema request cho endpoint tiếp nhận đánh giá phản hồi."""

    message_id: Optional[str] = Field(None, description="UUID tin nhắn được đánh giá (nếu có)")
    question: Optional[str] = Field(None, description="Câu hỏi người dùng đã gửi")
    answer: Optional[str] = Field(None, description="Câu trả lời đã nhận được")
    rating: str = Field(..., description="Đánh giá: helpful/unhelpful hoặc positive/negative")
    reason: Optional[str] = Field(None, description="Lý do chi tiết khi chưa hài lòng")
    comment: Optional[str] = Field(None, description="Ý kiến đóng góp của người dùng")
    response_time_ms: Optional[int] = Field(None, description="Thời gian phản hồi tính bằng ms")


class FeedbackResponse(BaseModel):
    """Schema response sau khi tiếp nhận đánh giá."""

    status: str = Field(..., description="Trạng thái xử lý: success")
    message: str = Field(..., description="Thông điệp phản hồi cho người dùng")
    id: Optional[str] = Field(None, description="ID bản ghi feedback")


class ChatResponse(BaseModel):
    """Schema response trả về cho người dùng."""

    answer: str = Field(..., description="Câu trả lời từ trợ lý AI có trích dẫn nguồn")
    sources: list[Source] = Field(default_factory=list, description="Danh sách các tài liệu trích dẫn")
    response_time_ms: int = Field(..., description="Thời gian xử lý tính bằng mili-giây")
    query_type: Optional[str] = Field(None, description="Phân loại câu hỏi (factual, procedural, comparative, out_of_scope)")
    fallback_used: Optional[bool] = Field(False, description="Đánh dấu câu trả lời có sử dụng Search Fallback haui.edu.vn không")
    citation_audit: Optional[dict] = Field(None, description="Kết quả thẩm định tính trung thực trích dẫn tự động")
    error: Optional[str] = Field(None, description="Chi tiết lỗi nếu có sự cố xảy ra")
    conversation_id: Optional[str] = Field(None, description="ID cuộc trò chuyện đã lưu")
    message_id: Optional[str] = Field(None, description="ID tin nhắn assistant đã lưu")


class ConversationCreateRequest(BaseModel):
    """Schema tạo phiên hội thoại mới."""

    title: Optional[str] = Field(default="Cuộc trò chuyện mới", description="Tiêu đề ban đầu")


class ConversationResponse(BaseModel):
    """Schema thông tin chi tiết một cuộc trò chuyện."""

    id: str = Field(..., description="UUID định danh cuộc trò chuyện")
    title: str = Field(..., description="Tiêu đề cuộc trò chuyện")
    created_at: str = Field(..., description="Thời điểm tạo (ISO 8601 UTC)")
    updated_at: str = Field(..., description="Thời điểm cập nhật gần nhất (ISO 8601 UTC)")
    message_count: int = Field(default=0, description="Tổng số tin nhắn trong cuộc trò chuyện")


class ConversationSummary(BaseModel):
    """Schema tóm tắt cuộc trò chuyện cho Sidebar."""

    id: str = Field(..., description="UUID định danh")
    title: str = Field(..., description="Tiêu đề hiển thị")
    updated_at: str = Field(..., description="Thời điểm cập nhật gần nhất (ISO 8601 UTC)")
    message_count: int = Field(..., description="Số lượng tin nhắn")


class SendMessageRequest(BaseModel):
    """Schema gửi câu hỏi mới vào cuộc trò chuyện."""

    content: str = Field(..., min_length=1, max_length=2000, description="Nội dung câu hỏi người dùng")
    top_k: Optional[int] = Field(default=5, ge=1, le=10, description="Số lượng trích dẫn mong muốn")


class MessageItem(BaseModel):
    """Schema một tin nhắn đơn lẻ trong cuộc trò chuyện."""

    id: str = Field(..., description="UUID tin nhắn")
    role: str = Field(..., description="Vai trò: user hoặc assistant")
    content: str = Field(..., description="Nội dung tin nhắn")
    created_at: str = Field(..., description="Thời điểm gửi")
    citations: Optional[list[dict]] = Field(default_factory=list, description="Danh sách trích dẫn đã lưu")
    query_type: Optional[str] = Field(None, description="Loại câu hỏi")
    latency_ms: Optional[int] = Field(None, description="Thời gian xử lý")
    fallback_used: Optional[bool] = Field(False, description="Có dùng fallback không")
    metadata: Optional[dict] = Field(default_factory=dict, description="Metadata mở rộng")


class SendMessageResponse(BaseModel):
    """Schema phản hồi sau khi gửi câu hỏi và hoàn thành RAG pipeline."""

    message: MessageItem = Field(..., description="Thông tin tin nhắn trả lời của trợ lý")
    citations: list[dict] = Field(default_factory=list, description="Danh sách trích dẫn nguồn")
    request_id: str = Field(..., description="Mã định danh yêu cầu request_id")
    latency_ms: int = Field(..., description="Tổng thời gian xử lý (ms)")
    fallback_used: bool = Field(default=False, description="Có sử dụng search fallback hay không")

