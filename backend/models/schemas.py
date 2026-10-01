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


class Source(BaseModel):
    """Schema thông tin một nguồn trích dẫn quy chế."""

    chunk_id: Optional[int] = Field(None, description="ID của chunk trong database")
    citation: str = Field(..., description="Trích dẫn dạng chuẩn: [Mã văn bản] - Điều X, Khoản Y")
    ma_van_ban: Optional[str] = Field(None, description="Mã số văn bản quy chế")
    ten_van_ban: Optional[str] = Field(None, description="Tên đầy đủ của văn bản")
    dieu: Optional[str] = Field(None, description="Điều số")
    distance: Optional[float] = Field(None, description="Khoảng cách cosine (None nếu nguồn từ web fallback)")
    source_type: Optional[str] = Field("database", description="Loại nguồn trích dẫn: database hoặc web")
    content: Optional[str] = Field(None, description="Nội dung trích đoạn từ văn bản")


class ChatResponse(BaseModel):
    """Schema response trả về cho người dùng."""

    answer: str = Field(..., description="Câu trả lời từ trợ lý AI có trích dẫn nguồn")
    sources: list[Source] = Field(default_factory=list, description="Danh sách các tài liệu trích dẫn")
    response_time_ms: int = Field(..., description="Thời gian xử lý tính bằng mili-giây")
    query_type: Optional[str] = Field(None, description="Phân loại câu hỏi (factual, procedural, comparative, out_of_scope)")
    fallback_used: Optional[bool] = Field(False, description="Đánh dấu câu trả lời có sử dụng Search Fallback haui.edu.vn không")
    citation_audit: Optional[dict] = Field(None, description="Kết quả thẩm định tính trung thực trích dẫn tự động")
    error: Optional[str] = Field(None, description="Chi tiết lỗi nếu có sự cố xảy ra")
